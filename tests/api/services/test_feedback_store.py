"""Tests for feedback_store ledger persistence functions."""
from __future__ import annotations

import json
import pytest
from pathlib import Path

from src.api.models.feedback import FeedbackEntry, FeedbackLedger, FeedbackType
from src.api.services.feedback_store import (
    load_feedback_history,
    load_ledger_from_disk,
    save_feedback,
    save_ledger_to_disk,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_ledger(*contents: str) -> FeedbackLedger:
    """Build a FeedbackLedger with one FREE_TEXT human entry per content string."""
    ledger = FeedbackLedger()
    for i, text in enumerate(contents, start=1):
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.FREE_TEXT,
            round=i,
            source="human",
            content=text,
        ))
    return ledger


# ---------------------------------------------------------------------------
# save_ledger_to_disk
# ---------------------------------------------------------------------------

class TestSaveLedgerToDisk:
    def test_creates_file_in_output_dir(self, tmp_path):
        ledger = _make_ledger("Fix unit column")
        path = save_ledger_to_disk(ledger, tmp_path)
        assert path == tmp_path / "feedback_ledger.json"
        assert path.exists()

    def test_file_is_valid_json(self, tmp_path):
        ledger = _make_ledger("entry one")
        save_ledger_to_disk(ledger, tmp_path)
        data = json.loads((tmp_path / "feedback_ledger.json").read_text())
        assert "entries" in data

    def test_returns_path_object(self, tmp_path):
        ledger = FeedbackLedger()
        result = save_ledger_to_disk(ledger, tmp_path)
        assert isinstance(result, Path)

    def test_overwrites_previous_ledger(self, tmp_path):
        ledger_v1 = _make_ledger("first entry")
        save_ledger_to_disk(ledger_v1, tmp_path)

        ledger_v2 = _make_ledger("second entry", "third entry")
        save_ledger_to_disk(ledger_v2, tmp_path)

        loaded = FeedbackLedger.model_validate_json(
            (tmp_path / "feedback_ledger.json").read_text()
        )
        assert len(loaded.entries) == 2
        assert loaded.entries[0].content == "second entry"
        assert loaded.entries[1].content == "third entry"

    def test_empty_ledger_saved_with_empty_entries(self, tmp_path):
        ledger = FeedbackLedger()
        save_ledger_to_disk(ledger, tmp_path)
        data = json.loads((tmp_path / "feedback_ledger.json").read_text())
        assert data["entries"] == []


# ---------------------------------------------------------------------------
# load_ledger_from_disk
# ---------------------------------------------------------------------------

class TestLoadLedgerFromDisk:
    def test_roundtrip_preserves_entries(self, tmp_path):
        ledger = _make_ledger("Fix place column", "Use FIPS codes")
        save_ledger_to_disk(ledger, tmp_path)

        loaded = load_ledger_from_disk(tmp_path)
        assert len(loaded.entries) == 2
        assert loaded.entries[0].content == "Fix place column"
        assert loaded.entries[1].content == "Use FIPS codes"

    def test_roundtrip_preserves_entry_type(self, tmp_path):
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.APPLY_RULE,
            round=1,
            source="human",
            content="Always use ISO dates",
            target="date_col",
        ))
        save_ledger_to_disk(ledger, tmp_path)

        loaded = load_ledger_from_disk(tmp_path)
        entry = loaded.entries[0]
        assert entry.type == FeedbackType.APPLY_RULE
        assert entry.target == "date_col"
        assert entry.source == "human"

    def test_nonexistent_path_returns_empty_ledger(self, tmp_path):
        missing = tmp_path / "no_such_dir"
        result = load_ledger_from_disk(missing)
        assert isinstance(result, FeedbackLedger)
        assert result.entries == []

    def test_missing_file_returns_empty_ledger(self, tmp_path):
        # Directory exists but no feedback_ledger.json inside
        result = load_ledger_from_disk(tmp_path)
        assert isinstance(result, FeedbackLedger)
        assert result.entries == []

    def test_corrupt_file_returns_empty_ledger(self, tmp_path):
        (tmp_path / "feedback_ledger.json").write_text("NOT VALID JSON {{")
        result = load_ledger_from_disk(tmp_path)
        assert isinstance(result, FeedbackLedger)
        assert result.entries == []

    def test_roundtrip_auto_entry(self, tmp_path):
        ledger = FeedbackLedger()
        ledger.add_entry(FeedbackEntry(
            type=FeedbackType.AUTO,
            round=2,
            source="auto",
            content="Validation error: missing observationDate",
        ))
        save_ledger_to_disk(ledger, tmp_path)
        loaded = load_ledger_from_disk(tmp_path)
        assert loaded.entries[0].type == FeedbackType.AUTO
        assert loaded.entries[0].source == "auto"
