"""
MCP Toolset Factory for Data Commons.

Creates configured MCPToolset instances for use with ADK agents.

Usage:
    from src.data_commons.api.mcp_toolset_factory import create_dc_mcp_toolset

    # Create toolset for MCP server
    toolset = create_dc_mcp_toolset(mcp_url="http://localhost:3000/mcp")

    # Use with an agent
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


def create_dc_mcp_toolset(
    mcp_url: str = "http://localhost:3000/mcp",
    tool_filter: Optional[List[str]] = None
) -> McpToolset:
    """
    Create an MCPToolset configured for Data Commons MCP server.

    The toolset provides access to Data Commons MCP tools:
    - search_indicators: Search for statistical variables and topics
    - get_observations: Fetch statistical data for variables and places

    Args:
        mcp_url: URL of the MCP server endpoint (default: "http://localhost:3000/mcp")
        tool_filter: Optional list of tool names to expose (default: all tools)
                    Example: ['search_indicators'] to only expose search

    Returns:
        Configured MCPToolset ready for use with ADK agents

    Example:
        ```python
        from src.data_commons.api.mcp_toolset_factory import create_dc_mcp_toolset
        from google.adk.agents import LlmAgent

        toolset = create_dc_mcp_toolset()

        agent = LlmAgent(
            name="dc_agent",
            model="gemini-2.5-pro",
            instruction="Query Data Commons for statistical data.",
            tools=[toolset]
        )
        ```
    """
    logger.debug(f"Creating MCPToolset for {mcp_url}")

    connection_params = StreamableHTTPConnectionParams(url=mcp_url)

    if tool_filter:
        logger.debug(f"Tool filter: {tool_filter}")
        toolset = McpToolset(
            connection_params=connection_params,
            tool_filter=tool_filter
        )
    else:
        toolset = McpToolset(connection_params=connection_params)

    return toolset


def create_search_only_toolset(
    mcp_url: str = "http://localhost:3000/mcp"
) -> McpToolset:
    """
    Create an MCPToolset with only the search_indicators tool.

    Useful for agents that only need to discover StatVars,
    not fetch actual observations.

    Args:
        mcp_url: URL of the MCP server endpoint

    Returns:
        MCPToolset with only search_indicators exposed
    """
    return create_dc_mcp_toolset(
        mcp_url=mcp_url,
        tool_filter=['search_indicators']
    )


def create_observations_only_toolset(
    mcp_url: str = "http://localhost:3000/mcp"
) -> McpToolset:
    """
    Create an MCPToolset with only the get_observations tool.

    Useful for agents that need to fetch data for known DCIDs,
    not discover new variables.

    Args:
        mcp_url: URL of the MCP server endpoint

    Returns:
        MCPToolset with only get_observations exposed
    """
    return create_dc_mcp_toolset(
        mcp_url=mcp_url,
        tool_filter=['get_observations']
    )
