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

import asyncio
import json
import logging
import os
from pathlib import Path
from typing import AsyncGenerator

from pydantic import PrivateAttr

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

    # Executive Summary (v4)
    if hasattr(plan.understanding, 'executive_summary') and plan.understanding.executive_summary:
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(plan.understanding.executive_summary)
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
        if hasattr(col, 'purpose') and col.purpose:
            lines.append(f"- **Purpose:** {col.purpose}")
        if hasattr(col, 'narrative') and col.narrative:
            lines.append(f"- **Narrative:** {col.narrative}")
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
            if hasattr(col, 'purpose') and col.purpose:
                lines.append(f"- **Purpose:** {col.purpose}")
            if hasattr(col, 'narrative') and col.narrative:
                lines.append(f"- **Narrative:** {col.narrative}")
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

    # --- Enriched plan sections (only present on EnrichedMappingPlan) ---

    # Composite Key
    if hasattr(plan, "composite_key") and plan.composite_key:
        lines.append("## Composite Key")
        lines.append(", ".join(f"`{k}`" for k in plan.composite_key))
        lines.append("")

    # StatVar Blueprint
    if hasattr(plan, "statvar_blueprint") and plan.statvar_blueprint:
        bp = plan.statvar_blueprint
        lines.append("## StatVar Blueprint")
        lines.append("")
        lines.append("**Base properties:**")
        for prop in bp.base_properties:
            lines.append(f"- `{prop.name}` = `{prop.value}`")
        if bp.constraint_columns:
            lines.append(f"- **Constraint columns:** {', '.join(f'`{c}`' for c in bp.constraint_columns)}")
        if bp.measure_columns:
            lines.append(f"- **Measure columns:** {', '.join(f'`{c}`' for c in bp.measure_columns)}")
        lines.append("")

    # Value Dictionaries
    if hasattr(plan, "value_dictionaries") and plan.value_dictionaries:
        lines.append("## Value Dictionaries")
        lines.append("")
        for vd in plan.value_dictionaries:
            lines.append(f"### {vd.column_name}")
            lines.append(f"DC property: `{vd.dc_property}`")
            lines.append("")
            lines.append("| Raw Value | Action | DCID | Reason |")
            lines.append("|-----------|--------|------|--------|")
            for m in vd.mappings:
                dcid_str = m.dcid if m.dcid else "—"
                lines.append(f"| {m.raw_value} | {m.action} | {dcid_str} | {m.reason} |")
            lines.append("")

    # Column Relationships (filter out "independent" type)
    if hasattr(plan, "column_relationships") and plan.column_relationships:
        meaningful = [r for r in plan.column_relationships if r.relationship.value != "independent"]
        if meaningful:
            lines.append("## Column Relationships")
            lines.append("")
            lines.append("| Column A | Relationship | Column B | Evidence |")
            lines.append("|----------|-------------|----------|----------|")
            for rel in meaningful:
                lines.append(
                    f"| {rel.column_a} | {rel.relationship.value} | {rel.column_b} | {rel.evidence} |"
                )
            lines.append("")

    # Place Resolution
    if hasattr(plan, "place_resolution") and plan.place_resolution:
        pr = plan.place_resolution
        lines.append("## Place Resolution")
        lines.append(f"- **Column:** `{pr.column_name}`")
        lines.append(f"- **Format:** {pr.format_detected}")
        lines.append(f"- **Prefix rule:** `{pr.prefix_rule}`")
        if pr.pad_zeros is not None:
            lines.append(f"- **Pad zeros:** {pr.pad_zeros}")
        lines.append(f"- **Resolution rate:** {pr.resolution_rate}")
        lines.append("")

    # Time Resolution
    if hasattr(plan, "time_resolution") and plan.time_resolution:
        tr = plan.time_resolution
        lines.append("## Time Resolution")
        lines.append(f"- **Columns:** {', '.join(f'`{c}`' for c in tr.columns)}")
        lines.append(f"- **Format:** {tr.format_detected}")
        lines.append(f"- **Normalization rule:** {tr.normalization_rule}")
        lines.append("")

    # Indicator Columns
    if hasattr(plan, "indicator_columns") and plan.indicator_columns:
        lines.append("## Indicator Columns")
        lines.append("")
        lines.append("These columns change the core StatVar definition per-value (not just add a constraint).")
        lines.append("")
        for ic in plan.indicator_columns:
            lines.append(f"### `{ic.column_name}`")
            lines.append("")
            lines.append("| Value | populationType | measuredProperty | statType | Reason |")
            lines.append("|-------|---------------|-----------------|----------|--------|")
            for ivm in ic.value_mappings:
                lines.append(f"| `{ivm.raw_value}` | `{ivm.population_type}` | `{ivm.measured_property}` | `{ivm.stat_type}` | {ivm.reason} |")
            lines.append("")

    # Mapping Rules
    if hasattr(plan, "mapping_rules") and plan.mapping_rules:
        lines.append("## Mapping Rules")
        lines.append("")
        for rule in plan.mapping_rules:
            lines.append(f"### Rule: `{rule.rule_id}` — {rule.description}")
            lines.append(f"- **Measure column:** `{rule.measure_column}`")
            obs = rule.observation
            lines.append(f"- **observationAbout:** `{obs.about_column}` = `{obs.about_expression}`")
            lines.append(f"- **observationDate:** `{obs.date_column}` = `{obs.date_expression}`")
            lines.append(f"- **value:** `{obs.value_column}` = `{obs.value_expression}`")
            if obs.unit:
                lines.append(f"- **unit:** `{obs.unit}`")
            if obs.unit_column:
                lines.append(f"- **unit (from column):** `{obs.unit_column}`")
            if rule.indicator_column:
                lines.append(f"- **indicator column:** `{rule.indicator_column}`")
            if rule.constraint_columns:
                lines.append(f"- **constraints:** {', '.join(f'`{c}`' for c in rule.constraint_columns)}")
            if rule.pvmap_rows:
                lines.append("")
                lines.append("**Target PVMAP rows:**")
                lines.append("```csv")
                for row in rule.pvmap_rows:
                    lines.append(row)
                lines.append("```")
            lines.append("")

    return "\n".join(lines)


class MappingPlanAgent(BaseAgent):
    """Generates a structured mapping plan by ranking pre-retrieved candidates."""

    _model_name: str = PrivateAttr(default="gemini-3.1-pro-preview")

    def __init__(self, name: str = "MappingPlanAgent", model: str = None):
        super().__init__(name=name)
        self._model_name = model or os.getenv("MAPPING_PLAN_MODEL", "gemini-3.1-pro-preview")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        """Generate structured mapping plan from candidate pool."""
        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text="Generating structured mapping plan...")]
        ))

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

        # Inject engineer feedback if provided (for plan regeneration)
        engineer_feedback = ctx.session.state.get("engineer_feedback", "")
        if not engineer_feedback:
            engineer_feedback = "(No feedback provided — this is the initial plan generation.)"

        dataset_name = ctx.session.state.get("dataset_name", "unknown")

        # Detect Phase A analysis availability for v2 mode
        column_analysis = ctx.session.state.get("column_analysis", "")
        use_v2 = bool(column_analysis and column_analysis != "{}")

        # SDMX mode: use a dedicated prompt primed with the DSD
        sdmx_mode_on = ctx.session.state.get("sdmx_mode", False)
        sdmx_structure = ctx.session.state.get("sdmx_structure", "")

        if sdmx_mode_on and sdmx_structure:
            logger.info("SDMX mode detected; using mapping_plan_prompt_sdmx_v1")
            template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt_sdmx_v1.txt"
            template = template_path.read_text()

            if sampled_data:
                sampled_lines = sampled_data.split("\n")
                sampled_data_truncated = "\n".join(sampled_lines[:6])
            else:
                sampled_data_truncated = ""

            populated = template.replace("{sdmx_structure}", sdmx_structure)
            populated = populated.replace("{candidate_pool_json}", candidate_pool_json)
            populated = populated.replace("{schema_vocab_content}", schema_vocab)
            populated = populated.replace("{sampled_data}", sampled_data_truncated)
            populated = populated.replace("{engineer_feedback}", engineer_feedback)

            plan_task = asyncio.create_task(
                self._generate_plan(populated, dataset_name, use_v2=True)
            )
            elapsed = 0
            while not plan_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(plan_task), timeout=60)
                except asyncio.TimeoutError:
                    elapsed += 60
                    yield Event(author=self.name, content=types.Content(
                        parts=[types.Part(text=f"Still generating SDMX plan... ({elapsed}s elapsed)")]
                    ))
            plan = plan_task.result()
        elif use_v2:
            # --- v2 path: enriched plan with Phase A column analysis ---
            logger.info("Phase A column_analysis detected; using v2 enriched plan prompt")
            template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt_v2.txt"
            template = template_path.read_text()

            # Truncate sampled_data to header + 5 rows for v2
            if sampled_data:
                sampled_lines = sampled_data.split("\n")
                sampled_data_truncated = "\n".join(sampled_lines[:6])
            else:
                sampled_data_truncated = ""

            populated = template.replace("{column_analysis_json}", column_analysis)
            populated = populated.replace("{candidate_pool_json}", candidate_pool_json)
            populated = populated.replace("{schema_vocab_content}", schema_vocab)
            populated = populated.replace("{sampled_data}", sampled_data_truncated)
            populated = populated.replace("{engineer_feedback}", engineer_feedback)

            # Yield heartbeat events while waiting for Gemini to prevent
            # the 300s stall detector in _run_pipeline_async from killing us.
            plan_task = asyncio.create_task(
                self._generate_plan(populated, dataset_name, use_v2=True)
            )
            elapsed = 0
            while not plan_task.done():
                try:
                    await asyncio.wait_for(asyncio.shield(plan_task), timeout=60)
                except asyncio.TimeoutError:
                    elapsed += 60
                    yield Event(author=self.name, content=types.Content(
                        parts=[types.Part(text=f"Still generating enriched plan... ({elapsed}s elapsed)")]
                    ))
            plan = plan_task.result()
        else:
            # --- v1 path: original plan generation (unchanged) ---
            template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt.txt"
            template = template_path.read_text()

            populated = template.replace("{skeleton_summary}", skeleton)
            populated = populated.replace("{schema_vocab_content}", schema_vocab)
            populated = populated.replace("{sampled_data}", sampled_data)
            populated = populated.replace("{statvar_summary}", statvar_summary)
            populated = populated.replace("{candidate_pool_json}", candidate_pool_json)
            populated = populated.replace("{engineer_feedback}", engineer_feedback)

            plan = await self._generate_plan(populated, dataset_name)

        # engineer_notes is reserved for human input — clear any LLM-generated
        # notes but preserve carried notes from a previous regeneration cycle.
        engineer_notes_carry = ctx.session.state.get("engineer_notes_carry", "")
        if engineer_notes_carry:
            try:
                carried = json.loads(engineer_notes_carry)
                plan.engineer_notes = carried if isinstance(carried, list) else []
            except (json.JSONDecodeError, TypeError):
                plan.engineer_notes = []
        else:
            plan.engineer_notes = []

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

    async def _generate_plan(
        self, prompt: str, dataset_name: str, use_v2: bool = False,
    ) -> MappingPlan:
        """Call Gemini with structured output to generate the mapping plan.

        When *use_v2* is True, uses the EnrichedMappingPlan schema with a
        larger output-token budget so the LLM can return the richer plan.

        Wide datasets (e.g. India NFHS, World Bank commodities, CDC SVI) can
        produce JSON that exceeds 32K tokens and gets truncated mid-structure,
        causing a Pydantic JSON_INVALID error that aborts the pipeline.
        Budget v2 generously and fall back to the v1 (leaner) schema on
        truncation failures.
        """
        client = genai.Client()

        if use_v2:
            from src.api.models.plan import EnrichedMappingPlan

            plan_schema = EnrichedMappingPlan.model_json_schema()
            # Gemini 2.5 / 3.x Pro support up to 65536 output tokens — use the
            # full budget for the enriched plan so wide datasets don't truncate.
            max_tokens = 65536
        else:
            plan_schema = MappingPlan.model_json_schema()
            max_tokens = 8192

        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=max_tokens,
                response_mime_type="application/json",
                response_schema=plan_schema,
            ),
        )

        # Parse via Pydantic for validation
        try:
            if use_v2:
                from src.api.models.plan import EnrichedMappingPlan

                plan = EnrichedMappingPlan.model_validate_json(response.text)
            else:
                plan = MappingPlan.model_validate_json(response.text)
        except Exception as e:
            logger.error("Failed to parse structured output: %s. Raw: %s", e, response.text[:500])
            if use_v2:
                # v2 (EnrichedMappingPlan) parse failed — retry with the leaner
                # v1 MappingPlan schema so the rest of the pipeline can proceed
                # instead of aborting the entire run.
                logger.warning(
                    "EnrichedMappingPlan parse failed; falling back to v1 MappingPlan schema"
                )
                return await self._generate_plan(prompt, dataset_name, use_v2=False)
            raise

        return plan


__all__ = ["MappingPlanAgent", "_plan_to_markdown"]
