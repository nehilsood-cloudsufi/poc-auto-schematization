"""ADK plugin for tracking pipeline progress events."""
import logging
import queue
import time
from dataclasses import dataclass, field
from typing import Optional

from google.adk.plugins import BasePlugin
from google.adk.agents.base_agent import BaseAgent
from google.adk.agents.callback_context import CallbackContext
from google.genai import types

logger = logging.getLogger(__name__)


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

    def __init__(self, progress_queue: queue.Queue):
        super().__init__(name="progress_tracker")
        self._queue = progress_queue
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

    async def after_agent_callback(
        self,
        *,
        agent: BaseAgent,
        callback_context: CallbackContext,
    ) -> Optional[types.Content]:
        """Capture agent completion events for progress tracking."""
        agent_name = agent.name

        self._push(ProgressEvent(
            agent_name=agent_name,
            message=f"{agent_name} completed",
        ))

        return None
