"""LLM-as-Judge agent for qualitative PVMAP evaluation.

Runs after EvaluationAgent in the pipeline. When ground truth is available,
sends generated PVMAP, GT PVMAP, diff text, and context to Gemini for a
structured qualitative assessment with scores, issues, and suggestions.

Follows Pattern 1: BaseAgent with direct Gemini API call (not LlmAgent).
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import AsyncGenerator, Dict, Any, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from google import genai

from src.agents.llm_judge_schemas import LLMJudgeReport
from src.agents.prompt_loader import load_prompt
from src.agents.retry_config import DEFAULT_RETRY_OPTIONS
from src.data_commons.api.gemini_client import load_gemini_api_key

logger = logging.getLogger(__name__)

# Maximum lines of diff text to include in prompt
MAX_DIFF_LINES = 300
# Maximum characters of skeleton summary to include
MAX_SKELETON_CHARS = 5000


def _truncate_diff(diff_text: str, max_lines: int = MAX_DIFF_LINES) -> str:
    """Truncate diff text to max_lines, keeping last 50 + random samples."""
    lines = diff_text.strip().split("\n")
    if len(lines) <= max_lines:
        return diff_text

    # Keep last 50 lines (most recent/relevant) + first 250 lines
    head = lines[:max_lines - 50]
    tail = lines[-50:]
    return "\n".join(head + [f"\n... ({len(lines) - max_lines} lines truncated) ...\n"] + tail)


def _truncate_skeleton(skeleton: str, max_chars: int = MAX_SKELETON_CHARS) -> str:
    """Truncate skeleton summary to max_chars."""
    if len(skeleton) <= max_chars:
        return skeleton
    return skeleton[:max_chars] + f"\n... (truncated at {max_chars} chars)"


def _build_data_context_summary(data_context: Optional[Dict]) -> str:
    """Extract key fields from data_context for the prompt."""
    if not data_context:
        return "No data context available."

    parts = []
    if data_context.get("dimension_columns"):
        parts.append(f"Dimension columns: {', '.join(data_context['dimension_columns'])}")
    if data_context.get("statvar_pattern"):
        parts.append(f"StatVar pattern: {data_context['statvar_pattern']}")
    if data_context.get("total_combinations"):
        parts.append(f"Expected combinations: {data_context['total_combinations']}")
    if data_context.get("coverage_percent"):
        parts.append(f"Sample coverage: {data_context['coverage_percent']:.1f}%")

    return "\n".join(parts) if parts else "No data context available."


def _format_markdown_report(report_dict: Dict[str, Any]) -> str:
    """Format the judge report as human-readable markdown."""
    lines = ["# LLM Judge Evaluation Report\n"]

    overall = report_dict.get("overall_score", 0)
    lines.append(f"**Overall Score: {overall:.1f}/5**\n")

    # Summary
    lines.append(f"## Summary\n\n{report_dict.get('summary', 'N/A')}\n")

    # Dimension scores
    for dim_name, dim_label in [
        ("structural_quality", "Structural Quality"),
        ("semantic_accuracy", "Semantic Accuracy"),
        ("value_mapping_quality", "Value Mapping Quality"),
    ]:
        dim = report_dict.get(dim_name, {})
        score = dim.get("score", "?")
        explanation = dim.get("explanation", "N/A")
        issues = dim.get("issues", [])

        lines.append(f"## {dim_label}: {score}/5\n")
        lines.append(f"{explanation}\n")
        if issues:
            lines.append("**Issues:**")
            for issue in issues:
                lines.append(f"- {issue}")
            lines.append("")

    # Top issues
    top_issues = report_dict.get("top_issues", [])
    if top_issues:
        lines.append("## Top Issues\n")
        for i, issue in enumerate(top_issues, 1):
            lines.append(f"{i}. {issue}")
        lines.append("")

    # Improvement suggestions
    suggestions = report_dict.get("improvement_suggestions", [])
    if suggestions:
        lines.append("## Improvement Suggestions\n")
        for i, suggestion in enumerate(suggestions, 1):
            lines.append(f"{i}. {suggestion}")
        lines.append("")

    return "\n".join(lines)


class LLMJudgeAgent(BaseAgent):
    """Agent for qualitative PVMAP evaluation using LLM-as-judge.

    Runs after EvaluationAgent. When ground truth is available, sends
    the generated PVMAP, GT PVMAP, diff, and context to Gemini for
    structured qualitative assessment.

    ADK State Inputs:
        - eval_metrics: Dict — numeric evaluation metrics
        - best_ground_truth_pvmap: str — path to best matching GT file
        - pvmap_path: str — path to generated PVMAP file
        - data_context: Dict — data context from sampling
        - skeleton_summary: str — skeleton summary from sampling
        - output_dir: str — output directory
        - skip_evaluation: bool — skip flag
        - skip_llm_judge: bool — skip flag
        - model: str — Gemini model name (optional)

    ADK State Outputs:
        - llm_judge_report: Dict — full judge report
    """

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        state = ctx.session.state

        # --- Skip conditions ---
        if state.get("skip_evaluation", False):
            logger.info("LLM Judge skipped: evaluation was skipped")
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="LLM Judge skipped (evaluation was skipped)")
                ]),
            )
            return

        if state.get("skip_llm_judge", False):
            logger.info("LLM Judge skipped: --skip-llm-judge flag set")
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="LLM Judge skipped (--skip-llm-judge)")
                ]),
            )
            return

        best_gt_pvmap = state.get("best_ground_truth_pvmap")
        if not best_gt_pvmap:
            logger.info("LLM Judge skipped: no ground truth PVMAP available")
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="LLM Judge skipped (no ground truth available)")
                ]),
            )
            return

        # --- Gather inputs ---
        pvmap_path = state.get("pvmap_path")
        output_dir = state.get("output_dir", "")
        eval_metrics = state.get("eval_metrics", {})
        data_context = state.get("data_context", {})
        skeleton_summary = state.get("skeleton_summary", "")
        model_name = state.get("model") or os.getenv(
            "GEMINI_MODEL", "gemini-3.1-pro-preview"
        )

        # Read generated PVMAP from disk
        generated_pvmap = ""
        if pvmap_path and Path(pvmap_path).exists():
            generated_pvmap = Path(pvmap_path).read_text(encoding="utf-8")
        else:
            logger.warning(f"Generated PVMAP not found at {pvmap_path}")

        # Read GT PVMAP from disk
        gt_pvmap_content = ""
        gt_path = Path(best_gt_pvmap)
        if gt_path.exists():
            gt_pvmap_content = gt_path.read_text(encoding="utf-8")
        else:
            logger.warning(f"Ground truth PVMAP not found at {best_gt_pvmap}")

        # Read diff text from disk
        diff_text = ""
        eval_results_dir = Path(output_dir) / "eval_results" if output_dir else None
        if eval_results_dir:
            diff_path = eval_results_dir / "diff.txt"
            if diff_path.exists():
                diff_text = diff_path.read_text(encoding="utf-8")

        # --- Build prompt ---
        prompt_template = load_prompt("llm_judge_prompt.txt")
        prompt = prompt_template
        prompt = prompt.replace("{generated_pvmap}", generated_pvmap)
        prompt = prompt.replace("{ground_truth_pvmap}", gt_pvmap_content)
        prompt = prompt.replace("{diff_text}", _truncate_diff(diff_text))
        prompt = prompt.replace("{eval_metrics}", json.dumps(eval_metrics, indent=2, default=str))
        prompt = prompt.replace("{data_context_summary}", _build_data_context_summary(data_context))
        prompt = prompt.replace("{skeleton_summary}", _truncate_skeleton(skeleton_summary) if skeleton_summary else "Not available")

        # --- Call Gemini ---
        try:
            api_key = load_gemini_api_key()
            client = genai.Client(
                api_key=api_key,
                http_options=types.HttpOptions(retry_options=DEFAULT_RETRY_OPTIONS),
            )

            response = client.models.generate_content(
                model=model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0,
                    response_mime_type="application/json",
                    response_schema=LLMJudgeReport,
                ),
            )

            # Parse structured response
            report_data = json.loads(response.text)
            report = LLMJudgeReport(**report_data)

        except Exception as e:
            logger.error(f"LLM Judge Gemini call failed: {e}")
            error_report = {"error": str(e)}
            state["llm_judge_report"] = error_report

            # Write error report to disk
            if eval_results_dir:
                eval_results_dir.mkdir(parents=True, exist_ok=True)
                error_path = eval_results_dir / "llm_judge_report.json"
                error_path.write_text(
                    json.dumps(error_report, indent=2), encoding="utf-8"
                )

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"LLM Judge failed: {e}. Pipeline continues.")
                ]),
            )
            return

        # --- Compute overall score ---
        overall_score = round(
            (
                report.structural_quality.score
                + report.semantic_accuracy.score
                + report.value_mapping_quality.score
            )
            / 3,
            1,
        )

        # Build full report dict
        report_dict = report.model_dump()
        report_dict["overall_score"] = overall_score

        # --- Write outputs ---
        state["llm_judge_report"] = report_dict

        if eval_results_dir:
            eval_results_dir.mkdir(parents=True, exist_ok=True)

            # JSON report
            json_path = eval_results_dir / "llm_judge_report.json"
            json_path.write_text(
                json.dumps(report_dict, indent=2, default=str), encoding="utf-8"
            )

            # Markdown report
            md_path = eval_results_dir / "llm_judge_report.md"
            md_path.write_text(
                _format_markdown_report(report_dict), encoding="utf-8"
            )

            logger.info(
                f"LLM Judge report saved to {eval_results_dir}. "
                f"Overall: {overall_score}/5"
            )

        # --- Yield result ---
        result_msg = (
            f"LLM Judge: Structural={report.structural_quality.score}/5, "
            f"Semantic={report.semantic_accuracy.score}/5, "
            f"Values={report.value_mapping_quality.score}/5 "
            f"(Overall: {overall_score}/5)"
        )

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text=result_msg)
            ]),
        )
