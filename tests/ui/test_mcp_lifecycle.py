"""Tests for src.ui.services.mcp_lifecycle."""
import sys
from unittest.mock import MagicMock, patch

import pytest

# Mock streamlit with a fresh session_state per test
_mock_st = MagicMock()
_mock_st.session_state = {}
sys.modules["streamlit"] = _mock_st


# ---------------------------------------------------------------------------
# Fixture to reset session_state between tests
# ---------------------------------------------------------------------------
@pytest.fixture(autouse=True)
def _reset_session_state():
    _mock_st.session_state = {}
    yield
    _mock_st.session_state = {}


# Import AFTER streamlit is mocked
from src.ui.services.mcp_lifecycle import (
    get_or_start_mcp,
    stop_mcp,
    get_mcp_url,
    _MCP_STATE_KEY,
    _MCP_URL_KEY,
)


# ---------------------------------------------------------------------------
# get_or_start_mcp
# ---------------------------------------------------------------------------
class TestGetOrStartMcp:

    def test_returns_existing_manager(self):
        fake_manager = MagicMock()
        _mock_st.session_state[_MCP_STATE_KEY] = fake_manager

        result = get_or_start_mcp()
        assert result is fake_manager

    @patch("src.ui.services.mcp_lifecycle.MCPServerManager", create=True)
    def test_starts_new_server(self, _):
        """When import succeeds and start returns True, stores in session."""
        mock_manager = MagicMock()
        mock_manager.start.return_value = True
        mock_manager.mcp_url = "http://localhost:3000"

        with patch.dict(sys.modules, {
            "src.data_commons.api.mcp_server_manager": MagicMock(
                MCPServerManager=MagicMock(return_value=mock_manager)
            ),
        }):
            # Need to re-trigger the import inside get_or_start_mcp
            from importlib import reload
            import src.ui.services.mcp_lifecycle as mod
            reload(mod)

            result = mod.get_or_start_mcp(port=3000)
            assert result is mock_manager
            assert _mock_st.session_state[_MCP_STATE_KEY] is mock_manager
            assert _mock_st.session_state[_MCP_URL_KEY] == "http://localhost:3000"

    def test_returns_none_on_import_error(self):
        with patch.dict(sys.modules, {
            "src.data_commons.api.mcp_server_manager": None,  # simulate ImportError
        }):
            from importlib import reload
            import src.ui.services.mcp_lifecycle as mod
            reload(mod)

            result = mod.get_or_start_mcp()
            # Should return None, not raise
            assert result is None

    def test_returns_none_on_start_failure(self):
        mock_manager = MagicMock()
        mock_manager.start.return_value = False

        with patch.dict(sys.modules, {
            "src.data_commons.api.mcp_server_manager": MagicMock(
                MCPServerManager=MagicMock(return_value=mock_manager)
            ),
        }):
            from importlib import reload
            import src.ui.services.mcp_lifecycle as mod
            reload(mod)

            result = mod.get_or_start_mcp()
            assert result is None


# ---------------------------------------------------------------------------
# stop_mcp
# ---------------------------------------------------------------------------
class TestStopMcp:

    def test_stops_and_clears_state(self):
        mock_manager = MagicMock()
        _mock_st.session_state[_MCP_STATE_KEY] = mock_manager
        _mock_st.session_state[_MCP_URL_KEY] = "http://localhost:3000"

        stop_mcp()
        mock_manager.stop.assert_called_once()
        assert _MCP_STATE_KEY not in _mock_st.session_state
        assert _MCP_URL_KEY not in _mock_st.session_state

    def test_noop_when_no_manager(self):
        stop_mcp()  # should not raise

    def test_handles_stop_exception(self):
        mock_manager = MagicMock()
        mock_manager.stop.side_effect = RuntimeError("cleanup error")
        _mock_st.session_state[_MCP_STATE_KEY] = mock_manager

        stop_mcp()  # should not raise
        assert _MCP_STATE_KEY not in _mock_st.session_state


# ---------------------------------------------------------------------------
# get_mcp_url
# ---------------------------------------------------------------------------
class TestGetMcpUrl:

    def test_returns_url_when_set(self):
        _mock_st.session_state[_MCP_URL_KEY] = "http://localhost:3000"
        assert get_mcp_url() == "http://localhost:3000"

    def test_returns_none_when_not_set(self):
        assert get_mcp_url() is None
