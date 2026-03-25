"""Real-time pipeline progress display."""
import logging
import queue
import time

import streamlit as st

from src.ui.config import PHASE_LABELS

logger = logging.getLogger(__name__)

# Ordered pipeline phases (matches typical execution order)
_PIPELINE_PHASES = [
    "StatePrep",
    "Sampling",
    "SchemaSelectionAgent",
    "Generator",
    "MetadataGenerator",
    "Validator",
    "QualityEvaluator",
    "UnifiedFeedback",
    "MaxRetriesCheck",
]

# MCP-only phases (shown only if they appear in events)
_MCP_PHASES = {"StatVarDiscovery", "MCPSpotCheck", "MCPErrorResolver"}


@st.fragment(run_every=2)
def render_progress(progress_queue: queue.Queue):
    """Render pipeline progress as a self-refreshing fragment.

    Uses ``@st.fragment(run_every=2)`` so only this section re-renders
    every 2 seconds — the rest of the page stays stable.

    When a terminal event arrives the fragment triggers a full-app rerun
    (``st.rerun(scope="app")``) so ``app.py`` picks up the new status.
    """
    # Initialize progress history in session state
    if "progress_events" not in st.session_state:
        st.session_state["progress_events"] = []
    if "pipeline_start_time" not in st.session_state:
        st.session_state["pipeline_start_time"] = time.time()

    events = st.session_state["progress_events"]

    # Drain queue of any new events
    drained = 0
    terminal_found = False
    while True:
        try:
            event = progress_queue.get_nowait()
            events.append(event)
            drained += 1

            if event.is_terminal:
                terminal_found = True
                st.session_state["progress_events"] = events
                if event.is_error:
                    st.session_state["pipeline_status"] = "error"
                    st.session_state["pipeline_error"] = event.metadata.get("error", "Unknown error")
                    logger.info("Terminal event (error): %s", event.message)
                else:
                    st.session_state["pipeline_status"] = "complete"
                    st.session_state["pipeline_result"] = event.metadata.get("result", {})
                    logger.info("Terminal event (success): %s", event.message)
                break
        except queue.Empty:
            break

    if drained:
        logger.debug("Drained %d events from progress queue (total: %d)", drained, len(events))

    # Collect completed agent names and track current attempt
    completed_agents: set[str] = set()
    current_attempt = 0
    max_attempts = 0
    attempt_msg = None
    for event in events:
        completed_agents.add(event.agent_name)
        if "attempt" in event.message.lower():
            attempt_msg = event.message
        # Track attempt number from event metadata
        evt_attempt = event.metadata.get("attempt", 0) if event.metadata else 0
        if evt_attempt > current_attempt:
            current_attempt = evt_attempt
            # Reset completed set for new attempt so phases show fresh
            completed_agents = {event.agent_name}
        # Track max attempt seen
        if evt_attempt > max_attempts:
            max_attempts = evt_attempt

    # Build ordered phase list (include MCP phases only if seen)
    phases = list(_PIPELINE_PHASES)
    for mcp_phase in _MCP_PHASES:
        if mcp_phase in completed_agents and mcp_phase not in phases:
            # Insert MCP phases near their logical position
            if mcp_phase == "StatVarDiscovery":
                idx = phases.index("Generator")
                phases.insert(idx, mcp_phase)
            elif mcp_phase in ("MCPSpotCheck", "MCPErrorResolver"):
                idx = phases.index("Validator") + 1
                phases.insert(idx, mcp_phase)

    # Count completed phases
    completed_count = sum(1 for p in phases if p in completed_agents)
    total_phases = len(phases)

    # Determine current status
    last_event = events[-1] if events else None
    is_done = last_event and last_event.is_terminal

    # Elapsed time
    elapsed = time.time() - st.session_state.get("pipeline_start_time", time.time())
    elapsed_str = f"{int(elapsed)}s" if elapsed < 60 else f"{int(elapsed // 60)}m {int(elapsed % 60)}s"

    # Header row
    if is_done:
        if last_event.is_error:
            st.error(f"Pipeline failed after {elapsed_str}")
        else:
            st.success(f"Pipeline complete in {elapsed_str}")
    else:
        if current_attempt > 0:
            title = f"Attempt {current_attempt + 1} — Pipeline running..."
        elif attempt_msg:
            title = attempt_msg
        else:
            title = "Pipeline running..."
        st.markdown(f"**{title}** &nbsp; | &nbsp; Elapsed: {elapsed_str}")

    # Progress bar
    progress_frac = completed_count / max(total_phases, 1)
    if is_done and not (last_event and last_event.is_error):
        progress_frac = 1.0
    st.progress(progress_frac, text=f"{completed_count}/{total_phases} phases")

    # Phase checklist — single markdown block to avoid fragment height issues
    next_phase = _next_phase(phases, completed_agents)
    lines = []
    for phase in phases:
        label = PHASE_LABELS.get(phase, phase)
        display_label = label.rstrip(".")

        if phase in completed_agents:
            phase_events = [e for e in events if e.agent_name == phase]
            has_error = any(e.is_error for e in phase_events)
            if has_error:
                lines.append(f"- :red[**X** {display_label}]")
            else:
                lines.append(f"- :green[**✓** {display_label}]")
        elif completed_count > 0 and phase == next_phase:
            lines.append(f"- :blue[**⟳** {label}]")
        else:
            lines.append(f"- :gray[○ {display_label}]")

    st.markdown("\n".join(lines))

    # If terminal event was found this cycle, trigger full-app rerun
    # so app.py transitions from "running" → "complete"/"error" layout.
    if terminal_found:
        st.rerun(scope="app")


def _next_phase(phases: list[str], completed: set[str]) -> str | None:
    """Return the first phase in the ordered list that isn't completed."""
    for phase in phases:
        if phase not in completed:
            return phase
    return None
