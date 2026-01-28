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
"""Utilities to sample csv files.

To sample a CSV data file, run the command:
  python data_sampler.py --sampler_input=<input-csv> --sampler_output=<output-csv>

This generates a sample output CSV with atmost 100 rows selecting input rows
with unique column values.

Use the function: sample_csv_file(<input_file>, <output_file>)
to generate sample CSV in code.
"""

import csv
import os
import random
import re
import sys
import tempfile

from absl import app
from absl import flags
from absl import logging

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_SCRIPT_DIR)
sys.path.append(os.path.dirname(_SCRIPT_DIR))
sys.path.append(os.path.dirname(os.path.dirname(_SCRIPT_DIR)))
sys.path.append(
    os.path.join(os.path.dirname(os.path.dirname(_SCRIPT_DIR)), 'util'))

flags.DEFINE_string('sampler_input', '',
                    'The path to the input CSV file to be sampled.')
flags.DEFINE_string('sampler_output', '',
                    'The path to the output file for the sampled CSV data.')
flags.DEFINE_integer(
    'sampler_output_rows', 100,
    'The maximum number of rows to include in the sampled output.')
flags.DEFINE_integer(
    'sampler_header_rows', 1,
    'The number of header rows to be copied directly to the output file.')
flags.DEFINE_integer(
    'sampler_rows_per_key', 5,
    'The maximum number of rows to select for each unique value found.')
flags.DEFINE_float(
    'sampler_rate', -1,
    'The sampling rate for random row selection (e.g., 0.1 for 10%).')
# TODO: Rename to sampler_cell_value_regex to better reflect its purpose.
# See: https://github.com/datacommonsorg/data/pull/1445#discussion_r2180147075
flags.DEFINE_string(
    'sampler_column_regex', r'^[0-9]{4}$|[a-zA-Z-]',
    'A regular expression used to identify and select unique column values.')
flags.DEFINE_string(
    'sampler_unique_columns', '',
    'A comma-separated list of column names to use for selecting unique rows.')
flags.DEFINE_string('sampler_input_delimiter', ',',
                    'The delimiter used in the input CSV file.')
flags.DEFINE_string('sampler_input_encoding', 'UTF8',
                    'The encoding of the input CSV file.')
flags.DEFINE_string('sampler_output_delimiter', None,
                    'The delimiter to use in the output CSV file.')
flags.DEFINE_float(
    'sampler_categorical_threshold', 0.1,
    'Columns with (unique_values/total_rows) below this are categorical.')
flags.DEFINE_bool(
    'sampler_auto_detect_categorical', True,
    'Automatically detect categorical columns for coverage sampling.')
flags.DEFINE_bool(
    'sampler_ensure_coverage', True,
    'Ensure all unique values in categorical columns are represented.')
flags.DEFINE_string(
    'sampler_id_column_patterns', 'ID,CODE,FIPS,KEY',
    'Comma-separated patterns to identify ID columns in wide datasets.')
flags.DEFINE_integer(
    'sampler_max_output_rows', 0,
    'Maximum output rows (0 = no limit, coverage takes priority).')
flags.DEFINE_bool(
    'sampler_smart_columns', True,
    'Enable smart column analysis to skip derived/constant columns.')
flags.DEFINE_bool(
    'sampler_detect_aggregation', True,
    'Detect and deprioritize aggregation/total rows.')
flags.DEFINE_float(
    'sampler_constant_threshold', 0.01,
    'Columns with unique_ratio below this are skipped as constant.')
flags.DEFINE_float(
    'sampler_correlation_threshold', 0.95,
    'Threshold for detecting redundant column pairs.')
flags.DEFINE_bool(
    'sampler_verbose', True,
    'Output detailed report of column analysis and sampling decisions.')
flags.DEFINE_string(
    'sampler_aggregation_keywords', 'Total,All,Sum,Overall,National,Combined,WHOLE,Entire,Grand',
    'Comma-separated keywords indicating aggregation rows.')
flags.DEFINE_integer(
    'sampler_max_aggregation_rows', 2,
    'Maximum aggregation rows to include in sample.')
flags.DEFINE_bool(
    'sampler_auto_detect_headers', True,
    'Automatically detect the number of header rows.')
flags.DEFINE_bool(
    'sampler_skip_empty_columns', True,
    'Skip columns with empty headers or mostly empty values.')
flags.DEFINE_bool(
    'sampler_detect_footers', True,
    'Detect and exclude footer/documentation rows.')
flags.DEFINE_string(
    'sampler_footer_keywords', 'Source,Note,Data from,Footnote,*,†,‡',
    'Comma-separated keywords that indicate footer rows.')
flags.DEFINE_integer(
    'sampler_min_rows', 40,
    'Minimum number of rows to output (prevents under-sampling).')
flags.DEFINE_integer(
    'sampler_max_rows', 80,
    'Target maximum rows to output (soft cap for predictable sizing).')

_FLAGS = flags.FLAGS

# Try new import paths first, fall back to old
try:
    from src.infrastructure.io import file_util
except ImportError:
    import file_util

try:
    from src.infrastructure.config.config_map import ConfigMap
except ImportError:
    from config_map import ConfigMap

try:
    from src.infrastructure.metrics.counters import Counters
except ImportError:
    from counters import Counters

try:
    from src.pipeline.sampling.column_analyzer import ColumnAnalyzer, ColumnAnalysisResult
except ImportError:
    from column_analyzer import ColumnAnalyzer, ColumnAnalysisResult


# Class to sample a data file.
class DataSampler:
    """A class for sampling data from a file.

    This class provides functionality to sample rows from a CSV file based on
    various criteria such as unique values in columns, sampling rate, and maximum
    number of rows.

    Attributes:
        _config: A ConfigMap object containing the configuration parameters.
        _counters: A Counters object for tracking various statistics during the
          sampling process.
        _column_counts: A dictionary to store the count of unique values per
          column.
        _column_headers: A dictionary to store the headers of the columns.
        _column_regex: A compiled regular expression to filter column values.
        _selected_rows: The number of rows selected so far.
    """

    def __init__(
        self,
        config_dict: dict = None,
        counters: Counters = None,
    ):
        """Initializes the DataSampler object.

        Args:
            config_dict: A dictionary of configuration parameters.
            counters: A Counters object for tracking statistics.
        """
        self._config = ConfigMap(config_dict=get_default_config())
        if config_dict:
            self._config.add_configs(config_dict)
        self._counters = counters if counters is not None else Counters()
        self.reset()

    def reset(self) -> None:
        """Resets the state of the DataSampler.

        This method resets the internal state of the DataSampler, including the
        counts of unique column values and the number of selected rows. This is
        useful when you want to reuse the same DataSampler instance for sampling
        multiple files.
        """
        # Dictionary of unique values: count per column
        self._column_counts = {}
        # Dictionary of column index: list of header strings
        self._column_headers = {}
        self._column_regex = None
        regex = self._config.get('sampler_column_regex')
        if regex:
            self._column_regex = re.compile(regex)
        self._selected_rows = 0
        # Parse unique column names from config
        self._unique_column_names = []
        self._unique_column_indices = {}
        unique_cols_str = self._config.get('sampler_unique_columns', '')
        if unique_cols_str:
            self._unique_column_names = [
                col.strip()
                for col in unique_cols_str.split(',')
                if col.strip()
            ]
        # Categorical column detection state
        self._categorical_columns = {}  # col_index -> set of all unique values
        self._uncovered_values = {}  # col_index -> set of uncovered values
        self._id_column_indices = set()  # indices of detected ID columns
        self._headers_list = []  # list of header names by index
        self._prescan_complete = False

        # Smart column analysis state (new)
        self._skip_columns = set()  # columns to skip for uniqueness tracking
        self._column_analysis = None  # ColumnAnalysisResult from analyzer
        self._numeric_ranges = {}  # col_index -> {min, max, covered_ranges}
        self._numeric_coverage = {}  # col_index -> set of covered quartiles

        # Aggregation row tracking (new)
        self._aggregation_keywords = []
        agg_kw_str = self._config.get('sampler_aggregation_keywords', '')
        if agg_kw_str:
            self._aggregation_keywords = [
                kw.strip().lower()
                for kw in agg_kw_str.split(',')
                if kw.strip()
            ]
        self._selected_aggregation_rows = 0
        self._max_aggregation_rows = self._config.get('sampler_max_aggregation_rows', 2)

        # Duplicate pattern tracking (new)
        self._selected_signatures = set()  # signatures of already selected rows

    def __del__(self) -> None:
        """Logs the column headers and counts upon object deletion."""
        logging.log(2, f'Sampler column headers: {self._column_headers}')
        logging.log(2, f'sampler column counts: {self._column_counts}')

    def _get_column_count(self, column_index: int, value: str) -> int:
        """Returns the existing number of rows for a given column value.

        This method checks if the value in a specific column should be tracked and
        returns the number of times this value has been seen before for that
        column.

        Args:
            column_index: The index of the column in the current row.
            value: The string value of the column at the given index.

        Returns:
            The number of times the value has been seen before for the column.
            Returns sys.maxsize if the column should not be tracked or if the
            column value does not match the sampler_column_regex.
        """
        # Check if this column should be tracked
        if not self._should_track_column(column_index):
            return sys.maxsize
        # Check if column value is to be tracked.
        if self._column_regex:
            if not self._column_regex.search(value):
                # Not an interesting value.
                return sys.maxsize

        col_values = self._column_counts.get(column_index)
        if col_values is None:
            return 0
        return col_values.get(value, 0)

    def _should_track_column(self, column_index: int) -> bool:
        """Determines if a column should be tracked for unique values.

        Args:
            column_index: The index of the column.

        Returns:
            True if the column should be tracked (either no unique columns
            specified or this column is in the unique columns list), AND
            the column is not in the skip list from smart column analysis.
        """
        # Skip columns identified by smart column analysis
        if column_index in self._skip_columns:
            return False

        if not self._unique_column_names:
            # No specific columns specified, track all (except skipped)
            return True
        # Check if this column is in our unique columns
        return column_index in self._unique_column_indices.values()

    def _process_header_row(self, row: list[str]) -> None:
        """Process a header row to build column name to index mapping.

        This method is called for each header row (up to header_rows config) to
        search for columns specified in sampler_unique_columns. It only maps
        columns that are in the configured list. If called multiple times with
        duplicate column names, the last mapping is used.

        Args:
            row: A header row containing column names.
        """
        # Store headers for later use
        self._headers_list = list(row)

        if not self._unique_column_names:
            return

        for index, column_name in enumerate(row):
            if column_name in self._unique_column_names:
                self._unique_column_indices[column_name] = index
                logging.level_debug() and logging.debug(
                    f'Mapped unique column "{column_name}" to index {index}')

    def _auto_detect_header_rows(self, input_file: str) -> int:
        """Automatically detect the number of header rows.

        Analyzes the first 10 rows to detect header patterns:
        - Rows with >50% empty cells
        - Rows with metadata patterns (e.g., "Table X", "Year:")
        - Rows that are all text with no numbers

        Args:
            input_file: Path to the CSV file.

        Returns:
            Detected number of header rows (defaults to 1 if uncertain).
        """
        try:
            input_encoding = self._config.get('input_encoding')
            if not input_encoding:
                input_encoding = file_util.file_get_encoding(input_file)

            with file_util.FileIO(input_file, encoding=input_encoding) as csv_file:
                csv_options = {'delimiter': self._config.get('input_delimiter')}
                csv_options = file_util.file_get_csv_reader_options(input_file, csv_options)
                csv_reader = csv.reader(csv_file, **csv_options)

                rows = []
                for i, row in enumerate(csv_reader):
                    if i >= 10:  # Only examine first 10 rows
                        break
                    rows.append(row)

                if not rows:
                    return 1

                header_count = 0
                for i, row in enumerate(rows):
                    # Count empty cells
                    empty_count = sum(1 for cell in row if not cell.strip())
                    empty_ratio = empty_count / len(row) if len(row) > 0 else 1.0

                    # Check for metadata patterns
                    first_cell = row[0].strip() if row else ''
                    metadata_patterns = ['table', 'figure', 'year:', 'note', 'source', '(number', 'unnamed:']
                    is_metadata = any(pattern in first_cell.lower() for pattern in metadata_patterns)

                    # Count numeric cells (for distinguishing data from headers)
                    numeric_count = 0
                    for cell in row:
                        try:
                            float(cell.replace(',', '').replace('%', '').strip())
                            numeric_count += 1
                        except (ValueError, AttributeError):
                            pass
                    numeric_ratio = numeric_count / len(row) if len(row) > 0 else 0

                    # Consider a row a header if:
                    # - It has many empty cells (>50%)
                    # - It has metadata patterns
                    # - It has very few numbers (<10%)
                    # - AND it's within the first 5 rows
                    if i < 5 and (empty_ratio > 0.5 or is_metadata or numeric_ratio < 0.1):
                        header_count = i + 1
                    else:
                        # Found data row, stop counting headers
                        break

                # Default to 1 if we didn't detect any special headers
                detected = max(1, header_count)

                if self._config.get('sampler_verbose', False):
                    logging.info(f'Auto-detected {detected} header row(s)')

                return detected

        except Exception as e:
            logging.warning(f'Error auto-detecting headers: {e}. Defaulting to 1.')
            return 1

    def _copy_entire_file(self, input_file: str, output_file: str, header_rows: int, output_delimiter: str) -> str:
        """Copy entire input file to output without sampling (for tiny datasets).

        Args:
            input_file: Path to input CSV file
            output_file: Path to output CSV file
            header_rows: Number of header rows
            output_delimiter: Delimiter for output file

        Returns:
            Path to output file
        """
        input_encoding = self._config.get('input_encoding')
        if not input_encoding:
            input_encoding = file_util.file_get_encoding(input_file)

        with file_util.FileIO(input_file, encoding=input_encoding) as csv_file:
            csv_options = {'delimiter': self._config.get('input_delimiter')}
            csv_options = file_util.file_get_csv_reader_options(input_file, csv_options)

            if not output_delimiter:
                output_delimiter = csv_options.get('delimiter', ',')

            with file_util.FileIO(output_file, mode='w') as output:
                csv_writer = csv.writer(output, delimiter=output_delimiter, doublequote=False, escapechar='\\')
                csv_reader = csv.reader(csv_file, **csv_options)

                for row in csv_reader:
                    csv_writer.writerow(row)
                    self._selected_rows += 1

        logging.info(f'Copied all {self._selected_rows} rows from {input_file} to {output_file}')
        return output_file

    def _add_random_rows_to_output(self, input_files: list[str], output_file: str,
                                   header_rows: int, rows_needed: int, output_delimiter: str) -> None:
        """Add random rows to output file to reach minimum/target threshold.

        Args:
            input_files: List of input CSV files
            output_file: Path to output file (will append to it)
            header_rows: Number of header rows to skip
            rows_needed: Number of additional rows needed
            output_delimiter: Delimiter for output
        """
        # Collect all data rows that weren't already selected
        available_rows = []

        for file in input_files:
            input_encoding = self._config.get('input_encoding')
            if not input_encoding:
                input_encoding = file_util.file_get_encoding(file)

            with file_util.FileIO(file, encoding=input_encoding) as csv_file:
                csv_options = {'delimiter': self._config.get('input_delimiter')}
                csv_options = file_util.file_get_csv_reader_options(file, csv_options)
                csv_reader = csv.reader(csv_file, **csv_options)

                row_index = 0
                for row in csv_reader:
                    row_index += 1
                    # Skip header rows
                    if row_index <= header_rows:
                        continue

                    # Check if this row was already selected
                    sig = self._get_row_signature(row)
                    if sig not in self._selected_signatures:
                        available_rows.append(row)

        # Randomly sample from available rows
        if available_rows:
            actual_rows_to_add = min(rows_needed, len(available_rows))
            rows_to_add = random.sample(available_rows, actual_rows_to_add)

            # Append to output file
            with file_util.FileIO(output_file, mode='a') as output:
                csv_writer = csv.writer(output, delimiter=output_delimiter, doublequote=False, escapechar='\\')
                for row in rows_to_add:
                    csv_writer.writerow(row)
                    self._selected_rows += 1

    def _detect_footer_start(self, rows: list[list[str]], start_index: int = 0) -> int:
        """Detect the starting index of footer/documentation rows.

        Analyzes rows from the end to detect footer patterns:
        - Rows containing footer keywords in the first column
        - Rows with significantly different structure than data rows

        Args:
            rows: All rows from the CSV (including headers).
            start_index: Index to start checking from (skip headers).

        Returns:
            Index where footer starts, or len(rows) if no footer detected.
        """
        if not rows or len(rows) <= start_index:
            return len(rows)

        footer_keywords_str = self._config.get('sampler_footer_keywords', '')
        if not footer_keywords_str:
            return len(rows)

        footer_keywords = [kw.strip().lower() for kw in footer_keywords_str.split(',') if kw.strip()]

        # Check last 20 rows for footer patterns
        check_from = max(start_index, len(rows) - 20)
        data_rows = rows[start_index:check_from]

        # Calculate baseline: average number of non-empty cells in data rows
        if data_rows:
            avg_non_empty = sum(sum(1 for cell in row if cell.strip()) for row in data_rows) / len(data_rows)
        else:
            avg_non_empty = 0

        footer_start = len(rows)

        for i in range(check_from, len(rows)):
            row = rows[i]
            if not row:
                continue

            # Check first cell for footer keywords
            first_cell = row[0].strip().lower() if row else ''
            has_footer_keyword = any(keyword in first_cell for keyword in footer_keywords)

            # Count non-empty cells
            non_empty = sum(1 for cell in row if cell.strip())

            # Consider it a footer if:
            # - Contains footer keywords in first column
            # - OR has significantly fewer non-empty cells than data rows (< 30% of average)
            if has_footer_keyword or (avg_non_empty > 0 and non_empty < avg_non_empty * 0.3):
                footer_start = i
                break

        if footer_start < len(rows) and self._config.get('sampler_verbose', False):
            logging.info(f'Detected footer starting at row {footer_start + 1} ({len(rows) - footer_start} rows)')

        return footer_start

    def _detect_id_columns(self, headers: list[str]) -> set[int]:
        """Detect likely identifier columns by name patterns.

        Args:
            headers: List of column header names.

        Returns:
            Set of column indices that are likely ID columns.
        """
        id_patterns_str = self._config.get('sampler_id_column_patterns', '')
        if not id_patterns_str:
            return set()

        patterns = [p.strip().upper() for p in id_patterns_str.split(',') if p.strip()]
        id_indices = set()

        for index, header in enumerate(headers):
            header_upper = header.upper()
            for pattern in patterns:
                if pattern in header_upper:
                    id_indices.add(index)
                    logging.level_debug() and logging.debug(
                        f'Detected ID column: "{header}" at index {index}')
                    break

        return id_indices

    def _get_adaptive_threshold(self, total_rows: int) -> float:
        """Calculate adaptive categorical threshold based on dataset size.

        Args:
            total_rows: Total number of data rows in the dataset.

        Returns:
            Categorical threshold value (0.05 to 0.2).
        """
        if total_rows < 500:
            threshold = 0.2  # 20% for small datasets
        elif total_rows < 2000:
            threshold = 0.1  # 10% for medium datasets
        else:
            threshold = 0.05  # 5% for large datasets

        if self._config.get('sampler_verbose', False):
            logging.info(
                f'Using adaptive categorical threshold: {threshold:.2%} '
                f'(dataset size: {total_rows} rows)')

        return threshold

    def _detect_categorical_columns(self, rows: list[list[str]],
                                     headers: list[str]) -> dict[int, set[str]]:
        """Analyze rows to detect categorical columns.

        A column is considered categorical if the ratio of unique values to
        total rows is below the configured threshold.

        Args:
            rows: Sample rows to analyze (excluding headers).
            headers: List of column header names.

        Returns:
            Dictionary mapping column_index -> set of unique values for
            categorical columns only.
        """
        if not rows:
            return {}

        num_rows = len(rows)
        # Use adaptive threshold based on dataset size
        threshold = self._get_adaptive_threshold(num_rows)
        num_columns = len(headers) if headers else (len(rows[0]) if rows else 0)

        # Count unique values per column
        column_values = {}
        for col_idx in range(num_columns):
            column_values[col_idx] = set()

        for row in rows:
            for col_idx in range(min(len(row), num_columns)):
                column_values[col_idx].add(row[col_idx])

        # Identify categorical columns (low cardinality)
        categorical_cols = {}
        for col_idx, values in column_values.items():
            unique_ratio = len(values) / num_rows if num_rows > 0 else 1.0
            if unique_ratio <= threshold:
                categorical_cols[col_idx] = values
                header_name = headers[col_idx] if col_idx < len(headers) else f'col_{col_idx}'
                logging.level_debug() and logging.debug(
                    f'Categorical column detected: "{header_name}" '
                    f'({len(values)} unique / {num_rows} rows = {unique_ratio:.2%})')

        return categorical_cols

    def _covers_new_categorical_value(self, row: list[str]) -> bool:
        """Check if row covers any uncovered categorical value.

        Args:
            row: The data row to check.

        Returns:
            True if the row contains at least one uncovered categorical value.
        """
        if not self._uncovered_values:
            return False

        for col_idx, uncovered in self._uncovered_values.items():
            if col_idx < len(row) and row[col_idx] in uncovered:
                return True
        return False

    def _mark_values_covered(self, row: list[str]) -> None:
        """Mark categorical values in this row as covered.

        Args:
            row: The selected data row.
        """
        for col_idx in list(self._uncovered_values.keys()):
            if col_idx < len(row):
                value = row[col_idx]
                if value in self._uncovered_values[col_idx]:
                    self._uncovered_values[col_idx].discard(value)
                    header_name = (self._headers_list[col_idx]
                                   if col_idx < len(self._headers_list)
                                   else f'col_{col_idx}')
                    logging.level_debug() and logging.debug(
                        f'Covered value "{value}" in column "{header_name}"')

    def _all_categorical_covered(self) -> bool:
        """Check if all categorical values have been covered.

        Returns:
            True if no uncovered values remain in any categorical column.
        """
        for uncovered in self._uncovered_values.values():
            if uncovered:
                return False
        return True

    def _get_coverage_stats(self) -> dict:
        """Get statistics about categorical coverage.

        Returns:
            Dictionary with coverage statistics.
        """
        stats = {
            'total_categorical_columns': len(self._categorical_columns),
            'columns': {}
        }
        for col_idx, all_values in self._categorical_columns.items():
            uncovered = self._uncovered_values.get(col_idx, set())
            covered = len(all_values) - len(uncovered)
            header_name = (self._headers_list[col_idx]
                           if col_idx < len(self._headers_list)
                           else f'col_{col_idx}')
            stats['columns'][header_name] = {
                'total': len(all_values),
                'covered': covered,
                'uncovered': len(uncovered)
            }
        return stats

    def _run_smart_column_analysis(self, rows: list, headers: list) -> None:
        """Run smart column analysis to identify columns to skip.

        Args:
            rows: All data rows from prescan.
            headers: Column headers.
        """
        analyzer_config = {
            'constant_threshold': self._config.get('sampler_constant_threshold', 0.01),
            'correlation_threshold': self._config.get('sampler_correlation_threshold', 0.95),
        }
        analyzer = ColumnAnalyzer(analyzer_config)
        self._column_analysis = analyzer.analyze(rows, headers)

        # Build skip columns set
        self._skip_columns = self._column_analysis.get_skip_columns()

        # Store numeric ranges for range coverage sampling
        self._numeric_ranges = self._column_analysis.numeric_columns
        for col_idx in self._numeric_ranges:
            self._numeric_coverage[col_idx] = set()  # track covered quartiles

        # Log analysis if verbose mode
        if self._config.get('sampler_verbose', False):
            self._log_column_analysis()

        logging.info(
            f'Smart column analysis: skipping {len(self._skip_columns)} columns '
            f'({len(self._column_analysis.constant_columns)} constant, '
            f'{len(self._column_analysis.derived_columns)} derived, '
            f'{len(self._column_analysis.redundant_pairs)} redundant pairs)'
        )

    def _log_column_analysis(self) -> None:
        """Log detailed column analysis report (verbose mode)."""
        if not self._column_analysis:
            return

        logging.info('=== Column Analysis Report ===')
        logging.info(f'Total columns: {len(self._headers_list)}')
        logging.info(f'Columns used for sampling: {len(self._headers_list) - len(self._skip_columns)}')

        if self._column_analysis.constant_columns:
            names = [self._headers_list[i] for i in self._column_analysis.constant_columns
                     if i < len(self._headers_list)]
            logging.info(f'Constant columns (skipped): {names[:10]}{"..." if len(names) > 10 else ""}')

        if self._column_analysis.derived_columns:
            names = [self._headers_list[i] for i in self._column_analysis.derived_columns
                     if i < len(self._headers_list)]
            logging.info(f'Derived columns (skipped): {names[:10]}{"..." if len(names) > 10 else ""}')

        if self._column_analysis.metadata_columns:
            names = [self._headers_list[i] for i in self._column_analysis.metadata_columns
                     if i < len(self._headers_list)]
            logging.info(f'Metadata columns (skipped): {names[:10]}{"..." if len(names) > 10 else ""}')

        if self._column_analysis.redundant_pairs:
            pairs = [(self._headers_list[a], self._headers_list[b])
                     for a, b in self._column_analysis.redundant_pairs
                     if a < len(self._headers_list) and b < len(self._headers_list)]
            logging.info(f'Redundant pairs (second skipped): {pairs[:5]}{"..." if len(pairs) > 5 else ""}')

        logging.info('==============================')

    def _is_aggregation_row(self, row: list[str]) -> bool:
        """Check if row is a total/aggregate row.

        Args:
            row: The data row to check.

        Returns:
            True if the row appears to be an aggregation/total row.
        """
        if not self._aggregation_keywords:
            return False

        # Check first few columns for aggregation keywords
        for i, val in enumerate(row[:min(5, len(row))]):
            val_lower = str(val).lower().strip()
            for keyword in self._aggregation_keywords:
                if keyword in val_lower:
                    return True
        return False

    def _get_row_signature(self, row: list[str]) -> tuple:
        """Get a signature for the row based on key columns.

        This creates a signature using only categorical columns that aren't
        skipped, to detect duplicate patterns.

        Args:
            row: The data row.

        Returns:
            Tuple signature for deduplication.
        """
        key_cols = []
        for col_idx in self._categorical_columns.keys():
            if col_idx not in self._skip_columns and col_idx < len(row):
                key_cols.append(col_idx)

        if not key_cols:
            # Fall back to first few non-skipped columns
            for i in range(min(5, len(row))):
                if i not in self._skip_columns:
                    key_cols.append(i)

        return tuple(row[i] if i < len(row) else '' for i in key_cols)

    def _is_duplicate_pattern(self, row: list[str]) -> bool:
        """Check if row pattern has already been selected.

        Args:
            row: The data row to check.

        Returns:
            True if a row with the same signature was already selected.
        """
        sig = self._get_row_signature(row)
        return sig in self._selected_signatures

    def _extends_numeric_range(self, row: list[str]) -> bool:
        """Check if row extends coverage of numeric ranges.

        Args:
            row: The data row to check.

        Returns:
            True if the row contains values in uncovered numeric quartiles.
        """
        if not self._numeric_ranges:
            return False

        for col_idx, range_info in self._numeric_ranges.items():
            if col_idx >= len(row) or col_idx in self._skip_columns:
                continue

            try:
                val = float(str(row[col_idx]).replace(',', '').replace('%', '').replace('$', ''))
            except (ValueError, TypeError):
                continue

            # Determine which quartile this value falls into
            q1, median, q3 = range_info['q1'], range_info['median'], range_info['q3']
            min_val, max_val = range_info['min'], range_info['max']

            quartile = None
            if val <= q1:
                quartile = 'q1'
            elif val <= median:
                quartile = 'q2'
            elif val <= q3:
                quartile = 'q3'
            else:
                quartile = 'q4'

            # Check for extreme values (min/max)
            if abs(val - min_val) < 0.001:
                quartile = 'min'
            elif abs(val - max_val) < 0.001:
                quartile = 'max'

            # Check if this quartile is uncovered
            if quartile and quartile not in self._numeric_coverage.get(col_idx, set()):
                return True

        return False

    def _update_numeric_coverage(self, row: list[str]) -> None:
        """Update numeric coverage tracking for a selected row.

        Args:
            row: The selected data row.
        """
        for col_idx, range_info in self._numeric_ranges.items():
            if col_idx >= len(row) or col_idx in self._skip_columns:
                continue

            try:
                val = float(str(row[col_idx]).replace(',', '').replace('%', '').replace('$', ''))
            except (ValueError, TypeError):
                continue

            q1, median, q3 = range_info['q1'], range_info['median'], range_info['q3']
            min_val, max_val = range_info['min'], range_info['max']

            quartile = None
            if val <= q1:
                quartile = 'q1'
            elif val <= median:
                quartile = 'q2'
            elif val <= q3:
                quartile = 'q3'
            else:
                quartile = 'q4'

            if abs(val - min_val) < 0.001:
                quartile = 'min'
            elif abs(val - max_val) < 0.001:
                quartile = 'max'

            if quartile and col_idx in self._numeric_coverage:
                self._numeric_coverage[col_idx].add(quartile)

    def _prescan_for_categorical_columns(self, input_files: list[str],
                                          header_rows: int) -> None:
        """Pre-scan input files to detect categorical columns.

        This method reads all input files to:
        1. Extract headers
        2. Collect all rows for categorical column detection
        3. Detect ID columns based on header name patterns
        4. Initialize uncovered values for coverage-based sampling

        Args:
            input_files: List of input file paths.
            header_rows: Number of header rows to skip.
        """
        all_rows = []
        headers = []

        for file in input_files:
            input_encoding = self._config.get('input_encoding')
            if not input_encoding:
                input_encoding = file_util.file_get_encoding(file)

            with file_util.FileIO(file, encoding=input_encoding) as csv_file:
                csv_options = {'delimiter': self._config.get('input_delimiter')}
                csv_options = file_util.file_get_csv_reader_options(
                    file, csv_options)
                csv_reader = csv.reader(csv_file, **csv_options)

                row_index = 0
                for row in csv_reader:
                    row_index += 1
                    if row_index <= header_rows:
                        # Capture headers from first header row
                        if row_index == 1 and not headers:
                            headers = list(row)
                        continue
                    all_rows.append(row)

        if not all_rows:
            logging.warning('No data rows found during prescan')
            return

        # Store headers
        self._headers_list = headers

        # Detect ID columns
        self._id_column_indices = self._detect_id_columns(headers)
        if self._id_column_indices:
            logging.info(f'Detected ID columns: {[headers[i] for i in self._id_column_indices if i < len(headers)]}')

        # Detect categorical columns
        self._categorical_columns = self._detect_categorical_columns(all_rows, headers)

        # Exclude ID columns from categorical columns (they're usually unique per row)
        for id_idx in self._id_column_indices:
            if id_idx in self._categorical_columns:
                del self._categorical_columns[id_idx]

        # Initialize uncovered values
        self._uncovered_values = {
            col_idx: set(values)
            for col_idx, values in self._categorical_columns.items()
        }

        self._prescan_complete = True

        # Smart column analysis (new)
        if self._config.get('sampler_smart_columns', True):
            self._run_smart_column_analysis(all_rows, headers)

        # Log summary
        if self._categorical_columns:
            total_values = sum(len(v) for v in self._categorical_columns.values())
            logging.info(
                f'Pre-scan complete: {len(self._categorical_columns)} categorical '
                f'columns with {total_values} unique values to cover'
            )
            for col_idx, values in self._categorical_columns.items():
                header_name = headers[col_idx] if col_idx < len(headers) else f'col_{col_idx}'
                logging.info(f'  - {header_name}: {len(values)} unique values')
        else:
            logging.info('Pre-scan complete: No categorical columns detected')

    def _add_column_header(self, column_index: int, value: str) -> str:
        """Adds the first non-empty value of a column as its header.

        Args:
            column_index: The index of the column.
            value: The value to be considered for the header.

        Returns:
            The header of the column.
        """
        cur_header = self._column_headers.get(column_index, '')
        if not cur_header and value:
            # This is the first value for the column. Set as header.
            self._column_headers[column_index] = value
            return value
        return cur_header

    def _add_row_counts(self, row: list[str]) -> None:
        """Updates the column counts for a selected row.

        This method iterates through the columns of a selected row and updates the
        counts of the unique values in each column.

        Args:
            row: The row that has been selected for the sample.
        """
        # Update counts for each tracked column value in the row.
        for index in range(len(row)):
            # Skip columns not being tracked
            if not self._should_track_column(index):
                continue
            value = row[index]
            col_counts = self._column_counts.get(index)
            if col_counts is None:
                # Add a new column
                col_counts = {}
                self._column_counts[index] = col_counts
            # Add count for column value
            if value not in col_counts:
                header = self._add_column_header(index, value)
                self._counters.add_counter(
                    f'sampler-unique-values-column-{index}-{header}', 1)
            count = col_counts.get(value, 0)
            col_counts[value] = count + 1
        self._selected_rows += 1
        return

    def select_row(self, row: list[str], sample_rate: float = -1) -> bool:
        """Determines whether a row should be added to the sample output.

        This method applies a set of rules to decide if a row should be
        selected. When coverage mode is enabled, rows covering new categorical
        values are prioritized. Otherwise, a row is selected if it contains a
        new unique value in any column, or if it is randomly selected based on
        the sampling rate.

        The method now also considers:
        - Aggregation row detection (deprioritize total/summary rows)
        - Duplicate pattern detection (skip rows with same signature)
        - Numeric range coverage (prefer rows that extend value ranges)

        Args:
            row: The row to be considered for selection.
            sample_rate: The sampling rate to use for random selection. If not
              provided, the configured sampling rate is used.

        Returns:
            True if the row should be selected, False otherwise.
        """
        ensure_coverage = self._config.get('sampler_ensure_coverage', True)
        max_output_rows = self._config.get('sampler_max_output_rows', 0)
        detect_aggregation = self._config.get('sampler_detect_aggregation', True)

        # Check max output rows limit (if set and not in coverage mode)
        if max_output_rows > 0 and self._selected_rows >= max_output_rows:
            # Already at limit, but check if we still need coverage
            if ensure_coverage and not self._all_categorical_covered():
                # Allow more rows to complete coverage
                pass
            else:
                return False

        # Check for duplicate pattern (skip if already have same signature)
        if self._is_duplicate_pattern(row):
            self._counters.add_counter('sampler-duplicate-skipped-rows', 1)
            return False

        # Check for aggregation row
        is_aggregation = detect_aggregation and self._is_aggregation_row(row)
        if is_aggregation:
            # Deprioritize aggregation rows but allow a few
            if self._selected_aggregation_rows >= self._max_aggregation_rows:
                self._counters.add_counter('sampler-aggregation-skipped-rows', 1)
                return False

        # Coverage-first logic: prioritize rows that cover uncovered values
        if ensure_coverage and self._prescan_complete:
            if self._covers_new_categorical_value(row):
                self._counters.add_counter('sampler-coverage-selected-rows', 1)
                return True

            # Check if row extends numeric range coverage
            if self._extends_numeric_range(row):
                self._counters.add_counter('sampler-range-selected-rows', 1)
                return True

            # If all categorical values are covered, apply random sampling
            if self._all_categorical_covered():
                # Check if we're under the max rows limit
                if max_output_rows > 0 and self._selected_rows >= max_output_rows:
                    return False
                # Apply random sampling for additional diversity
                if sample_rate < 0:
                    sample_rate = self._config.get('sampler_rate')
                if sample_rate > 0 and random.random() <= sample_rate:
                    self._counters.add_counter('sampler-random-fill-rows', 1)
                    return True
                return False

        # Original logic (fallback when coverage is disabled or prescan not done)
        max_rows = self._config.get('sampler_output_rows')
        if max_rows > 0 and self._selected_rows >= max_rows:
            return False

        max_count = self._config.get('sampler_rows_per_key', 3)
        max_uniques_per_col = self._config.get('sampler_uniques_per_column', 10)
        for index in range(len(row)):
            # Skip columns not in unique_columns list
            if not self._should_track_column(index):
                continue
            value = row[index]
            value_count = self._get_column_count(index, value)
            if value_count == 0 or value_count < max_count:
                # This is a new value for this column.
                col_counts = self._column_counts.get(index, {})
                if len(col_counts) < max_uniques_per_col:
                    # Column has few unique values. Select this row for column.
                    self._counters.add_counter('sampler-selected-rows', 1)
                    self._counters.add_counter(
                        f'sampler-selected-column-{index}', 1)
                    return True

        # No new unique value for the row.
        # Check random sampler.
        if sample_rate < 0:
            sample_rate = self._config.get('sampler_rate')
        if random.random() <= sample_rate:
            self._counters.add_counter('sampler-sampled-rows', 1)
            return True
        return False

    def sample_csv_file(self, input_file: str, output_file: str = '') -> str:
        """Emits a sample of rows from an input file into an output file.

        This method reads a CSV file, selects a sample of rows based on the
        configured criteria, and writes the selected rows to an output file.

        When sampler_unique_columns is configured, the method processes all
        header rows (up to header_rows config) to locate the specified column
        names. If any requested columns are not found within the header rows,
        a ValueError is raised.

        Args:
            input_file: The path to the input CSV file.
            output_file: The path to the output CSV file. If not provided, a
              temporary file will be created.

        Returns:
            The path to the output file with the sampled rows.

        Raises:
            ValueError: If sampler_unique_columns is configured and any of the
              specified column names are not found within the first header_rows
              rows of the input file.

        Usage:
            sampler = DataSampler()
            sampler.sample_csv_file('input.csv', 'output.csv')
        """
        max_rows = self._config.get('sampler_output_rows')
        sample_rate = self._config.get('sampler_rate')
        header_rows = self._config.get('header_rows', 1)
        input_files = file_util.file_get_matching(input_file)
        if not input_files:
            return None

        # Auto-detect header rows if enabled
        auto_detect_headers = self._config.get('sampler_auto_detect_headers', True)
        if auto_detect_headers and header_rows == 1:
            # Only auto-detect if default value (1) is being used
            detected_headers = self._auto_detect_header_rows(input_files[0])
            header_rows = detected_headers
        output_delimiter = self._config.get('output_delimiter')
        if not output_file:
            # Save in the same directory as input with naming convention sampled_data.csv
            input_dir = os.path.dirname(input_files[0])
            output_file = os.path.join(input_dir, 'sampled_data.csv')
        # Set sampling rate by file size
        num_rows = file_util.file_estimate_num_rows(input_files)

        # NEW: Early exit for tiny datasets
        min_rows = self._config.get('sampler_min_rows', 40)
        if num_rows and num_rows <= min_rows:
            if self._config.get('sampler_verbose', True):
                logging.info(
                    f'Dataset has {num_rows} rows (≤ min {min_rows}). '
                    'Outputting entire dataset without sampling.'
                )
            # Just copy the entire file
            return self._copy_entire_file(input_files[0], output_file, header_rows, output_delimiter)

        if num_rows and self._config.get('sampler_rate') < 0:
            if max_rows > 0:
                sample_rate = float(max_rows) / float(num_rows)
                logging.debug(
                    f'Sampling rate for {input_files}: {sample_rate} for {num_rows} rows'
                )

        # Pre-scan phase: detect categorical columns if auto-detect is enabled
        auto_detect = self._config.get('sampler_auto_detect_categorical', True)
        ensure_coverage = self._config.get('sampler_ensure_coverage', True)

        if auto_detect and ensure_coverage:
            self._prescan_for_categorical_columns(input_files, header_rows)

        # Get sample rows from each input file.
        for input_index in range(len(input_files)):
            file = input_files[input_index]
            input_encoding = self._config.get('input_encoding')
            if not input_encoding:
                input_encoding = file_util.file_get_encoding(file)
            with file_util.FileIO(file, encoding=input_encoding) as csv_file:
                csv_options = {'delimiter': self._config.get('input_delimiter')}
                csv_options = file_util.file_get_csv_reader_options(
                    file, csv_options)
                if not output_delimiter:
                    # No output delimiter set. Use same as input.
                    output_delimiter = csv_options.get('delimiter', ',')
                output_mode = 'w' if input_index == 0 else 'a'
                # Write sample rows from current input
                with file_util.FileIO(output_file, mode=output_mode) as output:
                    csv_writer = csv.writer(output,
                                            delimiter=output_delimiter,
                                            doublequote=False,
                                            escapechar='\\')
                    logging.level_debug() and logging.debug(
                        f'Sampling rows from {file} with config: {self._config.get_configs()}'
                    )
                    # Examine each input row for any unique column values
                    csv_reader = csv.reader(csv_file, **csv_options)
                    row_index = 0
                    for row in csv_reader:
                        self._counters.add_counter('sampler-input-row', 1)
                        row_index += 1
                        # Process and write header rows from the first input file.
                        if row_index <= header_rows and input_index == 0:
                            self._process_header_row(row)
                            csv_writer.writerow(row)
                            self._counters.add_counter('sampler-header-rows', 1)
                            # After processing all header rows, validate that all
                            # requested unique columns were found
                            if row_index == header_rows and self._unique_column_names:
                                found = set(self._unique_column_indices.keys())
                                missing = set(self._unique_column_names) - found
                                if missing:
                                    logging.error(
                                        'Failed to map unique columns %s within %d header '
                                        'row(s). Found: %s. Missing: %s. Increase '
                                        'header_rows or verify column names.',
                                        self._unique_column_names, header_rows,
                                        found or 'none', missing)
                                    raise ValueError(
                                        f'Missing unique columns in headers: {missing}'
                                    )
                            continue
                        # Check if input row has any unique values to be output
                        if self.select_row(row, sample_rate):
                            self._add_row_counts(row)
                            # Mark categorical values as covered
                            if self._prescan_complete:
                                self._mark_values_covered(row)
                            # Track row signature to avoid duplicates
                            sig = self._get_row_signature(row)
                            self._selected_signatures.add(sig)
                            # Track aggregation rows
                            if self._is_aggregation_row(row):
                                self._selected_aggregation_rows += 1
                            # Update numeric range coverage
                            if self._numeric_ranges:
                                self._update_numeric_coverage(row)
                            csv_writer.writerow(row)
                            logging.level_debug() and logging.log(
                                2, f'Selecting row:{file}:{row_index}')

                        # Check stopping conditions
                        max_output = self._config.get('sampler_max_output_rows', 0)
                        if max_output > 0 and self._selected_rows >= max_output:
                            if self._all_categorical_covered():
                                break
                        elif max_rows > 0 and self._selected_rows >= max_rows:
                            # Got enough sample output rows (legacy behavior)
                            break

                # Log coverage stats if using coverage mode
                if self._prescan_complete and self._categorical_columns:
                    stats = self._get_coverage_stats()
                    for col_name, col_stats in stats['columns'].items():
                        logging.info(
                            f'Coverage for {col_name}: {col_stats["covered"]}/{col_stats["total"]} values'
                        )

        # NEW: Minimum row guarantee - add more rows if needed
        min_rows = self._config.get('sampler_min_rows', 40)
        max_rows_target = self._config.get('sampler_max_rows', 80)

        if self._selected_rows < min_rows:
            rows_needed = min_rows - self._selected_rows
            if self._config.get('sampler_verbose', True):
                logging.info(
                    f'Categorical coverage produced {self._selected_rows} rows. '
                    f'Adding {rows_needed} random rows to reach minimum ({min_rows}).'
                )
            self._add_random_rows_to_output(input_files, output_file, header_rows, rows_needed, output_delimiter)

        elif self._selected_rows < max_rows_target:
            rows_to_add = min(max_rows_target - self._selected_rows, num_rows - self._selected_rows if num_rows else 0)
            if rows_to_add > 0 and self._config.get('sampler_verbose', True):
                logging.info(
                    f'Adding {rows_to_add} more random rows to approach target ({max_rows_target}).'
                )
            if rows_to_add > 0:
                self._add_random_rows_to_output(input_files, output_file, header_rows, rows_to_add, output_delimiter)

        logging.info(
            f'Sampled {self._selected_rows} rows from {input_files} into {output_file}'
        )
        logging.level_debug() and logging.debug(
            f'Column counts: {self._column_counts}')
        return output_file


def sample_csv_file(input_file: str,
                    output_file: str = '',
                    config: dict = None) -> str:
    """Samples a CSV file and returns the path to the sampled file.

    This function provides a convenient way to sample a CSV file with a single
    function call. It creates a DataSampler instance and uses it to perform the
    sampling.

    Args:
        input_file: The path to the input CSV file.
        output_file: The path to the output CSV file. If not provided, a
          temporary file will be created.
        config: A dictionary of configuration parameters for sampling. The
          supported parameters are:
          - sampler_output_rows: The maximum number of rows to include in the
            sample.
          - sampler_rate: The sampling rate to use for random selection.
          - header_rows: The number of header rows to copy from the input file
            and search for sampler_unique_columns. Increase this if column names
            appear in later header rows (e.g., after a title row).
          - sampler_rows_per_key: The number of rows to select for each unique
            key.
          - sampler_column_regex: A regular expression to filter column values.
          - sampler_unique_columns: A comma-separated list of column names to
            use for selecting unique rows. Column names must appear within the
            first header_rows rows or ValueError will be raised.
          - input_delimiter: The delimiter used in the input file.
          - output_delimiter: The delimiter to use in the output file.
          - input_encoding: The encoding of the input file.

    Returns:
        The path to the output file with the sampled rows.

    Raises:
        ValueError: If sampler_unique_columns is configured and any of the
          specified column names are not found within the first header_rows
          rows of the input file.

    Usage:
        # Basic usage with default settings
        sample_csv_file('input.csv', 'output.csv')

        # Sample with a specific number of output rows and a sampling rate
        config = {
            'sampler_output_rows': 50,
            'sampler_rate': 0.1,
        }
        sample_csv_file('input.csv', 'output.csv', config)

        # Sample a file with a semicolon delimiter and two header rows
        config = {
            'input_delimiter': ';',
            'header_rows': 2,
        }
        sample_csv_file('input.csv', 'output.csv', config)
    """
    if config is None:
        config = {}
    data_sampler = DataSampler(config_dict=config)
    return data_sampler.sample_csv_file(input_file, output_file)


def get_default_config() -> dict:
    """Returns a dictionary of default configuration parameter values.

    This function retrieves the default values of the configuration parameters
    from the command-line flags.

    Returns:
        A dictionary of default configuration parameter values.
    """
    # Use default values of flags for tests
    if not _FLAGS.is_parsed():
        _FLAGS.mark_as_parsed()
    return {
        'sampler_rate': _FLAGS.sampler_rate,
        'sampler_input': _FLAGS.sampler_input,
        'sampler_output': _FLAGS.sampler_output,
        'sampler_output_rows': _FLAGS.sampler_output_rows,
        'header_rows': _FLAGS.sampler_header_rows,
        'sampler_rows_per_key': _FLAGS.sampler_rows_per_key,
        'sampler_column_regex': _FLAGS.sampler_column_regex,
        'sampler_unique_columns': _FLAGS.sampler_unique_columns,
        'input_delimiter': _FLAGS.sampler_input_delimiter,
        'output_delimiter': _FLAGS.sampler_output_delimiter,
        'input_encoding': _FLAGS.sampler_input_encoding,
        # New categorical detection and coverage settings
        'sampler_categorical_threshold': _FLAGS.sampler_categorical_threshold,
        'sampler_auto_detect_categorical': _FLAGS.sampler_auto_detect_categorical,
        'sampler_ensure_coverage': _FLAGS.sampler_ensure_coverage,
        'sampler_id_column_patterns': _FLAGS.sampler_id_column_patterns,
        'sampler_max_output_rows': _FLAGS.sampler_max_output_rows,
        # Smart column analysis and aggregation detection settings
        'sampler_smart_columns': _FLAGS.sampler_smart_columns,
        'sampler_detect_aggregation': _FLAGS.sampler_detect_aggregation,
        'sampler_constant_threshold': _FLAGS.sampler_constant_threshold,
        'sampler_correlation_threshold': _FLAGS.sampler_correlation_threshold,
        'sampler_verbose': _FLAGS.sampler_verbose,
        'sampler_aggregation_keywords': _FLAGS.sampler_aggregation_keywords,
        'sampler_max_aggregation_rows': _FLAGS.sampler_max_aggregation_rows,
        'sampler_auto_detect_headers': _FLAGS.sampler_auto_detect_headers,
        'sampler_skip_empty_columns': _FLAGS.sampler_skip_empty_columns,
        'sampler_detect_footers': _FLAGS.sampler_detect_footers,
        'sampler_footer_keywords': _FLAGS.sampler_footer_keywords,
    }


def main(_):
    sample_csv_file(_FLAGS.sampler_input, _FLAGS.sampler_output)


if __name__ == '__main__':
    app.run(main)
