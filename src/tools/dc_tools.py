"""
Local Data Commons tools that call the DC API directly.

These bypass the MCP server for low-latency, targeted queries.
Each function is ADK-compatible (returns str, has docstring with Args).

Available tools:
- resolve_place_names: Resolve place names to DCIDs
- validate_statvar_observation: Check if a StatVar has data for a place
- get_entity_type: Get entity type for a DCID
"""

import logging
import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.data_commons.api.dc_api_wrapper import (
    get_datacommons_client,
    dc_api_resolve_placeid,
    dc_api_is_defined_dcid,
    dc_api_get_node_property,
)

logger = logging.getLogger(__name__)

# Lazy-initialized DataCommonsClient singleton
_dc_client = None


def _get_dc_client():
    """Get or create a DataCommonsClient instance."""
    global _dc_client
    if _dc_client is None:
        from dotenv import load_dotenv
        load_dotenv()

        api_key = os.getenv("DC_API_KEY", "")
        config = {}
        if api_key:
            config["dc_api_key"] = api_key
        _dc_client = get_datacommons_client(config)
    return _dc_client


def resolve_place_names(place_names: str) -> str:
    """Resolve place names to Data Commons DCIDs.

    Args:
        place_names: Comma-separated place names (e.g., "California, Texas, New York")

    Returns:
        Mapping of place names to their DCIDs, or error message.
    """
    names = [n.strip() for n in place_names.split(",") if n.strip()]
    if not names:
        return "No place names provided."

    try:
        # Try resolving as place names using the name property
        result = dc_api_resolve_placeid(names, in_prop='name')

        lines = []
        for name in names:
            dcid = result.get(name, "NOT_FOUND")
            lines.append(f"- {name} -> {dcid}")

        return "\n".join(lines) if lines else "No places resolved."
    except Exception as e:
        logger.warning(f"Place resolution failed: {e}")
        return f"Place resolution failed: {str(e)[:200]}"


def validate_statvar_observation(variable_dcid: str, place_dcid: str, date: str = "") -> str:
    """Check if a StatVar has observation data for a given place.

    Args:
        variable_dcid: The StatVar DCID (e.g., "Count_Person")
        place_dcid: The place DCID (e.g., "geoId/06")
        date: Optional date filter (e.g., "2020")

    Returns:
        Confirmation with sample data point, or "no data" message.
    """
    try:
        client = _get_dc_client()

        # Use the observation API via the client's observation endpoint
        # DataCommonsClient V2 supports observation.fetch
        if hasattr(client, 'observation') and hasattr(client.observation, 'fetch'):
            result = client.observation.fetch(
                variable_dcids=variable_dcid,
                entity_dcids=place_dcid,
                date=date or None,
            )
            # Extract sample data point from result
            result_str = str(result)[:500]
            if result and ('observations' in result_str.lower() or len(result_str) > 50):
                return f"CONFIRMED: {variable_dcid} has data for {place_dcid}. Response: {result_str}"
            else:
                return f"UNCONFIRMED: {variable_dcid} at {place_dcid} — empty response"
        else:
            # Fallback: check if the variable DCID is defined in DC
            is_defined = dc_api_is_defined_dcid([variable_dcid])
            if is_defined.get(variable_dcid, False):
                return f"PARTIAL: {variable_dcid} is a valid DCID in Data Commons (observation check not available)"
            else:
                return f"UNCONFIRMED: {variable_dcid} is NOT a recognized DCID in Data Commons"

    except Exception as e:
        logger.warning(f"Observation validation failed: {e}")
        return f"UNCONFIRMED: {variable_dcid} at {place_dcid} — {str(e)[:200]}"


def get_entity_type(dcid: str) -> str:
    """Get the entity type for a Data Commons DCID.

    Args:
        dcid: The DCID to look up (e.g., "geoId/06", "country/USA")

    Returns:
        Entity type (e.g., "State", "Country") or "unknown".
    """
    try:
        result = dc_api_get_node_property([dcid], "typeOf")
        type_info = result.get(dcid, {})
        type_of = type_info.get("typeOf", "unknown")

        return f"{dcid} is type: {type_of}"
    except Exception as e:
        logger.warning(f"Type lookup failed for {dcid}: {e}")
        return f"Type lookup failed for {dcid}: {str(e)[:200]}"


def reset_dc_client():
    """Reset the cached DataCommonsClient (for testing)."""
    global _dc_client
    _dc_client = None
