"""
StatVar Discovery Agent for MCP-based pre-generation discovery.

Loop-aware agent that discovers existing Data Commons StatVars.
On attempt 0, performs broad discovery. On attempt 1+, uses validation
errors to drive refined MCP queries.

Delegates all MCP query logic to dc_query_agent.py (centralized).

ADK State Inputs:
    - current_dataset: DatasetInfo
    - mcp_enabled: bool
    - mcp_url: str
    - attempt_number: int (from StatePrep)
    - data_context: Dict (from SamplingAgent)
    - error_feedback: str (from FeedbackAgent, attempt 1+)
    - validation_error: str (from ValidationAgent, attempt 1+)

ADK State Outputs:
    - discovered_statvars: List[dict]
    - statvar_summary: str (for injection into prompt)
    - discovery_success: bool
    - mcp_enrichment_context: dict (structured discovery results)
"""

import os
from pathlib import Path
from typing import AsyncGenerator
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
    Loop-aware agent for discovering StatVars via MCP.

    When placed inside the retry loop:
    - attempt 0: Broad discovery using data_context P+M+C formula
    - attempt 1+: Error-driven refinement using validation errors

    When placed outside the loop (legacy): Always does broad discovery.
    """

    def __init__(self, name: str = "StatVarDiscoveryAgent", model: str = None):
        super().__init__(name=name)
        self._model = model or os.getenv("STATVAR_DISCOVERY_MODEL", "gemini-3-flash-preview")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Run StatVar discovery using MCP."""
        # 1. Check if MCP is enabled
        mcp_enabled = ctx.session.state.get("mcp_enabled", False)
        if not mcp_enabled:
            ctx.session.state["discovery_success"] = True
            ctx.session.state["discovered_statvars"] = []
            ctx.session.state["statvar_summary"] = ""
            ctx.session.state["mcp_enrichment_context"] = {}
            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text="StatVar discovery skipped (MCP not enabled)")]
            ))
            return

        # 2. Get dataset info
        current_dataset = ctx.session.state.get("current_dataset")
        if not current_dataset:
            ctx.session.state["discovery_success"] = False
            ctx.session.state["error"] = "No current_dataset in state"
            ctx.session.state["mcp_enrichment_context"] = {}
            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text="Discovery failed: No dataset")]
            ))
            return

        # 3. Get attempt number for loop-awareness
        attempt = ctx.session.state.get("attempt_number", 0)
        mcp_url = ctx.session.state.get("mcp_url", "http://localhost:3000/mcp")
        data_context = ctx.session.state.get("data_context", {})

        if attempt == 0:
            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text=f"Discovering StatVars for {current_dataset.name} (broad discovery)...")]
            ))
        else:
            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text=f"Refining StatVar discovery for {current_dataset.name} (attempt {attempt + 1}, error-driven)...")]
            ))

        # 4. Get error context for attempt 1+ (loop-aware refinement)
        error_feedback = ctx.session.state.get("error_feedback", "") if attempt > 0 else ""
        validation_error = ctx.session.state.get("validation_error", "") if attempt > 0 else ""

        # 5. Query MCP via dc_query_agent factories
        try:
            from src.agents.dc_query_agent import (
                create_enrichment_agent,
                run_mcp_query,
                parse_statvars,
                build_structured_summary,
            )

            # Create attempt-aware enrichment agent
            enrichment_agent = create_enrichment_agent(
                mcp_url=mcp_url,
                model=self._model,
                data_context=data_context,
                attempt=attempt,
                error_feedback=error_feedback,
                validation_error=validation_error,
            )

            # Build query based on attempt
            if attempt == 0:
                search_terms = self._extract_search_terms(current_dataset, ctx)
                place_samples = self._extract_place_samples(ctx)
                query = f"Search for statistical variables related to: {', '.join(search_terms[:5])}"
                if place_samples:
                    query += f". Dataset places include: {', '.join(place_samples[:5])}"
                    query += ". Use these as the 'places' parameter in search_indicators."
            else:
                query = (
                    f"Refine StatVar discovery for {current_dataset.name}. "
                    f"Previous attempt {attempt} had errors. "
                    f"Find correct DCIDs to fix the issues."
                )

            # Run the query
            result_text = await run_mcp_query(mcp_url, enrichment_agent, query)

            # Parse results and build structured summary
            discovered = parse_statvars(result_text)
            structured_summary = build_structured_summary(discovered)

            # Build enrichment context (structured)
            enrichment_context = {
                "attempt": attempt,
                "discovered_count": len(discovered),
                "statvars": discovered,
                "raw_summary": result_text[:2000],  # Truncate for state
                "mode": "broad" if attempt == 0 else "refinement",
            }

            # Update state — use structured summary instead of raw text
            ctx.session.state["discovered_statvars"] = discovered
            ctx.session.state["statvar_summary"] = structured_summary or result_text
            ctx.session.state["discovery_success"] = True
            ctx.session.state["mcp_enrichment_context"] = enrichment_context

            logger.info(f"Discovered {len(discovered)} StatVars (attempt={attempt})")

            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text=f"Discovered {len(discovered)} relevant StatVars (attempt {attempt + 1})")]
            ))

        except Exception as e:
            logger.warning(f"StatVar discovery failed: {e}")
            ctx.session.state["discovery_success"] = False
            ctx.session.state["discovered_statvars"] = []
            ctx.session.state["statvar_summary"] = ""
            ctx.session.state["mcp_enrichment_context"] = {}
            ctx.session.state["error"] = str(e)

            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text=f"Discovery failed (continuing without): {str(e)[:100]}")]
            ))

    def _extract_place_samples(self, ctx) -> list:
        """
        Extract sample place values from data_context for place-aware queries.

        Looks at column_roles to find place columns, then extracts sample values
        from dimension_domains.

        Returns:
            List of place name strings (up to 5)
        """
        data_context = ctx.session.state.get("data_context", {})
        if not data_context:
            return []

        place_samples = []
        column_roles = data_context.get("column_roles", {})
        place_columns = [col for col, role in column_roles.items() if role == "place"]

        for col in place_columns:
            domain_vals = data_context.get("dimension_domains", {}).get(col, [])
            place_samples.extend(str(v) for v in domain_vals[:3])

        # Deduplicate
        return list(dict.fromkeys(place_samples))[:5]

    def _extract_search_terms(self, dataset, ctx) -> list:
        """
        Extract search terms from session state using P+M+C formula when data_context is available.

        P+M+C = Population + MeasuredProperty + Constraints (dimensions)
        """
        terms = [dataset.name.replace('_', ' ')]

        # 1. Use data_context if available (preferred - uses P+M+C formula)
        data_context = ctx.session.state.get("data_context", {})
        if data_context:
            population_type = data_context.get("population_type", "")
            if population_type:
                terms.append(population_type)

            statvar_pattern = data_context.get("statvar_pattern", "")
            if statvar_pattern:
                pattern_parts = statvar_pattern.split('_')
                if pattern_parts:
                    terms.append(pattern_parts[0])

            dimension_domains = data_context.get("dimension_domains", {})
            for dim_name, values in dimension_domains.items():
                terms.append(dim_name.replace('_', ' '))
                for val in values[:3]:
                    if val and str(val).lower() not in ['total', 'all', 'both', 'none']:
                        terms.append(str(val))

            dimension_columns = data_context.get("dimension_columns", [])
            for col in dimension_columns:
                terms.append(col.replace('_', ' '))

        # 2. Fallback: metadata content
        metadata_content = ctx.session.state.get("metadata_content", "")
        if metadata_content:
            for line in metadata_content.split('\n')[:20]:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    key, value = parts[0].strip(), parts[1].strip()
                    if key.lower() in ['datasetname', 'source', 'country', 'unit']:
                        terms.append(value)

        # 3. Fallback: sampled data headers
        if not data_context:
            sampled_data_content = ctx.session.state.get("sampled_data_content", "")
            if sampled_data_content:
                header_line = sampled_data_content.split('\n')[0] if sampled_data_content else ""
                if header_line:
                    columns = [col.strip().replace('_', ' ') for col in header_line.split(',')]
                    meaningful_cols = [c for c in columns if len(c) > 2 and c.lower() not in ['id', 'date', 'year', 'value', 'obs']]
                    terms.extend(meaningful_cols[:5])

        # Deduplicate and limit
        unique_terms = list(dict.fromkeys(terms))
        return unique_terms[:15]
