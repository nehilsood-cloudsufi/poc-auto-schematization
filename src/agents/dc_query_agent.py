"""
DC Query Agent for Data Commons MCP integration.

This agent uses MCP tools to query the Data Commons knowledge graph
for statistical variables and observations.

Use Cases:
1. Pre-generation StatVar discovery - find existing variables before PVMAP generation
2. Place resolution - validate and resolve place names
3. Schema validation - verify StatVar definitions against DC schema
4. Live data comparison - compare generated observations with DC data

Usage:
    from src.agents.dc_query_agent import create_dc_query_agent
    from src.data_commons.api.mcp_server_manager import MCPServerManager

    with MCPServerManager() as mcp:
        agent = create_dc_query_agent(mcp_url=mcp.mcp_url)

        # Use with ADK Runner
        runner = Runner(agent=agent, ...)
        result = runner.run(user_message="Find population variables for California")
"""

import logging
import sys
from pathlib import Path
from typing import Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import LlmAgent

from src.data_commons.api.mcp_toolset_factory import create_dc_mcp_toolset

logger = logging.getLogger(__name__)

# Default instruction for DC Query Agent
DC_QUERY_AGENT_INSTRUCTION = """You are a Data Commons expert assistant. Your role is to help
discover and query statistical data from the Data Commons knowledge graph.

You have access to MCP tools for querying Data Commons:

1. **search_indicators**: Search for statistical variables (StatVars) and topics
   - Use this to find what variables are available for a given topic or place
   - Parameters: query (required), places (optional), parent_place (optional)
   - Example: Search for "population" indicators for "California, USA"

2. **get_observations**: Fetch actual statistical data
   - Use this AFTER finding valid DCIDs from search_indicators
   - Parameters: variable_dcid (required), place_dcid (required), date (optional)
   - Example: Get observations for Count_Person in geoId/06 (California)

**CRITICAL WORKFLOW**:
1. ALWAYS call search_indicators FIRST to discover valid variable DCIDs
2. NEVER guess DCIDs - they must come from search results
3. Then use those DCIDs with get_observations to fetch data

**Place DCIDs**:
- US states: geoId/XX (e.g., geoId/06 for California)
- US counties: geoId/XXXXX (e.g., geoId/06075 for San Francisco)
- Countries: country/XXX (e.g., country/USA, country/IND)
- World: Earth

**Response Format**:
- Report exact DCIDs you found (e.g., Count_Person, UnemploymentRate_Person)
- Include values and dates for observations
- Be concise but include key data points
- If no results found, suggest alternative searches
"""

# Shorter instruction for specific use cases
STATVAR_DISCOVERY_INSTRUCTION = """You discover existing Data Commons statistical variables.

Use search_indicators to find variables matching the query.
Report only the variable DCIDs and brief descriptions.
Be concise - list format preferred.
"""

OBSERVATION_FETCH_INSTRUCTION = """You fetch statistical data from Data Commons.

Use search_indicators first to find the correct variable DCID.
Then use get_observations to fetch the data.
Report the value, date, and place for each observation.
"""


def create_dc_query_agent(
    mcp_url: str = "http://localhost:3000/mcp",
    model: str = "gemini-2.5-pro",
    name: str = "DCQueryAgent",
    instruction: Optional[str] = None,
    data_context: Optional[dict] = None
) -> LlmAgent:
    """
    Create a Data Commons Query Agent with MCP tools.

    This agent can query the Data Commons knowledge graph to:
    - Discover existing statistical variables
    - Fetch observations for known variables
    - Validate DCIDs and place names

    Args:
        mcp_url: URL of the MCP server endpoint
        model: Gemini model to use (default: gemini-2.5-pro)
        name: Agent name (default: "DCQueryAgent")
        instruction: Custom instruction (default: DC_QUERY_AGENT_INSTRUCTION)
        data_context: Optional data context from SamplingAgent for enhanced queries

    Returns:
        Configured LlmAgent with MCP tools

    Example:
        ```python
        from src.agents.dc_query_agent import create_dc_query_agent
        from google.adk import Runner

        agent = create_dc_query_agent()
        runner = Runner(agent=agent, ...)

        result = runner.run(
            user_message="Find unemployment rate variables for US states"
        )
        ```
    """
    logger.debug(f"Creating DC Query Agent with MCP URL: {mcp_url}")

    mcp_toolset = create_dc_mcp_toolset(mcp_url=mcp_url)

    # Build instruction with data_context if provided
    final_instruction = instruction or DC_QUERY_AGENT_INSTRUCTION

    if data_context and not instruction:
        # Enhance default instruction with data context
        context_section = _build_context_section(data_context)
        final_instruction = DC_QUERY_AGENT_INSTRUCTION + context_section

    agent = LlmAgent(
        name=name,
        model=model,
        instruction=final_instruction,
        tools=[mcp_toolset]
    )

    return agent


def _build_context_section(data_context: dict) -> str:
    """Build instruction section from data_context for enhanced queries."""
    if not data_context:
        return ""

    population_type = data_context.get("population_type", "")
    statvar_pattern = data_context.get("statvar_pattern", "")
    dimension_columns = data_context.get("dimension_columns", [])
    dimension_domains = data_context.get("dimension_domains", {})

    section = """

**Dataset Context (P+M+C Formula for StatVar Discovery):**
Use this context to build more targeted queries.
"""

    if population_type:
        section += f"- Population Type: {population_type}\n"
    if statvar_pattern:
        section += f"- Expected StatVar Pattern: {statvar_pattern}\n"
    if dimension_columns:
        section += f"- Dimension Columns: {', '.join(dimension_columns)}\n"
    if dimension_domains:
        section += "- Dimension Values:\n"
        for dim, values in dimension_domains.items():
            section += f"  - {dim}: {', '.join(str(v) for v in values[:5])}\n"

    section += """
**Query Strategy:**
1. Start broad: Search for "{measurement_type} {population_type}"
2. Add constraints: Include dimension values like gender, age, sector
3. Example: "Count Person Male" or "Mean Wage Rural"
"""

    return section


def create_statvar_discovery_agent(
    mcp_url: str = "http://localhost:3000/mcp",
    model: str = "gemini-2.5-pro"
) -> LlmAgent:
    """
    Create an agent specialized for discovering StatVars.

    This agent is optimized for finding existing Data Commons variables
    that match dataset columns, useful before PVMAP generation.

    Args:
        mcp_url: URL of the MCP server endpoint
        model: Gemini model to use

    Returns:
        LlmAgent configured for StatVar discovery
    """
    return create_dc_query_agent(
        mcp_url=mcp_url,
        model=model,
        name="StatVarDiscoveryAgent",
        instruction=STATVAR_DISCOVERY_INSTRUCTION
    )


def create_observation_fetch_agent(
    mcp_url: str = "http://localhost:3000/mcp",
    model: str = "gemini-2.5-pro"
) -> LlmAgent:
    """
    Create an agent specialized for fetching observations.

    This agent is optimized for retrieving statistical data
    for known variables and places.

    Args:
        mcp_url: URL of the MCP server endpoint
        model: Gemini model to use

    Returns:
        LlmAgent configured for observation fetching
    """
    return create_dc_query_agent(
        mcp_url=mcp_url,
        model=model,
        name="ObservationFetchAgent",
        instruction=OBSERVATION_FETCH_INSTRUCTION
    )


# Helper functions for common queries

async def discover_statvars_for_topic(
    topic: str,
    mcp_url: str = "http://localhost:3000/mcp",
    model: str = "gemini-2.5-pro",
    data_context: Optional[dict] = None
) -> str:
    """
    Discover StatVars related to a topic.

    Convenience function that creates an agent, runs a query,
    and returns the result.

    Args:
        topic: Topic to search for (e.g., "population", "unemployment", "GDP")
        mcp_url: URL of the MCP server endpoint
        model: Gemini model to use
        data_context: Optional data context from SamplingAgent for enhanced queries

    Returns:
        String containing discovered StatVar DCIDs and descriptions
    """
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types
    import uuid

    # Create agent with data_context if available
    if data_context:
        agent = create_dc_query_agent(
            mcp_url=mcp_url,
            model=model,
            name="StatVarDiscoveryAgent",
            instruction=STATVAR_DISCOVERY_INSTRUCTION,
            data_context=data_context
        )
    else:
        agent = create_statvar_discovery_agent(mcp_url=mcp_url, model=model)

    runner = Runner(
        app_name="statvar_discovery",
        agent=agent,
        session_service=InMemorySessionService(),
        auto_create_session=True
    )

    session_id = f"discover_{uuid.uuid4().hex[:8]}"

    # Build enhanced query if data_context is available
    query_text = f"Find statistical variables related to: {topic}. List the DCIDs."
    if data_context:
        population_type = data_context.get("population_type", "")
        dimension_columns = data_context.get("dimension_columns", [])
        if population_type or dimension_columns:
            query_text = (f"Find statistical variables related to: {topic}. "
                         f"Population type: {population_type or 'Unknown'}. "
                         f"Dimensions: {', '.join(dimension_columns) if dimension_columns else 'None'}. "
                         f"List the DCIDs.")

    user_message = types.Content(
        parts=[types.Part(text=query_text)]
    )

    result_text = ""
    for event in runner.run(
        user_id="discovery",
        session_id=session_id,
        new_message=user_message
    ):
        if hasattr(event, 'content') and event.content:
            for part in event.content.parts:
                if hasattr(part, 'text') and part.text:
                    result_text += part.text

    return result_text
