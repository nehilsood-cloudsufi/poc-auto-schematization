"""Programmatic safeguards that run between plan approval and PVMAP generation.

These mitigations apply deterministic fixes that the LLM might miss:
- Total-indicator overrides (DROP_CONSTRAINT for aggregate rows)
- Column alignment pre-flight checks
- Place/time format normalization
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from src.api.models.plan import EnrichedMappingPlan

logger = logging.getLogger(__name__)

# Values that represent "total / aggregate" rows — should be DROP_CONSTRAINT,
# not mapped to a specific DCID.
TOTAL_INDICATORS = {
    "T", "Total", "All", "Both", "Both Sexes", "All Races",
    "All Ages", "Overall", "TOT", "-", "*", "~",
    "00", "000", "999", "",
}


def strip_total_indicators(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """Override value mappings whose raw_value is a known total indicator.

    For each ValueDictionary in the plan, any ValueMapping whose stripped
    raw_value appears in TOTAL_INDICATORS gets action=DROP_CONSTRAINT,
    dcid=None, with an updated reason.
    """
    for vd in plan.value_dictionaries:
        for mapping in vd.mappings:
            if mapping.raw_value.strip() in TOTAL_INDICATORS:
                mapping.action = "DROP_CONSTRAINT"
                mapping.dcid = None
                mapping.reason = (
                    f"Total indicator detected: '{mapping.raw_value.strip()}' — "
                    "aggregate rows should drop this constraint"
                )
    return plan


def check_column_alignment(
    plan: EnrichedMappingPlan,
    full_data_path: str,
) -> list[str]:
    """Compare plan columns against the actual CSV headers.

    Returns a list of issue strings (empty = all good).
    Does NOT raise — callers decide severity.
    """
    csv_path = Path(full_data_path)
    csv_columns = set(pd.read_csv(csv_path, nrows=0).columns)

    plan_columns = set()
    for col in plan.active_columns:
        plan_columns.add(col.column_name)
    for col in plan.ignored_columns:
        plan_columns.add(col.column_name)

    issues: list[str] = []

    # Columns the plan references but CSV doesn't have
    missing = plan_columns - csv_columns
    for col_name in sorted(missing):
        issues.append(
            f"Plan column '{col_name}' not found in CSV headers"
        )

    # Columns in CSV that the plan doesn't mention
    unmapped = csv_columns - plan_columns
    for col_name in sorted(unmapped):
        issues.append(
            f"CSV column '{col_name}' not covered by plan (neither active nor ignored)"
        )

    return issues


def normalize_place_formats(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """Apply place_resolution.prefix_rule to the selected candidate's value_expression.

    If plan.place_resolution exists and has a prefix_rule, find the matching
    active column and update its selected candidate's value_expression to
    include the prefix (e.g. "country/[DATA]").  Avoids double-prefixing.
    """
    if plan.place_resolution is None:
        return plan

    pr = plan.place_resolution
    if not pr.prefix_rule:
        return plan

    for col in plan.active_columns:
        if col.column_name == pr.column_name:
            candidate = col.candidates[col.selected_index]
            if pr.prefix_rule not in candidate.value_expression:
                candidate.value_expression = f"{pr.prefix_rule}[DATA]"
            break

    return plan


def normalize_time_formats(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """Placeholder for time format normalization — returns plan unchanged."""
    return plan


def apply_mitigations(
    plan: EnrichedMappingPlan,
    full_data_path: str,
) -> EnrichedMappingPlan:
    """Run all mitigations in sequence.

    1. strip_total_indicators — override aggregate value mappings
    2. check_column_alignment — log warnings for mismatches
    3. normalize_place_formats — apply prefix rules
    4. normalize_time_formats — (placeholder)
    """
    plan = strip_total_indicators(plan)

    issues = check_column_alignment(plan, full_data_path)
    for issue in issues:
        logger.warning("Column alignment: %s", issue)

    plan = normalize_place_formats(plan)
    plan = normalize_time_formats(plan)

    return plan
