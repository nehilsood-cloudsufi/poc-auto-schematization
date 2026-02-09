"""
DC Query Agent for Data Commons MCP integration.

This module centralizes ALL MCP query logic for the pipeline:
1. Base query agent (generic DC queries)
2. Enrichment agent (loop-aware StatVar discovery)
3. Error resolver agent (post-validation error resolution)
4. Shared helpers (run_mcp_query, parse_statvars)

Usage:
    from src.agents.dc_query_agent import create_dc_query_agent, create_enrichment_agent
    from src.data_commons.api.mcp_server_manager import MCPServerManager

    with MCPServerManager() as mcp:
        agent = create_dc_query_agent(mcp_url=mcp.mcp_url)

        # Use with ADK Runner
        runner = Runner(agent=agent, ...)
        result = runner.run(user_message="Find population variables for California")
"""

import logging
import re
import sys
import uuid
from pathlib import Path
from typing import Optional, List, Dict

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import LlmAgent

from src.data_commons.api.mcp_toolset_factory import create_dc_mcp_toolset

logger = logging.getLogger(__name__)

# =============================================================================
# Instruction Templates
# =============================================================================

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

# Enrichment: Broad discovery (attempt 0)
ENRICHMENT_BROAD_INSTRUCTION = """You discover existing Data Commons statistical variables for a dataset.

Your goal: Find StatVars that EXACTLY match what this dataset measures.

{context_section}

**Search Strategy (P+M+C formula):**
1. Start broad: Search for "{{measurement}} {{population}}" (e.g., "Count Person")
2. Narrow with dimensions: "{{measurement}} {{population}} {{constraint}}" (e.g., "Count Person Male")
3. Use `places` parameter when the dataset has known place types (e.g., US states)
4. Try `get_observations` for top matches to validate they return data for the dataset's places/dates

**Output Format:**
For each discovered variable:
- DCID: <variable_dcid>
  Name: <human readable name>
  Description: <brief description>
  Match confidence: HIGH/MEDIUM
  Observation check: <CONFIRMED if get_observations returned data, UNCHECKED otherwise>

List up to 10 most relevant matches. Be selective and concise.
Only include HIGH or MEDIUM confidence matches."""

# Enrichment: Error-driven refinement (attempt 1+)
ENRICHMENT_REFINEMENT_INSTRUCTION = """You refine Data Commons StatVar discovery based on validation errors.

The previous PVMAP generation attempt failed or had low quality.
Use the error context below to make TARGETED MCP queries.

{context_section}

**Previous Validation Error:**
{validation_error}

**Previous Error Feedback:**
{error_feedback}

**Refinement Strategy:**
1. Identify which StatVars were incorrectly mapped or missing
2. Search for correct DCIDs using error context clues
3. If "key not found" errors: search for variables matching those column names
4. If "observationAbout" errors: search for place-related variables
5. Use `get_observations` to CONFIRM found variables return data for known places
6. If no better matches found, say so clearly - don't force incorrect matches

**Output Format:**
- DCID: <variable_dcid>
  Name: <human readable name>
  Description: <brief description>
  Match confidence: HIGH/MEDIUM
  Fixes: <which error this resolves>

List only variables that ADDRESS the errors. Be precise."""

# Error resolver: Post-validation targeted resolution
ERROR_RESOLVER_INSTRUCTION = """You resolve PVMAP validation errors using Data Commons queries.

A PVMAP was generated but validation failed. Classify the errors and make targeted queries.

**Validation Error:**
{validation_error}

**Current PVMAP (that failed):**
```csv
{pvmap_csv}
```

**Error Classification & Resolution:**

1. **StatVar naming errors** (wrong DCID format):
   - Search for correct DCIDs using search_indicators
   - Example: "Count_Person_Female" might need to be "dcid:Count_Person_Female"

2. **Place resolution errors** (observationAbout mapping wrong):
   - Search for place-related variables to understand expected DCID format
   - Use get_observations with a sample place DCID to confirm data exists

3. **Missing property errors** (required properties not mapped):
   - Identify which properties are missing from error
   - Search for similar StatVars to see their property patterns

4. **Value format errors** (wrong data type):
   - Check if numeric vs string handling is correct
   - Verify observation format matches DC expectations

**Output:**
For each error resolved:
- Error: <original error description>
  Resolution: <what the correct mapping should be>
  DCID: <correct DCID if applicable>
  Evidence: <what MCP query confirmed this>

Be specific and actionable. Only suggest fixes backed by MCP query results."""

# MCP tools instruction for the generator (injected when MCP enabled)
MCP_TOOLS_INSTRUCTION = """
## Live Data Commons Tools

You have DIRECT ACCESS to Data Commons MCP tools during generation:

1. **search_indicators(query, places?, parent_place?)**: Search for StatVar DCIDs
   - Use when you need to verify a StatVar DCID exists
   - Use when you're unsure about the correct DCID naming convention

2. **get_observations(variable_dcid, place_dcid, date?)**: Fetch real data
   - Use to validate that a StatVar+Place combination returns data
   - Use to check the expected data format

**When to use these tools:**
- Uncertain about a StatVar DCID: Call search_indicators
- Want to verify your mapping: Call get_observations with a sample place
- Error feedback mentions unknown DCIDs: Search for correct ones

**When NOT to use:**
- You're confident in standard DCIDs (Count_Person, etc.)
- The dataset is pre-formatted Data Commons data (passthrough mapping)
"""


# =============================================================================
# Base Agent Factory (unchanged)
# =============================================================================

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


# =============================================================================
# Enrichment Agent Factory (NEW - loop-aware discovery)
# =============================================================================

def create_enrichment_agent(
    mcp_url: str,
    model: str = "gemini-2.5-pro",
    data_context: Optional[dict] = None,
    attempt: int = 0,
    error_feedback: str = "",
    validation_error: str = "",
) -> LlmAgent:
    """
    Create MCP agent with attempt-aware instruction.

    - attempt 0: broad discovery using data_context P+M+C formula
    - attempt 1+: error-driven refinement using validation errors

    Args:
        mcp_url: URL of the MCP server endpoint
        model: Gemini model to use
        data_context: Data context from SamplingAgent (column_roles, dimensions, etc.)
        attempt: Current retry attempt number (0-based)
        error_feedback: Error feedback from previous attempt
        validation_error: Validation error from previous attempt

    Returns:
        Configured LlmAgent for enrichment queries
    """
    context_section = _build_context_section(data_context) if data_context else ""

    if attempt == 0:
        # Broad discovery
        instruction = ENRICHMENT_BROAD_INSTRUCTION.replace(
            "{context_section}", context_section
        )
        name = "EnrichmentBroad"
    else:
        # Error-driven refinement
        instruction = ENRICHMENT_REFINEMENT_INSTRUCTION.replace(
            "{context_section}", context_section
        ).replace(
            "{validation_error}", validation_error or "(no validation error)"
        ).replace(
            "{error_feedback}", error_feedback or "(no error feedback)"
        )
        name = f"EnrichmentRefine_{attempt}"

    logger.info(f"Creating enrichment agent: {name} (attempt={attempt})")

    mcp_toolset = create_dc_mcp_toolset(mcp_url=mcp_url)

    return LlmAgent(
        name=name,
        model=model,
        instruction=instruction,
        tools=[mcp_toolset]
    )


# =============================================================================
# Error Resolver Agent Factory (NEW - post-validation resolution)
# =============================================================================

def create_error_resolver_agent(
    mcp_url: str,
    model: str = "gemini-2.5-pro",
    validation_error: str = "",
    pvmap_csv: str = "",
) -> LlmAgent:
    """
    Create MCP agent for post-validation error resolution.

    Classifies errors and makes targeted MCP queries to resolve them.

    Args:
        mcp_url: URL of the MCP server endpoint
        model: Gemini model to use
        validation_error: The validation error to resolve
        pvmap_csv: Current PVMAP CSV that failed validation

    Returns:
        Configured LlmAgent for error resolution
    """
    instruction = ERROR_RESOLVER_INSTRUCTION.replace(
        "{validation_error}", validation_error or "(no validation error)"
    ).replace(
        "{pvmap_csv}", pvmap_csv or "(no PVMAP available)"
    )

    logger.info("Creating error resolver agent")

    mcp_toolset = create_dc_mcp_toolset(mcp_url=mcp_url)

    return LlmAgent(
        name="ErrorResolver",
        model=model,
        instruction=instruction,
        tools=[mcp_toolset]
    )


# =============================================================================
# Shared Helpers
# =============================================================================

async def run_mcp_query(mcp_url: str, agent: LlmAgent, query: str) -> str:
    """
    Run an MCP agent query and collect text results.

    Shared helper that creates a Runner, sends the query, and
    collects all text output from events.

    Args:
        mcp_url: URL of the MCP server (for logging)
        agent: Configured LlmAgent with MCP tools
        query: User message to send to the agent

    Returns:
        Concatenated text from all response events
    """
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

    runner = Runner(
        app_name="mcp_query",
        agent=agent,
        session_service=InMemorySessionService(),
        auto_create_session=True
    )

    session_id = f"mcp_{uuid.uuid4().hex[:8]}"
    user_message = types.Content(parts=[types.Part(text=query)])

    result_text = ""
    try:
        for event in runner.run(
            user_id="mcp_user",
            session_id=session_id,
            new_message=user_message
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        result_text += part.text
    except Exception as e:
        logger.warning(f"MCP query failed: {e}")
        result_text = f"(MCP query failed: {str(e)[:200]})"

    return result_text


def parse_statvars(text: str) -> List[Dict]:
    """
    Parse StatVar DCIDs from discovery output.

    Handles multiple output formats:
    - DCID: <value> / Description: <value> / Match confidence: HIGH/MEDIUM
    - Bullet list format: - <dcid> - <description>

    Args:
        text: Raw text output from discovery agent

    Returns:
        List of dicts with keys: dcid, description, confidence
    """
    statvars = []
    lines = text.split('\n')
    current = {}

    for line in lines:
        line = line.strip()

        # Match "DCID: <value>" or "- DCID: <value>"
        dcid_match = re.match(r'^[-*]?\s*DCID:\s*(.+)', line, re.IGNORECASE)
        if dcid_match:
            if current.get('dcid'):
                statvars.append(current)
            current = {'dcid': dcid_match.group(1).strip(), 'description': '', 'confidence': 'MEDIUM'}
            continue

        # Match "Description: <value>" or "Name: <value>"
        desc_match = re.match(r'^[-*]?\s*(?:Description|Name):\s*(.+)', line, re.IGNORECASE)
        if desc_match and current.get('dcid'):
            current['description'] = desc_match.group(1).strip()
            continue

        # Match "Match confidence: HIGH/MEDIUM"
        conf_match = re.match(r'^[-*]?\s*Match confidence:\s*(HIGH|MEDIUM|LOW)', line, re.IGNORECASE)
        if conf_match and current.get('dcid'):
            current['confidence'] = conf_match.group(1).upper()
            continue

        # Match "Fixes: <value>"
        fixes_match = re.match(r'^[-*]?\s*Fixes:\s*(.+)', line, re.IGNORECASE)
        if fixes_match and current.get('dcid'):
            current['fixes'] = fixes_match.group(1).strip()
            continue

        # Match "Observation check: <value>"
        obs_match = re.match(r'^[-*]?\s*Observation check:\s*(.+)', line, re.IGNORECASE)
        if obs_match and current.get('dcid'):
            current['observation_check'] = obs_match.group(1).strip()
            continue

    # Don't forget last entry
    if current.get('dcid'):
        statvars.append(current)

    return statvars


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


# =============================================================================
# Legacy convenience factories (kept for backward compatibility)
# =============================================================================

def create_statvar_discovery_agent(
    mcp_url: str = "http://localhost:3000/mcp",
    model: str = "gemini-2.5-pro"
) -> LlmAgent:
    """Create an agent specialized for discovering StatVars."""
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
    """Create an agent specialized for fetching observations."""
    return create_dc_query_agent(
        mcp_url=mcp_url,
        model=model,
        name="ObservationFetchAgent",
        instruction=OBSERVATION_FETCH_INSTRUCTION
    )


# =============================================================================
# Legacy helper (kept for backward compatibility)
# =============================================================================

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
    """
    from google.adk import Runner
    from google.adk.sessions import InMemorySessionService
    from google.genai import types

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


# =============================================================================
# Module exports
# =============================================================================

__all__ = [
    # Base
    'create_dc_query_agent',
    'DC_QUERY_AGENT_INSTRUCTION',
    # Enrichment (loop-aware)
    'create_enrichment_agent',
    'ENRICHMENT_BROAD_INSTRUCTION',
    'ENRICHMENT_REFINEMENT_INSTRUCTION',
    # Error resolver
    'create_error_resolver_agent',
    'ERROR_RESOLVER_INSTRUCTION',
    # Shared helpers
    'run_mcp_query',
    'parse_statvars',
    # MCP tools instruction for generator
    'MCP_TOOLS_INSTRUCTION',
    # Legacy
    'create_statvar_discovery_agent',
    'create_observation_fetch_agent',
    'discover_statvars_for_topic',
]
