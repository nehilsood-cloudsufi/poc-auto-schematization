# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Sampling tools for the agentic Data Sampling Agent.

This module provides 5 tools that wrap existing sampling logic, enabling
an LLM agent to make sampling decisions based on data evidence.

Tools:
1. preview_data - Preview first N rows of a CSV file
2. analyze_columns - Analyze columns for evidence-based classification
3. sample_rows - Execute sampling with LLM-designed strategy
4. check_coverage - Validate dimension uniqueness hypothesis
5. generate_context - Generate DataContext for PVMAP generation

Philosophy:
- Tools provide statistical EVIDENCE
- LLM makes semantic DECISIONS based on evidence
- Existing code is wrapped, not rewritten
"""

import csv
import os
import random
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    np = None
    PANDAS_AVAILABLE = False


# ============================================================================
# Helper: Sanitize NaN/inf values for JSON serialization
# ============================================================================

def _sanitize_for_json(obj: Any) -> Any:
    """Recursively sanitize NaN/inf values for JSON serialization.

    JSON doesn't support NaN or inf values. This function converts them to None
    so they become null in JSON, which is valid.

    Args:
        obj: Any Python object (dict, list, float, etc.)

    Returns:
        Sanitized object safe for JSON serialization
    """
    import math

    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [_sanitize_for_json(item) for item in obj]
    elif isinstance(obj, float):
        if math.isnan(obj) or math.isinf(obj):
            return None
        return obj
    elif PANDAS_AVAILABLE and pd is not None:
        # Handle pandas NA types
        if pd.isna(obj):
            return None
    return obj


# ============================================================================
# Tool 1: preview_data
# ============================================================================

def preview_data(file_path: str, n_rows: int = 20) -> dict:
    """Preview first N rows of a CSV file.

    Provides quick overview of data structure without full analysis.
    LLM uses this to get initial understanding of column names and format.

    Args:
        file_path: Path to CSV file
        n_rows: Number of rows to preview (default: 20)

    Returns:
        Dictionary with:
            - success: bool
            - headers: List[str] - Column names
            - sample_rows: List[dict] - First N rows as dicts
            - total_rows: int - Total rows in file (estimate)
            - total_columns: int - Number of columns
            - file_size_kb: float - File size in KB
            - error: str | None
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "headers": [],
                "sample_rows": [],
                "total_rows": 0,
                "total_columns": 0,
                "file_size_kb": 0,
            }

        # Get file size
        file_size_kb = file_path.stat().st_size / 1024

        # Read with pandas for efficiency if available
        if PANDAS_AVAILABLE:
            # Count total rows efficiently
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                total_rows = sum(1 for _ in f) - 1  # Subtract header

            # Read preview rows
            df = pd.read_csv(file_path, nrows=n_rows, encoding='utf-8',
                            on_bad_lines='skip', low_memory=False)
            headers = list(df.columns)
            # Sanitize NaN/inf values for JSON serialization
            sample_rows = _sanitize_for_json(df.to_dict('records'))
            total_columns = len(headers)
        else:
            # Fallback to csv module
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                sample_rows = []
                total_rows = 0
                for i, row in enumerate(reader):
                    total_rows += 1
                    if i < n_rows:
                        sample_rows.append(dict(row))
                total_columns = len(headers)

        return {
            "success": True,
            "error": None,
            "headers": headers,
            "sample_rows": sample_rows,
            "total_rows": total_rows,
            "total_columns": total_columns,
            "file_size_kb": round(file_size_kb, 2),
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to preview file: {str(e)}",
            "headers": [],
            "sample_rows": [],
            "total_rows": 0,
            "total_columns": 0,
            "file_size_kb": 0,
        }


# ============================================================================
# Tool 2: analyze_columns
# ============================================================================

def analyze_columns(file_path: str, sample_size: int = 500) -> dict:
    """Analyze columns to provide evidence for LLM classification decisions.

    Returns statistical evidence per column. The LLM uses this to decide:
    - Which columns are place/time/dimension/value/metadata
    - What sampling strategy to use

    Args:
        file_path: Path to CSV file
        sample_size: Number of rows to analyze (default: 500)

    Returns:
        Dictionary with:
            - success: bool
            - total_rows: int
            - total_columns: int
            - columns: Dict[str, ColumnAnalysis] where ColumnAnalysis contains:
                - cardinality: int (exact unique count)
                - cardinality_ratio: float (unique/total)
                - density: float (non-null percentage)
                - dtype: str (Integer, Float, String, Date)
                - sample_values: List[str] (5 most frequent + 5 random)
                - is_unique: bool (cardinality == total_rows?)
                - looks_like_place: bool
                - looks_like_date: bool
            - error: str | None
    """
    try:
        file_path = Path(file_path)
        if not file_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "columns": {},
                "total_rows": 0,
                "total_columns": 0,
            }

        # Read sample data
        if PANDAS_AVAILABLE:
            df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip',
                            low_memory=False)
            total_rows = len(df)
            if total_rows > sample_size:
                # Random sample for analysis
                df = df.sample(n=sample_size, random_state=42)
            headers = list(df.columns)
        else:
            # Fallback to csv module
            with open(file_path, 'r', encoding='utf-8', errors='replace') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                rows = list(reader)
                total_rows = len(rows)
                if total_rows > sample_size:
                    rows = random.sample(rows, sample_size)
                # Convert to pseudo-dataframe structure
                df = {col: [row.get(col, '') for row in rows] for col in headers}

        columns_analysis = {}
        n_sample = len(df) if PANDAS_AVAILABLE else len(df.get(headers[0], [])) if headers else 0

        for col in headers:
            if PANDAS_AVAILABLE:
                series = df[col]
                values = series.dropna().astype(str).tolist()
            else:
                values = [str(v) for v in df.get(col, []) if v and str(v).strip()]

            # Calculate statistics
            unique_values = list(set(values))
            cardinality = len(unique_values)
            cardinality_ratio = cardinality / n_sample if n_sample > 0 else 0
            density = len(values) / n_sample if n_sample > 0 else 0
            is_unique = cardinality >= n_sample * 0.95  # Allow 5% tolerance

            # Detect data type
            dtype = _detect_dtype(values)

            # Detect place patterns
            looks_like_place = _looks_like_place(col, unique_values[:20])

            # Detect date patterns
            looks_like_date = _looks_like_date(col, unique_values[:20])

            # Sample values: 5 most frequent + 5 random
            sample_values = _get_sample_values(values, max_frequent=5, max_random=5)

            columns_analysis[col] = {
                "cardinality": cardinality,
                "cardinality_ratio": round(cardinality_ratio, 4),
                "density": round(density, 4),
                "dtype": dtype,
                "sample_values": sample_values,
                "is_unique": is_unique,
                "looks_like_place": looks_like_place,
                "looks_like_date": looks_like_date,
            }

        # Sanitize for JSON serialization (NaN/inf values)
        return _sanitize_for_json({
            "success": True,
            "error": None,
            "total_rows": total_rows,
            "total_columns": len(headers),
            "columns": columns_analysis,
        })

    except Exception as e:
        return {
            "success": False,
            "error": f"Failed to analyze columns: {str(e)}",
            "columns": {},
            "total_rows": 0,
            "total_columns": 0,
        }


def _detect_dtype(values: List[str]) -> str:
    """Detect predominant data type in values."""
    if not values:
        return "Empty"

    int_count = 0
    float_count = 0
    date_count = 0

    for val in values[:100]:  # Check first 100 values
        val = str(val).strip().replace(',', '').replace('$', '').replace('%', '')

        # Try integer
        try:
            int(val)
            int_count += 1
            continue
        except (ValueError, TypeError):
            pass

        # Try float
        try:
            float(val)
            float_count += 1
            continue
        except (ValueError, TypeError):
            pass

        # Try date patterns
        if re.match(r'^\d{4}(-\d{2}){0,2}$', val) or re.match(r'^\d{4}Q\d$', val):
            date_count += 1

    total = len(values[:100])
    if int_count > total * 0.8:
        return "Integer"
    elif (int_count + float_count) > total * 0.8:
        return "Float"
    elif date_count > total * 0.8:
        return "Date"
    return "String"


def _looks_like_place(col_name: str, sample_values: List[str]) -> bool:
    """Check if column looks like a geographic identifier."""
    col_lower = col_name.lower()

    # Keyword patterns
    place_keywords = ['state', 'county', 'fips', 'geo', 'country', 'region',
                      'place', 'city', 'zip', 'tract', 'cbsa', 'msa', 'location']
    if any(kw in col_lower for kw in place_keywords):
        return True

    # Check value patterns
    for val in sample_values[:10]:
        val = str(val).strip()
        # geoId/ pattern
        if val.startswith('geoId/') or val.startswith('country/'):
            return True
        # FIPS-like (2 or 5 digit numbers)
        if re.match(r'^\d{2}$', val) or re.match(r'^\d{5}$', val):
            return True
        # ISO country codes
        if re.match(r'^[A-Z]{2,3}$', val):
            return True

    return False


def _looks_like_date(col_name: str, sample_values: List[str]) -> bool:
    """Check if column looks like a date/time identifier."""
    col_lower = col_name.lower()

    # Keyword patterns
    time_keywords = ['year', 'date', 'month', 'quarter', 'period', 'time',
                     'fiscal', 'annual', 'weekly', 'daily']
    if any(kw in col_lower for kw in time_keywords):
        return True

    # Check value patterns
    date_pattern_count = 0
    for val in sample_values[:10]:
        val = str(val).strip()
        # Year only (2000-2099)
        if re.match(r'^20\d{2}$', val) or re.match(r'^19\d{2}$', val):
            date_pattern_count += 1
        # Year-month or year-month-day
        elif re.match(r'^\d{4}-\d{2}(-\d{2})?$', val):
            date_pattern_count += 1
        # Quarter
        elif re.match(r'^\d{4}Q\d$', val):
            date_pattern_count += 1

    return date_pattern_count >= len(sample_values) * 0.5


def _get_sample_values(values: List[str], max_frequent: int = 5,
                       max_random: int = 5) -> List[str]:
    """Get sample values: most frequent + random."""
    if not values:
        return []

    from collections import Counter
    counter = Counter(values)

    # Most frequent
    frequent = [val for val, _ in counter.most_common(max_frequent)]

    # Random (from values not already included)
    remaining = [v for v in values if v not in frequent]
    if remaining:
        random_sample = random.sample(remaining, min(max_random, len(remaining)))
    else:
        random_sample = []

    return frequent + random_sample


# ============================================================================
# Tool 3: sample_rows
# ============================================================================

def sample_rows(
    file_path: str,
    output_path: str,
    strategy_json: str
) -> dict:
    """Execute sampling with LLM-designed strategy.

    The LLM decides the strategy based on analyze_columns evidence.

    Args:
        file_path: Path to input CSV file
        output_path: Path to output sampled CSV file
        strategy_json: JSON string with sampling strategy:
            e.g., '{"mode": "stratified", "target_rows": 80, "stratify_by": ["Gender"]}'
            Valid modes: "random", "head", "stratified", "fixed_pivot"
            For fixed_pivot, include pivot_config with fix and vary keys.

    Returns:
        Dictionary with:
            - success: bool
            - output_file: str
            - rows_sampled: int
            - strategy_used: str
            - error: str | None
    """
    try:
        file_path = Path(file_path)
        output_path = Path(output_path)

        if not file_path.exists():
            return {
                "success": False,
                "error": f"File not found: {file_path}",
                "output_file": "",
                "rows_sampled": 0,
                "strategy_used": "",
            }

        # Parse strategy JSON
        import json
        try:
            strategy = json.loads(strategy_json) if strategy_json else {}
        except json.JSONDecodeError:
            strategy = {}

        # Extract strategy parameters
        mode = strategy.get("mode", "head")
        target_rows = strategy.get("target_rows", 80)
        stratify_by = strategy.get("stratify_by", [])
        pivot_config = strategy.get("pivot_config", {})

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Execute based on mode
        if mode == "random":
            result = _sample_random(file_path, output_path, target_rows)
        elif mode == "head":
            result = _sample_head(file_path, output_path, target_rows)
        elif mode == "stratified":
            result = _sample_stratified(file_path, output_path, target_rows, stratify_by)
        elif mode == "fixed_pivot":
            result = _sample_fixed_pivot(file_path, output_path, target_rows, pivot_config)
        else:
            # Fallback to head sampling
            result = _sample_head(file_path, output_path, target_rows)

        result["strategy_used"] = mode
        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Sampling failed: {str(e)}",
            "output_file": "",
            "rows_sampled": 0,
            "strategy_used": "unknown",
        }


def _sample_random(file_path: Path, output_path: Path, target_rows: int) -> dict:
    """Random sampling."""
    if PANDAS_AVAILABLE:
        df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip', low_memory=False)
        n_sample = min(target_rows, len(df))
        sampled = df.sample(n=n_sample, random_state=42)
        sampled.to_csv(output_path, index=False)
        return {
            "success": True,
            "error": None,
            "output_file": str(output_path),
            "rows_sampled": len(sampled),
        }
    else:
        return _sample_head(file_path, output_path, target_rows)


def _sample_head(file_path: Path, output_path: Path, target_rows: int) -> dict:
    """Head sampling (first N rows)."""
    if PANDAS_AVAILABLE:
        df = pd.read_csv(file_path, nrows=target_rows, encoding='utf-8',
                        on_bad_lines='skip', low_memory=False)
        df.to_csv(output_path, index=False)
        return {
            "success": True,
            "error": None,
            "output_file": str(output_path),
            "rows_sampled": len(df),
        }
    else:
        with open(file_path, 'r', encoding='utf-8', errors='replace') as fin:
            with open(output_path, 'w', newline='', encoding='utf-8') as fout:
                reader = csv.reader(fin)
                writer = csv.writer(fout)
                row_count = 0
                for i, row in enumerate(reader):
                    if i == 0:  # Header
                        writer.writerow(row)
                    elif i <= target_rows:
                        writer.writerow(row)
                        row_count += 1
                    else:
                        break
        return {
            "success": True,
            "error": None,
            "output_file": str(output_path),
            "rows_sampled": row_count,
        }


def _sample_stratified(file_path: Path, output_path: Path, target_rows: int,
                       stratify_by: List[str]) -> dict:
    """Stratified sampling by specified columns."""
    if not PANDAS_AVAILABLE:
        return _sample_head(file_path, output_path, target_rows)

    df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip', low_memory=False)

    # Filter to valid stratify columns
    valid_cols = [c for c in stratify_by if c in df.columns]
    if not valid_cols:
        return _sample_random(file_path, output_path, target_rows)

    # Group by stratify columns
    sampled_rows = []
    grouped = df.groupby(valid_cols, dropna=False)

    # Calculate rows per group
    n_groups = len(grouped)
    rows_per_group = max(1, target_rows // n_groups)

    for _, group in grouped:
        n_sample = min(rows_per_group, len(group))
        sampled_rows.append(group.sample(n=n_sample, random_state=42))

    sampled = pd.concat(sampled_rows)

    # Trim to target if over
    if len(sampled) > target_rows:
        sampled = sampled.head(target_rows)

    sampled.to_csv(output_path, index=False)

    return {
        "success": True,
        "error": None,
        "output_file": str(output_path),
        "rows_sampled": len(sampled),
    }


def _sample_fixed_pivot(file_path: Path, output_path: Path, target_rows: int,
                        pivot_config: dict) -> dict:
    """Fixed-pivot sampling for skeleton demonstration.

    Fixes anchor columns (place/time) and varies dimensions to show
    how StatVars are formed.
    """
    if not PANDAS_AVAILABLE:
        return _sample_head(file_path, output_path, target_rows)

    df = pd.read_csv(file_path, encoding='utf-8', on_bad_lines='skip', low_memory=False)

    fix_values = pivot_config.get("fix", {})
    vary_columns = pivot_config.get("vary", [])

    # If no pivot config, fall back to stratified by vary columns
    if not fix_values and vary_columns:
        return _sample_stratified(file_path, output_path, target_rows, vary_columns)

    # Find rows matching fixed values
    mask = pd.Series([True] * len(df))
    for col, val in fix_values.items():
        if col in df.columns:
            mask &= (df[col].astype(str) == str(val))

    fixed_rows = df[mask]

    # If not enough rows with fixed values, relax constraints
    if len(fixed_rows) < 5:
        # Try with just the first fixed column
        if fix_values:
            first_col = list(fix_values.keys())[0]
            first_val = fix_values[first_col]
            if first_col in df.columns:
                mask = (df[first_col].astype(str) == str(first_val))
                fixed_rows = df[mask]

    # If still not enough, use stratified
    if len(fixed_rows) < 5:
        return _sample_stratified(file_path, output_path, target_rows, vary_columns)

    # Sample from fixed rows, varying dimensions
    if len(fixed_rows) <= target_rows:
        sampled = fixed_rows
    else:
        # Sample to cover dimension variety
        if vary_columns:
            sampled = _sample_stratified_df(fixed_rows, target_rows, vary_columns)
        else:
            sampled = fixed_rows.sample(n=target_rows, random_state=42)

    sampled.to_csv(output_path, index=False)

    return {
        "success": True,
        "error": None,
        "output_file": str(output_path),
        "rows_sampled": len(sampled),
    }


def _sample_stratified_df(df, target_rows: int, stratify_by: List[str]) -> 'pd.DataFrame':
    """Helper to stratify sample from DataFrame."""
    valid_cols = [c for c in stratify_by if c in df.columns]
    if not valid_cols:
        return df.sample(n=min(target_rows, len(df)), random_state=42)

    sampled_rows = []
    grouped = df.groupby(valid_cols, dropna=False)
    n_groups = len(grouped)
    rows_per_group = max(1, target_rows // n_groups)

    for _, group in grouped:
        n_sample = min(rows_per_group, len(group))
        sampled_rows.append(group.sample(n=n_sample, random_state=42))

    sampled = pd.concat(sampled_rows)
    if len(sampled) > target_rows:
        sampled = sampled.head(target_rows)

    return sampled


# ============================================================================
# Tool 4: check_coverage
# ============================================================================

def check_coverage(
    sampled_file: str,
    place_col: str,
    time_col: str,
    dimension_columns: List[str]
) -> dict:
    """Validate LLM's dimension hypothesis by checking uniqueness.

    Tests whether rows are unique by: place + time + dimensions.
    If not unique, the LLM missed a dimension.

    Args:
        sampled_file: Path to sampled CSV file
        place_col: Column identified as place (observationAbout)
        time_col: Column identified as time (observationDate)
        dimension_columns: Columns identified as dimensions

    Returns:
        Dictionary with:
            - success: bool
            - is_unique: bool (are rows unique by these columns?)
            - duplicate_count: int (how many duplicate combinations)
            - total_combinations: int
            - covered_combinations: int
            - coverage_percent: float
            - per_dimension: Dict[col, {covered, total, values}]
            - error: str | None
    """
    try:
        from src.pipeline.sampling.combination_tracker import CombinationTracker
    except ImportError:
        try:
            from combination_tracker import CombinationTracker
        except ImportError:
            CombinationTracker = None

    try:
        sampled_file = Path(sampled_file)
        if not sampled_file.exists():
            return {
                "success": False,
                "error": f"File not found: {sampled_file}",
                "is_unique": False,
                "duplicate_count": 0,
                "total_combinations": 0,
                "covered_combinations": 0,
                "coverage_percent": 0,
                "per_dimension": {},
            }

        # Build key columns
        key_columns = []
        if place_col:
            key_columns.append(place_col)
        if time_col:
            key_columns.append(time_col)
        key_columns.extend(dimension_columns)

        if not key_columns:
            return {
                "success": False,
                "error": "No columns specified for uniqueness check",
                "is_unique": False,
                "duplicate_count": 0,
                "total_combinations": 0,
                "covered_combinations": 0,
                "coverage_percent": 0,
                "per_dimension": {},
            }

        # Read data
        if PANDAS_AVAILABLE:
            df = pd.read_csv(sampled_file, encoding='utf-8', on_bad_lines='skip',
                            low_memory=False)

            # Check which columns exist
            valid_cols = [c for c in key_columns if c in df.columns]
            if not valid_cols:
                return {
                    "success": False,
                    "error": f"None of the specified columns found in file: {key_columns}",
                    "is_unique": False,
                    "duplicate_count": 0,
                    "total_combinations": 0,
                    "covered_combinations": 0,
                    "coverage_percent": 0,
                    "per_dimension": {},
                }

            # Check uniqueness
            total_rows = len(df)
            unique_combos = df[valid_cols].drop_duplicates()
            covered_combinations = len(unique_combos)
            duplicate_count = total_rows - covered_combinations
            is_unique = duplicate_count == 0

            # Per-dimension stats
            per_dimension = {}
            for col in dimension_columns:
                if col in df.columns:
                    unique_vals = df[col].dropna().unique().tolist()
                    per_dimension[col] = {
                        "covered": len(unique_vals),
                        "total": len(unique_vals),  # We don't know total without full data
                        "values": [str(v) for v in unique_vals[:20]],  # First 20
                    }

            # Estimate total combinations from dimension domains
            if CombinationTracker and dimension_columns:
                valid_dim_cols = [c for c in dimension_columns if c in df.columns]
                if valid_dim_cols:
                    dimension_domains = {
                        col: df[col].dropna().unique().tolist()
                        for col in valid_dim_cols
                    }
                    tracker = CombinationTracker(valid_dim_cols, dimension_domains)

                    # Add rows to tracker
                    for _, row in df.iterrows():
                        tracker.add_row(row.to_dict())

                    stats = tracker.get_coverage_stats()
                    total_combinations = stats.total_combinations
                    coverage_percent = stats.coverage_percent
                else:
                    total_combinations = covered_combinations
                    coverage_percent = 100.0
            else:
                total_combinations = covered_combinations
                coverage_percent = 100.0 if covered_combinations > 0 else 0.0

            # Sanitize for JSON serialization (NaN/inf values)
            return _sanitize_for_json({
                "success": True,
                "error": None,
                "is_unique": is_unique,
                "duplicate_count": duplicate_count,
                "total_combinations": total_combinations,
                "covered_combinations": covered_combinations,
                "coverage_percent": round(coverage_percent, 2),
                "per_dimension": per_dimension,
            })
        else:
            # Fallback without pandas
            return {
                "success": False,
                "error": "pandas is required for coverage check",
                "is_unique": False,
                "duplicate_count": 0,
                "total_combinations": 0,
                "covered_combinations": 0,
                "coverage_percent": 0,
                "per_dimension": {},
            }

    except Exception as e:
        return {
            "success": False,
            "error": f"Coverage check failed: {str(e)}",
            "is_unique": False,
            "duplicate_count": 0,
            "total_combinations": 0,
            "covered_combinations": 0,
            "coverage_percent": 0,
            "per_dimension": {},
        }


# ============================================================================
# Tool 5: generate_context
# ============================================================================

def generate_context(
    sampled_file: str,
    column_roles_json: str,
    dimension_columns: List[str],
    metadata_json: str = ""
) -> dict:
    """Generate DataContext for PVMAP generation.

    Creates a comprehensive context object and skeleton summary that
    downstream agents use to understand the dataset structure.

    Args:
        sampled_file: Path to sampled CSV file
        column_roles_json: JSON string of column classifications
            e.g., '{"State": "place", "Year": "time", "Gender": "dimension"}'
        dimension_columns: List of dimension column names
        metadata_json: Optional JSON string of metadata (from metadata.csv)

    Returns:
        Dictionary with:
            - success: bool
            - data_context: Dict (serializable context for state)
            - skeleton_summary: str (markdown for LLM prompts)
            - skeleton_sample: List[dict] (sample rows demonstrating structure)
            - statvar_pattern: str (e.g., "Count_Person_{Gender}_{Age}")
            - error: str | None
    """
    try:
        from src.pipeline.sampling.data_context import DataContext, DataContextGenerator
    except ImportError:
        try:
            from data_context import DataContext, DataContextGenerator
        except ImportError:
            DataContext = None
            DataContextGenerator = None

    try:
        import json

        sampled_file = Path(sampled_file)
        if not sampled_file.exists():
            return {
                "success": False,
                "error": f"File not found: {sampled_file}",
                "data_context": {},
                "skeleton_summary": "",
                "skeleton_sample": [],
                "statvar_pattern": "",
            }

        # Parse JSON parameters
        try:
            column_roles = json.loads(column_roles_json) if column_roles_json else {}
        except json.JSONDecodeError:
            column_roles = {}

        try:
            metadata = json.loads(metadata_json) if metadata_json else {}
        except json.JSONDecodeError:
            metadata = {}

        if not PANDAS_AVAILABLE:
            return {
                "success": False,
                "error": "pandas is required for context generation",
                "data_context": {},
                "skeleton_summary": "",
                "skeleton_sample": [],
                "statvar_pattern": "",
            }

        # Read sampled data
        df = pd.read_csv(sampled_file, encoding='utf-8', on_bad_lines='skip',
                        low_memory=False)

        # Extract dataset name from file
        dataset_name = sampled_file.parent.parent.name
        if dataset_name == "test_data":
            dataset_name = sampled_file.parent.parent.parent.name

        # Use DataContextGenerator if available
        if DataContextGenerator:
            generator = DataContextGenerator()
            context = generator.generate(df, metadata or {}, dataset_name)

            # Override column roles with LLM's classification
            if column_roles:
                context.column_roles = column_roles
                # Rebuild ignored_columns from LLM's classifications
                context.ignored_columns = [
                    col for col, role in column_roles.items()
                    if role == 'metadata'
                ]

            # Override dimension columns with LLM's identification
            if dimension_columns:
                context.dimension_columns = dimension_columns
                # Rebuild dimension domains
                context.dimension_domains = {
                    col: sorted([str(v) for v in df[col].dropna().unique()])
                    for col in dimension_columns if col in df.columns
                }
                # Rebuild aggregate values for new dimensions
                context.aggregate_values = generator._detect_aggregate_values(
                    df, dimension_columns
                )

            # Regenerate skeleton summary with LLM's classifications
            skeleton_summary = context.to_skeleton_summary()
            data_context = context.to_metadata_dict()
            statvar_pattern = context.statvar_pattern
        else:
            # Manual context generation without DataContextGenerator
            data_context, skeleton_summary, statvar_pattern = _generate_context_manual(
                df, column_roles, dimension_columns, metadata, dataset_name
            )

        # Get skeleton sample rows (first 10 for context)
        # Sanitize NaN/inf values for JSON serialization
        skeleton_sample = _sanitize_for_json(df.head(10).to_dict('records'))

        # Build result dict - sanitize for JSON serialization
        result = _sanitize_for_json({
            "success": True,
            "error": None,
            "data_context": data_context,
            "skeleton_summary": skeleton_summary,
            "skeleton_sample": skeleton_sample,
            "statvar_pattern": statvar_pattern,
            "column_roles": column_roles,
            "dimension_columns": dimension_columns,
        })

        # Write context to JSON file for SamplingAgentWrapper to read
        context_file = sampled_file.parent / "data_context.json"
        try:
            with open(context_file, 'w', encoding='utf-8') as f:
                # Serialize with special handling for non-JSON types
                def json_serializer(obj):
                    if hasattr(obj, 'isoformat'):
                        return obj.isoformat()
                    if hasattr(obj, 'tolist'):
                        return obj.tolist()
                    return str(obj)
                json.dump(result, f, indent=2, default=json_serializer)
        except Exception as write_err:
            # Don't fail the tool if file write fails, just log
            result["context_file_error"] = str(write_err)

        return result

    except Exception as e:
        return {
            "success": False,
            "error": f"Context generation failed: {str(e)}",
            "data_context": {},
            "skeleton_summary": "",
            "skeleton_sample": [],
            "statvar_pattern": "",
        }


def _generate_context_manual(
    df: 'pd.DataFrame',
    column_roles: Dict[str, str],
    dimension_columns: List[str],
    metadata: Dict[str, Any],
    dataset_name: str
) -> tuple:
    """Generate context without DataContextGenerator class.

    Produces enriched format with graceful degradation (no one-shot example
    or aggregate detection in fallback).
    """
    # Extract place and time columns from roles
    place_col = None
    time_col = None
    value_cols = []
    ignored_cols = []

    for col, role in column_roles.items():
        if role == 'place' and place_col is None:
            place_col = col
        elif role == 'time' and time_col is None:
            time_col = col
        elif role == 'value':
            value_cols.append(col)
        elif role == 'metadata':
            ignored_cols.append(col)

    # Build dimension domains
    dimension_domains = {}
    for col in dimension_columns:
        if col in df.columns:
            dimension_domains[col] = sorted([str(v) for v in df[col].dropna().unique()])

    # Infer measurement type
    measurement_type = "Count"
    if metadata:
        unit = metadata.get('unit', '').lower()
        if 'percent' in unit:
            measurement_type = "Percent"
        elif 'rate' in unit:
            measurement_type = "Rate"

    # Build StatVar pattern
    pattern_parts = [measurement_type, "Person"]
    for dim in dimension_columns[:3]:
        pattern_parts.append(f"{{{dim}}}")
    statvar_pattern = "_".join(pattern_parts)

    # Calculate combinations
    total_combinations = 1
    for vals in dimension_domains.values():
        total_combinations *= max(1, len(vals))

    # Detect pre-formatted DC data
    col_set = set(c.lower().strip() for c in df.columns)
    is_preformatted = {'variablemeasured', 'observationabout', 'value'}.issubset(col_set)

    # Build data context dict
    topology = "TIDY_LONG" if len(value_cols) <= 2 else "PIVOTED_WIDE"
    data_context = {
        "dataset_name": dataset_name,
        "topology": topology,
        "population_type": "Person",
        "geography": {"column": place_col} if place_col else {},
        "time": {"column": time_col} if time_col else {},
        "column_roles": column_roles,
        "dimension_columns": dimension_columns,
        "dimension_domains": dimension_domains,
        "value_columns": [{"name": c} for c in value_cols],
        "measurement_type": measurement_type,
        "statvar_pattern": statvar_pattern,
        "total_combinations": total_combinations,
        "total_rows": len(df),
        "total_columns": len(df.columns),
        "all_columns": list(df.columns),
        "ignored_columns": ignored_cols,
        "aggregate_values": {},
        "place_resolution_hints": [],
        "is_preformatted_dc": is_preformatted,
    }

    # Build enriched skeleton summary (graceful degradation)
    lines = [
        "## 1. TOPOLOGY & STRUCTURE",
        "",
        f"- **Dataset:** {dataset_name}",
        f"- **Format:** {topology}",
        f"- **Rows:** {len(df)}  |  **Columns:** {len(df.columns)}",
        "",
        f"**ALL column headers (exact, case-sensitive):** `{'`, `'.join(df.columns)}`",
        "",
        "## 2. COLUMN CLASSIFICATIONS",
        "",
    ]

    if column_roles:
        lines.append("| Column | Role |")
        lines.append("|--------|------|")
        for col, role in column_roles.items():
            lines.append(f"| `{col}` | {role} |")

    if ignored_cols:
        lines.append("")
        lines.append(f"**Ignored columns** (metadata/constant — do NOT map): `{'`, `'.join(ignored_cols)}`")
    lines.append("")

    lines.append("## 3. ANCHOR ANALYSIS")
    lines.append("")
    if place_col:
        lines.append(f"**Geography:** Column `{place_col}`")
    else:
        lines.append("**Geography:** Not detected (CRITICAL: must identify)")
    if time_col:
        lines.append(f"**Time:** Column `{time_col}`")
    else:
        lines.append("**Time:** Not detected")
    lines.append("")

    lines.append("## 4. DIMENSION DEEP DIVE")
    lines.append("")
    if dimension_columns:
        for dim in dimension_columns:
            vals = dimension_domains.get(dim, [])
            vals_preview = vals[:15]
            vals_str = ", ".join(vals_preview)
            if len(vals) > 15:
                vals_str += f", ... ({len(vals)} total)"
            lines.append(f"- **`{dim}`** ({len(vals)} values): [{vals_str}]")
    else:
        lines.append("- No dimension columns detected")
    lines.append("")

    lines.append("## 5. MEASUREMENT & UNITS")
    lines.append("")
    if value_cols:
        for vc in value_cols:
            lines.append(f"- Value Column: `{vc}`")
    else:
        lines.append("- No value columns detected")
    lines.append(f"- **Population Type:** Person")
    lines.append(f"- **Measurement Type:** {measurement_type}")
    lines.append("")

    lines.append("## 6. STATVAR PATTERN (P+M+C Formula)")
    lines.append("")
    lines.append(f"`{statvar_pattern}`")
    lines.append("")

    lines.append("## 7. ONE-SHOT PVMAP EXAMPLE")
    lines.append("")
    lines.append("_Simplified analysis. One-shot example not available in fallback mode._")
    lines.append("")

    lines.append("## 8. PRE-FORMATTED DATA COMMONS DETECTION")
    lines.append("")
    if is_preformatted:
        lines.append("**YES — This data is already in Data Commons format.**")
        lines.append("Use passthrough mapping.")
    else:
        lines.append("Not pre-formatted. Generate PVMAP from scratch.")
    lines.append("")

    lines.append("## 9. COVERAGE")
    lines.append("")
    lines.append(f"- Total Dimension Combinations: {total_combinations}")
    lines.append("")
    lines.append("**IMPORTANT:** Generate PVMAP for ALL dimension combinations, not just those in sample.")
    lines.append("")
    lines.append("_Simplified analysis. Full context generation not available._")

    skeleton_summary = "\n".join(lines)

    return data_context, skeleton_summary, statvar_pattern


# ============================================================================
# Tool Registry for ADK
# ============================================================================

def get_sampling_tools() -> List[callable]:
    """Return list of sampling tools for ADK agent registration."""
    return [
        preview_data,
        analyze_columns,
        sample_rows,
        check_coverage,
        generate_context,
    ]


# For backward compatibility
SAMPLING_TOOLS = get_sampling_tools()
