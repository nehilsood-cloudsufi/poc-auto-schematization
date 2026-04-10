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
    # --- Collect all rows (as lists of cells) to determine max width ---
    rows: list[list[str]] = []

    # Column rows
    for col in plan.active_columns:
        candidate = col.candidates[col.selected_index]
        cells = [col.column_name] + _build_property_value_pairs(
            candidate.property, candidate.value_expression
        )
        rows.append(cells)

    # Static-properties row: empty key, then property/value pairs
    static_cells: list[str] = [""]
    for sp in plan.static_properties:
        candidate = sp.candidates[sp.selected_index]
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
