"""Smart log filter for validation output.

Transforms high-volume counter logs into high-signal patterns:
- Key metrics (input/output counts, coverage)
- Error type aggregates
- VALUE PATTERN DETECTION: Cluster unmapped values by type to identify failing columns
- RICH SIGNAL EXTRACTION: Per-property cardinality, per-StatVar observation counts,
  dropped StatVars, unresolved placeholder refs, place failures, input structure

This module replaces the complex counter_feedback.py (~970 lines) with a simpler,
more focused approach that produces actionable feedback.

Usage:
    from src.pipeline.validation.log_filter import filter_counters, extract_sample_errors

    filtered = filter_counters(Path('output/dataset/processed_counters.txt'))
    print(filtered.to_summary())  # Rich multi-section feedback
"""

import csv
import logging
import re
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field
from collections import Counter


# ---------------------------------------------------------------------------
# Error priority, patterns, and iteration advice
# (ported from counter_feedback.py, trimmed to category + common_causes + fix)
# ---------------------------------------------------------------------------

ERROR_PRIORITY = [
    'error-pvmap-dropped-undefined-property',
    'error-unresolved-place',
    'error-statvar-missing-property',
    'error-svobs-missing-property',
    'error-mismatched-svobs',
    'error-duplicate-statvars',
    'error-aggregate-invalid-values',
    'error-invalid-multiply-factor',
]

ERROR_PATTERNS = {
    'error-pvmap-dropped-undefined-property': {
        'category': 'PVMAP Key Mismatch',
        'common_causes': [
            'Case mismatch (State FIPS vs state_fips)',
            'Typo in column name',
            'Column renamed or missing from input data',
        ],
        'fix': "Keys must match CSV headers EXACTLY (case-sensitive). Check for leading/trailing spaces and underscores vs spaces.",
    },
    'error-unresolved-place': {
        'category': 'Place Resolution',
        'common_causes': [
            'FIPS codes missing leading zeros (e.g., 6 instead of 06)',
            'Missing geoId/ prefix in observationAbout mapping',
            'Place names ambiguous without typeOf or containedInPlace context',
        ],
        'fix': "Use dcid:geoId/[NUMBER:02d] for FIPS codes, dcid:country/[DATA] for ISO codes. Ensure zero-padding for state/county codes.",
    },
    'error-statvar-missing-property': {
        'category': 'StatVar Definition Incomplete',
        'common_causes': [
            'Missing populationType (Person, Household, Establishment, etc.)',
            'Missing measuredProperty (count, income, area, etc.)',
            'Missing statType (Count, Mean, Median, Percent, etc.)',
        ],
        'fix': "Every StatVar needs populationType, measuredProperty, and statType. Add all three.",
    },
    'error-svobs-missing-property': {
        'category': 'Missing Observation Property',
        'common_causes': [
            'Missing observationAbout (place) mapping',
            'Missing observationDate mapping',
            'Missing value mapping',
        ],
        'fix': "Ensure observationAbout, observationDate, and value are ALL mapped. All three are required for every observation.",
    },
    'error-mismatched-svobs': {
        'category': 'Duplicate Observations',
        'common_causes': [
            'A dimension column (Gender, Age, Race) not mapped as StatVar qualifier',
            'Multiple measurement methods not differentiated',
            'Missing constraint property to distinguish rows',
        ],
        'fix': "Add qualifiers (gender, age, race) to differentiate observations. Rule: Place + Date + StatVar = ONE value only.",
    },
    'error-duplicate-statvars': {
        'category': 'Duplicate StatVars',
        'common_causes': [
            'Same measurement mapped multiple times',
            'Redundant PVMAP entries',
        ],
        'fix': "Remove duplicate StatVar definitions. Each unique property combination should define ONE StatVar.",
    },
    'error-aggregate-invalid-values': {
        'category': 'Aggregation Error',
        'common_causes': [
            'Non-numeric values in aggregation columns',
            'Missing or null values in aggregated fields',
        ],
        'fix': "Ensure numeric columns use [NUMBER] not [DATA]. Check for non-numeric values in measurement columns.",
    },
    'error-invalid-multiply-factor': {
        'category': 'Invalid Multiply Factor',
        'common_causes': [
            'Non-numeric multiply factor',
            'Invalid expression in value transformation',
        ],
        'fix': "Ensure multiply factors are valid numbers. Use standard numeric formats.",
    },
}

ITERATION_ADVICE = {
    0: "ATTEMPT 1: Focus on structural fixes -- key matching, required properties (observationAbout, observationDate, value), correct archetype.",
    1: "ATTEMPT 2: Structure should be sound. Focus on value-level fixes -- place resolution format, placeholder templates, enum values.",
    2: "ATTEMPT 3 (FINAL): Preserve all working rows. Only fix the highest-impact remaining error. Do not restructure.",
}


# ---------------------------------------------------------------------------
# Helper functions for error analysis
# ---------------------------------------------------------------------------

def _sort_errors_by_priority(errors: Dict[str, int]) -> List[Tuple[str, int]]:
    """Sort errors by ERROR_PRIORITY index; unknown errors sort last by count descending."""
    def _key(item):
        name, count = item
        try:
            idx = ERROR_PRIORITY.index(name)
        except ValueError:
            # Check prefix match
            for i, p in enumerate(ERROR_PRIORITY):
                if name.startswith(p):
                    return (i, -count)
            return (len(ERROR_PRIORITY), -count)
        return (idx, -count)
    return sorted(errors.items(), key=_key)


def _get_error_pattern(error_type: str) -> Optional[Dict]:
    """Lookup error_type in ERROR_PATTERNS with prefix matching."""
    if error_type in ERROR_PATTERNS:
        return ERROR_PATTERNS[error_type]
    for pattern_name, pattern_info in ERROR_PATTERNS.items():
        if error_type.startswith(pattern_name):
            return pattern_info
    return None


def detect_systematic_patterns(
    error_type: str,
    examples: List[Tuple[str, int]],
    total_count: int,
) -> List[Dict]:
    """Detect single_value, few_values, and format patterns in error examples.

    Args:
        error_type: The base error type string.
        examples: List of (failing_value, count) tuples.
        total_count: Total error count for this error type.

    Returns:
        List of detected pattern dicts sorted by confidence.
    """
    if not examples or total_count < 5:
        return []

    patterns: List[Dict] = []
    values = [v for v, _ in examples]

    # Single value pattern
    if len(examples) == 1:
        patterns.append({
            'type': 'single_value',
            'error': error_type,
            'value': examples[0][0],
            'count': total_count,
            'confidence': 1.0,
            'description': f"All {total_count} '{error_type}' errors have value='{examples[0][0]}'",
        })

    # Few values pattern
    elif len(examples) <= max(2, int(total_count * 0.2)) and total_count >= 10:
        patterns.append({
            'type': 'few_values',
            'error': error_type,
            'values': values[:5],
            'count': total_count,
            'confidence': 0.8,
            'description': f"Only {len(examples)} unique values causing {total_count} '{error_type}' errors",
        })

    # Format pattern
    fmt = _detect_format_pattern(values)
    if fmt:
        patterns.append({
            'type': 'format_pattern',
            'error': error_type,
            'pattern': fmt['pattern'],
            'examples': fmt['examples'],
            'count': total_count,
            'confidence': fmt['confidence'],
            'description': fmt['description'],
        })

    patterns.sort(key=lambda x: -x['confidence'])
    return patterns


def _detect_format_pattern(values: List[str]) -> Optional[Dict]:
    """Detect missing_leading_zeros or missing_dcid_prefix patterns."""
    if not values:
        return None

    # Missing leading zeros (common FIPS issue)
    single_digit_count = sum(1 for v in values if v.isdigit() and len(v) == 1)
    if single_digit_count > len(values) * 0.5 and len(values) >= 3:
        return {
            'pattern': 'missing_leading_zeros',
            'examples': [v for v in values if v.isdigit() and len(v) == 1][:3],
            'confidence': 0.9,
            'description': "Values appear to be missing leading zeros (e.g., '6' should be '06' for California)",
        }

    # Missing dcid: prefix
    dcid_candidates = sum(
        1 for v in values
        if v and not v.startswith('dcid:') and (
            v.startswith('geoId/') or
            v.startswith('country/') or
            v in ('Person', 'Household', 'HousingUnit', 'Establishment')
        )
    )
    if dcid_candidates > len(values) * 0.5:
        return {
            'pattern': 'missing_dcid_prefix',
            'examples': values[:3],
            'confidence': 0.85,
            'description': "Values appear to be missing 'dcid:' prefix",
        }

    return None


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
    """Clean, actionable validation summary with rich pattern analysis.

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

        property_cardinality: Per-output-property unique value counts
        fragmentation_ratio: unique_statvars / total_observations
        statvars_with_obs: Per-StatVar observation counts (sorted desc)
        dropped_statvars: StatVars with 0 observations (wasted PVMAP rows)
        statvars_generated_counts: Per-StatVar generation counts
        unresolved_refs: Unresolved placeholder references (name -> count)
        top_missing_keys: All unmapped values sorted by count desc
        unresolved_places: Place values that failed resolution
        place_failure_statvars: StatVars that lost obs due to place failures
        missing_place_statvars: StatVars with no observationAbout mapping
        input_header_rows: Number of header rows detected
        input_data_rows: Number of data rows in input
        input_sections: Number of sections in input file
        spell_check_errors: StatVar names with spelling issues
        dropped_mcf_statvars: StatVars dropped at MCF output stage
        existing_nodes_from_api: Existing DC nodes found via API
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

    # Rich signal fields
    property_cardinality: Dict[str, int] = field(default_factory=dict)
    fragmentation_ratio: float = 0.0
    statvars_with_obs: List[Tuple[str, int]] = field(default_factory=list)
    dropped_statvars: List[str] = field(default_factory=list)
    statvars_generated_counts: List[Tuple[str, int]] = field(default_factory=list)
    unresolved_refs: Dict[str, int] = field(default_factory=dict)
    top_missing_keys: List[Tuple[str, int]] = field(default_factory=list)
    unresolved_places: List[Tuple[str, int]] = field(default_factory=list)
    place_failure_statvars: Dict[str, int] = field(default_factory=dict)
    missing_place_statvars: List[Tuple[str, int]] = field(default_factory=list)
    input_header_rows: int = 0
    input_data_rows: int = 0
    input_sections: int = 0
    spell_check_errors: int = 0
    dropped_mcf_statvars: int = 0
    existing_nodes_from_api: int = 0

    # Enrichment fields (ported from counter_feedback.py)
    error_examples: Dict[str, List[Tuple[str, int]]] = field(default_factory=dict)
    attempt_number: Optional[int] = None

    def to_summary(self) -> str:
        """Generate rich, actionable summary for LLM feedback.

        Returns:
            Formatted markdown string with every diagnostic signal.
            Each line is actionable — no filler, no truncation.
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

        # Input structure
        if self.input_header_rows or self.input_data_rows or self.input_sections:
            lines.append("")
            lines.append("## Input Structure")
            lines.append(f"- Header rows: {self.input_header_rows}")
            lines.append(f"- Data rows: {self.input_data_rows}")
            lines.append(f"- Sections: {self.input_sections}")
            lines.append(f"- Total processed: {self.input_rows}")

        # Output property cardinality
        if self.property_cardinality:
            lines.append("")
            lines.append("## Output Property Cardinality")
            lines.append("For each output property, shows how many UNIQUE values were produced.")
            lines.append("A property with cardinality=1 means ALL observations map to the SAME value.")
            for prop, count in sorted(self.property_cardinality.items()):
                annotation = ""
                if prop == "observationAbout" and count == 1:
                    annotation = " [CRITICAL: Only 1 place resolved — geo column mapping is wrong or place values can't be resolved]"
                elif prop == "observationDate" and count == 1 and self.input_data_rows > 1:
                    annotation = " [WARNING: Only 1 unique date — either single-year dataset (OK) or date column not mapped]"
                elif prop == "value" and count == 1:
                    annotation = " [WARNING: Only 1 unique value — the value column is likely not mapped with [NUMBER]]"
                lines.append(f"- {prop}: {count}{annotation}")
            if self.fragmentation_ratio > 0:
                interp = _fragmentation_interpretation(self.fragmentation_ratio)
                lines.append(
                    f"- Fragmentation ratio: {self.fragmentation_ratio:.3f} "
                    f"({self.statvars_generated} unique StatVars / {self.observations_generated} observations)"
                )
                lines.append(f"  Interpretation: {interp}")

        # Error summary (priority-ordered with fix recipes)
        if self.errors:
            lines.append("")
            lines.append("## Errors (must fix)")
            sorted_errors = _sort_errors_by_priority(self.errors)
            for i, (err_type, count) in enumerate(sorted_errors, 1):
                pattern = _get_error_pattern(err_type)
                tag = f" [{pattern['category']}]" if pattern else ""
                clean_name = err_type.replace('error-', '').replace('-', ' ')
                lines.append(f"{i}. {clean_name}: {count:,}{tag}")

                # Debug examples (failing values)
                if err_type in self.error_examples:
                    examples = self.error_examples[err_type]
                    vals = ', '.join(f"'{v}' ({c})" for v, c in examples[:5])
                    lines.append(f"   Failing values: {vals}")

                # Fix recipe
                if pattern:
                    lines.append(f"   Common causes: {'; '.join(pattern['common_causes'])}")
                    lines.append(f"   Fix: {pattern['fix']}")

            # Systematic patterns section
            all_patterns: List[Dict] = []
            for err_type, count in sorted_errors:
                if err_type in self.error_examples:
                    pats = detect_systematic_patterns(
                        err_type, self.error_examples[err_type], count
                    )
                    all_patterns.extend(pats)
            if all_patterns:
                lines.append("")
                lines.append("## Systematic Error Patterns")
                for p in all_patterns[:5]:
                    lines.append(f"- [{p['type']}] {p['description']}")

        # StatVar observation breakdown
        if self.statvars_with_obs or self.dropped_statvars:
            lines.append("")
            lines.append("## StatVar Observation Breakdown")
            lines.append(
                f"Generated {self.statvars_generated} unique StatVars, "
                f"{self.observations_generated} total observations."
            )
            if self.statvars_with_obs:
                lines.append("")
                lines.append("### StatVars WITH observations (producing data):")
                for sv_name, count in self.statvars_with_obs[:40]:
                    lines.append(f"- {sv_name}: {count} observations")
                if len(self.statvars_with_obs) > 40:
                    lines.append(f"  ... and {len(self.statvars_with_obs) - 40} more")
            if self.dropped_statvars:
                lines.append("")
                lines.append("### StatVars DROPPED (generated but 0 observations — wasted PVMAP rows):")
                for sv_name in self.dropped_statvars[:40]:
                    lines.append(f"- {sv_name} (0 observations)")
                if len(self.dropped_statvars) > 40:
                    lines.append(f"  ... and {len(self.dropped_statvars) - 40} more")
                lines.append("These PVMAP rows should be fixed (wrong key name?) or removed to reduce noise.")

        # Unresolved placeholder references
        if self.unresolved_refs:
            total_unresolved = sum(self.unresolved_refs.values())
            lines.append("")
            lines.append("## Unresolved Placeholder References")
            lines.append("Placeholders that failed to resolve during cell value processing:")
            sorted_refs = sorted(self.unresolved_refs.items(), key=lambda x: -x[1])
            for ref_name, count in sorted_refs[:30]:
                lines.append(f"- [{ref_name.upper()}] template failed to resolve: {count} times")
            if len(sorted_refs) > 30:
                lines.append(f"  ... and {len(sorted_refs) - 30} more")
            lines.append(f"Total unresolved: {total_unresolved}")

        # Place resolution failures
        if self.place_failure_statvars or self.missing_place_statvars:
            lines.append("")
            lines.append("## Place Resolution Failures")
            if self.place_failure_statvars:
                total_dropped = sum(self.place_failure_statvars.values())
                lines.append(
                    f"{total_dropped} observations dropped because place values "
                    f"couldn't be resolved to Data Commons place DCIDs."
                )
                lines.append("")
                lines.append("### StatVars affected by place resolution failures:")
                sorted_pf = sorted(self.place_failure_statvars.items(), key=lambda x: -x[1])
                for sv_name, count in sorted_pf[:30]:
                    lines.append(f"- {sv_name}: {count} observations dropped")
                if len(sorted_pf) > 30:
                    lines.append(f"  ... and {len(sorted_pf) - 30} more")
            if self.missing_place_statvars:
                lines.append("")
                lines.append("### StatVars with NO observationAbout mapping at all:")
                for sv_name, count in self.missing_place_statvars[:30]:
                    lines.append(f"- {sv_name}: {count} observations missing place")
                if len(self.missing_place_statvars) > 30:
                    lines.append(f"  ... and {len(self.missing_place_statvars) - 30} more")
            lines.append("")
            lines.append(
                "Place resolution pipeline: already-DCID check -> PVMAP lookup -> Maps API."
            )
            lines.append(
                "If ALL places fail: the observationAbout column is likely mapped to a column "
                "with raw names instead of FIPS codes or DCIDs."
            )

        # Top unmatched input values (limit to top 20 to prevent token overflow)
        if self.top_missing_keys:
            total_missing = sum(c for _, c in self.top_missing_keys)
            lines.append("")
            lines.append("## Top Unmatched Input Values")
            lines.append(
                "These values went through ALL 5 key-matching levels "
                "(exact -> case-insensitive -> alphanumeric-only -> n-gram fragments -> substring) "
                "and STILL didn't match any PVMAP key."
            )
            lines.append(f"Total unmatched: {total_missing:,} values ({len(self.top_missing_keys):,} unique)")
            lines.append("")
            lines.append("### By frequency (top 40):")
            for val, count in self.top_missing_keys[:40]:
                pattern_type = _classify_value(val)
                pattern_label = f" ({pattern_type.upper()} pattern)" if pattern_type != 'unknown' else ""
                lines.append(f"- '{val}': {count:,} occurrences{pattern_label}")
            if len(self.top_missing_keys) > 40:
                remaining = len(self.top_missing_keys) - 40
                lines.append(f"  ... and {remaining:,} more unique values")

        # Value pattern analysis (existing)
        if self.unmapped_value_patterns:
            lines.append("")
            lines.append("## Unmapped Value Pattern Analysis")
            lines.append("Values clustered by detected type:")

            for pattern in self.unmapped_value_patterns:
                lines.append(f"\n### Pattern: {pattern.pattern_type} ({pattern.count:,} occurrences)")
                if pattern.likely_column:
                    lines.append(f"**Likely Column:** {pattern.likely_column}")
                sample_display = ', '.join(f"'{v}'" for v in pattern.sample_values[:5])
                lines.append(f"**Sample Values:** {sample_display}")
                fix = _get_fix_suggestion(pattern.pattern_type)
                if fix:
                    lines.append(f"**Fix:** {fix}")

        # Spelling issues
        if self.spell_check_errors > 0:
            lines.append("")
            lines.append("## Spelling Issues")
            lines.append(
                f"{self.spell_check_errors} StatVar name(s) flagged by spell checker. "
                f"Generated DCID names may have typos."
            )

        # MCF output
        if self.dropped_mcf_statvars > 0 or self.existing_nodes_from_api > 0:
            lines.append("")
            lines.append("## MCF Output")
            lines.append(f"- StatVars dropped at MCF output stage: {self.dropped_mcf_statvars}")
            lines.append(f"- Existing DC nodes found via API: {self.existing_nodes_from_api}")

        # Warnings (only if no critical errors)
        if self.warnings and not self.errors:
            lines.append("")
            lines.append("## Warnings")
            for warn_type, count in sorted(self.warnings.items(), key=lambda x: -x[1]):
                clean_name = warn_type.replace('warning-', '').replace('-', ' ')
                lines.append(f"- {clean_name}: {count:,}")

        # Iteration guidance
        if self.attempt_number is not None and self.attempt_number in ITERATION_ADVICE:
            lines.append("")
            lines.append("## Iteration Guidance")
            lines.append(ITERATION_ADVICE[self.attempt_number])

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


def _fragmentation_interpretation(ratio: float) -> str:
    """Return human-readable interpretation of fragmentation ratio.

    Args:
        ratio: statvars / observations ratio

    Returns:
        Interpretation string
    """
    if ratio < 0.05:
        return "<0.05 = very compact schema (few StatVars, many obs each)"
    elif ratio < 0.3:
        return "0.05-0.3 = healthy (moderate StatVars with multiple obs each)"
    elif ratio < 0.8:
        return "0.3-0.8 = moderate fragmentation (some dimension columns may create too many StatVars)"
    else:
        return ">0.8 = nearly 1 StatVar per observation (dimensions likely treated as value columns)"


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


def filter_counters(counters_path: Path, attempt_number: Optional[int] = None) -> FilteredLogs:
    """Extract useful metrics and analyze value patterns from counter file.

    Key improvements over simple filtering:
    1. Extracts aggregate metrics (coverage, statvars)
    2. Analyzes individual value failures to detect PATTERNS
    3. Clusters values by type to identify failing columns
    4. Mines debug examples for specific error types
    5. Attaches iteration-specific advice

    Args:
        counters_path: Path to the processed_counters.txt file
        attempt_number: Current attempt number (0-indexed) for iteration advice

    Returns:
        FilteredLogs with metrics and pattern analysis
    """
    result = FilteredLogs()
    result.attempt_number = attempt_number

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
        r'spell-check-',               # Spell check detail (keep error-spell-words)
        r'spell-allowlist',             # Spell allowlist stats
        r'urls-',                       # URL checks
        r'pvs-added',                   # Internal tracking
    ]
    noise_regex = re.compile('|'.join(noise_patterns))

    raw_counters: Dict[str, int] = {}
    unmapped_values: List[Tuple[str, int]] = []
    prefixed_metrics: Dict[str, int] = {}  # Key metrics from prefixed counters
    prefixed_counters: List[Tuple[str, int]] = []  # ALL prefixed counters for diagnostic extraction

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

                # Capture prefixed counters for diagnostic extraction, then skip
                if re.match(r'^\d+:', key):
                    prefixed_counters.append((key, count))
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
    # Exclude informational keys that are captured in dedicated fields
    INFORMATIONAL_ERROR_KEYS = {'error-spell-words'}
    INFORMATIONAL_WARNING_KEYS = {'dropped-output-statvars-mcf'}
    for key, value in raw_counters.items():
        if key.startswith('error-') and '_' not in key and key not in INFORMATIONAL_ERROR_KEYS:
            result.errors[key] = value
        elif (key.startswith('warning-') or key.startswith('dropped-')) and '_' not in key and key not in INFORMATIONAL_WARNING_KEYS:
            result.warnings[key] = value

    # Mine debug examples universally for ALL error/dropped/warning types
    # (replaces old hardcoded 7-type list)
    all_error_types = set(result.errors.keys())
    # Also mine dropped and warning counter types that have detail suffixes
    for key in raw_counters:
        if key in ('dropped-invalid-svobs', 'dropped-invalid-statvars',
                   'dropped-statvars-without-svobs'):
            all_error_types.add(key)
    for err_type in all_error_types:
        prefix = f"{err_type}_"
        examples = []
        for key, value in raw_counters.items():
            if key.startswith(prefix):
                example_val = key[len(prefix):]
                if example_val and not example_val.startswith('/'):
                    examples.append((example_val, value))
        if examples:
            examples.sort(key=lambda x: -x[1])
            result.error_examples[err_type] = examples

    # =====================================================================
    # Rich signal extraction from non-prefixed counters
    # =====================================================================

    # (a) Property cardinality from output-svobs-unique-*
    SKIP_CARDINALITY_PROPS = {'#input', 'typeOf'}
    for key, value in raw_counters.items():
        if key.startswith('output-svobs-unique-'):
            prop_name = key.replace('output-svobs-unique-', '')
            if prop_name not in SKIP_CARDINALITY_PROPS:
                result.property_cardinality[prop_name] = value

    # (b) Per-StatVar observation counts from svobs-added_dcid:* and generated-svobs_*
    for key, value in raw_counters.items():
        if key.startswith('svobs-added_dcid:'):
            sv_name = key.replace('svobs-added_dcid:', '')
            # Truncate very long names
            if len(sv_name) > 100:
                sv_name = sv_name[:100] + '...'
            result.statvars_with_obs.append((sv_name, value))
        elif key.startswith('generated-svobs_') and not key.endswith('.csv'):
            sv_name = key[len('generated-svobs_'):]
            if sv_name and not sv_name.startswith('/'):
                result.statvars_with_obs.append((sv_name, value))
    result.statvars_with_obs.sort(key=lambda x: -x[1])

    # (c) Dropped StatVars from dropped-statvars-without-svobs_* and dropped-invalid-statvars_*
    dropped_prefixes = ['dropped-invalid-statvars_', 'dropped-statvars-without-svobs_']
    for key, value in raw_counters.items():
        for dp in dropped_prefixes:
            if key.startswith(dp):
                sv_name = key[len(dp):]
                if sv_name and not sv_name.startswith('/'):
                    if sv_name not in result.dropped_statvars:
                        result.dropped_statvars.append(sv_name)

    # (d) Per-StatVar generation counts from generated-statvars_*
    for key, value in raw_counters.items():
        if key.startswith('generated-statvars_'):
            sv_name = key.replace('generated-statvars_', '')
            result.statvars_generated_counts.append((sv_name, value))
    result.statvars_generated_counts.sort(key=lambda x: -x[1])

    # (k) Spell check, MCF drops, API nodes from non-prefixed counters
    result.spell_check_errors = raw_counters.get('error-spell-words', 0)
    result.dropped_mcf_statvars = raw_counters.get('dropped-output-statvars-mcf', 0)
    result.existing_nodes_from_api = raw_counters.get('existing-nodes-from-api', 0)

    # =====================================================================
    # Rich signal extraction from prefixed counters
    # =====================================================================
    _missing_place_accum = {}
    for pkey, pcount in prefixed_counters:
        # Strip the numeric prefix (e.g., "1:process_input_") to get the suffix
        # The suffix is everything after the last known stage separator
        suffix = pkey
        prefix_match = re.match(r'^\d+:\w+_', pkey)
        if prefix_match:
            suffix = pkey[prefix_match.end():]

        # (e) Unresolved value references
        if 'warning-unresolved-value-ref_' in pkey:
            ref_name = suffix.replace('warning-unresolved-value-ref_', '')
            if ref_name and not ref_name.startswith('/') and ref_name != suffix:
                result.unresolved_refs[ref_name] = result.unresolved_refs.get(ref_name, 0) + pcount
            elif 'warning-unresolved-value-ref_' in suffix:
                ref_name = suffix.split('warning-unresolved-value-ref_', 1)[1]
                if ref_name:
                    result.unresolved_refs[ref_name] = result.unresolved_refs.get(ref_name, 0) + pcount

        # (g) Place failure StatVars
        if 'dropped-svobs-unresolved-place_' in pkey:
            sv_part = suffix.replace('dropped-svobs-unresolved-place_', '')
            if sv_part and sv_part != suffix:
                result.place_failure_statvars[sv_part] = (
                    result.place_failure_statvars.get(sv_part, 0) + pcount
                )

        # (h) Missing place StatVars
        if 'warning-svobs-missing-place_' in pkey:
            sv_part = suffix
            if 'warning-svobs-missing-place_' in suffix:
                sv_part = suffix.split('warning-svobs-missing-place_', 1)[1]
            if sv_part:
                _missing_place_accum[sv_part] = _missing_place_accum.get(sv_part, 0) + pcount

        # (i) Input structure
        if suffix == 'input-header-rows' or pkey.endswith('_input-header-rows'):
            if result.input_header_rows == 0:
                result.input_header_rows = pcount
        if suffix == 'input-data-rows' or pkey.endswith('_input-data-rows'):
            if result.input_data_rows == 0:
                result.input_data_rows = pcount
        if suffix == 'input-sections' or pkey.endswith('_input-sections'):
            if result.input_sections == 0:
                result.input_sections = pcount

    # Finalize missing_place_statvars from accumulated dict
    if _missing_place_accum:
        result.missing_place_statvars = sorted(_missing_place_accum.items(), key=lambda x: -x[1])

    # Also check non-prefixed for input structure (may exist there too)
    if result.input_header_rows == 0:
        result.input_header_rows = raw_counters.get('input-header-rows', 0)
    if result.input_data_rows == 0:
        result.input_data_rows = raw_counters.get('input-data-rows', 0)
    if result.input_sections == 0:
        result.input_sections = raw_counters.get('input-sections', 0)

    # Unresolved places from non-prefixed counters
    for key, value in raw_counters.items():
        if key.startswith('dropped-svobs-unresolved-place_'):
            place_val = key.replace('dropped-svobs-unresolved-place_', '')
            if place_val:
                result.unresolved_places.append((place_val, value))
    result.unresolved_places.sort(key=lambda x: -x[1])

    # (j) Fragmentation ratio
    if result.observations_generated > 0:
        result.fragmentation_ratio = result.statvars_generated / result.observations_generated

    # Analyze unmapped values to detect patterns
    if unmapped_values:
        result.unmapped_value_patterns = _analyze_value_patterns(unmapped_values)

        # Also keep top unmapped values for reference
        value_counts: Counter = Counter()
        for val, count in unmapped_values:
            value_counts[val] += count
        result.top_unmapped_values = value_counts.most_common(20)

        # (f) Top missing keys — limit to top 100 to prevent memory/token overflow
        # (full list can have 300K+ entries for wide datasets)
        result.top_missing_keys = value_counts.most_common(100)

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

# ============================================================================
# Logging noise filters
# ============================================================================

class DualApiKeyFilter(logging.Filter):
    """Suppress repeated 'Both GOOGLE_API_KEY and GEMINI_API_KEY are set' warnings."""

    def filter(self, record):
        return "Both GOOGLE_API_KEY and GEMINI_API_KEY" not in record.getMessage()


class McpSessionWarningFilter(logging.Filter):
    """Suppress empty 'Error on session runner task:' warnings from MCP cleanup."""

    def filter(self, record):
        msg = record.getMessage().strip()
        return not msg.startswith("Error on session runner task:")


class AdkNoiseFilter(logging.Filter):
    """Suppress low-value ADK/google-genai debug messages."""

    _SUPPRESSED_PATTERNS = (
        "No debug state for invocation",
        "non-text parts in the response:",
        "[EXPERIMENTAL] feature FeatureName",
    )

    def filter(self, record):
        msg = record.getMessage()
        return not any(pattern in msg for pattern in self._SUPPRESSED_PATTERNS)


def apply_log_noise_filters():
    """Apply all log noise filters to the relevant third-party loggers.

    Safe to call multiple times — filters are deduplicated by class name.

    Logger hierarchy note: google-adk uses ``google_adk`` (underscore)
    as the top-level logger, NOT ``google.adk`` (dot).
    """
    _filter_specs = [
        # Dual API key warnings (google_genai._api_client)
        ("google_genai._api_client", DualApiKeyFilter),
        ("google_genai", DualApiKeyFilter),
        # MCP session runner empty-error warnings
        ("google_adk.google.adk.tools.mcp_tool.session_context", McpSessionWarningFilter),
        ("google_adk", McpSessionWarningFilter),
        # ADK debug noise (No debug state, experimental features)
        ("google_adk.google.adk.plugins.debug_logging_plugin", AdkNoiseFilter),
        ("google_adk", AdkNoiseFilter),
        ("google_genai", AdkNoiseFilter),
    ]

    for logger_name, filter_cls in _filter_specs:
        target_logger = logging.getLogger(logger_name)
        # Avoid duplicate filters
        if not any(isinstance(f, filter_cls) for f in target_logger.filters):
            target_logger.addFilter(filter_cls())

    # Capture Python warnings through the logging system so filters apply
    # to UserWarning messages like "[EXPERIMENTAL] feature FeatureName..."
    logging.captureWarnings(True)
    warnings_logger = logging.getLogger("py.warnings")
    if not any(isinstance(f, AdkNoiseFilter) for f in warnings_logger.filters):
        warnings_logger.addFilter(AdkNoiseFilter())


__all__ = [
    'FilteredLogs',
    'ValuePattern',
    'filter_counters',
    'extract_sample_errors',
    'generate_concise_feedback',
    'apply_log_noise_filters',
    'DualApiKeyFilter',
    'McpSessionWarningFilter',
    'AdkNoiseFilter',
    '_fragmentation_interpretation',
    'ERROR_PRIORITY',
    'ERROR_PATTERNS',
    'ITERATION_ADVICE',
    '_sort_errors_by_priority',
    '_get_error_pattern',
    'detect_systematic_patterns',
    '_detect_format_pattern',
]
