"""Generate stat_var_processor config from PVMAP content + data analysis.

Pure functions for deterministic config generation. No ADK dependency.

The stat_var_processor expects a config/metadata CSV (--config_file) with
processing parameters. This module auto-generates that config from:
- PVMAP CSV content (output_columns, mapped_rows, mapped_columns)
- Data context from sampling (header_rows, number_decimal)
- Optional LLM enrichment (schemaless, description)

Config CSV format: 2-column (parameter,value) matching file_util.file_load_py_dict().
"""

import csv
import io
import logging
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# StatVarObs properties that belong in output CSV columns.
# Validated against config_flags.py:258-271 (default_svobs_pvs keys).
# Excludes typeOf and #Aggregate (internal).
VALID_SVOBS_PROPERTIES = {
    "observationAbout",
    "observationDate",
    "variableMeasured",
    "value",
    "unit",
    "scalingFactor",
    "measurementMethod",
    "observationPeriod",
    "measurementResult",
}

# Canonical ordering for output_columns (required first, then optional).
_OUTPUT_COLUMNS_ORDER = [
    "observationAbout",
    "observationDate",
    "variableMeasured",
    "value",
    "unit",
    "scalingFactor",
    "measurementMethod",
    "observationPeriod",
    "measurementResult",
]


def extract_output_columns(pvmap_csv_content: str) -> str:
    """Parse PVMAP CSV and collect StatVarObs properties from odd-indexed columns.

    PVMAP rows have the format:
        key, property1, value1, property2, value2, ...
    Odd-indexed columns (1, 3, 5, ...) are property names.

    Only properties in VALID_SVOBS_PROPERTIES are included.
    Always includes the 4 required columns first, then optional ones.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.

    Returns:
        Comma-separated string of output columns, e.g.
        'observationAbout,observationDate,variableMeasured,value,unit'
    """
    found_props = set()
    reader = csv.reader(io.StringIO(pvmap_csv_content))

    for row in reader:
        if not row:
            continue
        # Skip header row
        if row[0].strip().lower() == "key":
            continue
        # Odd-indexed columns are property names
        for i in range(1, len(row), 2):
            prop = row[i].strip()
            if prop in VALID_SVOBS_PROPERTIES:
                found_props.add(prop)

    # Build ordered list: canonical order, only those found
    ordered = [p for p in _OUTPUT_COLUMNS_ORDER if p in found_props]

    # If we found nothing, return the 4 required columns as default
    if not ordered:
        ordered = _OUTPUT_COLUMNS_ORDER[:4]

    return ",".join(ordered)


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
) -> int:
    """Detect number of header rows.

    Uses data_context first if available, then scans input file.
    Default: 1.

    Args:
        input_file: Path to input CSV file.
        data_context: Data context dict from sampling agent.

    Returns:
        Number of header rows (minimum 1).
    """
    # 1. Check data_context
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
                # Count leading text-only rows
                header_count = 0
                for row in rows:
                    if _is_text_row(row):
                        header_count += 1
                    else:
                        break
                if header_count > 0:
                    return header_count
        except Exception:
            pass

    return 1


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
    output_dir: Optional[str] = None,
    existing_metadata_path: Optional[str] = None,
    llm_enrichment: Optional[dict] = None,
) -> Dict[str, Any]:
    """Main entry: generates config dict and writes CSV.

    Merges deterministic params + optional LLM enrichment + existing metadata.
    Priority: existing_metadata > llm_enrichment > deterministic.

    Args:
        pvmap_csv_content: Raw PVMAP CSV text.
        data_context: Data context from sampling (optional).
        input_file: Path to input CSV for header detection (optional).
        output_dir: Directory to write auto_config.csv (optional).
        existing_metadata_path: Path to existing metadata CSV (optional).
        llm_enrichment: Dict of LLM-suggested params (optional).

    Returns:
        Dict with keys: success, config_path, parameters, error.
    """
    if not pvmap_csv_content or not pvmap_csv_content.strip():
        return {
            "success": False,
            "config_path": None,
            "parameters": {},
            "error": "Empty PVMAP content",
        }

    try:
        # Phase A: Deterministic params
        auto_params: Dict[str, Any] = {}

        output_columns = extract_output_columns(pvmap_csv_content)
        auto_params["output_columns"] = output_columns

        header_rows = detect_header_rows(input_file, data_context)
        auto_params["header_rows"] = header_rows

        mapped_rows = count_mapped_rows(pvmap_csv_content)
        auto_params["mapped_rows"] = mapped_rows

        mapped_columns = count_mapped_columns(pvmap_csv_content)
        auto_params["mapped_columns"] = mapped_columns

        # Detect multi-value properties
        multi_val = detect_multi_value_properties(pvmap_csv_content)
        if multi_val:
            # Combine with defaults
            defaults = ["name", "alternateName", "measurementDenominator"]
            combined = defaults + [p for p in multi_val if p not in defaults]
            auto_params["multi_value_properties"] = ",".join(combined)

        # Detect number format
        if data_context and data_context.get("number_decimal"):
            auto_params["number_decimal"] = data_context["number_decimal"]

        # Default processing params
        auto_params["drop_statvars_without_svobs"] = 1
        auto_params["generate_statvar_name"] = "True"

        # Phase B: Merge LLM enrichment (if provided)
        if llm_enrichment and isinstance(llm_enrichment, dict):
            for key in ["schemaless", "drop_statvars_without_svobs", "description"]:
                if key in llm_enrichment:
                    auto_params[key] = llm_enrichment[key]

        # Phase C: Merge with existing metadata (existing wins)
        final_params = merge_with_existing(auto_params, existing_metadata_path)

        # Write to file if output_dir specified
        config_path = None
        if output_dir:
            config_path = write_config_csv(
                final_params, str(Path(output_dir) / "auto_config.csv")
            )

        return {
            "success": True,
            "config_path": config_path,
            "parameters": final_params,
            "error": None,
        }

    except Exception as e:
        logger.error(f"Failed to generate processor config: {e}")
        return {
            "success": False,
            "config_path": None,
            "parameters": {},
            "error": str(e),
        }
