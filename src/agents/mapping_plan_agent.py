"""
MappingPlanAgent v2 — structured-output candidate ranker.

Runs after sampling + schema selection + candidate retrieval, before PVMAP generation.
Reads pre-retrieved candidates from state, asks Gemini to rank/refine them,
and produces a structured MappingPlan (JSON) plus a human-readable markdown summary.

ADK State Inputs:
    - skeleton_summary: str (column profiles from profiler)
    - schema_vocab_content: str (compressed vocab JSON)
    - sampled_data: str (representative sample rows)
    - statvar_summary: str (DC discovery results)
    - candidate_pool: str (JSON of per-column candidates from retrieval phase)
    - output_dir: str (where to save plan files)
    - dataset_name: str

ADK State Outputs:
    - mapping_plan: str (JSON string of the structured MappingPlan)
    - mapping_plan_json: str (same as mapping_plan — alias for downstream consumers)
"""

import json
import logging
import os
from pathlib import Path
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from google import genai

from src.api.models.plan import MappingPlan

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


def _plan_to_markdown(plan: MappingPlan) -> str:
    """Convert a structured MappingPlan to human-readable markdown.

    This is also imported by other modules (e.g. for logging / UI display).
    """
    lines: list[str] = []
    lines.append(f"# Mapping Plan: {plan.dataset_name}")
    lines.append("")

    # Dataset Understanding
    lines.append("## Dataset Understanding")
    lines.append(f"- **Archetype:** {plan.understanding.archetype}")
    lines.append(f"- **Observation grain:** {plan.understanding.observation_grain}")
    lines.append(f"- **Key insight:** {plan.understanding.key_insight}")
    lines.append("")

    # Active Column Mappings
    lines.append("## Active Column Mappings")
    lines.append("")
    for col in plan.active_columns:
        lines.append(f"### Column: `{col.column_name}`")
        lines.append(f"- **Role:** {col.role.value if hasattr(col.role, 'value') else col.role}")
        lines.append(f"- **Evidence:** {col.evidence}")
        if col.dc_match:
            lines.append(f"- **DC Match:** {col.dc_match}")
        if col.is_ambiguous:
            lines.append("- **WARNING:** This column is ambiguous")
        for i, cand in enumerate(col.candidates):
            marker = " **(selected)**" if i == col.selected_index else ""
            lines.append(
                f"  - Candidate {i + 1}{marker}: "
                f"`{cand.property}` = `{cand.value_expression}` "
                f"(confidence={cand.confidence:.2f}, source={cand.source.value if hasattr(cand.source, 'value') else cand.source}) "
                f"— {cand.reason}"
            )
        lines.append("")

    # Ignored Columns
    if plan.ignored_columns:
        lines.append("## Ignored Columns")
        lines.append("")
        for col in plan.ignored_columns:
            lines.append(f"### Column: `{col.column_name}`")
            lines.append(f"- **Role:** {col.role.value if hasattr(col.role, 'value') else col.role}")
            lines.append(f"- **Evidence:** {col.evidence}")
            lines.append("")

    # Static Properties
    if plan.static_properties:
        lines.append("## Static Properties")
        lines.append("")
        for prop in plan.static_properties:
            lines.append(f"### `{prop.property_name}`")
            for i, cand in enumerate(prop.candidates):
                marker = " **(selected)**" if i == prop.selected_index else ""
                lines.append(
                    f"  - Candidate {i + 1}{marker}: "
                    f"`{cand.property}` = `{cand.value_expression}` "
                    f"(confidence={cand.confidence:.2f}, source={cand.source.value if hasattr(cand.source, 'value') else cand.source}) "
                    f"— {cand.reason}"
                )
            lines.append("")

    # Global Notes
    if plan.global_notes:
        lines.append("## Global Notes")
        for note in plan.global_notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)


class MappingPlanAgent(BaseAgent):
    """Generates a structured mapping plan by ranking pre-retrieved candidates."""

    def __init__(self, name: str = "MappingPlanAgent", model: str = None):
        super().__init__(name=name)
        self._model_name = model or os.getenv("MAPPING_PLAN_MODEL", "gemini-3.1-pro-preview")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Generate structured mapping plan from candidate pool."""
        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text="Generating structured mapping plan...")]
        ))

        # Load prompt template
        template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt.txt"
        template = template_path.read_text()

        # Populate template from state
        skeleton = ctx.session.state.get("skeleton_summary", "")
        schema_vocab = ctx.session.state.get("schema_vocab_content", "")
        sampled_data = ctx.session.state.get("sampled_data", "")
        statvar_summary = ctx.session.state.get("statvar_summary", "")
        candidate_pool = ctx.session.state.get("candidate_pool", "")

        # Ensure candidate_pool is a JSON string
        if isinstance(candidate_pool, dict) or isinstance(candidate_pool, list):
            candidate_pool_json = json.dumps(candidate_pool, indent=2)
        else:
            candidate_pool_json = str(candidate_pool) if candidate_pool else "{}"

        populated = template.replace("{skeleton_summary}", skeleton)
        populated = populated.replace("{schema_vocab_content}", schema_vocab)
        populated = populated.replace("{sampled_data}", sampled_data)
        populated = populated.replace("{statvar_summary}", statvar_summary)
        populated = populated.replace("{candidate_pool_json}", candidate_pool_json)

        dataset_name = ctx.session.state.get("dataset_name", "unknown")

        # Generate structured plan via LLM
        plan = await self._generate_plan(populated, dataset_name)

        # Serialize to JSON
        plan_json = plan.model_dump_json(indent=2)

        # Save to state
        ctx.session.state["mapping_plan"] = plan_json
        ctx.session.state["mapping_plan_json"] = plan_json

        # Save to disk
        output_dir = Path(ctx.session.state.get("output_dir", "."))
        output_dir.mkdir(parents=True, exist_ok=True)

        # JSON is the source of truth
        json_path = output_dir / "mapping_plan.json"
        json_path.write_text(plan_json)

        # Markdown for human-readable logs
        md_text = _plan_to_markdown(plan)
        md_path = output_dir / "mapping_plan.md"
        md_path.write_text(md_text)

        logger.info(
            "Mapping plan generated for %s (%d chars JSON, %d chars MD), saved to %s",
            dataset_name, len(plan_json), len(md_text), output_dir,
        )

        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text=(
                f"Structured mapping plan generated ({len(plan_json)} chars). "
                f"Saved to {json_path} and {md_path}"
            ))]
        ))

    async def _generate_plan(self, prompt: str, dataset_name: str) -> MappingPlan:
        """Call Gemini with structured output to generate the mapping plan."""
        client = genai.Client()

        # Build the JSON schema from the Pydantic model for Gemini structured output
        plan_schema = MappingPlan.model_json_schema()

        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=plan_schema,
            ),
        )

        # Parse via Pydantic for validation
        try:
            plan = MappingPlan.model_validate_json(response.text)
        except Exception as e:
            logger.error("Failed to parse structured output: %s. Raw: %s", e, response.text[:500])
            raise

        return plan


__all__ = ["MappingPlanAgent", "_plan_to_markdown"]
