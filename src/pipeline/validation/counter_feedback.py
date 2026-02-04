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

Usage:
    from src.pipeline.validation.counter_feedback import parse_counters_file, generate_feedback

    counters = parse_counters_file(counters_file_path)
    feedback = generate_feedback(counters, log_output=optional_log_text)
"""

import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# Error counter patterns and their fix recommendations
ERROR_PATTERNS = {
    'error-unresolved-place': {
        'category': 'Place Resolution',
        'description': 'Place values could not be converted to Data Commons DCIDs',
        'common_causes': [
            'FIPS codes missing leading zeros (e.g., 6 instead of 06)',
            'Missing geoId/ prefix in observationAbout mapping',
            'Invalid place identifiers that don\'t match Data Commons schema',
        ],
        'fix_pattern': '''Fix place mapping in PVMAP:
- Add dcid:geoId/ prefix: observationAbout,dcid:geoId/{Data}
- Ensure FIPS codes are zero-padded (2 digits for state, 5 for county)
- For country codes, use dcid:country/{Data} format''',
    },
    'error-statvar-missing-property': {
        'category': 'StatVar Definition',
        'description': 'StatVar definitions are incomplete (missing required properties)',
        'common_causes': [
            'Missing populationType (what entity is being counted)',
            'Missing measuredProperty (what aspect is being measured)',
            'Missing value mapping for the measurement column',
        ],
        'fix_pattern': '''Fix StatVar definition in PVMAP:
Required properties for every StatVar:
- populationType: what are we counting? (Person, Household, Establishment, etc.)
- measuredProperty: what aspect? (count, income, age, amount, etc.)
- value: the numeric measurement from the data

Example: Population,populationType,dcid:Person,measuredProperty,dcid:count,value,{Number}''',
    },
    'error-mismatched-svobs': {
        'category': 'Duplicate Observations',
        'description': 'Multiple rows creating the same observation (collision)',
        'common_causes': [
            'A dimension column (Gender, Age, Race, etc.) is not mapped',
            'Multiple values for same Place + Date + StatVar combination',
            'Missing constraint property that differentiates rows',
        ],
        'fix_pattern': '''Fix by mapping the differentiating column:
The uniqueness rule: Place + Date + StatVar = ONE value only

Identify which column creates different rows and add its mapping:
- For gender: Male,gender,dcid:Male and Female,gender,dcid:Female
- For age groups: map each age bracket to appropriate constraint
- For categories: map each category value as a StatVar constraint''',
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
- Match CSV column headers exactly (case-sensitive)
- Check for underscores vs spaces in column names
- Verify column exists in the input data''',
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
- observationAbout: the place DCID
- observationDate: the date/time of observation
- value: the numeric measurement
- variableMeasured: reference to StatVar (auto-generated)''',
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
    include_coverage: bool = True
) -> str:
    """Generate targeted feedback based on counter analysis.

    Args:
        counters: Parsed counter dictionary
        log_output: Optional log output for extracting sample errors
        include_coverage: Whether to include coverage analysis

    Returns:
        Formatted feedback string for LLM retry loop
    """
    sections = []

    # 1. Coverage Analysis
    if include_coverage:
        coverage, output_rows, input_rows = calculate_coverage(counters)
        coverage_section = f"""## Coverage Analysis
- Input rows processed: {input_rows}
- Output observations generated: {output_rows}
- Coverage ratio: {coverage*100:.1f}%"""

        if coverage < 0.5:
            coverage_section += "\n\n⚠️ WARNING: Coverage below 50% - many rows are being dropped!"
        elif coverage < 0.8:
            coverage_section += "\n\n⚠️ NOTICE: Coverage below 80% - investigate dropped rows."

        sections.append(coverage_section)

    # 2. Error Analysis
    error_counters = get_error_counters(counters)

    if error_counters:
        error_section = "## Error Summary\n"
        error_section += "The following errors were detected:\n\n"

        # Sort errors by count (descending)
        sorted_errors = sorted(error_counters.items(), key=lambda x: -x[1])

        for error_name, count in sorted_errors:
            error_section += f"- **{error_name}**: {count:,} occurrences\n"

        sections.append(error_section)

        # 3. Primary Error Diagnosis
        primary_error = identify_primary_error(error_counters)
        if primary_error:
            pattern = match_error_pattern(primary_error)

            if pattern:
                diagnosis = f"""## Primary Issue: {pattern['category']}

**Problem:** {pattern['description']}

**Common Causes:**
"""
                for cause in pattern.get('common_causes', []):
                    diagnosis += f"- {cause}\n"

                diagnosis += f"""
**How to Fix:**
{pattern['fix_pattern']}"""
                sections.append(diagnosis)
            else:
                # Unknown error pattern
                sections.append(f"""## Primary Issue: {primary_error}

This error type is not in the known patterns.
Please review the PVMAP for issues related to: {primary_error.replace('error-', '').replace('-', ' ')}""")

        # 4. Sample Error Lines
        if log_output and primary_error:
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
