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
"""Combination tracker for dimension coverage analysis.

This module provides the CombinationTracker class that tracks coverage
of dimension value combinations during sampling. It helps ensure that
the sample represents the full cartesian product of dimensions.

Key features:
- Track seen dimension combinations
- Calculate coverage statistics
- Identify missing combinations
- Support for efficient set operations
"""

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Any, Optional
import itertools

from absl import logging


@dataclass
class CoverageStats:
    """Statistics about dimension combination coverage."""

    # Core counts
    total_combinations: int = 0
    seen_combinations: int = 0
    missing_combinations: int = 0

    # Coverage ratio
    coverage_percent: float = 0.0

    # Per-dimension stats
    dimension_coverage: Dict[str, Dict[str, int]] = field(default_factory=dict)

    # Most/least common combinations
    most_common: List[Tuple[Tuple, int]] = field(default_factory=list)
    least_common: List[Tuple[Tuple, int]] = field(default_factory=list)


class CombinationTracker:
    """Tracks coverage of dimension combinations.

    This class monitors which combinations of dimension values have been
    seen in the sample, enabling strategic selection of rows that maximize
    combination coverage.
    """

    def __init__(self, dimension_columns: List[str], dimension_domains: Dict[str, List[str]] = None):
        """Initialize the CombinationTracker.

        Args:
            dimension_columns: List of dimension column names
            dimension_domains: Optional dict mapping dimension name to list of possible values
        """
        self.dimension_columns = list(dimension_columns)
        self.dimension_domains = dimension_domains or {}

        # Core tracking state
        self._seen_combinations: Set[Tuple] = set()
        self._combination_counts: Counter = Counter()

        # Per-dimension value tracking
        self._dimension_value_counts: Dict[str, Counter] = {
            dim: Counter() for dim in dimension_columns
        }

        # Precompute full cartesian if domains provided
        self._full_cartesian: Optional[Set[Tuple]] = None
        if dimension_domains and all(dim in dimension_domains for dim in dimension_columns):
            self._full_cartesian = self._compute_cartesian(dimension_domains)

    def _compute_cartesian(self, domains: Dict[str, List[str]]) -> Set[Tuple]:
        """Compute full cartesian product of dimension domains.

        Args:
            domains: Dictionary mapping dimension to possible values

        Returns:
            Set of all possible value tuples
        """
        if not domains or not self.dimension_columns:
            return set()

        # Get values in column order
        ordered_values = []
        for col in self.dimension_columns:
            if col in domains and domains[col]:
                ordered_values.append(domains[col])
            else:
                return set()  # Missing domain, can't compute

        # Compute cartesian product
        if not ordered_values:
            return set()

        # Limit to prevent memory issues
        total_size = 1
        for vals in ordered_values:
            total_size *= len(vals)
            if total_size > 1000000:  # Cap at 1M combinations
                logging.warning(
                    f'Cartesian product too large ({total_size}), '
                    f'skipping full computation'
                )
                return set()

        return set(itertools.product(*ordered_values))

    def add_row(self, row: Dict[str, Any]) -> bool:
        """Add a row and return True if it's a new combination.

        Args:
            row: Dictionary mapping column name to value

        Returns:
            True if this combination was not seen before
        """
        combo = self._extract_combination(row)
        if not combo:
            return False

        is_new = combo not in self._seen_combinations

        # Track combination
        self._seen_combinations.add(combo)
        self._combination_counts[combo] += 1

        # Track per-dimension values
        for i, dim in enumerate(self.dimension_columns):
            if i < len(combo):
                self._dimension_value_counts[dim][combo[i]] += 1

        return is_new

    def add_row_from_list(self, row: List[str], headers: List[str]) -> bool:
        """Add a row from list format and return True if new combination.

        Args:
            row: List of values
            headers: List of column headers

        Returns:
            True if this combination was not seen before
        """
        # Convert to dict
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(row):
                row_dict[header] = row[i]

        return self.add_row(row_dict)

    def _extract_combination(self, row: Dict[str, Any]) -> Optional[Tuple]:
        """Extract dimension combination tuple from row.

        Args:
            row: Dictionary mapping column name to value

        Returns:
            Tuple of dimension values, or None if missing dimensions
        """
        values = []
        for dim in self.dimension_columns:
            if dim not in row:
                return None
            values.append(str(row[dim]).strip())

        return tuple(values)

    def has_combination(self, combination: Tuple) -> bool:
        """Check if a combination has been seen.

        Args:
            combination: Tuple of dimension values

        Returns:
            True if combination has been seen
        """
        return combination in self._seen_combinations

    def get_combination_count(self, combination: Tuple) -> int:
        """Get how many times a combination has been seen.

        Args:
            combination: Tuple of dimension values

        Returns:
            Count of times this combination was added
        """
        return self._combination_counts.get(combination, 0)

    def get_coverage_stats(self) -> CoverageStats:
        """Return coverage statistics.

        Returns:
            CoverageStats with full analysis
        """
        stats = CoverageStats()

        # Basic counts
        stats.seen_combinations = len(self._seen_combinations)

        if self._full_cartesian:
            stats.total_combinations = len(self._full_cartesian)
            stats.missing_combinations = stats.total_combinations - stats.seen_combinations
        else:
            # Estimate total from seen values
            stats.total_combinations = self._estimate_total_combinations()
            stats.missing_combinations = max(0, stats.total_combinations - stats.seen_combinations)

        # Coverage percent
        if stats.total_combinations > 0:
            stats.coverage_percent = (stats.seen_combinations / stats.total_combinations) * 100
        else:
            stats.coverage_percent = 100.0 if stats.seen_combinations > 0 else 0.0

        # Per-dimension coverage
        for dim in self.dimension_columns:
            domain = self.dimension_domains.get(dim, [])
            value_counts = self._dimension_value_counts.get(dim, Counter())

            stats.dimension_coverage[dim] = {
                'total_values': len(domain) if domain else len(value_counts),
                'seen_values': len(value_counts),
                'counts': dict(value_counts),
            }

        # Most/least common combinations
        stats.most_common = self._combination_counts.most_common(5)
        stats.least_common = self._combination_counts.most_common()[:-6:-1] if len(self._combination_counts) > 5 else []

        return stats

    def _estimate_total_combinations(self) -> int:
        """Estimate total combinations from observed values.

        Returns:
            Estimated total combinations
        """
        if not self._dimension_value_counts:
            return 0

        total = 1
        for dim, counts in self._dimension_value_counts.items():
            n_values = len(counts)
            if n_values > 0:
                total *= n_values

        return total

    def get_missing_combinations(self) -> Set[Tuple]:
        """Return combinations not yet seen.

        Returns:
            Set of unseen combinations (only if full cartesian was computed)
        """
        if self._full_cartesian is None:
            return set()

        return self._full_cartesian - self._seen_combinations

    def get_uncovered_values(self, dimension: str) -> Set[str]:
        """Get values for a dimension that haven't been seen yet.

        Args:
            dimension: Dimension column name

        Returns:
            Set of uncovered values
        """
        if dimension not in self.dimension_domains:
            return set()

        all_values = set(self.dimension_domains[dimension])
        seen_values = set(self._dimension_value_counts.get(dimension, {}).keys())

        return all_values - seen_values

    def covers_new_combination(self, row: Dict[str, Any]) -> bool:
        """Check if a row would cover a new combination without adding it.

        Args:
            row: Dictionary mapping column name to value

        Returns:
            True if this row represents a new combination
        """
        combo = self._extract_combination(row)
        if not combo:
            return False
        return combo not in self._seen_combinations

    def covers_new_combination_from_list(self, row: List[str], headers: List[str]) -> bool:
        """Check if a row (list format) would cover a new combination.

        Args:
            row: List of values
            headers: List of column headers

        Returns:
            True if this row represents a new combination
        """
        row_dict = {}
        for i, header in enumerate(headers):
            if i < len(row):
                row_dict[header] = row[i]
        return self.covers_new_combination(row_dict)

    def get_coverage_priority(self, row: Dict[str, Any]) -> int:
        """Calculate coverage priority for a row.

        Higher priority = row covers more uncovered dimension values.

        Args:
            row: Dictionary mapping column name to value

        Returns:
            Priority score (higher = more valuable)
        """
        priority = 0

        for dim in self.dimension_columns:
            if dim not in row:
                continue

            value = str(row[dim]).strip()

            # Check if this value is under-represented
            count = self._dimension_value_counts.get(dim, Counter()).get(value, 0)
            if count == 0:
                priority += 10  # High priority for unseen value
            elif count == 1:
                priority += 3   # Medium priority for rare value
            elif count < 5:
                priority += 1   # Low priority for uncommon value

        # Bonus for completely new combination
        if self.covers_new_combination(row):
            priority += 20

        return priority

    def reset(self) -> None:
        """Reset all tracking state."""
        self._seen_combinations.clear()
        self._combination_counts.clear()
        for dim in self.dimension_columns:
            self._dimension_value_counts[dim] = Counter()

    def get_seen_combinations(self) -> Set[Tuple]:
        """Return all seen combinations.

        Returns:
            Set of seen combination tuples
        """
        return self._seen_combinations.copy()

    def __len__(self) -> int:
        """Return number of unique combinations seen."""
        return len(self._seen_combinations)


def create_combination_tracker(dimension_columns: List[str],
                                 dimension_domains: Dict[str, List[str]] = None) -> CombinationTracker:
    """Factory function to create a CombinationTracker.

    Args:
        dimension_columns: List of dimension column names
        dimension_domains: Optional dict of dimension -> possible values

    Returns:
        Configured CombinationTracker
    """
    return CombinationTracker(dimension_columns, dimension_domains)
