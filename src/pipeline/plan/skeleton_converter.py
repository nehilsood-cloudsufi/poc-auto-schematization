"""Convert an approved MappingPlan into a partial PVMAP CSV skeleton."""
from __future__ import annotations

import csv
import io
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.api.models.plan import MappingPlan


def _convert_placeholders(value: str) -> str:
    """Convert plan-style placeholders to PVMAP CSV format.

    [DATA] -> {Data}, [NUMBER] -> {Number}
    """
    return value.replace("[DATA]", "{Data}").replace("[NUMBER]", "{Number}")


def _build_property_value_pairs(
    prop: str, value_expr: str
) -> list[str]:
    """Return a flat [property, value] list for one candidate."""
    return [prop, _convert_placeholders(value_expr)]


def plan_to_skeleton_csv(plan: "MappingPlan") -> str:
    """Convert a MappingPlan with selected candidates to a PVMAP CSV string.

    Parameters
    ----------
    plan : MappingPlan
        A mapping plan with ``selected_index`` set on each column/static
        property (defaults to 0 if untouched).

    Returns
    -------
    str
        A CSV string in PVMAP format with a header row, column rows, and a
        static-properties row.
    """
    # If EnrichedMappingPlan with mapping_rules that have pvmap_rows,
    # use them directly instead of generating from candidates
    if hasattr(plan, 'mapping_rules') and plan.mapping_rules:
        all_pvmap_rows = []
        for rule in plan.mapping_rules:
            if rule.pvmap_rows:
                all_pvmap_rows.extend(rule.pvmap_rows)
        if all_pvmap_rows:
            max_cols = max(len(row.split(",")) for row in all_pvmap_rows)
            header = "key" + "," * (max_cols - 1)
            lines = [header] + all_pvmap_rows
            return "\n".join(lines) + "\n"

    # --- Collect all rows (as lists of cells) to determine max width ---
    rows: list[list[str]] = []

    # Column rows
    for col in plan.active_columns:
        idx = col.selected_index
        if not col.candidates or idx < 0 or idx >= len(col.candidates):
            idx = 0  # fallback to first candidate
        if not col.candidates:
            continue  # skip columns with no candidates
        candidate = col.candidates[idx]
        cells = [col.column_name] + _build_property_value_pairs(
            candidate.property, candidate.value_expression
        )
        rows.append(cells)

    # Static-properties row: empty key, then property/value pairs
    static_cells: list[str] = [""]
    for sp in plan.static_properties:
        idx = sp.selected_index
        if not sp.candidates or idx < 0 or idx >= len(sp.candidates):
            idx = 0
        if not sp.candidates:
            continue
        candidate = sp.candidates[idx]
        static_cells += _build_property_value_pairs(
            candidate.property, candidate.value_expression
        )

    if len(plan.static_properties) > 0:
        rows.append(static_cells)

    # --- Determine the widest row to size the header ---
    if not rows:
        # Empty plan: just a header with the key column
        max_width = 1
    else:
        max_width = max(len(r) for r in rows)

    # Header: "key" followed by enough empty columns
    # We need max_width columns total; first is "key"
    header = ["key"] + [""] * (max_width - 1)

    # --- Pad all rows to the same width for consistent CSV ---
    padded_rows = [header]
    for row in rows:
        padded = row + [""] * (max_width - len(row))
        padded_rows.append(padded)

    # --- Write CSV ---
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(padded_rows)
    return buf.getvalue()
