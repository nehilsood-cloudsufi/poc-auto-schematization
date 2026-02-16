"""Developer feedback form — bugs, suggestions, UX issues.

Separate from the PVMAP feedback/re-run form. Sends feedback to a
Google Sheet (if configured) and always saves a local JSON fallback.
"""
import logging
from pathlib import Path

import streamlit as st

from src.ui.services.feedback_store import save_feedback
from src.ui.services.google_sheets_service import (
    append_feedback_to_sheet,
    is_sheets_configured,
)

logger = logging.getLogger(__name__)

_CATEGORIES = [
    "Bug Report",
    "Feature Suggestion",
    "UX Issue",
    "Documentation",
    "Performance",
    "Other",
]


def render_developer_feedback() -> None:
    """Render the developer feedback section."""
    st.subheader("Developer Feedback")

    if not is_sheets_configured():
        st.info(
            "Google Sheets integration is not configured. "
            "Feedback will be saved locally only. "
            "Set the `GOOGLE_SHEET_ID` environment variable to enable.",
            icon=":material/info:",
        )

    with st.form("developer_feedback_form", clear_on_submit=True):
        feedback_text = st.text_area(
            "Describe the issue or suggestion",
            height=100,
            placeholder="e.g. The progress bar got stuck at 60% for 2 minutes...",
        )
        category = st.selectbox("Category", _CATEGORIES)

        submitted = st.form_submit_button(
            ":material/send: Submit Feedback",
            disabled=False,
        )

    if submitted:
        if not feedback_text or not feedback_text.strip():
            st.warning("Please enter feedback text before submitting.")
            return
        _handle_submission(feedback_text.strip(), category)


def _handle_submission(text: str, category: str) -> None:
    """Send feedback to Sheets and save locally."""
    run_id = st.session_state.get("run_id", "")
    run_dir = st.session_state.get("run_dir", "")
    dataset_name = st.session_state.get("dataset_name", "")

    log_path = f"{run_dir}/logs/" if run_dir else ""

    # Always save locally
    output_dir = Path(run_dir) / "output" / dataset_name if run_dir and dataset_name else None
    _save_local(run_id, dataset_name, log_path, text, category, output_dir)

    # Attempt Sheets append
    if is_sheets_configured():
        ok = append_feedback_to_sheet(
            run_id=run_id,
            dataset_name=dataset_name,
            log_path=log_path,
            feedback_text=text,
            category=category,
        )
        if ok:
            st.success("Feedback submitted to Google Sheets. Thank you!")
        else:
            st.warning(
                "Could not reach Google Sheets — feedback saved locally.",
                icon=":material/warning:",
            )
    else:
        st.success("Feedback saved locally. Thank you!")


def _save_local(
    run_id: str,
    dataset_name: str,
    log_path: str,
    text: str,
    category: str,
    output_dir,
) -> None:
    """Persist feedback as a local JSON file via the feedback store."""
    entry = {
        "type": "developer_feedback",
        "run_id": run_id,
        "dataset_name": dataset_name,
        "log_path": log_path,
        "text": text,
        "category": category,
    }

    if output_dir and Path(output_dir).exists():
        save_feedback(entry, Path(output_dir))
        logger.info("Developer feedback saved locally to %s", output_dir)
    else:
        logger.warning(
            "No output directory available — developer feedback not persisted locally "
            "(run_dir=%s, dataset=%s)",
            run_id,
            dataset_name,
        )
