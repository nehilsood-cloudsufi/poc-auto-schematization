"""Generate stat_var_processor config from PVMAP content + data analysis.

Pure functions for deterministic config generation. No ADK dependency.

The stat_var_processor expects a config/metadata CSV (--config_file) with
processing parameters. This module auto-generates that config from:
- PVMAP CSV content (output_columns, mapped_columns)
- Data context from sampling (header_rows)
- Input CSV headers (mapped_columns confidence)
- Optional LLM enrichment (mapped_columns override)

Config CSV format: 2-column (parameter,value) matching file_util.file_load_py_dict().
"""

import csv
import io
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Required output columns — always included regardless of PVMAP content.
# 100% presence across 51 ground truth metadata files.
REQUIRED_OUTPUT_COLUMNS = [
    "observationAbout",
    "observationDate",
    "variableMeasured",
    "value",
]

# Optional output columns — included only when the PVMAP uses them.
OPTIONAL_OUTPUT_COLUMNS = [
    "unit",
    "scalingFactor",
    "measurementMethod",
    "observationPeriod",
]

# Combined set for validation (replaces old VALID_SVOBS_PROPERTIES).
VALID_SVOBS_PROPERTIES = set(REQUIRED_OUTPUT_COLUMNS + OPTIONAL_OUTPUT_COLUMNS)

# Full canonical ordering for output_columns.
_OUTPUT_COLUMNS_ORDER = REQUIRED_OUTPUT_COLUMNS + OPTIONAL_OUTPUT_COLUMNS


def extract_output_columns(pvmap_csv_content: str) -> str:
    """Extract output columns from PVMAP, guaranteeing required columns.

    Always includes the 4 required StatVarObs columns. Adds optional columns
    (unit, scalingFactor, measurementMethod, observationPeriod) only when
    they appear as property names in the PVMAP.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.

    Returns:
        Comma-separated string of output columns in canonical order.
    """
    found_optional = set()
    if pvmap_csv_content and pvmap_csv_content.strip():
        reader = csv.reader(io.StringIO(pvmap_csv_content))
        for row in reader:
            if not row:
                continue
            if row[0].strip().lower() == "key":
                continue
            # Odd-indexed columns are property names
            for i in range(1, len(row), 2):
                prop = row[i].strip()
                if prop in OPTIONAL_OUTPUT_COLUMNS:
                    found_optional.add(prop)

    # Build: required (always) + optional (only if found), in canonical order
    result = list(REQUIRED_OUTPUT_COLUMNS)
    for col in OPTIONAL_OUTPUT_COLUMNS:
        if col in found_optional:
            result.append(col)

    return ",".join(result)


def compute_mapped_rows(header_rows: int) -> int:
    """Compute mapped_rows for stat_var_processor config.

    In the processor, mapped_rows controls which input rows get row-based
    PV lookups. Ground truth analysis confirms mapped_rows == header_rows
    in all datasets where both are set.

    Args:
        header_rows: Number of header rows in the input CSV.

    Returns:
        mapped_rows value (minimum 1).
    """
    return max(1, header_rows)


def count_mapped_rows(pvmap_csv_content: str) -> int:
    """Count data rows in PVMAP (exclude header row starting with 'key').

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.

    Returns:
        Number of data rows.
    """
    count = 0
    reader = csv.reader(io.StringIO(pvmap_csv_content))
    for row in reader:
        if not row:
            continue
        if row[0].strip().lower() == "key":
            continue
        count += 1
    return count


def count_mapped_columns(pvmap_csv_content: str) -> int:
    """Max property-value pairs in any single PVMAP row.

    Each pair = 2 CSV columns (property, value). The first column is the key.
    So mapped_columns = (max_row_length - 1) // 2.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.

    Returns:
        Maximum number of property-value pairs across all rows.
    """
    max_pairs = 0
    reader = csv.reader(io.StringIO(pvmap_csv_content))
    for row in reader:
        if not row:
            continue
        if row[0].strip().lower() == "key":
            continue
        # Number of property-value pairs
        pairs = (len(row) - 1) // 2
        max_pairs = max(max_pairs, pairs)
    return max_pairs


def compute_mapped_columns(
    pvmap_csv_content: str,
    input_headers: List[str],
) -> tuple:
    """Compute mapped_columns by classifying input columns as dimension vs value.

    Parses PVMAP keys to find COLUMN:VALUE patterns (e.g., "agecat:0"),
    then identifies which input columns are dimension columns (their cell
    values are PVMAP keys) vs value columns (their header is a PVMAP key).

    In stat_var_processor, mapped_columns controls which input columns get
    cell-value PV lookups. It should be the 1-based position of the rightmost
    dimension column.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.
        input_headers: List of column names from the input CSV.

    Returns:
        Tuple of (mapped_columns: int, confidence: str).
        confidence is "high" or "low".
    """
    if not pvmap_csv_content or not pvmap_csv_content.strip() or not input_headers:
        return (0, "low")

    # Build case-insensitive header lookup
    header_lower = {h.strip().lower() for h in input_headers}

    # Step 1: Parse PVMAP keys — classify as direct or column:value
    direct_keys = set()
    column_value_columns = set()  # Column names from COLUMN:VALUE patterns

    reader = csv.reader(io.StringIO(pvmap_csv_content))
    for row in reader:
        if not row:
            continue
        key = row[0].strip()
        if not key or key.lower() == "key":
            continue

        # Check for COLUMN:VALUE pattern
        if ":" in key:
            col_part = key.split(":")[0].strip()
            # It's COLUMN:VALUE if the column part matches an input header
            # (but the full key does NOT match a header — distinguishes from
            # "REF_AREA:Reference area" which is a full header name)
            if col_part.lower() in header_lower and key.lower() not in header_lower:
                column_value_columns.add(col_part.lower())
                continue

        direct_keys.add(key)

    # Step 2: Find dimension column positions (1-based)
    dimension_positions = []
    for i, h in enumerate(input_headers):
        if h.strip().lower() in column_value_columns:
            dimension_positions.append(i + 1)  # 1-based

    if not dimension_positions:
        return (0, "low")

    dimension_positions.sort()
    rightmost = max(dimension_positions)

    # Step 3: Confidence scoring
    # HIGH: at least 1 column:value key found AND dimension columns form
    #        a reasonable block (not scattered across the entire width)
    is_contiguous = True
    if len(dimension_positions) > 1:
        # Check gap ratio: are dimensions clustered together?
        span = max(dimension_positions) - min(dimension_positions) + 1
        if span > len(dimension_positions) * 3:
            is_contiguous = False

    confidence = "high" if is_contiguous and len(column_value_columns) > 0 else "low"

    return (rightmost, confidence)


def detect_multi_value_properties(pvmap_csv_content: str) -> List[str]:
    """Detect properties appearing in rows for multiple different keys.

    A multi-value property is one where the same property name appears
    in PVMAP rows for different key values.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.

    Returns:
        List of property names that are multi-value.
    """
    # Map: property -> set of keys that use it
    prop_keys: Dict[str, set] = defaultdict(set)
    reader = csv.reader(io.StringIO(pvmap_csv_content))

    for row in reader:
        if not row:
            continue
        if row[0].strip().lower() == "key":
            continue
        key = row[0].strip()
        for i in range(1, len(row), 2):
            prop = row[i].strip()
            if prop:
                prop_keys[prop].add(key)

    # Default multi-value properties from config_flags.py
    defaults = {"name", "alternateName", "measurementDenominator"}

    multi = []
    for prop, keys in prop_keys.items():
        if len(keys) > 1 and prop not in defaults:
            multi.append(prop)

    return sorted(multi)


def detect_header_rows(
    input_file: Optional[str] = None,
    data_context: Optional[dict] = None,
    pvmap_csv_content: Optional[str] = None,
) -> int:
    """Detect number of header rows.

    Uses data_context first if available, then scans input file using both
    text-scan and PVMAP cross-reference (taking the maximum of the two).
    Default: 1.

    Args:
        input_file: Path to input CSV file.
        data_context: Data context dict from sampling agent.
        pvmap_csv_content: Optional PVMAP CSV text for cross-reference.

    Returns:
        Number of header rows (minimum 1).
    """
    # 1. Check data_context (trusted source — use directly)
    if data_context:
        hr = data_context.get("header_rows")
        if hr is not None:
            try:
                return max(1, int(hr))
            except (ValueError, TypeError):
                pass

    # 2. Scan input file first 10 rows
    if input_file and Path(input_file).exists():
        try:
            with open(input_file, "r", encoding="utf-8", errors="replace") as f:
                reader = csv.reader(f)
                rows = []
                for i, row in enumerate(reader):
                    if i >= 10:
                        break
                    rows.append(row)

            if len(rows) >= 2:
                # text_scan: count leading text-only rows (minimum 1 if any found)
                text_scan = 0
                for row in rows:
                    if _is_text_row(row):
                        text_scan += 1
                    else:
                        break
                text_scan = max(1, text_scan) if text_scan > 0 else 1

                # pvmap_cross_ref: check input rows against PVMAP keys
                pvmap_cross_ref = _pvmap_cross_ref_headers(rows, pvmap_csv_content)

                return max(text_scan, pvmap_cross_ref)
        except Exception:
            pass

    return 1


def _pvmap_cross_ref_headers(
    input_rows: List[list],
    pvmap_csv_content: Optional[str],
) -> int:
    """Cross-reference input rows against PVMAP keys to count header rows.

    For each of the first 5 input rows, checks if any cells match PVMAP keys
    (case-insensitive). Stops counting at the first non-matching row.

    Args:
        input_rows: List of CSV rows (each row is a list of strings).
        pvmap_csv_content: Raw PVMAP CSV text, or None.

    Returns:
        Number of header rows detected (0 if no PVMAP or no matches found,
        otherwise max(1, matched_count)).
    """
    if not pvmap_csv_content or not pvmap_csv_content.strip():
        return 0

    # Collect all PVMAP keys (lowercased)
    pvmap_keys: set = set()
    try:
        reader = csv.reader(io.StringIO(pvmap_csv_content))
        for row in reader:
            if not row:
                continue
            key = row[0].strip()
            if not key or key.lower() == "key":
                continue
            pvmap_keys.add(key.lower())
    except Exception:
        return 0

    if not pvmap_keys:
        return 0

    # Check each of the first 5 rows — stop at first non-matching row
    header_count = 0
    for row in input_rows[:5]:
        row_cells = {cell.strip().lower() for cell in row if cell.strip()}
        if row_cells & pvmap_keys:
            header_count += 1
        else:
            break

    return max(1, header_count) if header_count > 0 else 0


def _is_text_row(row: list) -> bool:
    """Check if a CSV row is all text (no numeric values).

    A row is considered text if all non-empty cells are non-numeric.
    """
    for cell in row:
        cell = cell.strip()
        if not cell:
            continue
        # Try to parse as number
        try:
            float(cell.replace(",", ""))
            return False
        except ValueError:
            continue
    return True


def merge_with_existing(
    auto_params: dict, existing_path: Optional[str]
) -> dict:
    """Merge auto-generated params under user/GT metadata. User values win.

    Args:
        auto_params: Auto-generated config parameters.
        existing_path: Path to existing metadata CSV (2-column format).

    Returns:
        Merged parameters dict (existing values override auto).
    """
    if not existing_path or not Path(existing_path).exists():
        return dict(auto_params)

    # Read existing metadata
    existing = {}
    try:
        with open(existing_path, "r", encoding="utf-8") as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    param = row[0].strip()
                    value = row[1].strip()
                    if param and not param.startswith("#"):
                        existing[param] = value
    except Exception as e:
        logger.warning(f"Failed to read existing metadata {existing_path}: {e}")
        return dict(auto_params)

    # Merge: start with auto, then overwrite with existing
    merged = dict(auto_params)
    merged.update(existing)
    return merged


def write_config_csv(params: dict, output_path: str) -> str:
    """Write config as 2-column CSV (parameter,value).

    Args:
        params: Config parameter dict.
        output_path: File path to write.

    Returns:
        Path to written file.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        for param, value in params.items():
            writer.writerow([param, str(value)])

    return str(path)


def generate_processor_config(
    pvmap_csv_content: str,
    data_context: Optional[dict] = None,
    input_file: Optional[str] = None,
    input_headers: Optional[List[str]] = None,
    output_dir: Optional[str] = None,
    existing_metadata_path: Optional[str] = None,
    llm_enrichment: Optional[dict] = None,
) -> Dict[str, Any]:
    """Main entry: generates config dict and writes CSV.

    Computes P1 flags: output_columns, header_rows, mapped_rows, mapped_columns.
    Merges with optional LLM enrichment and existing metadata.
    Priority: existing_metadata > llm_enrichment > deterministic.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.
        data_context: Data context from sampling (optional).
        input_file: Path to input CSV for header detection (optional).
        input_headers: List of input column names (optional, read from input_file if absent).
        output_dir: Directory to write output_metadata.csv (optional).
        existing_metadata_path: Path to existing metadata CSV (optional).
        llm_enrichment: Dict of LLM-suggested params (optional).

    Returns:
        Dict with keys: success, config_path, parameters, mapped_columns_confidence, error.
    """
    if not pvmap_csv_content or not pvmap_csv_content.strip():
        return {
            "success": False,
            "config_path": None,
            "parameters": {},
            "mapped_columns_confidence": None,
            "error": "Empty PVMAP content",
        }

    try:
        auto_params: Dict[str, Any] = {}

        # 1. output_columns — required 4 always + optional from PVMAP
        auto_params["output_columns"] = extract_output_columns(pvmap_csv_content)

        # 2. header_rows — text scan + PVMAP cross-reference
        header_rows = detect_header_rows(input_file, data_context, pvmap_csv_content)
        auto_params["header_rows"] = header_rows

        # 3. mapped_rows — equals header_rows
        auto_params["mapped_rows"] = compute_mapped_rows(header_rows)

        # 4. mapped_columns — PVMAP key analysis + confidence
        if not input_headers and input_file and Path(input_file).exists():
            try:
                with open(input_file, "r", encoding="utf-8", errors="replace") as f:
                    reader = csv.reader(f)
                    input_headers = next(reader, [])
            except Exception:
                input_headers = []

        mapped_cols, confidence = compute_mapped_columns(
            pvmap_csv_content, input_headers or []
        )
        auto_params["mapped_columns"] = mapped_cols

        # Merge LLM enrichment (only mapped_columns override now)
        if llm_enrichment and isinstance(llm_enrichment, dict):
            if "mapped_columns" in llm_enrichment:
                auto_params["mapped_columns"] = llm_enrichment["mapped_columns"]

        # Merge with existing metadata (existing wins)
        final_params = merge_with_existing(auto_params, existing_metadata_path)

        # Write to file
        config_path = None
        if output_dir:
            config_path = write_config_csv(
                final_params, str(Path(output_dir) / "output_metadata.csv")
            )

        return {
            "success": True,
            "config_path": config_path,
            "parameters": final_params,
            "mapped_columns_confidence": confidence,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Failed to generate processor config: {e}")
        return {
            "success": False,
            "config_path": None,
            "parameters": {},
            "mapped_columns_confidence": None,
            "error": str(e),
        }
