"""
MappingPlanAgent — generates a rich mapping plan with per-column reasoning.

Runs after sampling + schema selection, before PVMAP generation.
Produces a markdown plan that the user reviews and approves.

ADK State Inputs:
    - skeleton_summary: str (column profiles from profiler)
    - schema_category: str (selected schema category)
    - schema_vocab_content: str (compressed vocab JSON)
    - sampled_data: str (representative sample rows)
    - statvar_summary: str (DC discovery results)
    - per_column_dc_matches: str (per-column DC matches)
    - output_dir: str (where to save plan file)
    - dataset_name: str

ADK State Outputs:
    - mapping_plan: str (full markdown plan)
"""

import logging
import os
from pathlib import Path
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from google import genai

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


class MappingPlanAgent(BaseAgent):
    """Generates a rich mapping plan with per-column reasoning before PVMAP generation."""

    def __init__(self, name: str = "MappingPlanAgent", model: str = None):
        super().__init__(name=name)
        self._model_name = model or os.getenv("MAPPING_PLAN_MODEL", "gemini-3.1-pro-preview")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Generate mapping plan from profiler data and DC discovery."""
        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text="Generating mapping plan...")]
        ))

        # Load prompt template
        template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt.txt"
        template = template_path.read_text()

        # Populate template from state
        skeleton = ctx.session.state.get("skeleton_summary", "")
        schema_category = ctx.session.state.get("schema_category", "")
        schema_vocab = ctx.session.state.get("schema_vocab_content", "")
        sampled_data = ctx.session.state.get("sampled_data", "")
        statvar_summary = ctx.session.state.get("statvar_summary", "")
        per_column_dc = ctx.session.state.get("per_column_dc_matches", "")
        schemaorg_mappings = ctx.session.state.get("schemaorg_column_mappings", "")

        logger.info("MappingPlanAgent: schemaorg_column_mappings = %d chars, first 200: %s",
                    len(schemaorg_mappings), schemaorg_mappings[:200])

        populated = template.replace("{skeleton_summary}", skeleton)
        populated = populated.replace("{schema_category}", schema_category)
        populated = populated.replace("{schema_vocab_content}", schema_vocab)
        populated = populated.replace("{sampled_data}", sampled_data)
        populated = populated.replace("{statvar_summary}", statvar_summary)
        populated = populated.replace("{per_column_dc_matches}", str(per_column_dc))
        populated = populated.replace("{schemaorg_column_mappings}", schemaorg_mappings)

        # Generate plan via LLM
        plan_text = await self._generate_plan(populated)

        # Post-process: inject Schema.org data into plan columns
        # The LLM often writes "N/A" for Schema.org fields despite instructions.
        # We programmatically replace these with the actual enrichment data.
        # Re-read from state in case enrichment agent updated it after our initial read
        schemaorg_mappings = ctx.session.state.get("schemaorg_column_mappings", "")
        if schemaorg_mappings:
            plan_text = self._inject_schemaorg_into_plan(plan_text, schemaorg_mappings)

        # Save to state
        ctx.session.state["mapping_plan"] = plan_text

        # Save to disk
        output_dir = Path(ctx.session.state.get("output_dir", "."))
        output_dir.mkdir(parents=True, exist_ok=True)
        plan_path = output_dir / "mapping_plan.md"
        plan_path.write_text(plan_text)

        dataset_name = ctx.session.state.get("dataset_name", "unknown")
        logger.info("Mapping plan generated for %s (%d chars), saved to %s",
                    dataset_name, len(plan_text), plan_path)

        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text=f"Mapping plan generated ({len(plan_text)} chars). Saved to {plan_path}")]
        ))

    @staticmethod
    def _normalize_col(name: str) -> str:
        """Normalize a column name for matching: strip backticks, whitespace, lowercase."""
        return name.strip().strip('`').strip().lower()

    @staticmethod
    def _col_prefix(name: str) -> str:
        """Extract the prefix before the first colon (e.g., 'REF_AREA' from 'REF_AREA:Reference area')."""
        return name.split(':')[0].strip().lower()

    def _match_enrichment_col(self, plan_col: str, col_values: dict) -> str | None:
        """Find matching enrichment value for a plan column name.

        Matching strategy (in priority order):
        1. Exact match (case-insensitive, backtick-stripped)
        2. Either name starts with the other (handles truncated/extended names)
        3. Colon-prefix match (e.g., 'REF_AREA' matches 'REF_AREA:Reference area')
        """
        plan_norm = self._normalize_col(plan_col)
        plan_prefix = self._col_prefix(plan_col)

        for enrich_col, value in col_values.items():
            enrich_norm = self._normalize_col(enrich_col)
            enrich_prefix = self._col_prefix(enrich_col)

            # 1. Exact match (case-insensitive)
            if enrich_norm == plan_norm:
                return value

            # 2. Either starts with the other (handles truncated/extended names)
            if plan_norm.startswith(enrich_norm) or enrich_norm.startswith(plan_norm):
                return value

            # 3. Colon-prefix match (bidirectional)
            if plan_prefix == enrich_prefix and plan_prefix:
                return value

        return None

    def _inject_schemaorg_into_plan(self, plan_text: str, schemaorg_mappings: str) -> str:
        """Post-process plan to replace Schema.org N/A fields with real data.

        Parses the enrichment data to build a column->schema_info map,
        then replaces "**Schema.org:** N/A" lines in the plan where
        the preceding column header matches.
        """
        import re

        # Parse enrichment data: ### COLUMN_NAME or ### `COLUMN_NAME`
        col_schema = {}
        current_col = None
        for line in schemaorg_mappings.split('\n'):
            if line.startswith('### '):
                current_col = line[4:].strip().strip('`')
            elif current_col and line.strip().startswith('- '):
                if 'No direct Schema.org match' in line:
                    continue  # Leave as N/A
                if current_col not in col_schema:
                    col_schema[current_col] = []
                col_schema[current_col].append(line.strip()[2:])  # Strip "- "

        if not col_schema:
            return plan_text

        # Format each column's Schema.org data as a single-line value
        col_values = {}
        for col, info_lines in col_schema.items():
            col_values[col] = " / ".join(info_lines)

        # Replace in plan: find "### Column: `COL_NAME`" followed by "**Schema.org:** N/A"
        lines = plan_text.split('\n')
        result = []
        current_plan_col = None
        injected = 0

        for line in lines:
            # Detect column header: ### Column: `COL_NAME`
            if line.strip().startswith('### Column:'):
                match = re.search(r'`([^`]+)`', line)
                if match:
                    current_plan_col = match.group(1)

            # Replace Schema.org N/A if we have data for this column
            if current_plan_col and '**Schema.org:**' in line and 'N/A' in line:
                schema_value = self._match_enrichment_col(current_plan_col, col_values)
                if schema_value:
                    line = line.replace('N/A', schema_value)
                    injected += 1
                    logger.debug("Injected Schema.org for %s: %s", current_plan_col, schema_value[:80])

            result.append(line)

        logger.info("Schema.org post-injection: %d/%d columns injected, plan has %d lines",
                    injected, len(col_values), len(result))

        return '\n'.join(result)

    async def _generate_plan(self, prompt: str) -> str:
        """Call LLM to generate the mapping plan."""
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192,
            ),
        )
        return response.text


__all__ = ["MappingPlanAgent"]
