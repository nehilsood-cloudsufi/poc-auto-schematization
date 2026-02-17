"""
Unit tests for the enhanced PVMAP retry loop with quality-based retries.

Tests the LoopAgent architecture, conditional agents, and state management.
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from pathlib import Path
import asyncio

from src.agents.pvmap_retry_loop import (
    create_pvmap_retry_loop,
    GeneratorWrapperAgent,
    StatePreparationAgent,
    ConditionalFeedbackAgent,
    MaxRetriesCheckAgent,
    _compact_skeleton_for_feedback,
    _compact_skeleton_for_generator,
    _compact_vocab_for_feedback,
    _compact_vocab_for_generator,
    _FEEDBACK_RESTORE_KEYS,
)


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_dataset():
    """Create mock DatasetInfo object."""
    dataset = Mock()
    dataset.name = "test_dataset"
    dataset.output_dir = Path("/tmp/test_output")
    dataset.path = Path("/tmp/test_dataset")
    dataset.schema_examples = None
    dataset.sampled_data_files = []
    dataset.metadata_files = []
    dataset.use_metadata = False
    return dataset


@pytest.fixture
def mock_ctx():
    """Create mock InvocationContext."""
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.state = {}
    return ctx


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
# Test create_pvmap_retry_loop
# ============================================================================

class TestCreatePvmapRetryLoop:
    """Tests for the create_pvmap_retry_loop factory function."""

    def test_creates_loop_agent(self):
        """Should create a LoopAgent instance."""
        loop = create_pvmap_retry_loop()
        assert loop.name == "PVMAPRetryLoop"

    def test_default_max_retries_is_3(self):
        """Default should be 3 retries (4 total attempts)."""
        loop = create_pvmap_retry_loop()
        assert loop.max_iterations == 4  # 3 retries + 1 initial

    def test_custom_max_retries(self):
        """Should accept custom max_retries."""
        loop = create_pvmap_retry_loop(max_retries=2)
        assert loop.max_iterations == 3  # 2 retries + 1 initial

    def test_has_seven_sub_agents(self):
        """Should have 7 sub-agents in the loop (with MetadataGenerator)."""
        loop = create_pvmap_retry_loop()
        assert len(loop.sub_agents) == 7

    def test_sub_agent_order(self):
        """Sub-agents should be in correct order."""
        loop = create_pvmap_retry_loop()
        agent_names = [a.name for a in loop.sub_agents]

        expected_order = [
            "StatePrep",
            "Generator",
            "MetadataGenerator",
            "Validator",
            "QualityEvaluator",
            "MaxRetriesCheck",
            "UnifiedFeedback",
        ]

        assert agent_names == expected_order


# ============================================================================
# Test StatePreparationAgent
# ============================================================================

class TestStatePreparationAgent:
    """Tests for StatePreparationAgent."""

    def test_increments_attempt_number(self, mock_ctx, mock_dataset):
        """Should increment attempt_number starting from 0."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": -1,  # Initial value
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        assert mock_ctx.session.state["attempt_number"] == 0

    def test_initializes_tracking_state_on_first_attempt(self, mock_ctx, mock_dataset):
        """Should initialize quality_metrics_history and error_feedback on first attempt."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": -1,
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        assert mock_ctx.session.state["quality_metrics_history"] == []
        assert mock_ctx.session.state["error_feedback"] == ""
        assert mock_ctx.session.state["validation_counter_summary"] == ""

    def test_resets_per_iteration_flags(self, mock_ctx, mock_dataset):
        """Should reset per-iteration flags on each iteration."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 0,
            "quality_metrics_history": [],
            "validation_passed": True,  # From previous iteration
            "quality_acceptable": True,
            "quality_stagnant": True,
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        # Flags should be reset
        assert mock_ctx.session.state["validation_passed"] is False
        assert mock_ctx.session.state["quality_acceptable"] is False
        assert mock_ctx.session.state["quality_stagnant"] is False

    def test_preserves_feedback_on_retries(self, mock_ctx, mock_dataset):
        """Should preserve error_feedback from previous iteration on retries."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 0,  # Will become 1
            "quality_metrics_history": [],
            "error_feedback": "Previous error feedback",
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        # Feedback should be preserved
        assert mock_ctx.session.state["error_feedback"] == "Previous error feedback"

    def test_handles_missing_dataset(self, mock_ctx):
        """Should handle missing current_dataset gracefully."""
        mock_ctx.session.state = {}

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        # Should set error state
        assert "state_prep_error" in mock_ctx.session.state

    def test_ensures_optional_state_defaults(self, mock_ctx, mock_dataset):
        """Should ensure optional state variables have defaults."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": -1,
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        # Optional variables should have defaults
        assert mock_ctx.session.state.get("skeleton_summary") == ""
        assert mock_ctx.session.state.get("statvar_summary") == ""
        assert mock_ctx.session.state.get("structure_warnings") == ""
        assert mock_ctx.session.state.get("quality_diff_summary") == ""
        assert mock_ctx.session.state.get("gt_score_section") == ""

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_discovers_and_caches_gt_on_first_attempt(self, mock_find, mock_ctx, mock_dataset):
        """Should discover and cache GT PVMAP path on attempt 0."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": -1,
        }
        mock_find.return_value = {
            "success": True,
            "pvmaps": [Path("/fake/gt_pvmap.csv")],
            "count": 1,
            "error": None,
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        assert mock_ctx.session.state["gt_pvmap_path_cached"] == "/fake/gt_pvmap.csv"
        mock_find.assert_called_once()

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_gt_cache_none_when_not_found(self, mock_find, mock_ctx, mock_dataset):
        """Should set gt_pvmap_path_cached to None when no GT found."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": -1,
        }
        mock_find.return_value = {
            "success": False,
            "pvmaps": [],
            "count": 0,
            "error": "Not found",
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        assert mock_ctx.session.state["gt_pvmap_path_cached"] is None

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_gt_not_rediscovered_on_retry(self, mock_find, mock_ctx, mock_dataset):
        """Should not re-discover GT on subsequent attempts."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 0,  # Will become 1 (retry)
            "quality_metrics_history": [],
            "error_feedback": "",
            "gt_pvmap_path_cached": "/already/cached.csv",
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        # Should not call find_ground_truth_pvmaps on retry
        mock_find.assert_not_called()
        # Cached value should be preserved
        assert mock_ctx.session.state["gt_pvmap_path_cached"] == "/already/cached.csv"


# ============================================================================
# Test ConditionalFeedbackAgent (unified feedback)
# ============================================================================

class TestConditionalFeedbackAgent:
    """Tests for ConditionalFeedbackAgent (unified feedback)."""

    def test_runs_error_path_when_validation_failed(self, mock_ctx):
        """Should run feedback agent with error mode when validation failed."""
        mock_ctx.session.state = {
            "validation_passed": False,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_error": "Some error",
            "pvmap_csv": "key,prop,value",
            "sampled_data": "col1,col2",
        }

        agent = ConditionalFeedbackAgent()

        # Mock the inner feedback agent with async generator
        async def mock_run_async(ctx):
            if False:  # Empty generator
                yield

        mock_inner = Mock()
        mock_inner.run_async = mock_run_async
        agent.feedback_agent = mock_inner

        events = run_agent(agent, mock_ctx)

        # Should have yielded "error feedback" message
        assert any("error feedback" in str(e.content.parts[0].text).lower() for e in events)
        # Should have set feedback_mode
        assert "VALIDATION FAILED" in mock_ctx.session.state.get("feedback_mode", "")

    def test_runs_quality_path_when_quality_low(self, mock_ctx):
        """Should run feedback agent with quality mode when quality is low."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "quality_metrics": {"heuristic_score": 55.0},
            "pvmap_csv": "key,prop,value",
            "sampled_data": "col1,col2",
        }

        agent = ConditionalFeedbackAgent()

        async def mock_run_async(ctx):
            if False:
                yield

        mock_inner = Mock()
        mock_inner.run_async = mock_run_async
        agent.feedback_agent = mock_inner

        events = run_agent(agent, mock_ctx)

        # Should have yielded "quality" or "improvement" message
        assert any("quality" in str(e.content.parts[0].text).lower() or
                    "improvement" in str(e.content.parts[0].text).lower()
                    for e in events)
        # Should have set feedback_mode
        assert "QUALITY LOW" in mock_ctx.session.state.get("feedback_mode", "")

    def test_skips_when_quality_acceptable(self, mock_ctx):
        """Should skip when quality is acceptable."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": True,
            "quality_stagnant": False,
        }

        agent = ConditionalFeedbackAgent()
        events = run_agent(agent, mock_ctx)

        # Should skip
        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()
        assert "quality acceptable" in events[0].content.parts[0].text.lower()

    def test_skips_when_quality_stagnant(self, mock_ctx):
        """Should skip when quality is stagnant."""
        mock_ctx.session.state = {
            "validation_passed": True,
            "quality_acceptable": False,
            "quality_stagnant": True,
        }

        agent = ConditionalFeedbackAgent()
        events = run_agent(agent, mock_ctx)

        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()
        assert "stagnant" in events[0].content.parts[0].text.lower()

    def test_prepares_counter_summary_default(self, mock_ctx):
        """Should set default counter summary when missing."""
        mock_ctx.session.state = {
            "validation_passed": False,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_error": "err",
            "pvmap_csv": "key,prop,value",
        }

        agent = ConditionalFeedbackAgent()
        agent._prepare_feedback_state(mock_ctx)

        assert mock_ctx.session.state["validation_counter_summary"] == "Processing metrics not available."


# ============================================================================
# Test ConditionalFeedbackAgent state preparation
# ============================================================================

class TestFeedbackStatePreperation:
    """Tests for _prepare_feedback_state on ConditionalFeedbackAgent."""

    def test_prepares_quality_score_from_heuristic(self, mock_ctx):
        """Should extract heuristic_score as quality_score."""
        mock_ctx.session.state = {
            "quality_metrics": {"heuristic_score": 65.0},
        }

        agent = ConditionalFeedbackAgent()
        agent._prepare_feedback_state(mock_ctx)

        assert mock_ctx.session.state["quality_score"] == 65.0

    def test_formats_gt_section(self, mock_ctx):
        """Should format GT section from quality metrics."""
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

        agent = ConditionalFeedbackAgent()
        agent._prepare_feedback_state(mock_ctx)

        gt_section = mock_ctx.session.state["gt_score_section"]
        assert "Node Accuracy: 40.0%" in gt_section
        assert "PV Accuracy: 25.0%" in gt_section

    def test_handles_missing_quality_metrics(self, mock_ctx):
        """Should handle missing quality_metrics gracefully."""
        mock_ctx.session.state = {}

        agent = ConditionalFeedbackAgent()
        agent._prepare_feedback_state(mock_ctx)

        assert mock_ctx.session.state["quality_score"] == 0

    def test_escapes_counter_summary(self, mock_ctx):
        """Should escape PVMAP placeholders in counter summary."""
        mock_ctx.session.state = {
            "quality_metrics": {},
            "validation_counter_summary": "Coverage: {Data} mapped",
        }

        agent = ConditionalFeedbackAgent()
        agent._prepare_feedback_state(mock_ctx)

        # {Data} should be escaped to [DATA]
        assert "{Data}" not in mock_ctx.session.state["validation_counter_summary"]


# ============================================================================
# Test Metrics Formatting on ConditionalFeedbackAgent
# ============================================================================

class TestMetricsFormatting:
    """Tests for _format_metrics helper method on ConditionalFeedbackAgent."""

    def test_formats_heuristic_metrics(self):
        """Should format heuristic metrics correctly."""
        agent = ConditionalFeedbackAgent()
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

        formatted = agent._format_metrics(metrics)

        assert "Heuristic Score: 65.0/100" in formatted
        assert "Row Coverage: 15.0/25" in formatted
        assert "Property Coverage: 20.0/25" in formatted
        assert "Column Coverage: 15.0/25" in formatted
        assert "Format Score: 15.0/25" in formatted

    def test_includes_improvement_when_present(self):
        """Should include improvement from previous when available."""
        agent = ConditionalFeedbackAgent()
        metrics = {
            "heuristic_score": 60.0,
            "heuristic_breakdown": {},
            "improvement_from_previous": 3.5,
        }

        formatted = agent._format_metrics(metrics)

        assert "Improvement from previous: 3.5%" in formatted

    def test_includes_gt_scores(self):
        """Should include GT scores when present."""
        agent = ConditionalFeedbackAgent()
        metrics = {
            "heuristic_score": 55.0,
            "heuristic_breakdown": {},
            "gt_node_accuracy": 42.0,
            "gt_pv_accuracy": 33.5,
        }

        formatted = agent._format_metrics(metrics)
        assert "GT Node Accuracy: 42.0%" in formatted
        assert "GT PV Accuracy: 33.5%" in formatted


# ============================================================================
# Test GT Score Formatting on ConditionalFeedbackAgent
# ============================================================================

class TestGTScoreFormatting:
    """Tests for _format_gt_section on ConditionalFeedbackAgent."""

    def test_format_gt_section_with_scores(self):
        """Should format GT section with scores and counters."""
        agent = ConditionalFeedbackAgent()
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
        result = agent._format_gt_section(metrics)
        assert "Node Accuracy: 75.0%" in result
        assert "PV Accuracy: 60.0%" in result
        assert "Nodes matched: 3/4" in result
        assert "distance from ideal" in result

    def test_format_gt_section_without_gt(self):
        """Should show 'not available' when GT not present."""
        agent = ConditionalFeedbackAgent()
        result = agent._format_gt_section({})
        assert "not available" in result


# ============================================================================
# Test MaxRetriesCheckAgent
# ============================================================================

class TestMaxRetriesCheckAgent:
    """Tests for MaxRetriesCheckAgent."""

    def test_escalates_when_max_reached(self, mock_ctx, mock_dataset):
        """Should escalate when max retries reached."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,  # Max reached (0, 1, 2, 3 = 4 attempts)
            "quality_acceptable": False,
            "quality_stagnant": False,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Should escalate
        assert any(e.actions and e.actions.escalate for e in events)
        assert mock_ctx.session.state["exit_reason"] == "max_retries"
        assert mock_ctx.session.state["generation_success"] is False

    def test_continues_when_retries_available(self, mock_ctx, mock_dataset):
        """Should continue when retries still available."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 1,
            "quality_acceptable": False,
            "quality_stagnant": False,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Should NOT escalate
        final_event = events[-1]
        assert final_event.actions.escalate is False

    def test_skips_when_quality_already_handled_exit(self, mock_ctx, mock_dataset):
        """Should skip if quality already handled exit."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": True,  # Already accepted
            "quality_stagnant": False,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Should skip without escalating
        assert len(events) == 1
        # exit_reason should not be overwritten
        assert mock_ctx.session.state.get("exit_reason") != "max_retries"

    def test_error_message_includes_error_feedback(self, mock_ctx, mock_dataset):
        """Error message should include error_feedback when available."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "error_feedback": "Key 'year' not found",
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        error = mock_ctx.session.state["error"]
        assert "feedback" in error.lower()
        assert "Key 'year' not found" in error

    def test_error_message_includes_quality_score_when_no_feedback(self, mock_ctx, mock_dataset):
        """Error message should include quality score when no feedback available."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "quality_metrics": {"heuristic_score": 55.0},
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        error = mock_ctx.session.state["error"]
        assert "55.0%" in error

    def test_valid_best_restores_over_invalid_current(self, mock_ctx, mock_dataset, tmp_path):
        """Valid best attempt should be restored over invalid current."""
        mock_dataset.output_dir = tmp_path
        mock_dataset.input_data_files = []  # No input file → re-validation skipped
        mock_dataset.metadata_files = []
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": False,
            "validation_data_rows": 0,
            "pvmap_csv": "bad_csv",
            "best_pvmap_csv": "good_csv",
            "best_data_rows": 100,
            "best_validation_passed": True,
            "best_attempt_number": 1,
            "best_heuristic_score": 75.0,
            "best_pv_accuracy": 35.0,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        assert mock_ctx.session.state["pvmap_csv"] == "good_csv"
        assert mock_ctx.session.state["generation_success"] is True
        assert mock_ctx.session.state["exit_reason"] == "best_attempt_restored"

    def test_valid_current_kept_over_invalid_best(self, mock_ctx, mock_dataset):
        """Valid current should be kept when best was invalid."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": True,
            "validation_data_rows": 50,
            "pvmap_csv": "current_csv",
            "best_pvmap_csv": "old_csv",
            "best_data_rows": 0,
            "best_validation_passed": False,
            "best_attempt_number": 0,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Current should be kept (not restored)
        assert mock_ctx.session.state["pvmap_csv"] == "current_csv"
        assert mock_ctx.session.state["generation_success"] is False
        assert mock_ctx.session.state["exit_reason"] == "max_retries"

    def test_both_valid_restores_best_with_higher_pv_accuracy(self, mock_ctx, mock_dataset, tmp_path):
        """Both valid: best with higher PV accuracy should be restored."""
        mock_dataset.output_dir = tmp_path
        mock_dataset.input_data_files = []
        mock_dataset.metadata_files = []
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": True,
            "validation_data_rows": 80,
            "pvmap_csv": "current_csv",
            "quality_metrics": {"gt_pv_accuracy": 25.0, "heuristic_score": 72.0},
            "best_pvmap_csv": "best_csv",
            "best_data_rows": 90,
            "best_validation_passed": True,
            "best_attempt_number": 1,
            "best_pv_accuracy": 40.0,
            "best_heuristic_score": 70.0,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Best has higher PV accuracy (40 > 25) → restore
        assert mock_ctx.session.state["pvmap_csv"] == "best_csv"
        assert mock_ctx.session.state["generation_success"] is True

    def test_both_valid_keeps_current_with_higher_pv_accuracy(self, mock_ctx, mock_dataset):
        """Both valid: current with higher PV accuracy should be kept."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": True,
            "validation_data_rows": 80,
            "pvmap_csv": "current_csv",
            "quality_metrics": {"gt_pv_accuracy": 45.0, "heuristic_score": 72.0},
            "best_pvmap_csv": "best_csv",
            "best_data_rows": 90,
            "best_validation_passed": True,
            "best_attempt_number": 1,
            "best_pv_accuracy": 30.0,
            "best_heuristic_score": 75.0,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Current has higher PV accuracy (45 > 30) → keep current
        assert mock_ctx.session.state["pvmap_csv"] == "current_csv"

    def test_both_invalid_restores_best_with_higher_heuristic(self, mock_ctx, mock_dataset, tmp_path):
        """Both invalid: best with higher heuristic should be restored."""
        mock_dataset.output_dir = tmp_path
        mock_dataset.input_data_files = []
        mock_dataset.metadata_files = []
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": False,
            "validation_data_rows": 10,
            "pvmap_csv": "current_csv",
            "quality_metrics": {"heuristic_score": 40.0},
            "best_pvmap_csv": "best_csv",
            "best_data_rows": 30,
            "best_validation_passed": False,
            "best_attempt_number": 1,
            "best_heuristic_score": 55.0,
            "best_pv_accuracy": None,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Best has higher heuristic (55 > 40) → restore
        assert mock_ctx.session.state["pvmap_csv"] == "best_csv"

    def test_tiebreaker_uses_data_rows(self, mock_ctx, mock_dataset, tmp_path):
        """Equal accuracy should use data_rows as tiebreaker."""
        mock_dataset.output_dir = tmp_path
        mock_dataset.input_data_files = []
        mock_dataset.metadata_files = []
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": False,
            "validation_data_rows": 20,
            "pvmap_csv": "current_csv",
            "quality_metrics": {"heuristic_score": 50.0},
            "best_pvmap_csv": "best_csv",
            "best_data_rows": 50,
            "best_validation_passed": False,
            "best_attempt_number": 0,
            "best_heuristic_score": 50.0,  # Same heuristic
            "best_pv_accuracy": None,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Same heuristic, but best has more rows → restore
        assert mock_ctx.session.state["pvmap_csv"] == "best_csv"

    @patch('src.tools.validation_tool.run_validation')
    def test_revalidation_after_restore(self, mock_run_val, mock_ctx, mock_dataset, tmp_path):
        """Should re-run validation after restoring a validated best attempt."""
        mock_dataset.output_dir = tmp_path
        mock_dataset.input_data_files = [tmp_path / "input.csv"]
        mock_dataset.metadata_files = []
        # Create the input file so Path check passes
        (tmp_path / "input.csv").write_text("col1,col2\na,b")

        mock_run_val.return_value = {
            "success": True,
            "data_rows": 95,
        }

        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": False,
            "validation_data_rows": 0,
            "pvmap_csv": "bad_csv",
            "best_pvmap_csv": "good_csv",
            "best_data_rows": 100,
            "best_validation_passed": True,
            "best_attempt_number": 1,
            "best_heuristic_score": 75.0,
            "best_pv_accuracy": None,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # Should have called run_validation
        mock_run_val.assert_called_once()
        # validation_data_rows updated from re-validation
        assert mock_ctx.session.state["validation_data_rows"] == 95
        assert mock_ctx.session.state["generation_success"] is True

    def test_no_restore_when_same_csv(self, mock_ctx, mock_dataset):
        """Should not restore when best_pvmap_csv == current pvmap_csv."""
        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 3,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": True,
            "validation_data_rows": 50,
            "pvmap_csv": "same_csv",
            "best_pvmap_csv": "same_csv",
            "best_data_rows": 50,
            "best_validation_passed": True,
            "best_attempt_number": 2,
        }

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, mock_ctx)

        # No restore needed (same CSV), but it's still valid
        assert mock_ctx.session.state["pvmap_csv"] == "same_csv"
        # Since we didn't restore and current is valid but quality check failed,
        # it should be max_retries exit
        assert mock_ctx.session.state["exit_reason"] == "max_retries"


# ============================================================================
# Test Full Loop Flow (Integration-style)
# ============================================================================

class TestLoopFlow:
    """Integration-style tests for the full loop flow."""

    def test_max_attempts_is_four(self):
        """Loop should allow max 4 attempts by default."""
        loop = create_pvmap_retry_loop()
        assert loop.max_iterations == 4

    def test_loop_structure_supports_quality_retries(self):
        """Loop should have agents for quality-based retries."""
        loop = create_pvmap_retry_loop()
        agent_names = [a.name for a in loop.sub_agents]

        # Must have quality evaluator
        assert "QualityEvaluator" in agent_names

        # Must have unified feedback
        assert "UnifiedFeedback" in agent_names

    def test_state_outputs_documented(self):
        """Loop docstring should document all state outputs."""
        loop = create_pvmap_retry_loop()
        # The factory function has a docstring
        docstring = create_pvmap_retry_loop.__doc__

        expected_outputs = [
            "generation_success",
            "pvmap_path",
            "pvmap_csv",
            "exit_reason",
            "quality_metrics",
            "quality_metrics_history",
        ]

        for output in expected_outputs:
            assert output in docstring


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_handles_zero_max_retries(self):
        """Should handle max_retries=0 (single attempt only)."""
        loop = create_pvmap_retry_loop(max_retries=0)
        assert loop.max_iterations == 1

    def test_generator_is_wrapper_agent(self):
        """Generator sub-agent should be a GeneratorWrapperAgent."""
        loop = create_pvmap_retry_loop()
        generator = loop.sub_agents[1]  # Generator is second
        assert isinstance(generator, GeneratorWrapperAgent)

    def test_state_prep_with_file_read_errors(self, mock_ctx):
        """Should handle file read errors gracefully."""
        mock_dataset = Mock()
        mock_dataset.name = "test"
        mock_dataset.output_dir = Path("/tmp/test")
        mock_dataset.path = Path("/tmp/test")
        mock_dataset.schema_examples = "/nonexistent/path.txt"
        mock_dataset.sampled_data_files = []
        mock_dataset.metadata_files = []
        mock_dataset.use_metadata = False

        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": -1,
        }

        agent = StatePreparationAgent()
        events = run_agent(agent, mock_ctx)

        # Should complete without crashing
        # Schema examples should have fallback message
        assert "schema_examples" in mock_ctx.session.state


# ============================================================================
# Skeleton Compaction Helpers
# ============================================================================

def _build_skeleton(sections: dict[str, str] = None, n_columns: int = 30) -> str:
    """Build a realistic skeleton_summary for testing.

    Args:
        sections: Override specific sections by number.
        n_columns: Number of columns to generate (makes skeleton large enough
                   to exceed the 5000-char guard in compaction functions).
    """
    # Build column reference rows
    col_rows = []
    col_headers = []
    for i in range(n_columns):
        col_name = f"Column_{i:02d}_LongName"
        col_headers.append(col_name)
        col_rows.append(
            f"| `{col_name}` | object | {50 + i} | "
            f"SampleVal_{i}_A, SampleVal_{i}_B, SampleVal_{i}_C, SampleVal_{i}_D, SampleVal_{i}_E |"
        )

    # Build dimension lines (10 dimensions with 15 values each)
    dim_lines = []
    for i in range(10):
        values = [f"DimVal_{i}_{j}" for j in range(15)]
        values_str = ", ".join(values) + ", ... (15 total)"
        dim_lines.append(f"- **`Dim_{i}`** (15 values): [{values_str}]")
        dim_lines.append(f"  \u26a0 Aggregate values detected: Total — consider dropping")

    defaults = {
        "1": (
            "## 1. TOPOLOGY & STRUCTURE\n\n"
            "- **Dataset:** test_dataset\n"
            "- **Format:** flat\n"
            f"- **Rows:** 1000  |  **Columns:** {n_columns}\n\n"
            f"**ALL column headers (exact, case-sensitive):** `{'`, `'.join(col_headers)}`\n"
        ),
        "1.5": (
            "## 1.5 COLUMN REFERENCE TABLE (USE EXACT NAMES AS PVMAP KEYS)\n\n"
            "| Column Header (EXACT) | Type | Unique Values | Sample Values |\n"
            "|------------------------|------|---------------|---------------|\n"
            + "\n".join(col_rows) + "\n"
        ),
        "2": (
            "## 2. COLUMN CLASSIFICATIONS\n\n"
            "| Column | Role |\n"
            "|--------|------|\n"
            "| `Year` | time |\n"
            "| `State` | place |\n"
            "| `Population` | value |\n"
            "| `Age` | dimension |\n"
        ),
        "3": (
            "## 3. ANCHOR ANALYSIS\n\n"
            "**Geography:** Column `State` — Format: US_STATE_NAME\n"
            "  Sample values: California, Texas, New York\n\n"
            "**Time:** Column `Year` — Format: YYYY\n"
            "  Sample values: 2010, 2011, 2012\n"
        ),
        "4": (
            "## 4. DIMENSION DEEP DIVE\n\n"
            + "\n".join(dim_lines) + "\n"
        ),
        "5": (
            "## 5. MEASUREMENT & UNITS\n\n"
            "- Value Column: `Population` (StatType: measuredValue)\n"
            "- **Population Type:** Person\n"
            "- **Measurement Type:** measuredValue\n"
        ),
        "6": (
            "## 6. STATVAR PATTERN (P+M+C Formula)\n\n"
            "`Count_Person_ByAge`\n"
        ),
        "7": (
            "## 7. ONE-SHOT PVMAP EXAMPLE\n\n"
            "```csv\n"
            "key,property,value\n"
            "Year,observationDate,[DATA]\n"
            "State,observationAbout,[DATA]\n"
            "Population,value,[NUMBER]\n"
            "0-4,age,Years0To4\n"
            "5-14,age,Years5To14\n"
            "15-24,age,Years15To24\n"
            "```\n"
        ),
        "8": (
            "## 8. PRE-FORMATTED DATA COMMONS DETECTION\n\n"
            "Not pre-formatted. Generate PVMAP from scratch.\n"
        ),
        "9": (
            "## 9. COVERAGE\n\n"
            "- Total Dimension Combinations: 200\n"
            "- Sample Covers: 50 (25.0%)\n\n"
            "**IMPORTANT:** Generate PVMAP for ALL dimension combinations.\n"
        ),
    }
    if sections:
        defaults.update(sections)

    parts = []
    for sec_id in ["1", "1.5", "2", "3", "4", "5", "6", "7", "8", "9"]:
        if sec_id in defaults:
            parts.append(defaults[sec_id])
    return "\n".join(parts)


def _build_vocab(
    n_skeletons: int = 2,
    n_enum_props: int = 3,
    n_enum_values: int = 20,
    n_examples: int = 3,
) -> str:
    """Build realistic schema_vocab_content for testing."""
    lines = ["### Schema Vocabulary: Health", ""]
    lines.append("**StatVar Skeletons (which properties go with which populationType):**")
    for i in range(n_skeletons):
        lines.append(f"- Person{i}: gender, age, race")
    lines.append("")

    lines.append("**VALID ENUM VALUES (use these EXACT identifiers for dimension properties):**")
    for i in range(n_enum_props):
        values = [f"Value{j}" for j in range(n_enum_values)]
        lines.append(f"- prop{i}: {', '.join(values)}")
    lines.append("")
    lines.append("When mapping dimension values, use ONLY identifiers from this list.")
    lines.append("")

    if n_examples > 0:
        lines.append("**Representative examples (diverse patterns):**")
        for i in range(n_examples):
            lines.append(f'{i + 1}. "Example {i}" \u2192 mapping{i}')
        lines.append("")

    lines.append("Schema.org base: Thing \u2192 Intangible \u2192 StructuredValue")
    lines.append("DC extensions: measuredProperty, statType")
    return "\n".join(lines)


# ============================================================================
# Test Compaction Functions
# ============================================================================

class TestCompactSkeletonForFeedback:
    """Tests for _compact_skeleton_for_feedback."""

    def test_drops_sections_6_7_9(self):
        """Should drop sections 6 (StatVar), 7 (one-shot), 9 (coverage)."""
        skeleton = _build_skeleton()
        compacted = _compact_skeleton_for_feedback(skeleton)

        assert "## 6. STATVAR PATTERN" not in compacted
        assert "## 7. ONE-SHOT PVMAP EXAMPLE" not in compacted
        assert "## 9. COVERAGE" not in compacted

        # Should keep sections 1, 2, 3, 5, 8
        assert "## 1. TOPOLOGY" in compacted
        assert "## 2. COLUMN CLASSIFICATIONS" in compacted
        assert "## 3. ANCHOR ANALYSIS" in compacted
        assert "## 5. MEASUREMENT" in compacted
        assert "## 8. PRE-FORMATTED" in compacted

    def test_trims_column_samples_to_2(self):
        """Should reduce column sample values from 5 to 2 in Section 1.5."""
        skeleton = _build_skeleton()
        compacted = _compact_skeleton_for_feedback(skeleton)

        # Section 1.5 should still exist
        assert "## 1.5 COLUMN REFERENCE TABLE" in compacted

        # Each row had 5 sample values (SampleVal_N_A through _E), should now have 2 + "..."
        assert "SampleVal_0_A, SampleVal_0_B, ..." in compacted
        # Should NOT have all 5 values
        assert "SampleVal_0_D" not in compacted

    def test_trims_dimension_values_to_5(self):
        """Should reduce dimension value lists to 5 in Section 4."""
        skeleton = _build_skeleton()
        compacted = _compact_skeleton_for_feedback(skeleton)

        # Section 4 should still exist
        assert "## 4. DIMENSION DEEP DIVE" in compacted

        # Should have reduced values — original had 15 per dimension
        for line in compacted.split('\n'):
            if '**`Dim_0`**' in line:
                values_part = line[line.find('[') + 1:line.rfind(']')]
                values = [v.strip() for v in values_part.split(',') if not v.strip().startswith('...')]
                assert len(values) <= 5
                break

    def test_drops_aggregate_warnings(self):
        """Should drop aggregate value warning lines."""
        skeleton = _build_skeleton()
        compacted = _compact_skeleton_for_feedback(skeleton)
        assert "\u26a0 Aggregate values detected" not in compacted

    def test_passthrough_when_small(self):
        """Should return unchanged when skeleton is small."""
        small_skeleton = "## 1. TOPOLOGY\n\nSmall dataset."
        result = _compact_skeleton_for_feedback(small_skeleton)
        assert result == small_skeleton

    def test_passthrough_when_empty(self):
        """Should handle empty input."""
        assert _compact_skeleton_for_feedback("") == ""
        assert _compact_skeleton_for_feedback(None) is None


class TestCompactSkeletonForGenerator:
    """Tests for _compact_skeleton_for_generator."""

    def test_keeps_all_sections(self):
        """Should keep all sections including 6, 7, 9 (unlike feedback)."""
        skeleton = _build_skeleton()
        # Budget just under skeleton length to trigger compaction but not truncation
        compacted = _compact_skeleton_for_generator(skeleton, budget=len(skeleton) - 100)

        # Should keep sections that feedback drops
        assert "## 6. STATVAR PATTERN" in compacted
        assert "## 7. ONE-SHOT PVMAP EXAMPLE" in compacted
        assert "## 9. COVERAGE" in compacted
        # Should also keep core sections
        assert "## 1. TOPOLOGY" in compacted

    def test_trims_samples_to_3(self):
        """Should reduce column samples to 3 (less aggressive than feedback)."""
        skeleton = _build_skeleton()
        # Budget under length to trigger compaction
        compacted = _compact_skeleton_for_generator(skeleton, budget=len(skeleton) - 100)

        # Should have 3 sample values + "..."
        assert "SampleVal_0_A, SampleVal_0_B, SampleVal_0_C, ..." in compacted

    def test_passthrough_when_under_budget(self):
        """Should return unchanged when under budget."""
        skeleton = _build_skeleton()
        result = _compact_skeleton_for_generator(skeleton, budget=999999)
        assert result == skeleton


class TestCompactVocabForFeedback:
    """Tests for _compact_vocab_for_feedback."""

    def test_trims_enum_values_to_3(self):
        """Should reduce enum values to first 3 + count."""
        # Build vocab large enough to exceed the 3000-char guard
        vocab = _build_vocab(n_enum_props=15, n_enum_values=20, n_examples=5)
        assert len(vocab) > 3000, f"Test vocab too small: {len(vocab)} chars"
        compacted = _compact_vocab_for_feedback(vocab)

        for line in compacted.split('\n'):
            if line.startswith('- prop') and ':' in line:
                # Should have 3 values + "(N total)"
                colon_idx = line.index(':')
                values_part = line[colon_idx + 1:].strip()
                values = [v.strip() for v in values_part.split(',')]
                # 3 values + "... (20 total)"
                non_ellipsis = [v for v in values if not v.startswith('...')]
                assert len(non_ellipsis) <= 3
                assert "(20 total)" in values_part
                break

    def test_drops_examples_section(self):
        """Should drop representative examples section."""
        vocab = _build_vocab(n_enum_props=15, n_enum_values=20, n_examples=5)
        assert len(vocab) > 3000
        compacted = _compact_vocab_for_feedback(vocab)

        assert "**Representative examples" not in compacted
        assert "Example 0" not in compacted

    def test_keeps_skeletons(self):
        """Should keep StatVar skeletons."""
        vocab = _build_vocab(n_enum_props=15, n_enum_values=20)
        assert len(vocab) > 3000
        compacted = _compact_vocab_for_feedback(vocab)

        assert "**StatVar Skeletons" in compacted
        assert "Person0:" in compacted

    def test_keeps_schema_org(self):
        """Should keep schema.org context."""
        vocab = _build_vocab(n_enum_props=15, n_enum_values=20)
        assert len(vocab) > 3000
        compacted = _compact_vocab_for_feedback(vocab)

        assert "Schema.org base:" in compacted

    def test_passthrough_when_small(self):
        """Should return unchanged for small vocab."""
        small = "### Schema Vocab\n- Person: age"
        assert _compact_vocab_for_feedback(small) == small


class TestCompactVocabForGenerator:
    """Tests for _compact_vocab_for_generator."""

    def test_trims_enums_to_10(self):
        """Should reduce enum values to 10 (less aggressive than feedback)."""
        vocab = _build_vocab(n_enum_values=25)
        # Budget just under length to trigger compaction
        compacted = _compact_vocab_for_generator(vocab, budget=len(vocab) - 50)

        for line in compacted.split('\n'):
            if line.startswith('- prop') and ':' in line:
                colon_idx = line.index(':')
                values_part = line[colon_idx + 1:].strip()
                values = [v.strip() for v in values_part.split(',')]
                non_ellipsis = [v for v in values if not v.startswith('...')]
                assert len(non_ellipsis) <= 10
                break

    def test_keeps_examples(self):
        """Should keep representative examples (unlike feedback compaction)."""
        vocab = _build_vocab(n_examples=3)
        # Budget just under length to trigger compaction
        compacted = _compact_vocab_for_generator(vocab, budget=len(vocab) - 50)

        assert "**Representative examples" in compacted

    def test_passthrough_when_under_budget(self):
        """Should return unchanged when under budget."""
        vocab = _build_vocab(n_enum_values=5)
        result = _compact_vocab_for_generator(vocab, budget=999999)
        assert result == vocab


# ============================================================================
# Test Integration: Prompt Budget Preserves Error Feedback
# ============================================================================

class TestPromptBudgetIntegration:
    """Tests that budget-based allocation preserves error_feedback."""

    def test_populate_prompt_preserves_error_feedback(self, mock_ctx, mock_dataset, tmp_path):
        """Error feedback should NOT be truncated even with large skeleton + schema."""
        # Create a prompt template file
        template_path = tmp_path / "src" / "resources" / "prompts"
        template_path.mkdir(parents=True)
        template_file = template_path / "improved_pvmap_prompt_v2.txt"
        template_file.write_text(
            "TEMPLATE START\n"
            "{{DATA_CONTEXT}}\n"
            "{{SCHEMA_EXAMPLES}}\n"
            "{{SAMPLED_DATA}}\n"
            "{{METADATA_CONFIG}}\n"
            "{{ERROR_FEEDBACK}}\n"
            "{{STATVAR_SUMMARY}}\n"
            "{{MCP_TOOLS_INSTRUCTION}}\n"
            "TEMPLATE END\n"
        )

        # Set large skeleton and schema in state
        large_skeleton = "x" * 80000  # 80K chars
        large_schema = "y" * 40000   # 40K chars
        error_feedback = "FIX THIS: key 'Year' not found in headers"

        mock_ctx.session.state = {
            "current_dataset": mock_dataset,
            "attempt_number": 0,
            "skeleton_summary": large_skeleton,
            "schema_examples": large_schema,
            "sampled_data": "col1,col2\na,b",
            "metadata": "",
            "error_feedback": error_feedback,
            "statvar_summary": "",
            "mcp_tools_instruction": "",
            "prompt_version": "v2",
        }

        agent = StatePreparationAgent()

        # Monkey-patch PROJECT_ROOT to use our temp dir
        import src.agents.pvmap_retry_loop as module
        original_root = module.PROJECT_ROOT
        module.PROJECT_ROOT = tmp_path
        try:
            agent._populate_prompt_template(mock_ctx)
        finally:
            module.PROJECT_ROOT = original_root

        populated = mock_ctx.session.state.get("populated_pvmap_prompt", "")
        # Error feedback should be fully preserved in the populated prompt
        assert error_feedback in populated

    def test_originals_restored_after_feedback(self, mock_ctx):
        """Original state should be restored after feedback compaction."""
        original_skeleton = "A" * 10000
        original_vocab = "B" * 5000
        original_sampled = "col1,col2\nval1,val2"

        mock_ctx.session.state = {
            "validation_passed": False,
            "quality_acceptable": False,
            "quality_stagnant": False,
            "skeleton_summary": original_skeleton,
            "schema_vocab_content": original_vocab,
            "sampled_data": original_sampled,
            "validation_error": "some error",
            "pvmap_csv": "key,prop,value",
        }

        agent = ConditionalFeedbackAgent()

        # Mock the inner feedback agent
        async def mock_run_async(ctx):
            # Verify compaction happened during feedback
            assert len(ctx.session.state.get("skeleton_summary", "")) < len(original_skeleton)
            if False:
                yield

        mock_inner = Mock()
        mock_inner.run_async = mock_run_async
        agent.feedback_agent = mock_inner

        events = run_agent(agent, mock_ctx)

        # After feedback completes, originals should be restored
        assert mock_ctx.session.state["skeleton_summary"] == original_skeleton
        assert mock_ctx.session.state["schema_vocab_content"] == original_vocab
        assert mock_ctx.session.state["sampled_data"] == original_sampled

    def test_progressive_fallback_when_over_budget(self, mock_ctx):
        """Total instruction size guard should truncate largest variables."""
        mock_ctx.session.state = {
            "validation_passed": False,
            "quality_acceptable": False,
            "quality_stagnant": False,
            # Make total > 50K so guard triggers
            "skeleton_summary": "S" * 20000,
            "schema_vocab_content": "V" * 20000,
            "sampled_data": "D" * 15000,
            "validation_error": "E" * 5000,
            "pvmap_csv": "key,prop,value",
        }

        agent = ConditionalFeedbackAgent()
        agent._prepare_feedback_state(mock_ctx)

        # Total should be reduced below 50K
        keys = [
            "skeleton_summary", "schema_vocab_content", "pvmap_csv",
            "validation_error", "sampled_data", "key_match_report",
            "validation_statvar_analysis", "quality_diff_summary",
            "mcp_resolved_context", "validation_counter_summary",
        ]
        total = sum(len(mock_ctx.session.state.get(k, "")) for k in keys)
        assert total <= 50000
