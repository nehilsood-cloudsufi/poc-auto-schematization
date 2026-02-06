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
            "{quality_mode}",
            "{quality_score}",
            "{quality_metrics}",
            "{quality_diff_summary}",
            "{pvmap_csv}",
            "{sampled_data}",
        ]
        for placeholder in required_placeholders:
            assert placeholder in QUALITY_FEEDBACK_INSTRUCTION

    def test_includes_analysis_guidelines(self):
        """Instruction should include analysis guidelines."""
        assert "ANALYSIS GUIDELINES" in QUALITY_FEEDBACK_INSTRUCTION
        assert "Ground Truth Mode" in QUALITY_FEEDBACK_INSTRUCTION
        assert "Heuristic Mode" in QUALITY_FEEDBACK_INSTRUCTION

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
            "quality_metrics": {"mode": "ground_truth", "pv_accuracy": 15.0},
            "quality_diff_summary": "Some diff",
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

    def test_prepares_quality_mode_from_metrics(self, conditional_agent, mock_ctx):
        """Should extract quality_mode from quality_metrics dict."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "quality_metrics": {"mode": "ground_truth", "pv_accuracy": 20.0},
        }

        # Access private method for testing
        conditional_agent._prepare_feedback_state(mock_ctx)

        assert mock_ctx.session.state["quality_mode"] == "ground_truth"

    def test_prepares_quality_score_gt_mode(self, conditional_agent, mock_ctx):
        """Should extract pv_accuracy as quality_score for GT mode."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "quality_metrics": {"mode": "ground_truth", "pv_accuracy": 25.5},
        }

        conditional_agent._prepare_feedback_state(mock_ctx)

        assert mock_ctx.session.state["quality_score"] == 25.5

    def test_prepares_quality_score_heuristic_mode(self, conditional_agent, mock_ctx):
        """Should extract heuristic_score as quality_score for heuristic mode."""
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
            "quality_metrics": {"mode": "ground_truth", "pv_accuracy": 20.0},
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

    def test_formats_gt_metrics(self, conditional_agent):
        """Should format ground truth metrics correctly."""
        metrics = {
            "mode": "ground_truth",
            "pv_accuracy": 25.5,
            "node_accuracy": 30.0,
            "counters": {
                "nodes-matched": 5,
                "nodes-ground-truth": 10,
                "PVs-matched": 20,
            },
        }

        formatted = conditional_agent._format_metrics(metrics)

        assert "PV Accuracy: 25.5%" in formatted
        assert "Node Accuracy: 30.0%" in formatted
        assert "Nodes Matched: 5/10" in formatted
        assert "PVs Matched: 20" in formatted

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
            "mode": "ground_truth",
            "pv_accuracy": 25.0,
            "node_accuracy": 30.0,
            "counters": {},
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

        assert mock_ctx.session.state["quality_mode"] == "unknown"
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

        assert mock_ctx.session.state["quality_mode"] == "unknown"

    def test_formats_empty_metrics(self, conditional_agent):
        """Should handle empty metrics dict in formatting."""
        formatted = conditional_agent._format_metrics({})
        # Empty metrics defaults to heuristic mode with 0 score
        assert "0.0" in formatted or formatted == ""
