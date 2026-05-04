"""Tests for LLMJudgeAgent with proper ADK async patterns."""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from src.agents.llm_judge_agent import (
    LLMJudgeAgent,
    _truncate_diff,
    _truncate_skeleton,
    _build_data_context_summary,
    _format_markdown_report,
)
from src.agents.llm_judge_schemas import JudgeDimension, LLMJudgeReport


# ---------------------------------------------------------------------------
# Unit tests for helper functions
# ---------------------------------------------------------------------------


class TestTruncateDiff:
    def test_short_diff_unchanged(self):
        diff = "line1\nline2\nline3"
        assert _truncate_diff(diff, max_lines=10) == diff

    def test_long_diff_truncated(self):
        lines = [f"line{i}" for i in range(500)]
        result = _truncate_diff("\n".join(lines), max_lines=300)
        result_lines = result.split("\n")
        # Should have head + truncation marker + tail
        assert "truncated" in result
        assert len(result_lines) < 500

    def test_empty_diff(self):
        assert _truncate_diff("") == ""


class TestTruncateSkeleton:
    def test_short_skeleton_unchanged(self):
        skeleton = "short text"
        assert _truncate_skeleton(skeleton, max_chars=100) == skeleton

    def test_long_skeleton_truncated(self):
        skeleton = "x" * 10000
        result = _truncate_skeleton(skeleton, max_chars=5000)
        assert len(result) < 10000
        assert "truncated" in result

    def test_empty_skeleton(self):
        assert _truncate_skeleton("") == ""


class TestBuildDataContextSummary:
    def test_none_context(self):
        assert "No data context" in _build_data_context_summary(None)

    def test_empty_context(self):
        assert "No data context" in _build_data_context_summary({})

    def test_full_context(self):
        ctx = {
            "dimension_columns": ["age", "sex"],
            "statvar_pattern": "Count_Person",
            "total_combinations": 42,
            "coverage_percent": 85.5,
        }
        result = _build_data_context_summary(ctx)
        assert "age" in result
        assert "Count_Person" in result
        assert "42" in result
        assert "85.5" in result


class TestFormatMarkdownReport:
    def test_basic_formatting(self):
        report = {
            "structural_quality": {"score": 4, "explanation": "Good structure", "issues": ["minor gap"]},
            "semantic_accuracy": {"score": 3, "explanation": "Some wrong props", "issues": []},
            "value_mapping_quality": {"score": 5, "explanation": "Perfect", "issues": []},
            "overall_score": 4.0,
            "top_issues": ["issue1", "issue2"],
            "improvement_suggestions": ["fix prop X"],
            "summary": "Decent PVMAP.",
        }
        md = _format_markdown_report(report)
        assert "# LLM Judge Evaluation Report" in md
        assert "4.0/5" in md
        assert "Structural Quality: 4/5" in md
        assert "minor gap" in md
        assert "issue1" in md
        assert "fix prop X" in md


# ---------------------------------------------------------------------------
# Schema tests
# ---------------------------------------------------------------------------


class TestLLMJudgeSchemas:
    def test_judge_dimension_valid(self):
        dim = JudgeDimension(score=3, explanation="OK", issues=["a"])
        assert dim.score == 3

    def test_judge_dimension_score_bounds(self):
        with pytest.raises(Exception):
            JudgeDimension(score=0, explanation="Too low", issues=[])
        with pytest.raises(Exception):
            JudgeDimension(score=6, explanation="Too high", issues=[])

    def test_llm_judge_report_valid(self):
        dim = JudgeDimension(score=4, explanation="Good", issues=[])
        report = LLMJudgeReport(
            structural_quality=dim,
            semantic_accuracy=dim,
            value_mapping_quality=dim,
            top_issues=["issue1"],
            improvement_suggestions=["fix X"],
            summary="Good PVMAP.",
        )
        assert report.structural_quality.score == 4


# ---------------------------------------------------------------------------
# Agent tests
# ---------------------------------------------------------------------------


def test_llm_judge_agent_initialization():
    agent = LLMJudgeAgent(name="LLMJudge")
    assert agent.name == "LLMJudge"


@pytest.mark.asyncio
async def test_skip_when_evaluation_skipped(mock_invocation_context):
    mock_invocation_context.session.state["skip_evaluation"] = True

    agent = LLMJudgeAgent(name="LLMJudge")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    assert len(events) == 1
    assert "skipped" in events[0].content.parts[0].text.lower()


@pytest.mark.asyncio
async def test_skip_when_flag_set(mock_invocation_context):
    mock_invocation_context.session.state["skip_llm_judge"] = True

    agent = LLMJudgeAgent(name="LLMJudge")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    assert len(events) == 1
    assert "skipped" in events[0].content.parts[0].text.lower()


@pytest.mark.asyncio
async def test_skip_when_no_ground_truth(mock_invocation_context):
    # No best_ground_truth_pvmap in state
    agent = LLMJudgeAgent(name="LLMJudge")
    events = []
    async for event in agent._run_async_impl(mock_invocation_context):
        events.append(event)

    assert len(events) == 1
    assert "no ground truth" in events[0].content.parts[0].text.lower()


@pytest.mark.asyncio
async def test_gemini_failure_handled_gracefully(mock_invocation_context, tmp_path):
    """When Gemini call fails, agent should yield warning and write error report."""
    # Setup state with GT available
    pvmap_path = tmp_path / "generated_pvmap.csv"
    pvmap_path.write_text("key,property,value\nobs,observationAbout,dcid:country/USA")
    gt_path = tmp_path / "gt_pvmap.csv"
    gt_path.write_text("key,property,value\nobs,observationAbout,dcid:country/USA")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    eval_dir = output_dir / "eval_results"
    eval_dir.mkdir()

    state = mock_invocation_context.session.state
    state["best_ground_truth_pvmap"] = str(gt_path)
    state["pvmap_path"] = str(pvmap_path)
    state["output_dir"] = str(output_dir)
    state["eval_metrics"] = {"node_accuracy": 50.0}

    with patch("src.agents.llm_judge_agent.load_gemini_api_key", return_value="fake-key"), \
         patch("src.agents.llm_judge_agent.genai") as mock_genai, \
         patch("src.agents.llm_judge_agent.DEFAULT_RETRY_OPTIONS", None):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.side_effect = Exception("API quota exceeded")

        agent = LLMJudgeAgent(name="LLMJudge")
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)

    assert len(events) == 1
    assert "failed" in events[0].content.parts[0].text.lower()
    assert "error" in state["llm_judge_report"]

    # Check error report written to disk
    error_json = eval_dir / "llm_judge_report.json"
    assert error_json.exists()
    report = json.loads(error_json.read_text())
    assert "error" in report


@pytest.mark.asyncio
async def test_happy_path_writes_reports(mock_invocation_context, tmp_path):
    """Full happy path: Gemini returns structured report, files are written."""
    # Setup files
    pvmap_path = tmp_path / "generated_pvmap.csv"
    pvmap_path.write_text("key,property,value\nobs,observationAbout,dcid:country/USA")
    gt_path = tmp_path / "gt_pvmap.csv"
    gt_path.write_text("key,property,value\nobs,observationAbout,dcid:country/USA")
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    eval_dir = output_dir / "eval_results"
    eval_dir.mkdir()
    diff_path = eval_dir / "diff.txt"
    diff_path.write_text("No differences found")

    state = mock_invocation_context.session.state
    state["best_ground_truth_pvmap"] = str(gt_path)
    state["pvmap_path"] = str(pvmap_path)
    state["output_dir"] = str(output_dir)
    state["eval_metrics"] = {"node_accuracy": 100.0, "pv_accuracy": 100.0}
    state["data_context"] = {"dimension_columns": ["age"], "statvar_pattern": "Count_Person"}

    # Mock Gemini response
    mock_response_data = {
        "structural_quality": {"score": 5, "explanation": "Perfect structure", "issues": []},
        "semantic_accuracy": {"score": 4, "explanation": "Good props", "issues": ["minor naming"]},
        "value_mapping_quality": {"score": 5, "explanation": "All correct", "issues": []},
        "top_issues": ["minor naming issue"],
        "improvement_suggestions": ["rename prop X to Y"],
        "summary": "Excellent PVMAP with minor naming issues.",
    }

    mock_response = MagicMock()
    mock_response.text = json.dumps(mock_response_data)

    with patch("src.agents.llm_judge_agent.load_gemini_api_key", return_value="fake-key"), \
         patch("src.agents.llm_judge_agent.genai") as mock_genai, \
         patch("src.agents.llm_judge_agent.DEFAULT_RETRY_OPTIONS", None):
        mock_client = MagicMock()
        mock_genai.Client.return_value = mock_client
        mock_client.models.generate_content.return_value = mock_response

        agent = LLMJudgeAgent(name="LLMJudge")
        events = []
        async for event in agent._run_async_impl(mock_invocation_context):
            events.append(event)

    # Verify event
    assert len(events) == 1
    event_text = events[0].content.parts[0].text
    assert "Structural=5/5" in event_text
    assert "Semantic=4/5" in event_text
    assert "Overall: 4.7/5" in event_text

    # Verify state
    report = state["llm_judge_report"]
    assert report["overall_score"] == 4.7
    assert report["structural_quality"]["score"] == 5

    # Verify JSON file
    json_path = eval_dir / "llm_judge_report.json"
    assert json_path.exists()
    saved = json.loads(json_path.read_text())
    assert saved["overall_score"] == 4.7

    # Verify markdown file
    md_path = eval_dir / "llm_judge_report.md"
    assert md_path.exists()
    md_content = md_path.read_text()
    assert "LLM Judge Evaluation Report" in md_content
    assert "4.7/5" in md_content
