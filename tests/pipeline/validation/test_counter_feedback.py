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
        assert '1250' in feedback  # input rows
        assert '45' in feedback  # output rows
        assert 'WARNING' in feedback  # Low coverage warning

        # Check error section
        assert 'Error Summary' in feedback
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
        assert 'Error Summary' in feedback
        assert 'Primary Issue' in feedback
        assert 'Place Resolution' in feedback
        assert 'Sample Error Messages' in feedback
        assert 'Generation Statistics' in feedback
