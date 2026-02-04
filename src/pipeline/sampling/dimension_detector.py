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
"""Dimension detector module for identifying dimension columns.

This module provides the DimensionDetector class that applies multiple
heuristics to classify columns in a dataset:

1. Cardinality Test: Low unique ratio indicates dimension
2. Semantic Test: Keyword matching for known dimension types
3. Summation Test: Check if grouping + summing makes sense

Column roles:
- place: Geographic identifier (State, FIPS, Country)
- time: Temporal identifier (Year, Date, Quarter)
- dimension: Categorical constraint (Gender, Age, Sector)
- value: Measurement column (Population, Amount, Rate)
- metadata: Context column (Source, Unit, Notes)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any
import re

from absl import logging


@dataclass
class DimensionDetectionResult:
    """Results from dimension detection analysis."""

    # Column classifications
    place_columns: List[str] = field(default_factory=list)
    time_columns: List[str] = field(default_factory=list)
    dimension_columns: List[str] = field(default_factory=list)
    value_columns: List[str] = field(default_factory=list)
    metadata_columns: List[str] = field(default_factory=list)

    # Full classification mapping
    column_roles: Dict[str, str] = field(default_factory=dict)

    # Detection confidence scores
    confidence_scores: Dict[str, float] = field(default_factory=dict)

    # Column statistics
    column_stats: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def get_role(self, column: str) -> str:
        """Get the detected role for a column."""
        return self.column_roles.get(column, 'unknown')


class DimensionDetector:
    """Detects dimension columns using Gemini-validated heuristics.

    The detector applies three tests:
    1. Cardinality Test: unique_values / total_rows ratio
    2. Semantic Test: Keyword matching in column names
    3. Summation Test: Check if grouping makes statistical sense
    """

    # Default configuration
    DEFAULT_CONFIG = {
        # Cardinality thresholds
        'cardinality_dimension_threshold': 0.1,   # < 10% unique = likely dimension
        'cardinality_value_threshold': 0.5,       # > 50% unique = likely value
        'cardinality_metadata_threshold': 0.01,   # < 1% unique = likely metadata

        # Keyword lists for semantic detection
        'place_keywords': [
            'state', 'county', 'city', 'fips', 'geo', 'region', 'country',
            'place', 'district', 'area', 'location', 'territory', 'nation',
            'province', 'municipality', 'zip', 'tract', 'block', 'cbsa',
            'msa', 'metro', 'locale', 'geoname', 'geoid', 'geocode'
        ],
        'time_keywords': [
            'year', 'date', 'month', 'quarter', 'period', 'time', 'fiscal',
            'annual', 'weekly', 'daily', 'observation_date', 'ref_date',
            'reportdate', 'survey', 'semester', 'term'
        ],
        'dimension_keywords': [
            'gender', 'sex', 'age', 'race', 'ethnicity', 'industry', 'education',
            'status', 'type', 'category', 'sector', 'occupation', 'class',
            'group', 'level', 'grade', 'disability', 'citizenship', 'veteran',
            'marital', 'income_level', 'language', 'nativity', 'tenure',
            'mode', 'fuel', 'source', 'segment', 'program'
        ],
        'value_keywords': [
            'count', 'total', 'amount', 'percent', 'rate', 'value', 'number',
            'sum', 'avg', 'average', 'mean', 'median', 'population', 'estimate',
            'quantity', 'measurement', 'observation', 'score', 'index',
            'moe', 'margin', 'error', 'pct', 'ratio'
        ],
        'metadata_keywords': [
            'source', 'unit', 'note', 'annotation', 'method', 'flag',
            'footnote', 'comment', 'description', 'name', 'label',
            'suppressed', 'reliability', 'quality'
        ],

        # Total/aggregate detection
        'total_keywords': ['total', 'all', 'overall', 'aggregate', 'combined', 'entire'],

        # Numeric detection threshold
        'numeric_threshold': 0.8,  # 80% of values must be numeric
    }

    def __init__(self, config: Dict = None):
        """Initialize the DimensionDetector.

        Args:
            config: Optional configuration dictionary to override defaults.
        """
        self._config = {**self.DEFAULT_CONFIG, **(config or {})}

    def classify_columns(self, rows: List[List[str]], headers: List[str]) -> DimensionDetectionResult:
        """Classify columns into: place, time, dimension, value, metadata.

        Args:
            rows: List of data rows (each row is a list of string values)
            headers: List of column header names

        Returns:
            DimensionDetectionResult with classifications
        """
        result = DimensionDetectionResult()

        if not rows or not headers:
            return result

        n_rows = len(rows)
        n_cols = len(headers)

        # Collect column values
        column_values = self._collect_column_values(rows, headers)

        # Classify each column
        for col_idx, col_name in enumerate(headers):
            if col_idx >= n_cols:
                continue

            values = column_values.get(col_idx, [])

            # Run tests
            cardinality_result = self._cardinality_test(values, n_rows)
            semantic_result = self._semantic_test(col_name)
            numeric_result = self._is_numeric(values)

            # Store stats
            result.column_stats[col_name] = {
                'cardinality': cardinality_result,
                'semantic': semantic_result,
                'is_numeric': numeric_result['is_numeric'],
                'n_unique': len(set(values)),
                'n_rows': n_rows,
            }

            # Determine final role (semantic takes priority)
            role = self._determine_role(
                col_name,
                cardinality_result,
                semantic_result,
                numeric_result
            )

            result.column_roles[col_name] = role
            result.confidence_scores[col_name] = self._calculate_confidence(
                cardinality_result, semantic_result, numeric_result
            )

            # Add to appropriate list
            if role == 'place':
                result.place_columns.append(col_name)
            elif role == 'time':
                result.time_columns.append(col_name)
            elif role == 'dimension':
                result.dimension_columns.append(col_name)
            elif role == 'value':
                result.value_columns.append(col_name)
            elif role == 'metadata':
                result.metadata_columns.append(col_name)

        logging.info(
            f'DimensionDetector: {len(result.place_columns)} place, '
            f'{len(result.time_columns)} time, {len(result.dimension_columns)} dimension, '
            f'{len(result.value_columns)} value, {len(result.metadata_columns)} metadata'
        )

        return result

    def _collect_column_values(self, rows: List[List[str]],
                                headers: List[str]) -> Dict[int, List[str]]:
        """Collect values for each column.

        Args:
            rows: List of data rows
            headers: Column headers

        Returns:
            Dictionary mapping column index to list of values
        """
        column_values = {i: [] for i in range(len(headers))}

        for row in rows:
            for col_idx in range(min(len(row), len(headers))):
                val = row[col_idx]
                if val and str(val).strip():
                    column_values[col_idx].append(str(val).strip())

        return column_values

    def _cardinality_test(self, values: List[str], n_rows: int) -> Dict[str, Any]:
        """Apply cardinality ratio test.

        Low unique ratio indicates dimension column.
        High unique ratio indicates value or metadata column.

        Args:
            values: List of column values
            n_rows: Total number of rows

        Returns:
            Dictionary with cardinality analysis
        """
        if not values or n_rows == 0:
            return {'ratio': 1.0, 'suggested_role': 'metadata', 'unique_count': 0}

        unique_values = set(values)
        unique_count = len(unique_values)
        ratio = unique_count / n_rows

        # Determine suggested role based on thresholds
        if unique_count <= 1:
            suggested_role = 'metadata'  # Constant column
        elif ratio < self._config['cardinality_metadata_threshold']:
            suggested_role = 'metadata'
        elif ratio < self._config['cardinality_dimension_threshold']:
            suggested_role = 'dimension'
        elif ratio > self._config['cardinality_value_threshold']:
            suggested_role = 'value'
        else:
            suggested_role = 'dimension'  # Medium cardinality defaults to dimension

        return {
            'ratio': ratio,
            'suggested_role': suggested_role,
            'unique_count': unique_count,
        }

    def _semantic_test(self, col_name: str) -> Dict[str, Any]:
        """Apply semantic keyword matching test.

        Args:
            col_name: Column header name

        Returns:
            Dictionary with semantic analysis
        """
        col_lower = col_name.lower()

        # Check each keyword category
        for role, key in [
            ('place', 'place_keywords'),
            ('time', 'time_keywords'),
            ('dimension', 'dimension_keywords'),
            ('value', 'value_keywords'),
            ('metadata', 'metadata_keywords'),
        ]:
            keywords = self._config.get(key, [])
            for kw in keywords:
                if kw in col_lower:
                    return {
                        'matched_keyword': kw,
                        'suggested_role': role,
                        'confidence': 0.9,  # High confidence for keyword match
                    }

        return {
            'matched_keyword': None,
            'suggested_role': None,
            'confidence': 0.0,
        }

    def _is_numeric(self, values: List[str]) -> Dict[str, Any]:
        """Check if column is primarily numeric.

        Args:
            values: List of column values

        Returns:
            Dictionary with numeric analysis
        """
        if not values:
            return {'is_numeric': False, 'numeric_ratio': 0.0}

        numeric_count = 0
        for val in values:
            try:
                # Remove common formatting
                clean = val.replace(',', '').replace('%', '').replace('$', '').strip()
                if clean:
                    float(clean)
                    numeric_count += 1
            except (ValueError, TypeError):
                pass

        ratio = numeric_count / len(values)
        is_numeric = ratio >= self._config['numeric_threshold']

        return {
            'is_numeric': is_numeric,
            'numeric_ratio': ratio,
            'numeric_count': numeric_count,
        }

    def _determine_role(self, col_name: str,
                        cardinality: Dict[str, Any],
                        semantic: Dict[str, Any],
                        numeric: Dict[str, Any]) -> str:
        """Determine final column role from all tests.

        Priority:
        1. Semantic match (if high confidence)
        2. Cardinality + numeric combination
        3. Default based on cardinality

        Args:
            col_name: Column name
            cardinality: Cardinality test result
            semantic: Semantic test result
            numeric: Numeric test result

        Returns:
            Role string
        """
        # Semantic takes priority if match found
        if semantic.get('suggested_role'):
            return semantic['suggested_role']

        # Check for constant/empty column
        if cardinality.get('unique_count', 0) <= 1:
            return 'metadata'

        # Combine cardinality and numeric
        is_numeric = numeric.get('is_numeric', False)
        cardinality_role = cardinality.get('suggested_role', 'dimension')

        # High cardinality + numeric = value
        if cardinality_role == 'value' and is_numeric:
            return 'value'

        # High cardinality + non-numeric = metadata (likely IDs or text)
        if cardinality.get('ratio', 0) > self._config['cardinality_value_threshold'] and not is_numeric:
            return 'metadata'

        # Low cardinality = dimension (regardless of numeric)
        if cardinality.get('ratio', 1) < self._config['cardinality_dimension_threshold']:
            return 'dimension'

        # Default to cardinality suggestion
        return cardinality_role

    def _calculate_confidence(self, cardinality: Dict[str, Any],
                               semantic: Dict[str, Any],
                               numeric: Dict[str, Any]) -> float:
        """Calculate confidence score for the classification.

        Args:
            cardinality: Cardinality test result
            semantic: Semantic test result
            numeric: Numeric test result

        Returns:
            Confidence score 0-1
        """
        confidence = 0.5  # Base confidence

        # Semantic match adds confidence
        if semantic.get('matched_keyword'):
            confidence += 0.3

        # Clear cardinality signal adds confidence
        ratio = cardinality.get('ratio', 0.5)
        if ratio < 0.05 or ratio > 0.9:
            confidence += 0.2

        return min(1.0, confidence)

    def summation_test(self, rows: List[List[str]], headers: List[str],
                       candidate_col: str, value_col: str) -> bool:
        """Check if grouping by candidate and summing value is meaningful.

        This test verifies if the candidate column behaves like a dimension
        by checking if grouping by it and summing the value column produces
        sensible results.

        Args:
            rows: Data rows
            headers: Column headers
            candidate_col: Column to test as potential dimension
            value_col: Column with values to sum

        Returns:
            True if grouping makes statistical sense
        """
        if candidate_col not in headers or value_col not in headers:
            return False

        try:
            cand_idx = headers.index(candidate_col)
            val_idx = headers.index(value_col)

            # Group values by candidate
            groups = {}
            for row in rows:
                if cand_idx >= len(row) or val_idx >= len(row):
                    continue

                group_key = str(row[cand_idx]).strip()
                val_str = str(row[val_idx]).strip()

                try:
                    val = float(val_str.replace(',', '').replace('%', '').replace('$', ''))
                    if group_key not in groups:
                        groups[group_key] = []
                    groups[group_key].append(val)
                except (ValueError, TypeError):
                    continue

            # Check if grouping is meaningful
            if len(groups) < 2:
                return False  # Not enough groups

            # Check variance between groups
            group_means = [sum(vals) / len(vals) for vals in groups.values() if vals]
            if not group_means:
                return False

            overall_mean = sum(group_means) / len(group_means)
            if overall_mean == 0:
                return False

            # Check if there's meaningful variance between groups
            variance = sum((m - overall_mean) ** 2 for m in group_means) / len(group_means)
            coefficient_of_variation = (variance ** 0.5) / abs(overall_mean) if overall_mean != 0 else 0

            # If CV > 0.1, grouping is meaningful
            return coefficient_of_variation > 0.1

        except Exception as e:
            logging.debug(f'Summation test error: {e}')
            return False

    def detect_total_rows(self, rows: List[List[str]], headers: List[str],
                          dimension_cols: List[str]) -> Set[int]:
        """Detect rows that represent totals/aggregates.

        Args:
            rows: Data rows
            headers: Column headers
            dimension_cols: Identified dimension columns

        Returns:
            Set of row indices that are total/aggregate rows
        """
        total_rows = set()
        total_keywords = [kw.lower() for kw in self._config.get('total_keywords', [])]

        for row_idx, row in enumerate(rows):
            for col_name in dimension_cols:
                if col_name not in headers:
                    continue

                col_idx = headers.index(col_name)
                if col_idx >= len(row):
                    continue

                val_lower = str(row[col_idx]).lower().strip()
                for kw in total_keywords:
                    if kw in val_lower:
                        total_rows.add(row_idx)
                        break

        return total_rows


def detect_dimensions(rows: List[List[str]], headers: List[str],
                      config: Dict = None) -> DimensionDetectionResult:
    """Convenience function to detect dimension columns.

    Args:
        rows: Data rows
        headers: Column headers
        config: Optional configuration

    Returns:
        DimensionDetectionResult with classifications
    """
    detector = DimensionDetector(config)
    return detector.classify_columns(rows, headers)
