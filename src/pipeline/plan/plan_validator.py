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

        # Collect (candidate, future) pairs so we can assign results back.
        tasks: list[tuple[PropertyValueCandidate, asyncio.Task]] = []

        for col in plan.active_columns:
            for cand in col.candidates:
                tasks.append((cand, self._validate_candidate(cand)))

        for sp in plan.static_properties:
            for cand in sp.candidates:
                tasks.append((cand, self._validate_candidate(cand)))

        if not tasks:
            return plan

        candidates, coros = zip(*tasks)
        results = await asyncio.gather(*coros, return_exceptions=True)

        for cand, result in zip(candidates, results):
            if isinstance(result, BaseException):
                logger.warning(
                    "Validation failed for candidate %s: %s",
                    cand.property,
                    result,
                )
                cand.validation = CandidateValidation(
                    property_exists=False,
                    notes=f"Validation error: {result}",
                )
            else:
                cand.validation = result

        return plan


def clear_property_cache() -> None:
    """Clear the module-level property cache (useful in tests)."""
    _property_cache.clear()
