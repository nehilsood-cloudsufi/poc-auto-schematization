"""
Generate PVMAP skeleton and column manifest from data_context.

The skeleton provides a pre-filled baseline PVMAP that the LLM starts from,
ensuring all columns are accounted for. The manifest classifies each column
as must-map or can-ignore for completeness checking.
"""

import csv
import io
import logging
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

# Maximum dimension values to enumerate per column
MAX_DIMENSION_VALUES = 100

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
            entry["suggested_property"] = "dimension"
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
            # Enumerate COLUMN:VALUE rows — leave property empty for LLM to fill.
            # Using "TODO" confuses the LLM into copying it literally.
            domain = entry.get("domain_values", [])
            if domain:
                for val in domain:
                    val_str = str(val)
                    rows.append([f"{col}:{val_str}", "", val_str])
            else:
                # No domain values known — single placeholder row
                rows.append([col, "", "{Data}"])

        else:
            # Unknown role — placeholder row, empty property for LLM to fill
            rows.append([col, "", "{Data}"])

    # Process can-ignore columns
    for entry in manifest.get("can_ignore", []):
        col = entry["column_name"]
        rows.append([col, "#ignore", ""])

    if not rows:
        return ""

    # Determine max columns needed (some rows have p1,v1 pairs)
    max_cols = max(len(r) for r in rows)
    # Ensure minimum 3 columns (key, prop, val)
    max_cols = max(max_cols, 3)

    # Build header
    header = ["key", "prop", "val"]
    for i in range(1, (max_cols - 3) // 2 + 1):
        header.extend([f"p{i}", f"v{i}"])
    # Pad header if needed
    while len(header) < max_cols:
        header.append(f"p{len(header) // 2}")

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
    """Convert measurement type to DC measuredProperty name."""
    mapping = {
        "Count": "count",
        "Percent": "count",
        "Rate": "count",
        "Median": "income",
        "Mean": "income",
        "Amount": "amount",
    }
    return mapping.get(measurement_type, "count")
