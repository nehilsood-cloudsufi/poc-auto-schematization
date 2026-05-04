"""Tests for TieredCorrectionAgent and related retry loop changes."""

import asyncio
import pytest
from unittest.mock import MagicMock, AsyncMock, patch

from google.adk.agents import SequentialAgent

from src.agents.pvmap_retry_loop import (
    TieredCorrectionAgent,
    create_pvmap_retry_loop,
)
from src.agents.quality_evaluation_agent import QualityEvaluationAgent


# ============================================================================
# Helpers
# ============================================================================

def _make_ctx(state: dict):
    """Build a minimal mock InvocationContext with given state."""
    ctx = MagicMock()
    ctx.session.state = dict(state)
    ctx.session.events = []
    return ctx


async def _collect_events(agent, ctx):
    """Collect all events from an async generator agent run."""
    events = []
    async for event in agent._run_async_impl(ctx):
        events.append(event)
    return events


# ============================================================================
# Part A: QualityEvaluationAgent escalate_on_quality tests
# ============================================================================

class TestQualityEvalEscalateOnQuality:
    """Test the new escalate_on_quality parameter."""

    def test_default_escalate_on_quality_true(self):
        """Default value should be True for backward compat."""
        agent = QualityEvaluationAgent(name="TestQE")
        assert agent._escalate_on_quality is True

    def test_escalate_on_quality_false_sets_flag(self):
        """Passing escalate_on_quality=False should set the private attr."""
        agent = QualityEvaluationAgent(name="TestQE", escalate_on_quality=False)
        assert agent._escalate_on_quality is False

    @pytest.mark.asyncio
    async def test_quality_acceptable_no_escalate(self):
        """When escalate_on_quality=False, quality_acceptable should NOT escalate."""
        agent = QualityEvaluationAgent(name="TestQE", escalate_on_quality=False)
        ctx = _make_ctx({
            "validation_passed": True,
            "current_dataset": MagicMock(output_dir="/tmp/test"),
            "pvmap_csv": "key,p,v\ncol1,observationAbout,dcid:geoId/[DATA]",
            "attempt_number": 0,
            "quality_metrics_history": [],
            "sampled_data": "col1,col2\na,1",
            "metadata": "",
        })

        # Mock heuristic scoring to return high score
        # NOTE: column_coverage must be >= 80.0 for non-GT path acceptance
        with patch("src.agents.quality_evaluation_agent.calculate_heuristic_score") as mock_score:
            mock_score.return_value = {
                "total": 85.0,
                "row_coverage": 20.0,
                "prop_coverage": 20.0,
                "column_coverage": 85.0,
                "format_score": 20.0,
                "issues": "",
            }
            events = await _collect_events(agent, ctx)

        # State should be set
        assert ctx.session.state["quality_acceptable"] is True
        assert ctx.session.state["exit_reason"] == "quality_met"

        # Find the escalation event
        escalate_events = [e for e in events if hasattr(e, 'actions') and e.actions]
        assert any(e.actions.escalate is False for e in escalate_events), \
            "Should NOT escalate when escalate_on_quality=False"


# ============================================================================
# Part B: TieredCorrectionAgent tests
# ============================================================================

class TestTieredCorrectionAgent:
    """Test TieredCorrectionAgent gate checks and instantiation."""

    def test_tiered_agent_creation(self):
        """Verify TieredCorrectionAgent can be instantiated with required attrs."""
        agent = TieredCorrectionAgent(
            name="TestTiered",
            patch_agent=MagicMock(),
            generator_wrapper=MagicMock(),
            metadata_agent=MagicMock(),
            validation_agent=MagicMock(),
            model="gemini-2.5-flash",
        )
        assert agent.name == "TestTiered"
        assert agent._patch_agent is not None
        assert agent._generator_wrapper is not None
        assert agent._model == "gemini-2.5-flash"

    @pytest.mark.asyncio
    async def test_skips_when_quality_acceptable(self):
        """When quality_acceptable=True, agent should return immediately."""
        agent = TieredCorrectionAgent(name="TestTiered")
        ctx = _make_ctx({
            "quality_acceptable": True,
            "quality_stagnant": False,
            "validation_passed": True,
        })

        events = await _collect_events(agent, ctx)
        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()

    @pytest.mark.asyncio
    async def test_skips_when_quality_stagnant(self):
        """When quality_stagnant=True, agent should return immediately."""
        agent = TieredCorrectionAgent(name="TestTiered")
        ctx = _make_ctx({
            "quality_acceptable": False,
            "quality_stagnant": True,
            "validation_passed": True,
        })

        events = await _collect_events(agent, ctx)
        assert len(events) == 1
        assert "stagnant" in events[0].content.parts[0].text.lower()

    @pytest.mark.asyncio
    async def test_skips_when_validation_passed_no_quality_issues(self):
        """When validation passes and no quality diff, agent should skip."""
        agent = TieredCorrectionAgent(name="TestTiered")
        ctx = _make_ctx({
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": True,
            "quality_diff_summary": "",
        })

        events = await _collect_events(agent, ctx)
        assert len(events) == 1
        assert "skipping" in events[0].content.parts[0].text.lower()

    @pytest.mark.asyncio
    async def test_no_current_dataset_returns_error(self):
        """When current_dataset is missing, agent should return error."""
        agent = TieredCorrectionAgent(name="TestTiered")
        ctx = _make_ctx({
            "quality_acceptable": False,
            "quality_stagnant": False,
            "validation_passed": False,
        })

        events = await _collect_events(agent, ctx)
        assert any("error" in e.content.parts[0].text.lower() for e in events)

    def test_is_better_attempt_valid_beats_invalid(self):
        """Valid result should always beat invalid best."""
        agent = TieredCorrectionAgent(name="TestTiered")
        assert agent._is_better_attempt(
            {"success": True, "data_rows": 5}, best_rows=100, best_valid=False
        ) is True

    def test_is_better_attempt_more_rows_wins(self):
        """When both valid, more rows should win."""
        agent = TieredCorrectionAgent(name="TestTiered")
        assert agent._is_better_attempt(
            {"success": True, "data_rows": 100}, best_rows=50, best_valid=True
        ) is True
        assert agent._is_better_attempt(
            {"success": True, "data_rows": 30}, best_rows=50, best_valid=True
        ) is False

    def test_is_better_attempt_invalid_loses_to_valid(self):
        """Invalid result should never beat valid best."""
        agent = TieredCorrectionAgent(name="TestTiered")
        assert agent._is_better_attempt(
            {"success": False, "data_rows": 1000}, best_rows=10, best_valid=True
        ) is False


# ============================================================================
# Part C: create_pvmap_retry_loop returns SequentialAgent
# ============================================================================

class TestCreatePvmapRetryLoop:
    """Test the rewritten create_pvmap_retry_loop function."""

    def test_returns_sequential_agent(self):
        """Function should return a SequentialAgent (not LoopAgent)."""
        agent = create_pvmap_retry_loop()
        assert isinstance(agent, SequentialAgent)

    def test_default_name(self):
        """Default name should be PVMAPRetryLoop."""
        agent = create_pvmap_retry_loop()
        assert agent.name == "PVMAPRetryLoop"

    def test_sub_agents_include_tiered_correction(self):
        """Sub-agents should include TieredCorrectionAgent."""
        agent = create_pvmap_retry_loop()
        agent_names = [a.name for a in agent.sub_agents]
        assert "TieredCorrection" in agent_names

    def test_sub_agents_include_quality_evaluator(self):
        """Sub-agents should include QualityEvaluator with escalate_on_quality=False."""
        agent = create_pvmap_retry_loop()
        qe_agents = [a for a in agent.sub_agents if a.name == "QualityEvaluator"]
        assert len(qe_agents) == 1
        assert qe_agents[0]._escalate_on_quality is False

    def test_no_loop_agent_or_max_retries_check(self):
        """Should NOT contain LoopAgent or MaxRetriesCheckAgent in sub_agents."""
        agent = create_pvmap_retry_loop()
        agent_names = [a.name for a in agent.sub_agents]
        assert "MaxRetriesCheck" not in agent_names

    def test_deprecated_max_retries_warns(self):
        """Non-default max_retries should log a warning."""
        import logging
        with patch.object(logging.getLogger("src.agents.pvmap_retry_loop"), "warning") as mock_warn:
            create_pvmap_retry_loop(max_retries=5)
            mock_warn.assert_called_once()
            assert "deprecated" in mock_warn.call_args[0][0].lower()

    def test_sub_agent_order(self):
        """Verify the expected sub-agent ordering (no MCP)."""
        agent = create_pvmap_retry_loop()
        names = [a.name for a in agent.sub_agents]
        expected = [
            "StatePrep",
            "Generator",
            "MetadataGenerator",
            "Validator",
            "QualityEvaluator",
            "TieredCorrection",
        ]
        assert names == expected
