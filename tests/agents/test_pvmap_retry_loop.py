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
    StatePreparationAgent,
    ConditionalFeedbackAgent,
    MaxRetriesCheckAgent,
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
            "UnifiedFeedback",
            "MaxRetriesCheck",
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

    @patch.dict('os.environ', {'PVMAP_GENERATOR_MODEL': 'gemini-1.5-pro'})
    def test_respects_model_environment_override(self):
        """Should use model from environment if set."""
        loop = create_pvmap_retry_loop()
        # Generator should use environment model
        generator = loop.sub_agents[1]  # Generator is second
        from google.adk.models import Gemini
        if isinstance(generator.model, Gemini):
            assert generator.model.model == "gemini-1.5-pro"
        else:
            assert generator.model == "gemini-1.5-pro"

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
