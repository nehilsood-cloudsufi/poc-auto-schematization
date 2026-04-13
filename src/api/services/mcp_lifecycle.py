"""MCP server lifecycle management (framework-agnostic, no Streamlit dependency)."""
import atexit
import logging
import threading
from typing import Optional

logger = logging.getLogger(__name__)

# Module-level state (replaces st.session_state)
_mcp_manager = None
_mcp_url: Optional[str] = None
_mcp_lock = threading.Lock()


def get_or_start_mcp(port: int = 3000) -> Optional[object]:
    """Get existing or start new MCP server, stored as module-level variables."""
    global _mcp_manager, _mcp_url
    with _mcp_lock:
        if _mcp_manager is not None:
            return _mcp_manager

        try:
            from src.data_commons.api.mcp_server_manager import MCPServerManager

            manager = MCPServerManager(port=port)
            if manager.start(timeout=30):
                _mcp_manager = manager
                _mcp_url = manager.mcp_url
                atexit.register(_cleanup_mcp)
                logger.info("MCP server started at %s", manager.mcp_url)
                return manager
            else:
                logger.warning("MCP server failed to start")
                return None
        except ImportError:
            logger.warning("datacommons-mcp not installed")
            return None
        except Exception as e:
            logger.warning("MCP start failed: %s", e)
            return None


def stop_mcp() -> None:
    """Stop the MCP server and clear module-level state."""
    global _mcp_manager, _mcp_url

    if _mcp_manager is not None:
        logger.debug("Stopping MCP server")
        try:
            _mcp_manager.stop()
            logger.info("MCP server stopped")
        except Exception as e:
            logger.warning("Error stopping MCP server: %s", e)

    _mcp_manager = None
    _mcp_url = None


def get_mcp_url() -> Optional[str]:
    """Return MCP URL if server is running."""
    logger.debug("get_mcp_url() = %s", _mcp_url)
    return _mcp_url


def _cleanup_mcp():
    """atexit handler to stop MCP server."""
    logger.debug("atexit: cleaning up MCP server")
    try:
        stop_mcp()
    except Exception:
        pass
