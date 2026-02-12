"""
Unit tests for raw input fallback and emergency skeleton generation
in StatePreparationAgent.

These tests cover the new fallback logic added to ensure the LLM always
gets some data context, even when sampling fails or is skipped.
"""

import pytest
import asyncio
import tempfile
from unittest.mock import Mock, patch
from pathlib import Path

from src.agents.pvmap_retry_loop import StatePreparationAgent, MaxRetriesCheckAgent


# ============================================================================
# Helpers
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


def make_mock_dataset(**overrides):
    """Create a mock DatasetInfo with sensible defaults."""
    dataset = Mock()
    dataset.name = overrides.get("name", "test_dataset")
    dataset.output_dir = overrides.get("output_dir", Path("/tmp/nonexistent_output"))
    dataset.path = overrides.get("path", Path("/tmp/test_dataset"))
    dataset.schema_examples = overrides.get("schema_examples", None)
    dataset.sampled_data_files = overrides.get("sampled_data_files", [])
    dataset.metadata_files = overrides.get("metadata_files", [])
    dataset.use_metadata = overrides.get("use_metadata", False)
    dataset.input_data_files = overrides.get("input_data_files", [])
    return dataset


def make_ctx(dataset, **state_overrides):
    """Create a mock InvocationContext with given dataset and state."""
    ctx = Mock()
    ctx.session = Mock()
    ctx.session.state = {
        "current_dataset": dataset,
        "attempt_number": -1,
        **state_overrides,
    }
    return ctx


# ============================================================================
# Test raw input fallback
# ============================================================================

class TestRawInputFallback:
    """Tests for Level 4 raw input file fallback in sampled_data resolution."""

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_raw_input_fallback_when_no_sampled_data(self, mock_find, tmp_path):
        """When no sampled files exist, should fall back to raw input file."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        # Create a raw input CSV
        raw_csv = tmp_path / "input_data.csv"
        raw_csv.write_text("col_a,col_b,col_c\n1,foo,bar\n2,baz,qux\n")

        dataset = make_mock_dataset(
            input_data_files=[str(raw_csv)],
            sampled_data_files=[],
            output_dir=str(tmp_path / "output"),
        )
        ctx = make_ctx(dataset)

        agent = StatePreparationAgent()
        run_agent(agent, ctx)

        sampled = ctx.session.state["sampled_data"]
        assert "col_a" in sampled
        assert "foo" in sampled
        assert ctx.session.state.get("using_raw_input_fallback") is True

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_raw_input_truncated_to_100_rows(self, mock_find, tmp_path):
        """Raw input should be truncated to first 100 data rows."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        # Create a 500-row CSV
        lines = ["col_a,col_b"]
        for i in range(500):
            lines.append(f"{i},val_{i}")
        raw_csv = tmp_path / "big_input.csv"
        raw_csv.write_text("\n".join(lines))

        dataset = make_mock_dataset(
            input_data_files=[str(raw_csv)],
            sampled_data_files=[],
            output_dir=str(tmp_path / "output"),
        )
        ctx = make_ctx(dataset)

        agent = StatePreparationAgent()
        run_agent(agent, ctx)

        sampled = ctx.session.state["sampled_data"]
        sampled_lines = sampled.strip().split('\n')
        # Header + 100 data rows = 101 lines
        assert len(sampled_lines) == 101
        # First data row present
        assert "0,val_0" in sampled
        # Row 99 present (last included)
        assert "99,val_99" in sampled
        # Row 100 NOT present (truncated)
        assert "100,val_100" not in sampled

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_no_fallback_when_sampled_exists(self, mock_find, tmp_path):
        """When sampled data exists, raw input should NOT be used."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        # Create both sampled and raw files
        sampled_csv = tmp_path / "agentic_sampled.csv"
        sampled_csv.write_text("sampled_col\nsampled_val\n")

        raw_csv = tmp_path / "input_data.csv"
        raw_csv.write_text("raw_col\nraw_val\n")

        dataset = make_mock_dataset(
            input_data_files=[str(raw_csv)],
            sampled_data_files=[str(sampled_csv)],
            output_dir=str(tmp_path / "output"),
        )
        ctx = make_ctx(dataset)

        agent = StatePreparationAgent()
        run_agent(agent, ctx)

        sampled = ctx.session.state["sampled_data"]
        assert "sampled_col" in sampled
        assert "raw_col" not in sampled
        assert ctx.session.state.get("using_raw_input_fallback") is not True


# ============================================================================
# Test emergency skeleton generation
# ============================================================================

class TestEmergencySkeletonGeneration:
    """Tests for emergency skeleton_summary generation from sampled_data."""

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_emergency_skeleton_generated(self, mock_find, tmp_path):
        """When skeleton_summary is empty but sampled_data exists, should generate emergency skeleton."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        raw_csv = tmp_path / "input_data.csv"
        raw_csv.write_text("Year,State,Population\n2020,CA,39538223\n2021,TX,29145505\n")

        dataset = make_mock_dataset(
            input_data_files=[str(raw_csv)],
            sampled_data_files=[],
            output_dir=str(tmp_path / "output"),
        )
        ctx = make_ctx(dataset)

        agent = StatePreparationAgent()
        run_agent(agent, ctx)

        skeleton = ctx.session.state.get("skeleton_summary", "")
        # Emergency skeleton should contain column information
        assert skeleton != ""
        assert "Year" in skeleton
        assert "State" in skeleton
        assert "Population" in skeleton

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_emergency_skeleton_has_column_reference(self, mock_find, tmp_path):
        """Generated emergency skeleton should contain column headers from the data."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        raw_csv = tmp_path / "input_data.csv"
        raw_csv.write_text(
            "GeoAreaName,TimePeriod,Value,Units\n"
            "United States,2020,1234.5,Dollars\n"
            "Canada,2021,5678.9,Dollars\n"
        )

        dataset = make_mock_dataset(
            name="test_economy",
            input_data_files=[str(raw_csv)],
            sampled_data_files=[],
            output_dir=str(tmp_path / "output"),
        )
        ctx = make_ctx(dataset)

        agent = StatePreparationAgent()
        run_agent(agent, ctx)

        skeleton = ctx.session.state.get("skeleton_summary", "")
        # Should contain all column names
        for col in ["GeoAreaName", "TimePeriod", "Value", "Units"]:
            assert col in skeleton, f"Column '{col}' not found in emergency skeleton"

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_skeleton_not_regenerated_when_already_set(self, mock_find, tmp_path):
        """When skeleton_summary is already set, should NOT regenerate it."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        raw_csv = tmp_path / "input_data.csv"
        raw_csv.write_text("col_a,col_b\n1,2\n")

        dataset = make_mock_dataset(
            input_data_files=[str(raw_csv)],
            sampled_data_files=[],
            output_dir=str(tmp_path / "output"),
        )
        existing_skeleton = "## Existing Skeleton\nAlready computed."
        ctx = make_ctx(dataset, skeleton_summary=existing_skeleton)

        agent = StatePreparationAgent()
        run_agent(agent, ctx)

        # Should preserve existing skeleton
        assert ctx.session.state["skeleton_summary"] == existing_skeleton


# ============================================================================
# Test warning when both are empty
# ============================================================================

class TestEmptyDataWarning:
    """Tests for warning event when both sampled_data and skeleton_summary are empty."""

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_warning_when_both_empty(self, mock_find):
        """Should emit warning event when both sampled_data and skeleton_summary are empty."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        dataset = make_mock_dataset(
            input_data_files=[],  # No raw input either
            sampled_data_files=[],
            output_dir="/tmp/nonexistent",
        )
        ctx = make_ctx(dataset)

        agent = StatePreparationAgent()
        events = run_agent(agent, ctx)

        # Should have a warning event
        warning_events = [
            e for e in events
            if "WARNING" in (e.content.parts[0].text if e.content and e.content.parts else "")
        ]
        assert len(warning_events) >= 1
        assert "No sampled data" in warning_events[0].content.parts[0].text

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_no_warning_when_data_available(self, mock_find, tmp_path):
        """Should NOT emit warning when sampled_data is available."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        raw_csv = tmp_path / "input_data.csv"
        raw_csv.write_text("col_a,col_b\n1,2\n")

        dataset = make_mock_dataset(
            input_data_files=[str(raw_csv)],
            sampled_data_files=[],
            output_dir=str(tmp_path / "output"),
        )
        ctx = make_ctx(dataset)

        agent = StatePreparationAgent()
        events = run_agent(agent, ctx)

        # Should NOT have a warning event
        warning_events = [
            e for e in events
            if "WARNING" in (e.content.parts[0].text if e.content and e.content.parts else "")
        ]
        assert len(warning_events) == 0


# ============================================================================
# Test best-attempt tracking initialization
# ============================================================================

class TestBestAttemptTracking:
    """Tests for best-attempt state initialization and restoration."""

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_best_attempt_initialized_on_attempt_zero(self, mock_find, tmp_path):
        """StatePrep initializes best_data_rows, best_pvmap_csv, best_attempt_number on attempt 0."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        raw_csv = tmp_path / "input_data.csv"
        raw_csv.write_text("col_a,col_b\n1,2\n")

        dataset = make_mock_dataset(
            input_data_files=[str(raw_csv)],
            sampled_data_files=[],
            output_dir=str(tmp_path / "output"),
        )
        ctx = make_ctx(dataset)

        agent = StatePreparationAgent()
        run_agent(agent, ctx)

        assert ctx.session.state["best_data_rows"] == 0
        assert ctx.session.state["best_pvmap_csv"] is None
        assert ctx.session.state["best_attempt_number"] is None
        assert ctx.session.state["best_validation_passed"] is False

    @patch('src.agents.pvmap_retry_loop.find_ground_truth_pvmaps')
    def test_best_attempt_not_reinitialized_on_retry(self, mock_find, tmp_path):
        """StatePrep does NOT reinitialize best-attempt state on retry attempts."""
        mock_find.return_value = {"success": False, "pvmaps": [], "count": 0, "error": None}

        raw_csv = tmp_path / "input_data.csv"
        raw_csv.write_text("col_a,col_b\n1,2\n")

        dataset = make_mock_dataset(
            input_data_files=[str(raw_csv)],
            sampled_data_files=[],
            output_dir=str(tmp_path / "output"),
        )
        # Simulate state after attempt 0 completed (attempt_number=0 means next will be 1)
        ctx = make_ctx(
            dataset,
            attempt_number=0,
            best_data_rows=500,
            best_pvmap_csv="key,p,v\nYear,observationDate,{Data}\n",
            best_attempt_number=0,
            sampled_data="col_a,col_b\n1,2\n",
            skeleton_summary="## Columns\ncol_a, col_b",
            error_feedback="Fix the mapping",
        )

        agent = StatePreparationAgent()
        run_agent(agent, ctx)

        # Best-attempt state should be preserved from previous attempt
        assert ctx.session.state["best_data_rows"] == 500
        assert ctx.session.state["best_pvmap_csv"] == "key,p,v\nYear,observationDate,{Data}\n"
        assert ctx.session.state["best_attempt_number"] == 0


# ============================================================================
# Test MaxRetriesCheckAgent best-attempt restoration
# ============================================================================

class TestMaxRetriesRestoration:
    """Tests for best-attempt restoration in MaxRetriesCheckAgent."""

    def test_restores_best_when_current_is_worse(self, tmp_path):
        """When max retries reached and current attempt is worse, restore best."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        pvmap_path = output_dir / "generated_pvmap.csv"
        pvmap_path.write_text("current,attempt,csv\n")

        dataset = make_mock_dataset(output_dir=str(output_dir))

        ctx = make_ctx(
            dataset,
            attempt_number=3,  # >= max_retries (3)
            validation_data_rows=100,
            best_data_rows=500,
            best_pvmap_csv="best,attempt,csv\n",
            best_attempt_number=1,
            best_validation_passed=False,
            pvmap_csv="current,attempt,csv\n",
            error_feedback="some feedback",
        )

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, ctx)

        # Should have restored best PVMAP
        assert ctx.session.state["pvmap_csv"] == "best,attempt,csv\n"
        assert ctx.session.state["validation_data_rows"] == 500
        # File should be overwritten with best PVMAP
        assert pvmap_path.read_text() == "best,attempt,csv\n"
        # Should have escalated (exit loop)
        assert any(e.actions and e.actions.escalate for e in events)
        # best_validation_passed=False, so generation_success should still be False
        assert ctx.session.state["generation_success"] is False

    def test_restores_valid_best_marks_success(self, tmp_path):
        """When best attempt was validated, restoring it should set generation_success=True."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        pvmap_path = output_dir / "generated_pvmap.csv"
        pvmap_path.write_text("current,failed,csv\n")

        dataset = make_mock_dataset(output_dir=str(output_dir))

        ctx = make_ctx(
            dataset,
            attempt_number=3,  # >= max_retries (3)
            validation_data_rows=0,  # Current attempt failed validation
            validation_passed=False,
            best_data_rows=500,
            best_pvmap_csv="best,valid,csv\n",
            best_attempt_number=0,
            best_validation_passed=True,  # Best attempt passed validation
            pvmap_csv="current,failed,csv\n",
            error_feedback="validation failed",
        )

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, ctx)

        # Should have restored best PVMAP
        assert ctx.session.state["pvmap_csv"] == "best,valid,csv\n"
        assert ctx.session.state["validation_data_rows"] == 500
        # Key fix: generation_success should be True because best was valid
        assert ctx.session.state["generation_success"] is True
        assert ctx.session.state["validation_passed"] is True
        assert ctx.session.state["exit_reason"] == "best_attempt_restored"
        # File should be overwritten
        assert pvmap_path.read_text() == "best,valid,csv\n"

    def test_restores_valid_best_with_zero_rows(self, tmp_path):
        """When best attempt had 0 rows but was valid, and current also has 0 rows
        but is invalid, should still restore the valid attempt."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        pvmap_path = output_dir / "generated_pvmap.csv"
        pvmap_path.write_text("current,invalid,csv\n")

        dataset = make_mock_dataset(output_dir=str(output_dir))

        ctx = make_ctx(
            dataset,
            attempt_number=3,
            validation_data_rows=0,  # Current: 0 rows, invalid
            validation_passed=False,
            best_data_rows=0,  # Best: also 0 rows, but valid
            best_pvmap_csv="best,valid,zero_rows,csv\n",
            best_attempt_number=0,
            best_validation_passed=True,
            pvmap_csv="current,invalid,csv\n",
            error_feedback="0 output rows",
        )

        agent = MaxRetriesCheckAgent(max_retries=3)
        events = run_agent(agent, ctx)

        # Should restore because best was valid, current was not
        assert ctx.session.state["pvmap_csv"] == "best,valid,zero_rows,csv\n"
        assert ctx.session.state["generation_success"] is True
        assert ctx.session.state["validation_passed"] is True
        assert ctx.session.state["exit_reason"] == "best_attempt_restored"

    def test_keeps_current_when_it_is_best(self, tmp_path):
        """When current attempt is already best, don't restore."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        dataset = make_mock_dataset(output_dir=str(output_dir))

        ctx = make_ctx(
            dataset,
            attempt_number=3,
            validation_data_rows=500,
            best_data_rows=300,
            best_pvmap_csv="older,attempt,csv\n",
            best_attempt_number=0,
            pvmap_csv="current,best,csv\n",
            error_feedback="some feedback",
        )

        agent = MaxRetriesCheckAgent(max_retries=3)
        run_agent(agent, ctx)

        # Should keep current PVMAP
        assert ctx.session.state["pvmap_csv"] == "current,best,csv\n"
        assert ctx.session.state["validation_data_rows"] == 500

    def test_no_restore_when_no_best_csv(self, tmp_path):
        """When best_pvmap_csv is None, skip restoration."""
        dataset = make_mock_dataset(output_dir=str(tmp_path))

        ctx = make_ctx(
            dataset,
            attempt_number=3,
            validation_data_rows=100,
            best_data_rows=0,
            best_pvmap_csv=None,
            best_attempt_number=None,
            pvmap_csv="only,attempt,csv\n",
            error_feedback="some feedback",
        )

        agent = MaxRetriesCheckAgent(max_retries=3)
        run_agent(agent, ctx)

        # Should keep current PVMAP unchanged
        assert ctx.session.state["pvmap_csv"] == "only,attempt,csv\n"


# ============================================================================
# Test ConditionalFeedbackAgent deterministic fallback
# ============================================================================

class TestDeterministicFeedback:
    """Tests for _build_deterministic_feedback() method."""

    def _make_feedback_agent(self):
        """Create a ConditionalFeedbackAgent for testing."""
        from src.agents.pvmap_retry_loop import ConditionalFeedbackAgent
        return ConditionalFeedbackAgent(name="TestFeedback")

    def _make_feedback_ctx(self, **state_overrides):
        """Create a mock context for feedback tests."""
        dataset = make_mock_dataset()
        return make_ctx(dataset, **state_overrides)

    def test_deterministic_feedback_has_validation_error(self):
        """Fallback feedback should include validation_error from state."""
        agent = self._make_feedback_agent()
        ctx = self._make_feedback_ctx(
            validation_error="Key not found: 'POPULATION' — no matching column header",
            key_match_report="",
            validation_counter_summary="",
        )
        error = RuntimeError("429 Resource Exhausted")

        feedback = agent._build_deterministic_feedback(ctx, error)

        assert "Key not found" in feedback
        assert "POPULATION" in feedback
        assert "Validation Error" in feedback

    def test_deterministic_feedback_has_key_match_report(self):
        """Fallback feedback should include key_match_report from state."""
        agent = self._make_feedback_agent()
        ctx = self._make_feedback_ctx(
            validation_error="Some error",
            key_match_report="## KEY MATCH REPORT\n**Match rate:** 50% (3/6 unique columns)",
            validation_counter_summary="",
        )
        error = RuntimeError("Timeout")

        feedback = agent._build_deterministic_feedback(ctx, error)

        assert "KEY MATCH REPORT" in feedback
        assert "Match rate" in feedback

    def test_deterministic_feedback_zero_rows_guidance(self):
        """When validation_error mentions 0 rows, fallback should give key mismatch advice."""
        agent = self._make_feedback_agent()
        ctx = self._make_feedback_ctx(
            validation_error="Validation produced 0 rows — all observations were dropped",
            key_match_report="",
            validation_counter_summary="",
        )
        error = RuntimeError("Rate limit")

        feedback = agent._build_deterministic_feedback(ctx, error)

        assert "0 output rows" in feedback or "0 rows" in feedback
        assert "column headers" in feedback.lower() or "key" in feedback.lower()

    def test_deterministic_feedback_eval_guidance(self):
        """When validation_error mentions #Eval, fallback should give eval-specific advice."""
        agent = self._make_feedback_agent()
        ctx = self._make_feedback_ctx(
            validation_error="Error in #Eval expression: SyntaxError in eval()",
            key_match_report="",
            validation_counter_summary="",
        )
        error = RuntimeError("LLM crash")

        feedback = agent._build_deterministic_feedback(ctx, error)

        assert "#Eval" in feedback
        assert "f-string" in feedback.lower() or "simple" in feedback.lower()
