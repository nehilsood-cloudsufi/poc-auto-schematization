"""Tests for Google Sheets feedback service."""
import os
from unittest.mock import MagicMock, patch

import pytest

from src.ui.services.google_sheets_service import (
    HEADER_ROW,
    _ensure_header_row,
    append_feedback_to_sheet,
    get_sheet_id,
    is_sheets_configured,
)


# ── get_sheet_id / is_sheets_configured ─────────────────────────────


class TestConfiguration:
    def test_get_sheet_id_returns_env_var(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEET_ID", "abc123")
        assert get_sheet_id() == "abc123"

    def test_get_sheet_id_returns_none_when_unset(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
        assert get_sheet_id() is None

    def test_is_sheets_configured_true(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEET_ID", "abc123")
        assert is_sheets_configured() is True

    def test_is_sheets_configured_false(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
        assert is_sheets_configured() is False

    def test_is_sheets_configured_empty_string(self, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEET_ID", "")
        assert is_sheets_configured() is False


# ── _ensure_header_row ──────────────────────────────────────────────


class TestEnsureHeaderRow:
    def test_writes_header_when_empty(self):
        ws = MagicMock()
        ws.row_values.return_value = []

        _ensure_header_row(ws)

        ws.update.assert_called_once_with("A1", [HEADER_ROW])

    def test_skips_when_header_exists(self):
        ws = MagicMock()
        ws.row_values.return_value = HEADER_ROW

        _ensure_header_row(ws)

        ws.update.assert_not_called()


# ── append_feedback_to_sheet ────────────────────────────────────────


class TestAppendFeedback:
    def test_returns_false_when_not_configured(self, monkeypatch):
        monkeypatch.delenv("GOOGLE_SHEET_ID", raising=False)
        result = append_feedback_to_sheet(
            run_id="r1",
            dataset_name="ds",
            log_path="/tmp/logs/",
            feedback_text="bug found",
            category="Bug Report",
        )
        assert result is False

    @patch("src.ui.services.google_sheets_service._get_gspread_client")
    def test_appends_row_on_success(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet123")

        ws = MagicMock()
        ws.row_values.return_value = HEADER_ROW  # header already exists
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.sheet1 = ws
        mock_client.return_value.open_by_key.return_value = mock_spreadsheet

        result = append_feedback_to_sheet(
            run_id="run-42",
            dataset_name="my_dataset",
            log_path="/runs/42/logs/",
            feedback_text="The progress bar is stuck",
            category="UX Issue",
        )

        assert result is True
        ws.append_row.assert_called_once()
        row = ws.append_row.call_args[0][0]
        assert row[0] == "run-42"
        assert row[1] == "my_dataset"
        assert row[2] == "/runs/42/logs/"
        assert row[3] == "The progress bar is stuck"
        assert row[4] == "UX Issue"
        # row[5] is timestamp — just check it's a non-empty string
        assert len(row[5]) > 0

    @patch("src.ui.services.google_sheets_service._get_gspread_client")
    def test_returns_false_on_auth_failure(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet123")
        mock_client.side_effect = Exception("auth failed")

        result = append_feedback_to_sheet(
            run_id="r1",
            dataset_name="ds",
            log_path="/tmp/",
            feedback_text="oops",
            category="Bug Report",
        )
        assert result is False

    @patch("src.ui.services.google_sheets_service._get_gspread_client")
    def test_returns_false_on_append_failure(self, mock_client, monkeypatch):
        monkeypatch.setenv("GOOGLE_SHEET_ID", "sheet123")

        ws = MagicMock()
        ws.row_values.return_value = HEADER_ROW
        ws.append_row.side_effect = Exception("network error")
        mock_spreadsheet = MagicMock()
        mock_spreadsheet.sheet1 = ws
        mock_client.return_value.open_by_key.return_value = mock_spreadsheet

        result = append_feedback_to_sheet(
            run_id="r1",
            dataset_name="ds",
            log_path="/tmp/",
            feedback_text="oops",
            category="Bug Report",
        )
        assert result is False
