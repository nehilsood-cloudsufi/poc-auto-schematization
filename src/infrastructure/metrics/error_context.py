"""Enhanced error context for row-level failure tracking.

This module provides data structures for capturing detailed row-level error context
during PVMAP validation, including:
- Specific failing row data (before/after transformation)
- Error stage identification (pv_mapping, place_resolution, statvar_generation)
- Pattern detection across failures
- Serialization with size limits for token budget

Usage:
    from src.infrastructure.metrics.error_context import EnhancedErrorContext, FailingRowSample

    context = EnhancedErrorContext()
    context.add_error(
        error_type='error-unresolved-place',
        sample=FailingRowSample(
            row_number=5,
            original_values={'State FIPS': '6', 'Year': '2020'},
            transformed_values={'observationAbout': 'geoId/6'},
            error_stage='place_resolution',
            error_message='Unable to resolve "geoId/6" - expected "geoId/06"'
        )
    )

    # Serialize for LLM feedback (respects size limits)
    json_output = context.to_json(max_size_kb=50)
"""

import json
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional, Set


@dataclass
class FailingRowSample:
    """Sample of a row that caused an error during validation.

    Captures both the original input values and the attempted transformation,
    allowing the LLM to see exactly what went wrong.

    Attributes:
        row_number: 1-indexed row number from input data
        original_values: dict mapping column name -> original value from data
        transformed_values: dict mapping property name -> attempted transformed value
        error_stage: Pipeline stage where error occurred
            - 'pv_mapping': Error during property-value mapping
            - 'place_resolution': Error resolving place to DCID
            - 'statvar_generation': Error generating StatVar
            - 'date_resolution': Error parsing date
            - 'value_extraction': Error extracting numeric value
        error_message: Human-readable error description
    """
    row_number: int
    original_values: Dict[str, str]
    transformed_values: Dict[str, str] = field(default_factory=dict)
    error_stage: str = ""
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'row_number': self.row_number,
            'original_values': self.original_values,
            'transformed_values': self.transformed_values,
            'error_stage': self.error_stage,
            'error_message': self.error_message
        }


@dataclass
class ErrorTypeContext:
    """Context for a specific error type, aggregating samples and patterns.

    Tracks:
    - Total count of this error type
    - Sample rows (up to MAX_SAMPLES) for LLM analysis
    - Unique failing values per column for pattern detection

    Attributes:
        error_type: The error counter name (e.g., 'error-unresolved-place')
        total_count: Total occurrences of this error
        sample_rows: List of FailingRowSample instances
        unique_failing_values: Dict mapping column -> set of failing values
    """
    error_type: str
    total_count: int = 0
    sample_rows: List[FailingRowSample] = field(default_factory=list)
    unique_failing_values: Dict[str, Set[str]] = field(
        default_factory=lambda: defaultdict(set)
    )

    MAX_SAMPLES: int = 5
    MAX_UNIQUE_VALUES: int = 10

    def add_sample(self, sample: FailingRowSample) -> None:
        """Add a sample row, keeping only first N samples.

        Also tracks unique failing values for pattern detection.

        Args:
            sample: FailingRowSample to add
        """
        self.total_count += 1

        # Keep only first MAX_SAMPLES
        if len(self.sample_rows) < self.MAX_SAMPLES:
            self.sample_rows.append(sample)

        # Track unique failing values per column
        for col, val in sample.original_values.items():
            if len(self.unique_failing_values[col]) < self.MAX_UNIQUE_VALUES:
                self.unique_failing_values[col].add(str(val))

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'error_type': self.error_type,
            'total_count': self.total_count,
            'sample_rows': [s.to_dict() for s in self.sample_rows],
            'unique_failing_values': {
                col: list(vals) for col, vals in self.unique_failing_values.items()
            }
        }

    def detect_patterns(self) -> List[Dict[str, Any]]:
        """Detect systematic patterns in this error type's failures.

        Returns:
            List of detected patterns with confidence scores
        """
        patterns = []

        for col, values in self.unique_failing_values.items():
            value_list = list(values)

            # Single value pattern - all errors have same value
            if len(value_list) == 1 and self.total_count >= 3:
                patterns.append({
                    'type': 'single_value',
                    'column': col,
                    'value': value_list[0],
                    'count': self.total_count,
                    'confidence': 1.0,
                    'description': (
                        f"All {self.total_count} '{self.error_type}' errors "
                        f"have {col}='{value_list[0]}'"
                    )
                })

            # Few values pattern - limited unique values causing many errors
            elif len(value_list) < 5 and self.total_count >= 10:
                patterns.append({
                    'type': 'few_values',
                    'column': col,
                    'values': value_list,
                    'count': self.total_count,
                    'confidence': 0.8,
                    'description': (
                        f"Only {len(value_list)} unique values in '{col}' "
                        f"causing {self.total_count} errors"
                    )
                })

        return patterns


@dataclass
class EnhancedErrorContext:
    """Container for all enhanced error context across error types.

    Provides aggregation, pattern detection, and serialization for
    passing detailed error information to the LLM feedback loop.

    Attributes:
        errors: Dict mapping error_type -> ErrorTypeContext
        pipeline_stage: Current pipeline stage name
        dataset_name: Name of dataset being processed
    """
    errors: Dict[str, ErrorTypeContext] = field(default_factory=dict)
    pipeline_stage: str = ""
    dataset_name: str = ""

    def add_error(
        self,
        error_type: str,
        sample: FailingRowSample
    ) -> None:
        """Add an error with row-level context.

        Args:
            error_type: Error counter name (e.g., 'error-unresolved-place')
            sample: FailingRowSample with detailed context
        """
        if error_type not in self.errors:
            self.errors[error_type] = ErrorTypeContext(error_type=error_type)
        self.errors[error_type].add_sample(sample)

    def get_total_errors(self) -> int:
        """Get total error count across all types."""
        return sum(ctx.total_count for ctx in self.errors.values())

    def get_primary_error(self) -> Optional[str]:
        """Get the error type with highest count."""
        if not self.errors:
            return None
        return max(self.errors.items(), key=lambda x: x[1].total_count)[0]

    def detect_all_patterns(self) -> List[Dict[str, Any]]:
        """Detect patterns across all error types.

        Returns:
            List of patterns sorted by confidence (highest first)
        """
        all_patterns = []
        for ctx in self.errors.values():
            patterns = ctx.detect_patterns()
            for p in patterns:
                p['error_type'] = ctx.error_type
            all_patterns.extend(patterns)

        # Sort by confidence descending
        return sorted(all_patterns, key=lambda x: -x['confidence'])

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            'pipeline_stage': self.pipeline_stage,
            'dataset_name': self.dataset_name,
            'total_errors': self.get_total_errors(),
            'primary_error': self.get_primary_error(),
            'errors': {
                error_type: ctx.to_dict()
                for error_type, ctx in self.errors.items()
            },
            'patterns': self.detect_all_patterns()
        }

    def to_json(self, max_size_kb: int = 50) -> str:
        """Serialize to JSON, respecting size limits.

        If the full JSON exceeds max_size_kb, truncates sample_rows
        to fit within the limit.

        Args:
            max_size_kb: Maximum size in kilobytes (default: 50KB)

        Returns:
            JSON string representation
        """
        data = self.to_dict()
        json_str = json.dumps(data, indent=2)

        max_bytes = max_size_kb * 1024

        # If within limit, return as-is
        if len(json_str.encode('utf-8')) <= max_bytes:
            return json_str

        # Truncate sample_rows to fit
        for error_ctx in data.get('errors', {}).values():
            samples = error_ctx.get('sample_rows', [])
            # Reduce samples
            while len(samples) > 1:
                samples.pop()
                json_str = json.dumps(data, indent=2)
                if len(json_str.encode('utf-8')) <= max_bytes:
                    break

        # If still too large, truncate error messages
        if len(json_str.encode('utf-8')) > max_bytes:
            for error_ctx in data.get('errors', {}).values():
                for sample in error_ctx.get('sample_rows', []):
                    msg = sample.get('error_message', '')
                    if len(msg) > 100:
                        sample['error_message'] = msg[:100] + '...'

            json_str = json.dumps(data, indent=2)

        return json_str

    def format_transformation_feedback(self) -> str:
        """Format error context as human-readable transformation feedback.

        Shows before/after transformation for each error type's samples,
        making it clear what the PVMAP is doing wrong.

        Returns:
            Formatted string for LLM feedback
        """
        sections = []

        for error_type, ctx in self.errors.items():
            if not ctx.sample_rows:
                continue

            section_lines = [f"## {error_type} - Transformation Analysis"]
            section_lines.append(f"Total occurrences: {ctx.total_count}")

            for sample in ctx.sample_rows[:3]:
                section_lines.append(f"\n### Row {sample.row_number}")
                section_lines.append("```")
                section_lines.append("BEFORE (Original Data):")
                for col, val in sample.original_values.items():
                    section_lines.append(f"  {col}: {val}")

                if sample.transformed_values:
                    section_lines.append("\nAFTER (Transformation Attempted):")
                    for prop, val in sample.transformed_values.items():
                        section_lines.append(f"  {prop}: {val}")

                section_lines.append(f"\nERROR at '{sample.error_stage}':")
                section_lines.append(f"  {sample.error_message}")
                section_lines.append("```")

            sections.append('\n'.join(section_lines))

        return '\n\n---\n\n'.join(sections) if sections else ""

    def format_pattern_feedback(self) -> str:
        """Format detected patterns as actionable feedback.

        Returns:
            Formatted string highlighting systematic issues
        """
        patterns = self.detect_all_patterns()

        if not patterns:
            return "No systematic patterns detected - errors may be random data issues."

        lines = ["## Systematic Error Patterns Detected", ""]

        for i, p in enumerate(patterns[:5], 1):
            lines.append(f"**Pattern {i}** (confidence: {p['confidence']:.0%})")
            lines.append(f"  {p['description']}")

            if p['type'] == 'single_value':
                lines.append(
                    f"  **Action:** Check PVMAP mapping for column '{p['column']}' - "
                    f"the value '{p['value']}' is causing all errors"
                )
            elif p['type'] == 'few_values':
                lines.append(
                    f"  **Action:** Add specific mappings for values: {p['values']}"
                )
            lines.append("")

        return '\n'.join(lines)


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'FailingRowSample',
    'ErrorTypeContext',
    'EnhancedErrorContext',
]
