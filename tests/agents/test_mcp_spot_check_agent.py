"""
Tests for MCPSpotCheckAgent (src/agents/mcp_spot_check_agent.py).

Tests cover:
- Skip behavior when MCP disabled
- Skip when no discovered statvars
- Warning injection when observation unconfirmed
- No-op when observations confirmed
- Graceful error handling
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.mcp_spot_check_agent import (
    MCPSpotCheckAgent,
    _get_sample_places,
    _resolve_sample_place,
)

# Patch targets: dc_tools functions are imported inside the try block,
# so we patch them at their source module.
PATCH_RESOLVE = "src.tools.dc_tools.dc_api_resolve_placeid"
PATCH_VALIDATE_CLIENT = "src.tools.dc_tools._get_dc_client"


def _collect_events(agent, state):
    """Helper to run agent and collect events synchronously."""
    import asyncio
    from google.adk.agents.invocation_context import InvocationContext

    # Create a mock InvocationContext with the given state
    ctx = MagicMock(spec=InvocationContext)
    mock_session = MagicMock()
    mock_session.state = state
    ctx.session = mock_session

    async def _run():
        events = []
        async for event in agent._run_async_impl(ctx):
            events.append(event)
        return events

    # Use a new event loop to avoid corrupting the default loop
    loop = asyncio.new_event_loop()
    try:
        result = loop.run_until_complete(_run())
    finally:
        loop.close()
    return result, state


class TestMCPSpotCheckSkip:
    """Tests for skip conditions."""

    def test_skip_when_mcp_disabled(self):
        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {"mcp_enabled": False}
        events, _ = _collect_events(agent, state)

        assert len(events) == 1
        text = events[0].content.parts[0].text
        assert "skipped" in text.lower()
        assert "MCP not enabled" in text

    def test_skip_when_mcp_not_in_state(self):
        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {}
        events, _ = _collect_events(agent, state)

        assert len(events) == 1
        text = events[0].content.parts[0].text
        assert "skipped" in text.lower()

    def test_skip_when_no_discovered_statvars(self):
        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {
            "mcp_enabled": True,
            "discovered_statvars": [],
        }
        events, _ = _collect_events(agent, state)

        assert len(events) == 1
        text = events[0].content.parts[0].text
        assert "skipped" in text.lower()
        assert "no discovered StatVars" in text

    def test_skip_when_discovered_statvars_missing(self):
        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {"mcp_enabled": True}
        events, _ = _collect_events(agent, state)

        assert len(events) == 1
        text = events[0].content.parts[0].text
        assert "skipped" in text.lower()


class TestMCPSpotCheckExecution:
    """Tests for actual spot-check execution."""

    @patch(PATCH_VALIDATE_CLIENT)
    @patch(PATCH_RESOLVE)
    def test_confirmed_no_warnings(self, mock_resolve, mock_get_client):
        mock_resolve.return_value = {"California": "geoId/06"}
        mock_client = MagicMock()
        mock_client.observation.fetch.return_value = {
            "observations": [{"value": 39538223, "date": "2020"}]
        }
        mock_get_client.return_value = mock_client

        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {
            "mcp_enabled": True,
            "discovered_statvars": [
                {"dcid": "Count_Person", "confidence": "HIGH"},
            ],
            "data_context": {
                "column_roles": {"State": "place"},
                "dimension_domains": {"State": ["California"]},
            },
            "structure_warnings": "",
        }
        events, final_state = _collect_events(agent, state)

        # Should have "Running..." event and summary event
        assert len(events) >= 2
        summary = events[-1].content.parts[0].text
        assert "confirmed" in summary.lower()
        # No warnings added
        assert "WARNING" not in final_state.get("structure_warnings", "")

    @patch(PATCH_VALIDATE_CLIENT)
    @patch(PATCH_RESOLVE)
    def test_unconfirmed_adds_warning(self, mock_resolve, mock_get_client):
        mock_resolve.return_value = {"California": "geoId/06"}
        mock_client = MagicMock()
        mock_client.observation.fetch.side_effect = Exception("Not found")
        mock_get_client.return_value = mock_client

        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {
            "mcp_enabled": True,
            "discovered_statvars": [
                {"dcid": "FakeStat", "confidence": "HIGH"},
            ],
            "data_context": {
                "column_roles": {"State": "place"},
                "dimension_domains": {"State": ["California"]},
            },
            "structure_warnings": "",
        }
        events, final_state = _collect_events(agent, state)

        # Check warning was injected
        warnings = final_state.get("structure_warnings", "")
        assert "WARNING" in warnings
        assert "FakeStat" in warnings
        # Summary should mention warnings
        summary = events[-1].content.parts[0].text
        assert "warning" in summary.lower()

    @patch(PATCH_VALIDATE_CLIENT)
    @patch(PATCH_RESOLVE)
    def test_appends_to_existing_warnings(self, mock_resolve, mock_get_client):
        mock_resolve.return_value = {}
        mock_client = MagicMock()
        mock_client.observation.fetch.side_effect = Exception("Not found")
        mock_get_client.return_value = mock_client

        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {
            "mcp_enabled": True,
            "discovered_statvars": [
                {"dcid": "BadVar", "confidence": "HIGH"},
            ],
            "data_context": {},
            "structure_warnings": "Existing warning from validator",
        }
        events, final_state = _collect_events(agent, state)

        warnings = final_state.get("structure_warnings", "")
        assert "Existing warning from validator" in warnings
        assert "BadVar" in warnings

    @patch("src.tools.dc_tools._get_dc_client")
    @patch("src.tools.dc_tools.dc_api_resolve_placeid")
    def test_handles_exception_gracefully(self, mock_resolve, mock_get_client):
        """Test that agent handles exceptions in validate call gracefully."""
        mock_resolve.return_value = {"Test": "geoId/06"}
        # Make the client raise on observation.fetch
        mock_client = MagicMock()
        mock_client.observation.fetch.side_effect = RuntimeError("Connection reset")
        mock_get_client.return_value = mock_client

        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {
            "mcp_enabled": True,
            "discovered_statvars": [
                {"dcid": "Count_Person", "confidence": "HIGH"},
            ],
            "data_context": {},
            "structure_warnings": "",
        }
        events, final_state = _collect_events(agent, state)

        # Should not crash; the UNCONFIRMED result should produce a warning
        last_text = events[-1].content.parts[0].text
        # Either reports warnings or completes with check summary
        assert "check" in last_text.lower() or "warning" in last_text.lower()

    @patch(PATCH_VALIDATE_CLIENT)
    @patch(PATCH_RESOLVE)
    def test_checks_only_high_confidence(self, mock_resolve, mock_get_client):
        mock_resolve.return_value = {}
        mock_client = MagicMock()
        call_count = 0

        def mock_fetch(**kwargs):
            nonlocal call_count
            call_count += 1
            return {"observations": [{"value": 100}]}

        mock_client.observation.fetch = mock_fetch
        mock_get_client.return_value = mock_client

        agent = MCPSpotCheckAgent(name="TestSpotCheck")
        state = {
            "mcp_enabled": True,
            "discovered_statvars": [
                {"dcid": "MediumVar", "confidence": "MEDIUM"},
                {"dcid": "HighVar1", "confidence": "HIGH"},
                {"dcid": "HighVar2", "confidence": "HIGH"},
                {"dcid": "HighVar3", "confidence": "HIGH"},
            ],
            "data_context": {},
            "structure_warnings": "",
        }
        events, _ = _collect_events(agent, state)

        # Should only check 2 HIGH confidence vars (not all 4)
        assert call_count == 2


class TestHelperFunctions:
    """Tests for helper functions."""

    def test_get_sample_places_with_context(self):
        context = {
            "column_roles": {"State": "place", "Year": "time"},
            "dimension_domains": {"State": ["CA", "TX", "NY", "FL"]},
        }
        places = _get_sample_places(context)
        assert "CA" in places
        assert "TX" in places
        assert len(places) <= 5

    def test_get_sample_places_empty_context(self):
        assert _get_sample_places({}) == []
        assert _get_sample_places(None) == []

    def test_get_sample_places_no_place_columns(self):
        context = {
            "column_roles": {"Year": "time", "Value": "value"},
            "dimension_domains": {},
        }
        assert _get_sample_places(context) == []

    def test_resolve_sample_place_found(self):
        def mock_resolve(names):
            return "- California -> geoId/06"

        result = _resolve_sample_place(["California"], mock_resolve)
        assert result == "geoId/06"

    def test_resolve_sample_place_not_found_uses_default(self):
        def mock_resolve(names):
            return "- Unknown -> NOT_FOUND"

        result = _resolve_sample_place(["Unknown"], mock_resolve)
        assert result == "geoId/06"  # Default fallback

    def test_resolve_sample_place_empty_list(self):
        def mock_resolve(names):
            return ""

        result = _resolve_sample_place([], mock_resolve)
        assert result == "geoId/06"  # Default fallback
