"""Programmatic StatVar grounding via Data Commons API.

Validates generated StatVar DCIDs against the DC knowledge graph.
Only runs when --enable-mcp is set. No LLM calls.
"""

import logging
import re
from dataclasses import dataclass
from typing import List, Optional

from src.agents.sampling.schemas import RelationalSkeleton, SemanticAnalysis

logger = logging.getLogger(__name__)


@dataclass
class GroundedStatVar:
    """A StatVar DCID that has been validated against DC API."""

    dcid: str
    description: str = ""
    confirmed: bool = False
    observation_count: int = 0


def ground_statvars(
    skeleton: RelationalSkeleton,
    analysis: SemanticAnalysis,
    enable_mcp: bool = False,
    mcp_url: Optional[str] = None,
) -> List[GroundedStatVar]:
    """Programmatic StatVar grounding via DC API.

    Builds candidate DCIDs from the skeleton's statvar_pattern and
    dimension columns, then validates them against the DC knowledge graph.

    Args:
        skeleton: Relational skeleton with StatVar pattern.
        analysis: Semantic analysis with population/measurement types.
        enable_mcp: If False, returns empty list immediately.
        mcp_url: Optional MCP server URL (unused, reserved for future).

    Returns:
        List of GroundedStatVar with confirmed=True for valid DCIDs.
    """
    if not enable_mcp:
        return []

    # Build candidate DCIDs from pattern
    candidates = _build_candidate_dcids(skeleton, analysis)
    if not candidates:
        logger.info("No candidate StatVar DCIDs to ground")
        return []

    logger.info("Grounding %d candidate StatVar DCIDs", len(candidates))

    # Validate via DC API
    try:
        from src.data_commons.api.dc_api_wrapper import dc_api_is_defined_dcid

        dcid_list = [c.dcid for c in candidates]
        results = dc_api_is_defined_dcid(dcid_list)

        for candidate in candidates:
            candidate.confirmed = results.get(candidate.dcid, False)

        confirmed_count = sum(1 for c in candidates if c.confirmed)
        logger.info(
            "Grounded %d/%d StatVar DCIDs",
            confirmed_count, len(candidates),
        )
        return candidates

    except ImportError:
        logger.warning("DC API wrapper not available, skipping grounding")
        return candidates
    except Exception as e:
        logger.warning("StatVar grounding failed: %s", e)
        return candidates


def _build_candidate_dcids(
    skeleton: RelationalSkeleton,
    analysis: SemanticAnalysis,
) -> List[GroundedStatVar]:
    """Build candidate StatVar DCIDs from pattern + dimension values.

    Uses the P+M+C formula to construct plausible DCIDs.
    Only generates a few candidates per dimension to avoid API spam.
    """
    candidates = []

    # Parse the pattern to extract the base
    pattern = skeleton.statvar_pattern
    if not pattern:
        return []

    # Extract base parts (before first {placeholder})
    base_parts = re.split(r'\{[^}]+\}', pattern)
    base = base_parts[0].rstrip('_') if base_parts else pattern

    # Generate base DCID (no dimension constraints)
    candidates.append(GroundedStatVar(
        dcid=base,
        description=f"Base StatVar: {base}",
    ))

    # Generate common well-known DCIDs based on population + measurement
    pop_type = analysis.population_type
    meas_type = analysis.measurement_type

    well_known = [
        f"{meas_type}_{pop_type}",
    ]

    # Add dimension-specific variants (limit to avoid API flood)
    for dim_col in skeleton.dimension_columns[:3]:
        agg_flags_dict = skeleton.get_aggregate_flags_dict()
        agg_vals = agg_flags_dict.get(dim_col, [])
        for val in agg_vals[:2]:
            # Clean value for DCID format (CamelCase, no spaces)
            clean_val = _to_dcid_segment(val)
            if clean_val:
                well_known.append(f"{meas_type}_{pop_type}_{clean_val}")

    for dcid in well_known:
        if dcid != base:
            candidates.append(GroundedStatVar(
                dcid=dcid,
                description=f"Candidate: {dcid}",
            ))

    # Limit total candidates
    return candidates[:20]


def _to_dcid_segment(value: str) -> str:
    """Convert a dimension value to a DCID-compatible segment.

    Examples:
        "Male" -> "Male"
        "18 to 24" -> "18To24"
        "Bachelor's degree" -> "BachelorsDegree"
    """
    if not value:
        return ""

    # Remove special characters
    cleaned = re.sub(r"[^a-zA-Z0-9\s]", "", value)
    # Title case and remove spaces
    parts = cleaned.split()
    result = "".join(p.capitalize() for p in parts)
    return result
