"""
Quality Evaluation Agent for ADK pipeline.

This BaseAgent evaluates PVMAP quality after validation passes using
heuristic scoring (Score >= 70/100).

Ground truth comparison is intentionally NOT used here to avoid data leakage
into the retry loop. Ground truth evaluation happens only in the final
EvaluationAgent after the retry loop completes.

Key ADK features used:
- BaseAgent for custom evaluation logic
- EventActions.escalate to exit LoopAgent on acceptable quality or stagnation
- Session state for quality metrics tracking across attempts
"""

import sys
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, List, Optional, ClassVar

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from src.tools.heuristic_quality import calculate_heuristic_score, format_quality_report
from src.tools.evaluation_tools import compare_pvmaps

import logging
logger = logging.getLogger(__name__)


class QualityEvaluationAgent(BaseAgent):
    """
    Evaluates PVMAP quality after validation passes using heuristic scoring.

    NOTE: Ground truth comparison is intentionally excluded from the retry loop
    to prevent data leakage. Ground truth is only used in the final EvaluationAgent.

    This agent:
    1. Checks if validation passed (skip if not)
    2. Uses heuristic scoring (row/property/column coverage + format) >= 70/100
    3. Detects stagnation (improvement < 5% between attempts)
    4. Escalates to exit loop if quality acceptable OR stagnant

    ADK State Inputs:
        - validation_passed: bool (must be True to run evaluation)
        - current_dataset: DatasetInfo
        - pvmap_path: str - Path to generated PVMAP
        - pvmap_csv: str - PVMAP CSV content
        - attempt_number: int
        - quality_metrics_history: List[dict] (accumulated across attempts)
        - sampled_data: str - For heuristic scoring
        - metadata: str - For heuristic scoring

    ADK State Outputs:
        - quality_metrics: dict - Current attempt metrics
        - quality_acceptable: bool - Whether quality meets threshold
        - quality_diff_summary: str - Issues summary for feedback
        - quality_stagnant: bool - Whether improvement has stagnated
        - quality_metrics_history: List[dict] - Updated with current metrics
        - exit_reason: str - "quality_met" | "stagnant" | None

    Escalation:
        - escalate=True if quality_acceptable=True OR quality_stagnant=True
        - escalate=False to continue to QualityFeedbackAgent
    """

    # Quality thresholds (ClassVar to avoid Pydantic field treatment)
    QUALITY_THRESHOLD: ClassVar[float] = 70.0  # Heuristic score threshold (out of 100)
    STAGNATION_THRESHOLD: ClassVar[float] = 5.0  # Minimum improvement required between attempts

    def __init__(self, name: str = "QualityEvaluator"):
        """Initialize QualityEvaluationAgent."""
        super().__init__(name=name)

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run quality evaluation.

        On acceptable quality or stagnation, escalates to exit the LoopAgent.
        On low quality, continues to QualityFeedbackAgent.
        """
        # Check if validation passed
        validation_passed = ctx.session.state.get("validation_passed", False)

        if not validation_passed:
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Skipping quality evaluation - validation not passed")
                ]),
                actions=EventActions(escalate=False)
            )
            return

        current_dataset = ctx.session.state.get("current_dataset")
        pvmap_csv = ctx.session.state.get("pvmap_csv", "")
        attempt_number = ctx.session.state.get("attempt_number", 0)

        if not current_dataset:
            ctx.session.state["quality_acceptable"] = False
            ctx.session.state["quality_metrics"] = {"error": "No current_dataset"}
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="ERROR: No current_dataset in state")
                ]),
                actions=EventActions(escalate=False)
            )
            return

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=f"Evaluating quality for attempt {attempt_number + 1}...")
            ])
        )

        # =====================================================================
        # Step 1: Heuristic quality scoring
        # NOTE: Ground truth is intentionally NOT used here to prevent data
        # leakage into the retry loop. GT comparison happens only in the
        # final EvaluationAgent after generation completes.
        # =====================================================================
        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text="Evaluating quality using heuristic scoring...")
            ])
        )
        quality_metrics, quality_acceptable, quality_diff_summary = self._evaluate_with_heuristics(
            ctx, pvmap_csv
        )

        # =====================================================================
        # Step 1b: Ground truth numeric scoring (optional, safe)
        # Only numeric scores are extracted; diff_text is NEVER stored.
        # =====================================================================
        gt_pvmap_path = ctx.session.state.get("gt_pvmap_path_cached")
        if gt_pvmap_path:
            gt_scores = self._evaluate_with_ground_truth(ctx, pvmap_csv)
            if gt_scores:
                quality_metrics.update(gt_scores)
                gt_node = gt_scores.get("gt_node_accuracy", 0)
                gt_pv = gt_scores.get("gt_pv_accuracy", 0)
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"GT scores: Node Acc={gt_node:.1f}%, PV Acc={gt_pv:.1f}%")
                    ])
                )

        # =====================================================================
        # Step 2: Check for stagnation
        # =====================================================================
        metrics_history = ctx.session.state.get("quality_metrics_history", [])
        quality_stagnant = False

        if metrics_history and attempt_number > 0:
            prev_metrics = metrics_history[-1]
            prev_score = prev_metrics.get("heuristic_score", 0)
            curr_score = quality_metrics.get("heuristic_score", 0)
            improvement = curr_score - prev_score
            quality_metrics["improvement_from_previous"] = round(improvement, 1)

            if improvement < self.STAGNATION_THRESHOLD:
                quality_stagnant = True
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Stagnation detected: improvement = {improvement:.1f}% (< {self.STAGNATION_THRESHOLD}%)")
                    ])
                )

        # =====================================================================
        # Step 3: Update state
        # =====================================================================
        quality_metrics["attempt"] = attempt_number
        metrics_history.append(quality_metrics)

        ctx.session.state["quality_metrics_history"] = metrics_history
        ctx.session.state["quality_metrics"] = quality_metrics
        ctx.session.state["quality_acceptable"] = quality_acceptable
        ctx.session.state["quality_stagnant"] = quality_stagnant
        ctx.session.state["quality_diff_summary"] = quality_diff_summary

        # =====================================================================
        # Step 4: Determine escalation
        # =====================================================================
        should_escalate = quality_acceptable or quality_stagnant

        if quality_acceptable:
            ctx.session.state["exit_reason"] = "quality_met"
            ctx.session.state["generation_success"] = True
            ctx.session.state["retry_count"] = attempt_number

            # Update generation notes
            self._update_notes_on_success(ctx, quality_metrics)

            score_value = quality_metrics.get("heuristic_score", 0)
            gt_node = quality_metrics.get("gt_node_accuracy")
            gt_pv = quality_metrics.get("gt_pv_accuracy")
            message = (
                f"Quality ACCEPTABLE (heuristic): {score_value:.1f}/100 >= {self.QUALITY_THRESHOLD} threshold."
            )
            if gt_node is not None:
                message += f" GT: Node={gt_node:.1f}%, PV={gt_pv:.1f}%."
            message += " ESCALATING to exit loop."

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=message)]),
                actions=EventActions(escalate=True)
            )

        elif quality_stagnant:
            ctx.session.state["exit_reason"] = "stagnant"
            ctx.session.state["generation_success"] = True  # Best effort
            ctx.session.state["retry_count"] = attempt_number

            # Update generation notes
            self._update_notes_on_stagnation(ctx, quality_metrics)

            gt_node = quality_metrics.get("gt_node_accuracy")
            gt_pv = quality_metrics.get("gt_pv_accuracy")
            message = (
                f"Quality STAGNANT (improvement < {self.STAGNATION_THRESHOLD}%)."
            )
            if gt_node is not None:
                message += f" GT: Node={gt_node:.1f}%, PV={gt_pv:.1f}%."
            message += " ESCALATING with best effort result."

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=message)]),
                actions=EventActions(escalate=True)
            )

        else:
            score_value = quality_metrics.get("heuristic_score", 0)
            gt_node = quality_metrics.get("gt_node_accuracy")
            gt_pv = quality_metrics.get("gt_pv_accuracy")
            message = (
                f"Quality LOW (heuristic): {score_value:.1f}/100 < {self.QUALITY_THRESHOLD} threshold."
            )
            if gt_node is not None:
                message += f" GT: Node={gt_node:.1f}%, PV={gt_pv:.1f}%."
            message += " Continuing to quality feedback."

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=message)]),
                actions=EventActions(escalate=False)
            )

    def _evaluate_with_heuristics(
        self, ctx: InvocationContext, pvmap_csv: str
    ) -> tuple[Dict[str, Any], bool, str]:
        """
        Evaluate PVMAP quality using heuristic scoring.

        Returns:
            Tuple of (quality_metrics, quality_acceptable, quality_diff_summary)
        """
        sampled_data = ctx.session.state.get("sampled_data", "")
        metadata = ctx.session.state.get("metadata", "")

        heuristic_result = calculate_heuristic_score(
            pvmap_csv=pvmap_csv,
            sampled_data=sampled_data,
            metadata=metadata
        )

        quality_metrics = {
            "heuristic_score": heuristic_result["total"],
            "heuristic_breakdown": {
                "row_coverage": heuristic_result["row_coverage"],
                "prop_coverage": heuristic_result["prop_coverage"],
                "column_coverage": heuristic_result["column_coverage"],
                "format_score": heuristic_result["format_score"],
            },
            "mode": "heuristic"
        }

        quality_acceptable = heuristic_result["total"] >= self.QUALITY_THRESHOLD
        quality_diff_summary = heuristic_result.get("issues", "")

        # Add formatted report for feedback
        if not quality_acceptable:
            quality_diff_summary = format_quality_report(heuristic_result)

        return quality_metrics, quality_acceptable, quality_diff_summary

    def _evaluate_with_ground_truth(
        self, ctx: InvocationContext, pvmap_csv: str
    ) -> dict:
        """
        Compare generated PVMAP against cached ground truth for numeric scoring.

        SAFETY: Only extracts numeric scores and aggregate counters.
        The diff_text is NEVER stored in state or returned.

        Returns:
            Dictionary with gt_node_accuracy, gt_pv_accuracy, gt_counters_summary
            or empty dict if GT not available or comparison fails.
        """
        gt_pvmap_path = ctx.session.state.get("gt_pvmap_path_cached")
        pvmap_path = ctx.session.state.get("pvmap_path")

        if not gt_pvmap_path or not pvmap_path:
            return {}

        if not Path(pvmap_path).exists():
            return {}

        try:
            current_dataset = ctx.session.state.get("current_dataset")
            if current_dataset:
                eval_dir = Path(current_dataset.output_dir) / "loop_eval_temp"
            else:
                eval_dir = Path(pvmap_path).parent / "loop_eval_temp"

            result = compare_pvmaps(
                auto_pvmap_path=str(pvmap_path),
                gt_pvmap_path=gt_pvmap_path,
                output_dir=str(eval_dir)
            )

            if not result["success"]:
                logger.warning(f"GT comparison failed: {result.get('error', 'unknown')}")
                return {}

            # CRITICAL: Extract ONLY numeric scores. DISCARD diff_text.
            counters = result.get("counters", {})

            return {
                "gt_node_accuracy": result.get("accuracy", 0.0),
                "gt_pv_accuracy": result.get("pv_accuracy", 0.0),
                "gt_counters_summary": {
                    "nodes_matched": counters.get("nodes-matched", 0),
                    "nodes_ground_truth": counters.get("nodes-ground-truth", 0),
                    "nodes_auto_generated": counters.get("nodes-auto-generated", 0),
                    "pvs_matched": counters.get("PVs-matched", 0),
                    "pvs_modified": counters.get("pvs-modified", 0),
                    "pvs_deleted": counters.get("pvs-deleted", 0),
                }
            }

        except Exception as e:
            logger.warning(f"GT comparison error (non-fatal): {e}")
            return {}

    def _update_notes_on_success(self, ctx: InvocationContext, metrics: Dict[str, Any]) -> None:
        """Update generation notes on quality success."""
        try:
            from src.agents.pvmap_generation.helpers import update_generation_notes

            current_dataset = ctx.session.state.get("current_dataset")
            if not current_dataset:
                return

            attempt = ctx.session.state.get("attempt_number", 0)
            llm_result = ctx.session.state.get("pvmap_llm_result", {})
            pvmap_csv = ctx.session.state.get("pvmap_csv")

            score = metrics.get("heuristic_score", 0)

            update_generation_notes(
                output_dir=Path(current_dataset.output_dir),
                dataset_name=current_dataset.name,
                attempt=attempt,
                llm_result=llm_result,
                pvmap_csv=pvmap_csv,
                validation_result={"success": True},
                final_status=f"SUCCESS (heuristic quality: {score:.1f}/100) on attempt {attempt + 1}"
            )
        except Exception:
            pass  # Don't fail on logging errors

    def _update_notes_on_stagnation(self, ctx: InvocationContext, metrics: Dict[str, Any]) -> None:
        """Update generation notes on quality stagnation."""
        try:
            from src.agents.pvmap_generation.helpers import update_generation_notes

            current_dataset = ctx.session.state.get("current_dataset")
            if not current_dataset:
                return

            attempt = ctx.session.state.get("attempt_number", 0)
            llm_result = ctx.session.state.get("pvmap_llm_result", {})
            pvmap_csv = ctx.session.state.get("pvmap_csv")

            score = metrics.get("heuristic_score", 0)
            improvement = metrics.get("improvement_from_previous", 0)

            update_generation_notes(
                output_dir=Path(current_dataset.output_dir),
                dataset_name=current_dataset.name,
                attempt=attempt,
                llm_result=llm_result,
                pvmap_csv=pvmap_csv,
                validation_result={"success": True},
                final_status=f"STAGNANT (best effort, heuristic quality: {score:.1f}/100, improvement: {improvement:.1f}%) on attempt {attempt + 1}"
            )
        except Exception:
            pass  # Don't fail on logging errors


# ============================================================================
# Module exports
# ============================================================================

__all__ = ['QualityEvaluationAgent']
