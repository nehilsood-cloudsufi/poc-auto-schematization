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
"""Column analysis module for intelligent data sampling.

This module provides functionality to analyze CSV columns and classify them
to improve sampling decisions. It detects:
- Constant columns (single or very few unique values)
- Derived columns (percentages, sums calculated from other columns)
- Redundant column pairs (1:1 mappings like FIPS code <-> county name)
- Metadata columns (long text with low information value for sampling)
"""

from dataclasses import dataclass, field
from typing import Optional
import re

from absl import logging


@dataclass
class ColumnAnalysisResult:
    """Results of column analysis for a dataset."""

    # Column indices that should be skipped for sampling decisions
    constant_columns: set = field(default_factory=set)
    derived_columns: set = field(default_factory=set)
    metadata_columns: set = field(default_factory=set)

    # Pairs of redundant columns (index_a, index_b) - second should be skipped
    redundant_pairs: list = field(default_factory=list)

    # Column classifications for reporting
    column_types: dict = field(default_factory=dict)

    # Numeric columns with their detected ranges
    numeric_columns: dict = field(default_factory=dict)

    def get_skip_columns(self) -> set:
        """Returns all column indices that should be skipped."""
        skip = self.constant_columns | self.derived_columns | self.metadata_columns
        # Add second column of each redundant pair
        for _, col_b in self.redundant_pairs:
            skip.add(col_b)
        return skip


class ColumnAnalyzer:
    """Analyzes columns to identify which are useful for sampling decisions.

    This class examines the data to classify columns and detect relationships
    that can help the sampler make better row selection decisions.
    """

    def __init__(self, config: dict = None):
        """Initialize the column analyzer.

        Args:
            config: Optional configuration dictionary with thresholds:
                - constant_threshold: Ratio below which column is constant (default 0.01)
                - correlation_threshold: Ratio for redundant pair detection (default 0.95)
                - metadata_min_length: Min avg length for metadata detection (default 50)
                - derived_tolerance: Tolerance for derived column math checks (default 0.01)
        """
        self._config = config or {}
        self._constant_threshold = self._config.get('constant_threshold', 0.01)
        self._correlation_threshold = self._config.get('correlation_threshold', 0.95)
        self._metadata_min_length = self._config.get('metadata_min_length', 50)
        self._derived_tolerance = self._config.get('derived_tolerance', 0.01)

        # Internal state during analysis
        self._rows = []
        self._headers = []
        self._num_rows = 0
        self._num_cols = 0
        self._column_values = {}  # col_index -> list of values
        self._column_unique = {}  # col_index -> set of unique values
        self._column_numeric = {}  # col_index -> list of numeric values (or None)

    def analyze(self, rows: list, headers: list) -> ColumnAnalysisResult:
        """Analyze columns and return classification results.

        Args:
            rows: List of data rows (each row is a list of string values)
            headers: List of column header names

        Returns:
            ColumnAnalysisResult with column classifications
        """
        if not rows:
            return ColumnAnalysisResult()

        self._rows = rows
        self._headers = headers
        self._num_rows = len(rows)
        self._num_cols = len(headers) if headers else (len(rows[0]) if rows else 0)

        # Build column value collections
        self._collect_column_values()

        # Run detection algorithms
        result = ColumnAnalysisResult()
        result.constant_columns = self._detect_constant_columns()
        result.metadata_columns = self._detect_metadata_columns()
        result.redundant_pairs = self._detect_redundant_pairs()
        result.derived_columns = self._detect_derived_columns()
        result.numeric_columns = self._get_numeric_column_ranges()

        # Build column type classification
        result.column_types = self._classify_columns(result)

        logging.info(
            f'Column analysis complete: {len(result.constant_columns)} constant, '
            f'{len(result.derived_columns)} derived, '
            f'{len(result.metadata_columns)} metadata, '
            f'{len(result.redundant_pairs)} redundant pairs'
        )

        return result

    def _collect_column_values(self) -> None:
        """Collect values for each column from all rows."""
        self._column_values = {i: [] for i in range(self._num_cols)}
        self._column_unique = {i: set() for i in range(self._num_cols)}
        self._column_numeric = {i: [] for i in range(self._num_cols)}

        for row in self._rows:
            for col_idx in range(min(len(row), self._num_cols)):
                val = row[col_idx]
                self._column_values[col_idx].append(val)
                self._column_unique[col_idx].add(val)

                # Try to parse as numeric
                numeric_val = self._parse_numeric(val)
                if numeric_val is not None:
                    self._column_numeric[col_idx].append(numeric_val)
                else:
                    # Mark column as non-numeric if any value fails
                    if self._column_numeric[col_idx] is not None:
                        # Check if most values are numeric - allow some missing
                        pass  # We'll handle this in post-processing

        # Post-process numeric columns - require >80% numeric values
        for col_idx in range(self._num_cols):
            numeric_count = len(self._column_numeric[col_idx])
            if numeric_count < self._num_rows * 0.8:
                self._column_numeric[col_idx] = None

    def _parse_numeric(self, val: str) -> Optional[float]:
        """Try to parse a string value as numeric."""
        if not val or val.strip() == '' or val == '.':
            return None
        try:
            # Remove common formatting
            clean = val.strip().replace(',', '').replace('%', '').replace('$', '')
            return float(clean)
        except (ValueError, TypeError):
            return None

    def _detect_constant_columns(self) -> set:
        """Detect columns with very few unique values (nearly constant) or empty columns.

        Returns:
            Set of column indices that are constant, near-constant, or empty.
        """
        constant_cols = set()

        for col_idx in range(self._num_cols):
            header = self._headers[col_idx] if col_idx < len(self._headers) else f'col_{col_idx}'

            # Check for empty header
            if not header or not header.strip():
                constant_cols.add(col_idx)
                logging.debug(f'Empty header detected at column {col_idx}')
                continue

            unique_count = len(self._column_unique[col_idx])
            unique_ratio = unique_count / self._num_rows if self._num_rows > 0 else 1.0

            # Count empty values in column
            empty_count = sum(1 for val in self._column_values[col_idx] if not val or not val.strip())
            empty_ratio = empty_count / self._num_rows if self._num_rows > 0 else 0

            # Column is constant/empty if:
            # - Has very few unique values
            # - Has only 1 unique value
            # - Has >95% empty values
            if unique_ratio <= self._constant_threshold or unique_count <= 1 or empty_ratio > 0.95:
                constant_cols.add(col_idx)
                if empty_ratio > 0.95:
                    logging.debug(
                        f'Empty column detected: "{header}" '
                        f'({empty_count}/{self._num_rows} empty = {empty_ratio:.1%})')
                else:
                    logging.debug(
                        f'Constant column detected: "{header}" '
                        f'({unique_count} unique / {self._num_rows} rows = {unique_ratio:.2%})'
                    )

        return constant_cols

    def _detect_metadata_columns(self) -> set:
        """Detect columns with long text that are metadata, not data.

        Returns:
            Set of column indices that appear to be metadata.
        """
        metadata_cols = set()

        for col_idx in range(self._num_cols):
            values = self._column_values[col_idx]
            if not values:
                continue

            # Calculate average length
            total_len = sum(len(str(v)) for v in values)
            avg_len = total_len / len(values)

            # Check if long text AND mostly unique (not categorical)
            unique_ratio = len(self._column_unique[col_idx]) / self._num_rows if self._num_rows > 0 else 0

            if avg_len >= self._metadata_min_length and unique_ratio > 0.9:
                metadata_cols.add(col_idx)
                header = self._headers[col_idx] if col_idx < len(self._headers) else f'col_{col_idx}'
                logging.debug(
                    f'Metadata column detected: "{header}" '
                    f'(avg length {avg_len:.1f}, {unique_ratio:.1%} unique)'
                )

        return metadata_cols

    def _detect_redundant_pairs(self) -> list:
        """Detect pairs of columns that have 1:1 mapping (redundant).

        Returns:
            List of tuples (col_a, col_b) where col_b is redundant with col_a.
        """
        redundant_pairs = []
        checked = set()

        for col_a in range(self._num_cols):
            unique_a = self._column_unique[col_a]
            if len(unique_a) <= 1:
                continue  # Skip constant columns

            for col_b in range(col_a + 1, self._num_cols):
                if (col_a, col_b) in checked:
                    continue
                checked.add((col_a, col_b))

                unique_b = self._column_unique[col_b]

                # Quick check: must have same number of unique values
                if len(unique_a) != len(unique_b):
                    continue

                # Check for 1:1 mapping
                if self._check_one_to_one_mapping(col_a, col_b):
                    redundant_pairs.append((col_a, col_b))
                    header_a = self._headers[col_a] if col_a < len(self._headers) else f'col_{col_a}'
                    header_b = self._headers[col_b] if col_b < len(self._headers) else f'col_{col_b}'
                    logging.debug(
                        f'Redundant pair detected: "{header_a}" <-> "{header_b}"'
                    )

        return redundant_pairs

    def _check_one_to_one_mapping(self, col_a: int, col_b: int) -> bool:
        """Check if two columns have a 1:1 mapping relationship."""
        mapping_a_to_b = {}
        mapping_b_to_a = {}

        for row in self._rows:
            if col_a >= len(row) or col_b >= len(row):
                continue

            val_a = row[col_a]
            val_b = row[col_b]

            # Check A -> B mapping
            if val_a in mapping_a_to_b:
                if mapping_a_to_b[val_a] != val_b:
                    return False  # Not 1:1
            else:
                mapping_a_to_b[val_a] = val_b

            # Check B -> A mapping
            if val_b in mapping_b_to_a:
                if mapping_b_to_a[val_b] != val_a:
                    return False  # Not 1:1
            else:
                mapping_b_to_a[val_b] = val_a

        return True

    def _detect_derived_columns(self) -> set:
        """Detect columns that are derived/calculated from other columns.

        Detects:
        - Percentage columns (col_b = col_a / total * 100)
        - Sum columns (col_c = col_a + col_b)
        - Common prefixed patterns (E_*, EP_*, M_*, EPL_*, F_*)

        Returns:
            Set of column indices that appear to be derived.
        """
        derived_cols = set()

        # Pattern-based detection for common naming conventions
        derived_cols.update(self._detect_derived_by_pattern())

        # Math-based detection for percentage columns
        derived_cols.update(self._detect_percentage_columns())

        return derived_cols

    def _detect_derived_by_pattern(self) -> set:
        """Detect derived columns by header naming patterns."""
        derived = set()

        # Common derived column patterns
        derived_patterns = [
            # Percentage versions of count columns
            (r'^EP_', r'^E_'),      # EP_ is percentage of E_
            (r'^MP_', r'^M_'),      # MP_ is percentage of M_
            # Rank/percentile columns
            (r'^EPL_', r'^EP_'),    # EPL_ is percentile of EP_
            (r'^RPL_', None),       # RPL_ columns are derived ranks
            (r'^SPL_', None),       # SPL_ columns are derived sums
            # Flag columns
            (r'^F_', r'^E_'),       # F_ flags are derived from E_
            # Common suffixes
            (r'_pct$', None),       # Percentage suffix
            (r'_percent$', None),
            (r'_rate$', None),
            (r'_moe$', None),       # Margin of error
            (r'_MOE$', None),
        ]

        for col_idx, header in enumerate(self._headers):
            for pattern, base_pattern in derived_patterns:
                if re.search(pattern, header, re.IGNORECASE):
                    # If there's a base pattern, check if base column exists
                    if base_pattern:
                        base_name = re.sub(pattern, base_pattern.replace('^', '').replace('_', '_'), header)
                        if base_name in self._headers:
                            derived.add(col_idx)
                            logging.debug(f'Derived column by pattern: "{header}" (from "{base_name}")')
                            break
                    else:
                        derived.add(col_idx)
                        logging.debug(f'Derived column by pattern: "{header}"')
                        break

        return derived

    def _detect_percentage_columns(self) -> set:
        """Detect columns that are percentages of other columns."""
        derived = set()

        # Find numeric column pairs where one might be percentage of another
        numeric_cols = [i for i in range(self._num_cols) if self._column_numeric[i] is not None]

        for col_pct in numeric_cols:
            pct_values = self._column_numeric[col_pct]
            if not pct_values:
                continue

            # Skip if values don't look like percentages (0-100 range)
            max_val = max(pct_values) if pct_values else 0
            min_val = min(pct_values) if pct_values else 0
            if max_val > 100 or min_val < 0:
                continue

            # Check if this could be percentage of another column
            for col_base in numeric_cols:
                if col_base == col_pct:
                    continue

                base_values = self._column_numeric[col_base]
                if not base_values or len(base_values) != len(pct_values):
                    continue

                # Check if col_pct ≈ col_base / total * 100 for some total
                # This is expensive, so we use sampling
                if self._check_percentage_relationship(pct_values, base_values):
                    derived.add(col_pct)
                    header = self._headers[col_pct] if col_pct < len(self._headers) else f'col_{col_pct}'
                    base_header = self._headers[col_base] if col_base < len(self._headers) else f'col_{col_base}'
                    logging.debug(f'Percentage column detected: "{header}" (from "{base_header}")')
                    break

        return derived

    def _check_percentage_relationship(self, pct_values: list, base_values: list) -> bool:
        """Check if pct_values are percentages derived from base_values."""
        # Sample a few rows to check
        sample_size = min(10, len(pct_values))
        sample_indices = list(range(0, len(pct_values), max(1, len(pct_values) // sample_size)))[:sample_size]

        # Try to find a consistent total
        totals = []
        for idx in sample_indices:
            if pct_values[idx] > 0:
                implied_total = base_values[idx] / (pct_values[idx] / 100)
                totals.append(implied_total)

        if not totals:
            return False

        # Check if totals are consistent (same value)
        avg_total = sum(totals) / len(totals)
        if avg_total == 0:
            return False

        for total in totals:
            if abs(total - avg_total) / avg_total > self._derived_tolerance:
                return False

        return True

    def _get_numeric_column_ranges(self) -> dict:
        """Get min/max ranges for numeric columns.

        Returns:
            Dictionary mapping column index to (min, max, quartiles) tuple.
        """
        ranges = {}

        for col_idx in range(self._num_cols):
            values = self._column_numeric[col_idx]
            if values and len(values) > 0:
                sorted_vals = sorted(values)
                n = len(sorted_vals)
                ranges[col_idx] = {
                    'min': sorted_vals[0],
                    'max': sorted_vals[-1],
                    'q1': sorted_vals[n // 4] if n >= 4 else sorted_vals[0],
                    'median': sorted_vals[n // 2],
                    'q3': sorted_vals[3 * n // 4] if n >= 4 else sorted_vals[-1],
                }

        return ranges

    def _classify_columns(self, result: ColumnAnalysisResult) -> dict:
        """Classify all columns by type for reporting.

        Returns:
            Dictionary mapping column index to type string.
        """
        types = {}

        for col_idx in range(self._num_cols):
            if col_idx in result.constant_columns:
                types[col_idx] = 'constant'
            elif col_idx in result.derived_columns:
                types[col_idx] = 'derived'
            elif col_idx in result.metadata_columns:
                types[col_idx] = 'metadata'
            elif any(col_idx == pair[1] for pair in result.redundant_pairs):
                types[col_idx] = 'redundant'
            elif self._column_numeric[col_idx] is not None:
                types[col_idx] = 'numeric'
            else:
                # Check if categorical (low unique ratio)
                unique_ratio = len(self._column_unique[col_idx]) / self._num_rows if self._num_rows > 0 else 1
                if unique_ratio < 0.1:
                    types[col_idx] = 'categorical'
                else:
                    types[col_idx] = 'text'

        return types
