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
from typing import AsyncGenerator, ClassVar, Dict, List, Optional

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
        """Parse column names and semantic types from COLUMN REFERENCE TABLE.

        Handles both formats:
        - | Column | Type | Unique | Semantic Type |  (test format)
        - | Column Header (EXACT) | Type | Unique Values | Semantic | Sample Values |  (production format)
        """
        columns = []
        in_table = False
        semantic_col_idx = None

        for line in skeleton.split('\n'):
            line = line.strip()
            # Detect table header — look for Column + Type in same row
            if ('Column' in line) and ('Type' in line) and '|' in line:
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
                if len(parts) >= 1:
                    col_name = parts[0]
                    semantic_type = ""
                    if semantic_col_idx is not None and len(parts) > semantic_col_idx:
                        semantic_type = parts[semantic_col_idx]
                    columns.append({"name": col_name, "semantic_type": semantic_type})
            elif in_table and not line.startswith('|'):
                in_table = False

        return columns

    # Known semantic type → Schema.org property mappings
    # These are authoritative DC-to-Schema.org equivalences
    SEMANTIC_TYPE_MAPPINGS: ClassVar[Dict] = {
        "place": {
            "property": "observationAbout",
            "schemaorg": "about (from Observation) — maps to Place entities",
            "related": ["addressCountry", "containedInPlace", "geo"],
        },
        "date": {
            "property": "observationDate",
            "schemaorg": "dateCreated (from CreativeWork) — temporal observation axis",
            "related": ["datePublished", "startDate", "endDate"],
        },
        "measure": {
            "property": "value",
            "schemaorg": "value (from PropertyValue, QuantitativeValue)",
            "related": ["maxValue", "minValue", "unitText"],
        },
        "dimension": {
            "property": "variableMeasured (auto-built from dimension properties)",
            "schemaorg": "variableMeasured (from Dataset, Observation)",
            "related": ["measuredProperty", "statType"],
        },
    }

    def _lookup_column(self, column_name: str, semantic_type: str, vocab: SchemaOrgVocab) -> str:
        """Look up Schema.org property for a single column."""
        # First: use known semantic type mappings (most reliable)
        if semantic_type in self.SEMANTIC_TYPE_MAPPINGS:
            mapping = self.SEMANTIC_TYPE_MAPPINGS[semantic_type]
            lines = [
                f"- DC property: {mapping['property']}",
                f"- Schema.org equivalent: {mapping['schemaorg']}",
            ]
            # Try column-name-specific search for additional context
            search_term = column_name.replace('_', ' ').lower()
            col_results = vocab.search_properties(search_term, limit=2)
            if col_results:
                best = col_results[0]
                prop_name = best.get("name", "")
                # Only include if it's a reasonable match (not a random property)
                if any(kw in prop_name.lower() for kw in [
                    'country', 'place', 'location', 'address', 'date', 'time',
                    'value', 'number', 'amount', 'price', 'rate', 'percent',
                    'frequency', 'period', 'status', 'type', 'name', 'area',
                ]):
                    domain = best.get("domain", [])
                    domain_str = f" (from {', '.join(domain[:2])})" if domain else ""
                    lines.append(f"- Column-specific match: {prop_name}{domain_str}")
            return '\n'.join(lines)

        # Fallback: search by column name for unknown semantic types
        search_term = column_name.replace('_', ' ').lower()
        results = vocab.search_properties(search_term, limit=3)

        if not results:
            return "- No direct Schema.org match"

        best = results[0]
        prop_name = best.get("name", "")
        domain = best.get("domain", [])
        domain_str = f" (from {', '.join(domain[:2])})" if domain else ""

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
