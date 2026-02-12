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


# ── Schema.org MCP server lifecycle ─────────────────────────────

_SCHEMAORG_MCP_STATE_KEY = "schemaorg_mcp_manager"
_SCHEMAORG_MCP_URL_KEY = "schemaorg_mcp_url"


def get_or_start_schemaorg_mcp(port: int = 3001) -> Optional[object]:
    """Get existing or start new Schema.org MCP server, stored in session_state."""
    if _SCHEMAORG_MCP_STATE_KEY in st.session_state and st.session_state[_SCHEMAORG_MCP_STATE_KEY]:
        return st.session_state[_SCHEMAORG_MCP_STATE_KEY]

    try:
        from src.data_commons.api.schemaorg_mcp_manager import SchemaOrgMCPManager

        manager = SchemaOrgMCPManager(port=port)
        if manager.start(timeout=30):
            st.session_state[_SCHEMAORG_MCP_STATE_KEY] = manager
            st.session_state[_SCHEMAORG_MCP_URL_KEY] = manager.mcp_url
            atexit.register(_cleanup_schemaorg_mcp)
            logger.info(f"Schema.org MCP server started at {manager.mcp_url}")
            return manager
        else:
            logger.warning("Schema.org MCP server failed to start")
            return None
    except ImportError:
        logger.warning("schemaorg_mcp_manager not available")
        return None
    except Exception as e:
        logger.warning(f"Schema.org MCP start failed: {e}")
        return None


def stop_schemaorg_mcp() -> None:
    """Stop the Schema.org MCP server and clear session state."""
    manager = st.session_state.get(_SCHEMAORG_MCP_STATE_KEY)
    if manager:
        logger.debug("Stopping Schema.org MCP server")
        try:
            manager.stop()
            logger.info("Schema.org MCP server stopped")
        except Exception as e:
            logger.warning("Error stopping Schema.org MCP server: %s", e)
    st.session_state.pop(_SCHEMAORG_MCP_STATE_KEY, None)
    st.session_state.pop(_SCHEMAORG_MCP_URL_KEY, None)


def get_schemaorg_mcp_url() -> Optional[str]:
    """Return Schema.org MCP URL if server is running."""
    url = st.session_state.get(_SCHEMAORG_MCP_URL_KEY)
    logger.debug("get_schemaorg_mcp_url() = %s", url)
    return url


def _cleanup_schemaorg_mcp():
    """atexit handler to stop Schema.org MCP server."""
    logger.debug("atexit: cleaning up Schema.org MCP server")
    try:
        stop_schemaorg_mcp()
    except Exception:
        pass
