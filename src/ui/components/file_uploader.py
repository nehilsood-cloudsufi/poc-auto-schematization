"""File upload widget with CSV validation and preview."""
import logging
import uuid

import pandas as pd
import streamlit as st

from src.ui.config import SUPPORTED_UPLOAD_TYPES
from src.ui.services.file_manager import create_run_directory, save_uploaded_file

logger = logging.getLogger(__name__)


def render_file_upload():
    """Render file upload section. Returns True if pipeline should be launched."""
    st.subheader("Upload Data")

    col1, col2 = st.columns(2)

    with col1:
        input_csv = st.file_uploader(
            "Input CSV (required)",
            type=SUPPORTED_UPLOAD_TYPES,
            key="input_csv_uploader",
        )

    with col2:
        metadata_csv = st.file_uploader(
            "Metadata CSV (optional)",
            type=SUPPORTED_UPLOAD_TYPES,
            key="metadata_csv_uploader",
        )

    # Preview uploaded file
    if input_csv is not None:
        logger.info("File uploaded: %s (%d bytes)", input_csv.name, input_csv.size)
        try:
            df = pd.read_csv(input_csv)
            input_csv.seek(0)  # Reset after read

            with st.expander("Data Preview", expanded=True):
                st.dataframe(df.head(10), use_container_width=True)
                st.caption(f"{len(df)} rows x {len(df.columns)} columns")
            logger.info("CSV validated: %d rows x %d columns", len(df), len(df.columns))

            if len(df) == 0:
                logger.warning("Uploaded CSV has no data rows")
                st.error("Uploaded CSV has no data rows.")
                return False
        except Exception as e:
            logger.error("CSV validation failed: %s", e)
            st.error(f"Could not read CSV: {e}")
            return False

    # Dataset name + launch on one row
    default_name = ""
    if input_csv:
        default_name = input_csv.name.replace(".csv", "").replace(" ", "_")

    name_col, btn_col = st.columns([3, 1])
    with name_col:
        dataset_name = st.text_input(
            "Dataset name",
            value=default_name,
            help="Used for output directory naming",
            label_visibility="collapsed",
            placeholder="Dataset name (required)",
        )
    with btn_col:
        launch = st.button(
            ":material/play_arrow: Generate PVMAP",
            type="primary",
            disabled=input_csv is None,
            use_container_width=True,
        )

    if launch:
        if not dataset_name:
            st.error("Please enter a dataset name.")
            return False

        # Create run directory and save files
        run_id = uuid.uuid4().hex[:12]
        logger.info("Generated run_id=%s for dataset=%s", run_id, dataset_name)
        run_dir = create_run_directory(run_id)

        input_path = save_uploaded_file(
            input_csv, run_dir / "input", "input.csv"
        )

        metadata_path = None
        if metadata_csv is not None:
            metadata_path = save_uploaded_file(
                metadata_csv, run_dir / "input", "input_metadata.csv"
            )

        # Store in session state for pipeline launch
        st.session_state["run_id"] = run_id
        st.session_state["run_dir"] = str(run_dir)
        st.session_state["dataset_name"] = dataset_name
        st.session_state["input_path"] = str(input_path)
        st.session_state["metadata_path"] = str(metadata_path) if metadata_path else None
        st.session_state["pipeline_status"] = "launching"

        return True

    return False
