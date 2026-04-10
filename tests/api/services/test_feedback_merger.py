"""Tests for FeedbackMerger service (TDD — written before implementation)."""
from __future__ import annotations

import pytest

from src.api.models.feedback import FeedbackEntry, FeedbackLedger, FeedbackType
from src.api.services.feedback_merger import FeedbackMerger


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _human_entry(
    feedback_type: FeedbackType,
    content: str,
    target: str | None = None,
    round: int = 1,
) -> FeedbackEntry:
    return FeedbackEntry(
        type=feedback_type,
        round=round,
        source="human",
        content=content,
        target=target,
    )


def _auto_entry(
    content: str,
    target: str | None = None,
    round: int = 1,
) -> FeedbackEntry:
    return FeedbackEntry(
        type=FeedbackType.AUTO,
        round=round,
        source="auto",
        content=content,
        target=target,
    )


def _ledger(*entries: FeedbackEntry) -> FeedbackLedger:
    ledger = FeedbackLedger()
    for e in entries:
        ledger.entries.append(e)
    return ledger


# ---------------------------------------------------------------------------
# render_separate — empty ledger
# ---------------------------------------------------------------------------

class TestRenderSeparateEmpty:
    def test_empty_ledger_returns_empty_strings(self):
        ledger = FeedbackLedger()
        human_text, auto_text = FeedbackMerger.render_separate(ledger)
        assert human_text == ""
        assert auto_text == ""


# ---------------------------------------------------------------------------
# render_separate — human-only entries
# ---------------------------------------------------------------------------

class TestRenderSeparateHumanOnly:
    def test_pin_row_format(self):
        entry = _human_entry(FeedbackType.PIN_ROW, "row content here", target="col_A")
        human_text, auto_text = FeedbackMerger.render_separate(_ledger(entry))
        assert "PINNED ROW col_A" in human_text
        assert "DO NOT MODIFY THIS ROW" in human_text
        assert "row content here" in human_text
        assert auto_text == ""

    def test_set_mapping_format(self):
        entry = _human_entry(FeedbackType.SET_MAPPING, "statVar123", target="col_B")
        human_text, auto_text = FeedbackMerger.render_separate(_ledger(entry))
        assert "REQUIRED MAPPING" in human_text
        assert "`col_B`" in human_text
        assert "`statVar123`" in human_text
        assert auto_text == ""

    def test_apply_rule_format(self):
        entry = _human_entry(FeedbackType.APPLY_RULE, "Always use ISO dates")
        human_text, auto_text = FeedbackMerger.render_separate(_ledger(entry))
        assert "RULE:" in human_text
        assert "Always use ISO dates" in human_text
        assert auto_text == ""

    def test_free_text_format(self):
        entry = _human_entry(FeedbackType.FREE_TEXT, "Please fix the unit column")
        human_text, auto_text = FeedbackMerger.render_separate(_ledger(entry))
        assert "Please fix the unit column" in human_text
        assert auto_text == ""

    def test_multiple_human_entries_all_rendered(self):
        entries = [
            _human_entry(FeedbackType.APPLY_RULE, "Use FIPS codes", target="state"),
            _human_entry(FeedbackType.FREE_TEXT, "Check header row"),
        ]
        human_text, _ = FeedbackMerger.render_separate(_ledger(*entries))
        assert "RULE:" in human_text
        assert "Use FIPS codes" in human_text
        assert "Check header row" in human_text

    def test_retracted_human_entry_excluded(self):
        entry = _human_entry(FeedbackType.FREE_TEXT, "Ignore this", target="col_X")
        entry.retracted = True
        human_text, _ = FeedbackMerger.render_separate(_ledger(entry))
        assert "Ignore this" not in human_text

    def test_superseded_human_entry_excluded(self):
        entry = _human_entry(FeedbackType.FREE_TEXT, "Old instruction", target="col_Y")
        entry.superseded = True
        human_text, _ = FeedbackMerger.render_separate(_ledger(entry))
        assert "Old instruction" not in human_text


# ---------------------------------------------------------------------------
# render_separate — auto-only entries
# ---------------------------------------------------------------------------

class TestRenderSeparateAutoOnly:
    def test_auto_entry_rendered_in_auto_text(self):
        entry = _auto_entry("Auto feedback: fix row 3")
        human_text, auto_text = FeedbackMerger.render_separate(_ledger(entry))
        assert human_text == ""
        assert "Auto feedback: fix row 3" in auto_text

    def test_retracted_auto_entry_excluded(self):
        entry = _auto_entry("This was retracted")
        entry.retracted = True
        _, auto_text = FeedbackMerger.render_separate(_ledger(entry))
        assert "This was retracted" not in auto_text

    def test_auto_entry_without_target_kept(self):
        entry = _auto_entry("General auto feedback", target=None)
        _, auto_text = FeedbackMerger.render_separate(_ledger(entry))
        assert "General auto feedback" in auto_text


# ---------------------------------------------------------------------------
# render_separate — conflict filtering
# ---------------------------------------------------------------------------

class TestConflictFiltering:
    def test_auto_entry_filtered_when_same_target_as_human(self):
        human = _human_entry(FeedbackType.SET_MAPPING, "statVar123", target="col_A")
        auto = _auto_entry("Auto suggestion for col_A", target="col_A")
        human_text, auto_text = FeedbackMerger.render_separate(_ledger(human, auto))
        assert "Auto suggestion for col_A" not in auto_text
        assert "REQUIRED MAPPING" in human_text

    def test_auto_entry_kept_when_different_target(self):
        human = _human_entry(FeedbackType.SET_MAPPING, "statVar123", target="col_A")
        auto = _auto_entry("Auto suggestion for col_B", target="col_B")
        human_text, auto_text = FeedbackMerger.render_separate(_ledger(human, auto))
        assert "Auto suggestion for col_B" in auto_text

    def test_auto_entry_without_target_never_filtered(self):
        human = _human_entry(FeedbackType.SET_MAPPING, "statVar123", target="col_A")
        auto = _auto_entry("Global auto note", target=None)
        _, auto_text = FeedbackMerger.render_separate(_ledger(human, auto))
        assert "Global auto note" in auto_text

    def test_multiple_human_targets_filter_multiple_auto(self):
        human1 = _human_entry(FeedbackType.SET_MAPPING, "sv1", target="col_A")
        human2 = _human_entry(FeedbackType.SET_MAPPING, "sv2", target="col_B")
        auto_filtered1 = _auto_entry("Auto for col_A", target="col_A")
        auto_filtered2 = _auto_entry("Auto for col_B", target="col_B")
        auto_kept = _auto_entry("Auto for col_C", target="col_C")
        _, auto_text = FeedbackMerger.render_separate(
            _ledger(human1, human2, auto_filtered1, auto_filtered2, auto_kept)
        )
        assert "Auto for col_A" not in auto_text
        assert "Auto for col_B" not in auto_text
        assert "Auto for col_C" in auto_text

    def test_retracted_human_does_not_block_auto(self):
        """A retracted human entry should NOT contribute to conflict filtering."""
        human = _human_entry(FeedbackType.SET_MAPPING, "sv1", target="col_A")
        human.retracted = True
        auto = _auto_entry("Auto for col_A", target="col_A")
        _, auto_text = FeedbackMerger.render_separate(_ledger(human, auto))
        # Human is retracted, so its target should not block the auto entry
        assert "Auto for col_A" in auto_text


# ---------------------------------------------------------------------------
# merge() — combined output
# ---------------------------------------------------------------------------

class TestMerge:
    def test_merge_empty_ledger_returns_empty_string(self):
        assert FeedbackMerger.merge(FeedbackLedger()) == ""

    def test_merge_combines_human_and_auto(self):
        human = _human_entry(FeedbackType.FREE_TEXT, "Human note")
        auto = _auto_entry("Auto note", target="other_col")
        result = FeedbackMerger.merge(_ledger(human, auto))
        assert "Human note" in result
        assert "Auto note" in result

    def test_merge_human_only(self):
        human = _human_entry(FeedbackType.APPLY_RULE, "ISO dates only")
        result = FeedbackMerger.merge(_ledger(human))
        assert "RULE:" in result
        assert "ISO dates only" in result

    def test_merge_auto_only(self):
        auto = _auto_entry("Fix missing values")
        result = FeedbackMerger.merge(_ledger(auto))
        assert "Fix missing values" in result

    def test_merge_respects_conflict_filtering(self):
        """Auto entries targeting same column as human should be excluded from merge."""
        human = _human_entry(FeedbackType.SET_MAPPING, "sv1", target="col_A")
        auto_conflict = _auto_entry("Auto for col_A", target="col_A")
        auto_other = _auto_entry("Auto for col_B", target="col_B")
        result = FeedbackMerger.merge(_ledger(human, auto_conflict, auto_other))
        assert "Auto for col_A" not in result
        assert "Auto for col_B" in result

    def test_merge_returns_string_type(self):
        result = FeedbackMerger.merge(FeedbackLedger())
        assert isinstance(result, str)


# ---------------------------------------------------------------------------
# render_human_summary()
# ---------------------------------------------------------------------------

class TestRenderHumanSummary:
    def test_empty_ledger_returns_no_instructions_message(self):
        summary = FeedbackMerger.render_human_summary(FeedbackLedger())
        assert summary == "(No human instructions provided)"

    def test_summary_includes_type_and_content(self):
        entry = _human_entry(FeedbackType.APPLY_RULE, "Use FIPS codes", target="state")
        summary = FeedbackMerger.render_human_summary(_ledger(entry))
        assert "apply_rule" in summary
        assert "Use FIPS codes" in summary

    def test_summary_includes_target_when_present(self):
        entry = _human_entry(FeedbackType.SET_MAPPING, "sv1", target="col_A")
        summary = FeedbackMerger.render_human_summary(_ledger(entry))
        assert "col_A" in summary

    def test_summary_format_uses_dash_prefix(self):
        entry = _human_entry(FeedbackType.FREE_TEXT, "Some note")
        summary = FeedbackMerger.render_human_summary(_ledger(entry))
        assert summary.startswith("- ")

    def test_summary_multiple_entries_one_per_line(self):
        entries = [
            _human_entry(FeedbackType.FREE_TEXT, "Note one"),
            _human_entry(FeedbackType.APPLY_RULE, "Rule two"),
        ]
        summary = FeedbackMerger.render_human_summary(_ledger(*entries))
        lines = [l for l in summary.splitlines() if l.strip()]
        assert len(lines) == 2

    def test_summary_excludes_retracted_entries(self):
        entry = _human_entry(FeedbackType.FREE_TEXT, "Retracted note")
        entry.retracted = True
        summary = FeedbackMerger.render_human_summary(_ledger(entry))
        assert summary == "(No human instructions provided)"

    def test_summary_excludes_auto_entries(self):
        auto = _auto_entry("Auto note")
        summary = FeedbackMerger.render_human_summary(_ledger(auto))
        assert summary == "(No human instructions provided)"
