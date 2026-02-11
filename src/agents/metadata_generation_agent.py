"""Metadata Generation Agent for auto-generating stat_var_processor config.

Hybrid approach:
- Phase A (deterministic): Extract output_columns, header_rows, mapped_rows,
  mapped_columns from PVMAP CSV and data_context. Always runs. No LLM cost.
- Phase B (LLM-assisted): Optionally call an inner LlmAgent to analyze PVMAP +
  data_context and suggest contextual params: schemaless flag, description, etc.
  Only runs on first attempt (attempt_number == 0) to avoid repeated LLM costs.

Runs AFTER PVMAPGeneratorAgent, BEFORE ValidationAgent in the retry loop.
"""

import json
import logging
import sys
from pathlib import Path
from typing import AsyncGenerator, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent, LlmAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event, EventActions
from google.genai import types

from src.agents.pvmap_generation.helpers import convert_pvmap_output_to_csv
from src.agents.pvmap_generation.schemas import PVMAPOutput, PVMAPRow, PropertyValuePair
from src.agents.template_utils import escape_pvmap_placeholders
from src.tools.metadata_tools import generate_processor_config

logger = logging.getLogger(__name__)

_ENRICHMENT_INSTRUCTION = '''Analyze the PVMAP and data context to suggest stat_var_processor config parameters.

PVMAP CSV:
{pvmap_csv}

Skeleton Summary:
{skeleton_summary}

Data Context:
{data_context_str}

Based on this analysis, output a JSON object with ONLY the parameters you're confident about:
{{
  "schemaless": true/false,
  "drop_statvars_without_svobs": 0 or 1,
  "description": "Brief dataset description"
}}

Rules for schemaless:
- true if PVMAP contains dimension/defining properties beyond the standard StatVarObs set
  (e.g., gender, age, income, healthOutcome, populationType, measuredProperty)
  This means we are DEFINING new StatVars, not mapping to existing DCIDs
- false if PVMAP only maps to existing variableMeasured DCIDs without defining properties

Rules for drop_statvars_without_svobs:
- Default 1 (drop). Set 0 only for clearly sparse data where many dimension combos have no values

Rules for description:
- 1-sentence summary under 100 chars describing the dataset

Output ONLY valid JSON, no explanation.'''


def _create_enrichment_agent(model: str) -> LlmAgent:
    """Create inner LlmAgent for contextual metadata enrichment.

    This agent analyzes the PVMAP and data to suggest optional params:
    - schemaless: Whether StatVars use non-standard property names
    - description: Auto-generated dataset description
    - drop_statvars_without_svobs: Whether to filter empty observations

    Returns output_key='metadata_enrichment' as JSON string.
    """
    return LlmAgent(
        name="MetadataEnricher",
        model=model,
        instruction=_ENRICHMENT_INSTRUCTION,
        output_key="metadata_enrichment",
    )


class MetadataGenerationAgent(BaseAgent):
    """Generates stat_var_processor config CSV from PVMAP + data context.

    Runs AFTER PVMAPGeneratorAgent, BEFORE ValidationAgent in the retry loop.

    State Inputs:
        - pvmap_csv: str - Generated PVMAP CSV content
        - current_dataset: DatasetInfo - Dataset being processed
        - data_context: dict - From sampling (column_roles, header info)
        - skeleton_summary: str - Enriched data summary
        - attempt_number: int - Current attempt

    State Outputs:
        - generated_config_path: str - Path to auto_config.csv
        - generated_config_params: dict - Parameters written

    Metadata Priority (3-tier):
        1. Ground truth metadata (highest - for benchmark evaluation)
        2. User-provided metadata (medium - explicit --use-metadata)
        3. Auto-generated config (lowest - always generated from PVMAP)

    When user/GT metadata exists, auto-generated params merge UNDER (user wins).
    """

    # Declare enrichment_agent as a Pydantic field for ADK
    enrichment_agent: Optional[LlmAgent] = None

    def __init__(
        self, name: str = "MetadataGenerator", model: str = "gemini-2.5-flash"
    ):
        enrichment = _create_enrichment_agent(model)
        super().__init__(
            name=name,
            enrichment_agent=enrichment,
            sub_agents=[enrichment],
        )

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Generate stat_var_processor config from PVMAP and data context."""

        # Step 1: Check prerequisites - get PVMAP CSV from either source
        pvmap_csv = ctx.session.state.get("pvmap_csv")
        current_dataset = ctx.session.state.get("current_dataset")

        # If pvmap_csv not yet set (first attempt), convert from pvmap_output
        if not pvmap_csv:
            pvmap_output = ctx.session.state.get("pvmap_output")
            if pvmap_output:
                try:
                    pvmap_model = self._parse_pvmap_output(pvmap_output)
                    pvmap_csv = convert_pvmap_output_to_csv(pvmap_model)
                except Exception as e:
                    logger.warning(f"Failed to convert pvmap_output to CSV: {e}")

        if not pvmap_csv or not current_dataset:
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[
                        types.Part(
                            text="Skipping metadata generation (no PVMAP or dataset)"
                        )
                    ]
                ),
                actions=EventActions(escalate=False),
            )
            return

        yield Event(
            author=self.name,
            content=types.Content(
                parts=[types.Part(text="Generating stat_var_processor config...")]
            ),
        )

        # Step 2: Resolve existing metadata (GT > user > None)
        existing_metadata = self._resolve_existing_metadata(current_dataset)

        # Step 3: Get input file for header detection
        input_file = None
        if current_dataset.input_data_files:
            input_file = str(current_dataset.input_data_files[0])

        # Step 4: Phase A — Deterministic config generation (always)
        data_context = ctx.session.state.get("data_context", {})

        # Step 5: Phase B — LLM enrichment (first attempt only)
        llm_enrichment = None
        attempt_number = ctx.session.state.get("attempt_number", 0)

        if attempt_number == 0 and self.enrichment_agent:
            try:
                # Ensure state has defaults for enrichment instruction templating
                ctx.session.state.setdefault("skeleton_summary", "")
                # Use dedicated key for LLM templating, leave original dict untouched
                ctx.session.state["data_context_str"] = str(data_context)
                # Escape PVMAP placeholders ({Data}, {Number}) so ADK doesn't
                # try to resolve them as state variables
                ctx.session.state["pvmap_csv"] = escape_pvmap_placeholders(pvmap_csv)

                async for event in self.enrichment_agent.run_async(ctx):
                    yield event

                # Parse LLM output from state
                enrichment_str = ctx.session.state.get("metadata_enrichment", "")
                if enrichment_str:
                    # Strip markdown code fences if present
                    clean = enrichment_str.strip()
                    if clean.startswith("```"):
                        lines = clean.split("\n")
                        lines = lines[1:]  # Remove opening fence
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        clean = "\n".join(lines)
                    llm_enrichment = json.loads(clean)
                    logger.info(f"LLM enrichment: {llm_enrichment}")

            except Exception as e:
                logger.warning(f"LLM enrichment failed (non-fatal): {e}")

        # Step 6: Generate final config
        result = generate_processor_config(
            pvmap_csv_content=pvmap_csv,
            data_context=data_context if isinstance(data_context, dict) else {},
            input_file=input_file,
            output_dir=str(current_dataset.output_dir),
            existing_metadata_path=existing_metadata,
            llm_enrichment=llm_enrichment,
        )

        # Step 7: Update state
        if result.get("success"):
            ctx.session.state["generated_config_path"] = result["config_path"]
            ctx.session.state["generated_config_params"] = result["parameters"]

            params = result["parameters"]
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[
                        types.Part(
                            text=(
                                f"Config generated: output_columns={params.get('output_columns', 'N/A')}, "
                                f"mapped_rows={params.get('mapped_rows', 'N/A')}, "
                                f"header_rows={params.get('header_rows', 'N/A')}"
                            )
                        )
                    ]
                ),
                actions=EventActions(escalate=False),
            )
        else:
            logger.warning(
                f"Metadata generation failed: {result.get('error')}. "
                "Validation will proceed without auto-config."
            )
            yield Event(
                author=self.name,
                content=types.Content(
                    parts=[
                        types.Part(
                            text=f"Config generation failed (non-fatal): {result.get('error', 'unknown')}"
                        )
                    ]
                ),
                actions=EventActions(escalate=False),
            )

    def _parse_pvmap_output(self, pvmap_output: dict) -> PVMAPOutput:
        """Parse pvmap_output dict into PVMAPOutput Pydantic model."""
        if isinstance(pvmap_output, PVMAPOutput):
            return pvmap_output

        pvmap_rows = []
        for row_data in pvmap_output.get("pvmap_rows", []):
            mappings = [
                PropertyValuePair(property=m.get("property", ""), value=m.get("value", ""))
                for m in row_data.get("mappings", [])
            ]
            pvmap_rows.append(PVMAPRow(key=row_data.get("key", ""), mappings=mappings))

        return PVMAPOutput(
            format_detected=pvmap_output.get("format_detected", "raw"),
            pvmap_rows=pvmap_rows,
            validation_notes=pvmap_output.get("validation_notes", ""),
            confidence=pvmap_output.get("confidence", "medium"),
        )

    def _resolve_existing_metadata(self, current_dataset) -> Optional[str]:
        """Resolve existing metadata path using 3-tier priority.

        Same precedence as ValidationAgent:
        1. Ground truth metadata
        2. User-provided metadata (only if use_metadata enabled)
        3. None — will generate from scratch

        Returns:
            Path string to metadata CSV, or None.
        """
        # Tier 1: Ground truth metadata
        if current_dataset.ground_truth_metadata:
            gt_meta_dir = Path(current_dataset.ground_truth_metadata)
            if gt_meta_dir.exists():
                gt_meta_files = sorted(gt_meta_dir.glob("*.csv"))
                if gt_meta_files:
                    return str(gt_meta_files[0])

        # Tier 2: User-provided metadata
        if current_dataset.use_metadata and current_dataset.metadata_files:
            meta_path = Path(str(current_dataset.metadata_files[0]))
            if meta_path.exists():
                return str(meta_path)

        # Tier 3: None
        return None


# ============================================================================
# Module exports
# ============================================================================

__all__ = ["MetadataGenerationAgent"]
