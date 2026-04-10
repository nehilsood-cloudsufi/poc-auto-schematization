"""Tests for FeedbackLedger data model."""
import pytest
from datetime import datetime, timezone

from src.api.models.feedback import (
    FeedbackEntry,
    FeedbackEntryInput,
    FeedbackLedger,
    FeedbackType,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_human_entry(
    type_: FeedbackType = FeedbackType.FREE_TEXT,
    content: str = "fix this",
    target: str | None = None,
    retracted: bool = False,
    superseded: bool = False,
) -> FeedbackEntry:
    return FeedbackEntry(
        type=type_,
        round=1,
        source="human",
        content=content,
        target=target,
        retracted=retracted,
        superseded=superseded,
    )


def make_auto_entry(
    type_: FeedbackType = FeedbackType.SET_MAPPING,
    content: str = "auto fix",
    target: str | None = None,
    retracted: bool = False,
    superseded: bool = False,
) -> FeedbackEntry:
    return FeedbackEntry(
        type=type_,
        round=1,
        source="auto",
        content=content,
        target=target,
        retracted=retracted,
        superseded=superseded,
    )


# ---------------------------------------------------------------------------
# FeedbackType
# ---------------------------------------------------------------------------

class TestFeedbackType:
    def test_enum_values_exist(self):
        assert FeedbackType.PIN_ROW
        assert FeedbackType.SET_MAPPING
        assert FeedbackType.APPLY_RULE
        assert FeedbackType.FREE_TEXT
        assert FeedbackType.AUTO

    def test_enum_string_values(self):
        assert FeedbackType.PIN_ROW.value == "pin_row"
        assert FeedbackType.SET_MAPPING.value == "set_mapping"
        assert FeedbackType.APPLY_RULE.value == "apply_rule"
        assert FeedbackType.FREE_TEXT.value == "free_text"
        assert FeedbackType.AUTO.value == "auto"


# ---------------------------------------------------------------------------
# FeedbackEntry
# ---------------------------------------------------------------------------

class TestFeedbackEntry:
    def test_id_defaults_to_8char_hex(self):
        entry = make_human_entry()
        assert isinstance(entry.id, str)
        assert len(entry.id) == 8
        # Must be valid hex
        int(entry.id, 16)

    def test_ids_are_unique(self):
        ids = {make_human_entry().id for _ in range(20)}
        assert len(ids) == 20

    def test_timestamp_defaults_to_now(self):
        before = datetime.now(timezone.utc)
        entry = make_human_entry()
        after = datetime.now(timezone.utc)
        assert before <= entry.timestamp <= after

    def test_retracted_defaults_false(self):
        entry = make_human_entry()
        assert entry.retracted is False

    def test_superseded_defaults_false(self):
        entry = make_human_entry()
        assert entry.superseded is False

    def test_target_defaults_none(self):
        entry = make_human_entry()
        assert entry.target is None

    def test_source_human(self):
        entry = make_human_entry()
        assert entry.source == "human"

    def test_source_auto(self):
        entry = make_auto_entry()
        assert entry.source == "auto"

    def test_source_rejects_invalid(self):
        with pytest.raises(Exception):
            FeedbackEntry(
                type=FeedbackType.FREE_TEXT,
                round=1,
                source="robot",  # invalid
                content="x",
            )

    def test_json_roundtrip(self):
        entry = make_human_entry(
            type_=FeedbackType.SET_MAPPING,
            content="map col A to B",
            target="col_A",
        )
        json_str = entry.model_dump_json()
        restored = FeedbackEntry.model_validate_json(json_str)
        assert restored.id == entry.id
        assert restored.type == entry.type
        assert restored.source == entry.source
        assert restored.content == entry.content
        assert restored.target == entry.target
        assert restored.retracted == entry.retracted
        assert restored.superseded == entry.superseded


# ---------------------------------------------------------------------------
# FeedbackLedger - basic operations
# ---------------------------------------------------------------------------

class TestFeedbackLedgerBasics:
    def test_empty_ledger(self):
        ledger = FeedbackLedger()
        assert ledger.entries == []

    def test_has_human_entries_false_when_empty(self):
        ledger = FeedbackLedger()
        assert ledger.has_human_entries() is False

    def test_has_human_entries_true_after_adding_human(self):
        ledger = FeedbackLedger()
        ledger.add_entry(make_human_entry())
        assert ledger.has_human_entries() is True

    def test_has_human_entries_false_with_only_auto(self):
        ledger = FeedbackLedger()
        ledger.add_entry(make_auto_entry())
        assert ledger.has_human_entries() is False

    def test_add_entry_appends(self):
        ledger = FeedbackLedger()
        e1 = make_human_entry(content="first")
        e2 = make_human_entry(content="second")
        ledger.add_entry(e1)
        ledger.add_entry(e2)
        assert len(ledger.entries) == 2


# ---------------------------------------------------------------------------
# FeedbackLedger - active_human_entries
# ---------------------------------------------------------------------------

class TestActiveHumanEntries:
    def test_includes_normal_human_entry(self):
        ledger = FeedbackLedger()
        entry = make_human_entry()
        ledger.add_entry(entry)
        assert entry in ledger.active_human_entries()

    def test_excludes_retracted_human_entry(self):
        ledger = FeedbackLedger()
        entry = make_human_entry(retracted=True)
        ledger.add_entry(entry)
        assert ledger.active_human_entries() == []

    def test_excludes_superseded_human_entry(self):
        ledger = FeedbackLedger()
        entry = make_human_entry(superseded=True)
        ledger.add_entry(entry)
        assert ledger.active_human_entries() == []

    def test_excludes_auto_entries(self):
        ledger = FeedbackLedger()
        ledger.add_entry(make_auto_entry())
        assert ledger.active_human_entries() == []

    def test_returns_only_non_retracted_non_superseded_human(self):
        ledger = FeedbackLedger()
        good = make_human_entry(content="good")
        retracted = make_human_entry(content="retracted", retracted=True)
        superseded = make_human_entry(content="superseded", superseded=True)
        auto = make_auto_entry(content="auto")
        for e in [good, retracted, superseded, auto]:
            ledger.add_entry(e)
        result = ledger.active_human_entries()
        assert result == [good]


# ---------------------------------------------------------------------------
# FeedbackLedger - active_auto_entries
# ---------------------------------------------------------------------------

class TestActiveAutoEntries:
    def test_includes_normal_auto_entry(self):
        ledger = FeedbackLedger()
        entry = make_auto_entry()
        ledger.add_entry(entry)
        assert entry in ledger.active_auto_entries()

    def test_excludes_retracted_auto_entry(self):
        ledger = FeedbackLedger()
        entry = make_auto_entry(retracted=True)
        ledger.add_entry(entry)
        assert ledger.active_auto_entries() == []

    def test_includes_superseded_auto_entry(self):
        """active_auto_entries does NOT filter superseded — FeedbackMerger handles conflicts."""
        ledger = FeedbackLedger()
        entry = make_auto_entry(superseded=True)
        ledger.add_entry(entry)
        assert entry in ledger.active_auto_entries()

    def test_excludes_human_entries(self):
        ledger = FeedbackLedger()
        ledger.add_entry(make_human_entry())
        assert ledger.active_auto_entries() == []

    def test_mixed_entries(self):
        ledger = FeedbackLedger()
        active_auto = make_auto_entry(content="active")
        retracted_auto = make_auto_entry(content="retracted", retracted=True)
        superseded_auto = make_auto_entry(content="superseded", superseded=True)
        human = make_human_entry(content="human")
        for e in [active_auto, retracted_auto, superseded_auto, human]:
            ledger.add_entry(e)
        result = ledger.active_auto_entries()
        assert active_auto in result
        assert superseded_auto in result  # included — not filtered here
        assert retracted_auto not in result
        assert human not in result


# ---------------------------------------------------------------------------
# FeedbackLedger - retract
# ---------------------------------------------------------------------------

class TestRetract:
    def test_retract_marks_entry_retracted(self):
        ledger = FeedbackLedger()
        entry = make_human_entry()
        ledger.add_entry(entry)
        result = ledger.retract(entry.id)
        assert result is True
        assert ledger.entries[0].retracted is True

    def test_retract_returns_false_for_nonexistent(self):
        ledger = FeedbackLedger()
        result = ledger.retract("deadbeef")
        assert result is False

    def test_retract_does_not_affect_other_entries(self):
        ledger = FeedbackLedger()
        e1 = make_human_entry(content="one")
        e2 = make_human_entry(content="two")
        ledger.add_entry(e1)
        ledger.add_entry(e2)
        ledger.retract(e1.id)
        assert ledger.entries[0].retracted is True
        assert ledger.entries[1].retracted is False


# ---------------------------------------------------------------------------
# FeedbackLedger - add_entry superseding
# ---------------------------------------------------------------------------

class TestAddEntrySuperseding:
    def test_same_source_same_target_supersedes_older(self):
        ledger = FeedbackLedger()
        old = make_human_entry(content="old", target="col_A")
        new = make_human_entry(content="new", target="col_A")
        ledger.add_entry(old)
        ledger.add_entry(new)
        # old should be superseded
        assert ledger.entries[0].superseded is True
        assert ledger.entries[1].superseded is False

    def test_same_source_different_target_does_not_supersede(self):
        ledger = FeedbackLedger()
        e1 = make_human_entry(content="for A", target="col_A")
        e2 = make_human_entry(content="for B", target="col_B")
        ledger.add_entry(e1)
        ledger.add_entry(e2)
        assert ledger.entries[0].superseded is False
        assert ledger.entries[1].superseded is False

    def test_different_source_same_target_does_not_supersede(self):
        """human and auto are separate sources — no cross-source superseding."""
        ledger = FeedbackLedger()
        human = make_human_entry(content="human entry", target="col_A")
        auto = make_auto_entry(content="auto entry", target="col_A")
        ledger.add_entry(human)
        ledger.add_entry(auto)
        # human should NOT be superseded by auto
        assert ledger.entries[0].superseded is False
        assert ledger.entries[1].superseded is False

    def test_no_target_entries_not_superseded(self):
        """Entries with target=None should never be superseded by each other."""
        ledger = FeedbackLedger()
        e1 = make_human_entry(content="first no-target")
        e2 = make_human_entry(content="second no-target")
        ledger.add_entry(e1)
        ledger.add_entry(e2)
        assert ledger.entries[0].superseded is False
        assert ledger.entries[1].superseded is False

    def test_superseding_chains_correctly(self):
        """Adding 3 entries with same target: only the latest is active."""
        ledger = FeedbackLedger()
        e1 = make_human_entry(content="v1", target="col_A")
        e2 = make_human_entry(content="v2", target="col_A")
        e3 = make_human_entry(content="v3", target="col_A")
        ledger.add_entry(e1)
        ledger.add_entry(e2)
        ledger.add_entry(e3)
        assert ledger.entries[0].superseded is True
        assert ledger.entries[1].superseded is True
        assert ledger.entries[2].superseded is False
        active = ledger.active_human_entries()
        assert len(active) == 1
        assert active[0].content == "v3"


# ---------------------------------------------------------------------------
# FeedbackLedger - clear_auto_entries
# ---------------------------------------------------------------------------

class TestClearAutoEntries:
    def test_clears_all_auto_entries(self):
        ledger = FeedbackLedger()
        ledger.add_entry(make_auto_entry(content="auto1"))
        ledger.add_entry(make_auto_entry(content="auto2"))
        ledger.clear_auto_entries()
        assert all(e.source != "auto" for e in ledger.entries)

    def test_preserves_human_entries(self):
        ledger = FeedbackLedger()
        human = make_human_entry(content="keep me")
        ledger.add_entry(human)
        ledger.add_entry(make_auto_entry(content="remove me"))
        ledger.clear_auto_entries()
        assert len(ledger.entries) == 1
        assert ledger.entries[0].content == "keep me"

    def test_clear_auto_is_idempotent(self):
        ledger = FeedbackLedger()
        ledger.add_entry(make_human_entry())
        ledger.clear_auto_entries()
        ledger.clear_auto_entries()
        assert len(ledger.entries) == 1


# ---------------------------------------------------------------------------
# FeedbackLedger - JSON serialization
# ---------------------------------------------------------------------------

class TestFeedbackLedgerSerialization:
    def test_json_roundtrip_empty(self):
        ledger = FeedbackLedger()
        json_str = ledger.model_dump_json()
        restored = FeedbackLedger.model_validate_json(json_str)
        assert restored.entries == []

    def test_json_roundtrip_with_entries(self):
        ledger = FeedbackLedger()
        ledger.add_entry(make_human_entry(content="human", target="col_X"))
        ledger.add_entry(make_auto_entry(content="auto"))
        json_str = ledger.model_dump_json()
        restored = FeedbackLedger.model_validate_json(json_str)
        assert len(restored.entries) == 2
        assert restored.entries[0].source == "human"
        assert restored.entries[1].source == "auto"
        assert restored.entries[0].content == "human"
        assert restored.entries[0].target == "col_X"


# ---------------------------------------------------------------------------
# FeedbackEntryInput
# ---------------------------------------------------------------------------

class TestFeedbackEntryInput:
    def test_basic_construction(self):
        inp = FeedbackEntryInput(
            type=FeedbackType.SET_MAPPING,
            content="map col A",
            target="col_A",
        )
        assert inp.type == FeedbackType.SET_MAPPING
        assert inp.content == "map col A"
        assert inp.target == "col_A"

    def test_target_optional(self):
        inp = FeedbackEntryInput(
            type=FeedbackType.FREE_TEXT,
            content="general feedback",
        )
        assert inp.target is None

    def test_from_legacy_column_mapping(self):
        inp = FeedbackEntryInput.from_legacy("Column mapping", "fix A")
        assert inp.type == FeedbackType.SET_MAPPING

    def test_from_legacy_property_names(self):
        inp = FeedbackEntryInput.from_legacy("Property names", "fix prop")
        assert inp.type == FeedbackType.SET_MAPPING

    def test_from_legacy_value_formatting(self):
        inp = FeedbackEntryInput.from_legacy("Value formatting", "fix fmt")
        assert inp.type == FeedbackType.APPLY_RULE

    def test_from_legacy_missing_mappings(self):
        inp = FeedbackEntryInput.from_legacy("Missing mappings", "missing")
        assert inp.type == FeedbackType.SET_MAPPING

    def test_from_legacy_incorrect_mappings(self):
        inp = FeedbackEntryInput.from_legacy("Incorrect mappings", "wrong")
        assert inp.type == FeedbackType.SET_MAPPING

    def test_from_legacy_structural_issue(self):
        inp = FeedbackEntryInput.from_legacy("Structural issue", "bad structure")
        assert inp.type == FeedbackType.APPLY_RULE

    def test_from_legacy_other(self):
        inp = FeedbackEntryInput.from_legacy("Other", "misc")
        assert inp.type == FeedbackType.FREE_TEXT

    def test_from_legacy_unknown_falls_back_to_free_text(self):
        inp = FeedbackEntryInput.from_legacy("Unknown category", "unknown")
        assert inp.type == FeedbackType.FREE_TEXT

    def test_from_legacy_preserves_content(self):
        inp = FeedbackEntryInput.from_legacy("Column mapping", "my feedback text")
        assert inp.content == "my feedback text"
