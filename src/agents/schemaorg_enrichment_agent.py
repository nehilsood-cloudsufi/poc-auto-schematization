"""
SchemaOrgEnrichmentAgent — programmatic Schema.org per-column lookups.

Runs before MappingPlanAgent to enrich state with real Schema.org property
matches for each column. Uses the local SchemaOrgVocab cache (instant, no network).

ADK State Inputs:
    - skeleton_summary: str (column profiles from profiler)
    - schema_category: str (selected schema category)

ADK State Outputs:
    - schemaorg_column_mappings: str (formatted markdown — per-column findings)
"""

import logging
from typing import AsyncGenerator, Dict, List, Optional

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

logger = logging.getLogger(__name__)


class SchemaOrgEnrichmentAgent(BaseAgent):
    """Programmatic Schema.org per-column lookups using local cache."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        skeleton = ctx.session.state.get("skeleton_summary", "")
        schema_category = ctx.session.state.get("schema_category", "")

        if not skeleton:
            ctx.session.state["schemaorg_column_mappings"] = ""
            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text="Schema.org enrichment skipped (no skeleton)")]
            ))
            return

        result = self._enrich_columns(skeleton, schema_category)
        ctx.session.state["schemaorg_column_mappings"] = result

        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text=f"Schema.org enrichment complete ({len(result)} chars)")]
        ))

    def _enrich_columns(self, skeleton: str, schema_category: str) -> str:
        """Run Schema.org lookups for all columns in skeleton."""
        columns = self._parse_columns(skeleton)
        if not columns:
            return ""

        vocab = SchemaOrgVocab.instance()
        column_results = {}

        for col in columns:
            result = self._lookup_column(col["name"], col["semantic_type"], vocab)
            column_results[col["name"]] = result

        return self._format_results(column_results)

    def _parse_columns(self, skeleton: str) -> List[Dict[str, str]]:
        """Parse column names and semantic types from COLUMN REFERENCE TABLE."""
        columns = []
        in_table = False

        for line in skeleton.split('\n'):
            line = line.strip()
            if 'Column' in line and 'Type' in line and '|' in line:
                in_table = True
                continue
            if in_table and line.startswith('|') and set(line.replace('|', '').strip()) <= {'-'}:
                continue
            if in_table and line.startswith('|'):
                parts = [p.strip() for p in line.split('|') if p.strip()]
                if len(parts) >= 1:
                    col_name = parts[0]
                    semantic_type = parts[3] if len(parts) > 3 else ""
                    columns.append({"name": col_name, "semantic_type": semantic_type})
            elif in_table and not line.startswith('|'):
                in_table = False

        return columns

    def _lookup_column(self, column_name: str, semantic_type: str, vocab: SchemaOrgVocab) -> str:
        """Look up Schema.org property for a single column."""
        search_term = column_name.replace('_', ' ').lower()
        results = vocab.search_properties(search_term, limit=3)

        if not results:
            # Try semantic type as fallback
            if semantic_type == "place":
                results = vocab.search_properties("address country location", limit=3)
            elif semantic_type == "date":
                results = vocab.search_properties("date observation", limit=3)
            elif semantic_type == "measure":
                results = vocab.search_properties("value number amount", limit=3)

        if not results:
            return "- No direct Schema.org match"

        best = results[0]
        prop_name = best.get("name", "")
        domain = best.get("domain", [])
        domain_str = f" (from {', '.join(domain[:2])})" if domain else ""

        # Get range info
        prop_detail = vocab.get_property(prop_name)
        range_types = []
        if prop_detail:
            range_types = prop_detail.get("rangeIncludes", [])

        lines = [f"- Schema.org property: {prop_name}{domain_str}"]
        if range_types:
            lines.append(f"- Expected type: {' or '.join(range_types[:3])}")

        return '\n'.join(lines)

    def _format_results(self, column_results: Dict[str, str]) -> str:
        """Format all column results as markdown."""
        lines = []
        for col_name, result in column_results.items():
            lines.append(f"### {col_name}")
            lines.append(result)
            lines.append("")
        return '\n'.join(lines)
