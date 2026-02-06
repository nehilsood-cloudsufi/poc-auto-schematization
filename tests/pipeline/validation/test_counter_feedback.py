"""Tests for counter_feedback module.

Tests the counter parsing, error detection, and feedback generation functionality
used for improving PVMAP validation feedback in the retry loop.
"""

import pytest
import tempfile
from pathlib import Path

from src.pipeline.validation.counter_feedback import (
    parse_counters_file,
    get_error_counters,
    get_warning_counters,
    calculate_coverage,
    identify_primary_error,
    match_error_pattern,
    extract_log_samples_for_error,
    generate_feedback,
    diagnose_validation_failure,
    prioritize_errors,
    extract_debug_examples,
    ERROR_PRIORITY,
    ITERATION_ADVICE,
)


class TestParseCountersFile:
    """Tests for parse_counters_file function."""

    def test_parse_valid_counters_file(self, tmp_path):
        """Test parsing a valid counters file."""
        counters_content = """key,value
error-unresolved-place,1205
input-rows-processed,1250
output-svobs-csv-rows,45
generated-statvars,10
"""
        counters_file = tmp_path / "test_counters.txt"
        counters_file.write_text(counters_content)

        counters = parse_counters_file(counters_file)

        assert counters['error-unresolved-place'] == 1205
        assert counters['input-rows-processed'] == 1250
        assert counters['output-svobs-csv-rows'] == 45
        assert counters['generated-statvars'] == 10

    def test_parse_empty_file(self, tmp_path):
        """Test parsing an empty counters file."""
        counters_file = tmp_path / "empty_counters.txt"
        counters_file.write_text("")

        counters = parse_counters_file(counters_file)

        assert counters == {}

    def test_parse_nonexistent_file(self, tmp_path):
        """Test parsing a non-existent file returns empty dict."""
        counters_file = tmp_path / "nonexistent.txt"

        counters = parse_counters_file(counters_file)

        assert counters == {}

    def test_parse_float_values(self, tmp_path):
        """Test parsing float values."""
        counters_content = """key,value
processing-rate,123.45
count,100
"""
        counters_file = tmp_path / "float_counters.txt"
        counters_file.write_text(counters_content)

        counters = parse_counters_file(counters_file)

        assert counters['processing-rate'] == 123.45
        assert counters['count'] == 100  # Should be int, not float


class TestGetErrorCounters:
    """Tests for get_error_counters function."""

    def test_extract_error_counters(self):
        """Test extracting only error counters."""
        counters = {
            'error-unresolved-place': 100,
            'error-statvar-missing-property': 5,
            'warning-something': 10,
            'input-rows-processed': 1000,
            'generated-statvars': 50,
        }

        errors = get_error_counters(counters)

        assert len(errors) == 2
        assert errors['error-unresolved-place'] == 100
        assert errors['error-statvar-missing-property'] == 5
        assert 'warning-something' not in errors
        assert 'input-rows-processed' not in errors

    def test_exclude_zero_error_counters(self):
        """Test that zero-value error counters are excluded."""
        counters = {
            'error-unresolved-place': 100,
            'error-something-else': 0,
        }

        errors = get_error_counters(counters)

        assert len(errors) == 1
        assert 'error-something-else' not in errors


class TestGetWarningCounters:
    """Tests for get_warning_counters function."""

    def test_extract_warning_and_dropped_counters(self):
        """Test extracting warning and dropped counters."""
        counters = {
            'warning-svobs-missing-place': 10,
            'dropped-svobs-invalid': 5,
            'dropped-statvars-without-svobs': 3,
            'error-unresolved-place': 100,
            'input-rows-processed': 1000,
        }

        warnings = get_warning_counters(counters)

        assert len(warnings) == 3
        assert warnings['warning-svobs-missing-place'] == 10
        assert warnings['dropped-svobs-invalid'] == 5
        assert warnings['dropped-statvars-without-svobs'] == 3
        assert 'error-unresolved-place' not in warnings


class TestCalculateCoverage:
    """Tests for calculate_coverage function."""

    def test_calculate_coverage_normal(self):
        """Test coverage calculation with normal counters."""
        counters = {
            'input-rows-processed': 1000,
            'output-svobs-csv-rows': 800,
        }

        coverage, output, input_rows = calculate_coverage(counters)

        assert coverage == 0.8
        assert output == 800
        assert input_rows == 1000

    def test_calculate_coverage_zero_input(self):
        """Test coverage calculation with zero input rows."""
        counters = {
            'input-rows-processed': 0,
            'output-svobs-csv-rows': 0,
        }

        coverage, output, input_rows = calculate_coverage(counters)

        assert coverage == 0.0
        assert output == 0
        assert input_rows == 0

    def test_calculate_coverage_prefixed_counters(self):
        """Test coverage calculation with prefixed counters."""
        counters = {
            '1:process_input_input-rows-processed': 1000,
            '4:write_svobs_csv_output-svobs-csv-rows': 500,
        }

        coverage, output, input_rows = calculate_coverage(counters)

        assert coverage == 0.5
        assert output == 500
        assert input_rows == 1000


class TestIdentifyPrimaryError:
    """Tests for identify_primary_error function."""

    def test_identify_highest_count_error(self):
        """Test identification of primary error."""
        errors = {
            'error-unresolved-place': 1205,
            'error-statvar-missing-property': 5,
            'error-mismatched-svobs': 100,
        }

        primary = identify_primary_error(errors)

        assert primary == 'error-unresolved-place'

    def test_identify_primary_error_empty(self):
        """Test with no errors."""
        errors = {}

        primary = identify_primary_error(errors)

        assert primary is None


class TestMatchErrorPattern:
    """Tests for match_error_pattern function."""

    def test_match_known_error_pattern(self):
        """Test matching known error patterns."""
        pattern = match_error_pattern('error-unresolved-place')

        assert pattern is not None
        assert pattern['category'] == 'Place Resolution'
        assert 'FIPS codes' in pattern['common_causes'][0]

    def test_match_unknown_error_pattern(self):
        """Test matching unknown error pattern."""
        pattern = match_error_pattern('error-unknown-type')

        assert pattern is None

    def test_match_prefix_error_pattern(self):
        """Test matching error patterns by prefix."""
        # Error with suffix should match base pattern
        pattern = match_error_pattern('error-aggregate-invalid-values')

        assert pattern is not None
        assert pattern['category'] == 'Aggregation Error'


class TestExtractLogSamplesForError:
    """Tests for extract_log_samples_for_error function."""

    def test_extract_place_error_samples(self):
        """Test extracting log samples for place errors."""
        log_output = """
INFO: Processing data...
WARNING: Unable to resolve place '6' in {observationAbout: 6}
WARNING: Unable to resolve place '12' in {observationAbout: 12}
INFO: More processing...
ERROR: unresolved place error
INFO: Done.
"""
        samples = extract_log_samples_for_error(log_output, 'error-unresolved-place')

        assert len(samples) >= 2
        assert any('Unable to resolve place' in s for s in samples)

    def test_extract_statvar_error_samples(self):
        """Test extracting log samples for statvar errors."""
        log_output = """
INFO: Processing...
ERROR: Missing statvar properties ['populationType'] in {dcid: ...}
WARNING: measuredProperty not found
INFO: Done.
"""
        samples = extract_log_samples_for_error(
            log_output, 'error-statvar-missing-property'
        )

        assert len(samples) >= 1
        assert any('Missing' in s or 'populationType' in s or 'measuredProperty' in s
                   for s in samples)

    def test_max_samples_limit(self):
        """Test that max_samples limit is respected."""
        log_output = "\n".join([
            f"WARNING: Unable to resolve place '{i}'"
            for i in range(20)
        ])

        samples = extract_log_samples_for_error(
            log_output, 'error-unresolved-place', max_samples=3
        )

        assert len(samples) == 3


class TestGenerateFeedback:
    """Tests for generate_feedback function."""

    def test_generate_feedback_with_errors(self):
        """Test feedback generation with errors."""
        counters = {
            'error-unresolved-place': 1205,
            'error-statvar-missing-property': 5,
            'input-rows-processed': 1250,
            'output-svobs-csv-rows': 45,
            'generated-statvars': 10,
        }

        feedback = generate_feedback(counters)

        # Check coverage section
        assert 'Coverage Analysis' in feedback
        assert '1,250' in feedback or '1250' in feedback  # input rows (may be formatted)
        assert '45' in feedback  # output rows
        assert 'WARNING' in feedback  # Low coverage warning

        # Check error section (changed from "Error Summary" to "Prioritized Errors" in enhanced version)
        assert 'Prioritized Errors' in feedback or 'Error Summary' in feedback
        assert 'error-unresolved-place' in feedback
        assert '1,205' in feedback  # Formatted count

        # Check diagnosis section
        assert 'Place Resolution' in feedback
        assert 'geoId' in feedback  # Fix pattern

    def test_generate_feedback_no_errors(self):
        """Test feedback generation with no errors."""
        counters = {
            'input-rows-processed': 1000,
            'output-svobs-csv-rows': 950,
            'generated-statvars': 10,
            'generated-svobs': 950,
        }

        feedback = generate_feedback(counters)

        # Should have coverage and generation stats
        assert 'Coverage Analysis' in feedback
        assert '95.0%' in feedback
        assert 'Generation Statistics' in feedback
        assert 'Error Summary' not in feedback

    def test_generate_feedback_with_warnings_only(self):
        """Test feedback generation with warnings but no errors."""
        counters = {
            'warning-svobs-missing-place': 10,
            'dropped-svobs-invalid': 5,
            'input-rows-processed': 1000,
            'output-svobs-csv-rows': 985,
        }

        feedback = generate_feedback(counters)

        assert 'Warnings' in feedback
        assert 'warning-svobs-missing-place' in feedback

    def test_generate_feedback_empty_counters(self):
        """Test feedback generation with empty counters."""
        counters = {}

        feedback = generate_feedback(counters)

        assert 'No counter data available' in feedback or 'Coverage' in feedback


class TestDiagnoseValidationFailure:
    """Tests for diagnose_validation_failure function."""

    def test_diagnose_failure(self, tmp_path):
        """Test diagnostic output structure."""
        counters_content = """key,value
error-unresolved-place,1205
input-rows-processed,1250
output-svobs-csv-rows,45
"""
        counters_file = tmp_path / "test_counters.txt"
        counters_file.write_text(counters_content)

        result = diagnose_validation_failure(counters_file)

        assert result['counters_found'] is True
        assert result['coverage_ratio'] == pytest.approx(0.036, rel=0.01)
        assert result['input_rows'] == 1250
        assert result['output_rows'] == 45
        assert result['error_count'] == 1205
        assert 'error-unresolved-place' in result['error_types']
        assert result['primary_error'] == 'error-unresolved-place'
        assert result['primary_error_pattern'] is not None

    def test_diagnose_nonexistent_file(self, tmp_path):
        """Test diagnostic with nonexistent file."""
        result = diagnose_validation_failure(tmp_path / "nonexistent.txt")

        assert result['counters_found'] is False
        assert result['error_count'] == 0


class TestPrioritizeErrors:
    """Tests for prioritize_errors function (Phase 9 enhancement)."""

    def test_prioritize_by_error_priority_order(self):
        """Errors should be sorted by ERROR_PRIORITY order, then by count."""
        errors = {
            'error-unresolved-place': 100,
            'error-pvmap-dropped-undefined-property': 10,  # Higher priority
            'error-mismatched-svobs': 50,
        }

        sorted_errors = prioritize_errors(errors)

        # pvmap-dropped should come first (priority 0)
        assert sorted_errors[0][0] == 'error-pvmap-dropped-undefined-property'
        # unresolved-place should come second (priority 1)
        assert sorted_errors[1][0] == 'error-unresolved-place'
        # mismatched-svobs should come third (priority 4)
        assert sorted_errors[2][0] == 'error-mismatched-svobs'

    def test_prioritize_unknown_errors_last(self):
        """Unknown errors should be sorted to the end by count."""
        errors = {
            'error-unresolved-place': 100,
            'error-unknown-custom': 500,  # Unknown, high count
        }

        sorted_errors = prioritize_errors(errors)

        # Known error should come first
        assert sorted_errors[0][0] == 'error-unresolved-place'
        # Unknown error should come last
        assert sorted_errors[1][0] == 'error-unknown-custom'

    def test_prioritize_same_priority_by_count(self):
        """Errors with same priority should be sorted by count descending."""
        errors = {
            'error-unresolved-place': 100,
            # Both unknown, should sort by count
            'error-custom-a': 500,
            'error-custom-b': 200,
        }

        sorted_errors = prioritize_errors(errors)

        # Known error first
        assert sorted_errors[0][0] == 'error-unresolved-place'
        # Then unknown by count
        assert sorted_errors[1][0] == 'error-custom-a'
        assert sorted_errors[2][0] == 'error-custom-b'


class TestExtractDebugExamples:
    """Tests for extract_debug_examples function (Phase 9 enhancement)."""

    def test_extract_debug_examples_from_counters(self):
        """Should extract specific failing values from debug counters."""
        counters = {
            'error-unresolved-place': 1205,
            'error-unresolved-place_geoId/6': 500,
            'error-unresolved-place_geoId/12': 300,
            'error-unresolved-place_geoId/48': 200,
            'other-counter': 100,
        }

        examples = extract_debug_examples(counters, 'error-unresolved-place')

        assert len(examples) == 3
        # Should be sorted by count (descending)
        assert examples[0] == 'geoId/6'
        assert examples[1] == 'geoId/12'
        assert examples[2] == 'geoId/48'

    def test_extract_debug_examples_max_limit(self):
        """Should respect max_examples limit."""
        counters = {
            'error-unresolved-place_a': 10,
            'error-unresolved-place_b': 9,
            'error-unresolved-place_c': 8,
            'error-unresolved-place_d': 7,
            'error-unresolved-place_e': 6,
            'error-unresolved-place_f': 5,
        }

        examples = extract_debug_examples(counters, 'error-unresolved-place', max_examples=3)

        assert len(examples) == 3

    def test_extract_debug_examples_empty_when_no_match(self):
        """Should return empty list when no debug counters match."""
        counters = {
            'error-unresolved-place': 100,
            'other-counter': 50,
        }

        examples = extract_debug_examples(counters, 'error-unresolved-place')

        assert examples == []

    def test_extract_debug_examples_ignores_zero_counts(self):
        """Should ignore debug counters with zero count."""
        counters = {
            'error-unresolved-place_a': 10,
            'error-unresolved-place_b': 0,
        }

        examples = extract_debug_examples(counters, 'error-unresolved-place')

        assert len(examples) == 1
        assert examples[0] == 'a'


class TestIterationAdvice:
    """Tests for iteration-specific advice (Phase 9 enhancement)."""

    def test_iteration_advice_exists_for_attempts_1_to_3(self):
        """ITERATION_ADVICE should have entries for attempts 1, 2, and 3."""
        assert 1 in ITERATION_ADVICE
        assert 2 in ITERATION_ADVICE
        assert 3 in ITERATION_ADVICE

    def test_iteration_advice_includes_in_feedback(self):
        """generate_feedback should include iteration advice when attempt_number > 0."""
        counters = {
            'error-unresolved-place': 100,
            'input-rows-processed': 1000,
            'output-svobs-csv-rows': 100,
        }

        # Attempt 1 (second try)
        feedback = generate_feedback(counters, attempt_number=1)
        assert 'Retry Strategy (Attempt 1 → 2)' in feedback

        # Attempt 2 (third try)
        feedback = generate_feedback(counters, attempt_number=2)
        assert 'Retry Strategy (Attempt 2 → 3)' in feedback

        # Attempt 3 (final try)
        feedback = generate_feedback(counters, attempt_number=3)
        assert 'Retry Strategy (Attempt 3 → 4)' in feedback

    def test_no_iteration_advice_for_first_attempt(self):
        """generate_feedback should not include iteration advice on first attempt."""
        counters = {
            'error-unresolved-place': 100,
            'input-rows-processed': 1000,
            'output-svobs-csv-rows': 100,
        }

        feedback = generate_feedback(counters, attempt_number=0)

        assert 'Retry Strategy' not in feedback


class TestEnhancedFeedbackWithDebugContext:
    """Tests for generate_feedback with debug context (Phase 9 enhancement)."""

    def test_feedback_includes_specific_failing_examples(self):
        """Feedback should include specific failing examples from debug counters."""
        counters = {
            'error-unresolved-place': 1000,
            'error-unresolved-place_6': 500,  # California without leading zero
            'error-unresolved-place_12': 300,  # Florida without leading zero
            'input-rows-processed': 1000,
            'output-svobs-csv-rows': 0,
        }

        feedback = generate_feedback(counters)

        # Should include the specific failing examples
        assert 'Specific Failing Examples' in feedback
        assert '`6`' in feedback or '6' in feedback
        assert '`12`' in feedback or '12' in feedback

    def test_feedback_uses_prioritized_error_order(self):
        """Feedback should list errors in priority order."""
        counters = {
            'error-unresolved-place': 100,
            'error-pvmap-dropped-undefined-property': 10,
            'input-rows-processed': 1000,
            'output-svobs-csv-rows': 100,
        }

        feedback = generate_feedback(counters)

        # Should mention prioritized errors
        assert 'Prioritized Errors' in feedback or 'Error Summary' in feedback
        # pvmap-dropped should appear before unresolved-place in listing
        pvmap_pos = feedback.find('error-pvmap-dropped-undefined-property')
        place_pos = feedback.find('error-unresolved-place')
        if pvmap_pos != -1 and place_pos != -1:
            assert pvmap_pos < place_pos


class TestIntegration:
    """Integration tests for the full feedback generation pipeline."""

    def test_full_feedback_pipeline(self, tmp_path):
        """Test complete feedback generation from counters file."""
        # Create a realistic counters file
        counters_content = """key,value
1:process_input_input-rows-processed,5000
1:process_input_processed,5000
error-unresolved-place,4500
error-statvar-missing-property,100
generated-statvars,50
generated-svobs,500
output-svobs-csv-rows,500
4:write_svobs_csv_output-svobs-csv-rows,500
"""
        counters_file = tmp_path / "processed_counters.txt"
        counters_file.write_text(counters_content)

        # Create sample log output
        log_output = """
WARNING: Unable to resolve place '6' in {observationAbout: 6}
WARNING: Unable to resolve place '12' in {observationAbout: 12}
ERROR: Missing statvar properties ['populationType'] in {...}
"""

        counters = parse_counters_file(counters_file)
        feedback = generate_feedback(counters, log_output)

        # Verify complete feedback
        assert 'Coverage Analysis' in feedback
        assert 'Prioritized Errors' in feedback or 'Error Summary' in feedback
        assert 'Primary Issue' in feedback
        assert 'Place Resolution' in feedback
        assert 'Sample Error Messages' in feedback
        assert 'Generation Statistics' in feedback

    def test_full_pipeline_with_debug_counters_and_iteration(self, tmp_path):
        """Test complete pipeline with debug counters and iteration advice."""
        counters_content = """key,value
input-rows-processed,1000
output-svobs-csv-rows,100
error-unresolved-place,800
error-unresolved-place_geoId/6,400
error-unresolved-place_geoId/12,300
error-unresolved-place_geoId/48,100
generated-statvars,5
"""
        counters_file = tmp_path / "processed_counters.txt"
        counters_file.write_text(counters_content)

        counters = parse_counters_file(counters_file)
        feedback = generate_feedback(counters, log_output=None, attempt_number=2)

        # Should have all enhanced features
        assert 'Coverage Analysis' in feedback
        assert 'Specific Failing Examples' in feedback
        assert 'geoId/6' in feedback
        assert 'Retry Strategy (Attempt 2 → 3)' in feedback
