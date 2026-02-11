"""
Quality Evaluation Agent for ADK pipeline.

This BaseAgent evaluates PVMAP quality after validation passes using
a priority-based gating chain:
  Priority 2: PV accuracy >= 30% (when ground truth available)
  Priority 3: Heuristic score >= 70/100

Only numeric PV accuracy is used from ground truth — no content leakage.
When GT is unavailable, falls back to heuristic-only (existing behavior).

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
    Evaluates PVMAP quality after validation passes using priority-based gating.

    Priority chain for retry triggers:
        1. Validation failure (handled upstream) - always retry with error feedback
        2. PV accuracy < 30% (GT required) - retry with quality feedback
        3. Heuristic score < 70/100 - retry with quality feedback
        4. Stagnation (delta < 10% of previous accuracy) - stop, explain reasoning
        5. Max retries >= 3 - stop (safety net, handled downstream)

    Ground truth safety: Only numeric PV accuracy score is used as a trigger.
    GT content (diff_text) is NEVER stored or passed to feedback.

    This agent:
    1. Checks if validation passed (skip if not)
    2. Uses heuristic scoring (row/property/column coverage + format) >= 70/100
    3. Uses PV accuracy >= 30% when ground truth is available (Priority 2)
    4. Detects stagnation on the triggering metric (improvement < 10% of previous accuracy)
    5. Escalates to exit loop if quality acceptable OR stagnant

    ADK State Inputs:
        - validation_passed: bool (must be True to run evaluation)
        - current_dataset: DatasetInfo
        - pvmap_path: str - Path to generated PVMAP
        - pvmap_csv: str - PVMAP CSV content
        - attempt_number: int
        - quality_metrics_history: List[dict] (accumulated across attempts)
        - sampled_data: str - For heuristic scoring
        - metadata: str - For heuristic scoring
        - gt_pvmap_path_cached: str - Optional GT path for PV accuracy

    ADK State Outputs:
        - quality_metrics: dict - Current attempt metrics (includes quality_reject_reason)
        - quality_acceptable: bool - Whether quality meets all thresholds
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
    PV_ACCURACY_THRESHOLD: ClassVar[float] = 30.0  # GT PV accuracy threshold (%)
    STAGNATION_RATIO: ClassVar[float] = 0.10  # Minimum improvement as fraction of previous accuracy

    def __init__(self, name: str = "QualityEvaluator", max_retries: int = 2):
        """Initialize QualityEvaluationAgent."""
        super().__init__(name=name)
        self._max_retries = max_retries

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
        gt_comparison_failed = False
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
            else:
                # GT path exists but comparison failed — block heuristic acceptance
                gt_comparison_failed = True
                quality_acceptable = False
                quality_metrics["gt_comparison_failed"] = True
                quality_metrics["quality_reject_reason"] = "gt_comparison_failed"
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text="GT comparison failed — blocking heuristic acceptance, continuing retries")
                    ])
                )

        # =====================================================================
        # Step 1b-ii: Re-evaluate quality_acceptable with PV accuracy (Priority 2)
        # PV accuracy < 30% overrides heuristic acceptance when GT is available.
        # =====================================================================
        if not gt_comparison_failed:
            gt_pv_accuracy = quality_metrics.get("gt_pv_accuracy")
            if gt_pv_accuracy is not None and gt_pv_accuracy < self.PV_ACCURACY_THRESHOLD:
                quality_acceptable = False  # Override even if heuristic was fine
                quality_metrics["quality_reject_reason"] = "pv_accuracy_low"
                if not quality_diff_summary:
                    quality_diff_summary = format_quality_report(
                        {"total": quality_metrics.get("heuristic_score", 0),
                         "row_coverage": quality_metrics.get("heuristic_breakdown", {}).get("row_coverage", 0),
                         "prop_coverage": quality_metrics.get("heuristic_breakdown", {}).get("prop_coverage", 0),
                         "column_coverage": quality_metrics.get("heuristic_breakdown", {}).get("column_coverage", 0),
                         "format_score": quality_metrics.get("heuristic_breakdown", {}).get("format_score", 0),
                         "issues": ""}
                    )
            elif not quality_acceptable:
                quality_metrics["quality_reject_reason"] = "heuristic_low"

        # =====================================================================
        # Step 1c: Enrich diff summary with counter metrics (when quality low)
        # =====================================================================
        counter_summary = ctx.session.state.get("validation_counter_summary", "")
        if counter_summary and not quality_acceptable:
            quality_diff_summary = (
                quality_diff_summary + "\n\n---\n\n"
                "## Actual Processing Metrics\n" + counter_summary
            )

        # =====================================================================
        # Step 2: Check for stagnation (on the metric that triggered the retry)
        # =====================================================================
        metrics_history = ctx.session.state.get("quality_metrics_history", [])
        quality_stagnant = False
        stagnation_detail = ""
        stagnation_threshold = 0.5  # Default minimum

        if metrics_history and attempt_number > 0:
            prev_metrics = metrics_history[-1]

            # Compute deltas for both metrics
            prev_heuristic = prev_metrics.get("heuristic_score", 0)
            curr_heuristic = quality_metrics.get("heuristic_score", 0)
            heuristic_delta = curr_heuristic - prev_heuristic
            quality_metrics["improvement_from_previous"] = round(heuristic_delta, 1)

            # Determine which metric to check for stagnation
            reject_reason = quality_metrics.get("quality_reject_reason", "")
            prev_gt_pv = prev_metrics.get("gt_pv_accuracy")
            curr_gt_pv = quality_metrics.get("gt_pv_accuracy")

            if reject_reason == "pv_accuracy_low" and prev_gt_pv is not None and curr_gt_pv is not None:
                pv_delta = curr_gt_pv - prev_gt_pv
                quality_metrics["pv_improvement_from_previous"] = round(pv_delta, 1)
                stagnation_delta = pv_delta
                stagnation_detail = f"PV accuracy ({prev_gt_pv:.1f}% -> {curr_gt_pv:.1f}%)"
                # Relative threshold: 10% of previous attempt's PV accuracy
                stagnation_threshold = max(prev_gt_pv * self.STAGNATION_RATIO, 0.5)
            else:
                stagnation_delta = heuristic_delta
                stagnation_detail = f"heuristic ({prev_heuristic:.1f} -> {curr_heuristic:.1f})"
                # Relative threshold: 10% of previous attempt's heuristic score
                stagnation_threshold = max(prev_heuristic * self.STAGNATION_RATIO, 0.5)

            if stagnation_delta < stagnation_threshold:
                quality_stagnant = True
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Stagnation detected: {stagnation_detail} improved only {stagnation_delta:.1f}% (need >= {stagnation_threshold:.1f}%)")
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
            gt_pv = quality_metrics.get("gt_pv_accuracy")
            message = f"Quality ACCEPTABLE: heuristic {score_value:.1f}/100"
            if gt_pv is not None:
                message += f", PV accuracy {gt_pv:.1f}%"
            message += ". ESCALATING to exit loop."

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

            message = (
                f"Quality STAGNANT: {stagnation_detail} improved only "
                f"{quality_metrics.get('pv_improvement_from_previous', quality_metrics.get('improvement_from_previous', 0)):.1f}% "
                f"(need >= {stagnation_threshold:.1f}%). Stopping with best effort."
            )

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=message)]),
                actions=EventActions(escalate=True)
            )

        else:
            score_value = quality_metrics.get("heuristic_score", 0)
            gt_pv = quality_metrics.get("gt_pv_accuracy")
            reject_reason = quality_metrics.get("quality_reject_reason", "")

            if reject_reason == "pv_accuracy_low" and gt_pv is not None:
                message = (
                    f"Quality LOW: PV accuracy {gt_pv:.1f}% < {self.PV_ACCURACY_THRESHOLD}% threshold. "
                    f"Continuing to feedback."
                )
            elif reject_reason == "gt_comparison_failed":
                message = (
                    f"Quality LOW: GT comparison failed, heuristic {score_value:.1f}/100. "
                    f"Continuing to feedback."
                )
            else:
                message = (
                    f"Quality LOW: heuristic {score_value:.1f}/100 < {self.QUALITY_THRESHOLD} threshold. "
                    f"Continuing to feedback."
                )

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
            gt_pv = metrics.get("gt_pv_accuracy")
            status = f"SUCCESS (heuristic quality: {score:.1f}/100"
            if gt_pv is not None:
                status += f", PV accuracy: {gt_pv:.1f}%"
            status += f") on attempt {attempt + 1}"

            update_generation_notes(
                output_dir=Path(current_dataset.output_dir),
                dataset_name=current_dataset.name,
                attempt=attempt,
                llm_result=llm_result,
                pvmap_csv=pvmap_csv,
                validation_result={"success": True},
                final_status=status
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
            reject_reason = metrics.get("quality_reject_reason", "")
            if reject_reason == "pv_accuracy_low":
                pv_imp = metrics.get("pv_improvement_from_previous", 0)
                gt_pv = metrics.get("gt_pv_accuracy", 0)
                status = f"STAGNANT (best effort, PV accuracy: {gt_pv:.1f}%, PV improvement: {pv_imp:.1f}%) on attempt {attempt + 1}"
            else:
                improvement = metrics.get("improvement_from_previous", 0)
                status = f"STAGNANT (best effort, heuristic quality: {score:.1f}/100, improvement: {improvement:.1f}%) on attempt {attempt + 1}"

            update_generation_notes(
                output_dir=Path(current_dataset.output_dir),
                dataset_name=current_dataset.name,
                attempt=attempt,
                llm_result=llm_result,
                pvmap_csv=pvmap_csv,
                validation_result={"success": True},
                final_status=status
            )
        except Exception:
            pass  # Don't fail on logging errors


# ============================================================================
# Module exports
# ============================================================================

__all__ = ['QualityEvaluationAgent']
