"""
Quality Evaluation Agent for ADK pipeline.

This BaseAgent evaluates PVMAP quality after validation passes using:
1. Ground truth comparison (if available) - PV accuracy >= 30%
2. Heuristic scoring (if no ground truth) - Score >= 70/100

Key ADK features used:
- BaseAgent for custom evaluation logic
- EventActions.escalate to exit LoopAgent on acceptable quality or stagnation
- Session state for quality metrics tracking across attempts
"""

import os
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

from src.tools.evaluation_tools import find_ground_truth_pvmaps, compare_pvmaps
from src.tools.heuristic_quality import calculate_heuristic_score, format_quality_report


class QualityEvaluationAgent(BaseAgent):
    """
    Evaluates PVMAP quality after validation passes.

    This agent:
    1. Checks if validation passed (skip if not)
    2. Tries to find ground truth PVMAP for comparison
    3. If GT found: compares and checks PV accuracy >= threshold
    4. If no GT: uses heuristic scoring >= threshold
    5. Detects stagnation (improvement < 5% between attempts)
    6. Escalates to exit loop if quality acceptable OR stagnant

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
        - quality_diff_summary: str - Diff or issues summary for feedback
        - quality_stagnant: bool - Whether improvement has stagnated
        - quality_metrics_history: List[dict] - Updated with current metrics
        - exit_reason: str - "quality_met" | "stagnant" | None

    Escalation:
        - escalate=True if quality_acceptable=True OR quality_stagnant=True
        - escalate=False to continue to QualityFeedbackAgent
    """

    # Quality thresholds (ClassVar to avoid Pydantic field treatment)
    QUALITY_THRESHOLD: ClassVar[float] = 30.0  # PV accuracy threshold for ground truth mode
    HEURISTIC_THRESHOLD: ClassVar[float] = 70.0  # Heuristic score threshold (out of 100)
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
        pvmap_path = ctx.session.state.get("pvmap_path", "")
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
        # Step 1: Try ground truth comparison
        # =====================================================================
        gt_result = find_ground_truth_pvmaps(
            dataset_name=current_dataset.name,
            source_repo=os.getenv("GROUND_TRUTH_REPO", "ground_truth")
        )

        quality_metrics: Dict[str, Any] = {}
        quality_acceptable = False
        quality_diff_summary = ""

        if gt_result["success"] and gt_result["pvmaps"]:
            # Ground truth available - use comparison
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Found {gt_result['count']} ground truth PVMAP(s). Comparing...")
                ])
            )

            comparison = compare_pvmaps(
                auto_pvmap_path=pvmap_path,
                gt_pvmap_path=str(gt_result["pvmaps"][0]),
                output_dir=str(Path(current_dataset.output_dir) / "eval_results")
            )

            if comparison["success"]:
                quality_metrics = {
                    "pv_accuracy": comparison.get("pv_accuracy", 0),
                    "node_accuracy": comparison.get("accuracy", 0),
                    "counters": comparison.get("counters", {}),
                    "mode": "ground_truth",
                    "gt_pvmap": str(gt_result["pvmaps"][0])
                }

                # Truncate diff text for feedback (keep under token budget)
                diff_text = comparison.get("diff_text", "")
                if diff_text and len(diff_text) > 2000:
                    quality_diff_summary = diff_text[:2000] + "\n... (truncated)"
                else:
                    quality_diff_summary = diff_text or ""

                quality_acceptable = quality_metrics["pv_accuracy"] >= self.QUALITY_THRESHOLD

                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Ground truth comparison: PV accuracy = {quality_metrics['pv_accuracy']:.1f}% (threshold: {self.QUALITY_THRESHOLD}%)")
                    ])
                )
            else:
                # Comparison failed - fall back to heuristics
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text=f"Ground truth comparison failed: {comparison.get('error', 'unknown')}. Falling back to heuristics.")
                    ])
                )
                quality_metrics, quality_acceptable, quality_diff_summary = self._evaluate_with_heuristics(
                    ctx, pvmap_csv
                )
        else:
            # No ground truth - use heuristic scoring
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="No ground truth available. Using heuristic scoring...")
                ])
            )
            quality_metrics, quality_acceptable, quality_diff_summary = self._evaluate_with_heuristics(
                ctx, pvmap_csv
            )

        # =====================================================================
        # Step 2: Check for stagnation
        # =====================================================================
        metrics_history = ctx.session.state.get("quality_metrics_history", [])
        quality_stagnant = False

        if metrics_history and attempt_number > 0:
            prev_metrics = metrics_history[-1]
            prev_score = prev_metrics.get("pv_accuracy") or prev_metrics.get("heuristic_score", 0)
            curr_score = quality_metrics.get("pv_accuracy") or quality_metrics.get("heuristic_score", 0)
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

            mode = quality_metrics.get("mode", "unknown")
            score_value = quality_metrics.get("pv_accuracy") or quality_metrics.get("heuristic_score", 0)
            message = (
                f"Quality ACCEPTABLE ({mode} mode): {score_value:.1f}% >= threshold. "
                f"ESCALATING to exit loop."
            )

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
                f"Quality STAGNANT (improvement < {self.STAGNATION_THRESHOLD}%). "
                f"ESCALATING with best effort result."
            )

            yield Event(
                author=self.name,
                content=types.Content(parts=[types.Part(text=message)]),
                actions=EventActions(escalate=True)
            )

        else:
            mode = quality_metrics.get("mode", "unknown")
            score_value = quality_metrics.get("pv_accuracy") or quality_metrics.get("heuristic_score", 0)
            threshold = self.QUALITY_THRESHOLD if mode == "ground_truth" else self.HEURISTIC_THRESHOLD
            message = (
                f"Quality LOW ({mode} mode): {score_value:.1f}% < {threshold}% threshold. "
                f"Continuing to quality feedback."
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

        quality_acceptable = heuristic_result["total"] >= self.HEURISTIC_THRESHOLD
        quality_diff_summary = heuristic_result.get("issues", "")

        # Add formatted report for feedback
        if not quality_acceptable:
            quality_diff_summary = format_quality_report(heuristic_result)

        return quality_metrics, quality_acceptable, quality_diff_summary

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

            mode = metrics.get("mode", "unknown")
            score = metrics.get("pv_accuracy") or metrics.get("heuristic_score", 0)

            update_generation_notes(
                output_dir=Path(current_dataset.output_dir),
                dataset_name=current_dataset.name,
                attempt=attempt,
                llm_result=llm_result,
                pvmap_csv=pvmap_csv,
                validation_result={"success": True},
                final_status=f"SUCCESS ({mode} quality: {score:.1f}%) on attempt {attempt + 1}"
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

            mode = metrics.get("mode", "unknown")
            score = metrics.get("pv_accuracy") or metrics.get("heuristic_score", 0)
            improvement = metrics.get("improvement_from_previous", 0)

            update_generation_notes(
                output_dir=Path(current_dataset.output_dir),
                dataset_name=current_dataset.name,
                attempt=attempt,
                llm_result=llm_result,
                pvmap_csv=pvmap_csv,
                validation_result={"success": True},
                final_status=f"STAGNANT (best effort, {mode} quality: {score:.1f}%, improvement: {improvement:.1f}%) on attempt {attempt + 1}"
            )
        except Exception:
            pass  # Don't fail on logging errors


# ============================================================================
# Module exports
# ============================================================================

__all__ = ['QualityEvaluationAgent']
