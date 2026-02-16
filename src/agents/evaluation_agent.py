"""
Evaluation Agent for ADK pipeline.

Evaluates generated PVMAP against ground truth PVMAPs.
Follows Pattern 1: Simple BaseAgent (no LLM needed).

This agent uses Google ADK BaseAgent pattern for proper async execution.
"""

import json
import sys
from pathlib import Path
from typing import List, Dict, AsyncGenerator

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
        - data_context: Dict - Data context from SamplingAgent (for validation)

    ADK State Outputs:
        - eval_metrics: Dict - Evaluation metrics with keys:
            node_accuracy, pv_accuracy, nodes_matched, nodes_ground_truth,
            pvs_matched, best_ground_truth_pvmap, expected_combinations,
            expected_pattern
        - best_ground_truth_pvmap: Path - Best matching ground truth file
        - ground_truth_pvmaps: List[Path] - All found ground truth files
        - evaluation_passed: bool - Whether evaluation succeeded
        - error: str | None - Error message if evaluation failed

    Responsibilities:
    - Find ground truth PVMAP files for dataset
    - Compare generated PVMAP against each ground truth
    - Select best matching ground truth
    - Calculate and store evaluation metrics
    - Include data_context metrics (expected combinations, pattern) for analysis
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

        # 3. Find ground truth PVMAPs using precedence tiers:
        #    Tier 1: explicit_pvmap (highest priority)
        #    Tier 2: ground_truth_dir (search directory)
        #    Tier 3: ground_truth_repo (default)
        import os
        ground_truth_pvmap = ctx.session.state.get("ground_truth_pvmap")
        ground_truth_dir = ctx.session.state.get("ground_truth_dir")
        ground_truth_repo = ctx.session.state.get(
            "ground_truth_repo",
            os.getenv("GROUND_TRUTH_REPO", str(PROJECT_ROOT / "ground_truth"))
        )

        dataset_name = current_dataset.name

        # Apply precedence tiers
        if ground_truth_pvmap and Path(ground_truth_pvmap).exists():
            # Tier 1: Explicit file (highest priority)
            gt_result = find_ground_truth_pvmaps(
                dataset_name=dataset_name,
                explicit_pvmap=ground_truth_pvmap
            )
        elif ground_truth_dir and Path(ground_truth_dir).exists():
            # Tier 2: Directory search
            gt_result = find_ground_truth_pvmaps(
                dataset_name=dataset_name,
                search_dir=ground_truth_dir
            )
        else:
            # Tier 3: Repository (default)
            gt_result = find_ground_truth_pvmaps(
                dataset_name=dataset_name,
                source_repo=ground_truth_repo,
                search_dir=str(current_dataset.path) if current_dataset.path else ""
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
        # Use node accuracy for best match selection (matches procedural pipeline)
        best_accuracy = -1.0
        best_pv_accuracy = 0.0
        best_gt_pvmap = None
        best_diff_text = ""
        best_counters = {}

        for gt_pvmap in ground_truth_pvmaps:
            comparison = compare_pvmaps(
                auto_pvmap_path=str(pvmap_path),
                gt_pvmap_path=gt_pvmap,
                output_dir=str(Path(output_dir) if output_dir else current_dataset.path)
            )

            if comparison["success"]:
                # compare_pvmaps returns: success, error, counters, diff_text, accuracy, pv_accuracy
                node_accuracy = comparison.get("accuracy", 0.0)

                if node_accuracy > best_accuracy:
                    best_accuracy = node_accuracy
                    best_pv_accuracy = comparison.get("pv_accuracy", 0.0)
                    best_gt_pvmap = gt_pvmap
                    best_diff_text = comparison.get("diff_text", "")
                    best_counters = comparison.get("counters", {})

        # 5. Get data_context for additional metrics (if available)
        data_context = ctx.session.state.get("data_context", {})
        expected_combinations = data_context.get("total_combinations", 0) if data_context else 0
        expected_pattern = data_context.get("statvar_pattern", "") if data_context else ""
        dimension_columns = data_context.get("dimension_columns", []) if data_context else []
        coverage_percent = data_context.get("coverage_percent", 0) if data_context else 0

        # 6. Write results to state and save diff files
        if best_gt_pvmap is not None:
            # Store proper metrics in state (matches procedural pipeline + data_context)
            eval_metrics = {
                'node_accuracy': best_accuracy,
                'pv_accuracy': best_pv_accuracy,
                'nodes_matched': best_counters.get('nodes-matched', 0),
                'nodes_ground_truth': best_counters.get('nodes-ground-truth', 0),
                'pvs_matched': best_counters.get('PVs-matched', 0),
                'best_ground_truth_pvmap': str(Path(best_gt_pvmap).name)
            }

            # Add data_context metrics if available
            if data_context:
                eval_metrics['expected_combinations'] = expected_combinations
                eval_metrics['expected_pattern'] = expected_pattern
                eval_metrics['dimension_columns'] = dimension_columns
                eval_metrics['sample_coverage_percent'] = coverage_percent
                # Include aggregate value flags for debugging visibility
                aggregate_values = data_context.get('aggregate_values', {}) if data_context else {}
                if aggregate_values:
                    eval_metrics['aggregate_values_detected'] = aggregate_values

            ctx.session.state["eval_metrics"] = eval_metrics
            ctx.session.state["best_ground_truth_pvmap"] = str(best_gt_pvmap)
            ctx.session.state["evaluation_passed"] = True
            ctx.session.state["error"] = None

            # Save diff files to eval_results directory
            eval_results_dir = Path(output_dir if output_dir else current_dataset.output_dir) / "eval_results"
            eval_results_dir.mkdir(parents=True, exist_ok=True)

            # Save diff.txt (match procedural pipeline format + data_context info)
            diff_txt_path = eval_results_dir / "diff.txt"
            with open(diff_txt_path, 'w', encoding='utf-8') as f:
                f.write(f"Best match: {Path(best_gt_pvmap).name}\n")
                f.write(f"Tested {len(ground_truth_pvmaps)} ground truth PVMAP(s)\n")
                if data_context:
                    f.write(f"\nData Context:\n")
                    f.write(f"  Expected StatVar Pattern: {expected_pattern}\n")
                    f.write(f"  Dimension Columns: {', '.join(dimension_columns) if dimension_columns else 'None'}\n")
                    f.write(f"  Expected Combinations: {expected_combinations}\n")
                    f.write(f"  Sample Coverage: {coverage_percent:.1f}%\n")
                f.write("=" * 60 + "\n\n")
                f.write(best_diff_text if best_diff_text else "(No diff text available)")

            # Save diff_results.json (match procedural pipeline structure + data_context)
            # Save counters directly with extra fields (not wrapped in nested structure)
            diff_results_path = eval_results_dir / "diff_results.json"
            best_counters['best_ground_truth_pvmap'] = str(best_gt_pvmap)
            best_counters['ground_truth_pvmaps_tested'] = len(ground_truth_pvmaps)
            if data_context:
                best_counters['expected_combinations'] = expected_combinations
                best_counters['expected_pattern'] = expected_pattern
                best_counters['dimension_columns'] = dimension_columns
                best_counters['sample_coverage_percent'] = coverage_percent
            with open(diff_results_path, 'w', encoding='utf-8') as f:
                json.dump(best_counters, f, indent=2, default=str)

            # Build result message
            result_msg = (f"Evaluation complete: Node Acc={best_accuracy:.1f}%, "
                         f"PV Acc={best_pv_accuracy:.1f}%. "
                         f"Best match: {Path(best_gt_pvmap).name}.")
            if data_context and expected_combinations > 0:
                result_msg += f" Expected {expected_combinations} combinations."

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"{result_msg} Results saved to {eval_results_dir}")
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
