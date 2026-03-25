"""Developer feedback form — bugs, suggestions, UX issues.

Separate from the PVMAP feedback/re-run form. Sends feedback to a
Google Sheet (if configured) and always saves a local JSON fallback.
"""
import logging
from pathlib import Path

import streamlit as st

from src.ui.config import CLOUD_RUN, GCS_BUCKET
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
        )

    with st.form("developer_feedback_form", clear_on_submit=True):
        feedback_text = st.text_area(
            "Describe the issue or suggestion",
            height=100,
            placeholder="e.g. The progress bar got stuck at 60% for 2 minutes...",
        )
        category = st.selectbox("Category", _CATEGORIES)

        submitted = st.form_submit_button(
            "Submit Feedback",
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

    # Gather pipeline context for traceability
    result = st.session_state.get("pipeline_result", {})
    pipeline_status = st.session_state.get("pipeline_status", "")
    quality_metrics = result.get("quality_metrics", {}) if isinstance(result, dict) else {}
    heuristic_score = quality_metrics.get("heuristic_score", "") if isinstance(quality_metrics, dict) else ""
    exit_reason = result.get("exit_reason", "") if isinstance(result, dict) else ""
    retry_count = result.get("retry_count", "") if isinstance(result, dict) else ""
    attempts = str(int(retry_count) + 1) if retry_count != "" else ""
    model = st.session_state.get("model", "")
    mcp_enabled = str(st.session_state.get("mcp_enabled", ""))

    # Always save locally
    output_dir = Path(run_dir) / "output" / dataset_name if run_dir and dataset_name else None
    _save_local(run_id, dataset_name, text, category, pipeline_status, output_dir)

    # Build GCS output link
    gcs_output_link = ""
    if CLOUD_RUN and GCS_BUCKET and run_id and dataset_name:
        gcs_output_link = (
            f"https://console.cloud.google.com/storage/browser/"
            f"{GCS_BUCKET}/{run_id}/output/{dataset_name}"
        )

    # Attempt Sheets append
    if is_sheets_configured():
        ok = append_feedback_to_sheet(
            run_id=run_id,
            dataset_name=dataset_name,
            feedback_text=text,
            category=category,
            pipeline_status=pipeline_status,
            quality_score=str(heuristic_score),
            exit_reason=str(exit_reason),
            attempts=attempts,
            model=model,
            mcp_enabled=mcp_enabled,
            gcs_output_link=gcs_output_link,
        )
        if ok:
            st.success("Feedback submitted to Google Sheets. Thank you!")
        else:
            st.warning("Could not reach Google Sheets — feedback saved locally.")
    else:
        st.success("Feedback saved locally. Thank you!")


def _save_local(
    run_id: str,
    dataset_name: str,
    text: str,
    category: str,
    pipeline_status: str,
    output_dir,
) -> None:
    """Persist feedback as a local JSON file via the feedback store."""
    entry = {
        "type": "developer_feedback",
        "run_id": run_id,
        "dataset_name": dataset_name,
        "pipeline_status": pipeline_status,
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
