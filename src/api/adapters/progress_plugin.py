"""ADK plugin for tracking pipeline progress events."""
from __future__ import annotations

import json
import logging
import queue
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Optional

from google.adk.plugins import BasePlugin
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

if TYPE_CHECKING:
    from src.api.services.run_state import RunState

logger = logging.getLogger(__name__)

# Session state keys to persist in a checkpoint
_CHECKPOINT_KEYS = (
    "attempt_number",
    "best_pvmap_csv",
    "skeleton_summary",
    "schema_category",
    "mapping_plan",
    "approved_mapping_plan",
    "exit_reason",
)


@dataclass
class ProgressEvent:
    """A progress event from the pipeline."""
    agent_name: str
    message: str
    timestamp: float = field(default_factory=time.time)
    is_terminal: bool = False
    is_error: bool = False
    metadata: dict = field(default_factory=dict)


class ProgressTrackingPlugin(BasePlugin):
    """ADK plugin that pushes progress events to a queue for the UI."""

    def __init__(
        self,
        progress_queue: queue.Queue,
        run_state: Optional["RunState"] = None,
    ):
        super().__init__(name="progress_tracker")
        self._queue = progress_queue
        self._run_state = run_state
        logger.debug("ProgressTrackingPlugin initialised")

    def _push(self, event: ProgressEvent):
        """Push event to queue (non-blocking)."""
        try:
            self._queue.put_nowait(event)
            logger.debug(
                "Progress event pushed: agent=%s, msg=%.80s, terminal=%s",
                event.agent_name, event.message, event.is_terminal,
            )
        except queue.Full:
            logger.warning("Progress queue full — dropped event from %s", event.agent_name)

    # ------------------------------------------------------------------
    # Checkpoint helpers
    # ------------------------------------------------------------------

    def _save_checkpoint(self, callback_context: CallbackContext, reason: str, agent_name: str = ""):
        """Write a checkpoint JSON to the run directory."""
        if not self._run_state:
            return
        run_dir = Path(self._run_state.run_dir)
        run_dir.mkdir(parents=True, exist_ok=True)

        state = {}
        try:
            if hasattr(callback_context, "session") and callback_context.session:
                sess_state = callback_context.session.state
                for key in _CHECKPOINT_KEYS:
                    val = sess_state.get(key)
                    if val is not None:
                        state[key] = val
        except Exception:
            pass

        checkpoint = {
            "last_completed_agent": agent_name or "unknown",
            "attempt_number": state.get("attempt_number", 0),
            "best_pvmap_csv": state.get("best_pvmap_csv"),
            "skeleton_summary": state.get("skeleton_summary"),
            "schema_category": state.get("schema_category"),
            "mapping_plan": state.get("mapping_plan"),
            "approved_mapping_plan": state.get("approved_mapping_plan"),
            "exit_reason": reason,
        }

        checkpoint_path = run_dir / "checkpoint.json"
        checkpoint_path.write_text(json.dumps(checkpoint, default=str))
        logger.info("Checkpoint saved: %s", checkpoint_path)

    # ------------------------------------------------------------------
    # Callback
    # ------------------------------------------------------------------

    async def after_agent_callback(
        self,
        *,
        agent: BaseAgent,
        callback_context: CallbackContext,
    ) -> Optional[types.Content]:
        """Capture agent completion events for progress tracking."""
        agent_name = agent.name

        # Extract attempt number from session state for attempt-aware tracking
        attempt = 0
        try:
            if hasattr(callback_context, "session") and callback_context.session:
                attempt = callback_context.session.state.get("attempt_number", 0)
        except Exception:
            pass

        self._push(ProgressEvent(
            agent_name=agent_name,
            message=f"{agent_name} completed",
            metadata={"attempt": attempt},
        ))

        # --- Cancel check ---
        if self._run_state and self._run_state.cancel_event.is_set():
            logger.info("Cancel requested after %s — saving checkpoint", agent_name)
            self._save_checkpoint(callback_context, reason="cancelled", agent_name=agent_name)
            self._push(ProgressEvent(
                agent_name="Pipeline",
                message="Pipeline cancelled by user",
                is_terminal=True,
                metadata={"reason": "cancelled"},
            ))
            raise SystemExit("Pipeline cancelled by user")

        return None
