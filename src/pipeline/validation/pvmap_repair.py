"""PVMAP repair module for programmatic post-generation fixes.

Fixes common PVMAP issues AFTER LLM generation but BEFORE validation subprocess:
- Key mismatch (case, whitespace, character differences)
- {Data}/{Number} normalization (ADK escaping artifacts)
- Structural pre-validation (fast fail before 5-minute subprocess)

Usage:
    from src.pipeline.validation.pvmap_repair import repair_pvmap, pre_validate_pvmap

    pvmap_csv, changes = repair_pvmap(pvmap_csv_str, Path("input_data.csv"))
    ok, errors = pre_validate_pvmap(pvmap_csv_str, Path("input_data.csv"))
"""

import csv
import difflib
import io
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import logging

logger = logging.getLogger(__name__)


def load_input_headers(input_data_path: Path) -> List[str]:
    """Read first row of input CSV and return exact column headers.

    Args:
        input_data_path: Path to the input CSV file.

    Returns:
        List of column header strings, preserving exact case and whitespace.
    """
    try:
        with open(input_data_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f)
            headers = next(reader, [])
            # Strip whitespace and normalize embedded newlines (multi-line quoted headers)
            # e.g. "Violent\ncrime" → "Violent crime"
            return [re.sub(r'\s+', ' ', h).strip() for h in headers]
    except Exception as e:
        logger.warning(f"Failed to read headers from {input_data_path}: {e}")
        return []


def build_key_index(headers: List[str]) -> Dict[str, str]:
    """Build normalized-to-original header lookup dict.

    Creates multiple normalization levels for cascading match:
    - lowercase stripped
    - alphanumeric only (lowercase)

    Args:
        headers: List of exact column header strings.

    Returns:
        Dict mapping normalized form to original header string.
        If multiple headers normalize to the same key, first wins.
    """
    index: Dict[str, str] = {}
    for h in headers:
        # Level 1: lowercase stripped
        key_lower = h.strip().lower()
        if key_lower not in index:
            index[key_lower] = h

        # Level 2: alphanumeric only
        key_alnum = re.sub(r'[^a-z0-9]', '', key_lower)
        if key_alnum and key_alnum not in index:
            index[key_alnum] = h

        # Level 3: prefix before colon (for headers like "FREQ:Frequency")
        if ':' in h:
            prefix = h.split(':', 1)[0].strip().lower()
            if prefix and prefix not in index:
                index[prefix] = h
            prefix_alnum = re.sub(r'[^a-z0-9]', '', prefix)
            if prefix_alnum and prefix_alnum not in index:
                index[prefix_alnum] = h

    return index


def match_key_to_header(
    key: str,
    key_index: Dict[str, str],
    headers: List[str],
) -> Optional[str]:
    """Cascading match of a PVMAP key to an actual column header.

    Match order:
    1. Exact match
    2. Case-insensitive match
    3. Stripped whitespace match
    4. Alphanumeric-only match
    5. Fuzzy match (difflib, cutoff=0.85)

    For COLUMN:VALUE syntax, matches only the COLUMN portion.

    Args:
        key: The PVMAP key to match.
        key_index: Normalized-to-original lookup from build_key_index().
        headers: List of exact column headers.

    Returns:
        Matched header string, or None if no match found.
    """
    # Handle COLUMN:VALUE syntax - match only the COLUMN portion
    column_part = key
    value_suffix = ""
    if ':' in key:
        parts = key.split(':', 1)
        column_part = parts[0]
        value_suffix = ':' + parts[1]

    # Skip special keys that aren't column headers
    if column_part.startswith('#') or column_part.startswith('key'):
        return None

    # 1. Exact match
    if column_part in headers:
        return None  # Already correct, no fix needed

    # 2. Case-insensitive match
    key_lower = column_part.strip().lower()
    if key_lower in key_index:
        matched = key_index[key_lower]
        if matched != column_part:
            return matched

    # 3. Stripped whitespace (already handled by lower match above)

    # 4. Alphanumeric-only match
    key_alnum = re.sub(r'[^a-z0-9]', '', key_lower)
    if key_alnum and key_alnum in key_index:
        matched = key_index[key_alnum]
        if matched != column_part:
            return matched

    # 5. Fuzzy match
    matches = difflib.get_close_matches(
        column_part, headers, n=1, cutoff=0.85
    )
    if matches and matches[0] != column_part:
        return matches[0]

    return None


def _normalize_placeholders(line: str) -> str:
    """Normalize common ADK escaping artifacts in a PVMAP line.

    Fixes:
    - [DATA] -> {Data}
    - [NUMBER] -> {Number}
    - [Key] -> {Key}
    - Various case variants

    Args:
        line: A single line from the PVMAP CSV.

    Returns:
        Line with normalized placeholders.
    """
    # Pattern: [DATA] or [data] or [Data] -> {Data}
    line = re.sub(r'\[DATA\]', '{Data}', line, flags=re.IGNORECASE)
    # More specific: only replace standalone [Data] variants
    line = re.sub(r'\[Data\]', '{Data}', line)

    # Pattern: [NUMBER] or [number] or [Number] -> {Number}
    line = re.sub(r'\[NUMBER\]', '{Number}', line, flags=re.IGNORECASE)
    line = re.sub(r'\[Number\]', '{Number}', line)

    # Pattern: [KEY] or [key] or [Key] -> {Key}
    line = re.sub(r'\[KEY\]', '{Key}', line, flags=re.IGNORECASE)
    line = re.sub(r'\[Key\]', '{Key}', line)

    return line


def repair_pvmap(
    pvmap_csv: str,
    input_data_path: Path,
) -> Tuple[str, List[str]]:
    """Main repair function. Fixes common PVMAP issues programmatically.

    For each PVMAP row:
    - Fix key mismatches against actual headers
    - Trim whitespace from keys and values
    - Normalize placeholder syntax ([DATA] -> {Data}, etc.)

    Args:
        pvmap_csv: The raw PVMAP CSV string from LLM generation.
        input_data_path: Path to the input data CSV file.

    Returns:
        Tuple of (repaired_csv, changes_list) where changes_list
        describes each fix applied.
    """
    if not pvmap_csv or not pvmap_csv.strip():
        return pvmap_csv, []

    headers = load_input_headers(input_data_path)
    if not headers:
        return pvmap_csv, ["WARNING: Could not read input headers for repair"]

    key_index = build_key_index(headers)
    changes: List[str] = []
    repaired_lines: List[str] = []

    for line_num, line in enumerate(pvmap_csv.splitlines(), 1):
        original_line = line

        # Skip empty lines and comments
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            repaired_lines.append(line)
            continue

        # Normalize placeholders first
        line = _normalize_placeholders(line)
        if line != original_line:
            changes.append(
                f"Line {line_num}: Normalized placeholders: "
                f"'{original_line.strip()}' -> '{line.strip()}'"
            )
            original_line = line

        # Parse the line to extract the key (first field)
        try:
            reader = csv.reader(io.StringIO(line))
            row = next(reader, [])
        except Exception:
            repaired_lines.append(line)
            continue

        if not row:
            repaired_lines.append(line)
            continue

        key = row[0].strip()

        # Skip header row
        if key.lower() == 'key':
            repaired_lines.append(line)
            continue

        # Handle COLUMN:VALUE syntax
        column_part = key
        value_suffix = ""
        if ':' in key:
            parts = key.split(':', 1)
            column_part = parts[0]
            value_suffix = ':' + parts[1]

        # Skip special syntax keys
        if column_part.startswith('#'):
            repaired_lines.append(line)
            continue

        # Try to match and fix the key
        matched = match_key_to_header(key, key_index, headers)
        if matched is not None:
            # Build the corrected key
            corrected_key = matched + value_suffix

            # Replace the key in the line
            # We need to reconstruct the CSV line with the fixed key
            row[0] = corrected_key
            output = io.StringIO()
            writer = csv.writer(output, lineterminator='')
            writer.writerow(row)
            new_line = output.getvalue()

            changes.append(
                f"Line {line_num}: Key fix: '{key}' -> '{corrected_key}'"
            )
            repaired_lines.append(new_line)
        else:
            repaired_lines.append(line)

    repaired_csv = '\n'.join(repaired_lines)

    if changes:
        logger.info(f"PVMAP repair applied {len(changes)} fixes")
        for c in changes[:10]:
            logger.info(f"  {c}")

    return repaired_csv, changes


def generate_key_match_report(
    pvmap_csv: str,
    input_data_path: Path,
) -> str:
    """Generate diagnostic markdown report on key matching.

    Reports:
    - Matched keys (correct)
    - Auto-fixed keys (repaired)
    - Unmatched keys (potential issues)
    - Unmapped headers (missing from PVMAP)

    Args:
        pvmap_csv: The PVMAP CSV string.
        input_data_path: Path to the input data CSV file.

    Returns:
        Markdown-formatted diagnostic report.
    """
    if not pvmap_csv or not pvmap_csv.strip():
        return "No PVMAP content to analyze."

    headers = load_input_headers(input_data_path)
    if not headers:
        return "Could not read input headers for analysis."

    key_index = build_key_index(headers)
    headers_set = set(headers)

    matched_keys: List[str] = []
    fixable_keys: List[Tuple[str, str]] = []  # (original, corrected)
    unmatched_keys: List[str] = []
    special_keys: List[str] = []
    pvmap_column_keys: set = set()

    for line in pvmap_csv.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        try:
            reader = csv.reader(io.StringIO(stripped))
            row = next(reader, [])
        except Exception:
            continue

        if not row:
            continue

        key = row[0].strip()
        if key.lower() == 'key':
            continue

        # Handle COLUMN:VALUE
        column_part = key
        if ':' in key:
            column_part = key.split(':', 1)[0]

        # Special syntax
        if column_part.startswith('#'):
            special_keys.append(key)
            continue

        pvmap_column_keys.add(column_part)

        if column_part in headers_set:
            matched_keys.append(key)
        else:
            fix = match_key_to_header(key, key_index, headers)
            if fix is not None:
                fixable_keys.append((key, fix))
            else:
                unmatched_keys.append(key)

    # Find unmapped headers
    unmapped_headers = [h for h in headers if h not in pvmap_column_keys]

    # Build report
    lines = ["## KEY MATCH REPORT\n"]

    lines.append(f"**Input columns:** {len(headers)} | "
                 f"**PVMAP keys:** {len(matched_keys) + len(fixable_keys) + len(unmatched_keys)}\n")

    if matched_keys:
        lines.append(f"### Matched ({len(matched_keys)})")
        for k in matched_keys[:20]:
            lines.append(f"- `{k}`")
        if len(matched_keys) > 20:
            lines.append(f"- ... and {len(matched_keys) - 20} more")
        lines.append("")

    if fixable_keys:
        lines.append(f"### Auto-Fixed ({len(fixable_keys)})")
        for orig, fix in fixable_keys:
            lines.append(f"- `{orig}` -> `{fix}`")
        lines.append("")

    if unmatched_keys:
        lines.append(f"### UNMATCHED ({len(unmatched_keys)}) - these keys won't match any column!")
        for k in unmatched_keys:
            # Suggest closest match
            close = difflib.get_close_matches(k, headers, n=1, cutoff=0.6)
            suggestion = f" (did you mean `{close[0]}`?)" if close else ""
            lines.append(f"- `{k}`{suggestion}")
        lines.append("")

    if unmapped_headers:
        lines.append(f"### Unmapped Columns ({len(unmapped_headers)}) - not referenced in PVMAP")
        for h in unmapped_headers:
            lines.append(f"- `{h}`")
        lines.append("")

    if special_keys:
        lines.append(f"### Special Syntax Keys ({len(special_keys)})")
        for k in special_keys[:10]:
            lines.append(f"- `{k}`")
        lines.append("")

    # Summary — use unique column parts for accurate rate when COLUMN:VALUE keys exist
    # (e.g. Sex:Male, Sex:Female, Sex:Both all reference column "Sex" — count once)
    matched_column_parts = set()
    fixable_column_parts = set()
    unmatched_column_parts = set()
    for k in matched_keys:
        matched_column_parts.add(k.split(':', 1)[0] if ':' in k else k)
    for orig, _ in fixable_keys:
        fixable_column_parts.add(orig.split(':', 1)[0] if ':' in orig else orig)
    for k in unmatched_keys:
        unmatched_column_parts.add(k.split(':', 1)[0] if ':' in k else k)

    total_unique = len(matched_column_parts | fixable_column_parts | unmatched_column_parts)
    matched_unique = len(matched_column_parts | fixable_column_parts)
    match_rate = matched_unique / total_unique * 100 if total_unique > 0 else 0
    lines.append(f"**Match rate:** {match_rate:.0f}% ({matched_unique}/{total_unique} unique columns)")

    return '\n'.join(lines)


def pre_validate_pvmap(
    pvmap_csv: str,
    input_data_path: Path,
) -> Tuple[bool, List[str]]:
    """Fast structural pre-validation (milliseconds, not minutes).

    Checks:
    - Has at least 1 data row
    - Has observationAbout mapping
    - Has observationDate mapping
    - Has value or {Number} mapping
    - >=50% of keys match actual headers
    - No placeholder keys (p2, v2, FIXME)

    Args:
        pvmap_csv: The PVMAP CSV string.
        input_data_path: Path to the input data CSV file.

    Returns:
        Tuple of (passes, critical_errors). If passes is False,
        skip the 5-minute subprocess and feed errors back immediately.
    """
    errors: List[str] = []

    if not pvmap_csv or not pvmap_csv.strip():
        return False, ["PVMAP is empty - no content generated"]

    headers = load_input_headers(input_data_path)
    headers_set = set(headers)
    key_index = build_key_index(headers) if headers else {}

    # Parse PVMAP rows
    data_rows = []
    has_observation_about = False
    has_observation_date = False
    has_value_mapping = False
    placeholder_keys = []
    matched_columns: set = set()    # Unique column parts that match headers
    unmatched_columns: set = set()  # Unique column parts that DON'T match

    for line in pvmap_csv.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        try:
            reader = csv.reader(io.StringIO(stripped))
            row = next(reader, [])
        except Exception:
            continue

        if not row:
            continue

        key = row[0].strip()
        if key.lower() == 'key':
            continue

        data_rows.append(row)

        # Check for observationAbout
        row_text = ','.join(row).lower()
        if 'observationabout' in row_text:
            has_observation_about = True

        # Check for observationDate
        if 'observationdate' in row_text:
            has_observation_date = True

        # Check for value/{Number} mapping
        if '{number}' in row_text or 'value,{' in row_text:
            has_value_mapping = True

        # Check for placeholder keys
        placeholder_pattern = re.compile(
            r'^(p\d+|v\d+|dcid:v\d+|FIXME|TODO|placeholder|xxx)$',
            re.IGNORECASE
        )
        if placeholder_pattern.match(key):
            placeholder_keys.append(key)

        # Key matching against headers — use UNIQUE column parts to avoid
        # penalizing COLUMN:VALUE dimension keys (e.g. Sex:Male, Sex:Female
        # all reference the same column "Sex" and should count once)
        column_part = key.split(':', 1)[0] if ':' in key else key
        if not column_part.startswith('#') and column_part.lower() != 'key':
            if column_part in headers_set:
                matched_columns.add(column_part)
            elif match_key_to_header(key, key_index, headers) is not None:
                matched_columns.add(column_part)  # Fixable counts as matched
            else:
                unmatched_columns.add(column_part)

    # Check 1: Has data rows
    if not data_rows:
        errors.append("PVMAP has 0 data rows (only header or empty)")

    # Check 2: observationAbout
    if not has_observation_about:
        errors.append(
            "CRITICAL: No observationAbout mapping found. "
            "Every observation needs a place/entity. "
            "Map a place column (FIPS, country code, etc.) to observationAbout."
        )

    # Check 3: observationDate
    if not has_observation_date:
        errors.append(
            "CRITICAL: No observationDate mapping found. "
            "Map a date/year column to observationDate."
        )

    # Check 4: value mapping
    if not has_value_mapping:
        errors.append(
            "WARNING: No value/{Number} mapping found. "
            "At least one column should map to value,{Number}."
        )

    # Check 5: Key match rate (based on unique column parts, not total keys)
    # This prevents COLUMN:VALUE dimension keys (Sex:Male, Sex:Female, Sex:Both)
    # from inflating the denominator — they all reference the same column "Sex"
    total_unique_columns = len(matched_columns) + len(unmatched_columns)
    matched_count = len(matched_columns)
    if headers and total_unique_columns > 0:
        match_rate = matched_count / total_unique_columns
        if match_rate < 0.5:
            errors.append(
                f"LOW KEY MATCH RATE: Only {matched_count}/{total_unique_columns} "
                f"({match_rate:.0%}) PVMAP column keys match input column headers. "
                f"Unmatched: {', '.join(sorted(unmatched_columns)[:5])}. "
                f"Input columns: {', '.join(headers[:10])}"
            )

    # Check 6: Placeholder keys
    if placeholder_keys:
        errors.append(
            f"PLACEHOLDER KEYS FOUND: {', '.join(placeholder_keys)}. "
            "Use exact column headers or cell values as keys."
        )

    passes = len(errors) == 0
    return passes, errors


__all__ = [
    'load_input_headers',
    'build_key_index',
    'match_key_to_header',
    'repair_pvmap',
    'generate_key_match_report',
    'pre_validate_pvmap',
]
