"""
Unit tests for QualityEvaluationAgent.

Tests the quality evaluation logic for ground truth and heuristic modes.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import asyncio

from src.agents.quality_evaluation_agent import QualityEvaluationAgent


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_dataset():
    """Create mock DatasetInfo object."""
    dataset = Mock()
    dataset.name = "test_dataset"
    dataset.output_dir = Path("/tmp/test_output")
    return dataset


@pytest.fixture
def mock_ctx():
    """Create mock InvocationContext."""
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.state = {}
    return ctx


@pytest.fixture
def quality_agent():
    """Create QualityEvaluationAgent instance."""
    return QualityEvaluationAgent(name="TestQualityEvaluator")


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
# Test Validation Not Passed
# ============================================================================

class TestValidationNotPassed:
    """Tests when validation_passed is False."""

    def test_skips_quality_evaluation_when_validation_failed(self, quality_agent, mock_ctx):
        """Should skip quality evaluation if validation didn't pass."""
        mock_ctx.session.state = {
            "validation_passed": False,
        }

        events = run_agent(quality_agent, mock_ctx)

        # Should yield skip message
        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()
        assert events[0].actions.escalate is False

        # State should not have quality metrics
        assert mock_ctx.session.state.get("quality_acceptable") is None

    def test_skips_when_validation_passed_not_set(self, quality_agent, mock_ctx):
        """Should skip if validation_passed is not in state."""
        mock_ctx.session.state = {}

        events = run_agent(quality_agent, mock_ctx)

        assert len(events) == 1
        assert events[0].actions.escalate is False


# ============================================================================
# Test Ground Truth Mode
# ============================================================================

class TestGroundTruthMode:
    """Tests for quality evaluation with ground truth."""

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    def test_quality_acceptable_with_gt_above_threshold(
        self, mock_compare, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """PV accuracy >= 30% should set quality_acceptable = True."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value\nYear,observationDate,{Data}",
            "attempt_number": 0,
            "quality_metrics_history": [],
        }

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [Path("/tmp/gt.csv")],
            "count": 1,
        }

        mock_compare.return_value = {
            "success": True,
            "pv_accuracy": 35.0,  # Above threshold
            "accuracy": 40.0,
            "counters": {},
            "diff_text": "diff output",
        }

        events = run_agent(quality_agent, mock_ctx)

        # Should escalate (quality acceptable)
        assert any(e.actions.escalate for e in events if e.actions)
        assert mock_ctx.session.state["quality_acceptable"] is True
        assert mock_ctx.session.state["exit_reason"] == "quality_met"

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    def test_quality_unacceptable_with_gt_below_threshold(
        self, mock_compare, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """PV accuracy < 30% should set quality_acceptable = False."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
        }

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [Path("/tmp/gt.csv")],
            "count": 1,
        }

        mock_compare.return_value = {
            "success": True,
            "pv_accuracy": 20.0,  # Below threshold
            "accuracy": 25.0,
            "counters": {},
            "diff_text": "diff output",
        }

        events = run_agent(quality_agent, mock_ctx)

        # Should NOT escalate (quality low)
        final_event = [e for e in events if e.actions][-1]
        assert final_event.actions.escalate is False
        assert mock_ctx.session.state["quality_acceptable"] is False

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    def test_escalate_on_quality_acceptable(
        self, mock_compare, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """Should escalate=True when quality is acceptable."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
        }

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [Path("/tmp/gt.csv")],
            "count": 1,
        }

        mock_compare.return_value = {
            "success": True,
            "pv_accuracy": 50.0,  # Well above threshold
            "accuracy": 60.0,
            "counters": {},
            "diff_text": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        # Last event with actions should have escalate=True
        events_with_actions = [e for e in events if e.actions]
        assert any(e.actions.escalate for e in events_with_actions)


# ============================================================================
# Test Heuristic Mode
# ============================================================================

class TestHeuristicMode:
    """Tests for quality evaluation with heuristic scoring."""

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_uses_heuristics_when_no_gt(
        self, mock_heuristic, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """Should use heuristic scoring when no ground truth available."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "col1,col2\nval1,val2",
            "metadata": "",
        }

        mock_find_gt.return_value = {
            "success": False,
            "pvmaps": [],
            "count": 0,
            "error": "No ground truth found",
        }

        mock_heuristic.return_value = {
            "total": 75.0,  # Above heuristic threshold
            "row_coverage": 20.0,
            "prop_coverage": 20.0,
            "column_coverage": 20.0,
            "format_score": 15.0,
            "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        # Should call heuristic scoring
        mock_heuristic.assert_called_once()

        # Should set mode to heuristic
        metrics = mock_ctx.session.state["quality_metrics"]
        assert metrics["mode"] == "heuristic"
        assert "heuristic_score" in metrics

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_heuristic_threshold_70(
        self, mock_heuristic, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """Heuristic score >= 70 should be acceptable."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
        }

        mock_find_gt.return_value = {"success": False, "pvmaps": [], "count": 0}

        # Test boundary: exactly 70
        mock_heuristic.return_value = {
            "total": 70.0,
            "row_coverage": 17.5,
            "prop_coverage": 17.5,
            "column_coverage": 17.5,
            "format_score": 17.5,
            "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)
        assert mock_ctx.session.state["quality_acceptable"] is True

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_heuristic_below_threshold(
        self, mock_heuristic, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """Heuristic score < 70 should not be acceptable."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
        }

        mock_find_gt.return_value = {"success": False, "pvmaps": [], "count": 0}

        mock_heuristic.return_value = {
            "total": 65.0,  # Below threshold
            "row_coverage": 15.0,
            "prop_coverage": 15.0,
            "column_coverage": 20.0,
            "format_score": 15.0,
            "issues": "Some issues",
        }

        events = run_agent(quality_agent, mock_ctx)
        assert mock_ctx.session.state["quality_acceptable"] is False


# ============================================================================
# Test Stagnation Detection
# ============================================================================

class TestStagnationDetection:
    """Tests for quality stagnation detection."""

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    def test_stagnation_detected_no_improvement(
        self, mock_compare, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """Improvement < 5% should set quality_stagnant = True."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 1,  # Second attempt
            "quality_metrics_history": [
                {"pv_accuracy": 20.0, "mode": "ground_truth", "attempt": 0}
            ],
        }

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [Path("/tmp/gt.csv")],
            "count": 1,
        }

        mock_compare.return_value = {
            "success": True,
            "pv_accuracy": 22.0,  # Only 2% improvement (< 5%)
            "accuracy": 25.0,
            "counters": {},
            "diff_text": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_stagnant"] is True
        assert mock_ctx.session.state["exit_reason"] == "stagnant"

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    def test_stagnation_not_triggered_on_first_attempt(
        self, mock_compare, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """First attempt should never trigger stagnation."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,  # First attempt
            "quality_metrics_history": [],
        }

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [Path("/tmp/gt.csv")],
            "count": 1,
        }

        mock_compare.return_value = {
            "success": True,
            "pv_accuracy": 15.0,
            "accuracy": 20.0,
            "counters": {},
            "diff_text": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_stagnant"] is False

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    def test_good_improvement_not_stagnant(
        self, mock_compare, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """Improvement >= 5% should not be stagnant."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 1,
            "quality_metrics_history": [
                {"pv_accuracy": 20.0, "mode": "ground_truth", "attempt": 0}
            ],
        }

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [Path("/tmp/gt.csv")],
            "count": 1,
        }

        mock_compare.return_value = {
            "success": True,
            "pv_accuracy": 28.0,  # 8% improvement (>= 5%)
            "accuracy": 30.0,
            "counters": {},
            "diff_text": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_stagnant"] is False


# ============================================================================
# Test Metrics History
# ============================================================================

class TestMetricsHistory:
    """Tests for quality metrics history accumulation."""

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    def test_metrics_history_accumulation(
        self, mock_compare, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """Metrics should accumulate across attempts."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value",
            "attempt_number": 2,  # Third attempt
            "quality_metrics_history": [
                {"pv_accuracy": 15.0, "attempt": 0},
                {"pv_accuracy": 22.0, "attempt": 1},
            ],
        }

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [Path("/tmp/gt.csv")],
            "count": 1,
        }

        mock_compare.return_value = {
            "success": True,
            "pv_accuracy": 25.0,
            "accuracy": 28.0,
            "counters": {},
            "diff_text": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        history = mock_ctx.session.state["quality_metrics_history"]
        assert len(history) == 3
        assert history[-1]["attempt"] == 2


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Tests for error handling scenarios."""

    def test_missing_current_dataset(self, quality_agent, mock_ctx):
        """Should handle missing current_dataset gracefully."""
        mock_ctx.session.state = {
            "validation_passed": True,
            # No current_dataset
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_acceptable"] is False
        assert "error" in mock_ctx.session.state.get("quality_metrics", {})

    @patch('src.agents.quality_evaluation_agent.find_ground_truth_pvmaps')
    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    def test_comparison_failure_falls_back_to_heuristics(
        self, mock_compare, mock_find_gt, quality_agent, mock_ctx, mock_dataset
    ):
        """Should fall back to heuristics if GT comparison fails."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_path": "/tmp/test.csv",
            "pvmap_csv": "key,prop,value\nYear,observationDate,{Data}",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "Year,Value\n2020,100",
            "metadata": "",
        }

        mock_find_gt.return_value = {
            "success": True,
            "pvmaps": [Path("/tmp/gt.csv")],
            "count": 1,
        }

        mock_compare.return_value = {
            "success": False,
            "error": "Comparison failed",
        }

        events = run_agent(quality_agent, mock_ctx)

        # Should have fallen back to heuristics
        metrics = mock_ctx.session.state["quality_metrics"]
        assert metrics["mode"] == "heuristic"
