"""
Verify skeleton PVMAP properties against Schema.org, DC API, and optionally MCP.

Three-tier verification:
  1. Schema.org vocab (local, instant) — check property exists
  2. DC API (remote, fast) — verify DCIDs and place resolution
  3. MCP (remote, optional) — search for StatVar candidates
"""

import csv
import io
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Properties that are always valid (DC built-ins, not in Schema.org)
ALWAYS_VALID_PROPERTIES = {
    "observationabout", "observationdate", "value", "#ignore",
    "#regex", "#format", "#eval", "#filter", "#aggregate", "#multiply",
    "populationtype", "measuredproperty", "stattype", "unit",
    "measurementdenominator", "measurementqualifier", "observationperiod",
    "scalingfactor", "memberof",
}


def verify_skeleton_properties(
    skeleton_csv: str,
    manifest: dict,
    data_context: dict,
    use_dc_api: bool = False,
    use_mcp: bool = False,
    mcp_url: Optional[str] = None,
) -> dict:
    """Verify property names in skeleton against Schema.org + DC API + MCP.

    Args:
        skeleton_csv: Generated skeleton CSV string
        manifest: Column manifest from build_column_manifest()
        data_context: Full data_context dict
        use_dc_api: Enable DC API verification (place resolution, DCID checks)
        use_mcp: Enable MCP enrichment for low-confidence columns
        mcp_url: MCP server URL (required if use_mcp=True)

    Returns:
        {
            "columns": {col_name: {property_verified, verification_source, alternatives, confidence}},
            "place_verified": bool,
            "properties_checked": int,
            "properties_valid": int,
            "verification_sources": ["schema_org", ...],
        }
    """
    result = {
        "columns": {},
        "place_verified": False,
        "properties_checked": 0,
        "properties_valid": 0,
        "verification_sources": [],
    }

    # Parse skeleton to extract properties per column
    column_properties = _extract_properties_from_skeleton(skeleton_csv, manifest)

    # Tier 1: Schema.org verification (always available, instant)
    _verify_via_schemaorg(column_properties, result)
    result["verification_sources"].append("schema_org")

    # Tier 2: DC API verification (if enabled)
    if use_dc_api:
        _verify_via_dc_api(column_properties, result, data_context)
        result["verification_sources"].append("dc_api")

    # Tier 3: MCP enrichment (if enabled)
    if use_mcp and mcp_url:
        _enrich_via_mcp(column_properties, result, data_context, mcp_url)
        result["verification_sources"].append("mcp")

    # Finalize counts
    result["properties_checked"] = len(column_properties)
    result["properties_valid"] = sum(
        1 for c in result["columns"].values() if c.get("property_verified")
    )

    return result


def correct_skeleton_from_verification(
    skeleton_csv: str,
    verification: dict,
) -> str:
    """Replace invalid properties in skeleton with verified alternatives.

    For each column where verification found the property invalid and
    provided alternatives, replace the property in the skeleton CSV.

    Args:
        skeleton_csv: Original skeleton CSV string
        verification: Results from verify_skeleton_properties()

    Returns:
        Corrected skeleton CSV string
    """
    if not skeleton_csv or not verification:
        return skeleton_csv

    columns = verification.get("columns", {})
    # Build replacement map: old_property -> new_property
    replacements = {}
    for col_name, info in columns.items():
        if not info.get("property_verified") and info.get("alternatives"):
            old_prop = info.get("property", "")
            if old_prop:
                new_prop = info["alternatives"][0]  # Use top alternative
                replacements[old_prop] = new_prop
                logger.info(
                    "Correcting skeleton property: '%s' -> '%s' (for column '%s')",
                    old_prop, new_prop, col_name,
                )

    if not replacements:
        return skeleton_csv

    # Parse and correct the skeleton CSV
    reader = csv.reader(io.StringIO(skeleton_csv))
    rows = list(reader)
    corrected_rows = [rows[0]]  # Keep header

    for row in rows[1:]:
        if len(row) >= 2 and row[1].strip() in replacements:
            row = list(row)
            row[1] = replacements[row[1].strip()]
        corrected_rows.append(row)

    output = io.StringIO()
    writer = csv.writer(output)
    for row in corrected_rows:
        writer.writerow(row)

    corrected = output.getvalue()
    logger.info(
        "Corrected %d properties in skeleton (%d chars -> %d chars)",
        len(replacements), len(skeleton_csv), len(corrected),
    )
    return corrected


def _extract_properties_from_skeleton(
    skeleton_csv: str, manifest: dict
) -> Dict[str, Dict[str, Any]]:
    """Extract the property name used for each column from the skeleton CSV."""
    must_map_by_name = {}
    for entry in manifest.get("must_map", []):
        must_map_by_name[entry["column_name"]] = entry
    can_ignore_names = {
        e["column_name"].lower() for e in manifest.get("can_ignore", [])
    }

    column_props = {}
    if not skeleton_csv:
        return column_props

    reader = csv.reader(io.StringIO(skeleton_csv))
    rows = list(reader)

    for row in rows[1:]:  # skip header
        if not row or not row[0].strip():
            continue
        key = row[0].strip()
        prop = row[1].strip() if len(row) > 1 else ""

        # Skip #ignore columns
        if prop == "#ignore" or key.lower() in can_ignore_names:
            continue

        # Extract column name (handle COLUMN:VALUE format)
        col_name = key.split(":")[0] if ":" in key else key

        # Only track the first property seen per column
        if col_name not in column_props:
            entry = must_map_by_name.get(col_name, {})
            role = entry.get("role", "unknown")
            column_props[col_name] = {
                "property": prop,
                "role": role,
                "key": key,
                "property_verified": False,
                "verification_source": "unverified",
                "alternatives": [],
                "confidence": "low",
            }

    return column_props


def _verify_via_schemaorg(
    column_properties: Dict[str, dict], result: dict
) -> None:
    """Tier 1: Check properties against local Schema.org cache."""
    try:
        from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab
        vocab = SchemaOrgVocab.instance()
    except Exception:
        logger.warning("Schema.org vocab not available, skipping tier 1")
        for col_name, info in column_properties.items():
            result["columns"][col_name] = info
        return

    for col_name, info in column_properties.items():
        prop = info["property"]
        role = info["role"]

        # Place/time/value columns have fixed properties — always valid
        if role in ("place", "time", "value"):
            info["property_verified"] = True
            info["verification_source"] = "built_in"
            info["confidence"] = "high"
            if role == "place":
                result["place_verified"] = True
            result["columns"][col_name] = info
            continue

        # Empty property — LLM will fill, mark as unverified
        if not prop:
            info["property_verified"] = False
            info["verification_source"] = "unverified"
            info["confidence"] = "low"
            result["columns"][col_name] = info
            continue

        # Check if it's a DC built-in
        if prop.lower() in ALWAYS_VALID_PROPERTIES:
            info["property_verified"] = True
            info["verification_source"] = "dc_built_in"
            info["confidence"] = "high"
            result["columns"][col_name] = info
            continue

        # Check Schema.org
        prop_info = vocab.get_property(prop)
        if prop_info is not None:
            info["property_verified"] = True
            info["verification_source"] = "schema_org"
            info["confidence"] = "high"
            result["columns"][col_name] = info
            continue

        # Check if it's a known DC extension property
        if hasattr(vocab, 'is_known_dc_property') and vocab.is_known_dc_property(prop):
            info["property_verified"] = True
            info["verification_source"] = "dc_extension"
            info["confidence"] = "medium"
            result["columns"][col_name] = info
            continue

        # Not found — search for alternatives
        alternatives = vocab.search_properties(prop, limit=3)
        info["alternatives"] = [a["name"] for a in alternatives]
        info["property_verified"] = False
        info["verification_source"] = "unverified"
        info["confidence"] = "low"
        result["columns"][col_name] = info


def _verify_via_dc_api(
    column_properties: Dict[str, dict],
    result: dict,
    data_context: dict,
) -> None:
    """Tier 2: Verify place resolution and property DCIDs via DC API."""
    try:
        from src.data_commons.api.dc_api_wrapper import (
            dc_api_resolve_placeid,
            dc_api_is_defined_dcid,
        )
    except Exception:
        logger.warning("DC API not available, skipping tier 2")
        return

    # Verify place column resolution
    geography = data_context.get("geography", {})
    geo_format = geography.get("format", "NAME")
    sample_values = geography.get("sample_values", [])[:3]

    if sample_values:
        try:
            in_prop_map = {
                "FIPS_STATE": "geoId", "FIPS_COUNTY": "geoId", "FIPS": "geoId",
                "ISO_2": "isoCode", "ISO_3": "isoCode",
                "NAME": "name", "DC_DCID": "dcid",
            }
            in_prop = in_prop_map.get(geo_format, "name")
            resolved = dc_api_resolve_placeid(sample_values, in_prop=in_prop)
            resolved_count = sum(1 for v in resolved.values() if v)
            result["place_verified"] = resolved_count > 0

            for col_name, info in column_properties.items():
                if info["role"] == "place":
                    if resolved_count >= len(sample_values) * 0.5:
                        info["confidence"] = "high"
                        info["verification_source"] = "dc_api"
                    else:
                        info["confidence"] = "medium"
                    result["columns"][col_name] = info

            logger.info(
                "DC API place verification: %d/%d resolved",
                resolved_count, len(sample_values),
            )
        except Exception as e:
            logger.warning("DC API place verification failed: %s", e)

    # Verify unverified dimension properties exist as DCIDs
    props_to_check = []
    prop_to_col = {}
    for col_name, info in column_properties.items():
        if (info["role"] == "dimension"
                and info["property"]
                and not info.get("property_verified")):
            props_to_check.append(info["property"])
            prop_to_col[info["property"]] = col_name

    if props_to_check:
        try:
            existence = dc_api_is_defined_dcid(props_to_check)
            for prop, exists in existence.items():
                col_name = prop_to_col.get(prop)
                if col_name and col_name in result["columns"]:
                    if exists:
                        result["columns"][col_name]["property_verified"] = True
                        result["columns"][col_name]["verification_source"] = "dc_api"
                        result["columns"][col_name]["confidence"] = "high"
            logger.info("DC API property verification: %s", existence)
        except Exception as e:
            logger.warning("DC API property verification failed: %s", e)


def _enrich_via_mcp(
    column_properties: Dict[str, dict],
    result: dict,
    data_context: dict,
    mcp_url: str,
) -> None:
    """Tier 3: MCP enrichment for unverified columns."""
    unverified = [
        (col, info) for col, info in column_properties.items()
        if not info.get("property_verified") and info["role"] == "dimension"
    ]
    if not unverified:
        return

    try:
        from src.agents.dc_query_agent import (
            create_enrichment_agent, run_mcp_query, parse_statvars,
        )
    except Exception:
        logger.warning("MCP query module not available, skipping tier 3")
        return

    import asyncio

    for col_name, info in unverified[:3]:  # Max 3 MCP calls
        query = (
            f"What Data Commons property represents '{col_name}' "
            f"with values like {info.get('key', col_name)}?"
        )
        try:
            agent = create_enrichment_agent(
                mcp_url=mcp_url,
                model="gemini-3-flash-preview",
                data_context=data_context,
                attempt=0,
                error_feedback="",
            )
            response = asyncio.run(run_mcp_query(mcp_url, agent, query))
            if response:
                statvars = parse_statvars(response)
                if statvars:
                    info["mcp_candidates"] = statvars[:3]
                    info["verification_source"] = "mcp"
                    info["confidence"] = "medium"
                    result["columns"][col_name] = info
            logger.info(
                "MCP enrichment for '%s': %s",
                col_name, response[:100] if response else "empty",
            )
        except Exception as e:
            logger.warning("MCP enrichment for '%s' failed: %s", col_name, e)
