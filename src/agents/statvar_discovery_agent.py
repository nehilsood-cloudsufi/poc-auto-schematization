"""
StatVar Discovery Agent for MCP-based pre-generation discovery.

Discovers existing Data Commons StatVars that may match the dataset,
and stores them in session state for PVMAPGenerationAgent to use.

This is a BaseAgent (not LlmAgent) that:
1. Reads dataset metadata from session state
2. Queries MCP for relevant existing StatVars
3. Stores discoveries in session state
4. PVMAPGenerationAgent reads and injects into prompt
"""

from pathlib import Path
from typing import AsyncGenerator, Optional, List, Dict
import sys
import logging

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

logger = logging.getLogger(__name__)


class StatVarDiscoveryAgent(BaseAgent):
    """
    Agent for discovering StatVars via MCP before PVMAP generation.

    ADK State Inputs:
        - current_dataset: DatasetInfo
        - mcp_enabled: bool
        - mcp_url: str
        - sampled_data_content: str (from session state, NOT full data)
        - metadata_content: str (from session state)
        - data_context: Dict (from SamplingAgent - column_roles, dimensions, statvar_pattern)

    ADK State Outputs:
        - discovered_statvars: List[dict]
        - statvar_summary: str (for injection into prompt)
        - discovery_success: bool
    """

    def __init__(self, name: str = "StatVarDiscoveryAgent", model: str = "gemini-2.5-pro"):
        super().__init__(name=name)
        self._model = model

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Run StatVar discovery using MCP."""
        # 1. Check if MCP is enabled
        mcp_enabled = ctx.session.state.get("mcp_enabled", False)
        if not mcp_enabled:
            ctx.session.state["discovery_success"] = True
            ctx.session.state["discovered_statvars"] = []
            ctx.session.state["statvar_summary"] = ""
            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text="StatVar discovery skipped (MCP not enabled)")]
            ))
            return

        # 2. Get dataset info
        current_dataset = ctx.session.state.get("current_dataset")
        if not current_dataset:
            ctx.session.state["discovery_success"] = False
            ctx.session.state["error"] = "No current_dataset in state"
            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text="Discovery failed: No dataset")]
            ))
            return

        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text=f"Discovering StatVars for {current_dataset.name}...")]
        ))

        # 3. Extract search terms from metadata and sampled data (uses data_context if available)
        search_terms = self._extract_search_terms(current_dataset, ctx)
        logger.info(f"Extracted search terms: {search_terms}")

        # 4. Get data context for enhanced discovery
        data_context = ctx.session.state.get("data_context", {})
        if data_context:
            logger.info(f"Using data_context: population={data_context.get('population_type')}, "
                       f"dimensions={data_context.get('dimension_columns')}")

        # 5. Get sampled data preview from session state (first few rows only)
        sampled_data_preview = self._get_sampled_data_preview(ctx)

        # 6. Query MCP via DCQueryAgent
        mcp_url = ctx.session.state.get("mcp_url", "http://localhost:3000/mcp")

        try:
            from src.agents.dc_query_agent import create_dc_query_agent
            from google.adk import Runner
            from google.adk.sessions import InMemorySessionService
            import uuid

            # Create discovery agent with specific instruction (includes data_context)
            discovery_agent = create_dc_query_agent(
                mcp_url=mcp_url,
                model=self._model,
                name="StatVarHelper",
                instruction=self._build_discovery_instruction(search_terms, sampled_data_preview, data_context)
            )

            # Run discovery query
            runner = Runner(
                app_name="statvar_discovery",
                agent=discovery_agent,
                session_service=InMemorySessionService(),
                auto_create_session=True
            )

            session_id = f"discovery_{uuid.uuid4().hex[:8]}"
            query = f"Search for statistical variables related to: {', '.join(search_terms[:5])}"
            user_message = types.Content(parts=[types.Part(text=query)])

            result_text = ""
            for event in runner.run(user_id="discovery", session_id=session_id, new_message=user_message):
                if hasattr(event, 'content') and event.content:
                    for part in event.content.parts:
                        if hasattr(part, 'text') and part.text:
                            result_text += part.text

            # 6. Parse and store results
            discovered = self._parse_statvars(result_text)

            ctx.session.state["discovered_statvars"] = discovered
            ctx.session.state["statvar_summary"] = result_text
            ctx.session.state["discovery_success"] = True

            logger.info(f"Discovered {len(discovered)} StatVars")

            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text=f"Discovered {len(discovered)} relevant StatVars")]
            ))

        except Exception as e:
            logger.warning(f"StatVar discovery failed: {e}")
            ctx.session.state["discovery_success"] = False
            ctx.session.state["discovered_statvars"] = []
            ctx.session.state["statvar_summary"] = ""
            ctx.session.state["error"] = str(e)

            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text=f"Discovery failed (continuing without): {str(e)[:100]}")]
            ))

    def _extract_search_terms(self, dataset, ctx) -> List[str]:
        """
        Extract search terms from session state using P+M+C formula when data_context is available.

        P+M+C = Population + MeasuredProperty + Constraints (dimensions)
        """
        terms = [dataset.name.replace('_', ' ')]

        # 1. Use data_context if available (preferred - uses P+M+C formula)
        data_context = ctx.session.state.get("data_context", {})
        if data_context:
            # Population type (e.g., Person, Household, Worker)
            population_type = data_context.get("population_type", "")
            if population_type:
                terms.append(population_type)

            # Measurement type from statvar_pattern
            statvar_pattern = data_context.get("statvar_pattern", "")
            if statvar_pattern:
                # Extract measurement from pattern like "Count_Person_{Gender}"
                pattern_parts = statvar_pattern.split('_')
                if pattern_parts:
                    terms.append(pattern_parts[0])  # e.g., "Count", "Mean", "Rate"

            # Dimension values (constraints) - add unique values from each dimension
            dimension_domains = data_context.get("dimension_domains", {})
            for dim_name, values in dimension_domains.items():
                # Add dimension name
                terms.append(dim_name.replace('_', ' '))
                # Add some dimension values for specificity
                for val in values[:3]:  # First 3 values per dimension
                    if val and str(val).lower() not in ['total', 'all', 'both', 'none']:
                        terms.append(str(val))

            # Also add dimension column names
            dimension_columns = data_context.get("dimension_columns", [])
            for col in dimension_columns:
                terms.append(col.replace('_', ' '))

            logger.info(f"Using data_context for search terms: population={population_type}, pattern={statvar_pattern}")

        # 2. Fallback: Get metadata content from session state
        metadata_content = ctx.session.state.get("metadata_content", "")
        if metadata_content:
            for line in metadata_content.split('\n')[:20]:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    key, value = parts[0].strip(), parts[1].strip()
                    if key.lower() in ['datasetname', 'source', 'country', 'unit']:
                        terms.append(value)

        # 3. Fallback: Get SAMPLED data content from session state (not full data)
        if not data_context:
            sampled_data_content = ctx.session.state.get("sampled_data_content", "")
            if sampled_data_content:
                header_line = sampled_data_content.split('\n')[0] if sampled_data_content else ""
                if header_line:
                    columns = [col.strip().replace('_', ' ') for col in header_line.split(',')]
                    # Filter out generic columns
                    meaningful_cols = [c for c in columns if len(c) > 2 and c.lower() not in ['id', 'date', 'year', 'value', 'obs']]
                    terms.extend(meaningful_cols[:5])

        # Deduplicate and limit
        unique_terms = list(dict.fromkeys(terms))  # Preserve order, remove duplicates
        return unique_terms[:15]  # Increased limit when using data_context

    def _get_sampled_data_preview(self, ctx) -> str:
        """Get first few rows of SAMPLED data from session state (not full data)."""
        sampled_data_content = ctx.session.state.get("sampled_data_content", "")
        if not sampled_data_content:
            return ""

        # Return first 6 lines (header + 5 data rows)
        lines = sampled_data_content.split('\n')[:6]
        return '\n'.join(lines)

    def _build_discovery_instruction(self, search_terms: List[str], sampled_data_preview: str = "", data_context: Dict = None) -> str:
        """
        Build instruction for the discovery agent.

        Uses P+M+C formula (Population + MeasuredProperty + Constraints) when data_context is available.
        """
        instruction = f"""You discover existing Data Commons statistical variables that EXACTLY match the dataset.

Search for variables related to: {', '.join(search_terms)}
"""

        # Add context-aware guidance if available
        if data_context:
            population_type = data_context.get("population_type", "")
            statvar_pattern = data_context.get("statvar_pattern", "")
            dimension_columns = data_context.get("dimension_columns", [])
            dimension_domains = data_context.get("dimension_domains", {})

            instruction += f"""
**Dataset Context (P+M+C Formula):**
- Population Type: {population_type or 'Unknown'}
- StatVar Pattern: {statvar_pattern or 'Unknown'}
- Dimension Columns: {', '.join(dimension_columns) if dimension_columns else 'None detected'}
"""
            if dimension_domains:
                instruction += "- Dimension Values:\n"
                for dim, values in dimension_domains.items():
                    instruction += f"  - {dim}: {', '.join(str(v) for v in values[:5])}\n"

            instruction += """
**Search Strategy (use P+M+C formula):**
1. First search: "{measurement} {population}" (e.g., "Count Person")
2. Then narrow: "{measurement} {population} {constraint}" (e.g., "Count Person Male")
3. Try combinations with dimension values for specific StatVars
"""

        if sampled_data_preview:
            instruction += f"""
Sample data columns (from sampled data, not full dataset):
{sampled_data_preview}
"""
        instruction += """
Use the search_indicators MCP tool.

IMPORTANT: Only report variables that are EXACT or VERY CLOSE matches to the dataset.
- Do NOT include "related" or "similar" variables from different sources
- If the exact variable is not found, say "No exact matches found" instead of listing alternatives
- Only list variables that could directly replace the dataset's statistical measure

Report found variables in this format:
- DCID: <variable_dcid>
  Description: <brief description>
  Match confidence: HIGH/MEDIUM (only include HIGH or MEDIUM matches)

List up to 5 most relevant EXACT matches. Be selective and concise."""
        return instruction

    def _parse_statvars(self, text: str) -> List[Dict]:
        """Parse StatVar DCIDs from discovery output."""
        statvars = []
        lines = text.split('\n')
        current_dcid = None

        for line in lines:
            line = line.strip()
            if 'DCID:' in line or 'dcid:' in line:
                # Extract DCID
                parts = line.split(':', 1)
                if len(parts) > 1:
                    current_dcid = parts[1].strip()
                    statvars.append({'dcid': current_dcid, 'description': ''})
            elif current_dcid and ('Description:' in line or 'description:' in line):
                parts = line.split(':', 1)
                if len(parts) > 1 and statvars:
                    statvars[-1]['description'] = parts[1].strip()

        return statvars
