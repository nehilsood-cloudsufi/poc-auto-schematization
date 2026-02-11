"""
Unit tests for QualityEvaluationAgent.

Tests the quality evaluation logic using heuristic scoring with optional
ground truth numeric scoring (scores only, never diff_text content).
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
# Test Heuristic Mode (only mode now - no ground truth in retry loop)
# ============================================================================

class TestHeuristicMode:
    """Tests for quality evaluation with heuristic scoring."""

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_always_uses_heuristics(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Should always use heuristic scoring (no GT in retry loop)."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "col1,col2\nval1,val2",
            "metadata": "",
        }

        mock_heuristic.return_value = {
            "total": 75.0,
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

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_heuristic_threshold_70(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Heuristic score >= 70 should be acceptable."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
        }

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

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_heuristic_below_threshold(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Heuristic score < 70 should not be acceptable."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
        }

        mock_heuristic.return_value = {
            "total": 65.0,
            "row_coverage": 15.0,
            "prop_coverage": 15.0,
            "column_coverage": 20.0,
            "format_score": 15.0,
            "issues": "Some issues",
        }

        events = run_agent(quality_agent, mock_ctx)
        assert mock_ctx.session.state["quality_acceptable"] is False

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_escalates_on_quality_acceptable(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Should escalate=True when quality is acceptable."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
        }

        mock_heuristic.return_value = {
            "total": 80.0,
            "row_coverage": 20.0,
            "prop_coverage": 20.0,
            "column_coverage": 20.0,
            "format_score": 20.0,
            "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        events_with_actions = [e for e in events if e.actions]
        assert any(e.actions.escalate for e in events_with_actions)
        assert mock_ctx.session.state["exit_reason"] == "quality_met"

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_does_not_escalate_on_low_quality(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Should not escalate when quality is low."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
        }

        mock_heuristic.return_value = {
            "total": 50.0,
            "row_coverage": 10.0,
            "prop_coverage": 15.0,
            "column_coverage": 15.0,
            "format_score": 10.0,
            "issues": "Low coverage",
        }

        events = run_agent(quality_agent, mock_ctx)

        final_event = [e for e in events if e.actions][-1]
        assert final_event.actions.escalate is False
        assert mock_ctx.session.state["quality_acceptable"] is False


# ============================================================================
# Test Stagnation Detection
# ============================================================================

class TestStagnationDetection:
    """Tests for quality stagnation detection."""

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_stagnation_detected_no_improvement(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Improvement < 10% of previous accuracy should set quality_stagnant = True."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 1,  # Second attempt
            "quality_metrics_history": [
                {"heuristic_score": 55.0, "mode": "heuristic", "attempt": 0}
            ],
            "sampled_data": "",
            "metadata": "",
        }

        mock_heuristic.return_value = {
            "total": 57.0,  # Only 2 point improvement (< 5.5 = 10% of 55)
            "row_coverage": 14.0,
            "prop_coverage": 14.0,
            "column_coverage": 15.0,
            "format_score": 14.0,
            "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_stagnant"] is True
        assert mock_ctx.session.state["exit_reason"] == "stagnant"

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_stagnation_not_triggered_on_first_attempt(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """First attempt should never trigger stagnation."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,  # First attempt
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
        }

        mock_heuristic.return_value = {
            "total": 45.0,
            "row_coverage": 10.0,
            "prop_coverage": 10.0,
            "column_coverage": 15.0,
            "format_score": 10.0,
            "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_stagnant"] is False

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_good_improvement_not_stagnant(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Improvement >= 10% of previous accuracy should not be stagnant."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 1,
            "quality_metrics_history": [
                {"heuristic_score": 50.0, "mode": "heuristic", "attempt": 0}
            ],
            "sampled_data": "",
            "metadata": "",
        }

        mock_heuristic.return_value = {
            "total": 60.0,  # 10 point improvement (>= 5.0 = 10% of 50)
            "row_coverage": 15.0,
            "prop_coverage": 15.0,
            "column_coverage": 15.0,
            "format_score": 15.0,
            "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_stagnant"] is False


# ============================================================================
# Test Metrics History
# ============================================================================

class TestMetricsHistory:
    """Tests for quality metrics history accumulation."""

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_metrics_history_accumulation(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Metrics should accumulate across attempts."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 2,  # Third attempt
            "quality_metrics_history": [
                {"heuristic_score": 45.0, "attempt": 0},
                {"heuristic_score": 55.0, "attempt": 1},
            ],
            "sampled_data": "",
            "metadata": "",
        }

        mock_heuristic.return_value = {
            "total": 65.0,
            "row_coverage": 16.0,
            "prop_coverage": 16.0,
            "column_coverage": 17.0,
            "format_score": 16.0,
            "issues": "",
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


# ============================================================================
# Test No Ground Truth Content Leakage
# ============================================================================

class TestNoGroundTruthContentLeakage:
    """Verify that ground truth CONTENT (diff_text) never reaches state."""

    def test_single_quality_threshold(self, quality_agent):
        """Should have a single threshold (heuristic-based, not GT-based)."""
        assert quality_agent.QUALITY_THRESHOLD == 70.0
        assert not hasattr(quality_agent, 'HEURISTIC_THRESHOLD')

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_diff_text_never_reaches_state(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """diff_text from GT comparison must NEVER appear in any state key."""
        # Create a real pvmap file so Path.exists() passes
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/tmp/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 55.0, "row_coverage": 14.0, "prop_coverage": 14.0,
            "column_coverage": 14.0, "format_score": 13.0, "issues": "Low coverage",
        }
        mock_compare.return_value = {
            "success": True,
            "accuracy": 40.0,
            "pv_accuracy": 25.0,
            "counters": {"nodes-matched": 2, "nodes-ground-truth": 5,
                         "PVs-matched": 3, "pvs-modified": 4, "pvs-deleted": 2,
                         "nodes-auto-generated": 6},
            "diff_text": "LEAKED: - populationType: Person\n+ populationType: Household",
            "error": None,
        }

        events = run_agent(quality_agent, mock_ctx)

        # Verify diff_text never stored in any state key
        for key, value in mock_ctx.session.state.items():
            if isinstance(value, str):
                assert "LEAKED" not in value, f"diff_text leaked into state key '{key}'"
                assert "populationType: Person" not in value, f"GT content leaked into state key '{key}'"
            if isinstance(value, dict):
                assert "diff_text" not in value, f"diff_text key found in state key '{key}'"

        # But GT numeric scores should be present
        metrics = mock_ctx.session.state["quality_metrics"]
        assert metrics["gt_node_accuracy"] == 40.0
        assert metrics["gt_pv_accuracy"] == 25.0


# ============================================================================
# Test GT Numeric Scoring
# ============================================================================

class TestGTNumericScoring:
    """Tests for ground truth numeric scoring integration."""

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_gt_scores_merged_into_quality_metrics(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """GT numeric scores should be merged into quality_metrics dict."""
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/tmp/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 60.0, "row_coverage": 15.0, "prop_coverage": 15.0,
            "column_coverage": 15.0, "format_score": 15.0, "issues": "",
        }
        mock_compare.return_value = {
            "success": True, "accuracy": 75.0, "pv_accuracy": 60.0,
            "counters": {"nodes-matched": 3, "nodes-ground-truth": 4,
                         "PVs-matched": 6, "pvs-modified": 2, "pvs-deleted": 1,
                         "nodes-auto-generated": 5},
            "diff_text": "some diff", "error": None,
        }

        events = run_agent(quality_agent, mock_ctx)

        metrics = mock_ctx.session.state["quality_metrics"]
        assert metrics["gt_node_accuracy"] == 75.0
        assert metrics["gt_pv_accuracy"] == 60.0
        assert metrics["gt_counters_summary"]["nodes_matched"] == 3
        assert metrics["gt_counters_summary"]["nodes_ground_truth"] == 4
        assert metrics["gt_counters_summary"]["pvs_matched"] == 6
        # Heuristic score also present
        assert metrics["heuristic_score"] == 60.0

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_no_gt_when_cache_is_none(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Should not attempt GT comparison when gt_pvmap_path_cached is None."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": None,
        }

        mock_heuristic.return_value = {
            "total": 55.0, "row_coverage": 14.0, "prop_coverage": 14.0,
            "column_coverage": 14.0, "format_score": 13.0, "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        metrics = mock_ctx.session.state["quality_metrics"]
        assert "gt_node_accuracy" not in metrics
        assert "gt_pv_accuracy" not in metrics

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_no_gt_when_cache_not_in_state(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """Should work fine when gt_pvmap_path_cached key doesn't exist."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            # No gt_pvmap_path_cached key at all
        }

        mock_heuristic.return_value = {
            "total": 55.0, "row_coverage": 14.0, "prop_coverage": 14.0,
            "column_coverage": 14.0, "format_score": 13.0, "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        metrics = mock_ctx.session.state["quality_metrics"]
        assert "gt_node_accuracy" not in metrics

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_gt_comparison_failure_non_fatal(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """GT comparison failure should not crash the agent."""
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/nonexistent/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 55.0, "row_coverage": 14.0, "prop_coverage": 14.0,
            "column_coverage": 14.0, "format_score": 13.0, "issues": "",
        }
        mock_compare.return_value = {
            "success": False, "error": "File not found",
            "counters": {}, "diff_text": None, "accuracy": 0.0, "pv_accuracy": 0.0,
        }

        events = run_agent(quality_agent, mock_ctx)

        # Should still have heuristic scores, no GT scores
        metrics = mock_ctx.session.state["quality_metrics"]
        assert "heuristic_score" in metrics
        assert "gt_node_accuracy" not in metrics

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_gt_scores_in_log_messages(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """Log messages should include GT scores when available."""
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/tmp/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 55.0, "row_coverage": 14.0, "prop_coverage": 14.0,
            "column_coverage": 14.0, "format_score": 13.0, "issues": "",
        }
        mock_compare.return_value = {
            "success": True, "accuracy": 40.0, "pv_accuracy": 25.0,
            "counters": {"nodes-matched": 2, "nodes-ground-truth": 5,
                         "PVs-matched": 3, "pvs-modified": 4, "pvs-deleted": 2,
                         "nodes-auto-generated": 6},
            "diff_text": "", "error": None,
        }

        events = run_agent(quality_agent, mock_ctx)

        # Find the GT scores event
        event_texts = [e.content.parts[0].text for e in events]
        assert any("GT scores" in t for t in event_texts)
        assert any("Node Acc=40.0%" in t for t in event_texts)


# ============================================================================
# Test PV Accuracy Retry Trigger (Priority 2)
# ============================================================================

class TestPVAccuracyRetryTrigger:
    """Tests for PV accuracy as a retry trigger (Priority 2 in the gating chain)."""

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_pv_below_threshold_overrides_heuristic_acceptable(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """Heuristic=80 (>70) but PV=15% (<30%) should override to quality_acceptable=False."""
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/tmp/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 80.0, "row_coverage": 20.0, "prop_coverage": 20.0,
            "column_coverage": 20.0, "format_score": 20.0, "issues": "",
        }
        mock_compare.return_value = {
            "success": True, "accuracy": 30.0, "pv_accuracy": 15.0,
            "counters": {"nodes-matched": 2, "nodes-ground-truth": 5,
                         "PVs-matched": 3, "pvs-modified": 4, "pvs-deleted": 2,
                         "nodes-auto-generated": 6},
            "diff_text": "", "error": None,
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_acceptable"] is False
        metrics = mock_ctx.session.state["quality_metrics"]
        assert metrics["quality_reject_reason"] == "pv_accuracy_low"

        # Final event should NOT escalate (low quality → continue to feedback)
        final_event = [e for e in events if e.actions][-1]
        assert final_event.actions.escalate is False

        # Message should mention PV accuracy
        assert "PV accuracy" in final_event.content.parts[0].text

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_pv_above_threshold_with_good_heuristic(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """Heuristic=80, PV=40% (both above thresholds) should be acceptable."""
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/tmp/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 80.0, "row_coverage": 20.0, "prop_coverage": 20.0,
            "column_coverage": 20.0, "format_score": 20.0, "issues": "",
        }
        mock_compare.return_value = {
            "success": True, "accuracy": 60.0, "pv_accuracy": 40.0,
            "counters": {"nodes-matched": 3, "nodes-ground-truth": 5,
                         "PVs-matched": 6, "pvs-modified": 2, "pvs-deleted": 1,
                         "nodes-auto-generated": 5},
            "diff_text": "", "error": None,
        }

        events = run_agent(quality_agent, mock_ctx)

        assert mock_ctx.session.state["quality_acceptable"] is True
        # Should escalate
        events_with_actions = [e for e in events if e.actions]
        assert any(e.actions.escalate for e in events_with_actions)

    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_no_gt_falls_back_to_heuristic_only(
        self, mock_heuristic, quality_agent, mock_ctx, mock_dataset
    ):
        """No GT path → quality_acceptable based on heuristic only."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "",
            "metadata": "",
            # No gt_pvmap_path_cached
        }

        mock_heuristic.return_value = {
            "total": 80.0, "row_coverage": 20.0, "prop_coverage": 20.0,
            "column_coverage": 20.0, "format_score": 20.0, "issues": "",
        }

        events = run_agent(quality_agent, mock_ctx)

        # Heuristic is 80 >= 70, so should be acceptable
        assert mock_ctx.session.state["quality_acceptable"] is True
        metrics = mock_ctx.session.state["quality_metrics"]
        # No reject reason should be set
        assert "quality_reject_reason" not in metrics
        # No GT scores
        assert "gt_pv_accuracy" not in metrics

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_stagnation_uses_pv_delta_when_pv_triggered(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """When PV is the reject reason, stagnation should check PV delta."""
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 1,
            "quality_metrics_history": [
                {"heuristic_score": 75.0, "gt_pv_accuracy": 12.0, "attempt": 0}
            ],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/tmp/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 80.0, "row_coverage": 20.0, "prop_coverage": 20.0,
            "column_coverage": 20.0, "format_score": 20.0, "issues": "",
        }
        mock_compare.return_value = {
            "success": True, "accuracy": 30.0, "pv_accuracy": 13.0,  # Only 1% improvement
            "counters": {"nodes-matched": 2, "nodes-ground-truth": 5,
                         "PVs-matched": 3, "pvs-modified": 4, "pvs-deleted": 2,
                         "nodes-auto-generated": 6},
            "diff_text": "", "error": None,
        }

        events = run_agent(quality_agent, mock_ctx)

        # PV accuracy 13% < 30% → quality_reject_reason = pv_accuracy_low
        metrics = mock_ctx.session.state["quality_metrics"]
        assert metrics["quality_reject_reason"] == "pv_accuracy_low"

        # PV delta = 13 - 12 = 1 < 1.2 (10% of 12) → stagnant
        assert mock_ctx.session.state["quality_stagnant"] is True
        assert metrics["pv_improvement_from_previous"] == 1.0

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_stagnation_uses_heuristic_delta_when_heuristic_triggered(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """When heuristic is the reject reason, stagnation should check heuristic delta."""
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 1,
            "quality_metrics_history": [
                {"heuristic_score": 55.0, "gt_pv_accuracy": 40.0, "attempt": 0}
            ],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/tmp/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 57.0, "row_coverage": 14.0, "prop_coverage": 14.0,
            "column_coverage": 15.0, "format_score": 14.0, "issues": "",
        }
        # PV accuracy is above threshold, so heuristic is the gating factor
        mock_compare.return_value = {
            "success": True, "accuracy": 60.0, "pv_accuracy": 42.0,
            "counters": {"nodes-matched": 3, "nodes-ground-truth": 5,
                         "PVs-matched": 6, "pvs-modified": 2, "pvs-deleted": 1,
                         "nodes-auto-generated": 5},
            "diff_text": "", "error": None,
        }

        events = run_agent(quality_agent, mock_ctx)

        # Heuristic 57 < 70 → quality_reject_reason = heuristic_low
        metrics = mock_ctx.session.state["quality_metrics"]
        assert metrics["quality_reject_reason"] == "heuristic_low"

        # Heuristic delta = 57 - 55 = 2 < 5.5 (10% of 55) → stagnant
        assert mock_ctx.session.state["quality_stagnant"] is True
        assert metrics["improvement_from_previous"] == 2.0
        # No PV improvement tracked since PV wasn't the trigger
        assert "pv_improvement_from_previous" not in metrics

    @patch('src.agents.quality_evaluation_agent.compare_pvmaps')
    @patch('src.agents.quality_evaluation_agent.calculate_heuristic_score')
    def test_stagnation_message_includes_reasoning(
        self, mock_heuristic, mock_compare, quality_agent, mock_ctx, mock_dataset, tmp_path
    ):
        """Stagnation event text should explain which metric and its delta."""
        pvmap_file = tmp_path / "test.csv"
        pvmap_file.write_text("key,prop,value")
        mock_dataset.output_dir = tmp_path / "output"

        mock_ctx.session.state = {
            "validation_passed": True,
            "current_dataset": mock_dataset,
            "pvmap_csv": "key,prop,value",
            "pvmap_path": str(pvmap_file),
            "attempt_number": 1,
            "quality_metrics_history": [
                {"heuristic_score": 75.0, "gt_pv_accuracy": 10.0, "attempt": 0}
            ],
            "sampled_data": "",
            "metadata": "",
            "gt_pvmap_path_cached": "/tmp/gt.csv",
        }

        mock_heuristic.return_value = {
            "total": 78.0, "row_coverage": 19.0, "prop_coverage": 20.0,
            "column_coverage": 20.0, "format_score": 19.0, "issues": "",
        }
        mock_compare.return_value = {
            "success": True, "accuracy": 25.0, "pv_accuracy": 10.5,  # 0.5% improvement (< 1.0 = 10% of 10)
            "counters": {"nodes-matched": 2, "nodes-ground-truth": 5,
                         "PVs-matched": 3, "pvs-modified": 4, "pvs-deleted": 2,
                         "nodes-auto-generated": 6},
            "diff_text": "", "error": None,
        }

        events = run_agent(quality_agent, mock_ctx)

        # Should be stagnant (PV delta = 0.5 < 1.0 = 10% of 10)
        assert mock_ctx.session.state["quality_stagnant"] is True

        # Stagnation event should include PV accuracy reasoning
        event_texts = [e.content.parts[0].text for e in events]
        stagnation_events = [t for t in event_texts if "STAGNANT" in t or "Stagnation" in t]
        assert len(stagnation_events) >= 1

        # Check the detail message mentions PV accuracy
        assert any("PV accuracy" in t for t in stagnation_events)
        assert any("10.0%" in t for t in stagnation_events)
        assert any("10.5%" in t for t in stagnation_events)
