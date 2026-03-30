"""Counter-based feedback generator for PVMAP validation.

This module parses stat_var_processor counter files and generates targeted,
actionable feedback for the LLM retry loop. Instead of random log sampling,
it provides structured diagnostics based on actual error counters.

Counter Categories:
- error-*: Validation failures that must be fixed
- warning-*: Non-fatal issues worth investigating
- dropped-*: Rows filtered out (potential data loss)
- generated-*: Success metrics
- input-*: Input statistics

Enhanced Features:
- Debug context extraction: Extracts specific failing values from debug counters
- Iteration-specific advice: Different guidance for each retry attempt
- Error prioritization: Errors sorted by impact (Gemini-recommended order)
- Actionable fixes: Concrete examples for common error types
- Transformation feedback: Shows before/after for failing rows
- Systematic pattern detection: Identifies patterns across errors

Usage:
    from src.pipeline.validation.counter_feedback import parse_counters_file, generate_feedback

    counters = parse_counters_file(counters_file_path)
    feedback = generate_feedback(counters, log_output=optional_log_text, attempt_number=1)

    # For transformation analysis (Phase 10)
    from src.pipeline.validation.counter_feedback import detect_systematic_patterns
    patterns = detect_systematic_patterns(error_context_dict)
"""

import warnings
warnings.warn(
    "counter_feedback is deprecated. Use log_filter.filter_counters() instead. "
    "Key features have been merged into log_filter.py: ERROR_PRIORITY, ERROR_PATTERNS, "
    "debug example extraction, systematic pattern detection, and ITERATION_ADVICE.",
    DeprecationWarning,
    stacklevel=2,
)

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Error priority order (Gemini-recommended: fix highest-impact errors first)
# Errors are sorted by this priority, then by count
ERROR_PRIORITY = [
    'error-pvmap-dropped-undefined-property',  # 1. PVMAP structure errors first
    'error-unresolved-place',                  # 2. Place resolution (unlocks many rows)
    'error-statvar-missing-property',          # 3. StatVar completeness
    'error-svobs-missing-property',            # 4. Observation completeness
    'error-mismatched-svobs',                  # 5. Duplicate observations
    'error-duplicate-statvars',                # 6. Duplicate StatVar definitions
    'error-aggregate-invalid-values',          # 7. Value aggregation
    'error-invalid-multiply-factor',           # 8. Multiplication factors
]

# Iteration-specific advice (retry strategies)
ITERATION_ADVICE = {
    1: """## Retry Strategy (Attempt 1 → 2)
Focus on the highest-count errors first. Fixing place resolution often unlocks many other rows.
Check PVMAP key names match CSV column headers EXACTLY (case-sensitive).""",

    2: """## Retry Strategy (Attempt 2 → 3)
Review changes from last attempt - did they address the right issue?
For place errors: verify format with Data Commons Explorer (e.g., geoId/06 not geoId/6).
For property errors: check CSV column names match PVMAP property definitions.""",

    3: """## Retry Strategy (Attempt 3 → 4)
Consider simplifying: fix ONE error type at a time.
If place resolution fails repeatedly, try explicit dcid mappings instead of format strings.
If StatVar properties missing, ensure populationType, measuredProperty, statType are all defined.""",
}

# Error counter patterns and their fix recommendations
ERROR_PATTERNS = {
    'error-unresolved-place': {
        'category': 'Place Resolution',
        'description': 'Place values could not be converted to Data Commons DCIDs',
        'common_causes': [
            'FIPS codes missing leading zeros (e.g., 6 instead of 06)',
            'Missing geoId/ prefix in observationAbout mapping',
            'Place names ambiguous without typeOf or containedInPlace context',
        ],
        'fix_pattern': '''Fix place mapping in PVMAP:

**For FIPS codes (most common):**
```
State FIPS Code,observationAbout,dcid:geoId/{Number:02d}
```
Or use explicit padding: `dcid:geoId/0{Data}` for single-digit states.

**For country ISO codes:**
```
Country,observationAbout,dcid:country/{Data}
```

**For city/county names (needs context):**
Add both place name AND parent place for disambiguation.

**Common FIPS Fixes:**
- California: geoId/06 (not geoId/6)
- Texas: geoId/48
- Counties need 5 digits: geoId/06037 (Los Angeles)''',
    },
    'error-statvar-missing-property': {
        'category': 'StatVar Definition Incomplete',
        'description': 'Statistical variable missing required properties',
        'common_causes': [
            'Missing populationType (Person, Household, Establishment, etc.)',
            'Missing measuredProperty (count, income, area, etc.)',
            'Missing statType (Count, Mean, Median, Percent, etc.)',
        ],
        'fix_pattern': '''Add required StatVar properties:

**Every StatVar needs:**
- populationType: what entity (Person, Household, Place)
- measuredProperty: what aspect (count, income, area)
- statType: how measured (Count, Mean, Percent)
- value: the numeric measurement column

**Example for population count:**
```
Population,populationType,dcid:Person,measuredProperty,dcid:count,statType,dcid:measuredValue,value,{Number}
```

**Example for median income:**
```
Median Income,populationType,dcid:Person,measuredProperty,dcid:income,statType,dcid:medianValue,value,{Number}
```''',
    },
    'error-mismatched-svobs': {
        'category': 'Duplicate Observations',
        'description': 'Multiple observations for same StatVar + Place + Date',
        'common_causes': [
            'A dimension column (Gender, Age, Race) not mapped as StatVar qualifier',
            'Multiple measurement methods not differentiated',
            'Missing constraint property to distinguish rows',
        ],
        'fix_pattern': '''Add qualifiers to differentiate observations:

**Identify the column creating different rows and add its mapping:**

**For gender breakdowns:**
```
Male,gender,dcid:Male
Female,gender,dcid:Female
```

**For age groups:**
```
0-17,age,dcid:Years0To17
18-64,age,dcid:Years18To64
65+,age,dcid:Years65Onwards
```

**For race/ethnicity:**
```
White,race,dcid:WhiteAlone
Black,race,dcid:BlackOrAfricanAmericanAlone
```

**Rule: Place + Date + StatVar = ONE value only**''',
    },
    'error-pvmap-dropped-undefined-property': {
        'category': 'PVMAP Key Mismatch',
        'description': 'PVMAP key doesn\'t match any input column header',
        'common_causes': [
            'Case mismatch (State FIPS vs state_fips)',
            'Typo in column name',
            'Column renamed or missing from input data',
        ],
        'fix_pattern': '''Fix column name matching:

**Keys must match EXACTLY (case-sensitive):**
- If CSV has "State FIPS", PVMAP key must be "State FIPS" (not "state fips")
- Check for leading/trailing spaces in CSV headers
- Check for underscores vs spaces: "State_FIPS" vs "State FIPS"

**Debugging tip:** Print the first row of the CSV to see exact column names.''',
    },
    'error-duplicate-statvars': {
        'category': 'Duplicate StatVars',
        'description': 'Multiple StatVar definitions with same DCID',
        'common_causes': [
            'Same measurement mapped multiple times',
            'Redundant PVMAP entries',
        ],
        'fix_pattern': '''Remove duplicate StatVar definitions:
- Each unique combination of properties should define ONE StatVar
- Check for redundant key mappings in PVMAP''',
    },
    'error-aggregate-invalid-values': {
        'category': 'Aggregation Error',
        'description': 'Invalid values during aggregation',
        'common_causes': [
            'Non-numeric values in aggregation columns',
            'Missing or null values in aggregated fields',
        ],
        'fix_pattern': '''Fix value mapping:
- Ensure numeric columns use {Number} not {Data}
- Check for non-numeric values in measurement columns''',
    },
    'error-svobs-missing-property': {
        'category': 'Missing Observation Property',
        'description': 'StatVarObservation missing required property',
        'common_causes': [
            'Missing observationAbout (place) mapping',
            'Missing observationDate mapping',
            'Missing value mapping',
        ],
        'fix_pattern': '''Ensure all required observation properties are mapped:

**Required for every observation:**
```
Year,observationDate,{Data}
State FIPS,observationAbout,dcid:geoId/{Data}
Population,value,{Number}
```

All three (observationAbout, observationDate, value) MUST be present.''',
    },
    'error-invalid-multiply-factor': {
        'category': 'Invalid Multiply Factor',
        'description': 'Invalid multiplication factor in value transformation',
        'common_causes': [
            'Non-numeric multiply factor',
            'Invalid expression in value transformation',
        ],
        'fix_pattern': '''Check value transformation expressions:
- Ensure multiply factors are valid numbers
- Use standard numeric formats''',
    },
}

# Warning patterns
WARNING_PATTERNS = {
    'warning-svobs-missing-place': {
        'category': 'Missing Place',
        'description': 'Observations missing place information',
    },
    'dropped-svobs-unresolved-date': {
        'category': 'Date Resolution',
        'description': 'Observations dropped due to unresolved date format',
    },
    'dropped-svobs-unresolved-place': {
        'category': 'Place Resolution',
        'description': 'Observations dropped due to unresolved place',
    },
    'dropped-svobs-invalid': {
        'category': 'Invalid Observation',
        'description': 'Observations dropped due to validation failure',
    },
    'dropped-statvars-without-svobs': {
        'category': 'Unused StatVars',
        'description': 'StatVars defined but no observations generated',
    },
}


def parse_counters_file(counters_path: Path) -> Dict[str, int]:
    """Parse a stat_var_processor counters file.

    Args:
        counters_path: Path to the _counters.txt file

    Returns:
        Dictionary mapping counter names to their values
    """
    counters = {}

    if not counters_path.exists():
        return counters

    try:
        with open(counters_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            for row in reader:
                if len(row) >= 2:
                    key = row[0].strip()
                    try:
                        # Try to parse as number
                        value = float(row[1].strip())
                        if value == int(value):
                            value = int(value)
                        counters[key] = value
                    except (ValueError, IndexError):
                        # Keep as string if not numeric
                        counters[key] = row[1].strip() if len(row) > 1 else ''
    except Exception as e:
        # Return empty dict if file can't be parsed
        pass

    return counters


def get_error_counters(counters: Dict[str, int]) -> Dict[str, int]:
    """Extract only error counters from the full counter dict.

    Args:
        counters: Full counter dictionary

    Returns:
        Dictionary of only error counters (those starting with 'error-')
    """
    return {k: v for k, v in counters.items()
            if k.startswith('error-') and isinstance(v, (int, float)) and v > 0}


def get_warning_counters(counters: Dict[str, int]) -> Dict[str, int]:
    """Extract warning and dropped counters.

    Args:
        counters: Full counter dictionary

    Returns:
        Dictionary of warning/dropped counters
    """
    return {k: v for k, v in counters.items()
            if (k.startswith('warning-') or k.startswith('dropped-'))
            and isinstance(v, (int, float)) and v > 0}


def calculate_coverage(counters: Dict[str, int]) -> Tuple[float, int, int]:
    """Calculate the coverage ratio (output rows / input rows).

    Args:
        counters: Full counter dictionary

    Returns:
        Tuple of (coverage_ratio, output_rows, input_rows)
    """
    # Try different counter names for input/output
    input_rows = counters.get('input-rows-processed', 0)
    if not input_rows:
        input_rows = counters.get('1:process_input_input-rows-processed', 0)

    output_rows = counters.get('output-svobs-csv-rows', 0)
    if not output_rows:
        output_rows = counters.get('4:write_svobs_csv_output-svobs-csv-rows', 0)

    if input_rows > 0:
        coverage = output_rows / input_rows
    else:
        coverage = 0.0

    return coverage, output_rows, input_rows


def identify_primary_error(error_counters: Dict[str, int]) -> Optional[str]:
    """Identify the primary (most frequent) error type.

    Args:
        error_counters: Dictionary of error counters

    Returns:
        The error counter name with highest count, or None
    """
    if not error_counters:
        return None
    return max(error_counters.items(), key=lambda x: x[1])[0]


def prioritize_errors(error_counters: Dict[str, int]) -> List[Tuple[str, int]]:
    """Sort errors by priority order, then by count.

    Uses ERROR_PRIORITY to determine which errors to fix first.
    Errors not in priority list are sorted to the end by count.

    Args:
        error_counters: Dictionary of error counters

    Returns:
        List of (error_name, count) tuples sorted by priority
    """
    def priority_key(item):
        error_name, count = item
        # Find priority (lower = higher priority)
        try:
            priority = ERROR_PRIORITY.index(error_name)
        except ValueError:
            # Check if error_name starts with any priority pattern
            for i, pattern in enumerate(ERROR_PRIORITY):
                if error_name.startswith(pattern):
                    priority = i
                    break
            else:
                priority = len(ERROR_PRIORITY)  # Unknown errors last

        return (priority, -count)  # Sort by priority, then by count desc

    return sorted(error_counters.items(), key=priority_key)


def extract_debug_examples(
    counters: Dict[str, int],
    error_type: str,
    max_examples: int = 5
) -> List[str]:
    """Extract specific failing examples from debug counters.

    When stat_var_processor runs with --debug=True, it creates extended
    counters like 'error-unresolved-place_geoId/6' that capture the
    specific failing values. This function extracts those values.

    Args:
        counters: Full counter dictionary including debug counters
        error_type: Base error type (e.g., 'error-unresolved-place')
        max_examples: Maximum examples to return

    Returns:
        List of specific failing values (e.g., ['geoId/6', 'geoId/12', ...])
    """
    examples = []
    prefix = f"{error_type}_"

    for counter_name, count in counters.items():
        if counter_name.startswith(prefix) and isinstance(count, (int, float)) and count > 0:
            # Extract the debug context (everything after the prefix)
            example = counter_name[len(prefix):]
            if example:  # Skip empty examples
                examples.append((example, int(count)))

    # Sort by count (most frequent first) and return top N
    examples.sort(key=lambda x: -x[1])
    return [ex[0] for ex in examples[:max_examples]]


def match_error_pattern(error_name: str) -> Optional[Dict]:
    """Match an error counter name to a known error pattern.

    Args:
        error_name: The error counter name (e.g., 'error-unresolved-place')

    Returns:
        The error pattern dict if matched, None otherwise
    """
    # Direct match
    if error_name in ERROR_PATTERNS:
        return ERROR_PATTERNS[error_name]

    # Prefix match (some errors have suffixes)
    for pattern_name, pattern_info in ERROR_PATTERNS.items():
        if error_name.startswith(pattern_name):
            return pattern_info

    return None


def extract_log_samples_for_error(
    log_output: str,
    error_type: str,
    max_samples: int = 5
) -> List[str]:
    """Extract relevant log lines for a specific error type.

    Args:
        log_output: Full log output text
        error_type: The error type to search for
        max_samples: Maximum number of sample lines to return

    Returns:
        List of relevant log lines
    """
    samples = []

    # Build regex patterns based on error type
    patterns = []
    if 'place' in error_type.lower():
        patterns.extend([
            r'Unable to resolve place',
            r'unresolved.*place',
            r'observationAbout.*error',
        ])
    if 'statvar' in error_type.lower() or 'property' in error_type.lower():
        patterns.extend([
            r'Missing.*propert',
            r'statvar.*error',
            r'populationType',
            r'measuredProperty',
        ])
    if 'mismatch' in error_type.lower() or 'duplicate' in error_type.lower():
        patterns.extend([
            r'[Dd]uplicate',
            r'[Mm]ismatch',
            r'collision',
        ])
    if 'pvmap' in error_type.lower() or 'undefined' in error_type.lower():
        patterns.extend([
            r'No mapping found',
            r'undefined.*property',
            r'column.*not found',
        ])

    # Search log for matching lines
    lines = log_output.split('\n')
    for line in lines:
        if len(samples) >= max_samples:
            break
        for pattern in patterns:
            if re.search(pattern, line, re.IGNORECASE):
                samples.append(line.strip())
                break

    return samples


def generate_feedback(
    counters: Dict[str, int],
    log_output: Optional[str] = None,
    include_coverage: bool = True,
    attempt_number: int = 0
) -> str:
    """Generate targeted feedback based on counter analysis.

    Enhanced version with:
    - Priority-sorted errors (fix most impactful first)
    - Specific failing examples from debug counters
    - Iteration-specific advice

    Args:
        counters: Parsed counter dictionary
        log_output: Optional log output for extracting sample errors
        include_coverage: Whether to include coverage analysis
        attempt_number: Current attempt number (0-indexed) for iteration-specific advice

    Returns:
        Formatted feedback string for LLM retry loop
    """
    sections = []

    # 1. Coverage Analysis
    if include_coverage:
        coverage, output_rows, input_rows = calculate_coverage(counters)
        coverage_section = f"""## Coverage Analysis
- Input rows processed: {input_rows:,}
- Output observations generated: {output_rows:,}
- Coverage ratio: {coverage*100:.1f}%"""

        if coverage < 0.5:
            coverage_section += "\n\n⚠️ WARNING: Coverage below 50% - many rows are being dropped!"
        elif coverage < 0.8:
            coverage_section += "\n\n⚠️ NOTICE: Coverage below 80% - investigate dropped rows."

        sections.append(coverage_section)

    # 2. Prioritized Error Analysis
    error_counters = get_error_counters(counters)

    if error_counters:
        error_section = "## Prioritized Errors\n"
        error_section += "The following errors were detected (sorted by fix priority):\n\n"

        # Sort errors by priority, then by count
        sorted_errors = prioritize_errors(error_counters)

        for i, (error_name, count) in enumerate(sorted_errors, 1):
            error_section += f"{i}. **{error_name}**: {count:,} occurrences\n"

        sections.append(error_section)

        # 3. Primary Error Diagnosis (highest priority error)
        if sorted_errors:
            primary_error = sorted_errors[0][0]
            pattern = match_error_pattern(primary_error)

            if pattern:
                diagnosis = f"""## Primary Issue: {pattern['category']}

**Problem:** {pattern['description']}

**Common Causes:**
"""
                for cause in pattern.get('common_causes', []):
                    diagnosis += f"- {cause}\n"

                # 3a. Extract specific failing examples from debug counters
                debug_examples = extract_debug_examples(counters, primary_error)
                if debug_examples:
                    diagnosis += f"""
**Specific Failing Examples:**
These values are causing {pattern['category'].lower()} errors:
"""
                    for example in debug_examples[:5]:
                        diagnosis += f"- `{example}`\n"
                    diagnosis += "\nFocus on fixing these specific cases in your PVMAP.\n"

                diagnosis += f"""
**How to Fix:**
{pattern['fix_pattern']}"""
                sections.append(diagnosis)
            else:
                # Unknown error pattern
                sections.append(f"""## Primary Issue: {primary_error}

This error type is not in the known patterns.
Please review the PVMAP for issues related to: {primary_error.replace('error-', '').replace('-', ' ')}""")

        # 4. Sample Error Lines from Log
        if log_output and sorted_errors:
            primary_error = sorted_errors[0][0]
            samples = extract_log_samples_for_error(log_output, primary_error)
            if samples:
                sample_section = "## Sample Error Messages\n```\n"
                sample_section += '\n'.join(samples[:5])
                sample_section += "\n```"
                sections.append(sample_section)

    # 5. Warning Analysis (if no critical errors)
    if not error_counters:
        warning_counters = get_warning_counters(counters)
        if warning_counters:
            warning_section = "## Warnings\n"
            for warn_name, count in sorted(warning_counters.items(), key=lambda x: -x[1]):
                warning_section += f"- **{warn_name}**: {count:,}\n"
            sections.append(warning_section)

    # 6. Success Metrics
    generated_svobs = counters.get('generated-svobs', 0)
    generated_statvars = counters.get('generated-statvars', 0) or counters.get('generated-unique-statvars', 0)

    if generated_svobs > 0 or generated_statvars > 0:
        success_section = "## Generation Statistics\n"
        if generated_statvars:
            success_section += f"- StatVars generated: {generated_statvars}\n"
        if generated_svobs:
            success_section += f"- Observations generated: {generated_svobs}\n"
        sections.append(success_section)

    # 7. Iteration-Specific Advice
    if attempt_number > 0 and attempt_number in ITERATION_ADVICE:
        sections.append(ITERATION_ADVICE[attempt_number])

    # Combine all sections
    if sections:
        return '\n\n'.join(sections)
    else:
        return "No counter data available for analysis."


def generate_feedback_from_file(
    counters_path: Path,
    log_output: Optional[str] = None
) -> str:
    """Convenience function to generate feedback directly from a counters file.

    Args:
        counters_path: Path to the _counters.txt file
        log_output: Optional log output for extracting sample errors

    Returns:
        Formatted feedback string
    """
    counters = parse_counters_file(counters_path)
    return generate_feedback(counters, log_output)


# Quick diagnostic function for debugging
def diagnose_validation_failure(
    counters_path: Path,
    log_output: Optional[str] = None
) -> Dict:
    """Diagnose a validation failure and return structured results.

    Args:
        counters_path: Path to the _counters.txt file
        log_output: Optional log output

    Returns:
        Dictionary with diagnostic information
    """
    counters = parse_counters_file(counters_path)
    error_counters = get_error_counters(counters)
    warning_counters = get_warning_counters(counters)
    coverage, output_rows, input_rows = calculate_coverage(counters)
    primary_error = identify_primary_error(error_counters)

    result = {
        'counters_found': len(counters) > 0,
        'coverage_ratio': coverage,
        'output_rows': output_rows,
        'input_rows': input_rows,
        'error_count': sum(error_counters.values()) if error_counters else 0,
        'error_types': list(error_counters.keys()),
        'primary_error': primary_error,
        'primary_error_pattern': match_error_pattern(primary_error) if primary_error else None,
        'warning_count': sum(warning_counters.values()) if warning_counters else 0,
        'warning_types': list(warning_counters.keys()),
    }

    return result


# ============================================================================
# Phase 9-10: Enhanced Pattern Detection and Transformation Feedback
# ============================================================================

def detect_systematic_patterns(
    error_contexts: Dict,
    threshold: float = 0.8
) -> List[Dict]:
    """Detect systematic patterns in errors.

    Analyzes error context to identify patterns that affect many rows
    with the same or similar characteristics.

    Args:
        error_contexts: Dict mapping error_type -> context dict with
            'total_count' and 'unique_failing_values' keys
        threshold: Minimum ratio of errors sharing a pattern (default: 0.8)

    Returns:
        List of detected patterns sorted by confidence
    """
    patterns = []

    for error_type, ctx in error_contexts.items():
        total_count = ctx.get('total_count', 0)
        if total_count < 5:
            continue

        unique_values = ctx.get('unique_failing_values', {})

        for col, values in unique_values.items():
            value_list = list(values) if isinstance(values, set) else values

            # Single-value pattern: all errors have same value
            if len(value_list) == 1:
                patterns.append({
                    'type': 'single_value',
                    'error': error_type,
                    'column': col,
                    'value': value_list[0],
                    'count': total_count,
                    'confidence': 1.0,
                    'description': (
                        f"All {total_count} '{error_type}' errors "
                        f"have {col}='{value_list[0]}'"
                    )
                })

            # Few-values pattern: limited unique values causing many errors
            elif len(value_list) < total_count * 0.2 and total_count >= 10:
                patterns.append({
                    'type': 'few_values',
                    'error': error_type,
                    'column': col,
                    'values': value_list[:5],
                    'count': total_count,
                    'confidence': 0.8,
                    'description': (
                        f"Only {len(value_list)} unique values in '{col}' "
                        f"causing {total_count} errors"
                    )
                })

            # Format pattern: detect common format issues
            if _detect_format_pattern(value_list):
                pattern_info = _detect_format_pattern(value_list)
                patterns.append({
                    'type': 'format_pattern',
                    'error': error_type,
                    'column': col,
                    'pattern': pattern_info['pattern'],
                    'examples': pattern_info['examples'],
                    'count': total_count,
                    'confidence': pattern_info['confidence'],
                    'description': pattern_info['description']
                })

    # Sort by confidence descending
    return sorted(patterns, key=lambda x: -x['confidence'])


def _detect_format_pattern(values: List[str]) -> Optional[Dict]:
    """Detect common format patterns in failing values.

    Args:
        values: List of failing values

    Returns:
        Pattern info dict or None
    """
    if not values:
        return None

    # Check for missing leading zeros (common FIPS issue)
    single_digit_count = sum(1 for v in values if v.isdigit() and len(v) == 1)
    if single_digit_count > len(values) * 0.5 and len(values) >= 3:
        return {
            'pattern': 'missing_leading_zeros',
            'examples': [v for v in values[:3] if v.isdigit() and len(v) == 1],
            'confidence': 0.9,
            'description': (
                "Values appear to be missing leading zeros "
                "(e.g., '6' should be '06' for California)"
            )
        }

    # Check for missing dcid: prefix
    dcid_candidates = sum(
        1 for v in values
        if v and not v.startswith('dcid:') and (
            v.startswith('geoId/') or
            v.startswith('country/') or
            v in ['Person', 'Household', 'HousingUnit', 'Establishment']
        )
    )
    if dcid_candidates > len(values) * 0.5:
        return {
            'pattern': 'missing_dcid_prefix',
            'examples': values[:3],
            'confidence': 0.85,
            'description': "Values appear to be missing 'dcid:' prefix"
        }

    return None


def format_pattern_feedback(patterns: List[Dict]) -> str:
    """Format detected patterns into actionable feedback.

    Args:
        patterns: List of pattern dicts from detect_systematic_patterns

    Returns:
        Formatted feedback string
    """
    if not patterns:
        return "No systematic patterns detected - errors may be random data issues."

    lines = ["## Systematic Error Patterns Detected", ""]

    for i, p in enumerate(patterns[:5], 1):
        lines.append(f"**Pattern {i}** (confidence: {p['confidence']:.0%})")
        lines.append(f"  {p['description']}")

        if p['type'] == 'single_value':
            lines.append(
                f"  **Action:** Check PVMAP mapping for column '{p['column']}' - "
                f"value '{p['value']}' is causing all errors"
            )
        elif p['type'] == 'few_values':
            lines.append(
                f"  **Action:** Add specific mappings for values: {p['values']}"
            )
        elif p['type'] == 'format_pattern':
            if p['pattern'] == 'missing_leading_zeros':
                lines.append(
                    "  **Action:** Add zero-padding to FIPS codes, e.g., "
                    "dcid:geoId/{Number:02d} or dcid:geoId/0{Data}"
                )
            elif p['pattern'] == 'missing_dcid_prefix':
                lines.append(
                    "  **Action:** Add 'dcid:' prefix to Data Commons identifiers"
                )

        lines.append("")

    return '\n'.join(lines)


def generate_transformation_feedback(
    error_contexts: Dict,
    max_examples: int = 3
) -> str:
    """Generate feedback showing before/after transformations for failing rows.

    This helps the LLM understand exactly what went wrong during transformation.

    Args:
        error_contexts: Dict mapping error_type -> context dict with
            'sample_rows' containing transformation details
        max_examples: Maximum examples per error type

    Returns:
        Formatted transformation analysis string
    """
    sections = []

    for error_type, ctx in error_contexts.items():
        sample_rows = ctx.get('sample_rows', [])
        if not sample_rows:
            continue

        section_lines = [f"## {error_type} - Transformation Analysis"]
        section_lines.append(f"Total occurrences: {ctx.get('total_count', len(sample_rows))}")

        for sample in sample_rows[:max_examples]:
            row_num = sample.get('row_number', '?')
            section_lines.append(f"\n### Row {row_num}")
            section_lines.append("```")

            # Original values
            original = sample.get('original_values', {})
            if original:
                section_lines.append("BEFORE (Original Data):")
                for col, val in original.items():
                    section_lines.append(f"  {col}: {val}")

            # Transformed values
            transformed = sample.get('transformed_values', {})
            if transformed:
                section_lines.append("\nAFTER (Transformation Attempted):")
                for prop, val in transformed.items():
                    section_lines.append(f"  {prop}: {val}")

            # Error info
            error_stage = sample.get('error_stage', 'unknown')
            error_msg = sample.get('error_message', 'Unknown error')
            section_lines.append(f"\nERROR at '{error_stage}':")
            section_lines.append(f"  {error_msg}")
            section_lines.append("```")

        sections.append('\n'.join(section_lines))

    return '\n\n---\n\n'.join(sections) if sections else ""


def generate_enhanced_feedback(
    counters: Dict[str, int],
    error_context: Optional[Dict] = None,
    log_output: Optional[str] = None,
    attempt_number: int = 0,
    include_transformation: bool = True,
    include_patterns: bool = True
) -> str:
    """Generate comprehensive enhanced feedback with all Phase 9-10 features.

    This is the main entry point for enhanced feedback generation, combining:
    - Standard counter-based feedback
    - Transformation analysis (before/after)
    - Systematic pattern detection
    - Iteration-specific advice

    Args:
        counters: Parsed counter dictionary
        error_context: Enhanced error context dict (from EnhancedErrorContext.to_dict())
        log_output: Optional log output for sample extraction
        attempt_number: Current attempt number (0-indexed)
        include_transformation: Whether to include transformation feedback
        include_patterns: Whether to include pattern detection

    Returns:
        Comprehensive feedback string
    """
    sections = []

    # 1. Standard counter-based feedback
    base_feedback = generate_feedback(
        counters=counters,
        log_output=log_output,
        include_coverage=True,
        attempt_number=attempt_number
    )
    sections.append(base_feedback)

    # 2. Transformation analysis (if error_context provided)
    if include_transformation and error_context:
        errors_dict = error_context.get('errors', {})
        if errors_dict:
            transformation_feedback = generate_transformation_feedback(errors_dict)
            if transformation_feedback:
                sections.append(transformation_feedback)

    # 3. Pattern detection
    if include_patterns and error_context:
        errors_dict = error_context.get('errors', {})
        if errors_dict:
            patterns = detect_systematic_patterns(errors_dict)
            if patterns:
                pattern_feedback = format_pattern_feedback(patterns)
                sections.append(pattern_feedback)

    return '\n\n'.join(sections)
