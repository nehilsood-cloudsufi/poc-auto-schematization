"""Validate candidate property-value pairs against the live Data Commons API.

Best-effort: if the DC API is unreachable the plan is returned unchanged
(all validations default to property_exists=False with an error note).
"""

from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from src.api.models.plan import (
    CandidateValidation,
    MappingPlan,
    PropertyValueCandidate,
)

logger = logging.getLogger(__name__)

# Module-level cache so repeated property lookups across plans are cheap.
_property_cache: dict[str, bool] = {}

# Properties that are guaranteed to exist in Data Commons and never need an
# API round-trip.
WELL_KNOWN_PROPERTIES: frozenset[str] = frozenset(
    {
        "observationAbout",
        "observationDate",
        "value",
        "variableMeasured",
        "observationPeriod",
        "measuredProperty",
        "populationType",
        "statType",
        "unit",
        "measurementQualifier",
        "measurementDenominator",
        "scalingFactor",
        "geoId",
        "containedInPlace",
    }
)

DC_API_BASE = "https://api.datacommons.org/v2/node"


class PlanValidator:
    """Validates a ``MappingPlan`` against the Data Commons knowledge graph."""

    def __init__(self, timeout: float = 10.0) -> None:
        self._timeout = timeout

    # ------------------------------------------------------------------
    # Low-level helpers
    # ------------------------------------------------------------------

    async def _check_property_exists(self, property_name: str) -> bool:
        """Return *True* if *property_name* is a known DC property.

        Well-known properties are returned immediately without a network
        call.  Everything else hits the DC ``/v2/node`` endpoint and
        caches the result.  On any error the method returns ``False``
        (best-effort).
        """
        if property_name in WELL_KNOWN_PROPERTIES:
            return True

        if property_name in _property_cache:
            return _property_cache[property_name]

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    DC_API_BASE,
                    params={
                        "nodes": f"dcid:{property_name}",
                        "property": "->*",
                    },
                )
                resp.raise_for_status()
                data = resp.json()
                # The API returns a "data" dict keyed by DCID.  If the
                # property exists the key will be present with arcs.
                node_key = f"dcid:{property_name}"
                exists = bool(data.get("data", {}).get(node_key))
                if exists:
                    _property_cache[property_name] = exists
                return exists
        except Exception:
            logger.debug(
                "DC API check failed for property %s, assuming absent",
                property_name,
                exc_info=True,
            )
            return False

    # ------------------------------------------------------------------
    # Candidate-level validation
    # ------------------------------------------------------------------

    async def _validate_candidate(
        self, candidate: PropertyValueCandidate
    ) -> CandidateValidation:
        """Validate a single candidate against the DC API."""
        property_exists = await self._check_property_exists(candidate.property)
        notes = ""
        if not property_exists:
            notes = f"Property '{candidate.property}' not found in Data Commons"
        return CandidateValidation(property_exists=property_exists, notes=notes)

    # ------------------------------------------------------------------
    # Plan-level validation
    # ------------------------------------------------------------------

    async def validate(self, plan: MappingPlan) -> MappingPlan:
        """Validate all candidates in *plan* and return it with results.

        Validations are run concurrently via ``asyncio.gather``.  Any
        individual failure is caught and recorded as a validation with an
        error note -- the plan is always returned.
        """

        # Deduplicate property checks to avoid cache-miss thundering herd.
        all_candidates: list[PropertyValueCandidate] = []
        for col in plan.active_columns:
            all_candidates.extend(col.candidates)
        for sp in plan.static_properties:
            all_candidates.extend(sp.candidates)

        if not all_candidates:
            return plan

        # Collect unique property names and validate each once
        unique_props = list({c.property for c in all_candidates})
        prop_results = await asyncio.gather(
            *[self._check_property_exists(p) for p in unique_props],
            return_exceptions=True,
        )
        prop_map: dict[str, bool] = {}
        for prop, result in zip(unique_props, prop_results):
            prop_map[prop] = result if isinstance(result, bool) else False

        # Assign validation results to each candidate
        results = []
        for cand in all_candidates:
            exists = prop_map.get(cand.property, False)
            notes = "" if exists else f"Property '{cand.property}' not found in Data Commons"
            results.append(CandidateValidation(property_exists=exists, notes=notes))

        for cand, result in zip(all_candidates, results):
            cand.validation = result

        # Log properties that failed lookup (for debugging)
        failed_props = [p for p, exists in prop_map.items() if not exists]
        if failed_props:
            logger.info(
                "DC API: %d/%d properties not found: %s",
                len(failed_props), len(unique_props),
                ", ".join(failed_props[:10]),
            )

        return plan


def clear_property_cache() -> None:
    """Clear the module-level property cache (useful in tests)."""
    _property_cache.clear()


# --- ADK Agent Wrapper ---
from pathlib import Path
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types


class PlanValidatorAgent(BaseAgent):
    """ADK agent wrapper for PlanValidator. Runs after MappingPlanAgent."""

    def __init__(self, name: str = "PlanValidator"):
        super().__init__(name=name)

    async def _run_async_impl(self, ctx: InvocationContext):
        plan_json = ctx.session.state.get("mapping_plan_json", "")
        if not plan_json:
            yield Event(author=self.name, content=genai_types.Content(
                parts=[genai_types.Part(text="No plan to validate — skipping")]
            ))
            return

        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text="Validating plan against DC API...")]
        ))

        plan = MappingPlan.model_validate_json(plan_json)

        validator = PlanValidator()
        validated = await validator.validate(plan)

        # Update state with validated plan
        validated_json = validated.model_dump_json(indent=2)
        ctx.session.state["mapping_plan"] = validated_json
        ctx.session.state["mapping_plan_json"] = validated_json

        # Overwrite the JSON file on disk
        output_dir = Path(ctx.session.state.get("output_dir", "."))
        json_path = output_dir / "mapping_plan.json"
        if json_path.exists():
            json_path.write_text(validated_json, encoding="utf-8")

        logger.info("Plan validation complete")

        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text="Plan validation complete")]
        ))
