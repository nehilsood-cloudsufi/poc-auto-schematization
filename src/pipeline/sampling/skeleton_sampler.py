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
"""Skeleton sampler implementing the Fixed-Pivot sampling strategy.

This module provides advanced sampling that demonstrates the dimension
structure of a dataset to the LLM. The strategy has three phases:

1. Diagonal Scan (25%): Cover all unique dimension values
2. Fixed-Pivot Blocks (50%): Vary one dimension at a time, fix others
3. Edge Cases (25%): Totals, nulls, formatting edge cases

The goal is to help the LLM understand:
- Which columns are dimensions vs values
- How dimensions are independent
- What the StatVar pattern should be
"""

import random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any

from absl import logging

try:
    import pandas as pd
except ImportError:
    pd = None


@dataclass
class SkeletonSampleResult:
    """Result from skeleton sampling."""

    # Sampled data
    sampled_rows: List[Dict[str, Any]] = field(default_factory=list)
    sampled_indices: List[int] = field(default_factory=list)

    # Breakdown by strategy
    diagonal_scan_count: int = 0
    fixed_pivot_count: int = 0
    edge_case_count: int = 0

    # Coverage stats
    dimension_value_coverage: Dict[str, float] = field(default_factory=dict)
    combination_coverage: float = 0.0

    # Total rows in original
    total_rows: int = 0


class SkeletonSampler:
    """Implements Fixed-Pivot sampling strategy.

    This sampler creates a strategic sample that demonstrates the
    dimension structure of a dataset, helping downstream LLMs
    understand how to generate correct PVMAPs.
    """

    # Default configuration
    DEFAULT_CONFIG = {
        # Target sample size
        'target_rows': 80,

        # Allocation ratios (Fixed-Pivot strategy)
        'diagonal_scan_ratio': 0.25,      # 20 rows
        'fixed_pivot_ratio': 0.50,        # 40 rows
        'edge_cases_ratio': 0.25,         # 20 rows

        # Total/aggregate detection keywords
        'total_keywords': ['total', 'all', 'overall', 'aggregate', 'combined',
                          'national', 'entire', 'grand', 'whole', 'sum'],

        # Null/missing detection
        'null_values': ['', 'null', 'na', 'n/a', 'none', '.', '-', 'nan', 'missing'],

        # Maximum dimensions to track (prevents cartesian explosion)
        'max_dimensions': 5,

        # Fixed-pivot: max rows per pivot block
        'max_pivot_block_size': 15,
    }

    def __init__(self, config: Dict = None):
        """Initialize the SkeletonSampler.

        Args:
            config: Optional configuration dictionary
        """
        self._config = {**self.DEFAULT_CONFIG, **(config or {})}

    def sample(self, df, dimension_columns: List[str],
               dimension_domains: Dict[str, List[str]] = None,
               target_rows: int = None) -> SkeletonSampleResult:
        """Generate skeleton sample preserving dimension structure.

        Args:
            df: pandas DataFrame to sample from
            dimension_columns: List of dimension column names
            dimension_domains: Optional dict of dimension -> unique values
            target_rows: Target number of rows (default from config)

        Returns:
            SkeletonSampleResult with sampled data
        """
        if pd is None:
            raise ImportError("pandas is required for SkeletonSampler")

        if df is None or len(df) == 0:
            return SkeletonSampleResult()

        target = target_rows or self._config['target_rows']
        result = SkeletonSampleResult(total_rows=len(df))

        # Limit dimensions to prevent explosion
        dims = dimension_columns[:self._config['max_dimensions']]
        if not dims:
            # No dimensions, just random sample
            result.sampled_indices = list(df.sample(min(target, len(df))).index)
            result.sampled_rows = df.loc[result.sampled_indices].to_dict('records')
            return result

        # Build dimension domains if not provided
        if dimension_domains is None:
            dimension_domains = {}
        for dim in dims:
            if dim not in dimension_domains and dim in df.columns:
                dimension_domains[dim] = df[dim].dropna().unique().tolist()

        # Track selected indices
        selected = set()

        # Calculate allocation
        diagonal_target = int(target * self._config['diagonal_scan_ratio'])
        pivot_target = int(target * self._config['fixed_pivot_ratio'])
        edge_target = int(target * self._config['edge_cases_ratio'])

        # Phase 1: Diagonal Scan
        diagonal_indices = self._diagonal_scan(df, dims, dimension_domains, diagonal_target, selected)
        selected.update(diagonal_indices)
        result.diagonal_scan_count = len(diagonal_indices)

        # Phase 2: Fixed-Pivot Blocks
        pivot_indices = self._fixed_pivot_blocks(df, dims, dimension_domains, pivot_target, selected)
        selected.update(pivot_indices)
        result.fixed_pivot_count = len(pivot_indices)

        # Phase 3: Edge Cases
        edge_indices = self._edge_cases(df, dims, edge_target, selected)
        selected.update(edge_indices)
        result.edge_case_count = len(edge_indices)

        # Compile results
        result.sampled_indices = list(selected)
        result.sampled_rows = df.loc[result.sampled_indices].to_dict('records')

        # Calculate coverage
        result.dimension_value_coverage = self._calculate_value_coverage(
            df.loc[result.sampled_indices], dims, dimension_domains
        )
        result.combination_coverage = self._calculate_combination_coverage(
            df.loc[result.sampled_indices], dims, dimension_domains
        )

        logging.info(
            f'Skeleton sample: {len(selected)} rows '
            f'(diagonal={result.diagonal_scan_count}, '
            f'pivot={result.fixed_pivot_count}, '
            f'edge={result.edge_case_count})'
        )

        return result

    def _diagonal_scan(self, df, dimensions: List[str],
                       domains: Dict[str, List[str]],
                       target: int, exclude: Set[int]) -> List[int]:
        """Select rows to maximize dimension value coverage.

        Goal: Ensure all unique values across all dimensions appear at least once.

        Args:
            df: DataFrame
            dimensions: Dimension column names
            domains: Dimension value domains
            target: Target number of rows
            exclude: Indices to exclude

        Returns:
            List of selected indices
        """
        selected = []
        uncovered = {dim: set(domains.get(dim, [])) for dim in dimensions}

        # Greedy selection: pick rows that cover the most uncovered values
        available = [i for i in df.index if i not in exclude]
        random.shuffle(available)

        for idx in available:
            if len(selected) >= target:
                break

            # Count how many uncovered values this row covers
            coverage_score = 0
            for dim in dimensions:
                if dim in df.columns:
                    val = str(df.loc[idx, dim]).strip()
                    if val in uncovered[dim]:
                        coverage_score += 1

            if coverage_score > 0:
                selected.append(idx)
                # Mark values as covered
                for dim in dimensions:
                    if dim in df.columns:
                        val = str(df.loc[idx, dim]).strip()
                        uncovered[dim].discard(val)

        # If we haven't reached target and still have uncovered values, continue
        while len(selected) < target and any(uncovered.values()):
            # Find rows with uncovered values
            for idx in available:
                if idx in selected or idx in exclude:
                    continue

                for dim in dimensions:
                    if dim in df.columns:
                        val = str(df.loc[idx, dim]).strip()
                        if val in uncovered[dim]:
                            selected.append(idx)
                            for d in dimensions:
                                if d in df.columns:
                                    v = str(df.loc[idx, d]).strip()
                                    uncovered[d].discard(v)
                            break

                if len(selected) >= target:
                    break

            break  # Exit if no progress

        return selected

    def _fixed_pivot_blocks(self, df, dimensions: List[str],
                             domains: Dict[str, List[str]],
                             target: int, exclude: Set[int]) -> List[int]:
        """Create pivot blocks varying one dimension at a time.

        This helps the LLM see that dimensions are independent.
        For each dimension, we fix all others and vary just that one.

        Args:
            df: DataFrame
            dimensions: Dimension column names
            domains: Dimension value domains
            target: Target number of rows
            exclude: Indices to exclude

        Returns:
            List of selected indices
        """
        selected = []
        per_dim_target = target // max(1, len(dimensions))
        block_size = min(per_dim_target, self._config['max_pivot_block_size'])

        for pivot_dim in dimensions:
            if len(selected) >= target:
                break

            # Get pivot values
            pivot_values = domains.get(pivot_dim, [])
            if not pivot_values:
                continue

            # Find a "fixed" set of values for other dimensions
            fixed_values = self._find_common_fixed_values(df, dimensions, pivot_dim, exclude)

            # Select rows varying only the pivot dimension
            block_indices = self._select_pivot_block(
                df, pivot_dim, pivot_values, dimensions, fixed_values,
                block_size, exclude | set(selected)
            )

            selected.extend(block_indices)

        return selected[:target]

    def _find_common_fixed_values(self, df, dimensions: List[str],
                                   pivot_dim: str, exclude: Set[int]) -> Dict[str, str]:
        """Find the most common value combination for non-pivot dimensions.

        Args:
            df: DataFrame
            dimensions: All dimension columns
            pivot_dim: The dimension being varied
            exclude: Indices to exclude

        Returns:
            Dictionary of {dimension: fixed_value}
        """
        fixed_dims = [d for d in dimensions if d != pivot_dim and d in df.columns]

        if not fixed_dims:
            return {}

        # Find most common combination
        available_df = df.drop(index=list(exclude), errors='ignore')
        if len(available_df) == 0:
            available_df = df

        # Count combinations
        combo_counts = defaultdict(int)
        for _, row in available_df.iterrows():
            combo = tuple(str(row.get(d, '')).strip() for d in fixed_dims)
            combo_counts[combo] += 1

        if not combo_counts:
            return {}

        # Get most common
        most_common = max(combo_counts.items(), key=lambda x: x[1])[0]

        return {d: v for d, v in zip(fixed_dims, most_common)}

    def _select_pivot_block(self, df, pivot_dim: str, pivot_values: List,
                             dimensions: List[str], fixed_values: Dict[str, str],
                             block_size: int, exclude: Set[int]) -> List[int]:
        """Select rows for a fixed-pivot block.

        Args:
            df: DataFrame
            pivot_dim: Dimension being varied
            pivot_values: Values to vary over
            dimensions: All dimension columns
            fixed_values: Fixed values for other dimensions
            block_size: Max rows for this block
            exclude: Indices to exclude

        Returns:
            List of selected indices
        """
        selected = []
        covered_pivot = set()

        for idx in df.index:
            if idx in exclude:
                continue
            if len(selected) >= block_size:
                break

            # Check if this row matches fixed values
            matches_fixed = True
            for dim, val in fixed_values.items():
                if dim in df.columns:
                    row_val = str(df.loc[idx, dim]).strip()
                    if row_val != val:
                        matches_fixed = False
                        break

            if not matches_fixed:
                continue

            # Get pivot value
            if pivot_dim in df.columns:
                pivot_val = str(df.loc[idx, pivot_dim]).strip()
                if pivot_val not in covered_pivot:
                    selected.append(idx)
                    covered_pivot.add(pivot_val)

        return selected

    def _edge_cases(self, df, dimensions: List[str],
                    target: int, exclude: Set[int]) -> List[int]:
        """Select total rows, nulls, and formatting edge cases.

        Args:
            df: DataFrame
            dimensions: Dimension columns
            target: Target number of rows
            exclude: Indices to exclude

        Returns:
            List of selected indices
        """
        selected = []
        total_kw = [kw.lower() for kw in self._config['total_keywords']]
        null_vals = [v.lower() for v in self._config['null_values']]

        # Split target: 40% totals, 30% nulls, 30% edge formatting
        totals_target = int(target * 0.4)
        nulls_target = int(target * 0.3)
        format_target = target - totals_target - nulls_target

        # 1. Find total/aggregate rows
        total_indices = []
        for idx in df.index:
            if idx in exclude:
                continue

            for dim in dimensions:
                if dim in df.columns:
                    val = str(df.loc[idx, dim]).lower().strip()
                    if any(kw in val for kw in total_kw):
                        total_indices.append(idx)
                        break

        selected.extend(total_indices[:totals_target])

        # 2. Find rows with null/missing values
        null_indices = []
        for idx in df.index:
            if idx in exclude or idx in selected:
                continue

            for dim in dimensions:
                if dim in df.columns:
                    val = str(df.loc[idx, dim]).lower().strip()
                    if val in null_vals or pd.isna(df.loc[idx, dim]):
                        null_indices.append(idx)
                        break

        selected.extend(null_indices[:nulls_target])

        # 3. Find rows with formatting edge cases (special chars, punctuation)
        format_indices = []
        for idx in df.index:
            if idx in exclude or idx in selected:
                continue

            for dim in dimensions:
                if dim in df.columns:
                    val = str(df.loc[idx, dim]).strip()
                    # Look for special characters
                    if any(c in val for c in [',', '.', '(', ')', '-', '/', '"', "'"]):
                        format_indices.append(idx)
                        break

        selected.extend(format_indices[:format_target])

        # Fill remaining with random if needed
        remaining = target - len(selected)
        if remaining > 0:
            available = [i for i in df.index if i not in exclude and i not in selected]
            if available:
                extra = random.sample(available, min(remaining, len(available)))
                selected.extend(extra)

        return selected[:target]

    def _calculate_value_coverage(self, sample_df, dimensions: List[str],
                                    domains: Dict[str, List[str]]) -> Dict[str, float]:
        """Calculate per-dimension value coverage.

        Args:
            sample_df: Sampled DataFrame
            dimensions: Dimension columns
            domains: Dimension value domains

        Returns:
            Dictionary of dimension -> coverage percentage
        """
        coverage = {}

        for dim in dimensions:
            if dim not in sample_df.columns:
                coverage[dim] = 0.0
                continue

            domain_values = set(str(v) for v in domains.get(dim, []))
            sample_values = set(str(v).strip() for v in sample_df[dim].dropna())

            if domain_values:
                covered = len(sample_values & domain_values)
                coverage[dim] = (covered / len(domain_values)) * 100
            else:
                coverage[dim] = 100.0

        return coverage

    def _calculate_combination_coverage(self, sample_df, dimensions: List[str],
                                          domains: Dict[str, List[str]]) -> float:
        """Calculate overall combination coverage.

        Args:
            sample_df: Sampled DataFrame
            dimensions: Dimension columns
            domains: Dimension value domains

        Returns:
            Coverage percentage
        """
        if not dimensions or sample_df.empty:
            return 0.0

        # Calculate total possible combinations
        total = 1
        for dim in dimensions:
            n_values = len(domains.get(dim, []))
            if n_values > 0:
                total *= n_values

        if total == 0:
            return 100.0

        # Count unique combinations in sample
        valid_dims = [d for d in dimensions if d in sample_df.columns]
        if not valid_dims:
            return 0.0

        sample_combos = set()
        for _, row in sample_df.iterrows():
            combo = tuple(str(row.get(d, '')).strip() for d in valid_dims)
            sample_combos.add(combo)

        # Cap at 100%
        coverage = min(100.0, (len(sample_combos) / total) * 100)
        return coverage


def sample_skeleton(df, dimension_columns: List[str],
                    dimension_domains: Dict[str, List[str]] = None,
                    target_rows: int = 80,
                    config: Dict = None) -> SkeletonSampleResult:
    """Convenience function to create skeleton sample.

    Args:
        df: pandas DataFrame
        dimension_columns: Dimension column names
        dimension_domains: Optional dimension value domains
        target_rows: Target sample size
        config: Optional configuration

    Returns:
        SkeletonSampleResult
    """
    sampler = SkeletonSampler(config)
    return sampler.sample(df, dimension_columns, dimension_domains, target_rows)
