"""
MCP Toolset Factory for Schema.org vocabulary.

Creates configured MCPToolset instances for use with ADK agents.
Follows the same pattern as mcp_toolset_factory.py for Data Commons.

Usage:
    from src.data_commons.api.schemaorg_mcp_toolset_factory import create_schemaorg_mcp_toolset

    toolset = create_schemaorg_mcp_toolset(mcp_url="http://localhost:3001/mcp")

    agent = LlmAgent(
        name="my_agent",
        model="gemini-2.5-pro",
        tools=[toolset]
    )
"""

import logging
from typing import Optional, List

from google.adk.tools.mcp_tool import McpToolset
from google.adk.tools.mcp_tool.mcp_session_manager import StreamableHTTPConnectionParams

logger = logging.getLogger(__name__)


def create_schemaorg_mcp_toolset(
    mcp_url: str = "http://localhost:3001/mcp",
    tool_filter: Optional[List[str]] = None,
) -> McpToolset:
    """
    Create an MCPToolset configured for Schema.org MCP server.

    The toolset provides access to schema.org vocabulary tools:
    - lookup_type: Look up schema.org types
    - lookup_property: Look up schema.org properties
    - search_vocabulary: Search for types/properties
    - validate_mapping: Check property-type compatibility
    - get_type_hierarchy: Get ancestor chain for a type

    Args:
        mcp_url: URL of the MCP server endpoint (default: "http://localhost:3001/mcp")
        tool_filter: Optional list of tool names to expose (default: all tools)

    Returns:
        Configured MCPToolset ready for use with ADK agents
    """
    logger.debug(f"Creating Schema.org MCPToolset for {mcp_url}")

    connection_params = StreamableHTTPConnectionParams(url=mcp_url)

    if tool_filter:
        logger.debug(f"Tool filter: {tool_filter}")
        toolset = McpToolset(
            connection_params=connection_params,
            tool_filter=tool_filter,
        )
    else:
        toolset = McpToolset(connection_params=connection_params)

    return toolset
