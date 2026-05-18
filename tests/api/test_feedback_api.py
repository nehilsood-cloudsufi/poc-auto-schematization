"""Unit tests for feedback API data model logic (ledger accumulation, entry wrapping)."""
import pytest

from src.api.models.feedback import (
    FeedbackEntry,
    FeedbackEntryInput,
    FeedbackLedger,
    FeedbackType,
)


class TestLegacyWrapping:
    """Test that legacy text+category requests are wrapped as typed entries."""

    def test_other_category_wraps_as_free_text(self):
        entry_input = FeedbackEntryInput.from_legacy(
            category="Other",
            content="Something is wrong",
        )
        assert entry_input.type == FeedbackType.FREE_TEXT
        assert entry_input.content == "Something is wrong"
        assert entry_input.target is None

    def test_column_mapping_category_wraps_as_set_mapping(self):
        entry_input = FeedbackEntryInput.from_legacy(
            category="Column mapping",
            content="Map col_a to observationAbout",
        )
        assert entry_input.type == FeedbackType.SET_MAPPING
        assert entry_input.content == "Map col_a to observationAbout"

    def test_unknown_category_falls_back_to_free_text(self):
        entry_input = FeedbackEntryInput.from_legacy(
            category="NonExistentCategory",
            content="Some feedback",
        )
        assert entry_input.type == FeedbackType.FREE_TEXT

    def test_value_formatting_wraps_as_apply_rule(self):
        entry_input = FeedbackEntryInput.from_legacy(
            category="Value formatting",
            content="Dates should be ISO 8601",
        )
        assert entry_input.type == FeedbackType.APPLY_RULE

    def test_target_is_passed_through(self):
        entry_input = FeedbackEntryInput.from_legacy(
            category="Column mapping",
            content="Map this column",
            target="col_x",
        )
        assert entry_input.target == "col_x"


class TestLedgerAccumulation:
    """Test that ledger accumulates entries across multiple rounds."""

    def _make_entry(self, round_num: int, content: str, target=None) -> FeedbackEntry:
        return FeedbackEntry(
            type=FeedbackType.FREE_TEXT,
            round=round_num,
            source="human",
            content=content,
            target=target,
        )

    def test_round_2_adds_to_round_1_entries(self):
        ledger = FeedbackLedger()

        # Round 1 entry
        e1 = self._make_entry(round_num=1, content="Round 1 feedback")
        ledger.add_entry(e1)

        # Round 2 entry added to the same ledger
        e2 = self._make_entry(round_num=2, content="Round 2 additional feedback")
        ledger.add_entry(e2)

        assert len(ledger.entries) == 2
        active = ledger.active_human_entries()
        assert len(active) == 2
        assert active[0].content == "Round 1 feedback"
        assert active[1].content == "Round 2 additional feedback"

    def test_same_target_supersedes_older_entry(self):
        ledger = FeedbackLedger()

        e1 = self._make_entry(round_num=1, content="Map col_a to X", target="col_a")
        ledger.add_entry(e1)

        e2 = self._make_entry(round_num=2, content="Map col_a to Y", target="col_a")
        ledger.add_entry(e2)

        # Both entries are stored but e1 is superseded
        assert len(ledger.entries) == 2
        assert ledger.entries[0].superseded is True
        assert ledger.entries[1].superseded is False

        # active_human_entries excludes superseded
        active = ledger.active_human_entries()
        assert len(active) == 1
        assert active[0].content == "Map col_a to Y"

    def test_different_targets_do_not_supersede(self):
        ledger = FeedbackLedger()

        e1 = self._make_entry(round_num=1, content="Map col_a", target="col_a")
        e2 = self._make_entry(round_num=2, content="Map col_b", target="col_b")
        ledger.add_entry(e1)
        ledger.add_entry(e2)

        active = ledger.active_human_entries()
        assert len(active) == 2
        assert all(not e.superseded for e in active)

    def test_clear_auto_entries_preserves_human_entries(self):
        ledger = FeedbackLedger()

        human_entry = FeedbackEntry(
            type=FeedbackType.FREE_TEXT,
            round=1,
            source="human",
            content="Human says fix this",
        )
        auto_entry = FeedbackEntry(
            type=FeedbackType.AUTO,
            round=1,
            source="auto",
            content="Auto-detected issue",
        )
        ledger.add_entry(human_entry)
        ledger.add_entry(auto_entry)

        assert len(ledger.entries) == 2
        ledger.clear_auto_entries()
        assert len(ledger.entries) == 1
        assert ledger.entries[0].source == "human"


class TestRetractEntry:
    """Test that retract marks an entry as retracted and persists."""

    def test_retract_marks_entry_retracted(self):
        ledger = FeedbackLedger()
        entry = FeedbackEntry(
            type=FeedbackType.FREE_TEXT,
            round=1,
            source="human",
            content="This needs fixing",
        )
        ledger.add_entry(entry)
        entry_id = entry.id

        result = ledger.retract(entry_id)

        assert result is True
        assert ledger.entries[0].retracted is True

    def test_retract_excludes_from_active_entries(self):
        ledger = FeedbackLedger()
        e1 = FeedbackEntry(
            type=FeedbackType.FREE_TEXT,
            round=1,
            source="human",
            content="Keep this",
        )
        e2 = FeedbackEntry(
            type=FeedbackType.FREE_TEXT,
            round=1,
            source="human",
            content="Retract this",
        )
        ledger.add_entry(e1)
        ledger.add_entry(e2)

        ledger.retract(e2.id)

        active = ledger.active_human_entries()
        assert len(active) == 1
        assert active[0].content == "Keep this"

    def test_retract_nonexistent_entry_returns_false(self):
        ledger = FeedbackLedger()
        result = ledger.retract("nonexistent_id")
        assert result is False

    def test_retracted_state_survives_serialization(self):
        """Retracted flag must survive a round-trip through JSON."""
        ledger = FeedbackLedger()
        entry = FeedbackEntry(
            type=FeedbackType.FREE_TEXT,
            round=1,
            source="human",
            content="Will be retracted",
        )
        ledger.add_entry(entry)
        ledger.retract(entry.id)

        # Serialize and reload
        serialized = ledger.model_dump_json()
        reloaded = FeedbackLedger.model_validate_json(serialized)

        assert len(reloaded.entries) == 1
        assert reloaded.entries[0].retracted is True
        assert len(reloaded.active_human_entries()) == 0
