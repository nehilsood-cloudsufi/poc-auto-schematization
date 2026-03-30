"""Tier 1 counter-driven PVMAP correction rule engine.

Applies programmatic fixes to PVMAP CSV strings based on enriched FilteredLogs
data from log_filter.py. This runs AFTER validation fails and BEFORE any LLM
retry, attempting fast deterministic repairs.

Each rule targets a specific error type from the stat_var_processor counters.
Rules are sorted by priority and applied in order. Changes are accumulated
and returned alongside the corrected PVMAP CSV.

Usage:
    from src.pipeline.validation.pvmap_corrector import apply_correction_rules

    corrected_csv, changes = apply_correction_rules(
        pvmap_csv=raw_pvmap,
        filtered_logs=filtered,
        key_match_report=report_text,
        input_data_path=Path("input/dataset/test_data/data_input.csv"),
    )
"""

import csv
import difflib
import io
import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Dict, List, Optional, Tuple

from src.pipeline.validation.log_filter import (
    FilteredLogs,
    detect_systematic_patterns,
    _detect_format_pattern,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# CorrectionRule dataclass
# ---------------------------------------------------------------------------

@dataclass
class CorrectionRule:
    """A single correction rule targeting a specific error type.

    Attributes:
        name: Human-readable rule identifier (e.g., 'fix_key_mismatch').
        error_type: The counter error key this rule addresses.
        priority: Execution order -- lower values run first.
        condition: Callable(filtered_logs, context) -> bool.
        apply: Callable(pvmap_csv, filtered_logs, context) -> pvmap_csv.
    """
    name: str
    error_type: str
    priority: int
    condition: Callable[[FilteredLogs, dict], bool]
    apply: Callable[[str, FilteredLogs, dict], str]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_pvmap_rows(pvmap_csv: str) -> List[List[str]]:
    """Parse PVMAP CSV string into list of rows."""
    reader = csv.reader(io.StringIO(pvmap_csv))
    return list(reader)


def _rows_to_csv(rows: List[List[str]]) -> str:
    """Convert list of rows back to CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerows(rows)
    return buf.getvalue()


def _load_headers_from_path(input_data_path: Path) -> List[str]:
    """Read first row of input CSV and return column headers."""
    try:
        with open(input_data_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            return [re.sub(r'\\s+', ' ', h).strip() for h in headers]
    except Exception:
        return []


def _parse_headers_from_key_match_report(report: str) -> List[str]:
    """Extract actual column headers mentioned in key_match_report text.

    Looks for lines like:
      Actual headers: ['col1', 'col2', ...]
      Available columns: col1, col2, ...
      Header: col1 | col2 | ...
    Or lines starting with "  - " listing individual headers.
    """
    headers: List[str] = []

    # Pattern: Actual headers: ['col1', 'col2']
    m = re.search(r"(?:Actual|Available|Input)\s+(?:headers|columns)\s*:\s*\[([^\]]+)\]", report, re.IGNORECASE)
    if m:
        raw = m.group(1)
        # Parse quoted strings
        headers = [s.strip().strip("'\"") for s in raw.split(',')]
        return [h for h in headers if h]

    # Pattern: comma-separated after "columns:" or "headers:"
    m = re.search(r"(?:columns|headers)\s*:\s*(.+)", report, re.IGNORECASE)
    if m:
        raw = m.group(1).strip()
        headers = [s.strip().strip("'\"") for s in raw.split(',')]
        return [h for h in headers if h]

    return headers


def _parse_unmatched_keys_from_report(report: str) -> List[str]:
    """Extract unmatched PVMAP keys from key_match_report.

    Looks for patterns like:
      Unmatched PVMAP keys: key1, key2
      UNMATCHED: key1
      - UNMATCHED: "key1"
      key1 -> NO MATCH
    """
    unmatched: List[str] = []

    # Pattern: Unmatched PVMAP keys: key1, key2
    m = re.search(r"[Uu]nmatched.*?keys?\s*:\s*(.+)", report)
    if m:
        raw = m.group(1).strip()
        unmatched = [s.strip().strip("'\"") for s in raw.split(',')]
        return [k for k in unmatched if k]

    # Pattern: lines with "UNMATCHED" or "NO MATCH"
    for line in report.split('\n'):
        line = line.strip()
        m2 = re.match(r'[-*]\s*(?:UNMATCHED|NO MATCH)\s*:?\s*["\']?(.+?)["\']?\s*$', line, re.IGNORECASE)
        if m2:
            unmatched.append(m2.group(1).strip())
            continue
        m3 = re.match(r'["\']?(.+?)["\']?\s*(?:->|=>|:)\s*(?:NO MATCH|UNMATCHED)', line, re.IGNORECASE)
        if m3:
            unmatched.append(m3.group(1).strip())

    return unmatched


def _get_actual_headers(
    input_data_path: Optional[Path],
    key_match_report: str,
) -> List[str]:
    """Get actual column headers from input file or key_match_report."""
    if input_data_path and input_data_path.exists():
        headers = _load_headers_from_path(input_data_path)
        if headers:
            return headers
    return _parse_headers_from_key_match_report(key_match_report)


# ---------------------------------------------------------------------------
# Rule 0: fix_key_mismatch
# ---------------------------------------------------------------------------

def _condition_key_mismatch(filtered_logs: FilteredLogs, ctx: dict) -> bool:
    """Check if key mismatch errors exist and report has unmatched keys."""
    error_type = 'error-pvmap-dropped-undefined-property'
    has_errors = (
        error_type in filtered_logs.errors and filtered_logs.errors[error_type] > 0
    ) or (
        error_type in filtered_logs.error_examples and len(filtered_logs.error_examples[error_type]) > 0
    )
    report = ctx.get('key_match_report', '')
    has_unmatched = bool(report and (
        'unmatched' in report.lower() or
        'no match' in report.lower() or
        'undefined' in report.lower()
    ))
    return has_errors and has_unmatched


def _apply_key_mismatch(pvmap_csv: str, filtered_logs: FilteredLogs, ctx: dict) -> str:
    """Replace mismatched PVMAP keys with best-matching actual headers."""
    report = ctx.get('key_match_report', '')
    input_path = ctx.get('input_data_path')
    headers = _get_actual_headers(input_path, report)
    if not headers:
        return pvmap_csv

    unmatched = _parse_unmatched_keys_from_report(report)
    # Also pull from error_examples if available
    error_type = 'error-pvmap-dropped-undefined-property'
    if error_type in filtered_logs.error_examples:
        for val, _count in filtered_logs.error_examples[error_type]:
            if val not in unmatched:
                unmatched.append(val)

    if not unmatched:
        return pvmap_csv

    # Build replacement map using case-insensitive matching
    headers_lower = {h.lower(): h for h in headers}
    replacements: Dict[str, str] = {}
    for bad_key in unmatched:
        # For COLUMN:VALUE syntax, only match the column part
        col_part = bad_key.split(':')[0] if ':' in bad_key else bad_key

        # 1. Exact case-insensitive match
        if col_part.lower() in headers_lower:
            replacements[bad_key] = headers_lower[col_part.lower()]
            continue

        # 2. Fuzzy match (case-insensitive via lowered comparison)
        matches = difflib.get_close_matches(
            col_part.lower(), [h.lower() for h in headers], n=1, cutoff=0.8
        )
        if matches:
            # Map back to original-cased header
            replacements[bad_key] = headers_lower[matches[0]]

    if not replacements:
        return pvmap_csv

    # Apply replacements to PVMAP rows
    rows = _parse_pvmap_rows(pvmap_csv)
    new_rows = []
    for row in rows:
        if not row:
            new_rows.append(row)
            continue
        key = row[0]
        # Check for COLUMN:VALUE syntax
        if ':' in key:
            col_part, _, value_part = key.partition(':')
            if key in replacements:
                # Full key was unmatched, replace column part only
                new_key = replacements[key]
                if ':' not in new_key:
                    new_key = new_key + ':' + value_part
                row = [new_key] + row[1:]
            elif col_part in replacements:
                row = [replacements[col_part] + ':' + value_part] + row[1:]
        elif key in replacements:
            row = [replacements[key]] + row[1:]
        new_rows.append(row)

    return _rows_to_csv(new_rows)


# ---------------------------------------------------------------------------
# Rule 1: fix_place_leading_zeros
# ---------------------------------------------------------------------------

def _condition_place_leading_zeros(filtered_logs: FilteredLogs, ctx: dict) -> bool:
    """Check for place errors with missing_leading_zeros pattern."""
    error_type = 'error-unresolved-place'
    if error_type not in filtered_logs.errors or filtered_logs.errors[error_type] == 0:
        return False

    examples = filtered_logs.error_examples.get(error_type, [])
    if not examples:
        return False

    total_count = filtered_logs.errors.get(error_type, 0)
    patterns = detect_systematic_patterns(error_type, examples, total_count)
    return any(p.get('pattern') == 'missing_leading_zeros' for p in patterns)


def _apply_place_leading_zeros(pvmap_csv: str, filtered_logs: FilteredLogs, ctx: dict) -> str:
    """Add zero-padding to place placeholder in observationAbout row."""
    # Determine padding width from examples
    examples = filtered_logs.error_examples.get('error-unresolved-place', [])
    values = [v for v, _ in examples]
    max_len = max((len(v) for v in values if v.isdigit()), default=1)

    # If examples show 4-5 digit values, use 5-digit padding (county FIPS)
    # If 1-2 digit values, use 2-digit padding (state FIPS)
    if max_len >= 4:
        pad_width = 5
    else:
        pad_width = 2

    rows = _parse_pvmap_rows(pvmap_csv)
    new_rows = []
    for row in rows:
        if not row or len(row) < 3:
            new_rows.append(row)
            continue

        # Find observationAbout rows
        is_obs_about = any(
            cell.strip() == 'observationAbout' for cell in row[1:]
        )
        if not is_obs_about:
            new_rows.append(row)
            continue

        # Replace placeholders with padded versions
        new_row = []
        for cell in row:
            new_cell = cell
            # geoId/{Number} -> geoId/{Number:02d}
            new_cell = re.sub(
                r'geoId/\{Number\}',
                f'geoId/{{Number:0{pad_width}d}}',
                new_cell,
            )
            # geoId/{Data} -> geoId/{Data:0>N}
            new_cell = re.sub(
                r'geoId/\{Data\}',
                f'geoId/{{Data:0>{pad_width}}}',
                new_cell,
            )
            new_row.append(new_cell)
        new_rows.append(new_row)

    return _rows_to_csv(new_rows)


# ---------------------------------------------------------------------------
# Rule 2: fix_place_prefix
# ---------------------------------------------------------------------------

def _condition_place_prefix(filtered_logs: FilteredLogs, ctx: dict) -> bool:
    """Check if place errors show bare FIPS values without geoId/ prefix."""
    error_type = 'error-unresolved-place'
    if error_type not in filtered_logs.errors or filtered_logs.errors[error_type] == 0:
        return False

    examples = filtered_logs.error_examples.get(error_type, [])
    if not examples:
        return False

    # Check if examples are bare numeric values (FIPS-like)
    bare_count = sum(1 for v, _ in examples if re.match(r'^\d{1,5}$', v))
    return bare_count > len(examples) * 0.5


def _apply_place_prefix(pvmap_csv: str, filtered_logs: FilteredLogs, ctx: dict) -> str:
    """Ensure observationAbout row has geoId/ prefix before placeholder."""
    rows = _parse_pvmap_rows(pvmap_csv)
    new_rows = []
    for row in rows:
        if not row or len(row) < 3:
            new_rows.append(row)
            continue

        is_obs_about = any(
            cell.strip() == 'observationAbout' for cell in row[1:]
        )
        if not is_obs_about:
            new_rows.append(row)
            continue

        new_row = []
        for i, cell in enumerate(row):
            new_cell = cell
            # Only modify value cells (even-indexed after the key column)
            # Check for bare placeholder without geoId/ prefix
            if i > 0:
                stripped = cell.strip()
                # {Data} or {Number} without geoId/ prefix
                if stripped in ('{Data}', '{Number}', 'dcid:{Data}', 'dcid:{Number}'):
                    if '{Data}' in stripped:
                        new_cell = 'dcid:geoId/{Data}'
                    elif '{Number}' in stripped:
                        new_cell = 'dcid:geoId/{Number}'
                # Already has dcid: but no geoId/
                elif re.match(r'^dcid:\{(Data|Number)\}$', stripped):
                    placeholder = re.search(r'\{(Data|Number)\}', stripped).group(0)
                    new_cell = f'dcid:geoId/{placeholder}'
            new_row.append(new_cell)
        new_rows.append(new_row)

    return _rows_to_csv(new_rows)


# ---------------------------------------------------------------------------
# Rule 3: fix_duplicate_observations (diagnostic only)
# ---------------------------------------------------------------------------

def _condition_duplicate_observations(filtered_logs: FilteredLogs, ctx: dict) -> bool:
    """Check for mismatched-svobs errors."""
    error_type = 'error-mismatched-svobs'
    return (
        error_type in filtered_logs.errors
        and filtered_logs.errors[error_type] > 0
    )


def _apply_duplicate_observations(pvmap_csv: str, filtered_logs: FilteredLogs, ctx: dict) -> str:
    """Cannot fix programmatically -- return PVMAP unchanged.

    The diagnostic message is added to the changes list by the caller
    via the context mechanism.
    """
    # We just return unchanged; the orchestrator reads diagnostics from context
    return pvmap_csv


def _diagnostic_duplicate_observations(filtered_logs: FilteredLogs) -> str:
    """Build diagnostic string for duplicate observations."""
    error_type = 'error-mismatched-svobs'
    count = filtered_logs.errors.get(error_type, 0)
    examples = filtered_logs.error_examples.get(error_type, [])

    lines = [
        f"DIAGNOSTIC: {count} duplicate observation(s) detected.",
        "Multiple rows produce the same (Place + Date + StatVar) combination.",
        "A dimension column is likely missing from the PVMAP as a qualifier.",
    ]
    if examples:
        lines.append("Affected values:")
        for val, c in examples[:5]:
            lines.append(f"  - '{val}' ({c} occurrences)")
    lines.append(
        "FIX: Identify the unmapped dimension column (e.g., gender, age, race) "
        "and add it as a StatVar qualifier property."
    )
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Rule 4: fix_missing_required_props
# ---------------------------------------------------------------------------

def _condition_missing_required_props(filtered_logs: FilteredLogs, ctx: dict) -> bool:
    """Check for svobs-missing-property errors."""
    error_type = 'error-svobs-missing-property'
    return (
        error_type in filtered_logs.errors
        and filtered_logs.errors[error_type] > 0
    )


def _apply_missing_required_props(pvmap_csv: str, filtered_logs: FilteredLogs, ctx: dict) -> str:
    """Attempt structural CSV repair for malformed required property rows.

    Checks for:
    - Missing comma separators in property/value pairs
    - Odd number of cells after key (property/value must come in pairs)
    - Empty value cells next to property names
    """
    rows = _parse_pvmap_rows(pvmap_csv)
    new_rows = []
    changed = False

    for row in rows:
        if not row or len(row) < 2:
            new_rows.append(row)
            continue

        # Check for odd number of cells after key (properties come in pairs)
        data_cells = row[1:]
        if len(data_cells) % 2 != 0:
            # Odd count -- likely a missing comma or extra cell
            # Try to fix by removing trailing empty cell
            if data_cells and data_cells[-1].strip() == '':
                row = row[:-1]
                changed = True
            else:
                # Add empty cell to make pairs complete
                row = row + ['']
                changed = True

        new_rows.append(row)

    if changed:
        return _rows_to_csv(new_rows)
    return pvmap_csv


# ---------------------------------------------------------------------------
# Rule 5: fix_aggregate_invalid
# ---------------------------------------------------------------------------

def _condition_aggregate_invalid(filtered_logs: FilteredLogs, ctx: dict) -> bool:
    """Check for aggregate-invalid-values errors."""
    error_type = 'error-aggregate-invalid-values'
    return (
        error_type in filtered_logs.errors
        and filtered_logs.errors[error_type] > 0
    )


def _apply_aggregate_invalid(pvmap_csv: str, filtered_logs: FilteredLogs, ctx: dict) -> str:
    """Replace {Number} with {Data} for columns causing aggregation errors.

    When a column has non-numeric values but is mapped with {Number},
    the aggregation step fails. Switching to {Data} treats the values
    as text pass-through instead.
    """
    # Identify failing columns from error examples
    error_type = 'error-aggregate-invalid-values'
    examples = filtered_logs.error_examples.get(error_type, [])

    # Extract column names from examples -- examples may contain
    # column names or failing values
    failing_cols: List[str] = []
    for val, _count in examples:
        # Sometimes the example is "column_name: bad_value"
        if ':' in val:
            col = val.split(':')[0].strip()
            failing_cols.append(col)
        else:
            failing_cols.append(val)

    rows = _parse_pvmap_rows(pvmap_csv)
    new_rows = []
    changed = False

    for row in rows:
        if not row or len(row) < 3:
            new_rows.append(row)
            continue

        key = row[0]
        # Check if this row's key matches a failing column
        key_matches = (
            key in failing_cols
            or any(difflib.SequenceMatcher(None, key.lower(), fc.lower()).ratio() > 0.8
                   for fc in failing_cols)
        )

        if key_matches:
            # Replace {Number} with {Data} in value cells
            new_row = []
            for cell in row:
                if cell.strip() == '{Number}':
                    new_row.append('{Data}')
                    changed = True
                else:
                    new_row.append(cell)
            new_rows.append(new_row)
        else:
            # Even if key doesn't match, check value property rows
            # that reference the column via #Aggregate
            new_row = list(row)
            for i, cell in enumerate(row):
                if '{Number}' in cell and any(fc.lower() in key.lower() for fc in failing_cols if fc):
                    new_row[i] = cell.replace('{Number}', '{Data}')
                    changed = True
            new_rows.append(new_row)

    if changed:
        return _rows_to_csv(new_rows)
    return pvmap_csv


# ---------------------------------------------------------------------------
# Rule registry and orchestrator
# ---------------------------------------------------------------------------

def _build_rules() -> List[CorrectionRule]:
    """Construct the ordered list of correction rules."""
    return [
        CorrectionRule(
            name='fix_key_mismatch',
            error_type='error-pvmap-dropped-undefined-property',
            priority=0,
            condition=_condition_key_mismatch,
            apply=_apply_key_mismatch,
        ),
        CorrectionRule(
            name='fix_place_leading_zeros',
            error_type='error-unresolved-place',
            priority=1,
            condition=_condition_place_leading_zeros,
            apply=_apply_place_leading_zeros,
        ),
        CorrectionRule(
            name='fix_place_prefix',
            error_type='error-unresolved-place',
            priority=2,
            condition=_condition_place_prefix,
            apply=_apply_place_prefix,
        ),
        CorrectionRule(
            name='fix_duplicate_observations',
            error_type='error-mismatched-svobs',
            priority=3,
            condition=_condition_duplicate_observations,
            apply=_apply_duplicate_observations,
        ),
        CorrectionRule(
            name='fix_missing_required_props',
            error_type='error-svobs-missing-property',
            priority=4,
            condition=_condition_missing_required_props,
            apply=_apply_missing_required_props,
        ),
        CorrectionRule(
            name='fix_aggregate_invalid',
            error_type='error-aggregate-invalid-values',
            priority=5,
            condition=_condition_aggregate_invalid,
            apply=_apply_aggregate_invalid,
        ),
    ]


def apply_correction_rules(
    pvmap_csv: str,
    filtered_logs: FilteredLogs,
    key_match_report: str,
    input_data_path: Optional[Path] = None,
) -> Tuple[str, List[str]]:
    """Apply all matching correction rules in priority order.

    Args:
        pvmap_csv: The PVMAP CSV string to correct.
        filtered_logs: Enriched validation summary from log_filter.
        key_match_report: Key matching report text from pvmap_repair.
        input_data_path: Optional path to the input CSV for header lookup.

    Returns:
        Tuple of (corrected_pvmap_csv, list_of_change_descriptions).
    """
    rules = _build_rules()
    rules.sort(key=lambda r: r.priority)

    ctx: dict = {
        'key_match_report': key_match_report,
        'input_data_path': input_data_path,
    }

    changes: List[str] = []
    current_csv = pvmap_csv

    for rule in rules:
        try:
            if not rule.condition(filtered_logs, ctx):
                continue

            new_csv = rule.apply(current_csv, filtered_logs, ctx)

            # Special case: diagnostic-only rules (duplicate observations)
            if rule.name == 'fix_duplicate_observations':
                diag = _diagnostic_duplicate_observations(filtered_logs)
                changes.append(f"[{rule.name}] {diag}")
                continue

            if new_csv != current_csv:
                current_csv = new_csv
                changes.append(
                    f"[{rule.name}] Applied correction for {rule.error_type}"
                )
                logger.info("Correction rule '%s' applied", rule.name)
            else:
                logger.debug("Correction rule '%s' matched but made no changes", rule.name)

        except Exception as e:
            logger.warning("Correction rule '%s' failed: %s", rule.name, e)
            changes.append(f"[{rule.name}] FAILED: {e}")

    return current_csv, changes
