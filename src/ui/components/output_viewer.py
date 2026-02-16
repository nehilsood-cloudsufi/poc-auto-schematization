"""Tabbed output viewer/editor for pipeline results."""
import logging
from pathlib import Path

import pandas as pd
import streamlit as st

from src.ui.services.file_manager import get_output_files
from src.ui.services.revalidation_service import revalidate

logger = logging.getLogger(__name__)


def render_output_tabs(output_dir: Path):
    """Render tabbed output viewer with editable files.

    Args:
        output_dir: Dataset-specific output directory containing pipeline outputs.
    """
    files = get_output_files(output_dir)

    if not files:
        logger.warning("No output files found in %s", output_dir)
        st.warning("No output files found.")
        return

    logger.info("Rendering output tabs: %s", list(files.keys()))

    # Show compact result banner
    result = st.session_state.get("pipeline_result", {})
    validation_passed = result.get("validation_passed", False)
    exit_reason = result.get("exit_reason", "unknown")
    retry_count = result.get("retry_count", 0)

    banner_col, log_col = st.columns([3, 1])
    with banner_col:
        msg = f"**{retry_count + 1} attempt(s)** — {exit_reason}"
        if validation_passed:
            st.success(msg)
        else:
            st.error(msg)
    with log_col:
        raw_logs_path = output_dir / "statvar_processor_raw_logs.txt"
        if raw_logs_path.exists():
            size_mb = raw_logs_path.stat().st_size / 1_000_000
            if size_mb > 10:
                st.download_button(
                    label=f"Raw Logs ({size_mb:.0f} MB)",
                    data=_truncated_log(raw_logs_path),
                    file_name="statvar_processor_raw_logs_truncated.txt",
                    mime="text/plain",
                    use_container_width=True,
                )
            else:
                st.download_button(
                    label="Raw Logs",
                    data=raw_logs_path.read_bytes(),
                    file_name="statvar_processor_raw_logs.txt",
                    mime="text/plain",
                    use_container_width=True,
                )

    # Create tabs
    tab_names = []
    tab_files = []

    tab_order = [
        ("PVMAP", "generated_pvmap.csv"),
        ("Metadata Config", "output_metadata.csv"),
        ("Processed Data", "processed.csv"),
        ("MCF", "processed.mcf"),
        ("TMCF", "processed.tmcf"),
        ("StatVars", "processed_stat_vars.mcf"),
        ("Generation Notes", "generation_notes.md"),
        ("Metrics", "processed_counters.txt"),
        # Raw Logs excluded from tabs — too large (100MB+) for inline rendering.
        # Download link shown above tabs instead.
    ]

    for label, fname in tab_order:
        if fname in files:
            tab_names.append(label)
            tab_files.append((fname, files[fname]))

    if not tab_names:
        st.info("No output files available yet.")
        return

    tabs = st.tabs(tab_names)

    for i, (fname, fpath) in enumerate(tab_files):
        with tabs[i]:
            _render_file_tab(fname, fpath, output_dir)

    # Save & Revalidate — prominent action below tabs
    if "generated_pvmap.csv" in files:
        _, center, _ = st.columns([2, 1, 2])
        with center:
            if st.button("Save & Revalidate", type="primary", key="revalidate_btn", use_container_width=True):
                _handle_revalidation(files, output_dir)


def _handle_revalidation(files: dict, output_dir: Path):
    """Save edited files to disk and run stat_var_processor."""
    # Save edited PVMAP to disk
    pvmap_path = files["generated_pvmap.csv"]
    edited_pvmap = st.session_state.get("edited_generated_pvmap.csv")
    if edited_pvmap is not None:
        edited_pvmap.to_csv(pvmap_path, index=False)
        logger.info("Saved edited PVMAP for revalidation: %s", pvmap_path)

    # Save edited metadata to disk (if present and edited)
    metadata_path = files.get("output_metadata.csv")
    edited_metadata = st.session_state.get("edited_output_metadata.csv")
    if metadata_path and edited_metadata is not None:
        edited_metadata.to_csv(metadata_path, index=False)
        logger.info("Saved edited metadata for revalidation: %s", metadata_path)

    # Resolve input data path
    run_dir = st.session_state.get("run_dir")
    if not run_dir:
        st.error("Run directory not found in session state.")
        return

    input_data = Path(run_dir) / "input" / "input.csv"
    if not input_data.exists():
        st.error(f"Input data not found: {input_data}")
        return

    with st.spinner("Running validation..."):
        result = revalidate(
            input_data=input_data,
            pvmap_path=pvmap_path,
            metadata_path=metadata_path,
            output_dir=output_dir,
        )

    if result["success"]:
        st.success(f"Validation passed: {result['data_rows']} data rows")
    else:
        error_msg = result.get("error", "Unknown error")
        # Truncate long error messages for display
        if len(error_msg) > 500:
            error_msg = error_msg[:500] + "..."
        st.error(f"Validation failed: {error_msg}")

    st.rerun()


def _render_file_tab(fname: str, fpath: Path, output_dir: Path):
    """Render a single file tab with appropriate editor."""
    if fname.endswith(".csv"):
        _render_csv_tab(fname, fpath, output_dir)
    elif fname == "generation_notes.md":
        _render_markdown_tab(fpath)
    elif fname == "processed_counters.txt":
        _render_metrics_tab(fpath)
    elif fname == "statvar_processor_raw_logs.txt":
        _render_raw_logs_tab(fpath)
    else:
        _render_text_tab(fname, fpath, output_dir)


def _render_csv_tab(fname: str, fpath: Path, output_dir: Path):
    """Render CSV file with st.data_editor."""
    try:
        df = pd.read_csv(fpath)
        logger.debug("Loaded CSV %s: %d rows x %d cols", fname, len(df), len(df.columns))
    except Exception as e:
        logger.error("Failed to load CSV %s: %s", fname, e)
        st.error(f"Could not read {fname}: {e}")
        return

    # Use a unique key for each editor
    editor_key = f"editor_{fname}"

    st.caption(f"{len(df)} rows x {len(df.columns)} columns")

    edited_df = st.data_editor(
        df,
        num_rows="dynamic" if fname == "generated_pvmap.csv" else "fixed",
        key=editor_key,
    )

    # Store edited DataFrame in session state for feedback re-runs
    st.session_state[f"edited_{fname}"] = edited_df

    col_save, col_download, _ = st.columns([1, 1, 4])
    with col_save:
        if st.button(":material/save: Save", key=f"save_{fname}", use_container_width=True):
            try:
                edited_df.to_csv(fpath, index=False)
                logger.info("Saved edited CSV: %s", fpath)
                st.toast(f"Saved {fname}")
            except Exception as e:
                logger.error("Failed to save %s: %s", fname, e)
                st.error(f"Failed to save: {e}")
    with col_download:
        csv_data = edited_df.to_csv(index=False).encode("utf-8")
        st.download_button(
            label=":material/download: Download",
            data=csv_data,
            file_name=fname,
            mime="text/csv",
            key=f"download_{fname}",
            use_container_width=True,
        )


def _render_text_tab(fname: str, fpath: Path, output_dir: Path):
    """Render text file with st.text_area (editable)."""
    try:
        content = fpath.read_text(encoding="utf-8")
    except Exception as e:
        st.error(f"Could not read {fname}: {e}")
        return

    edited = st.text_area(
        f"Edit {fname}",
        value=content,
        height=400,
        key=f"text_{fname}",
    )

    col_save, _ = st.columns([1, 5])
    with col_save:
        if st.button(":material/save: Save", key=f"save_{fname}", use_container_width=True):
            try:
                fpath.write_text(edited, encoding="utf-8")
                logger.info("Saved edited text file: %s", fpath)
                st.toast(f"Saved {fname}")
            except Exception as e:
                logger.error("Failed to save %s: %s", fname, e)
                st.error(f"Failed to save: {e}")


def _render_markdown_tab(fpath: Path):
    """Render markdown file (read-only)."""
    try:
        content = fpath.read_text(encoding="utf-8")
        st.markdown(content)
    except Exception as e:
        st.error(f"Could not read generation notes: {e}")


def _truncated_log(fpath: Path, head: int = 5000, tail: int = 5000) -> bytes:
    """Return first + last N lines of a large log file as bytes."""
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        head_lines = []
        for i, line in enumerate(f):
            if i < head:
                head_lines.append(line)
            else:
                break
    lines = head_lines

    # Read tail lines
    tail_lines = []
    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        from collections import deque
        tail_lines = list(deque(f, maxlen=tail))

    if len(lines) + len(tail_lines) < head + tail:
        # File is small enough to fit — just return head_lines
        return "".join(lines).encode("utf-8")

    separator = f"\n\n{'=' * 60}\n... TRUNCATED ({fpath.stat().st_size / 1_000_000:.0f} MB total) ...\n{'=' * 60}\n\n"
    return ("".join(lines) + separator + "".join(tail_lines)).encode("utf-8")


def _render_raw_logs_tab(fpath: Path):
    """Render raw stat_var_processor logs (read-only).

    For large files (>10MB), shows file path instead of loading content.
    """
    size_mb = fpath.stat().st_size / 1_000_000
    if size_mb > 10:
        st.info(f"Log file too large to display ({size_mb:.0f} MB). File path: `{fpath}`")
        return

    try:
        content = fpath.read_text(encoding="utf-8")
    except Exception as e:
        st.error(f"Could not read raw logs: {e}")
        return

    st.code(content, language="text")


def _render_metrics_tab(fpath: Path):
    """Render processed_counters.txt as a key-value metrics table.

    The file can be very large (200K+ lines for big datasets) so we only
    show a summary of the top counters rather than rendering everything.
    """
    MAX_DISPLAY_ROWS = 100

    file_size = fpath.stat().st_size
    if file_size > 5_000_000:  # > 5 MB
        st.caption(f"Large metrics file ({file_size / 1_000_000:.1f} MB) — showing top {MAX_DISPLAY_ROWS} rows.")

    # Try CSV format first ("key","value")
    try:
        df = pd.read_csv(fpath, nrows=MAX_DISPLAY_ROWS)
        if len(df.columns) >= 2:
            df.columns = ["Metric", "Value"] + list(df.columns[2:])
            st.dataframe(df)
            return
    except Exception:
        pass

    # Fall back to line-based parsing (key: value or key=value)
    try:
        content = fpath.read_text(encoding="utf-8")
    except Exception as e:
        st.error(f"Could not read metrics: {e}")
        return

    rows = []
    for line in content.strip().split("\n"):
        if len(rows) >= MAX_DISPLAY_ROWS:
            break
        line = line.strip()
        if not line:
            continue
        if ": " in line:
            key, val = line.split(": ", 1)
            rows.append({"Metric": key.strip(), "Value": val.strip()})
        elif "=" in line:
            key, val = line.split("=", 1)
            rows.append({"Metric": key.strip(), "Value": val.strip()})
        else:
            rows.append({"Metric": line, "Value": ""})

    if rows:
        st.table(rows)
    else:
        st.text(content[:5000])
