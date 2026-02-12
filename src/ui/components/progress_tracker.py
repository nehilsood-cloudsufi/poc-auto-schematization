"""Real-time pipeline progress display."""
import logging
import queue

import streamlit as st

from src.ui.adapters.progress_plugin import ProgressEvent
from src.ui.config import PHASE_LABELS

logger = logging.getLogger(__name__)


@st.fragment(run_every=2)
def render_progress(progress_queue: queue.Queue):
    """Render pipeline progress as a self-refreshing fragment.

    Uses ``@st.fragment(run_every=2)`` so only this section re-renders
    every 2 seconds — the rest of the page stays stable.

    Shows a compact progress view: current attempt + latest completed phase,
    instead of rebuilding the full cumulative event list each cycle.

    When a terminal event arrives the fragment triggers a full-app rerun
    (``st.rerun(scope="app")``) so ``app.py`` picks up the new status.
    """
    # Initialize progress history in session state
    if "progress_events" not in st.session_state:
        st.session_state["progress_events"] = []

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

    # Build compact progress summary: deduplicate by agent, keep latest per agent
    latest_by_agent: dict[str, ProgressEvent] = {}
    attempt_msg = None
    for event in events:
        if "attempt" in event.message.lower():
            attempt_msg = event.message
        latest_by_agent[event.agent_name] = event

    # Display compact progress
    last_event = events[-1] if events else None
    is_done = last_event and last_event.is_terminal

    status_label = "Pipeline running..."
    status_state = "running"
    if is_done:
        if last_event.is_error:
            status_label = "Pipeline failed"
            status_state = "error"
        else:
            status_label = "Pipeline complete!"
            status_state = "complete"

    with st.status(status_label, expanded=True, state=status_state):
        if attempt_msg:
            st.write(f"**{attempt_msg}**")

        if not events:
            st.write("Initializing pipeline...")
        else:
            # Show only the latest event per agent (deduplicated, ordered by first appearance)
            seen_agents = []
            for event in events:
                if event.agent_name not in seen_agents:
                    seen_agents.append(event.agent_name)

            for agent_name in seen_agents:
                event = latest_by_agent[agent_name]
                label = PHASE_LABELS.get(event.agent_name, event.agent_name)
                if event.is_error:
                    st.error(f"{label}: {event.message}")
                else:
                    st.write(f":white_check_mark: {label}")

    # If terminal event was found this cycle, trigger full-app rerun
    # so app.py transitions from "running" → "complete"/"error" layout.
    if terminal_found:
        st.rerun(scope="app")
