"""
Validation Agent for ADK pipeline with LoopAgent escalation.

This BaseAgent handles:
1. Converting structured JSON (from PVMAPGeneratorAgent) to CSV
2. Running stat_var_processor subprocess for validation
3. Using EventActions(escalate=True) on success to exit the LoopAgent
4. Tracking feedback effectiveness across retry attempts

Key ADK features used:
- BaseAgent for custom async logic
- EventActions.escalate to exit LoopAgent early on success
- Session state for passing data between agents
- Feedback tracker for effectiveness analysis
"""

import logging
import sys
from pathlib import Path
from typing import AsyncGenerator

logger = logging.getLogger(__name__)

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from src.agents.pvmap_generation.schemas import PVMAPOutput, PVMAPRow, PropertyValuePair
from src.agents.pvmap_generation.helpers import (
    convert_pvmap_output_to_csv,
    validate_pvmap_structure,
    save_attempt_response,
    append_llm_call_log,
    update_generation_notes,
)
from src.tools.validation_tool import run_validation
from src.pipeline.validation.feedback_tracker import FeedbackEffectivenessTracker
from src.pipeline.validation.pvmap_repair import (
    repair_pvmap,
    pre_validate_pvmap,
    generate_key_match_report,
)


class ValidationAgent(BaseAgent):
    """
    Agent for validating PVMAP output.

    This agent:
    1. Reads pvmap_output (JSON dict) from session state
    2. Converts it to CSV using deterministic conversion
    3. Runs stat_var_processor subprocess to validate
    4. On SUCCESS: Sets validation_passed=True, continues to QualityEvaluationAgent
    5. On FAILURE: Sets validation_error in state for FeedbackAgent

    ADK State Inputs:
        - pvmap_output: dict - Structured PVMAP from PVMAPGeneratorAgent
        - current_dataset: DatasetInfo - Dataset being processed
        - attempt_number: int - Current attempt (0-indexed)

    ADK State Outputs:
        - validation_success: bool - Whether validation passed
        - validation_passed: bool - Flag for QualityEvaluationAgent
        - validation_error: str - Error message if failed
        - validation_data_rows: int - Number of data rows in output
        - pvmap_csv: str - CSV content
        - pvmap_path: str - Path to saved PVMAP file
        - processed_output_path: str - Path to processed output

    Escalation:
        - On validation SUCCESS: Returns Event with escalate=False (continue to quality eval)
        - On validation FAILURE: Returns Event with escalate=False (continue to feedback)
        - NOTE: QualityEvaluationAgent handles escalation when quality is acceptable
    """

    def __init__(self, name: str = "Validator"):
        """Initialize ValidationAgent."""
        super().__init__(name=name)

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run validation with CSV conversion and subprocess execution.

        On success, escalates to exit the LoopAgent.
        On failure, prepares error state for FeedbackAgent.
        """
        # Get required state
        current_dataset = ctx.session.state.get("current_dataset")
        pvmap_output = ctx.session.state.get("pvmap_output")
        attempt_number = ctx.session.state.get("attempt_number", 0)

        # Validate inputs
        if not current_dataset:
            ctx.session.state["validation_success"] = False
            ctx.session.state["validation_error"] = "No current_dataset in session state"
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="ERROR: Missing current_dataset in state")
                ]),
                actions=EventActions(escalate=False)
            )
            return

        if not pvmap_output:
            ctx.session.state["validation_success"] = False
            ctx.session.state["validation_error"] = "No pvmap_output in session state - Generator may have failed"
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="ERROR: Missing pvmap_output in state - Generator may have failed")
                ]),
                actions=EventActions(escalate=False)
            )
            return

        # =====================================================================
        # Step 1: Convert JSON to CSV (deterministic, no LLM)
        # =====================================================================
        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Converting structured output to CSV (attempt {attempt_number + 1})...")
            ])
        )

        try:
            # Parse pvmap_output dict into PVMAPOutput model
            pvmap_model = self._parse_pvmap_output(pvmap_output)

            # Validate structure before conversion
            structure_warnings = validate_pvmap_structure(pvmap_model)
            if structure_warnings:
                ctx.session.state["structure_warnings"] = structure_warnings
                # Log warnings but continue
                warning_text = "; ".join(structure_warnings[:3])
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Structure warnings: {warning_text}")
                    ])
                )

            # Convert to CSV
            pvmap_csv = convert_pvmap_output_to_csv(pvmap_model)

            # =====================================================================
            # Step 1.5: Repair PVMAP keys + pre-validate structure
            # =====================================================================
            input_file_for_repair = None
            if current_dataset.input_data_files:
                input_file_for_repair = Path(str(current_dataset.input_data_files[0]))

            if input_file_for_repair and input_file_for_repair.exists():
                # Repair key mismatches programmatically
                pvmap_csv, repair_changes = repair_pvmap(pvmap_csv, input_file_for_repair)
                ctx.session.state["pvmap_repair_changes"] = repair_changes
                if repair_changes:
                    changes_preview = "; ".join(repair_changes[:5])
                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text=f"Auto-repaired {len(repair_changes)} key issues: {changes_preview}")
                        ])
                    )

                # Fast pre-validation (milliseconds, not minutes)
                property_vocabulary = ctx.session.state.get("property_vocabulary", {})
                pre_ok, pre_errors = pre_validate_pvmap(
                    pvmap_csv, input_file_for_repair,
                    property_vocabulary=property_vocabulary if property_vocabulary else None
                )
                # Surface informational warnings even when pre-validation passes
                if pre_ok and pre_errors:
                    ctx.session.state["pre_validation_warnings"] = "\n".join(pre_errors)

                if not pre_ok:
                    # Skip expensive subprocess - feed errors back immediately
                    error_msg = "PRE-VALIDATION FAILED (skipping subprocess):\n" + "\n".join(pre_errors)
                    ctx.session.state["validation_success"] = False
                    ctx.session.state["validation_error"] = error_msg
                    ctx.session.state["pvmap_csv"] = pvmap_csv

                    # Save attempt artifacts before early return
                    try:
                        llm_result = ctx.session.state.get("pvmap_llm_result") or {
                            'model': ctx.session.state.get('model', 'unknown'),
                            'text': pvmap_csv or str(pvmap_output),
                        }
                        save_attempt_response(
                            output_dir=Path(current_dataset.output_dir),
                            attempt=attempt_number,
                            llm_result=llm_result,
                            error_feedback=ctx.session.state.get("error_feedback"),
                            pvmap_csv=pvmap_csv,
                            validation_result={"success": False, "error": error_msg}
                        )
                    except Exception:
                        pass  # Don't fail validation due to logging errors

                    yield Event(
                        author=self.name,
                        content=types.Content(parts=[
                            types.Part(text=f"Pre-validation FAILED: {'; '.join(pre_errors[:3])}")
                        ]),
                        actions=EventActions(escalate=False)
                    )
                    return

            ctx.session.state["pvmap_csv"] = pvmap_csv

            # Save to file
            pvmap_path = Path(current_dataset.output_dir) / "generated_pvmap.csv"
            pvmap_path.parent.mkdir(parents=True, exist_ok=True)
            pvmap_path.write_text(pvmap_csv, encoding='utf-8')
            ctx.session.state["pvmap_path"] = str(pvmap_path)

            # Store metadata from structured output
            ctx.session.state["pvmap_format_detected"] = pvmap_model.format_detected
            ctx.session.state["pvmap_confidence"] = pvmap_model.confidence
            ctx.session.state["pvmap_validation_notes"] = pvmap_model.validation_notes

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"CSV saved to {pvmap_path} ({len(pvmap_model.pvmap_rows)} rows)")
                ])
            )

        except Exception as e:
            ctx.session.state["validation_success"] = False
            ctx.session.state["validation_error"] = f"CSV conversion failed: {str(e)}"

            # Save attempt artifacts before early return
            try:
                llm_result = ctx.session.state.get("pvmap_llm_result") or {
                    'model': ctx.session.state.get('model', 'unknown'),
                    'text': str(pvmap_output),
                }
                save_attempt_response(
                    output_dir=Path(current_dataset.output_dir),
                    attempt=attempt_number,
                    llm_result=llm_result,
                    error_feedback=ctx.session.state.get("error_feedback"),
                    pvmap_csv=None,
                    validation_result={"success": False, "error": str(e)}
                )
            except Exception:
                pass  # Don't fail validation due to logging errors

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"ERROR: CSV conversion failed: {e}")
                ]),
                actions=EventActions(escalate=False)
            )
            return

        # =====================================================================
        # Step 2: Run stat_var_processor subprocess validation
        # =====================================================================
        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text="Running stat_var_processor validation...")
            ])
        )

        # Get input file for validation (full dataset, not sampled)
        input_file = None
        if current_dataset.input_data_files:
            input_file = str(current_dataset.input_data_files[0])

        if not input_file or not Path(input_file).exists():
            ctx.session.state["validation_success"] = False
            ctx.session.state["validation_error"] = f"No input data file found for validation"
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="ERROR: No input data file for validation")
                ]),
                actions=EventActions(escalate=False)
            )
            return

        # Get metadata file: prefer auto-generated config (has merged GT/user values + PVMAP-derived params)
        metadata_file = None
        # Tier 1: Auto-generated config from MetadataGenerationAgent (PVMAP-derived + merged values)
        generated_config = ctx.session.state.get("generated_config_path")
        if generated_config and Path(generated_config).exists():
            metadata_file = generated_config
        # Tier 2: User-provided metadata (fallback)
        if not metadata_file and current_dataset.use_metadata and current_dataset.metadata_files:
            metadata_file = str(current_dataset.metadata_files[0])
        # Tier 3: Ground truth metadata (last resort, for benchmarking only)
        if not metadata_file:
            if current_dataset.ground_truth_metadata and Path(current_dataset.ground_truth_metadata).exists():
                gt_meta_dir = Path(current_dataset.ground_truth_metadata)
                gt_meta_files = sorted(gt_meta_dir.glob("*.csv"))
                if gt_meta_files:
                    metadata_file = str(gt_meta_files[0])
        if not metadata_file:
            # Metadata is optional — validation can proceed without it
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Warning: No metadata file found, proceeding without config_file")
                ])
            )

        # Run validation (pass attempt_number for iteration-specific feedback)
        result = run_validation(
            input_data=input_file,
            pvmap_path=str(pvmap_path),
            metadata_file=metadata_file,
            output_dir=str(current_dataset.output_dir),
            timeout=300,  # 5 minute timeout
            attempt_number=attempt_number  # For iteration-specific advice in feedback
        )

        # Store validation results
        ctx.session.state["validation_success"] = result["success"]
        ctx.session.state["validation_data_rows"] = result.get("data_rows", 0)
        ctx.session.state["processed_output_path"] = result.get("output_file", "")
        ctx.session.state["validation_counter_summary"] = result.get("counter_summary", "")
        ctx.session.state["validation_statvar_analysis"] = result.get("statvar_analysis", "")

        # Track best attempt — prefer validated attempts, then most data rows
        current_data_rows = result.get("data_rows", 0)
        best_data_rows = ctx.session.state.get("best_data_rows", 0)
        best_was_valid = ctx.session.state.get("best_validation_passed", False)
        current_is_valid = result["success"]

        # Update best if: (a) more data rows, OR (b) current is valid and best wasn't
        should_update = (
            current_data_rows > best_data_rows
            or (current_is_valid and not best_was_valid)
        )
        if should_update:
            ctx.session.state["best_data_rows"] = current_data_rows
            ctx.session.state["best_pvmap_csv"] = pvmap_csv
            ctx.session.state["best_attempt_number"] = attempt_number
            ctx.session.state["best_validation_passed"] = current_is_valid

        # Generate key match report for feedback agent
        if input_file_for_repair and input_file_for_repair.exists():
            key_match_report = generate_key_match_report(pvmap_csv, input_file_for_repair)
        else:
            key_match_report = ""

        # Append pre-validation warnings (ENUM, schema.org) to key_match_report
        pre_warnings = ctx.session.state.get("pre_validation_warnings", "")
        if pre_warnings:
            key_match_report += f"\n\n## Vocabulary Warnings\n{pre_warnings}"

        ctx.session.state["key_match_report"] = key_match_report

        # =====================================================================
        # Step 3: Save attempt artifacts
        # =====================================================================
        try:
            # Build llm_result dict for logging (from generator state if available)
            llm_result = ctx.session.state.get("pvmap_llm_result") or {
                'model': ctx.session.state.get('model', 'unknown'),
                'text': pvmap_csv or str(pvmap_output),
            }

            save_attempt_response(
                output_dir=Path(current_dataset.output_dir),
                attempt=attempt_number,
                llm_result=llm_result,
                error_feedback=ctx.session.state.get("error_feedback"),
                pvmap_csv=pvmap_csv,
                validation_result=result
            )

            # Append to llm_calls.jsonl if we have prompt info
            prompt_length = len(ctx.session.state.get("pvmap_generation_prompt", ""))
            if prompt_length > 0:
                append_llm_call_log(
                    output_dir=Path(current_dataset.output_dir),
                    attempt=attempt_number,
                    llm_result=llm_result,
                    prompt_length=prompt_length,
                    validation_success=result["success"]
                )
        except Exception as e:
            # Don't fail validation due to logging errors
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Warning: Failed to save artifacts: {e}")
                ])
            )

        # =====================================================================
        # Step 4: Record attempt with feedback tracker
        # =====================================================================
        self._record_attempt_with_tracker(
            ctx=ctx,
            attempt_number=attempt_number,
            result=result,
            pvmap_csv=pvmap_csv
        )

        # =====================================================================
        # Step 5: Handle success or failure
        # =====================================================================
        if result["success"]:
            # Validation passed - set flag for QualityEvaluationAgent
            # NOTE: Do NOT update generation_notes here - QualityEvaluationAgent handles final status
            # NOTE: Do NOT set generation_success here - QualityEvaluationAgent handles that

            ctx.session.state["validation_passed"] = True
            ctx.session.state["error"] = None

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Validation PASSED! {result['data_rows']} data rows generated. Proceeding to quality evaluation.")
                ]),
                actions=EventActions(escalate=False)  # Continue to QualityEvaluationAgent
            )
        else:
            # Validation failed - prepare error for FeedbackAgent
            ctx.session.state["validation_passed"] = False
            error_msg = result.get("error", "Validation failed with unknown error")
            ctx.session.state["validation_error"] = error_msg

            # Update generation notes with failure (not final unless max retries)
            update_generation_notes(
                output_dir=Path(current_dataset.output_dir),
                dataset_name=current_dataset.name,
                attempt=attempt_number,
                llm_result=llm_result,
                pvmap_csv=pvmap_csv,
                validation_result=result,
                final_status=None  # FeedbackAgent or loop exit will set final status
            )

            # Add feedback effectiveness analysis for retry attempts
            if attempt_number > 0:
                self._add_effectiveness_analysis(ctx)

            # Truncate error for display
            error_preview = error_msg[:300] + "..." if len(error_msg) > 300 else error_msg

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Validation FAILED: {error_preview}")
                ]),
                actions=EventActions(escalate=False)  # Continue to FeedbackAgent
            )

    def _parse_pvmap_output(self, pvmap_output: dict) -> PVMAPOutput:
        """
        Parse pvmap_output dict into PVMAPOutput Pydantic model.

        Handles both direct Pydantic dict output and raw dicts.

        Args:
            pvmap_output: Dict from session state (from LlmAgent output_schema)

        Returns:
            PVMAPOutput model instance

        Raises:
            ValueError: If parsing fails
        """
        try:
            # If already a PVMAPOutput, return as-is
            if isinstance(pvmap_output, PVMAPOutput):
                return pvmap_output

            # Build from dict
            pvmap_rows = []
            for row_data in pvmap_output.get("pvmap_rows", []):
                mappings = []
                for m in row_data.get("mappings", []):
                    mappings.append(PropertyValuePair(
                        property=m.get("property", ""),
                        value=m.get("value", "")
                    ))
                pvmap_rows.append(PVMAPRow(
                    key=row_data.get("key", ""),
                    mappings=mappings
                ))

            return PVMAPOutput(
                format_detected=pvmap_output.get("format_detected", "raw"),
                pvmap_rows=pvmap_rows,
                validation_notes=pvmap_output.get("validation_notes", ""),
                confidence=pvmap_output.get("confidence", "medium")
            )

        except Exception as e:
            raise ValueError(f"Failed to parse pvmap_output: {e}") from e

    def _record_attempt_with_tracker(
        self,
        ctx: InvocationContext,
        attempt_number: int,
        result: dict,
        pvmap_csv: str
    ) -> None:
        """Record this attempt with the feedback effectiveness tracker.

        Creates tracker on first attempt, then records each attempt's
        errors, feedback, and quality for effectiveness analysis.

        Args:
            ctx: Invocation context with session state
            attempt_number: Current attempt number (0-indexed)
            result: Validation result dict
            pvmap_csv: PVMAP CSV content
        """
        try:
            current_dataset = ctx.session.state.get("current_dataset")
            if not current_dataset:
                return

            # Get or create feedback tracker
            tracker = ctx.session.state.get("feedback_tracker")
            if not tracker:
                tracker = FeedbackEffectivenessTracker(
                    dataset_name=current_dataset.name
                )
                ctx.session.state["feedback_tracker"] = tracker

            # Get feedback that was given before this attempt
            feedback_given = ctx.session.state.get("error_feedback", "")

            # Get errors from counters
            errors = result.get("counters", {})
            error_counters = {
                k: v for k, v in errors.items()
                if k.startswith('error-') and isinstance(v, (int, float)) and v > 0
            }

            # Get quality score (may not be set yet, defaults to 0)
            quality_score = ctx.session.state.get("quality_metrics", {}).get(
                "pv_accuracy",
                ctx.session.state.get("quality_metrics", {}).get("heuristic_score", 0)
            )

            # Record the attempt
            tracker.record_attempt(
                attempt_number=attempt_number,
                errors=error_counters,
                feedback_given=feedback_given,
                pvmap_csv=pvmap_csv,
                quality_score=quality_score,
                validation_passed=result.get("success", False)
            )

        except Exception:
            # Don't fail validation due to tracker errors
            pass

    def _add_effectiveness_analysis(self, ctx: InvocationContext) -> None:
        """Add feedback effectiveness analysis to session state.

        Analyzes whether previous feedback was addressed and adds
        alternative strategy suggestions if the loop is not making progress.

        Args:
            ctx: Invocation context with session state
        """
        try:
            tracker = ctx.session.state.get("feedback_tracker")
            if not tracker or len(tracker.attempts) < 2:
                return

            # Analyze effectiveness
            effectiveness = tracker.analyze_effectiveness()
            ctx.session.state["feedback_effectiveness"] = effectiveness

            # Check if we need an alternative strategy
            error_changes = effectiveness.get('error_changes', {})
            net_change = error_changes.get('net_change', -1)

            if net_change >= 0:
                # Not making progress - add alternative strategy
                alt_strategy = tracker.get_alternative_strategy()
                if alt_strategy:
                    ctx.session.state["alternative_strategy"] = alt_strategy

            # Add effectiveness report to state for feedback agent
            effectiveness_report = tracker.format_effectiveness_report()
            ctx.session.state["effectiveness_report"] = effectiveness_report

        except Exception:
            # Don't fail on analysis errors
            pass


# ============================================================================
# Module exports
# ============================================================================

__all__ = ['ValidationAgent']
