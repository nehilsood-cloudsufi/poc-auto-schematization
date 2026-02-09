"""
Unit tests for QualityFeedbackAgent and ConditionalQualityFeedbackAgent.

Tests the quality feedback generation and conditional execution logic.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
import asyncio

from src.agents.quality_feedback_agent import (
    create_quality_feedback_agent,
    ConditionalQualityFeedbackAgent,
    QUALITY_FEEDBACK_INSTRUCTION,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_ctx():
    """Create mock InvocationContext."""
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.state = {}
    return ctx


@pytest.fixture
def conditional_agent():
    """Create ConditionalQualityFeedbackAgent instance."""
    return ConditionalQualityFeedbackAgent(name="TestConditionalQualityFeedback")


# ============================================================================
# Helper Functions
# ============================================================================

async def collect_events(agent, ctx):
    """Collect all events from agent's async generator."""
    events = []
    async for event in agent._run_async_impl(ctx):
        events.append(event)
    return events


def run_agent(agent, ctx):
    """Run agent synchronously for testing."""
    return asyncio.get_event_loop().run_until_complete(collect_events(agent, ctx))


# ============================================================================
# Test create_quality_feedback_agent
# ============================================================================

class TestCreateQualityFeedbackAgent:
    """Tests for the create_quality_feedback_agent factory function."""

    def test_creates_llm_agent(self):
        """Should create an LlmAgent instance."""
        agent = create_quality_feedback_agent()
        assert agent.name == "QualityFeedbackAgent"

    def test_custom_name(self):
        """Should use custom name when provided."""
        agent = create_quality_feedback_agent(name="CustomFeedback")
        assert agent.name == "CustomFeedback"

    def test_output_key_is_quality_feedback(self):
        """Should set output_key to quality_feedback."""
        agent = create_quality_feedback_agent()
        assert agent.output_key == "quality_feedback"

    @patch.dict('os.environ', {'QUALITY_FEEDBACK_MODEL': 'gemini-1.5-pro'})
    def test_respects_environment_model_override(self):
        """Should use model from environment if set."""
        agent = create_quality_feedback_agent()
        # Model should be from environment
        assert agent.model == "gemini-1.5-pro"


# ============================================================================
# Test QUALITY_FEEDBACK_INSTRUCTION
# ============================================================================

class TestQualityFeedbackInstruction:
    """Tests for the instruction template."""

    def test_includes_required_placeholders(self):
        """Instruction should include all required state placeholders."""
        required_placeholders = [
            "{attempt_number}",
            "{quality_score}",
            "{quality_metrics}",
            "{quality_diff_summary}",
            "{pvmap_csv}",
            "{sampled_data}",
            "{gt_score_section}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in QUALITY_FEEDBACK_INSTRUCTION

    def test_includes_analysis_guidelines(self):
        """Instruction should include heuristic analysis guidelines."""
        assert "ANALYSIS GUIDELINES" in QUALITY_FEEDBACK_INSTRUCTION
        assert "heuristic" in QUALITY_FEEDBACK_INSTRUCTION.lower() or "coverage" in QUALITY_FEEDBACK_INSTRUCTION.lower()

    def test_no_ground_truth_content_leakage(self):
        """Instruction should not reference Ground Truth Mode or GT diffs."""
        assert "Ground Truth Mode" not in QUALITY_FEEDBACK_INSTRUCTION
        # "Ground Truth Accuracy" section header is OK (numeric scores only)
        assert "Ground Truth Accuracy" in QUALITY_FEEDBACK_INSTRUCTION
        # But should never mention GT diff analysis
        assert "diff provided" not in QUALITY_FEEDBACK_INSTRUCTION.lower()

    def test_includes_output_format(self):
        """Instruction should include output format guidance."""
        assert "OUTPUT FORMAT" in QUALITY_FEEDBACK_INSTRUCTION
        assert "Quality Gap Analysis" in QUALITY_FEEDBACK_INSTRUCTION
        assert "High-Impact Fixes" in QUALITY_FEEDBACK_INSTRUCTION


# ============================================================================
# Test ConditionalQualityFeedbackAgent - Conditional Execution
# ============================================================================

class TestConditionalExecution:
    """Tests for conditional execution logic."""

    def test_runs_when_validation_passed_quality_low(self, conditional_agent, mock_ctx):
        """Should run when validation passed but quality is low."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "attempt_number": 0,
            "quality_metrics": {"mode": "heuristic", "heuristic_score": 55.0},
            "quality_diff_summary": "Low coverage issues",
            "pvmap_csv": "key,prop,value",
            "sampled_data": "col1,col2",
        }

        # Mock the inner feedback agent to avoid actual LLM call
        # Use async generator pattern instead of iter()
        async def mock_run_async(ctx):
            if False:  # Empty generator
                yield

        mock_inner_agent = Mock()
        mock_inner_agent.run_async = mock_run_async
        conditional_agent.feedback_agent = mock_inner_agent

        events = run_agent(conditional_agent, mock_ctx)

        # Should have yielded "generating feedback" message
        assert any("generating" in str(e.content.parts[0].text).lower() for e in events)

    def test_skips_when_validation_failed(self, conditional_agent, mock_ctx):
        """Should skip when validation failed."""
        mock_ctx.session.state = {
            "validation_passed": False,
            "quality_acceptable": False,
            "quality_stagnant": False,
        }

        events = run_agent(conditional_agent, mock_ctx)

        # Should skip with message
        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()

    def test_skips_when_quality_acceptable(self, conditional_agent, mock_ctx):
        """Should skip when quality is already acceptable."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": True,
            "quality_stagnant": False,
        }

        events = run_agent(conditional_agent, mock_ctx)

        # Should skip with message
        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()
        assert "quality acceptable" in events[0].content.parts[0].text.lower()

    def test_skips_when_quality_stagnant(self, conditional_agent, mock_ctx):
        """Should skip when quality is stagnant."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": True,
        }

        events = run_agent(conditional_agent, mock_ctx)

        # Should skip with message
        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()
        assert "stagnant" in events[0].content.parts[0].text.lower()


# ============================================================================
# Test State Preparation
# ============================================================================

class TestStatePreperation:
    """Tests for state preparation before feedback generation."""

    def test_prepares_quality_score_from_heuristic(self, conditional_agent, mock_ctx):
        """Should extract heuristic_score as quality_score."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "quality_metrics": {"mode": "heuristic", "heuristic_score": 65.0},
        }

        conditional_agent._prepare_feedback_state(mock_ctx)

        assert mock_ctx.session.state["quality_score"] == 65.0

    def test_increments_attempt_number_for_display(self, conditional_agent, mock_ctx):
        """Should increment attempt_number for 1-indexed display."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "quality_metrics": {"mode": "heuristic", "heuristic_score": 55.0},
            "attempt_number": 0,  # 0-indexed
        }

        conditional_agent._prepare_feedback_state(mock_ctx)

        # Should be 1-indexed for display
        assert mock_ctx.session.state["attempt_number"] == 1


# ============================================================================
# Test Metrics Formatting
# ============================================================================

class TestMetricsFormatting:
    """Tests for _format_metrics helper method."""

    def test_formats_heuristic_metrics(self, conditional_agent):
        """Should format heuristic metrics correctly."""
        metrics = {
            "mode": "heuristic",
            "heuristic_score": 65.0,
            "heuristic_breakdown": {
                "row_coverage": 15.0,
                "prop_coverage": 20.0,
                "column_coverage": 15.0,
                "format_score": 15.0,
            },
        }

        formatted = conditional_agent._format_metrics(metrics)

        assert "Heuristic Score: 65.0/100" in formatted
        assert "Row Coverage: 15.0/25" in formatted
        assert "Property Coverage: 20.0/25" in formatted
        assert "Column Coverage: 15.0/25" in formatted
        assert "Format Score: 15.0/25" in formatted

    def test_includes_improvement_when_present(self, conditional_agent):
        """Should include improvement from previous when available."""
        metrics = {
            "mode": "heuristic",
            "heuristic_score": 60.0,
            "heuristic_breakdown": {},
            "improvement_from_previous": 3.5,
        }

        formatted = conditional_agent._format_metrics(metrics)

        assert "Improvement from previous: 3.5%" in formatted


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_missing_quality_metrics(self, conditional_agent, mock_ctx):
        """Should handle missing quality_metrics gracefully."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": False,
            # No quality_metrics
        }

        # Should not crash
        conditional_agent._prepare_feedback_state(mock_ctx)

        assert mock_ctx.session.state["quality_score"] == 0

    def test_handles_empty_quality_metrics(self, conditional_agent, mock_ctx):
        """Should handle empty quality_metrics dict."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "quality_metrics": {},
        }

        conditional_agent._prepare_feedback_state(mock_ctx)

        assert mock_ctx.session.state["quality_score"] == 0

    def test_formats_empty_metrics(self, conditional_agent):
        """Should handle empty metrics dict in formatting."""
        formatted = conditional_agent._format_metrics({})
        # Empty metrics defaults to heuristic mode with 0 score
        assert "0.0" in formatted or formatted == ""


# ============================================================================
# Test GT Score Formatting
# ============================================================================

class TestGTScoreFormatting:
    """Tests for _format_gt_section and GT scores in _format_metrics."""

    def test_format_gt_section_with_scores(self, conditional_agent):
        """Should format GT section with scores and counters."""
        metrics = {
            "gt_node_accuracy": 75.0,
            "gt_pv_accuracy": 60.0,
            "gt_counters_summary": {
                "nodes_matched": 3,
                "nodes_ground_truth": 4,
                "pvs_matched": 6,
                "pvs_modified": 2,
            }
        }
        result = conditional_agent._format_gt_section(metrics)
        assert "Node Accuracy: 75.0%" in result
        assert "PV Accuracy: 60.0%" in result
        assert "Nodes matched: 3/4" in result
        assert "distance from ideal" in result

    def test_format_gt_section_without_gt(self, conditional_agent):
        """Should show 'not available' when GT not present."""
        result = conditional_agent._format_gt_section({})
        assert "not available" in result

    def test_format_gt_section_no_counters(self, conditional_agent):
        """Should format even without counters."""
        metrics = {
            "gt_node_accuracy": 50.0,
            "gt_pv_accuracy": 30.0,
        }
        result = conditional_agent._format_gt_section(metrics)
        assert "Node Accuracy: 50.0%" in result
        assert "PV Accuracy: 30.0%" in result

    def test_format_metrics_with_gt_scores(self, conditional_agent):
        """_format_metrics should include GT scores when present."""
        metrics = {
            "heuristic_score": 55.0,
            "heuristic_breakdown": {
                "row_coverage": 15.0,
                "prop_coverage": 20.0,
                "column_coverage": 10.0,
                "format_score": 10.0,
            },
            "gt_node_accuracy": 42.0,
            "gt_pv_accuracy": 33.5,
        }
        result = conditional_agent._format_metrics(metrics)
        assert "GT Node Accuracy: 42.0%" in result
        assert "GT PV Accuracy: 33.5%" in result
        assert "Heuristic Score: 55.0/100" in result

    def test_format_metrics_without_gt_scores(self, conditional_agent):
        """_format_metrics should not include GT lines when not present."""
        metrics = {
            "heuristic_score": 55.0,
            "heuristic_breakdown": {},
        }
        result = conditional_agent._format_metrics(metrics)
        assert "GT Node Accuracy" not in result
        assert "GT PV Accuracy" not in result

    def test_prepare_feedback_state_sets_gt_section(self, conditional_agent, mock_ctx):
        """_prepare_feedback_state should set gt_score_section in state."""
        mock_ctx.session.state = {
            "quality_metrics": {
                "heuristic_score": 55.0,
                "gt_node_accuracy": 40.0,
                "gt_pv_accuracy": 25.0,
                "gt_counters_summary": {
                    "nodes_matched": 2,
                    "nodes_ground_truth": 5,
                    "pvs_matched": 3,
                    "pvs_modified": 4,
                }
            },
        }

        conditional_agent._prepare_feedback_state(mock_ctx)

        gt_section = mock_ctx.session.state["gt_score_section"]
        assert "Node Accuracy: 40.0%" in gt_section
        assert "PV Accuracy: 25.0%" in gt_section

    def test_prepare_feedback_state_no_gt(self, conditional_agent, mock_ctx):
        """_prepare_feedback_state should handle no GT gracefully."""
        mock_ctx.session.state = {
            "quality_metrics": {"heuristic_score": 55.0},
        }

        conditional_agent._prepare_feedback_state(mock_ctx)

        gt_section = mock_ctx.session.state["gt_score_section"]
        assert "not available" in gt_section
