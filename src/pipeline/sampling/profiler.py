"""Deterministic dataset profiler for programmatic sampling.

Provides statistical evidence about a dataset without any LLM calls.
The profiler outputs a DatasetProfile that is consumed by the
SemanticAnalyzer LLM agent for column classification decisions.

Design principle: The profiler provides EVIDENCE; the LLM makes DECISIONS.

7 Profiling Capabilities:
1. Column role evidence (cardinality, dtype, looks_like_place, looks_like_date)
2. Semantic type detection (ISO_2, FIPS_STATE, YYYY, YYYY-MM, etc.)
3. Numeric-but-categorical detection (numeric dtype + low cardinality)
4. Top values with frequency counts
5. Aggregate row detection (Total, All, Overall)
6. Functional dependency detection (A determines B)
7. Sentinel value detection (-1, -999, N/A, suppressed)
"""

import logging
import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    np = None
    PANDAS_AVAILABLE = False

# Reuse existing helper functions instead of reimplementing
from src.tools.sampling_tools import (
    _detect_dtype,
    _looks_like_place,
    _looks_like_date,
    _sanitize_for_json,
)

logger = logging.getLogger(__name__)


# --- Known sentinel values for numeric columns ---
SENTINEL_VALUES = {
    '-1', '-2', '-9', '-99', '-999', '-9999',
    '999', '999.99', '9999', '99999',
    '0', '.',  '..', '...', '*',
    'n/a', 'na', 'nan', 'null', 'none',
    'suppressed', 'withheld', 'confidential',
    'x', 'z', 's', 'd', 'n',
}

# --- Aggregate/total keywords ---
AGGREGATE_KEYWORDS = [
    'total', 'all', 'overall', 'aggregate', 'combined',
    'national', 'entire', 'grand total',
]


@dataclass
class ColumnProfile:
    """Statistical profile of a single column."""

    name: str
    dtype: str                                    # Integer, Float, String, Date
    semantic_type: Optional[str] = None           # FIPS_STATE, ISO_2, YYYY, etc.
    cardinality: int = 0
    cardinality_ratio: float = 0.0                # unique / total
    null_pct: float = 0.0
    is_numeric_categorical: bool = False          # Numeric dtype but low cardinality
    looks_like_place: bool = False
    looks_like_date: bool = False
    top_values: List[Tuple[str, int]] = field(default_factory=list)   # (value, count)
    sample_values: List[str] = field(default_factory=list)            # 5 random unique
    aggregate_values: List[str] = field(default_factory=list)         # ["Total", "All"]
    sentinel_values: List[str] = field(default_factory=list)          # ["-1", "999.99"]


@dataclass
class DatasetProfile:
    """Complete statistical profile of a dataset."""

    file_path: str = ""
    file_size_kb: float = 0.0
    total_rows: int = 0
    total_columns: int = 0
    headers: List[str] = field(default_factory=list)
    columns: Dict[str, ColumnProfile] = field(default_factory=dict)
    functional_dependencies: List[Dict[str, Any]] = field(default_factory=list)
    aggregate_flags: Dict[str, List[str]] = field(default_factory=dict)
    is_preformatted_dc: bool = False
    sample_rows: List[Dict[str, Any]] = field(default_factory=list)   # First 15 rows
    metadata_rows: List[Dict[str, Any]] = field(default_factory=list)  # Unit/description rows (context, not data)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to JSON-serializable dictionary."""
        result = {
            "file_path": self.file_path,
            "file_size_kb": self.file_size_kb,
            "total_rows": self.total_rows,
            "total_columns": self.total_columns,
            "headers": self.headers,
            "columns": {},
            "functional_dependencies": self.functional_dependencies,
            "aggregate_flags": self.aggregate_flags,
            "is_preformatted_dc": self.is_preformatted_dc,
            "sample_rows": self.sample_rows,
            "metadata_rows": self.metadata_rows,
        }
        for name, col in self.columns.items():
            result["columns"][name] = {
                "name": col.name,
                "dtype": col.dtype,
                "semantic_type": col.semantic_type,
                "cardinality": col.cardinality,
                "cardinality_ratio": round(col.cardinality_ratio, 4),
                "null_pct": round(col.null_pct, 2),
                "is_numeric_categorical": col.is_numeric_categorical,
                "looks_like_place": col.looks_like_place,
                "looks_like_date": col.looks_like_date,
                "top_values": col.top_values,
                "sample_values": col.sample_values,
                "aggregate_values": col.aggregate_values,
                "sentinel_values": col.sentinel_values,
            }
        return _sanitize_for_json(result)


def profile_dataset(file_path: Path, sample_size: int = 500) -> DatasetProfile:
    """Profile a dataset for downstream LLM analysis.

    Runs in <2 seconds on typical datasets. No LLM calls.

    Args:
        file_path: Path to CSV file.
        sample_size: Max rows to read for analysis (default 500).

    Returns:
        DatasetProfile with complete statistical evidence.

    Raises:
        FileNotFoundError: If file_path does not exist.
        ImportError: If pandas is not available.
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas is required for profile_dataset")

    file_path = Path(file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    file_size_kb = file_path.stat().st_size / 1024

    # Read full file for accurate row count, but limit analysis rows
    df_full = pd.read_csv(
        file_path, encoding='utf-8', on_bad_lines='skip', low_memory=False
    )

    # Separate metadata rows (units, descriptions) from data rows
    df_clean, metadata_rows = _detect_metadata_rows(df_full)
    if metadata_rows:
        logger.info(
            "Detected %d metadata row(s) — preserving as context, profiling clean data",
            len(metadata_rows),
        )

    total_rows = len(df_clean)

    # Sample for analysis if too large
    if total_rows > sample_size:
        df = df_clean.sample(n=sample_size, random_state=42)
    else:
        df = df_clean

    headers = list(df_full.columns)
    n_analysis = len(df)

    # Build per-column profiles
    columns: Dict[str, ColumnProfile] = {}
    for col_name in headers:
        col_profile = _profile_column(df, col_name, n_analysis, total_rows)
        columns[col_name] = col_profile

    # Detect functional dependencies
    func_deps = _detect_functional_dependencies(df, columns)

    # Build aggregate flags from per-column aggregates
    aggregate_flags = {
        col_name: col.aggregate_values
        for col_name, col in columns.items()
        if col.aggregate_values
    }

    # Detect pre-formatted DC data
    is_preformatted = _detect_preformatted_dc(df)

    # Sample rows (first 15 from clean data, excluding metadata rows)
    sample_rows_list = _sanitize_for_json(
        df_clean.head(15).to_dict('records')
    )

    profile = DatasetProfile(
        file_path=str(file_path),
        file_size_kb=round(file_size_kb, 2),
        total_rows=total_rows,
        total_columns=len(headers),
        headers=headers,
        columns=columns,
        functional_dependencies=func_deps,
        aggregate_flags=aggregate_flags,
        is_preformatted_dc=is_preformatted,
        sample_rows=sample_rows_list,
        metadata_rows=_sanitize_for_json(metadata_rows),
    )

    logger.info(
        "Profiled %s: %d rows, %d cols, %d func_deps, preformatted=%s",
        file_path.name, total_rows, len(headers),
        len(func_deps), is_preformatted,
    )
    return profile


def _profile_column(
    df: 'pd.DataFrame', col_name: str, n_analysis: int, total_rows: int
) -> ColumnProfile:
    """Profile a single column."""
    series = df[col_name]
    values_str = series.dropna().astype(str).tolist()

    # Basic stats
    cardinality = series.nunique()
    cardinality_ratio = cardinality / total_rows if total_rows > 0 else 0
    null_count = series.isna().sum()
    null_pct = (null_count / n_analysis * 100) if n_analysis > 0 else 0

    # Dtype detection (reuse existing)
    dtype = _detect_dtype(values_str)

    # Place/date detection (reuse existing)
    unique_sample = list(set(values_str))[:20]
    looks_place = _looks_like_place(col_name, unique_sample)
    looks_date = _looks_like_date(col_name, unique_sample)

    # Semantic type detection
    semantic_type = _detect_semantic_type(col_name, unique_sample, dtype, looks_place, looks_date)

    # Numeric-but-categorical flag
    is_numeric_cat = (
        dtype in ("Integer", "Float")
        and cardinality_ratio < 0.05
        and cardinality > 1  # exclude constants
    )

    # Top values with counts (top 10)
    top_values = _get_top_values_with_counts(values_str, top_n=10)

    # Random sample values (5 unique)
    sample_vals = unique_sample[:5]

    # Aggregate detection
    agg_vals = _detect_aggregate_in_column(values_str)

    # Sentinel detection (only for value-like columns)
    sentinel_vals = []
    if dtype in ("Integer", "Float") and cardinality_ratio > 0.05:
        sentinel_vals = _detect_sentinels_in_column(values_str)

    return ColumnProfile(
        name=col_name,
        dtype=dtype,
        semantic_type=semantic_type,
        cardinality=cardinality,
        cardinality_ratio=cardinality_ratio,
        null_pct=null_pct,
        is_numeric_categorical=is_numeric_cat,
        looks_like_place=looks_place,
        looks_like_date=looks_date,
        top_values=top_values,
        sample_values=sample_vals,
        aggregate_values=agg_vals,
        sentinel_values=sentinel_vals,
    )


def _detect_semantic_type(
    col_name: str,
    sample_values: List[str],
    dtype: str,
    looks_place: bool,
    looks_date: bool,
) -> Optional[str]:
    """Detect semantic subtype for place/time columns.

    Reuses logic from DataContextGenerator._detect_geo_format().
    """
    col_lower = col_name.lower()

    # --- Place semantic types ---
    if looks_place:
        # FIPS patterns from column name
        if 'fips' in col_lower:
            if 'state' in col_lower:
                return 'FIPS_STATE'
            elif 'county' in col_lower:
                return 'FIPS_COUNTY'
            return 'FIPS'

        # Check value patterns
        if sample_values:
            first_val = str(sample_values[0]).strip()

            # ISO country codes
            if len(first_val) == 2 and first_val.isalpha() and first_val.isupper():
                return 'ISO_2'
            elif len(first_val) == 3 and first_val.isalpha() and first_val.isupper():
                return 'ISO_3'

            # Numeric codes
            if first_val.isdigit():
                if len(first_val) == 2:
                    return 'FIPS_STATE'
                elif len(first_val) == 5:
                    return 'FIPS_COUNTY'
                return 'NUMERIC_CODE'

            # DC format
            if first_val.startswith('geoId/') or first_val.startswith('country/'):
                return 'DC_DCID'

        return 'NAME'

    # --- Time semantic types ---
    if looks_date:
        if sample_values:
            for val in sample_values[:5]:
                val = str(val).strip()
                if re.match(r'^\d{4}$', val):
                    return 'YYYY'
                elif re.match(r'^\d{4}-\d{2}$', val):
                    return 'YYYY-MM'
                elif re.match(r'^\d{4}-\d{2}-\d{2}$', val):
                    return 'YYYY-MM-DD'
                elif re.match(r'^\d{4}Q\d$', val):
                    return 'YYYY-Q'
        return 'YYYY'  # default for date-like

    return None


def _get_top_values_with_counts(
    values: List[str], top_n: int = 10
) -> List[Tuple[str, int]]:
    """Return top-N (value, count) pairs by frequency."""
    if not values:
        return []
    counter = Counter(values)
    return counter.most_common(top_n)


def _detect_aggregate_in_column(values: List[str]) -> List[str]:
    """Detect aggregate/total values in a column's values.

    Reuses logic from DataContextGenerator._detect_aggregate_values().
    """
    found = []
    unique_vals = set(values)
    for val in unique_vals:
        val_lower = str(val).strip().lower()
        for kw in AGGREGATE_KEYWORDS:
            if val_lower == kw or val_lower.startswith(kw + ' ') or val_lower.endswith(' ' + kw):
                found.append(str(val).strip())
                break
    return sorted(found)


def _detect_sentinels_in_column(values: List[str]) -> List[str]:
    """Detect known sentinel values in a column."""
    found = set()
    for val in values:
        val_clean = str(val).strip().lower()
        if val_clean in SENTINEL_VALUES:
            found.add(str(val).strip())
            continue
        # Handle float representations like "-1.0" matching "-1"
        try:
            num = float(val_clean)
            if num == int(num):
                int_str = str(int(num))
                if int_str in SENTINEL_VALUES:
                    found.add(str(val).strip())
        except (ValueError, TypeError, OverflowError):
            pass
    return sorted(found)


def _detect_preformatted_dc(df: 'pd.DataFrame') -> bool:
    """Check if data is already in Data Commons format.

    Reuses logic from DataContextGenerator._detect_preformatted_dc().
    """
    col_set = set(c.lower().strip() for c in df.columns)
    required = {'variablemeasured', 'observationabout', 'value'}
    return required.issubset(col_set)


def _is_numeric_string(s: str) -> bool:
    """Check if a string represents a numeric value (int, float, or empty/NaN)."""
    s = s.strip()
    if not s or s.lower() in ('nan', 'na', '', '.', '..'):
        return True  # Missing values don't break numeric pattern
    try:
        float(s.replace(',', ''))
        return True
    except (ValueError, TypeError):
        return False


def _detect_metadata_rows(
    df: 'pd.DataFrame',
) -> Tuple['pd.DataFrame', List[Dict[str, Any]]]:
    """Separate metadata rows (units, descriptions) from data rows.

    A metadata row is one where >50% of the "mostly numeric" columns
    contain non-numeric values — indicating a unit descriptor, footnote,
    or description row rather than actual data.

    Returns:
        (clean_df, metadata_rows) — clean data for profiling + metadata as context dicts.
    """
    if len(df) < 3:
        return df, []  # Too few rows to detect anomalies reliably

    # Step 1: Identify "mostly numeric" columns (>80% of values parse as numbers)
    numeric_cols = []
    for col in df.columns:
        numeric_count = 0
        for val in df[col].astype(str):
            if _is_numeric_string(val):
                numeric_count += 1
        if numeric_count / len(df) >= 0.8:
            numeric_cols.append(col)

    if len(numeric_cols) < 2:
        return df, []  # Not enough numeric columns to detect anomalies

    # Step 2: For each row, check if it breaks the numeric pattern
    metadata_indices = []
    for idx in df.index:
        non_numeric = sum(
            1 for col in numeric_cols
            if not _is_numeric_string(str(df.at[idx, col]))
        )
        if non_numeric > len(numeric_cols) * 0.5:
            metadata_indices.append(idx)

    if not metadata_indices:
        return df, []

    metadata_rows = df.loc[metadata_indices].to_dict('records')
    clean_df = df.drop(index=metadata_indices).reset_index(drop=True)
    return clean_df, metadata_rows


def _detect_functional_dependencies(
    df: 'pd.DataFrame', columns: Dict[str, ColumnProfile]
) -> List[Dict[str, Any]]:
    """Detect functional dependencies between low-cardinality columns.

    A functional dependency A -> B means: for every unique value of A,
    there is exactly one unique value of B.

    Only tests column pairs where both have cardinality < 100 to avoid
    O(n^2) explosion on wide datasets.

    Returns:
        List of {source, target, strength} dicts.
    """
    # Find candidate columns (cardinality < 100)
    candidates = [
        name for name, col in columns.items()
        if col.cardinality < 100 and col.cardinality > 1
    ]

    # Limit to avoid excessive computation
    if len(candidates) > 20:
        # Sort by cardinality and take top 20
        candidates = sorted(candidates, key=lambda n: columns[n].cardinality)[:20]

    dependencies = []
    tested = set()

    for a in candidates:
        for b in candidates:
            if a == b:
                continue
            pair_key = (a, b)
            if pair_key in tested:
                continue
            tested.add(pair_key)

            try:
                # A -> B if groupby(A)[B].nunique().max() == 1
                max_b_per_a = df.groupby(a)[b].nunique().max()
                if max_b_per_a == 1:
                    dependencies.append({
                        "source": a,
                        "target": b,
                        "strength": 1.0,
                    })
            except Exception:
                continue

    return dependencies
