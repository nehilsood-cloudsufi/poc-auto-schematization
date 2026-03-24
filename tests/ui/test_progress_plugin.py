"""Tests for src.ui.adapters.progress_plugin."""
import queue
import sys
import time
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

# Mock streamlit and ADK dependencies
_mock_st = MagicMock()
_mock_st.session_state = {}
sys.modules.setdefault("streamlit", _mock_st)

from src.ui.adapters.progress_plugin import ProgressEvent, ProgressTrackingPlugin


# ---------------------------------------------------------------------------
# ProgressEvent
# ---------------------------------------------------------------------------
class TestProgressEvent:

    def test_defaults(self):
        ev = ProgressEvent(agent_name="TestAgent", message="hello")
        assert ev.agent_name == "TestAgent"
        assert ev.message == "hello"
        assert ev.is_terminal is False
        assert ev.is_error is False
        assert ev.metadata == {}
        assert isinstance(ev.timestamp, float)

    def test_terminal_error(self):
        ev = ProgressEvent(
            agent_name="Pipeline",
            message="fail",
            is_terminal=True,
            is_error=True,
            metadata={"error": "oops"},
        )
        assert ev.is_terminal is True
        assert ev.is_error is True
        assert ev.metadata["error"] == "oops"

    def test_timestamp_is_recent(self):
        before = time.time()
        ev = ProgressEvent(agent_name="A", message="m")
        after = time.time()
        assert before <= ev.timestamp <= after


# ---------------------------------------------------------------------------
# ProgressTrackingPlugin
# ---------------------------------------------------------------------------
class TestProgressTrackingPlugin:

    def test_push_event(self):
        q = queue.Queue()
        plugin = ProgressTrackingPlugin(q)
        ev = ProgressEvent(agent_name="X", message="done")
        plugin._push(ev)
        assert q.get_nowait() is ev

    def test_full_queue_does_not_raise(self):
        q = queue.Queue(maxsize=1)
        plugin = ProgressTrackingPlugin(q)
        # Fill the queue
        q.put("filler")
        # This should not raise — just drop the event
        plugin._push(ProgressEvent(agent_name="Y", message="dropped"))
        assert q.qsize() == 1

    @pytest.mark.asyncio
    async def test_after_agent_callback(self):
        q = queue.Queue()
        plugin = ProgressTrackingPlugin(q)

        mock_agent = MagicMock()
        mock_agent.name = "Generator"

        mock_ctx = MagicMock()
        mock_ctx.session.state = {"attempt_number": 2}

        result = await plugin.after_agent_callback(
            agent=mock_agent,
            callback_context=mock_ctx,
        )
        assert result is None

        ev = q.get_nowait()
        assert ev.agent_name == "Generator"
        assert "completed" in ev.message
        assert ev.metadata["attempt"] == 2

    @pytest.mark.asyncio
    async def test_after_agent_callback_no_session(self):
        q = queue.Queue()
        plugin = ProgressTrackingPlugin(q)

        mock_agent = MagicMock()
        mock_agent.name = "Sampler"
        mock_ctx = MagicMock()
        mock_ctx.session = None

        result = await plugin.after_agent_callback(
            agent=mock_agent,
            callback_context=mock_ctx,
        )
        assert result is None

        ev = q.get_nowait()
        assert ev.metadata["attempt"] == 0  # fallback
