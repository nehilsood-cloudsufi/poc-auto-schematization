"""Streamlit UI for PVMAP Generation Pipeline.

Launch with:
    PYTHONPATH="$(pwd):$(pwd)/src" streamlit run src/ui/app.py
"""
import logging
import queue
import sys
import time
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
from src.ui.components.developer_feedback import render_developer_feedback
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
# Custom CSS for cleaner layout
# ──────────────────────────────────────────────────────────────────
st.markdown("""
<style>
    /* Tighter section spacing — keep enough room so top content is not clipped */
    .block-container { padding-top: 3.5rem; }
    /* Hide default sidebar title padding */
    [data-testid="stSidebar"] > div:first-child { padding-top: 1rem; }
    /* Smaller sub-headers */
    .stMarkdown h2 { font-size: 1.25rem; margin-top: 1rem; }
    .stMarkdown h3 { font-size: 1.1rem; }
    /* Compact metrics */
    [data-testid="stMetric"] { padding: 0.5rem 0; }
    [data-testid="stMetricValue"] { font-size: 1.5rem; }
    /* Compact expanders */
    .streamlit-expanderHeader { font-size: 0.9rem; }
    /* Sidebar header block */
    .sidebar-header { margin-bottom: 0.75rem; }
    .sidebar-header h2 {
        margin: 0 0 0.1rem 0;
        font-size: 1.4rem;
        font-weight: 700;
        line-height: 1.2;
    }
    .sidebar-header .subtitle {
        color: #6b7280;
        font-size: 0.85rem;
        margin: 0;
    }
    .status-pill {
        display: inline-block;
        padding: 0.2rem 0.65rem;
        border-radius: 999px;
        font-size: 0.8rem;
        font-weight: 500;
        margin-top: 0.4rem;
    }
    .status-idle { background: #e5e7eb; color: #4b5563; }
    .status-launching { background: #fed7aa; color: #9a3412; }
    .status-running { background: #bfdbfe; color: #1e40af; }
    .status-complete { background: #bbf7d0; color: #166534; }
    .status-error { background: #fecaca; color: #991b1b; }
</style>
""", unsafe_allow_html=True)

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
    "pipeline_start_time": None,
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
    logger.info(
        "Launching pipeline for dataset=%s, run_dir=%s", dataset_name, run_dir,
        extra={"user_event": "pipeline_start", "run_id": st.session_state.get("run_id", ""), "dataset_name": dataset_name, "action": "upload_and_run"},
    )

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
        thinking_level="high",
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
    st.session_state["pipeline_start_time"] = time.time()
    logger.info("Pipeline thread started: %s", thread.name)

    st.rerun()


# ──────────────────────────────────────────────────────────────────
# Sidebar
# ──────────────────────────────────────────────────────────────────
with st.sidebar:
    # Compact header with inline status pill
    status = st.session_state["pipeline_status"]
    _status_labels = {
        "idle": ("Idle", "idle"),
        "launching": ("Launching", "launching"),
        "running": ("Running", "running"),
        "complete": ("Complete", "complete"),
        "error": ("Error", "error"),
    }
    pill_text, pill_class = _status_labels.get(status, ("?", "idle"))
    st.markdown(f"""
    <div class="sidebar-header">
        <h2>Agent B <span class="status-pill status-{pill_class}">{pill_text}</span></h2>
        <p class="subtitle">Auto Schematization Pipeline</p>
    </div>
    """, unsafe_allow_html=True)

    if status in ("complete", "error"):
        if st.button("New Run", use_container_width=True):
            logger.info("User initiated New Run — resetting session state", extra={"user_event": "new_run", "action": "reset_session"})
            for key, default in _DEFAULTS.items():
                st.session_state[key] = default
            st.rerun()

    st.divider()

    # ── Configuration ───────────────────────────────────────────
    st.subheader("Configuration")

    col_retries, col_mcp = st.columns(2)
    with col_retries:
        max_retries = st.number_input(
            "Max Retries",
            min_value=0,
            max_value=10,
            value=st.session_state.get("max_retries", DEFAULT_MAX_RETRIES),
            step=1,
            help="Retry attempts after initial generation",
            key="max_retries_input",
        )
        st.session_state["max_retries"] = max_retries
    with col_mcp:
        mcp_enabled = st.toggle(
            "MCP",
            value=st.session_state.get("mcp_enabled", False),
            help="Enable DC MCP server for StatVar discovery",
        )
        st.session_state["mcp_enabled"] = mcp_enabled

    with st.expander("Advanced"):
        prompt_version = st.radio(
            "Prompt Version",
            ["v2", "v1"],
            index=["v2", "v1"].index(st.session_state.get("prompt_version", DEFAULT_PROMPT_VERSION)),
            help="v2 = restructured (recommended)",
            horizontal=True,
        )
        st.session_state["prompt_version"] = prompt_version

        use_schema_examples = st.toggle(
            "Schema Examples",
            value=st.session_state.get("use_schema_examples", True),
            help="Inject schema vocabulary into prompt",
        )
        st.session_state["use_schema_examples"] = use_schema_examples

    # ── History ─────────────────────────────────────────────────
    st.divider()
    st.subheader("History")
    runs = discover_historical_runs()
    if not runs:
        st.caption("No previous runs.")
    else:
        for run in runs[:10]:
            ts_short = run["timestamp"][:10] if run["timestamp"] else "?"
            passed = run["result"].get("validation_passed")
            icon = "\u2713" if passed else "\u2717"
            label = f"{icon} {run['dataset_name']} ({ts_short})"
            if st.button(label, key=f"hist_{run['run_id']}", use_container_width=True):
                logger.info("Loading historical run: %s", run["run_id"], extra={"user_event": "load_history", "run_id": run["run_id"], "dataset_name": run["dataset_name"]})
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

        logger.info("Showing results for %s", dataset_name, extra={"user_event": "pipeline_complete", "run_id": st.session_state.get("run_id", ""), "dataset_name": dataset_name})
        st.subheader(f"Results: `{dataset_name}`")
        render_output_tabs(output_dir)

        st.divider()

        # ── Feedback & Download ──────────────────────────────────
        feedback_col, download_col = st.columns([3, 1])
        with feedback_col:
            rerun = render_feedback_form(output_dir)
            if rerun:
                _launch_pipeline()
        with download_col:
            render_download_button(output_dir, dataset_name)

        st.divider()
        render_developer_feedback()


# ── Error state ──────────────────────────────────────────────────
if status == "error":
    err = st.session_state.get("pipeline_error", "Unknown error")
    logger.error("Pipeline error state displayed: %s", err, extra={"user_event": "pipeline_error", "run_id": st.session_state.get("run_id", ""), "dataset_name": st.session_state.get("dataset_name", "")})
    st.error(f"Pipeline failed: {err}")

    if st.button("Try Again"):
        st.session_state["pipeline_status"] = "idle"
        st.rerun()

    st.divider()
    render_developer_feedback()
