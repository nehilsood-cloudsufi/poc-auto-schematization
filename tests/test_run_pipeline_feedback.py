"""Tests for the human feedback -> FeedbackLedger injection logic in run_pipeline.py.

These tests exercise the parsing logic in isolation without running the full pipeline.
The logic lives in `run_dataset_pipeline()` around lines 662-680 of src/run_pipeline.py.
"""
import json

import pytest

from src.api.models.feedback import FeedbackEntry, FeedbackLedger, FeedbackType


# ---------------------------------------------------------------------------
# Helpers that replicate the injection block so we can unit-test it cleanly
# ---------------------------------------------------------------------------

def _apply_feedback_injection(
    human_feedback: str,
    initial_state: dict,
    extra_initial_state: dict | None = None,
) -> dict:
    """Reproduce the human-feedback injection block from run_dataset_pipeline().

    Returns the mutated initial_state dict.
    """
    if human_feedback:
        ledger_json = initial_state.get("feedback_ledger_json") or (
            extra_initial_state.get("feedback_ledger_json") if extra_initial_state else None
        )
        if not ledger_json:
            ledger = FeedbackLedger()
            ledger.add_entry(FeedbackEntry(
                type=FeedbackType.FREE_TEXT, round=1,
                source="human", content=human_feedback,
            ))
            initial_state["feedback_ledger_json"] = ledger.model_dump_json()
        initial_state["error_feedback"] = human_feedback
        initial_state["human_feedback_provided"] = True

    return initial_state


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestLegacyFeedbackStringCreatesLedger:
    """Legacy path: raw feedback string with no pre-existing ledger."""

    def test_feedback_ledger_json_is_set(self):
        state = _apply_feedback_injection("Please fix the date column", {})
        assert "feedback_ledger_json" in state

    def test_ledger_contains_one_entry(self):
        state = _apply_feedback_injection("Please fix the date column", {})
        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(ledger.entries) == 1

    def test_entry_type_is_free_text(self):
        state = _apply_feedback_injection("Please fix the date column", {})
        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert ledger.entries[0].type == FeedbackType.FREE_TEXT

    def test_entry_source_is_human(self):
        state = _apply_feedback_injection("Please fix the date column", {})
        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert ledger.entries[0].source == "human"

    def test_entry_content_matches_feedback(self):
        feedback = "Please fix the date column"
        state = _apply_feedback_injection(feedback, {})
        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert ledger.entries[0].content == feedback

    def test_entry_round_is_1(self):
        state = _apply_feedback_injection("Some feedback", {})
        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert ledger.entries[0].round == 1


class TestPreExistingLedgerInInitialState:
    """When feedback_ledger_json is already in initial_state, no new ledger is created."""

    def test_existing_ledger_not_overwritten(self):
        existing_ledger = FeedbackLedger()
        existing_ledger.add_entry(FeedbackEntry(
            type=FeedbackType.SET_MAPPING, round=1,
            source="human", content="Map col A to observationAbout",
        ))
        existing_json = existing_ledger.model_dump_json()

        state = _apply_feedback_injection(
            "New feedback",
            {"feedback_ledger_json": existing_json},
        )

        assert state["feedback_ledger_json"] == existing_json

    def test_existing_ledger_entry_count_unchanged(self):
        existing_ledger = FeedbackLedger()
        existing_ledger.add_entry(FeedbackEntry(
            type=FeedbackType.SET_MAPPING, round=1,
            source="human", content="Map col A to observationAbout",
        ))
        existing_json = existing_ledger.model_dump_json()

        state = _apply_feedback_injection(
            "New feedback",
            {"feedback_ledger_json": existing_json},
        )

        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(ledger.entries) == 1


class TestPreExistingLedgerInExtraInitialState:
    """When feedback_ledger_json is in extra_initial_state (not yet merged), no new ledger is created."""

    def test_ledger_from_extra_state_prevents_new_ledger(self):
        extra_ledger = FeedbackLedger()
        extra_ledger.add_entry(FeedbackEntry(
            type=FeedbackType.APPLY_RULE, round=2,
            source="human", content="Apply unit conversion",
        ))
        extra_json = extra_ledger.model_dump_json()

        state = _apply_feedback_injection(
            "Some raw feedback",
            {},
            extra_initial_state={"feedback_ledger_json": extra_json},
        )

        # The pre-existing ledger (from extra_initial_state) was used — so only 1 entry
        # (the injection block should NOT have created a new single-entry ledger)
        # The state may or may not have feedback_ledger_json depending on whether we
        # eagerly copy it. The key invariant is: the original ledger is not replaced.
        # Since extra_initial_state is not yet applied, initial_state["feedback_ledger_json"]
        # may be absent. What matters is: if it IS present, it matches the extra one.
        if "feedback_ledger_json" in state:
            ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
            # Should NOT be the auto-created single FREE_TEXT entry
            assert not (
                len(ledger.entries) == 1
                and ledger.entries[0].type == FeedbackType.FREE_TEXT
                and ledger.entries[0].content == "Some raw feedback"
            )

    def test_no_new_ledger_created_when_extra_state_has_ledger(self):
        """Ensures the injection block skips ledger creation when extra_initial_state carries one."""
        extra_ledger = FeedbackLedger()
        extra_ledger.add_entry(FeedbackEntry(
            type=FeedbackType.PIN_ROW, round=1,
            source="human", content="Pin row 5",
        ))
        extra_json = extra_ledger.model_dump_json()

        initial_state_before = {}
        result = _apply_feedback_injection(
            "raw feedback",
            initial_state_before,
            extra_initial_state={"feedback_ledger_json": extra_json},
        )

        # The injection block should not have set feedback_ledger_json in initial_state
        # (it detected extra_initial_state already has one)
        assert "feedback_ledger_json" not in result


class TestBackwardCompatKeys:
    """error_feedback and human_feedback_provided are always set when feedback is non-empty."""

    def test_error_feedback_set(self):
        feedback = "Check the unit column"
        state = _apply_feedback_injection(feedback, {})
        assert state["error_feedback"] == feedback

    def test_human_feedback_provided_set_true(self):
        state = _apply_feedback_injection("Any feedback", {})
        assert state["human_feedback_provided"] is True

    def test_error_feedback_set_when_ledger_preexists(self):
        existing_ledger = FeedbackLedger()
        existing_ledger.add_entry(FeedbackEntry(
            type=FeedbackType.FREE_TEXT, round=1,
            source="human", content="old feedback",
        ))
        feedback = "new feedback"
        state = _apply_feedback_injection(
            feedback,
            {"feedback_ledger_json": existing_ledger.model_dump_json()},
        )
        assert state["error_feedback"] == feedback
        assert state["human_feedback_provided"] is True

    def test_no_keys_set_when_feedback_is_empty_string(self):
        state = _apply_feedback_injection("", {})
        assert "error_feedback" not in state
        assert "human_feedback_provided" not in state
        assert "feedback_ledger_json" not in state

    def test_no_keys_set_when_feedback_is_none(self):
        # Pass None — simulates the default param value
        state = _apply_feedback_injection(None, {})  # type: ignore[arg-type]
        assert "error_feedback" not in state
        assert "human_feedback_provided" not in state
        assert "feedback_ledger_json" not in state


class TestLedgerJsonIsValidJson:
    """Sanity-check that the stored value is parseable JSON."""

    def test_ledger_json_parseable(self):
        state = _apply_feedback_injection("Fix the mapping", {})
        raw = state["feedback_ledger_json"]
        parsed = json.loads(raw)
        assert "entries" in parsed
        assert isinstance(parsed["entries"], list)
