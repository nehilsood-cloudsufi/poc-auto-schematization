"""
MCP Spot-Check Agent for quick pre-validation of PVMAP mappings.

Lightweight BaseAgent that performs a quick validation of key PVMAP mappings
against live DC data before the expensive stat_var_processor subprocess.

Checks 1-2 discovered StatVars by resolving sample places and calling
validate_statvar_observation. Stores warnings in state but does NOT block
the pipeline — warnings are informational for the feedback agent.

ADK State Inputs:
    - mcp_enabled: bool
    - discovered_statvars: List[dict] (from StatVarDiscoveryAgent)
    - pvmap_csv: str (from PVMAPGeneratorAgent)
    - data_context: dict (from SamplingAgent)

ADK State Outputs:
    - structure_warnings: str (appended with spot-check warnings)
"""

import logging
import re
import sys
from pathlib import Path
from typing import AsyncGenerator

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types

logger = logging.getLogger(__name__)


class MCPSpotCheckAgent(BaseAgent):
    """Quick pre-validation: check 1-2 PVMAP mappings against live DC data."""

    def __init__(self, name: str = "MCPSpotCheck"):
        super().__init__(name=name)

    async def _run_async_impl(
        self, ctx: InvocationContext
    ) -> AsyncGenerator[Event, None]:
        """Run spot-check validation of discovered StatVars."""

        # Skip if MCP not enabled
        if not ctx.session.state.get("mcp_enabled"):
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="MCP spot-check skipped (MCP not enabled)")
                ])
            )
            return

        # Skip if no discovered statvars
        discovered = ctx.session.state.get("discovered_statvars", [])
        if not discovered:
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text="MCP spot-check skipped (no discovered StatVars)")
                ])
            )
            return

        yield Event(
            author=self.name,
            content=types.Content(parts=[
                types.Part(text="Running MCP spot-check on discovered StatVars...")
            ])
        )

        try:
            from src.tools.dc_tools import (
                resolve_place_names,
                validate_statvar_observation,
            )

            # 1. Get sample place values from data_context
            data_context = ctx.session.state.get("data_context", {})
            sample_places = _get_sample_places(data_context)

            # 2. Resolve a place DCID for validation
            resolved_dcid = _resolve_sample_place(sample_places, resolve_place_names)

            if not resolved_dcid:
                yield Event(
                    author=self.name,
                    content=types.Content(parts=[
                        types.Part(text="MCP spot-check: no place DCID to validate against, skipping")
                    ])
                )
                return

            # 3. Check top 2 HIGH-confidence discovered StatVars
            high_conf = [sv for sv in discovered if sv.get("confidence") == "HIGH"]
            to_check = high_conf[:2] if high_conf else discovered[:1]

            warnings = []
            checked = 0
            for sv in to_check:
                dcid = sv.get("dcid", "")
                if not dcid:
                    continue

                result = validate_statvar_observation(dcid, resolved_dcid)
                checked += 1

                if "UNCONFIRMED" in result.upper():
                    warnings.append(
                        f"Spot-check WARNING: StatVar {dcid} has no data for "
                        f"{resolved_dcid} — mapping may be incorrect"
                    )
                    logger.info(f"Spot-check UNCONFIRMED: {dcid} at {resolved_dcid}")
                else:
                    logger.info(f"Spot-check CONFIRMED: {dcid} at {resolved_dcid}")

            # 4. Store warnings in state (don't block — just warn)
            if warnings:
                existing = ctx.session.state.get("structure_warnings", "")
                if isinstance(existing, list):
                    existing = "\n".join(str(w) for w in existing)
                new_warnings = "\n".join(warnings)
                ctx.session.state["structure_warnings"] = (
                    f"{existing}\n{new_warnings}" if existing else new_warnings
                )

            summary = f"Spot-checked {checked} StatVar(s) against {resolved_dcid}"
            if warnings:
                summary += f" — {len(warnings)} warning(s)"
            else:
                summary += " — all confirmed"

            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=summary)
                ])
            )

        except Exception as e:
            logger.warning(f"MCP spot-check failed (continuing): {e}")
            yield Event(
                author=self.name,
                content=types.Content(parts=[
                    types.Part(text=f"MCP spot-check failed (continuing): {str(e)[:100]}")
                ])
            )


def _get_sample_places(data_context: dict) -> list:
    """Extract sample place values from data_context."""
    if not data_context:
        return []

    places = []
    column_roles = data_context.get("column_roles", {})
    place_columns = [col for col, role in column_roles.items() if role == "place"]

    for col in place_columns:
        domain_vals = data_context.get("dimension_domains", {}).get(col, [])
        places.extend(str(v) for v in domain_vals[:3])

    return list(dict.fromkeys(places))[:5]


def _resolve_sample_place(sample_places: list, resolve_fn) -> str:
    """Try to resolve sample places to a DCID. Falls back to common defaults."""

    # Try resolving from data_context places
    if sample_places:
        result = resolve_fn(", ".join(sample_places[:2]))
        # Parse result for first resolved DCID
        for line in result.split("\n"):
            if "->" in line and "NOT_FOUND" not in line:
                parts = line.split("->")
                if len(parts) == 2:
                    dcid = parts[1].strip()
                    if dcid:
                        return dcid

    # Fallback defaults: try US (most common in DC datasets)
    return "geoId/06"  # California — common default for US state data
