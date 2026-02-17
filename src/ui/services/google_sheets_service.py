"""Google Sheets integration for developer feedback.

Appends feedback rows to a configured Google Sheet. Works with:
- Cloud Run Workload Identity (google.auth.default)
- Local dev via GOOGLE_APPLICATION_CREDENTIALS
- Gracefully degrades when unconfigured (returns False, never raises)
"""
import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

# Load .env so GOOGLE_SHEET_ID is available even when run via Streamlit
load_dotenv(Path(__file__).parent.parent.parent.parent / ".env")

logger = logging.getLogger(__name__)

SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

HEADER_ROW = [
    "timestamp",
    "run_id",
    "dataset_name",
    "category",
    "feedback_text",
    "pipeline_status",
    "quality_score",
    "exit_reason",
    "attempts",
    "model",
    "mcp_enabled",
]


def get_sheet_id() -> Optional[str]:
    """Return the configured Google Sheet ID, or None."""
    return os.environ.get("GOOGLE_SHEET_ID")


def is_sheets_configured() -> bool:
    """Check whether Google Sheets integration is available."""
    return bool(get_sheet_id())


def _get_gspread_client():
    """Build an authorized gspread client using Application Default Credentials."""
    import google.auth
    import gspread

    creds, _ = google.auth.default(scopes=SCOPES)
    return gspread.authorize(creds)


def _ensure_header_row(worksheet) -> None:
    """Write the header row if the worksheet is empty."""
    existing = worksheet.row_values(1)
    if not existing:
        worksheet.update("A1", [HEADER_ROW])
        logger.debug("Wrote header row to worksheet")


def append_feedback_to_sheet(
    run_id: str,
    dataset_name: str,
    feedback_text: str,
    category: str,
    pipeline_status: str = "",
    quality_score: str = "",
    exit_reason: str = "",
    attempts: str = "",
    model: str = "",
    mcp_enabled: str = "",
) -> bool:
    """Append a feedback row to the configured Google Sheet.

    Returns True on success, False on any error (never raises).
    """
    sheet_id = get_sheet_id()
    if not sheet_id:
        logger.warning("GOOGLE_SHEET_ID not set — skipping Sheets append")
        return False

    try:
        client = _get_gspread_client()
        spreadsheet = client.open_by_key(sheet_id)
        worksheet = spreadsheet.sheet1

        _ensure_header_row(worksheet)

        row = [
            datetime.now().isoformat(),
            run_id,
            dataset_name,
            category,
            feedback_text,
            pipeline_status,
            quality_score,
            exit_reason,
            attempts,
            model,
            mcp_enabled,
        ]
        worksheet.append_row(row, value_input_option="RAW")
        logger.info("Appended feedback row to Google Sheet %s", sheet_id)
        return True

    except Exception:
        logger.exception("Failed to append feedback to Google Sheet")
        return False
