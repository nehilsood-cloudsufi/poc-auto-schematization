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


def _split_column_value(key: str, headers: List[str]) -> Tuple[str, str]:
    """Header-aware split of a PVMAP key into (column_part, value_suffix).

    For COLUMN:VALUE syntax, we need to determine where the column name
    ends and the value begins. SDMX-style headers contain colons
    (e.g. "REF_AREA:Reference area"), so naive first-colon split is wrong.

    Strategy: find the longest header that is a prefix of the key,
    then treat the remainder as the value suffix. Falls back to
    first-colon split if no header prefix matches.

    Args:
        key: The full PVMAP key string.
        headers: List of exact column header strings.

    Returns:
        Tuple of (column_part, value_suffix) where value_suffix
        includes the leading colon (e.g. ":M: Monthly") or is empty.
    """
    if ':' not in key:
        return key, ""

    # Check if any header is a prefix of this key (longest match first)
    best_match = ""
    for h in headers:
        if ':' in h and key.startswith(h) and len(h) > len(best_match):
            # Must be followed by ':' or end-of-string to be a valid prefix
            remainder = key[len(h):]
            if remainder == "" or remainder.startswith(':'):
                best_match = h

    if best_match:
        remainder = key[len(best_match):]
        return best_match, remainder  # remainder is "" or ":value..."

    # Also check case-insensitive prefix match
    key_lower = key.lower()
    for h in headers:
        if ':' in h:
            h_lower = h.lower()
            if key_lower.startswith(h_lower) and len(h) > len(best_match):
                remainder = key[len(h):]
                if remainder == "" or remainder.startswith(':'):
                    best_match = h

    if best_match:
        remainder = key[len(best_match):]
        return best_match, remainder

    # Fallback: naive first-colon split
    parts = key.split(':', 1)
    return parts[0], ':' + parts[1]


def _clean_hallucinated_key(
    key: str, headers: List[str], headers_set: set
) -> str:
    """Clean LLM key hallucinations before matching.

    Handles cases where the LLM duplicates description segments:
    - "REF_AREA:Reference area:Reference area" → "REF_AREA:Reference area"
    - "FREQ:Frequency:Frequency:M: Monthly" → "FREQ:Frequency:M: Monthly"

    Also handles header prefix matches with appended values:
    - "REF_AREA:Reference area:Reference area:AR: Argentina"
      → "REF_AREA:Reference area:AR: Argentina" (if COLUMN:VALUE)
      → "REF_AREA:Reference area" (if exact header match suffices)

    Args:
        key: The PVMAP key to clean.
        headers: List of exact column header strings.
        headers_set: Set of headers for O(1) lookup.

    Returns:
        Cleaned key string.
    """
    if ':' not in key:
        return key

    # If key already matches a header exactly, no cleaning needed
    if key in headers_set:
        return key

    # Strategy 1: Check if a header is a prefix of the key with a
    # duplicated description segment following it.
    # e.g. header="REF_AREA:Reference area", key="REF_AREA:Reference area:Reference area"
    for h in headers:
        if ':' not in h:
            continue
        if not key.startswith(h):
            continue
        remainder = key[len(h):]
        if not remainder:
            continue
        if not remainder.startswith(':'):
            continue

        # Get the description part of the header (after first colon)
        h_desc = h.split(':', 1)[1].strip()
        remainder_stripped = remainder[1:].strip()  # Remove leading ':'

        # Case A: remainder is exactly the description repeated
        # "REF_AREA:Reference area" + ":Reference area" → just header
        if remainder_stripped.lower() == h_desc.lower():
            return h

        # Case B: remainder starts with duplicated description + more content
        # "FREQ:Frequency:Frequency:M: Monthly" → "FREQ:Frequency:M: Monthly"
        if remainder_stripped.lower().startswith(h_desc.lower() + ':'):
            after_dup = remainder_stripped[len(h_desc):]  # ":M: Monthly"
            return h + after_dup

        # Case C: remainder starts with duplicated description (case-insensitive)
        if remainder_stripped.lower().startswith(h_desc.lower()):
            after_dup = remainder_stripped[len(h_desc):]
            if after_dup == '' or after_dup.startswith(':'):
                return h + after_dup

    # Strategy 2: Deduplicate consecutive identical segments
    # "A:B:B:C" → "A:B:C"
    segments = key.split(':')
    if len(segments) >= 3:
        deduped = [segments[0]]
        for seg in segments[1:]:
            if seg.strip().lower() != deduped[-1].strip().lower():
                deduped.append(seg)
        deduped_key = ':'.join(deduped)
        if deduped_key != key and deduped_key in headers_set:
            return deduped_key

    return key


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
    # Handle COLUMN:VALUE syntax - use header-aware split
    column_part, value_suffix = _split_column_value(key, headers)

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

    # 5. Fuzzy match (use appropriate cutoff based on key length)
    cutoff = 0.80 if len(column_part) > 15 else 0.85
    matches = difflib.get_close_matches(
        column_part, headers, n=1, cutoff=cutoff
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


def _strip_dcid_prefixes(line: str) -> Tuple[str, Optional[str]]:
    """Strip dcid: and dcs: prefixes from PVMAP value fields.

    The LLM often adds dcid: or dcs: prefixes to values (e.g., dcid:Person,
    dcs:Male), but stat_var_processor also adds these prefixes automatically,
    creating double-prefixed values like dcid:dcid:Person.

    Preserves dcid:{Data} and dcs:{Data} passthrough patterns.

    Args:
        line: A single PVMAP CSV line.

    Returns:
        Tuple of (cleaned_line, change_description_or_None).
    """
    try:
        reader = csv.reader(io.StringIO(line))
        row = next(reader, [])
    except Exception:
        return line, None

    if len(row) < 3:
        return line, None

    changed = False
    stripped_values = []

    for i, field in enumerate(row):
        # Value fields are at indices 2, 4, 6, ... (0=key, 1=prop1, 2=val1, ...)
        if i >= 2 and i % 2 == 0:
            stripped_field = field.strip()
            # Preserve passthrough patterns: dcid:{Data}, dcs:{Data}, dcid:{Number}
            if re.match(r'^(?:dcid|dcs):\{(?:Data|Number|Key)\}$', stripped_field, re.IGNORECASE):
                stripped_values.append(field)
                continue
            # Strip dcid: prefix
            if stripped_field.startswith('dcid:'):
                new_val = stripped_field[5:]  # len('dcid:') == 5
                stripped_values.append(new_val)
                changed = True
                continue
            # Strip dcs: prefix
            if stripped_field.startswith('dcs:'):
                new_val = stripped_field[4:]  # len('dcs:') == 4
                stripped_values.append(new_val)
                changed = True
                continue
        stripped_values.append(field)

    if not changed:
        return line, None

    output = io.StringIO()
    writer = csv.writer(output, lineterminator='')
    writer.writerow(stripped_values)
    new_line = output.getvalue()

    return new_line, f"Stripped dcid:/dcs: prefixes: '{line.strip()}' -> '{new_line.strip()}'"


def _resolve_ignore_conflicts(pvmap_csv: str, headers: List[str]) -> Tuple[str, List[str]]:
    """Remove #ignore rows that conflict with COLUMN:VALUE mappings.

    When the LLM maps a column as '#ignore,skip' AND generates COLUMN:VALUE
    dimension mappings for the same column, the #ignore drops all rows and
    the dimension mappings produce 0 output. This function detects the
    conflict and removes the #ignore line.

    Args:
        pvmap_csv: The PVMAP CSV string.
        headers: List of input column headers.

    Returns:
        Tuple of (resolved_csv, changes_list).
    """
    lines = pvmap_csv.splitlines()
    changes: List[str] = []

    # Pass 1: Collect ignored columns and COLUMN:VALUE columns
    ignored_columns: Dict[str, int] = {}  # column -> line index
    column_value_columns: set = set()

    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        try:
            reader = csv.reader(io.StringIO(stripped))
            row = next(reader, [])
        except Exception:
            continue
        if not row or len(row) < 2:
            continue

        key = row[0].strip()
        if key.lower() == 'key':
            continue

        # Detect #ignore rows: key maps to "#ignore" or values contain "skip"/"ignore"
        row_text = ','.join(row[1:]).lower()
        if '#ignore' in row_text or (len(row) >= 3 and row[1].strip().lower() == '#ignore'):
            # The key is the column being ignored
            col_part, _ = _split_column_value(key, headers)
            if not col_part.startswith('#'):
                ignored_columns[col_part] = i

        # Detect COLUMN:VALUE syntax
        if ':' in key:
            col_part, val_suffix = _split_column_value(key, headers)
            if val_suffix and not col_part.startswith('#'):
                column_value_columns.add(col_part)

    # Pass 2: Remove #ignore lines for columns that also have COLUMN:VALUE mappings
    conflicting = set(ignored_columns.keys()) & column_value_columns
    if not conflicting:
        return pvmap_csv, []

    lines_to_remove: set = set()
    for col in conflicting:
        line_idx = ignored_columns[col]
        lines_to_remove.add(line_idx)
        changes.append(
            f"Removed #ignore for column '{col}' (line {line_idx + 1}) — "
            f"conflicts with COLUMN:VALUE dimension mappings"
        )

    resolved_lines = [line for i, line in enumerate(lines) if i not in lines_to_remove]
    return '\n'.join(resolved_lines), changes


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

    headers_set = set(headers)
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

        # Strip dcid:/dcs: prefixes from value fields
        stripped_line, strip_change = _strip_dcid_prefixes(line)
        if strip_change:
            changes.append(f"Line {line_num}: {strip_change}")
            line = stripped_line
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

        # Step 1: Clean hallucinated key duplicates FIRST
        cleaned_key = _clean_hallucinated_key(key, headers, headers_set)
        if cleaned_key != key:
            changes.append(
                f"Line {line_num}: Cleaned hallucinated key: '{key}' -> '{cleaned_key}'"
            )
            key = cleaned_key

        # Handle COLUMN:VALUE syntax — header-aware split
        column_part, value_suffix = _split_column_value(key, headers)

        # Skip special syntax keys
        if column_part.startswith('#'):
            repaired_lines.append(line)
            continue

        # Step 2: Try to match and fix the column portion of the key
        matched = match_key_to_header(key, key_index, headers)
        if matched is not None:
            # Build the corrected key
            corrected_key = matched + value_suffix

            # Replace the key in the line
            row[0] = corrected_key
            output = io.StringIO()
            writer = csv.writer(output, lineterminator='')
            writer.writerow(row)
            new_line = output.getvalue()

            changes.append(
                f"Line {line_num}: Key fix: '{key}' -> '{corrected_key}'"
            )
            repaired_lines.append(new_line)
        elif cleaned_key != row[0].strip():
            # Key was cleaned but didn't need further header matching
            row[0] = key  # Use the cleaned key
            output = io.StringIO()
            writer = csv.writer(output, lineterminator='')
            writer.writerow(row)
            new_line = output.getvalue()
            repaired_lines.append(new_line)
        else:
            repaired_lines.append(line)

    repaired_csv = '\n'.join(repaired_lines)

    # Resolve #ignore conflicts with COLUMN:VALUE mappings
    repaired_csv, ignore_changes = _resolve_ignore_conflicts(repaired_csv, headers)
    changes.extend(ignore_changes)

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

        # Handle COLUMN:VALUE — header-aware split
        column_part, _value_suffix = _split_column_value(key, headers)

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

    logger.info(
        "Key match report: matched=%d, fixable=%d, unmatched=%d, unmapped=%d",
        len(matched_keys), len(fixable_keys), len(unmatched_keys), len(unmapped_headers),
    )

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
        col, _ = _split_column_value(k, headers)
        matched_column_parts.add(col)
    for orig, _ in fixable_keys:
        col, _ = _split_column_value(orig, headers)
        fixable_column_parts.add(col)
    for k in unmatched_keys:
        col, _ = _split_column_value(k, headers)
        unmatched_column_parts.add(col)

    total_unique = len(matched_column_parts | fixable_column_parts | unmatched_column_parts)
    matched_unique = len(matched_column_parts | fixable_column_parts)
    match_rate = matched_unique / total_unique * 100 if total_unique > 0 else 0
    lines.append(f"**Match rate:** {match_rate:.0f}% ({matched_unique}/{total_unique} unique columns)")

    return '\n'.join(lines)


def _validate_eval_syntax(pvmap_csv: str) -> List[str]:
    """Statically check all #Eval expressions in a PVMAP for common issues.

    Detects:
    - f-strings (f"..." or f'...')
    - Nested double quotes (2+ " after CSV parsing)
    - Lambda expressions
    - Import statements
    - Python syntax errors (via compile() with dummy values)

    Args:
        pvmap_csv: The PVMAP CSV string.

    Returns:
        List of warning strings (empty if all expressions are valid).
    """
    warnings: List[str] = []

    for line_num, line in enumerate(pvmap_csv.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith('#'):
            continue

        # Find #Eval in the line (case-insensitive)
        if '#eval' not in stripped.lower():
            continue

        # Parse the CSV line to extract fields
        try:
            reader = csv.reader(io.StringIO(stripped))
            row = next(reader, [])
        except Exception:
            continue

        if not row:
            continue

        # Find #Eval fields and their following expression
        for i, field in enumerate(row):
            if field.strip().lower() != '#eval':
                continue

            # The expression is the next field
            if i + 1 >= len(row):
                warnings.append(
                    f"EVAL WARNING (line {line_num}): #Eval has no expression following it"
                )
                continue

            expr = row[i + 1].strip()
            if not expr:
                warnings.append(
                    f"EVAL WARNING (line {line_num}): #Eval expression is empty"
                )
                continue

            # Check 1: f-strings
            if re.search(r'\bf["\']', expr):
                warnings.append(
                    f"EVAL WARNING (line {line_num}): f-string detected in #Eval expression "
                    f"— processor uses eval(), not exec(). Expression: {expr[:80]}"
                )

            # Check 2: Nested double quotes (2+ " in the expression after CSV parsing)
            if expr.count('"') >= 2:
                warnings.append(
                    f"EVAL WARNING (line {line_num}): Nested double quotes in #Eval expression "
                    f"— breaks CSV parsing. Use single quotes inside expressions. "
                    f"Expression: {expr[:80]}"
                )

            # Check 3: Lambda expressions
            if re.search(r'\blambda\b', expr):
                warnings.append(
                    f"EVAL WARNING (line {line_num}): lambda detected in #Eval expression "
                    f"— not supported by processor. Expression: {expr[:80]}"
                )

            # Check 4: Import statements
            if re.search(r'\bimport\b', expr):
                warnings.append(
                    f"EVAL WARNING (line {line_num}): import detected in #Eval expression "
                    f"— not supported by processor. Expression: {expr[:80]}"
                )

            # Check 5: compile() test with dummy values
            test_expr = expr
            # Replace quoted placeholders first ('{Data}' → 'dummy_data')
            # This prevents double-quoting when {Data} appears inside quotes
            for quoted_ph, dummy in [
                ("'{Data}'", "'dummy_data'"),
                ("'{Number}'", "'42'"),
                ("'{Variable}'", "'dummy_var'"),
                ("'{Year}'", "'2020'"),
                ("'{Month}'", "'01'"),
                ("'{Key}'", "'dummy_key'"),
                ("'{data}'", "'dummy_data'"),
                ("'{number}'", "'42'"),
            ]:
                test_expr = test_expr.replace(quoted_ph, dummy)
            # Then replace bare placeholders
            for placeholder, dummy in [
                ('{Data}', "'dummy_data'"),
                ('{Number}', '42'),
                ('{Variable}', "'dummy_var'"),
                ('{Year}', "'2020'"),
                ('{Month}', "'01'"),
                ('{Key}', "'dummy_key'"),
                ('{data}', "'dummy_data'"),
                ('{number}', '42'),
            ]:
                test_expr = test_expr.replace(placeholder, dummy)
            # Replace escaped [DATA]/[NUMBER] variants too
            for placeholder, dummy in [
                ('[DATA]', "'dummy_data'"),
                ('[NUMBER]', '42'),
                ('[Year]', "'2020'"),
            ]:
                test_expr = test_expr.replace(placeholder, dummy)

            try:
                compile(test_expr, '<pvmap_eval>', 'eval')
            except SyntaxError:
                # Try as exec (assignments like var=expr)
                try:
                    compile(test_expr, '<pvmap_eval>', 'exec')
                except SyntaxError as e:
                    warnings.append(
                        f"EVAL WARNING (line {line_num}): Syntax error in #Eval expression "
                        f"— {e.msg}. Expression: {expr[:80]}"
                    )

    return warnings


def pre_validate_pvmap(
    pvmap_csv: str,
    input_data_path: Path,
    property_vocabulary: Optional[Dict] = None,
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
        column_part, _ = _split_column_value(key, headers)
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
    # Threshold: 30% — low enough to avoid false-positive rejections on datasets
    # with many dimension columns, but catches clearly broken PVMAPs.
    total_unique_columns = len(matched_columns) + len(unmatched_columns)
    matched_count = len(matched_columns)
    if headers and total_unique_columns > 0:
        match_rate = matched_count / total_unique_columns
        if match_rate < 0.3:
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
    if headers:
        logger.info(
            "Pre-validation: %s (matched=%d/%d unique columns, threshold=30%%)",
            "PASS" if passes else "FAIL",
            len(matched_columns), len(matched_columns) + len(unmatched_columns),
        )

    # Schema.org property validation (informational warnings appended after pass/fail decision)
    try:
        from src.pipeline.validation.schemaorg_validator import validate_pvmap_properties
        _, schema_warnings = validate_pvmap_properties(pvmap_csv)
        if schema_warnings:
            errors.extend(schema_warnings)
    except Exception as e:
        logger.debug(f"Schema.org validation skipped: {e}")

    # #Eval syntax validation (informational warnings appended after pass/fail decision)
    try:
        eval_warnings = _validate_eval_syntax(pvmap_csv)
        if eval_warnings:
            errors.extend(eval_warnings)
    except Exception as e:
        logger.debug(f"Eval syntax validation skipped: {e}")

    # Enum value validation (informational warnings appended after pass/fail decision)
    if property_vocabulary:
        try:
            from src.pipeline.validation.schemaorg_validator import validate_pvmap_enum_values
            _, enum_warnings = validate_pvmap_enum_values(pvmap_csv, property_vocabulary)
            if enum_warnings:
                errors.extend(enum_warnings)
        except Exception as e:
            logger.debug(f"Enum validation skipped: {e}")

    return passes, errors


__all__ = [
    'load_input_headers',
    'build_key_index',
    'match_key_to_header',
    'repair_pvmap',
    'generate_key_match_report',
    'pre_validate_pvmap',
    '_split_column_value',
    '_clean_hallucinated_key',
    '_strip_dcid_prefixes',
    '_resolve_ignore_conflicts',
    '_validate_eval_syntax',
]
