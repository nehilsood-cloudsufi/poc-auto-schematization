"""Smart log filter for validation output.

Transforms high-volume counter logs into high-signal patterns:
- Key metrics (input/output counts, coverage)
- Error type aggregates
- VALUE PATTERN DETECTION: Cluster unmapped values by type to identify failing columns

This module replaces the complex counter_feedback.py (~970 lines) with a simpler,
more focused approach (~200 lines) that produces concise, actionable feedback.

Usage:
    from src.pipeline.validation.log_filter import filter_counters, extract_sample_errors

    filtered = filter_counters(Path('output/dataset/processed_counters.txt'))
    print(filtered.to_summary())  # Concise ~50-80 line feedback
"""

import csv
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import Counter


@dataclass
class ValuePattern:
    """Pattern detected in unmapped values.

    Attributes:
        pattern_type: Category like 'numeric', 'state_code', 'place_name', 'year', etc.
        sample_values: Representative examples of this pattern
        count: Total occurrences of this pattern type
        likely_column: Inferred column name based on pattern
    """
    pattern_type: str
    sample_values: List[str] = field(default_factory=list)
    count: int = 0
    likely_column: str = ""


@dataclass
class FilteredLogs:
    """Clean, concise validation summary with pattern analysis.

    Attributes:
        input_rows: Number of rows in input data
        output_rows: Number of rows in output (observations)
        coverage_pct: Output/input percentage
        success_rate_critical: True if coverage < 10%
        errors: Error type to count mapping (max 10 types)
        warnings: Warning type to count mapping (max 5 types)
        statvars_generated: Number of unique StatVars
        observations_generated: Total observations
        unmapped_value_patterns: Patterns detected in unmapped values
        top_unmapped_values: Most frequent unmapped values
    """
    input_rows: int = 0
    output_rows: int = 0
    coverage_pct: float = 0.0
    success_rate_critical: bool = False

    errors: Dict[str, int] = field(default_factory=dict)
    warnings: Dict[str, int] = field(default_factory=dict)

    statvars_generated: int = 0
    observations_generated: int = 0

    unmapped_value_patterns: List[ValuePattern] = field(default_factory=list)
    top_unmapped_values: List[Tuple[str, int]] = field(default_factory=list)

    def to_summary(self) -> str:
        """Generate concise, actionable summary for LLM.

        Returns:
            Formatted markdown string (~50-80 lines) with:
            - Validation metrics
            - Error summary
            - Unmapped value analysis with fix suggestions
        """
        lines = [
            "## Validation Summary",
            f"- Input rows: {self.input_rows}",
            f"- Output rows: {self.output_rows}",
            f"- Coverage: {self.coverage_pct:.1f}%",
        ]

        if self.success_rate_critical:
            lines.append("- **STATUS: CRITICAL FAILURE** (coverage < 10%)")

        lines.extend([
            f"- StatVars generated: {self.statvars_generated}",
            f"- Observations: {self.observations_generated}",
        ])

        # Error summary
        if self.errors:
            lines.append("\n## Errors (must fix)")
            for err_type, count in sorted(self.errors.items(), key=lambda x: -x[1])[:5]:
                clean_name = err_type.replace('error-', '').replace('-', ' ')
                lines.append(f"- {clean_name}: {count:,}")

        # Value pattern analysis (the key diagnostic info!)
        if self.unmapped_value_patterns:
            lines.append("\n## Unmapped Value Analysis")
            lines.append("The PVMAP is missing mappings for these value patterns:")

            for pattern in self.unmapped_value_patterns[:3]:
                lines.append(f"\n### Pattern: {pattern.pattern_type} ({pattern.count:,} occurrences)")
                if pattern.likely_column:
                    lines.append(f"**Likely Column:** {pattern.likely_column}")
                sample_display = ', '.join(f"'{v}'" for v in pattern.sample_values[:5])
                lines.append(f"**Sample Values:** {sample_display}")

                # Add fix suggestion based on pattern type
                fix = _get_fix_suggestion(pattern.pattern_type)
                if fix:
                    lines.append(f"**Fix:** {fix}")

        elif self.top_unmapped_values:
            lines.append("\n## Top Unmapped Values")
            for val, count in self.top_unmapped_values[:10]:
                lines.append(f"- `{val}`: {count:,}")

        # Warnings (only if no critical errors)
        if self.warnings and not self.errors:
            lines.append("\n## Warnings")
            for warn_type, count in sorted(self.warnings.items(), key=lambda x: -x[1])[:3]:
                clean_name = warn_type.replace('warning-', '').replace('-', ' ')
                lines.append(f"- {clean_name}: {count:,}")

        return '\n'.join(lines)


def _get_fix_suggestion(pattern_type: str) -> str:
    """Return fix suggestion based on value pattern type.

    Args:
        pattern_type: The detected pattern type

    Returns:
        Actionable fix suggestion string
    """
    fixes = {
        'state_code': "Map state codes to DCIDs: 'AL' -> 'geoId/01', or use State FIPS column instead",
        'place_name': "Place names cannot be resolved directly. Use FIPS codes or add dcid:geoId/ prefix",
        'year': "Add year column mapping to observationDate property",
        'fips_code': "Add zero-padding if needed: use 'dcid:geoId/{Data:02d}' for 2-digit FIPS",
        'enum': "Add value mappings for these enum values in the PVMAP",
        'numeric_id': "These may be unmapped ID columns (NCESID, SCHID). Check if column is in PVMAP keys",
        'numeric': "These are numeric values - check if column should be mapped to 'value' property",
        'empty': "Empty values detected - column may have missing data",
    }
    return fixes.get(pattern_type, "")


def _classify_value(value: str) -> str:
    """Classify an unmapped value to detect pattern type.

    Args:
        value: The unmapped value string

    Returns:
        Pattern type string
    """
    if not value or value.strip() == '-' or value.strip() == '':
        return 'empty'

    value = value.strip()

    # State codes (2-letter uppercase)
    if re.match(r'^[A-Z]{2}$', value):
        return 'state_code'

    # Year (4 digits, 1900-2100)
    if re.match(r'^(19|20)\d{2}$', value):
        return 'year'

    # FIPS-like codes (2-5 digit zero-padded)
    if re.match(r'^0\d{1,4}$', value):
        return 'fips_code'

    # Numeric IDs (long numbers, 6+ digits)
    if re.match(r'^\d{6,}$', value):
        return 'numeric_id'

    # Small integers (likely IDs or counts)
    if re.match(r'^\d{1,5}$', value):
        return 'numeric'

    # Place names (title case words)
    if re.match(r'^[A-Z][a-z]+(\s+[A-Z][a-z]+)*$', value):
        return 'place_name'

    # All caps place names (ALBERTVILLE, HOOVER CITY)
    if re.match(r'^[A-Z]+(\s+[A-Z]+)*$', value) and len(value) > 2:
        return 'place_name'

    # Enum-like values (short strings, not all digits)
    if len(value) < 30 and not value.isdigit():
        return 'enum'

    return 'unknown'


def filter_counters(counters_path: Path) -> FilteredLogs:
    """Extract useful metrics and analyze value patterns from counter file.

    Key improvements over simple filtering:
    1. Extracts aggregate metrics (coverage, statvars)
    2. Analyzes individual value failures to detect PATTERNS
    3. Clusters values by type to identify failing columns

    Args:
        counters_path: Path to the processed_counters.txt file

    Returns:
        FilteredLogs with metrics and pattern analysis
    """
    result = FilteredLogs()

    if not counters_path.exists():
        return result

    # Key metrics to extract from prefixed counters (before filtering)
    # These are important metrics that may only appear in prefixed form
    key_metrics_patterns = {
        'input-rows-processed': 'input_rows',
        'generated-svobs': 'observations_generated',
        'generated-unique-statvars': 'statvars_generated',
    }

    # Patterns to IGNORE (operational noise)
    noise_patterns = [
        r'process-mem',                 # Memory stats
        r'process-time',                # Timing stats
        r'processing[-_]rate',          # Rate stats
        r'processing[-_]time',          # Time stats
        r'start_time',                  # Timestamps
        r'elapsed_time',                # Timing
        r'remaining_time',              # Timing
        r'_/[Uu]sers/',                 # File path variants
        r'_/Users/',                    # File paths
        r'num-rows-/',                  # File path variants
        r'spell-',                      # Spell check
        r'urls-',                       # URL checks
        r'pvs-added',                   # Internal tracking
    ]
    noise_regex = re.compile('|'.join(noise_patterns))

    raw_counters: Dict[str, int] = {}
    unmapped_values: List[Tuple[str, int]] = []
    prefixed_metrics: Dict[str, int] = {}  # Key metrics from prefixed counters

    try:
        with open(counters_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) < 2:
                    continue

                key = row[0].strip().strip('"')
                try:
                    count = int(float(row[1].strip().strip('"')))
                except (ValueError, IndexError):
                    continue

                # Extract key metrics from prefixed counters BEFORE filtering noise
                # These may only appear in prefixed form (e.g., "1:process_input_input-rows-processed")
                for metric_pattern, attr_name in key_metrics_patterns.items():
                    if metric_pattern in key and not key.endswith('.csv'):
                        # Only store first occurrence (avoid file-specific duplicates)
                        if attr_name not in prefixed_metrics:
                            prefixed_metrics[attr_name] = count

                # Skip operational noise (but after extracting key metrics)
                if noise_regex.search(key):
                    continue

                # Skip prefixed counters (1:process_input_*) except for key metrics already extracted
                if re.match(r'^\d+:', key):
                    continue

                # Collect individual unmapped values for pattern analysis
                if key.startswith('warning-missing-property-key_'):
                    value = key.replace('warning-missing-property-key_', '')
                    # Filter out file paths and noise
                    if value and not value.startswith('/') and not value.startswith(' '):
                        unmapped_values.append((value, count))
                else:
                    raw_counters[key] = count

    except Exception:
        return result

    # Extract key metrics - prefer non-prefixed, fall back to prefixed
    result.input_rows = raw_counters.get('input-rows-processed', 0)
    if result.input_rows == 0:
        result.input_rows = prefixed_metrics.get('input_rows', 0)

    result.output_rows = raw_counters.get('output-svobs-csv-rows', 0)

    result.statvars_generated = raw_counters.get('generated-unique-statvars', 0)
    if result.statvars_generated == 0:
        result.statvars_generated = prefixed_metrics.get('statvars_generated', 0)

    result.observations_generated = raw_counters.get('generated-svobs', 0)
    if result.observations_generated == 0:
        result.observations_generated = prefixed_metrics.get('observations_generated', 0)

    # Also check svobs-added if generated-svobs not available
    if result.observations_generated == 0:
        result.observations_generated = raw_counters.get('svobs-added', 0)

    # Calculate coverage
    if result.input_rows > 0:
        result.coverage_pct = (result.output_rows / result.input_rows) * 100
        result.success_rate_critical = result.coverage_pct < 10

    # Extract errors (base types only, no suffixes)
    for key, value in raw_counters.items():
        if key.startswith('error-') and '_' not in key:
            result.errors[key] = value
        elif (key.startswith('warning-') or key.startswith('dropped-')) and '_' not in key:
            result.warnings[key] = value

    # Analyze unmapped values to detect patterns
    if unmapped_values:
        result.unmapped_value_patterns = _analyze_value_patterns(unmapped_values)

        # Also keep top unmapped values for reference
        value_counts: Counter = Counter()
        for val, count in unmapped_values:
            value_counts[val] += count
        result.top_unmapped_values = value_counts.most_common(20)

    return result


def _analyze_value_patterns(unmapped_values: List[Tuple[str, int]]) -> List[ValuePattern]:
    """Cluster unmapped values by type to identify failing columns.

    Args:
        unmapped_values: List of (value, count) tuples

    Returns:
        List of ValuePattern objects sorted by count
    """
    patterns: Dict[str, ValuePattern] = {}

    for value, count in unmapped_values:
        pattern_type = _classify_value(value)
        if pattern_type == 'empty':
            continue

        if pattern_type not in patterns:
            patterns[pattern_type] = ValuePattern(
                pattern_type=pattern_type,
                sample_values=[],
                count=0
            )

        patterns[pattern_type].count += count
        if len(patterns[pattern_type].sample_values) < 10:
            # Avoid duplicates in samples
            if value not in patterns[pattern_type].sample_values:
                patterns[pattern_type].sample_values.append(value)

    # Infer likely column names based on pattern
    column_hints = {
        'state_code': 'LEA_STATE, State Postal Code, or similar state column',
        'place_name': 'City/County/School Name column',
        'year': 'Year or observationDate column',
        'fips_code': 'State FIPS Code or District ID column',
        'numeric_id': 'NCESID, SCHID, LEAID, or similar ID column',
        'numeric': 'Numeric column (possibly value or ID)',
        'enum': 'Categorical column with unmapped values',
    }
    for pattern in patterns.values():
        pattern.likely_column = column_hints.get(pattern.pattern_type, '')

    # Sort by count (most common patterns first)
    return sorted(patterns.values(), key=lambda p: -p.count)


def extract_sample_errors(stderr: str, max_samples: int = 5) -> str:
    """Extract unique representative error messages from stderr.

    Args:
        stderr: Standard error output from validation subprocess
        max_samples: Maximum number of unique samples to return

    Returns:
        Formatted string with unique error samples
    """
    if not stderr:
        return ""

    seen: set = set()
    samples: List[str] = []

    for line in stderr.split('\n'):
        if 'ERROR' in line or 'WARNING' in line:
            # Normalize line (remove timestamps, line numbers, specific values)
            normalized = re.sub(r'\d+', 'N', line)
            normalized = re.sub(r"'[^']+'\s*,?\s*", "'X', ", normalized)
            if normalized not in seen and len(samples) < max_samples:
                seen.add(normalized)
                samples.append(line.strip()[:200])

    return '\n'.join(samples) if samples else ""


def generate_concise_feedback(
    counters_path: Path,
    stderr: Optional[str] = None,
    max_error_samples: int = 5
) -> str:
    """Generate concise feedback from counters file and optional stderr.

    Convenience function that combines filter_counters and extract_sample_errors.

    Args:
        counters_path: Path to the processed_counters.txt file
        stderr: Optional stderr output from validation subprocess
        max_error_samples: Maximum error samples to include

    Returns:
        Concise feedback string ready for LLM consumption
    """
    filtered = filter_counters(counters_path)
    feedback = filtered.to_summary()

    if stderr:
        error_samples = extract_sample_errors(stderr, max_error_samples)
        if error_samples:
            feedback += f"\n\n## Sample Error Messages\n```\n{error_samples}\n```"

    return feedback


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'FilteredLogs',
    'ValuePattern',
    'filter_counters',
    'extract_sample_errors',
    'generate_concise_feedback',
]
