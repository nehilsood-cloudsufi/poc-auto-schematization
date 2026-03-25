"""Data Commons API integration.

This module provides API clients for external services.

Main components:
- gemini_client: Client for Google's Gemini API
- dc_api_wrapper: Wrapper for Data Commons API
- mcp_server_manager: MCP server lifecycle management
- mcp_toolset_factory: Factory for creating ADK MCPToolset instances
"""

from src.data_commons.api.gemini_client import GeminiClient

# MCP integration (optional - may not be installed)
try:
    from src.data_commons.api.mcp_server_manager import MCPServerManager
    from src.data_commons.api.mcp_toolset_factory import (
        create_dc_mcp_toolset,
        create_search_only_toolset,
        create_observations_only_toolset
    )
    MCP_AVAILABLE = True
except ImportError:
    MCPServerManager = None
    create_dc_mcp_toolset = None
    create_search_only_toolset = None
    create_observations_only_toolset = None
    MCP_AVAILABLE = False

# dc_api_wrapper has many exports, import selectively as needed
# from src.data_commons.api.dc_api_wrapper import dc_api_batched_wrapper, dc_api_wrapper

__all__ = [
    'GeminiClient',
    'MCPServerManager',
    'create_dc_mcp_toolset',
    'create_search_only_toolset',
    'create_observations_only_toolset',
    'MCP_AVAILABLE'
]
