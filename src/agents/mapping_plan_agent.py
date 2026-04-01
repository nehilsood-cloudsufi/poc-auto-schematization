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

        populated = template.replace("{skeleton_summary}", skeleton)
        populated = populated.replace("{schema_category}", schema_category)
        populated = populated.replace("{schema_vocab_content}", schema_vocab)
        populated = populated.replace("{sampled_data}", sampled_data)
        populated = populated.replace("{statvar_summary}", statvar_summary)
        populated = populated.replace("{per_column_dc_matches}", str(per_column_dc))
        populated = populated.replace("{schemaorg_column_mappings}", schemaorg_mappings)

        # Generate plan via LLM
        plan_text = await self._generate_plan(populated)

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
