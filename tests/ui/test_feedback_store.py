"""Tests for src.ui.services.feedback_store."""
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# Mock streamlit before any src.ui imports
_mock_st = MagicMock()
_mock_st.session_state = {}
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.services.feedback_store import save_feedback, load_feedback_history


# ---------------------------------------------------------------------------
# save_feedback
# ---------------------------------------------------------------------------
class TestSaveFeedback:

    def test_creates_feedback_dir(self, tmp_path):
        entry = {"text": "looks good"}
        path = save_feedback(entry, tmp_path)
        assert (tmp_path / "feedback").is_dir()
        assert path.exists()

    def test_auto_numbers_files(self, tmp_path):
        p1 = save_feedback({"text": "first"}, tmp_path)
        p2 = save_feedback({"text": "second"}, tmp_path)
        assert p1.name == "feedback_001.json"
        assert p2.name == "feedback_002.json"

    def test_sets_default_timestamp(self, tmp_path):
        entry = {"text": "hello"}
        path = save_feedback(entry, tmp_path)
        data = json.loads(path.read_text())
        assert "timestamp" in data

    def test_preserves_existing_timestamp(self, tmp_path):
        entry = {"text": "hello", "timestamp": "2026-01-01T00:00:00"}
        path = save_feedback(entry, tmp_path)
        data = json.loads(path.read_text())
        assert data["timestamp"] == "2026-01-01T00:00:00"

    def test_sets_feedback_round(self, tmp_path):
        entry = {"text": "hello"}
        path = save_feedback(entry, tmp_path)
        data = json.loads(path.read_text())
        assert data["feedback_round"] == 1

    def test_valid_json_output(self, tmp_path):
        entry = {"text": "data", "score": 0.95, "tags": ["a", "b"]}
        path = save_feedback(entry, tmp_path)
        data = json.loads(path.read_text())
        assert data["text"] == "data"
        assert data["score"] == 0.95
        assert data["tags"] == ["a", "b"]


# ---------------------------------------------------------------------------
# load_feedback_history
# ---------------------------------------------------------------------------
class TestLoadFeedbackHistory:

    def test_empty_when_no_dir(self, tmp_path):
        assert load_feedback_history(tmp_path) == []

    def test_loads_in_sorted_order(self, tmp_path):
        fb_dir = tmp_path / "feedback"
        fb_dir.mkdir()
        (fb_dir / "feedback_002.json").write_text(json.dumps({"round": 2}))
        (fb_dir / "feedback_001.json").write_text(json.dumps({"round": 1}))

        entries = load_feedback_history(tmp_path)
        assert len(entries) == 2
        assert entries[0]["round"] == 1
        assert entries[1]["round"] == 2

    def test_skips_invalid_json(self, tmp_path):
        fb_dir = tmp_path / "feedback"
        fb_dir.mkdir()
        (fb_dir / "feedback_001.json").write_text("{valid: true}")  # invalid JSON
        (fb_dir / "feedback_002.json").write_text(json.dumps({"ok": True}))

        entries = load_feedback_history(tmp_path)
        assert len(entries) == 1
        assert entries[0]["ok"] is True

    def test_roundtrip(self, tmp_path):
        save_feedback({"text": "alpha"}, tmp_path)
        save_feedback({"text": "beta"}, tmp_path)

        entries = load_feedback_history(tmp_path)
        assert len(entries) == 2
        assert entries[0]["text"] == "alpha"
        assert entries[1]["text"] == "beta"
