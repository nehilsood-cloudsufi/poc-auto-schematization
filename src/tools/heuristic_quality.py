"""
Heuristic quality scoring for PVMAP evaluation without ground truth.

This module calculates a quality score (0-100) based on structural
analysis when no ground truth PVMAP is available.

Scoring Components (100 points total):
- Row coverage: 25 points (PVMAP rows vs expected based on data)
- Required property coverage: 25 points (observationAbout, observationDate, value)
- Column mapping completeness: 25 points (data columns mapped in PVMAP)
- Value format correctness: 25 points ({Data}, {Number}, dcid: prefixes)
"""

import csv
import io
import re
from typing import Dict, Any, List, Set, Tuple


def calculate_heuristic_score(
    pvmap_csv: str,
    sampled_data: str,
    metadata: str = ""
) -> Dict[str, Any]:
    """
    Calculate quality score without ground truth.

    Args:
        pvmap_csv: Generated PVMAP CSV content
        sampled_data: Sampled input data CSV content
        metadata: Optional metadata CSV content

    Returns:
        Dictionary with:
            - total: float (0-100 overall score)
            - row_coverage: float (0-25)
            - prop_coverage: float (0-25)
            - column_coverage: float (0-25)
            - format_score: float (0-25)
            - issues: str (newline-separated list of issues found)
            - details: dict with breakdown info
    """
    issues = []
    details = {}

    # 1. Row count check (max 25 points)
    expected_rows = _estimate_expected_rows(sampled_data, metadata)
    actual_rows = _count_pvmap_rows(pvmap_csv)
    details["expected_rows"] = expected_rows
    details["actual_rows"] = actual_rows

    if expected_rows > 0:
        row_ratio = min(actual_rows / expected_rows, 1.5)  # Cap at 150%
        if row_ratio > 1.0:
            row_ratio = 1.0 - (row_ratio - 1.0) * 0.5  # Penalize over-generation slightly
        row_coverage = max(0, row_ratio * 25)
    else:
        row_coverage = 12.5 if actual_rows > 0 else 0  # Default if can't estimate

    if row_coverage < 15:
        issues.append(f"Low row coverage: {actual_rows}/{expected_rows} rows")
    details["row_coverage_ratio"] = actual_rows / max(expected_rows, 1)

    # 2. Required property coverage (max 25 points)
    required_props = ['observationAbout', 'observationDate', 'value']
    props_found = _count_properties_in_pvmap(pvmap_csv, required_props)
    details["required_props_found"] = props_found

    prop_coverage = (len(props_found) / len(required_props)) * 25
    missing_props = set(required_props) - props_found
    if missing_props:
        issues.append(f"Missing required properties: {list(missing_props)}")
    details["missing_required_props"] = list(missing_props)

    # 3. Column mapping completeness (max 25 points)
    data_columns = _get_columns_from_csv(sampled_data)
    mapped_keys = _get_keys_from_pvmap(pvmap_csv)
    details["data_columns"] = list(data_columns)
    details["mapped_keys"] = list(mapped_keys)

    # Calculate overlap (case-insensitive matching)
    data_columns_lower = {c.lower().strip() for c in data_columns}
    mapped_keys_lower = {k.lower().strip() for k in mapped_keys}

    # Also consider Column:Value syntax - extract column part
    for key in list(mapped_keys):
        if ':' in key:
            col_part = key.split(':')[0].lower().strip()
            mapped_keys_lower.add(col_part)

    matched_columns = data_columns_lower & mapped_keys_lower
    column_coverage = len(matched_columns) / max(len(data_columns), 1) * 25
    unmapped = data_columns - {c for c in data_columns if c.lower().strip() in mapped_keys_lower}

    if unmapped and len(unmapped) <= 5:
        issues.append(f"Unmapped columns: {list(unmapped)}")
    elif unmapped:
        issues.append(f"Unmapped columns: {list(unmapped)[:5]} (and {len(unmapped) - 5} more)")
    details["unmapped_columns"] = list(unmapped)
    details["column_match_count"] = len(matched_columns)

    # 4. Value format correctness (max 25 points)
    format_score, format_issues = _check_value_formats(pvmap_csv)
    if format_issues:
        issues.extend(format_issues[:3])  # Limit to top 3 format issues
    details["format_issues"] = format_issues

    # Calculate total
    total = row_coverage + prop_coverage + column_coverage + format_score

    return {
        "total": round(total, 1),
        "row_coverage": round(row_coverage, 1),
        "prop_coverage": round(prop_coverage, 1),
        "column_coverage": round(column_coverage, 1),
        "format_score": round(format_score, 1),
        "issues": "\n".join(issues) if issues else "",
        "details": details
    }


def _estimate_expected_rows(sampled_data: str, metadata: str = "") -> int:
    """
    Estimate expected PVMAP rows based on data structure.

    Expected rows = data columns + unique categorical values that need mapping.
    """
    columns = _get_columns_from_csv(sampled_data)

    # Base expectation: at least one row per column that might need mapping
    # Typically: date col, place col, value cols, dimension cols
    expected = len(columns)

    # Check for pre-formatted data (fewer rows needed)
    data_lower = sampled_data.lower()
    if 'variablemeasured' in data_lower and 'observationabout' in data_lower:
        # Pre-formatted data typically needs only 4-5 passthrough mappings
        expected = 5

    # Check metadata for hints
    if metadata:
        # If metadata suggests complex dimension structure, expect more rows
        metadata_lower = metadata.lower()
        if 'dimension' in metadata_lower or 'category' in metadata_lower:
            expected = max(expected, 15)

    # Cap at reasonable maximum
    return min(max(expected, 3), 100)


def _count_pvmap_rows(pvmap_csv: str) -> int:
    """Count data rows in PVMAP (excluding header)."""
    if not pvmap_csv or not pvmap_csv.strip():
        return 0

    try:
        reader = csv.reader(io.StringIO(pvmap_csv))
        rows = list(reader)
        # Subtract header row if present
        if rows and rows[0] and rows[0][0].lower() == 'key':
            return len(rows) - 1
        return len(rows)
    except Exception:
        # Fallback: count non-empty lines
        lines = [l for l in pvmap_csv.strip().split('\n') if l.strip()]
        return max(0, len(lines) - 1)  # Assume first line is header


def _count_properties_in_pvmap(pvmap_csv: str, required_props: List[str]) -> Set[str]:
    """Find which required properties appear in PVMAP."""
    found = set()
    pvmap_lower = pvmap_csv.lower()

    for prop in required_props:
        if prop.lower() in pvmap_lower:
            found.add(prop)

    return found


def _get_columns_from_csv(csv_content: str) -> Set[str]:
    """Extract column headers from CSV data."""
    if not csv_content or not csv_content.strip():
        return set()

    try:
        reader = csv.reader(io.StringIO(csv_content))
        headers = next(reader, [])
        # Filter out empty headers
        return {h.strip() for h in headers if h and h.strip()}
    except Exception:
        # Fallback: try to parse first line manually
        first_line = csv_content.strip().split('\n')[0]
        return {h.strip() for h in first_line.split(',') if h.strip()}


def _get_keys_from_pvmap(pvmap_csv: str) -> Set[str]:
    """Extract all keys from PVMAP CSV."""
    if not pvmap_csv or not pvmap_csv.strip():
        return set()

    keys = set()
    try:
        reader = csv.reader(io.StringIO(pvmap_csv))
        rows = list(reader)

        # Find key column index (usually 0)
        key_col = 0
        if rows and rows[0]:
            for i, header in enumerate(rows[0]):
                if header.lower().strip() == 'key':
                    key_col = i
                    break

        # Extract keys from data rows
        for row in rows[1:]:  # Skip header
            if row and len(row) > key_col and row[key_col].strip():
                keys.add(row[key_col].strip())

    except Exception:
        # Fallback: regex for keys
        # Keys are typically the first value in each row
        lines = pvmap_csv.strip().split('\n')[1:]  # Skip header
        for line in lines:
            if line.strip():
                match = re.match(r'^"?([^",]+)"?,', line)
                if match:
                    keys.add(match.group(1).strip())

    return keys


def _check_value_formats(pvmap_csv: str) -> Tuple[float, List[str]]:
    """
    Check value format correctness.

    Validates:
    - {Data} and {Number} placeholders used correctly
    - dcid: prefixes present where expected
    - No malformed values

    Returns:
        Tuple of (score out of 25, list of issues)
    """
    issues = []
    score = 25.0  # Start with full score, deduct for issues

    if not pvmap_csv or not pvmap_csv.strip():
        return 0.0, ["Empty PVMAP"]

    # Check for placeholder usage
    has_data_placeholder = '{data}' in pvmap_csv.lower() or '[data]' in pvmap_csv.lower()
    has_number_placeholder = '{number}' in pvmap_csv.lower() or '[number]' in pvmap_csv.lower()

    # Pre-formatted check
    is_preformatted = 'variablemeasured' in pvmap_csv.lower()

    if not is_preformatted:
        # Raw data should have placeholders
        if not has_data_placeholder and not has_number_placeholder:
            issues.append("No {Data} or {Number} placeholders found")
            score -= 10

    # Check for dcid: usage
    dcid_pattern = r'\bdcid:[A-Za-z0-9_/]+\b'
    dcid_matches = re.findall(dcid_pattern, pvmap_csv)

    # Check for likely DC identifiers missing dcid: prefix
    bare_dcid_patterns = [
        r'\b(Person|Household|HousingUnit|Establishment)\b',
        r'\b(count|median|measuredValue|percentile)\b',
        r'\bgeoId/\d+\b',
        r'\bcountry/[A-Z]{3}\b',
    ]

    for pattern in bare_dcid_patterns:
        matches = re.findall(pattern, pvmap_csv)
        for match in matches:
            # Check if this match is already prefixed with dcid:
            if f'dcid:{match}' not in pvmap_csv and f'dcid: {match}' not in pvmap_csv:
                # Only flag if it's in a value position (not a key)
                if match not in _get_keys_from_pvmap(pvmap_csv):
                    issues.append(f"Missing dcid: prefix for '{match}'")
                    score -= 2

    # Check for required properties in proper format
    required_value_props = ['observationabout', 'observationdate', 'value']
    pvmap_lower = pvmap_csv.lower()
    for prop in required_value_props:
        if prop in pvmap_lower:
            # Good, property exists
            pass
        else:
            # Already counted in property coverage, but double-check
            pass

    # Check for malformed CSV
    try:
        reader = csv.reader(io.StringIO(pvmap_csv))
        rows = list(reader)
        # Check for inconsistent row lengths
        if len(rows) > 1:
            header_len = len(rows[0])
            for i, row in enumerate(rows[1:], 1):
                if len(row) != header_len:
                    # Allow some variance (padding is ok)
                    if len(row) > header_len + 2 or len(row) < header_len - 2:
                        issues.append(f"Row {i} has inconsistent length")
                        score -= 1
    except Exception as e:
        issues.append(f"CSV parsing error: {str(e)[:50]}")
        score -= 5

    return max(0, score), issues[:5]  # Cap at 5 issues


def is_quality_acceptable(score: float, threshold: float = 70.0) -> bool:
    """Check if heuristic score meets quality threshold."""
    return score >= threshold


def format_quality_report(result: Dict[str, Any]) -> str:
    """Format quality scoring result as a human-readable report."""
    lines = [
        f"Heuristic Quality Score: {result['total']}/100",
        "",
        "Score Breakdown:",
        f"  - Row Coverage: {result['row_coverage']}/25",
        f"  - Property Coverage: {result['prop_coverage']}/25",
        f"  - Column Coverage: {result['column_coverage']}/25",
        f"  - Format Score: {result['format_score']}/25",
    ]

    if result['issues']:
        lines.extend([
            "",
            "Issues Found:",
        ])
        for issue in result['issues'].split('\n'):
            if issue.strip():
                lines.append(f"  - {issue}")

    return '\n'.join(lines)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'calculate_heuristic_score',
    'is_quality_acceptable',
    'format_quality_report',
]
