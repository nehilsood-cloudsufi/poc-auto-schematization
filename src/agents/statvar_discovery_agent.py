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
            ctx.session.state["per_column_dc_matches"] = ""
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

            # Per-column DC matches — execute real queries if MCP enabled
            skeleton = ctx.session.state.get("skeleton_summary", "")
            per_column_queries = self._build_per_column_queries(skeleton)
            if per_column_queries and mcp_url:
                per_column_matches = await self._execute_per_column_queries(
                    per_column_queries, mcp_url=mcp_url, max_queries=3
                )
            else:
                per_column_matches = {pq["column"]: [] for pq in per_column_queries}

            ctx.session.state["per_column_dc_matches"] = self._format_per_column_matches(per_column_matches)

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
            ctx.session.state["per_column_dc_matches"] = ""
            ctx.session.state["error"] = str(e)

            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text=f"Discovery failed (continuing without): {str(e)[:100]}")]
            ))

    async def _execute_per_column_queries(
        self, queries: list, mcp_url: str, max_queries: int = 3
    ) -> dict:
        """
        Execute actual MCP queries for top N columns.

        Prioritizes: measure > dimension > place columns.
        Returns dict mapping column names to lists of DC match dicts.
        """
        from src.agents.dc_query_agent import (
            create_enrichment_agent,
            run_mcp_query,
            parse_statvars,
        )

        priority = {"measure": 0, "dimension": 1, "place": 2}
        sorted_queries = sorted(queries, key=lambda q: priority.get(q["semantic_type"], 9))
        top_queries = sorted_queries[:max_queries]

        matches = {q["column"]: [] for q in queries}

        for pq in top_queries:
            try:
                enrichment_agent = create_enrichment_agent(
                    mcp_url=mcp_url,
                    model=self._model,
                    data_context={},
                    attempt=0,
                    error_feedback="",
                    validation_error="",
                )
                result_text = await run_mcp_query(mcp_url, enrichment_agent, pq["query"])
                discovered = parse_statvars(result_text)
                matches[pq["column"]] = discovered
                logger.info("Per-column DC query for %s: found %d matches", pq["column"], len(discovered))
            except Exception as e:
                logger.warning("Per-column DC query failed for %s: %s", pq["column"], e)
                matches[pq["column"]] = []

        return matches

    def _build_per_column_queries(self, skeleton_summary: str) -> list:
        """
        Parse skeleton_summary to build per-column DC search queries.

        Extracts column names and semantic types from the COLUMN REFERENCE TABLE,
        then builds a search query for each non-trivial column.

        Returns:
            List of dicts: [{"column": str, "query": str, "semantic_type": str}]
        """
        if not skeleton_summary:
            return []

        queries = []
        in_table = False
        semantic_col_idx = None

        for line in skeleton_summary.split('\n'):
            line = line.strip()
            # Detect table header
            if 'Column' in line and 'Type' in line and '|' in line:
                in_table = True
                # Find which column index has "Semantic"
                header_parts = [p.strip().lower() for p in line.split('|') if p.strip()]
                for i, h in enumerate(header_parts):
                    if 'semantic' in h:
                        semantic_col_idx = i
                        break
                continue
            # Skip separator
            if in_table and line.startswith('|') and set(line.replace('|', '').strip()) <= {'-'}:
                continue
            # Parse table rows
            if in_table and line.startswith('|'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 3:
                    col_name = parts[0]
                    semantic_type = ""
                    if semantic_col_idx is not None and len(parts) > semantic_col_idx:
                        semantic_type = parts[semantic_col_idx]

                    search_term = col_name.replace('_', ' ')
                    if semantic_type in ('measure', 'dimension'):
                        queries.append({
                            "column": col_name,
                            "query": f"Search for statistical variables related to: {search_term}",
                            "semantic_type": semantic_type,
                        })
                    elif semantic_type == 'place':
                        queries.append({
                            "column": col_name,
                            "query": f"Search for place types matching: {search_term}",
                            "semantic_type": semantic_type,
                        })
            elif in_table and not line.startswith('|'):
                in_table = False

        return queries

    def _format_per_column_matches(self, matches: dict) -> str:
        """
        Format per-column DC matches as a readable string for the plan agent.

        Args:
            matches: Dict mapping column names to lists of DC match dicts

        Returns:
            Formatted string
        """
        if not matches:
            return "No per-column DC matches available."

        lines = []
        for col_name, col_matches in matches.items():
            if col_matches:
                match_strs = []
                for m in col_matches:
                    dcid = m.get("dcid", "")
                    name = m.get("name", "")
                    relevance = m.get("relevance", "")
                    match_strs.append(f"  - {dcid} ({name}) [relevance: {relevance}]")
                lines.append(f"### {col_name}")
                lines.extend(match_strs)
            else:
                lines.append(f"### {col_name}")
                lines.append("  - No DC matches found")

        return '\n'.join(lines)

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
