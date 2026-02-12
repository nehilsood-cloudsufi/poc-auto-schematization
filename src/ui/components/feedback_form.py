"""Structured feedback form with edited file re-use."""
import logging
from pathlib import Path
from typing import Optional

import pandas as pd
import streamlit as st

from src.ui.services.feedback_store import save_feedback
from src.ui.services.file_manager import (
    get_latest_version,
    save_edited_files,
    save_run_manifest,
    snapshot_version,
)

logger = logging.getLogger(__name__)


def render_feedback_form(output_dir: Path):
    """Render feedback form and handle re-run with feedback.

    Args:
        output_dir: Dataset-specific output directory.

    Returns:
        True if a re-run was triggered, False otherwise.
    """
    st.header("Feedback & Re-run")

    result = st.session_state.get("pipeline_result", {})

    # Display previous run summary
    retry_count = result.get("retry_count", 0)
    exit_reason = result.get("exit_reason", "unknown")
    quality_metrics = result.get("quality_metrics", {})
    heuristic_score = 0
    if isinstance(quality_metrics, dict):
        heuristic_score = quality_metrics.get("heuristic_score", 0)

    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Attempts", retry_count + 1)
    with col2:
        st.metric("Heuristic Score", f"{heuristic_score:.1f}/100")
    with col3:
        st.metric("Exit Reason", exit_reason)

    st.divider()

    # Feedback form
    feedback_text = st.text_area(
        "What should be changed?",
        height=200,
        placeholder="Describe what needs to be fixed or improved in the PVMAP...",
        key="feedback_text",
    )

    col1, col2 = st.columns(2)
    with col1:
        category = st.selectbox(
            "Category",
            [
                "Column mapping",
                "Property names",
                "Value formatting",
                "Missing mappings",
                "Incorrect mappings",
                "Structural issue",
                "Other",
            ],
            key="feedback_category",
        )
    with col2:
        severity = st.slider("Severity", 1, 5, 3, key="feedback_severity")

    # Re-run button
    if st.button("Re-run with Feedback", type="primary", disabled=not feedback_text):
        logger.info(
            "Feedback submitted: category=%s, severity=%d, text=%.80s",
            category, severity, feedback_text,
        )
        return _handle_rerun(output_dir, feedback_text, category, severity, result)

    return False


def _handle_rerun(
    output_dir: Path,
    feedback_text: str,
    category: str,
    severity: int,
    result: dict,
) -> bool:
    """Snapshot current output, save feedback, and trigger re-run."""
    # Step 1: Determine current version
    current_version = get_latest_version(output_dir)
    if current_version == 0:
        current_version = 1
    next_version = current_version + 1

    # Step 2: Snapshot current output
    logger.info("Snapshotting v%d → v%d", current_version, next_version)
    snapshot_version(output_dir, current_version)

    # Step 3: Save run manifest for current version
    config = {
        "run_id": st.session_state.get("run_id", ""),
        "dataset_name": st.session_state.get("dataset_name", ""),
        "model": st.session_state.get("model", ""),
        "input_file": st.session_state.get("input_path", ""),
        "metadata_file": st.session_state.get("metadata_path", ""),
        "mcp_enabled": st.session_state.get("mcp_enabled", False),
        "prompt_version": st.session_state.get("prompt_version", "v2"),
        "use_schema_examples": st.session_state.get("use_schema_examples", True),
    }
    save_run_manifest(output_dir, current_version, config, result)

    # Step 4: Detect user edits to PVMAP
    edited_pvmap_df = _detect_edited_pvmap(output_dir)
    edited_metadata_df = _detect_edited_metadata(output_dir)
    logger.info(
        "Edited file detection: pvmap_changed=%s, metadata_changed=%s",
        edited_pvmap_df is not None, edited_metadata_df is not None,
    )

    # Step 5: Save edited files to version feedback dir
    if edited_pvmap_df is not None or edited_metadata_df is not None:
        save_edited_files(output_dir, current_version, edited_pvmap_df, edited_metadata_df)

    # Step 6: Build human feedback string
    human_feedback = _build_human_feedback(
        feedback_text, category, severity,
        edited_pvmap_df, result,
    )

    # Step 7: Save feedback JSON
    feedback_entry = {
        "run_id": st.session_state.get("run_id", ""),
        "text": feedback_text,
        "category": category,
        "severity": severity,
        "dataset_name": st.session_state.get("dataset_name", ""),
        "input_file": st.session_state.get("input_path", ""),
        "edited_pvmap": edited_pvmap_df is not None,
        "edited_metadata": edited_metadata_df is not None,
        "pipeline_metrics": {
            "attempts": result.get("retry_count", 0) + 1,
            "heuristic_score": result.get("quality_metrics", {}).get("heuristic_score", 0)
            if isinstance(result.get("quality_metrics"), dict) else 0,
            "exit_reason": result.get("exit_reason", ""),
        },
    }

    # Save to next version's feedback dir
    next_feedback_dir = output_dir / f"v{next_version}" / "feedback"
    next_feedback_dir.mkdir(parents=True, exist_ok=True)
    save_feedback(feedback_entry, output_dir / f"v{next_version}")

    # Step 8: Update session state for re-run
    logger.info(
        "Re-run triggered: human_feedback length=%d, skip_sampling=True",
        len(human_feedback),
    )
    st.session_state["human_feedback"] = human_feedback
    st.session_state["pipeline_status"] = "launching"
    st.session_state["skip_sampling"] = True  # Re-use existing samples
    st.session_state["progress_events"] = []  # Clear progress

    # Pass edited metadata path for re-run
    if edited_metadata_df is not None:
        edited_meta_path = output_dir / f"v{current_version}" / "feedback" / "edited_metadata.csv"
        st.session_state["metadata_path"] = str(edited_meta_path)
        st.session_state["use_metadata"] = True

    st.session_state["used_edited_pvmap"] = edited_pvmap_df is not None

    return True


def _detect_edited_pvmap(output_dir: Path) -> Optional[pd.DataFrame]:
    """Check if user edited the PVMAP in the data editor."""
    edited = st.session_state.get("edited_generated_pvmap.csv")
    if edited is None:
        return None

    # Compare with file on disk
    pvmap_path = output_dir / "generated_pvmap.csv"
    if not pvmap_path.exists():
        return None

    try:
        original = pd.read_csv(pvmap_path)
        if not edited.equals(original):
            return edited
    except Exception:
        pass

    return None


def _detect_edited_metadata(output_dir: Path) -> Optional[pd.DataFrame]:
    """Check if user edited the metadata config in the data editor."""
    edited = st.session_state.get("edited_output_metadata.csv")
    if edited is None:
        return None

    meta_path = output_dir / "output_metadata.csv"
    if not meta_path.exists():
        return None

    try:
        original = pd.read_csv(meta_path)
        if not edited.equals(original):
            return edited
    except Exception:
        pass

    return None


def _build_human_feedback(
    feedback_text: str,
    category: str,
    severity: int,
    edited_pvmap_df: Optional[pd.DataFrame],
    result: dict,
) -> str:
    """Build the combined human feedback string for the pipeline."""
    parts = [
        f"USER FEEDBACK: {feedback_text}",
        f"CATEGORY: {category}",
        f"SEVERITY: {severity}",
    ]

    if edited_pvmap_df is not None:
        pvmap_csv = edited_pvmap_df.to_csv(index=False)
        parts.append("")
        parts.append(
            "The user has corrected the PVMAP. Here is their edited version "
            "- incorporate these corrections:"
        )
        parts.append(f"```csv\n{pvmap_csv}```")

    # Add previous run context
    retry_count = result.get("retry_count", 0)
    exit_reason = result.get("exit_reason", "unknown")
    quality_metrics = result.get("quality_metrics", {})
    heuristic = 0
    if isinstance(quality_metrics, dict):
        heuristic = quality_metrics.get("heuristic_score", 0)

    parts.append("")
    parts.append(
        f"Previous run: {retry_count + 1} attempts, "
        f"heuristic score {heuristic:.1f}/100, "
        f"exit reason: {exit_reason}"
    )

    return "\n".join(parts)
