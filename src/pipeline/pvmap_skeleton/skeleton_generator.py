"""
Generate PVMAP skeleton and column manifest from data_context.

The skeleton provides a pre-filled baseline PVMAP that the LLM starts from,
ensuring all columns are accounted for. The manifest classifies each column
as must-map or can-ignore for completeness checking.
"""

import csv
import io
import json
import logging
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Maximum dimension values to enumerate per column
MAX_DIMENSION_VALUES = 100

# Maximum total rows in skeleton (prevent token explosion on wide datasets)
MAX_SKELETON_ROWS = 300

# Geo format to DCID template mapping (mirrors context_assembler.py GEO_FORMAT_MAP)
GEO_DCID_TEMPLATES = {
    "FIPS_STATE": "geoId/{Data}",
    "FIPS_COUNTY": "geoId/{Data}",
    "FIPS": "geoId/{Data}",
    "ISO_2": "country/{Data}",
    "ISO_3": "country/{Data}",
    "DC_DCID": "{Data}",
    "NAME": "{Data}",
    "NUMERIC_CODE": "geoId/{Data}",
}

# Time formats that represent pure years (use {Number})
NUMERIC_TIME_FORMATS = {"YYYY", "YEAR"}


def build_column_manifest(data_context: dict) -> dict:
    """Classify every column as must-map or can-ignore.

    Args:
        data_context: Dict from context_assembler with column_roles,
            dimension_domains, column_stats, geography, time, value_columns, etc.

    Returns:
        {
            "must_map": [{"column_name", "role", "suggested_property", "cardinality", "sample_values"}],
            "can_ignore": [...],
            "all_columns": [str],
        }
    """
    column_roles = data_context.get("column_roles", {})
    column_stats = data_context.get("column_stats", {})
    all_columns = data_context.get("all_columns", [])
    dimension_domains = data_context.get("dimension_domains", {})

    # Extract dc_property mappings from skeleton_summary (set by RelationalSkeleton edges)
    # Format in skeleton: "  - `agecat` qualifies `NIPR` (dc_property: age)"
    dc_property_map = _extract_dc_properties(data_context.get("skeleton_summary", ""))

    must_map: List[Dict[str, Any]] = []
    can_ignore: List[Dict[str, Any]] = []

    # Map role -> suggested DC property
    role_to_property = {
        "place": "observationAbout",
        "time": "observationDate",
        "value": "value",
    }

    for col in all_columns:
        role = column_roles.get(col, "")
        stats = column_stats.get(col, {})
        cardinality = stats.get("cardinality", 0)
        sample_values = stats.get("sample_values", [])

        entry = {
            "column_name": col,
            "role": role,
            "suggested_property": role_to_property.get(role, ""),
            "cardinality": cardinality,
            "sample_values": sample_values[:5],
        }

        if role == "metadata":
            can_ignore.append(entry)
        elif role == "dimension":
            # Dimension columns need COLUMN:VALUE enumeration
            domain = dimension_domains.get(col, [])
            # Use dc_property from RelationalSkeleton if available
            dc_prop = dc_property_map.get(col, "")
            entry["suggested_property"] = dc_prop if dc_prop else "dimension"
            entry["dc_property"] = dc_prop
            entry["domain_values"] = domain[:MAX_DIMENSION_VALUES]
            entry["domain_truncated"] = len(domain) > MAX_DIMENSION_VALUES
            must_map.append(entry)
        elif role in role_to_property:
            must_map.append(entry)
        else:
            # Unknown role — treat as must-map to be safe
            entry["role"] = role or "unknown"
            entry["suggested_property"] = ""
            must_map.append(entry)

    logger.info(
        "Column manifest: %d must-map, %d can-ignore, %d total",
        len(must_map), len(can_ignore), len(all_columns),
    )

    return {
        "must_map": must_map,
        "can_ignore": can_ignore,
        "all_columns": all_columns,
    }


def generate_pvmap_skeleton(manifest: dict, data_context: dict) -> str:
    """Generate a CSV-formatted PVMAP skeleton from the column manifest.

    The skeleton includes:
    - Header row: key,prop,val,p1,v1
    - One row per place/time/value column with appropriate placeholders
    - COLUMN:VALUE rows for dimension columns (capped at MAX_DIMENSION_VALUES)
    - #ignore rows for metadata columns

    Args:
        manifest: Output of build_column_manifest()
        data_context: Full data_context dict for geography/time format info

    Returns:
        CSV string with PVMAP skeleton
    """
    rows: List[List[str]] = []

    geography = data_context.get("geography", {})
    time_info = data_context.get("time", {})
    population_type = data_context.get("population_type", "")
    measurement_type = data_context.get("measurement_type", "")

    # Process must-map columns
    for entry in manifest.get("must_map", []):
        col = entry["column_name"]
        role = entry["role"]

        if role == "place":
            dcid_template = _get_place_template(geography)
            rows.append([col, "observationAbout", dcid_template])

        elif role == "time":
            time_placeholder = _get_time_placeholder(time_info)
            rows.append([col, "observationDate", time_placeholder])

        elif role == "value":
            # Value columns need measuredProperty and populationType
            row = [col, "value", "{Number}"]
            if population_type:
                row.extend(["populationType", population_type])
            else:
                row.extend(["populationType", "TODO"])
            if measurement_type:
                row.extend(["measuredProperty", _measurement_to_property(measurement_type)])
            else:
                row.extend(["measuredProperty", "TODO"])
            rows.append(row)

        elif role == "dimension":
            # Enumerate COLUMN:VALUE rows.
            # Use dc_property from RelationalSkeleton if available (e.g., "gender", "age").
            # Otherwise leave empty for LLM to fill.
            dc_prop = entry.get("dc_property", "")
            domain = entry.get("domain_values", [])
            if domain:
                for val in domain:
                    val_str = str(val)
                    rows.append([f"{col}:{val_str}", dc_prop, val_str])
            else:
                # No domain values known — single placeholder row
                rows.append([col, dc_prop, "{Data}"])

        else:
            # Unknown role — placeholder row, empty property for LLM to fill
            rows.append([col, "", "{Data}"])

    # Process can-ignore columns
    for entry in manifest.get("can_ignore", []):
        col = entry["column_name"]
        rows.append([col, "#ignore", ""])

    if not rows:
        return ""

    # Cap total rows to prevent token explosion on wide/multi-dimension datasets
    if len(rows) > MAX_SKELETON_ROWS:
        logger.warning(
            "Skeleton rows (%d) exceeds MAX_SKELETON_ROWS (%d), truncating",
            len(rows), MAX_SKELETON_ROWS,
        )
        rows = rows[:MAX_SKELETON_ROWS]

    # Determine max columns needed (some rows have p1,v1 pairs)
    max_cols = max(len(r) for r in rows)
    # Ensure minimum 3 columns (key, prop, val)
    max_cols = max(max_cols, 3)

    # Build header: "key" followed by empty column names (positional format).
    # The stat_var_processor reads columns positionally, not by name.
    # Ground truth PVMAPs use this format: key,,,,,,
    header = ["key"] + [""] * (max_cols - 1)

    # Write CSV
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(header[:max_cols])
    for row in rows:
        # Pad row to match header length
        padded = row + [""] * (max_cols - len(row))
        writer.writerow(padded[:max_cols])

    result = output.getvalue()
    logger.info(
        "Generated PVMAP skeleton: %d rows, %d chars",
        len(rows), len(result),
    )
    return result


def format_completeness_report(completeness: dict) -> str:
    """Format a column completeness check result into a readable report.

    Args:
        completeness: Output of check_column_completeness() from heuristic_quality.py

    Returns:
        Human-readable markdown string for injection into feedback prompt.
    """
    if not completeness:
        return ""

    severity = completeness.get("severity", "ok")
    missing = completeness.get("missing_must_map", [])
    ratio = completeness.get("coverage_ratio", 1.0)

    if severity == "ok":
        return f"All must-map columns are present (coverage: {ratio:.0%})."

    lines = [f"**Column Coverage: {ratio:.0%}** — Severity: **{severity.upper()}**", ""]
    lines.append("Missing must-map columns:")
    for col_info in missing:
        col = col_info.get("column", "?")
        role = col_info.get("role", "?")
        prop = col_info.get("suggested_property", "")
        lines.append(f"- `{col}` [{role.upper()}] — should map to {prop}")

    return "\n".join(lines)


def _extract_dc_properties(skeleton_summary: str) -> Dict[str, str]:
    """Extract dc_property mappings from skeleton_summary text.

    Parses lines like:
        - `agecat` qualifies `NIPR` (dc_property: age)
        - `sexcat` qualifies `NIPR` (dc_property: gender)

    Returns:
        {column_name: dc_property} e.g. {"agecat": "age", "sexcat": "gender"}
    """
    dc_map: Dict[str, str] = {}
    if not skeleton_summary:
        return dc_map

    # Match column names with any characters (spaces, hyphens, dots, colons)
    pattern = re.compile(r"`([^`]+)`\s+qualifies\s+`[^`]+`\s+\(dc_property:\s+(\w+)\)")
    for match in pattern.finditer(skeleton_summary):
        col_name = match.group(1)
        dc_prop = match.group(2)
        if col_name not in dc_map:  # first match wins
            dc_map[col_name] = dc_prop

    return dc_map


def _get_place_template(geography: dict) -> str:
    """Get the DCID template for place columns based on geo format."""
    geo_format = geography.get("format", "NAME")
    return GEO_DCID_TEMPLATES.get(geo_format, "{Data}")


def _get_time_placeholder(time_info: dict) -> str:
    """Get the placeholder for time columns based on time format."""
    time_format = time_info.get("format", "YYYY")
    if time_format in NUMERIC_TIME_FORMATS:
        return "{Number}"
    return "{Data}"


def _measurement_to_property(measurement_type: str) -> str:
    """Convert measurement type to DC measuredProperty name.

    Only maps unambiguous types. Returns empty string for types where
    the correct property depends on dataset context (e.g., Median could
    be median age, income, or price).
    """
    mapping = {
        "Count": "count",
        "Percent": "percent",
        "Rate": "count",
        "Amount": "amount",
    }
    return mapping.get(measurement_type, "")


def write_discovery_artifact(
    manifest: dict,
    verification: dict,
    data_context: dict,
    output_dir: str,
) -> str:
    """Write column_discovery.json artifact for transparency.

    Args:
        manifest: Column manifest from build_column_manifest()
        verification: Results from verify_skeleton_properties()
        data_context: Full data_context dict
        output_dir: Dataset output directory

    Returns:
        Path to written file
    """
    artifact = {
        "timestamp": datetime.now().isoformat(),
        "dataset": data_context.get("dataset_name", "unknown"),
        "total_columns": len(manifest.get("all_columns", [])),
        "must_map": len(manifest.get("must_map", [])),
        "can_ignore": len(manifest.get("can_ignore", [])),
        "verification_summary": {
            "properties_checked": verification.get("properties_checked", 0),
            "properties_valid": verification.get("properties_valid", 0),
            "place_verified": verification.get("place_verified", False),
            "sources_used": verification.get("verification_sources", []),
        },
        "columns": {},
    }

    # Merge manifest + verification per column
    for entry in manifest.get("must_map", []):
        col = entry["column_name"]
        col_data = {
            "role": entry["role"],
            "suggested_property": entry.get("suggested_property", ""),
            "cardinality": entry.get("cardinality", 0),
            "sample_values": entry.get("sample_values", []),
        }
        if col in verification.get("columns", {}):
            v = verification["columns"][col]
            col_data["verified"] = v.get("property_verified", False)
            col_data["verification_source"] = v.get("verification_source", "")
            col_data["confidence"] = v.get("confidence", "low")
            col_data["alternatives"] = v.get("alternatives", [])
        artifact["columns"][col] = col_data

    for entry in manifest.get("can_ignore", []):
        artifact["columns"][entry["column_name"]] = {
            "role": "metadata",
            "action": "ignore",
        }

    output_path = Path(output_dir) / "column_discovery.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(artifact, f, indent=2, default=str)

    logger.info("Wrote column discovery artifact: %s", output_path)
    return str(output_path)
