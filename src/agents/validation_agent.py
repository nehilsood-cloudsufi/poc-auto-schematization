"""
Validation Agent for ADK pipeline with LoopAgent escalation.

This BaseAgent handles:
1. Converting structured JSON (from PVMAPGeneratorAgent) to CSV
2. Running stat_var_processor subprocess for validation
3. Using EventActions(escalate=True) on success to exit the LoopAgent

Key ADK features used:
- BaseAgent for custom async logic
- EventActions.escalate to exit LoopAgent early on success
- Session state for passing data between agents
"""

import sys
from pathlib import Path
from typing import AsyncGenerator

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


class ValidationAgent(BaseAgent):
    """
    Agent for validating PVMAP output and escalating on success.

    This agent:
    1. Reads pvmap_output (JSON dict) from session state
    2. Converts it to CSV using deterministic conversion
    3. Runs stat_var_processor subprocess to validate
    4. On SUCCESS: Sets escalate=True to exit LoopAgent immediately
    5. On FAILURE: Sets validation_error in state for FeedbackAgent

    ADK State Inputs:
        - pvmap_output: dict - Structured PVMAP from PVMAPGeneratorAgent
        - current_dataset: DatasetInfo - Dataset being processed
        - attempt_number: int - Current attempt (0-indexed)

    ADK State Outputs:
        - validation_success: bool - Whether validation passed
        - validation_error: str - Error message if failed
        - validation_data_rows: int - Number of data rows in output
        - pvmap_csv: str - CSV content
        - pvmap_path: str - Path to saved PVMAP file
        - processed_output_path: str - Path to processed output

    Escalation:
        - On validation SUCCESS: Returns Event with escalate=True
        - This causes the LoopAgent to exit immediately
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
        elif current_dataset.combined_input_data:
            input_file = str(current_dataset.combined_input_data)

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

        # Get metadata file
        metadata_file = str(current_dataset.combined_metadata) if current_dataset.combined_metadata else None
        if not metadata_file or not Path(metadata_file).exists():
            ctx.session.state["validation_success"] = False
            ctx.session.state["validation_error"] = "No metadata file found"
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="ERROR: No metadata file for validation")
                ]),
                actions=EventActions(escalate=False)
            )
            return

        # Run validation
        result = run_validation(
            input_data=input_file,
            pvmap_path=str(pvmap_path),
            metadata_file=metadata_file,
            output_dir=str(current_dataset.output_dir),
            timeout=300  # 5 minute timeout
        )

        # Store validation results
        ctx.session.state["validation_success"] = result["success"]
        ctx.session.state["validation_data_rows"] = result.get("data_rows", 0)
        ctx.session.state["processed_output_path"] = result.get("output_file", "")

        # =====================================================================
        # Step 3: Save attempt artifacts
        # =====================================================================
        try:
            # Build llm_result dict for logging (from generator state if available)
            llm_result = ctx.session.state.get("pvmap_llm_result", {
                'model': ctx.session.state.get('model', 'unknown'),
                'text': str(pvmap_output),
            })

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
        # Step 4: Handle success or failure
        # =====================================================================
        if result["success"]:
            # Update generation notes with success
            update_generation_notes(
                output_dir=Path(current_dataset.output_dir),
                dataset_name=current_dataset.name,
                attempt=attempt_number,
                llm_result=llm_result,
                pvmap_csv=pvmap_csv,
                validation_result=result,
                final_status=f"SUCCESS on attempt {attempt_number + 1}"
            )

            ctx.session.state["generation_success"] = True
            ctx.session.state["error"] = None
            ctx.session.state["retry_count"] = attempt_number

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Validation PASSED! {result['data_rows']} data rows generated. ESCALATING to exit loop.")
                ]),
                actions=EventActions(escalate=True)  # EXIT LOOP!
            )
        else:
            # Validation failed - prepare error for FeedbackAgent
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


# ============================================================================
# Module exports
# ============================================================================

__all__ = ['ValidationAgent']
