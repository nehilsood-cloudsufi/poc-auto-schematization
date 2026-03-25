"""Validation utilities for the pipeline.

This module provides the StatVar processor for validating PVMAP transformations
and counter-based feedback generation for the retry loop.
"""

from .counter_feedback import (
    parse_counters_file,
    generate_feedback,
    generate_feedback_from_file,
    calculate_coverage,
    get_error_counters,
    get_warning_counters,
    diagnose_validation_failure,
)

__all__ = [
    'stat_var_processor',
    'parse_counters_file',
    'generate_feedback',
    'generate_feedback_from_file',
    'calculate_coverage',
    'get_error_counters',
    'get_warning_counters',
    'diagnose_validation_failure',
]
