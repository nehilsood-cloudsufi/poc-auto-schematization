"""
Evaluation Agent for ADK pipeline.

Evaluates generated PVMAP against ground truth PVMAPs.
Follows Pattern 1: Simple BaseAgent (no LLM needed).

This agent uses Google ADK BaseAgent pattern for proper async execution.
"""

import sys
from pathlib import Path
from typing import List, Dict, Any, AsyncGenerator

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.tools.evaluation_tools import find_ground_truth_pvmaps, compare_pvmaps


class EvaluationAgent(BaseAgent):
    """
    Agent for evaluating generated PVMAP against ground truth.

    This is a simple (non-LLM) agent that performs deterministic
    PVMAP comparison and calculates metrics.

    ADK State Inputs:
        - current_dataset: DatasetInfo - Current dataset being processed
        - pvmap_path: Path - Path to generated PVMAP file
        - skip_evaluation: bool - Whether to skip evaluation
        - output_dir: Path - Directory for evaluation outputs

    ADK State Outputs:
        - eval_metrics: Dict - Evaluation metrics (precision, recall, etc.)
        - best_ground_truth_pvmap: Path - Best matching ground truth file
        - ground_truth_pvmaps: List[Path] - All found ground truth files
        - evaluation_passed: bool - Whether evaluation succeeded
        - error: str | None - Error message if evaluation failed

    Responsibilities:
    - Find ground truth PVMAP files for dataset
    - Compare generated PVMAP against each ground truth
    - Select best matching ground truth
    - Calculate and store evaluation metrics
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """
        Run evaluation logic using ADK pattern.

        Reads dataset info and pvmap_path from ctx.session.state,
        finds ground truth, performs comparison, and writes metrics to state.

        Args:
            ctx: ADK invocation context with session state

        Yields:
            Event with evaluation results
        """
        # 1. Check skip flag
        skip_evaluation = ctx.session.state.get("skip_evaluation", False)
        if skip_evaluation:
            ctx.session.state["evaluation_passed"] = True
            ctx.session.state["eval_metrics"] = {}
            ctx.session.state["error"] = None

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Evaluation skipped (skip_evaluation=True)")
                ])
            )
            return

        # 2. Read inputs from state
        current_dataset = ctx.session.state.get("current_dataset")
        pvmap_path = ctx.session.state.get("pvmap_path")
        output_dir = ctx.session.state.get("output_dir")

        if not current_dataset:
            ctx.session.state["error"] = "No current_dataset specified in state"
            ctx.session.state["evaluation_passed"] = False
            ctx.session.state["eval_metrics"] = {}

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Evaluation failed: No current_dataset in state")
                ])
            )
            return

        if not pvmap_path or not Path(pvmap_path).exists():
            ctx.session.state["error"] = f"Generated PVMAP not found: {pvmap_path}"
            ctx.session.state["evaluation_passed"] = False
            ctx.session.state["eval_metrics"] = {}

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Evaluation failed: PVMAP file not found at {pvmap_path}")
                ])
            )
            return

        # 3. Find ground truth PVMAPs
        dataset_name = current_dataset.name
        gt_result = find_ground_truth_pvmaps(
            dataset_name=dataset_name,
            search_dir=current_dataset.path
        )

        if not gt_result["success"] or gt_result["count"] == 0:
            ctx.session.state["error"] = gt_result.get("error", "No ground truth PVMAPs found")
            ctx.session.state["evaluation_passed"] = False
            ctx.session.state["eval_metrics"] = {}
            ctx.session.state["ground_truth_pvmaps"] = []

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Evaluation failed: {gt_result.get('error', 'No ground truth found')}")
                ])
            )
            return

        ground_truth_pvmaps = gt_result["pvmaps"]
        ctx.session.state["ground_truth_pvmaps"] = ground_truth_pvmaps

        # 4. Compare against all ground truths and select best
        best_metrics = None
        best_gt_pvmap = None
        best_f1 = -1.0

        for gt_pvmap in ground_truth_pvmaps:
            comparison = compare_pvmaps(
                auto_pvmap_path=Path(pvmap_path),
                gt_pvmap_path=gt_pvmap,
                output_dir=Path(output_dir) if output_dir else current_dataset.path
            )

            if comparison["success"]:
                metrics = comparison["metrics"]
                f1_score = metrics.get("f1_score", 0.0)

                if f1_score > best_f1:
                    best_f1 = f1_score
                    best_metrics = metrics
                    best_gt_pvmap = gt_pvmap

        # 5. Write results to state
        if best_metrics:
            ctx.session.state["eval_metrics"] = best_metrics
            ctx.session.state["best_ground_truth_pvmap"] = str(best_gt_pvmap)
            ctx.session.state["evaluation_passed"] = True
            ctx.session.state["error"] = None

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"Evaluation complete: F1={best_metrics.get('f1_score', 0.0):.3f}, "
                                   f"Precision={best_metrics.get('precision', 0.0):.3f}, "
                                   f"Recall={best_metrics.get('recall', 0.0):.3f}")
                ])
            )
        else:
            ctx.session.state["error"] = "All PVMAP comparisons failed"
            ctx.session.state["evaluation_passed"] = False
            ctx.session.state["eval_metrics"] = {}

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="Evaluation failed: Could not compare with any ground truth")
                ])
            )
