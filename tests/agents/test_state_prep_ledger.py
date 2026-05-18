"""Tests for FeedbackLedger integration in StatePreparationAgent.

These tests verify the data-flow patterns (ledger JSON roundtrip, derived state
keys, auto-feedback parsing, human entry preservation) without spinning up a
full ADK agent.
"""
import json

import pytest

from src.api.models.feedback import (
    FeedbackEntry,
    FeedbackLedger,
    FeedbackType,
)
from src.api.services.feedback_merger import FeedbackMerger
from src.agents.template_utils import escape_pvmap_placeholders


# ---------------------------------------------------------------------------
# 1. Ledger JSON roundtrip via state key
# ---------------------------------------------------------------------------

class TestLedgerJsonRoundtrip:
    """Verify that serializing/deserializing the ledger through a state dict
    preserves all entry data."""

    def test_empty_ledger_roundtrip(self):
        ledger = FeedbackLedger()
        state = {"feedback_ledger_json": ledger.model_dump_json()}

        restored = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert restored.entries == []

    def test_ledger_with_entries_roundtrip(self):
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.FREE_TEXT, round=1,
            source="human", content="Fix the date column",
        ))
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=1,
            source="auto", content="Column X is unmapped",
        ))
        state = {"feedback_ledger_json": ledger.model_dump_json()}

        restored = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(restored.entries) == 2
        assert restored.entries[0].source == "human"
        assert restored.entries[0].content == "Fix the date column"
        assert restored.entries[1].source == "auto"

    def test_retracted_entries_survive_roundtrip(self):
        ledger = FeedbackLedger()
        entry = FeedbackEntry(
            type=FeedbackType.SET_MAPPING, round=1,
            source="human", content="observationDate",
            target="Year",
        )
        ledger.add_entry(entry)
        ledger.retract(entry.id)

        state = {"feedback_ledger_json": ledger.model_dump_json()}
        restored = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert restored.entries[0].retracted is True


# ---------------------------------------------------------------------------
# 2. Ledger render populates derived state keys
# ---------------------------------------------------------------------------

class TestLedgerRenderPopulatesDerivedKeys:
    """Simulate the Change 3 logic that renders the ledger into prompt
    sections and verify all derived state keys are populated."""

    @staticmethod
    def _simulate_render_to_state(state: dict) -> dict:
        """Reproduce the Change 3 logic from StatePreparationAgent."""
        ledger_json = state.get("feedback_ledger_json", "")
        if ledger_json:
            ledger = FeedbackLedger.model_validate_json(ledger_json)
            merger = FeedbackMerger()
            human_text, auto_text = merger.render_separate(ledger)
            merged = merger.merge(ledger)

            if len(merged) > 4000:
                merged = merged[:4000] + "\n...[truncated for token budget]"

            state["human_feedback_prompt"] = escape_pvmap_placeholders(human_text)
            state["auto_feedback_prompt"] = escape_pvmap_placeholders(auto_text)
            state["error_feedback"] = escape_pvmap_placeholders(merged)
            state["human_feedback_provided"] = ledger.has_human_entries()
            state["human_instructions_summary"] = escape_pvmap_placeholders(
                merger.render_human_summary(ledger)
            )
        else:
            error_feedback = state.get("error_feedback", "")
            if error_feedback:
                if len(error_feedback) > 4000:
                    error_feedback = error_feedback[:4000] + "\n...[truncated for token budget]"
                state["error_feedback"] = escape_pvmap_placeholders(error_feedback)
            state.setdefault("human_feedback_prompt", "")
            state.setdefault("auto_feedback_prompt", "")
            state.setdefault("human_instructions_summary", "(No human instructions provided)")
        return state

    def test_empty_ledger_sets_defaults(self):
        ledger = FeedbackLedger()
        state = {"feedback_ledger_json": ledger.model_dump_json()}
        state = self._simulate_render_to_state(state)

        assert state["human_feedback_prompt"] == ""
        assert state["auto_feedback_prompt"] == ""
        assert state["error_feedback"] == ""
        assert state["human_feedback_provided"] is False
        assert state["human_instructions_summary"] == "(No human instructions provided)"

    def test_human_entry_populates_prompt(self):
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.SET_MAPPING, round=1,
            source="human", content="observationDate",
            target="Year",
        ))
        state = {"feedback_ledger_json": ledger.model_dump_json()}
        state = self._simulate_render_to_state(state)

        assert "REQUIRED MAPPING" in state["human_feedback_prompt"]
        assert "Year" in state["human_feedback_prompt"]
        assert state["human_feedback_provided"] is True
        assert "set_mapping" in state["human_instructions_summary"]

    def test_auto_entry_populates_auto_prompt(self):
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=1,
            source="auto", content="Validation found 5 errors in column X",
        ))
        state = {"feedback_ledger_json": ledger.model_dump_json()}
        state = self._simulate_render_to_state(state)

        assert state["auto_feedback_prompt"] != ""
        assert "5 errors" in state["auto_feedback_prompt"]
        assert state["human_feedback_provided"] is False

    def test_merged_contains_both_human_and_auto(self):
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.FREE_TEXT, round=1,
            source="human", content="Keep Year column as-is",
        ))
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=1,
            source="auto", content="Column X unmapped",
        ))
        state = {"feedback_ledger_json": ledger.model_dump_json()}
        state = self._simulate_render_to_state(state)

        assert "Keep Year column" in state["error_feedback"]
        assert "Column X unmapped" in state["error_feedback"]

    def test_large_merged_is_truncated(self):
        ledger = FeedbackLedger()
        # Create a very large auto feedback entry
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=1,
            source="auto", content="X" * 5000,
        ))
        state = {"feedback_ledger_json": ledger.model_dump_json()}
        state = self._simulate_render_to_state(state)

        assert len(state["error_feedback"]) <= 4100  # 4000 + truncation msg
        assert "truncated for token budget" in state["error_feedback"]

    def test_pvmap_placeholders_escaped_in_all_keys(self):
        """Ensure {Data} and {Number} in feedback are escaped to [DATA]/[NUMBER]."""
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.FREE_TEXT, round=1,
            source="human", content="Map Year to {Data} format",
        ))
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=1,
            source="auto", content="Value should use {Number}",
        ))
        state = {"feedback_ledger_json": ledger.model_dump_json()}
        state = self._simulate_render_to_state(state)

        # Escaped form depends on escape_pvmap_placeholders implementation
        assert "{Data}" not in state["human_feedback_prompt"]
        assert "{Number}" not in state["auto_feedback_prompt"]
        assert "{Data}" not in state["error_feedback"]

    def test_no_ledger_fallback_uses_raw_error_feedback(self):
        """When no ledger JSON exists, fall back to raw error_feedback."""
        state = {
            "feedback_ledger_json": "",
            "error_feedback": "Some raw error from old path",
        }
        state = self._simulate_render_to_state(state)

        assert "Some raw error" in state["error_feedback"]
        assert state["human_feedback_prompt"] == ""
        assert state["human_instructions_summary"] == "(No human instructions provided)"


# ---------------------------------------------------------------------------
# 3. Auto feedback raw parsed into ledger correctly
# ---------------------------------------------------------------------------

class TestAutoFeedbackRawParsing:
    """Simulate the Change 2 logic: auto_feedback_raw from previous iteration
    is consumed and added to the ledger."""

    @staticmethod
    def _simulate_auto_feedback_parse(state: dict, attempt: int) -> dict:
        """Reproduce the Change 2 logic from StatePreparationAgent."""
        auto_raw = state.pop("auto_feedback_raw", "")
        if auto_raw and attempt > 0:
            ledger_json = state.get("feedback_ledger_json", "")
            if ledger_json:
                ledger = FeedbackLedger.model_validate_json(ledger_json)
                ledger.clear_auto_entries()
                ledger.add_entry(FeedbackEntry(
                    type=FeedbackType.AUTO, round=attempt,
                    source="auto", content=auto_raw,
                ))
                state["feedback_ledger_json"] = ledger.model_dump_json()
        return state

    def test_auto_raw_consumed_on_attempt_1(self):
        ledger = FeedbackLedger()
        state = {
            "feedback_ledger_json": ledger.model_dump_json(),
            "auto_feedback_raw": "Column X has 3 errors",
        }
        state = self._simulate_auto_feedback_parse(state, attempt=1)

        assert "auto_feedback_raw" not in state
        restored = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(restored.entries) == 1
        assert restored.entries[0].source == "auto"
        assert restored.entries[0].content == "Column X has 3 errors"
        assert restored.entries[0].round == 1

    def test_auto_raw_ignored_on_attempt_0(self):
        ledger = FeedbackLedger()
        state = {
            "feedback_ledger_json": ledger.model_dump_json(),
            "auto_feedback_raw": "Should not be added",
        }
        state = self._simulate_auto_feedback_parse(state, attempt=0)

        # auto_feedback_raw is still popped but not added to ledger
        assert "auto_feedback_raw" not in state
        restored = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(restored.entries) == 0

    def test_auto_raw_replaces_old_auto_entries(self):
        """clear_auto_entries removes prior auto feedback before adding new."""
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=1,
            source="auto", content="Old auto feedback",
        ))
        state = {
            "feedback_ledger_json": ledger.model_dump_json(),
            "auto_feedback_raw": "New auto feedback",
        }
        state = self._simulate_auto_feedback_parse(state, attempt=2)

        restored = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        auto_entries = [e for e in restored.entries if e.source == "auto"]
        assert len(auto_entries) == 1
        assert auto_entries[0].content == "New auto feedback"
        assert auto_entries[0].round == 2

    def test_empty_auto_raw_is_noop(self):
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=1,
            source="auto", content="Existing auto feedback",
        ))
        state = {
            "feedback_ledger_json": ledger.model_dump_json(),
            "auto_feedback_raw": "",
        }
        state = self._simulate_auto_feedback_parse(state, attempt=2)

        restored = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        # Existing auto entry should remain since auto_raw was empty
        auto_entries = [e for e in restored.entries if e.source == "auto"]
        assert len(auto_entries) == 1
        assert auto_entries[0].content == "Existing auto feedback"


# ---------------------------------------------------------------------------
# 4. Human entries preserved when auto entries cleared between attempts
# ---------------------------------------------------------------------------

class TestHumanEntriesPreservedAcrossAttempts:
    """Verify that human entries survive clear_auto_entries calls across
    multiple simulated retry iterations."""

    def test_human_entries_survive_auto_clear(self):
        ledger = FeedbackLedger()
        # Simulate: human feedback from UI
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.SET_MAPPING, round=1,
            source="human", content="observationDate",
            target="Year",
        ))
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.PIN_ROW, round=1,
            source="human", content="Keep header row",
            target="row_0",
        ))
        # Simulate: auto feedback from iteration 1
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO, round=1,
            source="auto", content="5 unmapped columns",
        ))

        # Clear auto (like iteration 2 prep)
        ledger.clear_auto_entries()

        assert len(ledger.entries) == 2
        assert all(e.source == "human" for e in ledger.entries)
        assert ledger.has_human_entries() is True

    def test_three_iteration_cycle(self):
        """Full cycle: attempt 0 init -> attempt 1 auto -> attempt 2 auto.
        Human entries must survive all clears."""
        # Attempt 0: human feedback injected
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.FREE_TEXT, round=1,
            source="human", content="Use wikidataId for places",
        ))
        state = {"feedback_ledger_json": ledger.model_dump_json()}

        # Attempt 1: auto feedback arrives
        state["auto_feedback_raw"] = "Validation errors: 12 unmapped keys"
        auto_raw = state.pop("auto_feedback_raw", "")
        if auto_raw:
            ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
            ledger.clear_auto_entries()
            ledger.add_entry(FeedbackEntry(
                type=FeedbackType.AUTO, round=1,
                source="auto", content=auto_raw,
            ))
            state["feedback_ledger_json"] = ledger.model_dump_json()

        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(ledger.active_human_entries()) == 1
        assert len(ledger.active_auto_entries()) == 1

        # Attempt 2: new auto feedback replaces old
        state["auto_feedback_raw"] = "Validation errors: 3 unmapped keys"
        auto_raw = state.pop("auto_feedback_raw", "")
        if auto_raw:
            ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
            ledger.clear_auto_entries()
            ledger.add_entry(FeedbackEntry(
                type=FeedbackType.AUTO, round=2,
                source="auto", content=auto_raw,
            ))
            state["feedback_ledger_json"] = ledger.model_dump_json()

        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(ledger.active_human_entries()) == 1
        assert ledger.active_human_entries()[0].content == "Use wikidataId for places"
        assert len(ledger.active_auto_entries()) == 1
        assert ledger.active_auto_entries()[0].content == "Validation errors: 3 unmapped keys"
        assert ledger.active_auto_entries()[0].round == 2

    def test_retracted_human_not_in_active(self):
        """Retracted human entries are excluded from active_human_entries."""
        ledger = FeedbackLedger()
        entry = FeedbackEntry(
            type=FeedbackType.FREE_TEXT, round=1,
            source="human", content="Old instruction",
        )
        ledger.add_entry(entry)
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.FREE_TEXT, round=2,
            source="human", content="New instruction",
        ))
        ledger.retract(entry.id)

        assert len(ledger.active_human_entries()) == 1
        assert ledger.active_human_entries()[0].content == "New instruction"
        # has_human_entries includes retracted (checks source only)
        assert ledger.has_human_entries() is True


# ---------------------------------------------------------------------------
# 5. Attempt 0 initialization paths
# ---------------------------------------------------------------------------

class TestAttempt0Initialization:
    """Simulate the Change 1 logic: attempt 0 initializes the ledger."""

    @staticmethod
    def _simulate_attempt0_init(state: dict) -> dict:
        """Reproduce the Change 1 logic from StatePreparationAgent."""
        state["quality_metrics_history"] = []
        ledger_json = state.get("feedback_ledger_json", "")
        if ledger_json:
            pass  # ledger already in state
        elif state.get("human_feedback_provided"):
            raw = state.get("error_feedback", "")
            ledger = FeedbackLedger()
            if raw:
                ledger.add_entry(FeedbackEntry(
                    type=FeedbackType.FREE_TEXT, round=1,
                    source="human", content=raw,
                ))
            state["feedback_ledger_json"] = ledger.model_dump_json()
        else:
            state["feedback_ledger_json"] = FeedbackLedger().model_dump_json()
            state["error_feedback"] = ""
        return state

    def test_fresh_run_creates_empty_ledger(self):
        state = {}
        state = self._simulate_attempt0_init(state)

        assert "feedback_ledger_json" in state
        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(ledger.entries) == 0
        assert state["error_feedback"] == ""

    def test_human_feedback_wrapped_in_ledger(self):
        state = {
            "human_feedback_provided": True,
            "error_feedback": "Fix the date column to use {Data}",
        }
        state = self._simulate_attempt0_init(state)

        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(ledger.entries) == 1
        assert ledger.entries[0].source == "human"
        assert ledger.entries[0].type == FeedbackType.FREE_TEXT
        assert "Fix the date column" in ledger.entries[0].content

    def test_existing_ledger_preserved(self):
        """If feedback_ledger_json is already in state, don't overwrite it."""
        existing = FeedbackLedger()
        existing.add_entry(FeedbackEntry(
            type=FeedbackType.SET_MAPPING, round=1,
            source="human", content="observationDate",
            target="Year",
        ))
        state = {"feedback_ledger_json": existing.model_dump_json()}
        state = self._simulate_attempt0_init(state)

        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(ledger.entries) == 1
        assert ledger.entries[0].type == FeedbackType.SET_MAPPING

    def test_human_feedback_empty_string_creates_empty_ledger(self):
        state = {
            "human_feedback_provided": True,
            "error_feedback": "",
        }
        state = self._simulate_attempt0_init(state)

        ledger = FeedbackLedger.model_validate_json(state["feedback_ledger_json"])
        assert len(ledger.entries) == 0
