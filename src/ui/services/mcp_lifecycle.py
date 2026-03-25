"""MCP server lifecycle management for Streamlit UI."""
import atexit
import logging
from typing import Optional

import streamlit as st

logger = logging.getLogger(__name__)

_MCP_STATE_KEY = "mcp_manager"
_MCP_URL_KEY = "mcp_url"


def get_or_start_mcp(port: int = 3000) -> Optional[object]:
    """Get existing or start new MCP server, stored in session_state."""
    if _MCP_STATE_KEY in st.session_state and st.session_state[_MCP_STATE_KEY]:
        return st.session_state[_MCP_STATE_KEY]

    try:
        from src.data_commons.api.mcp_server_manager import MCPServerManager

        manager = MCPServerManager(port=port)
        if manager.start(timeout=30):
            st.session_state[_MCP_STATE_KEY] = manager
            st.session_state[_MCP_URL_KEY] = manager.mcp_url
            atexit.register(_cleanup_mcp)
            logger.info(f"MCP server started at {manager.mcp_url}")
            return manager
        else:
            logger.warning("MCP server failed to start")
            return None
    except ImportError:
        logger.warning("datacommons-mcp not installed")
        return None
    except Exception as e:
        logger.warning(f"MCP start failed: {e}")
        return None


def stop_mcp() -> None:
    """Stop the MCP server and clear session state."""
    manager = st.session_state.get(_MCP_STATE_KEY)
    if manager:
        logger.debug("Stopping MCP server")
        try:
            manager.stop()
            logger.info("MCP server stopped")
        except Exception as e:
            logger.warning("Error stopping MCP server: %s", e)
    st.session_state.pop(_MCP_STATE_KEY, None)
    st.session_state.pop(_MCP_URL_KEY, None)


def get_mcp_url() -> Optional[str]:
    """Return MCP URL if server is running."""
    url = st.session_state.get(_MCP_URL_KEY)
    logger.debug("get_mcp_url() = %s", url)
    return url


def _cleanup_mcp():
    """atexit handler to stop MCP server."""
    logger.debug("atexit: cleaning up MCP server")
    try:
        stop_mcp()
    except Exception:
        pass
