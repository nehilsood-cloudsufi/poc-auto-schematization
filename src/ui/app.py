"""Streamlit UI for PVMAP Generation Pipeline.

Launch with:
    PYTHONPATH="$(pwd):$(pwd)/src" streamlit run src/ui/app.py
"""
import logging
import queue
import sys
from pathlib import Path

# Ensure project root is on sys.path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
    sys.path.insert(0, str(PROJECT_ROOT / "src"))

import streamlit as st

from src.ui.config import (
    DEFAULT_MAX_RETRIES,
    DEFAULT_MODEL,
    DEFAULT_PROMPT_VERSION,
    MCP_DEFAULT_PORT,
    MIN_PIPELINE_ATTEMPTS,
    setup_ui_logging,
)

logger = logging.getLogger(__name__)
from src.ui.components.file_uploader import render_file_upload
from src.ui.components.progress_tracker import render_progress
from src.ui.components.output_viewer import render_output_tabs
from src.ui.components.feedback_form import render_feedback_form
from src.ui.components.download_helper import render_download_button
from src.ui.services.pipeline_runner import PipelineConfig, launch_pipeline
from src.ui.services.file_manager import discover_historical_runs

# ──────────────────────────────────────────────────────────────────
# Page config
# ──────────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Agent B: Auto Schematization",
    page_icon=":bar_chart:",
    layout="wide",
)

# ──────────────────────────────────────────────────────────────────
# Session state defaults
# ──────────────────────────────────────────────────────────────────
_DEFAULTS = {
    "pipeline_status": "idle",      # idle | launching | running | complete | error
    "run_id": None,
    "run_dir": None,
    "dataset_name": None,
    "input_path": None,
    "metadata_path": None,
    "progress_queue": None,
    "pipeline_thread": None,
    "pipeline_result": {},
    "pipeline_error": None,
    "progress_events": [],
    "human_feedback": None,
    "skip_sampling": False,
    "mcp_enabled": True,
    "model": DEFAULT_MODEL,
    "used_edited_pvmap": False,
    "use_metadata": False,
    "max_retries": DEFAULT_MAX_RETRIES,
    "prompt_version": DEFAULT_PROMPT_VERSION,
    "use_schema_examples": True,
}

for key, default in _DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = default

logger.debug("Session state initialised: %s", {k: v for k, v in _DEFAULTS.items() if k != "pipeline_result"})


# ──────────────────────────────────────────────────────────────────
# Pipeline launch helper (defined before use)
# ──────────────────────────────────────────────────────────────────
def _launch_pipeline():
    """Create PipelineConfig and launch in background thread."""
    run_dir = Path(st.session_state["run_dir"])
    dataset_name = st.session_state["dataset_name"]

    # Set up UI logging for this run
    setup_ui_logging(run_dir)
    logger.info("Launching pipeline for dataset=%s, run_dir=%s", dataset_name, run_dir)

    # Handle MCP (DC MCP only — Schema.org uses local tools, no server needed)
    mcp_url = None
    mcp_enabled = st.session_state.get("mcp_enabled", False)
    if mcp_enabled:
        logger.info("MCP enabled — starting DC MCP server on port %d", MCP_DEFAULT_PORT)
        from src.ui.services.mcp_lifecycle import get_or_start_mcp, get_mcp_url
        get_or_start_mcp(MCP_DEFAULT_PORT)
        mcp_url = get_mcp_url()
        logger.info("DC MCP URL: %s", mcp_url)

    config = PipelineConfig(
        run_id=st.session_state["run_id"],
        dataset_name=dataset_name,
        input_dir=run_dir / "input",
        output_dir=run_dir / "output",
        input_file=st.session_state.get("input_path"),
        model=st.session_state.get("model", DEFAULT_MODEL),
        enable_mcp=mcp_enabled,
        mcp_url=mcp_url,
        prompt_version=st.session_state.get("prompt_version", DEFAULT_PROMPT_VERSION),
        use_schema_examples=st.session_state.get("use_schema_examples", True),
        skip_sampling=st.session_state.get("skip_sampling", False),
        skip_evaluation=True,  # No ground truth in UI mode
        use_metadata=st.session_state.get("use_metadata", False),
        metadata_file_path=st.session_state.get("metadata_path"),
        human_feedback=st.session_state.get("human_feedback"),
        min_attempts=MIN_PIPELINE_ATTEMPTS,
        max_retries=st.session_state.get("max_retries", DEFAULT_MAX_RETRIES),
    )

    logger.info(
        "PipelineConfig: model=%s, mcp=%s, skip_sampling=%s, use_metadata=%s, "
        "human_feedback=%s, min_attempts=%d",
        config.model, config.enable_mcp, config.skip_sampling,
        config.use_metadata, config.human_feedback is not None,
        config.min_attempts,
    )

    progress_queue = queue.Queue(maxsize=100)
    st.session_state["progress_queue"] = progress_queue

    thread = launch_pipeline(config, progress_queue)
    st.session_state["pipeline_thread"] = thread
    st.session_state["pipeline_status"] = "running"
    logger.info("Pipeline thread started: %s", thread.name)

    st.rerun()


# ──────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.title("Agent B: Auto Schematization")

    # Model selector
    model = st.selectbox(
        "Model",
        ["gemini-3-pro-preview", "gemini-2.5-pro", "gemini-2.5-flash"],
        index=0,
        key="model_selector",
    )
    st.session_state["model"] = model

    # Retry count
    max_retries = st.number_input(
        "Max Retries",
        min_value=0,
        max_value=10,
        value=st.session_state.get("max_retries", DEFAULT_MAX_RETRIES),
        step=1,
        help="Number of retry attempts after the initial generation (total attempts = retries + 1)",
        key="max_retries_input",
    )
    st.session_state["max_retries"] = max_retries

    # MCP toggle
    mcp_enabled = st.toggle("Enable MCP", value=st.session_state.get("mcp_enabled", False))
    st.session_state["mcp_enabled"] = mcp_enabled

    if mcp_enabled:
        st.caption("MCP servers will start automatically")

    # Advanced settings
    with st.expander("Advanced Settings"):
        prompt_version = st.radio(
            "Prompt Version",
            ["v2", "v1"],
            index=["v2", "v1"].index(st.session_state.get("prompt_version", DEFAULT_PROMPT_VERSION)),
            help="v2 = restructured prompt (recommended). v1 = legacy prompt.",
            horizontal=True,
        )
        st.session_state["prompt_version"] = prompt_version

        use_schema_examples = st.toggle(
            "Include Schema Examples",
            value=st.session_state.get("use_schema_examples", True),
            help="Inject schema vocabulary into the PVMAP prompt",
        )
        st.session_state["use_schema_examples"] = use_schema_examples

    # Run status badge
    status = st.session_state["pipeline_status"]
    status_colors = {
        "idle": ":gray[Idle]",
        "launching": ":orange[Launching...]",
        "running": ":blue[Running...]",
        "complete": ":green[Complete]",
        "error": ":red[Error]",
    }
    st.markdown(f"**Status:** {status_colors.get(status, status)}")

    # Reset button
    if status in ("complete", "error"):
        if st.button("New Run"):
            logger.info("User initiated New Run — resetting session state")
            for key, default in _DEFAULTS.items():
                st.session_state[key] = default
            st.rerun()

    # ── History section ─────────────────────────────────────────
    st.divider()
    st.subheader("History")
    runs = discover_historical_runs()
    if not runs:
        st.caption("No previous runs found.")
    else:
        for run in runs[:10]:
            ts_short = run["timestamp"][:10] if run["timestamp"] else "unknown"
            icon = "\U0001F7E2" if run["result"].get("validation_passed") else "\U0001F534"
            label = f"{icon} {run['dataset_name']} ({ts_short})"
            if st.button(label, key=f"hist_{run['run_id']}"):
                logger.info("Loading historical run: %s", run["run_id"])
                st.session_state["pipeline_status"] = "complete"
                st.session_state["run_id"] = run["run_id"]
                st.session_state["run_dir"] = run["run_dir"]
                st.session_state["dataset_name"] = run["dataset_name"]
                st.session_state["pipeline_result"] = run.get("result", {})
                st.session_state["progress_events"] = []
                st.rerun()


# ──────────────────────────────────────────────────────────────────
# Main content
# ──────────────────────────────────────────────────────────────────
status = st.session_state["pipeline_status"]

# ── Section 1: Upload & Run ──────────────────────────────────────
if status in ("idle", "launching"):
    should_launch = render_file_upload()

    if status == "launching" or should_launch:
        _launch_pipeline()


# ── Section 2: Progress ──────────────────────────────────────────
if status == "running":
    progress_queue = st.session_state.get("progress_queue")
    if progress_queue:
        render_progress(progress_queue)


# ── Section 3: Results ───────────────────────────────────────────
if status == "complete":
    dataset_name = st.session_state.get("dataset_name", "")
    run_dir = st.session_state.get("run_dir")

    if run_dir and dataset_name:
        output_dir = Path(run_dir) / "output" / dataset_name
        render_output_tabs(output_dir)

        st.divider()

        # ── Section 4: Feedback ──────────────────────────────────
        rerun = render_feedback_form(output_dir)
        if rerun:
            _launch_pipeline()

        st.divider()

        # ── Section 5: Download ──────────────────────────────────
        render_download_button(output_dir, dataset_name)


# ── Error state ──────────────────────────────────────────────────
if status == "error":
    err = st.session_state.get("pipeline_error", "Unknown error")
    logger.error("Pipeline error state displayed: %s", err)
    st.error(f"Pipeline failed: {err}")

    if st.button("Try Again"):
        st.session_state["pipeline_status"] = "idle"
        st.rerun()
