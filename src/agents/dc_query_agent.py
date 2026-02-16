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
from google.genai import types as genai_types

from src.data_commons.api.mcp_toolset_factory import create_dc_mcp_toolset
from src.agents.prompt_loader import load_prompt_json
from src.agents.retry_config import create_resilient_model
from src.agents.template_utils import sanitize_for_adk

# DC query / MCP agents use a fast model with thinking disabled to reduce
# latency on the many repeated tool-calling round-trips.
_DC_AGENT_MODEL = "gemini-3-flash-preview"
_NO_THINKING = genai_types.GenerateContentConfig(
    thinking_config=genai_types.ThinkingConfig(thinking_level="low"),
)

logger = logging.getLogger(__name__)

# =============================================================================
# Instruction Templates (loaded from src/resources/prompts/dc_query_instructions.json)
# =============================================================================

_DC_INSTRUCTIONS = load_prompt_json("dc_query_instructions.json")

DC_QUERY_AGENT_INSTRUCTION = _DC_INSTRUCTIONS["dc_query_agent"]
STATVAR_DISCOVERY_INSTRUCTION = _DC_INSTRUCTIONS["statvar_discovery"]
OBSERVATION_FETCH_INSTRUCTION = _DC_INSTRUCTIONS["observation_fetch"]
ENRICHMENT_BROAD_INSTRUCTION = _DC_INSTRUCTIONS["enrichment_broad"]
ENRICHMENT_REFINEMENT_INSTRUCTION = _DC_INSTRUCTIONS["enrichment_refinement"]
ERROR_RESOLVER_INSTRUCTION = _DC_INSTRUCTIONS["error_resolver"]
MCP_TOOLS_INSTRUCTION = _DC_INSTRUCTIONS["mcp_tools"]


# =============================================================================
# Base Agent Factory (unchanged)
# =============================================================================

def create_dc_query_agent(
    mcp_url: str = "http://localhost:3000/mcp",
    model: str = _DC_AGENT_MODEL,
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
        model=create_resilient_model(model),
        instruction=sanitize_for_adk(final_instruction),
        tools=[mcp_toolset],
        include_contents="none",  # Prevent history accumulation in MCP queries
        generate_content_config=_NO_THINKING,
    )

    return agent


# =============================================================================
# Enrichment Agent Factory (NEW - loop-aware discovery)
# =============================================================================

def create_enrichment_agent(
    mcp_url: str,
    model: str = _DC_AGENT_MODEL,
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
        model=create_resilient_model(model),
        instruction=sanitize_for_adk(instruction),
        tools=[mcp_toolset],
        include_contents="none",  # Prevent history accumulation in MCP queries
        generate_content_config=_NO_THINKING,
    )


# =============================================================================
# Error Resolver Agent Factory (NEW - post-validation resolution)
# =============================================================================

def create_error_resolver_agent(
    mcp_url: str,
    model: str = _DC_AGENT_MODEL,
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
        model=create_resilient_model(model),
        instruction=sanitize_for_adk(instruction),
        tools=[mcp_toolset],
        include_contents="none",  # Prevent history accumulation in MCP queries
        generate_content_config=_NO_THINKING,
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
    finally:
        # Close MCP toolsets to prevent session leak warnings
        for tool in getattr(agent, 'tools', []) or []:
            if hasattr(tool, 'close') and callable(tool.close):
                try:
                    await tool.close()
                except Exception:
                    pass

    return result_text


def parse_statvars(text: str) -> List[Dict]:
    """
    Parse StatVar DCIDs from discovery output.

    Handles multiple output formats:
    - DCID: <value> / Description: <value> / Match confidence: HIGH/MEDIUM
    - Properties: populationType=X, measuredProperty=Y, ...
    - Place types: Country|State|County|...
    - Copy-Paste PVMAP Reference: <DCID>: prop1,val1,...
    - Bullet list format: - <dcid> - <description>

    Args:
        text: Raw text output from discovery agent

    Returns:
        List of dicts with keys: dcid, description, confidence, properties,
        place_types, pvmap_reference, observation_check, fixes
    """
    statvars = []
    lines = text.split('\n')
    current = {}
    in_pvmap_ref = False
    pvmap_ref_lines = []

    for line in lines:
        line = line.strip()

        # Detect Copy-Paste PVMAP Reference section header
        if re.match(r'^[-*]?\s*\**Copy-Paste PVMAP Reference\**:?\s*$', line, re.IGNORECASE):
            in_pvmap_ref = True
            continue

        # Collect PVMAP reference lines (DCID: prop,val,prop,val format)
        if in_pvmap_ref:
            if line and not line.startswith('- DCID:') and not line.startswith('DCID:'):
                pvmap_ref_lines.append(line)
                continue
            else:
                in_pvmap_ref = False
                # Fall through to normal parsing

        # Match "DCID: <value>" or "- DCID: <value>"
        dcid_match = re.match(r'^[-*]?\s*DCID:\s*(.+)', line, re.IGNORECASE)
        if dcid_match:
            if current.get('dcid'):
                statvars.append(current)
            current = {
                'dcid': dcid_match.group(1).strip(),
                'description': '',
                'confidence': 'MEDIUM',
                'properties': {},
                'place_types': [],
                'pvmap_reference': '',
                'observation_check': '',
            }
            continue

        # Match "Description: <value>" or "Name: <value>"
        desc_match = re.match(r'^[-*]?\s*(?:Description|Name):\s*(.+)', line, re.IGNORECASE)
        if desc_match and current.get('dcid'):
            current['description'] = desc_match.group(1).strip()
            continue

        # Match "Properties: populationType=X, measuredProperty=Y, ..."
        props_match = re.match(r'^[-*]?\s*Properties:\s*(.+)', line, re.IGNORECASE)
        if props_match and current.get('dcid'):
            props_str = props_match.group(1).strip()
            props = {}
            for pair in props_str.split(','):
                pair = pair.strip()
                if '=' in pair:
                    k, v = pair.split('=', 1)
                    props[k.strip()] = v.strip()
            current['properties'] = props
            continue

        # Match "Place types: Country|State|County|..."
        place_match = re.match(r'^[-*]?\s*Place types?:\s*(.+)', line, re.IGNORECASE)
        if place_match and current.get('dcid'):
            place_str = place_match.group(1).strip()
            current['place_types'] = [p.strip() for p in re.split(r'[|,]', place_str) if p.strip()]
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

        # Match "Verification: <value>"
        ver_match = re.match(r'^[-*]?\s*Verification:\s*(.+)', line, re.IGNORECASE)
        if ver_match and current.get('dcid'):
            current['observation_check'] = ver_match.group(1).strip()
            continue

    # Don't forget last entry
    if current.get('dcid'):
        statvars.append(current)

    # Attach PVMAP reference lines to matching statvars
    for ref_line in pvmap_ref_lines:
        ref_match = re.match(r'^(.+?):\s*(.+)$', ref_line)
        if ref_match:
            ref_dcid = ref_match.group(1).strip()
            ref_mapping = ref_match.group(2).strip()
            for sv in statvars:
                if sv['dcid'] == ref_dcid:
                    sv['pvmap_reference'] = ref_mapping
                    break

    return statvars


def build_structured_summary(statvars: List[Dict]) -> str:
    """
    Build a structured markdown summary from parsed StatVars.

    Creates a prompt-friendly summary with:
    1. Copy-Paste Reference section for PVMAP generation
    2. Details section with DCID, confidence, observation status
    3. Summary counts

    Args:
        statvars: List of parsed StatVar dicts from parse_statvars()

    Returns:
        Formatted markdown string for injection into PVMAP prompt
    """
    if not statvars:
        return ""

    lines = []
    high_count = sum(1 for sv in statvars if sv.get('confidence') == 'HIGH')
    confirmed_count = sum(1 for sv in statvars if 'CONFIRMED' in sv.get('observation_check', '').upper())

    lines.append(f"Found {len(statvars)} relevant StatVars ({high_count} HIGH confidence, {confirmed_count} observation-confirmed).")
    lines.append("")

    # Section 1: Copy-Paste PVMAP Reference
    refs = [sv for sv in statvars if sv.get('pvmap_reference') or sv.get('properties')]
    if refs:
        lines.append("### Copy-Paste Reference for PVMAP")
        for sv in refs:
            dcid = sv['dcid']
            if sv.get('pvmap_reference'):
                lines.append(f"- {dcid}: {sv['pvmap_reference']}")
            elif sv.get('properties'):
                props = sv['properties']
                pairs = ','.join(f"{k},{v}" for k, v in props.items())
                lines.append(f"- {dcid}: {pairs}")
        lines.append("")

    # Section 2: Details
    lines.append("### StatVar Details")
    for sv in statvars:
        dcid = sv['dcid']
        conf = sv.get('confidence', 'MEDIUM')
        obs = sv.get('observation_check', 'UNCHECKED')
        desc = sv.get('description', '')
        places = ', '.join(sv.get('place_types', [])) if sv.get('place_types') else ''

        detail = f"- **{dcid}** [{conf}]"
        if obs:
            detail += f" — {obs}"
        if desc:
            detail += f"\n  {desc}"
        if places:
            detail += f"\n  Place types: {places}"
        lines.append(detail)

    return '\n'.join(lines)


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
1. Start broad: Search for "[measurement_type] [population_type]"
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
    try:
        for event in runner.run(
            user_id="discovery",
            session_id=session_id,
            new_message=user_message
        ):
            if hasattr(event, 'content') and event.content:
                for part in event.content.parts:
                    if hasattr(part, 'text') and part.text:
                        result_text += part.text
    except Exception as e:
        logger.warning(f"StatVar discovery failed: {e}")
        result_text = f"(StatVar discovery failed: {str(e)[:200]})"
    finally:
        # Close MCP toolsets to prevent session leak warnings
        for tool in getattr(agent, 'tools', []) or []:
            if hasattr(tool, 'close') and callable(tool.close):
                try:
                    await tool.close()
                except Exception:
                    pass

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
    'build_structured_summary',
    # MCP tools instruction for generator
    'MCP_TOOLS_INSTRUCTION',
    # Legacy
    'create_statvar_discovery_agent',
    'create_observation_fetch_agent',
    'discover_statvars_for_topic',
]
