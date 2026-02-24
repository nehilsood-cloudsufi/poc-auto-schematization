"""Deterministic stratified sampler for programmatic sampling.

Replaces LLM-driven strategy selection with code-controlled sampling.
Reuses the 4 sampling modes from sampling_tools.py.

Strategy selection is deterministic:
- Pre-formatted DC data -> head sampling
- PIVOTED_WIDE topology -> head sampling (structure in headers)
- Has dimensions -> stratified by dimensions
- Fallback -> random with seed=42
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    np = None
    PANDAS_AVAILABLE = False

from src.agents.sampling.schemas import RelationalSkeleton, SemanticAnalysis
from src.pipeline.sampling.profiler import DatasetProfile, _detect_metadata_rows
from src.tools.sampling_tools import (
    _sample_head,
    _sample_random,
    _sample_stratified,
    _sanitize_for_json,
)

logger = logging.getLogger(__name__)

# Row target bounds
MIN_TARGET_ROWS = 30
MAX_TARGET_ROWS = 150
EDGE_CASE_BUDGET = 5
DEFAULT_ANCHOR_BUDGET = 15  # min(10, places) + min(5, time_periods)


@dataclass
class SamplingResult:
    """Result of deterministic sampling."""

    sampled_file: Path = Path()
    rows_sampled: int = 0
    strategy_used: str = ""
    target_rows: int = 0
    success: bool = True
    error: Optional[str] = None
    coverage_stats: dict = field(default_factory=dict)


def calculate_target_rows(
    profile: DatasetProfile,
    analysis: SemanticAnalysis,
    skeleton: RelationalSkeleton,
) -> int:
    """Calculate dynamic row target based on data complexity.

    Formula:
        base = sum of unique values across all dimension columns
        target = base + edge_case_budget + anchor_budget
        target = clamp(target, min=30, max=150)

    For wide datasets, column headers ARE the dimensions -- fewer rows needed.
    For tall datasets with many categoricals, more rows needed.
    """
    # Sum cardinality of dimension columns
    dim_values_sum = 0
    for dim_col in skeleton.dimension_columns:
        col_profile = profile.columns.get(dim_col)
        if col_profile:
            dim_values_sum += col_profile.cardinality

    # Anchor budget
    place_col = profile.columns.get(skeleton.place_column)
    time_col = profile.columns.get(skeleton.time_column)
    place_budget = min(10, place_col.cardinality) if place_col else 5
    time_budget = min(5, time_col.cardinality) if time_col else 3
    anchor_budget = place_budget + time_budget

    # Edge case budget (NaN rows, sentinel rows, min/max)
    edge_budget = EDGE_CASE_BUDGET
    sentinel_cols = [
        name for name, col in profile.columns.items()
        if col.sentinel_values
    ]
    if sentinel_cols:
        edge_budget = min(10, edge_budget + len(sentinel_cols))

    target = dim_values_sum + anchor_budget + edge_budget
    target = max(MIN_TARGET_ROWS, min(MAX_TARGET_ROWS, target))

    logger.info(
        "Target rows: %d (dims=%d, anchors=%d, edges=%d)",
        target, dim_values_sum, anchor_budget, edge_budget,
    )
    return target


def select_strategy(
    analysis: SemanticAnalysis,
    skeleton: RelationalSkeleton,
) -> str:
    """Deterministic strategy selection.

    Returns:
        Strategy name: "head", "stratified", or "random".
    """
    if analysis.is_preformatted_dc:
        return "head"

    if analysis.topology == "PIVOTED_WIDE":
        return "head"

    if skeleton.dimension_columns:
        return "stratified"

    return "random"


def execute_sampling(
    file_path: Path,
    output_path: Path,
    skeleton: RelationalSkeleton,
    analysis: SemanticAnalysis,
    profile: DatasetProfile,
    target_rows: Optional[int] = None,
) -> SamplingResult:
    """Execute deterministic sampling with strategy based on data analysis.

    Args:
        file_path: Path to input CSV.
        output_path: Path to write sampled CSV.
        skeleton: Relational skeleton from LLM.
        analysis: Semantic analysis from LLM.
        profile: Dataset profile from profiler.
        target_rows: Override for target row count.

    Returns:
        SamplingResult with file path and stats.
    """
    if not PANDAS_AVAILABLE:
        return SamplingResult(
            success=False, error="pandas is required for sampling"
        )

    file_path = Path(file_path)
    output_path = Path(output_path)

    if not file_path.exists():
        return SamplingResult(
            success=False, error=f"File not found: {file_path}"
        )

    # Calculate target rows
    if target_rows is None:
        target_rows = calculate_target_rows(profile, analysis, skeleton)

    # Select strategy
    strategy = select_strategy(analysis, skeleton)

    # Ensure output directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    logger.info(
        "Sampling %s: strategy=%s, target=%d rows",
        file_path.name, strategy, target_rows,
    )

    # Pre-clean: write metadata-free CSV for head/random strategies
    clean_file = file_path
    if profile.metadata_rows and strategy in ("head", "random"):
        try:
            df_raw = pd.read_csv(
                file_path, encoding='utf-8', on_bad_lines='skip', low_memory=False
            )
            df_clean, _ = _detect_metadata_rows(df_raw)
            clean_file = output_path.parent / f"_clean_{file_path.name}"
            df_clean.to_csv(clean_file, index=False)
            logger.info("Wrote metadata-free source (%d rows) for %s sampling",
                        len(df_clean), strategy)
        except Exception as e:
            logger.warning("Failed to pre-clean metadata rows: %s", e)
            clean_file = file_path

    # Execute sampling
    if strategy == "head":
        result = _sample_head(clean_file, output_path, target_rows)
    elif strategy == "stratified":
        result = _execute_stratified_with_coverage(
            file_path, output_path, target_rows,
            skeleton.dimension_columns, profile,
        )
    else:
        result = _sample_random(clean_file, output_path, target_rows)

    # Clean up temp file
    if clean_file != file_path and clean_file.exists():
        try:
            clean_file.unlink()
        except OSError:
            pass

    if not result.get("success"):
        return SamplingResult(
            success=False,
            error=result.get("error", "Sampling failed"),
            strategy_used=strategy,
        )

    rows_sampled = result.get("rows_sampled", 0)

    # Inject edge cases
    edge_rows = _inject_edge_cases(
        file_path, output_path, profile, skeleton, target_rows - rows_sampled
    )
    rows_sampled += edge_rows

    # Inline coverage check
    coverage = _check_coverage_inline(output_path, skeleton)

    return SamplingResult(
        sampled_file=output_path,
        rows_sampled=rows_sampled,
        strategy_used=strategy,
        target_rows=target_rows,
        success=True,
        coverage_stats=coverage,
    )


def _execute_stratified_with_coverage(
    file_path: Path,
    output_path: Path,
    target_rows: int,
    dimension_columns: List[str],
    profile: DatasetProfile,
) -> dict:
    """Stratified sampling with guaranteed dimension value coverage.

    Two-pass approach:
      Pass 1: Select one representative row per unique value per dimension column.
      Pass 2: Fill remaining budget with stratified sampling across groups.

    Also excludes metadata rows (units, descriptions) from the sampling source.

    Returns:
        dict with keys: success, rows_sampled, error (on failure).
    """
    try:
        df = pd.read_csv(
            file_path, encoding='utf-8', on_bad_lines='skip', low_memory=False
        )

        # Exclude metadata rows from sampling source
        if profile.metadata_rows:
            df, _ = _detect_metadata_rows(df)

        valid_dims = [c for c in dimension_columns if c in df.columns]
        if not valid_dims:
            # Fallback to random if no valid dimension columns
            return _sample_random(file_path, output_path, target_rows)

        # PASS 1: Coverage guarantee — one representative row per unique value per dimension
        coverage_indices = set()
        for dim_col in valid_dims:
            for val in df[dim_col].unique():
                candidates = df[df[dim_col] == val].index
                # Pick the first candidate not already selected
                added = False
                for idx in candidates:
                    if idx not in coverage_indices:
                        coverage_indices.add(idx)
                        added = True
                        break
                if not added:
                    # All candidates already selected — just use one
                    coverage_indices.add(candidates[0])

        logger.info(
            "Coverage pass: %d rows cover all unique values across %d dimension columns",
            len(coverage_indices), len(valid_dims),
        )

        # PASS 2: Fill remaining budget with stratified sampling
        remaining_budget = target_rows - len(coverage_indices)
        if remaining_budget > 0:
            remaining_df = df.drop(index=list(coverage_indices))
            if len(remaining_df) > 0 and valid_dims:
                try:
                    grouped = remaining_df.groupby(valid_dims, dropna=False)
                    n_groups = len(grouped)
                    rows_per = max(1, remaining_budget // n_groups)
                    fill_rows = []
                    for _, group in grouped:
                        fill_rows.append(
                            group.sample(n=min(rows_per, len(group)), random_state=42)
                        )
                    fill_df = pd.concat(fill_rows)
                    if len(fill_df) > remaining_budget:
                        fill_df = fill_df.sample(n=remaining_budget, random_state=42)
                    coverage_indices.update(fill_df.index)
                except Exception as e:
                    logger.warning("Stratified fill failed, using random fill: %s", e)
                    fill = remaining_df.sample(
                        n=min(remaining_budget, len(remaining_df)), random_state=42
                    )
                    coverage_indices.update(fill.index)

        # Build final sample preserving original row order
        sampled_df = df.loc[sorted(coverage_indices)]

        # Trim to target if coverage pass alone exceeded budget
        if len(sampled_df) > target_rows:
            sampled_df = sampled_df.sample(n=target_rows, random_state=42).sort_index()

        sampled_df.to_csv(output_path, index=False)

        return {
            "success": True,
            "rows_sampled": len(sampled_df),
        }

    except Exception as e:
        logger.error("Stratified sampling with coverage failed: %s", e)
        return {
            "success": False,
            "error": str(e),
        }


def _inject_edge_cases(
    source_path: Path,
    output_path: Path,
    profile: DatasetProfile,
    skeleton: RelationalSkeleton,
    budget: int,
) -> int:
    """Append edge-case rows (NaN, sentinels, min/max) to sampled file.

    Args:
        source_path: Original full CSV.
        output_path: Sampled CSV to append to.
        profile: Dataset profile.
        skeleton: Relational skeleton.
        budget: Max additional rows to add.

    Returns:
        Number of rows actually appended.
    """
    if budget <= 0 or not PANDAS_AVAILABLE:
        return 0

    try:
        df_full = pd.read_csv(
            source_path, encoding='utf-8', on_bad_lines='skip', low_memory=False
        )
        df_sampled = pd.read_csv(
            output_path, encoding='utf-8', on_bad_lines='skip', low_memory=False
        )
        sampled_indices = set(df_sampled.index.tolist())
        edge_rows = []

        # Find rows with NaN in value columns
        for val_col in skeleton.value_columns[:3]:
            if val_col in df_full.columns:
                nan_rows = df_full[df_full[val_col].isna()]
                if len(nan_rows) > 0:
                    edge_rows.append(nan_rows.head(2))

        # Find rows with sentinel values in value columns
        for col_name, col_profile in profile.columns.items():
            if col_profile.sentinel_values and col_name in df_full.columns:
                for sentinel in col_profile.sentinel_values[:2]:
                    mask = df_full[col_name].astype(str).str.strip() == sentinel
                    sentinel_rows = df_full[mask]
                    if len(sentinel_rows) > 0:
                        edge_rows.append(sentinel_rows.head(1))

        # Find min/max rows for value columns
        for val_col in skeleton.value_columns[:2]:
            if val_col in df_full.columns:
                numeric_series = pd.to_numeric(df_full[val_col], errors='coerce')
                if numeric_series.notna().any():
                    min_idx = numeric_series.idxmin()
                    max_idx = numeric_series.idxmax()
                    if min_idx is not None:
                        edge_rows.append(df_full.iloc[[min_idx]])
                    if max_idx is not None:
                        edge_rows.append(df_full.iloc[[max_idx]])

        if not edge_rows:
            return 0

        # Concatenate and deduplicate
        all_edge = pd.concat(edge_rows).drop_duplicates()
        # Remove rows already in sample
        if len(all_edge) > budget:
            all_edge = all_edge.head(budget)

        # Append to output file
        combined = pd.concat([df_sampled, all_edge]).drop_duplicates()
        combined.to_csv(output_path, index=False)

        added = len(combined) - len(df_sampled)
        if added > 0:
            logger.info("Injected %d edge-case rows", added)
        return max(0, added)

    except Exception as e:
        logger.warning("Edge-case injection failed: %s", e)
        return 0


def _check_coverage_inline(
    sampled_path: Path, skeleton: RelationalSkeleton
) -> dict:
    """Inline coverage check without LLM.

    Returns coverage statistics dict.
    """
    if not PANDAS_AVAILABLE or not skeleton.dimension_columns:
        return {}

    try:
        df = pd.read_csv(
            sampled_path, encoding='utf-8', on_bad_lines='skip', low_memory=False
        )
        valid_dims = [c for c in skeleton.dimension_columns if c in df.columns]
        if not valid_dims:
            return {}

        # Check uniqueness by place + time + dimensions
        key_cols = []
        if skeleton.place_column and skeleton.place_column in df.columns:
            key_cols.append(skeleton.place_column)
        if skeleton.time_column and skeleton.time_column in df.columns:
            key_cols.append(skeleton.time_column)
        key_cols.extend(valid_dims)

        total_rows = len(df)
        unique_combos = len(df[key_cols].drop_duplicates())
        duplicate_count = total_rows - unique_combos

        # Per-dimension coverage
        per_dim = {}
        for dim in valid_dims:
            unique_vals = df[dim].dropna().unique().tolist()
            per_dim[dim] = {
                "covered": len(unique_vals),
                "values": [str(v) for v in unique_vals[:20]],
            }

        return _sanitize_for_json({
            "is_unique": duplicate_count == 0,
            "duplicate_count": duplicate_count,
            "unique_combinations": unique_combos,
            "per_dimension": per_dim,
        })

    except Exception as e:
        logger.warning("Coverage check failed: %s", e)
        return {}
