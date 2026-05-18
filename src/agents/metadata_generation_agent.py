"""Metadata Generation Agent for auto-generating stat_var_processor config.

Hybrid approach:
- Phase A (deterministic): Extract output_columns, header_rows, mapped_rows,
  mapped_columns from PVMAP CSV, data_context, and input headers. Always runs.
  No LLM cost.
- Phase B (LLM-assisted): Only when mapped_columns_confidence == "low" on first
  attempt. LLM classifies input columns as DIMENSION vs VALUE to refine
  mapped_columns. Fires at most once per pipeline run.

Runs AFTER PVMAPGeneratorAgent, BEFORE ValidationAgent in the retry loop.
"""

import csv
import io
import json
import logging
import os
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

from src.agents.prompt_loader import load_prompt
from src.agents.retry_config import create_resilient_model
from src.agents.pvmap_generation.helpers import convert_pvmap_output_to_csv
from src.agents.pvmap_generation.schemas import PVMAPOutput, PVMAPRow, PropertyValuePair
from src.tools.metadata_tools import generate_processor_config

logger = logging.getLogger(__name__)

_ENRICHMENT_INSTRUCTION = load_prompt("metadata_enrichment.txt")


def _create_enrichment_agent(model: str) -> LlmAgent:
    """Create inner LlmAgent for mapped_columns refinement.

    This agent classifies input columns as DIMENSION vs VALUE to determine
    mapped_columns when deterministic analysis has low confidence.

    Returns output_key='metadata_enrichment' as JSON string with mapped_columns.
    """
    return LlmAgent(
        name="MetadataEnricher",
        model=create_resilient_model(model),
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
        - generated_config_path: str - Path to output_metadata.csv
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
        self, name: str = "MetadataGenerator", model: Optional[str] = None,
    ):
        model = model or os.getenv("METADATA_AGENT_MODEL", "gemini-2.5-pro")
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

        # Step 1: Check prerequisites
        pvmap_csv = ctx.session.state.get("pvmap_csv")
        current_dataset = ctx.session.state.get("current_dataset")

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

        # Step 2: Resolve existing metadata
        existing_metadata = self._resolve_existing_metadata(current_dataset)

        # Step 3: Get input file and headers
        input_file = None
        input_headers = []
        if current_dataset.input_data_files:
            input_file = str(current_dataset.input_data_files[0])
            input_headers = self._read_input_headers(input_file)

        # Step 4: Phase A — Deterministic config generation
        data_context = ctx.session.state.get("data_context", {})

        result = generate_processor_config(
            pvmap_csv_content=pvmap_csv,
            data_context=data_context if isinstance(data_context, dict) else {},
            input_file=input_file,
            input_headers=input_headers,
            output_dir=str(current_dataset.output_dir),
            existing_metadata_path=existing_metadata,
        )

        # Step 5: Phase B — LLM refinement for mapped_columns (first attempt, low confidence only)
        attempt_number = ctx.session.state.get("attempt_number", 0)
        confidence = result.get("mapped_columns_confidence", "high")

        if attempt_number == 0 and confidence == "low" and self.enrichment_agent:
            try:
                # Prepare state for LLM prompt templating
                ctx.session.state["input_headers"] = str(input_headers)
                direct_keys, cv_keys = self._parse_pvmap_key_types(pvmap_csv)
                ctx.session.state["direct_keys_list"] = str(sorted(direct_keys)[:30])
                ctx.session.state["column_value_keys_list"] = str(sorted(cv_keys)[:30])
                ctx.session.state["sample_rows"] = self._read_sample_rows(input_file, 3)

                async for event in self.enrichment_agent.run_async(ctx):
                    yield event

                # Parse LLM output
                enrichment_str = ctx.session.state.get("metadata_enrichment", "")
                if enrichment_str:
                    clean = enrichment_str.strip()
                    if clean.startswith("```"):
                        lines = clean.split("\n")
                        lines = lines[1:]
                        if lines and lines[-1].strip() == "```":
                            lines = lines[:-1]
                        clean = "\n".join(lines)
                    llm_result = json.loads(clean)
                    if "mapped_columns" in llm_result:
                        result = generate_processor_config(
                            pvmap_csv_content=pvmap_csv,
                            data_context=data_context if isinstance(data_context, dict) else {},
                            input_file=input_file,
                            input_headers=input_headers,
                            output_dir=str(current_dataset.output_dir),
                            existing_metadata_path=existing_metadata,
                            llm_enrichment=llm_result,
                        )
                        logger.info(f"LLM mapped_columns refinement: {llm_result}")

            except Exception as e:
                logger.warning(f"LLM enrichment failed (non-fatal): {e}")

        # Step 6: Update state
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
                                f"mapped_columns={params.get('mapped_columns', 'N/A')}, "
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

    def _read_input_headers(self, input_file: str) -> list:
        """Read column headers from input CSV file."""
        try:
            with open(input_file, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                return next(reader, [])
        except Exception as e:
            logger.warning(f"Failed to read input headers: {e}")
            return []

    def _read_sample_rows(self, input_file: Optional[str], n: int = 3) -> str:
        """Read first N data rows from input CSV as string for LLM context."""
        if not input_file:
            return ""
        try:
            with open(input_file, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                next(reader, None)  # Skip header
                rows = []
                for i, row in enumerate(reader):
                    if i >= n:
                        break
                    rows.append(",".join(row[:10]))  # Truncate wide rows
                return "\n".join(rows)
        except Exception:
            return ""

    def _parse_pvmap_key_types(self, pvmap_csv: str) -> tuple:
        """Parse PVMAP keys into direct keys and column:value keys."""
        direct_keys = set()
        cv_keys = set()
        try:
            reader = csv.reader(io.StringIO(pvmap_csv))
            for row in reader:
                if not row:
                    continue
                key = row[0].strip()
                if not key or key.lower() == "key":
                    continue
                if ":" in key:
                    cv_keys.add(key)
                else:
                    direct_keys.add(key)
        except Exception:
            pass
        return direct_keys, cv_keys


# ============================================================================
# Module exports
# ============================================================================

__all__ = ["MetadataGenerationAgent"]
