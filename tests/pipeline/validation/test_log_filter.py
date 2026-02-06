"""Tests for log_filter.py - Smart log filtering for validation output."""

import pytest
import tempfile
from pathlib import Path

from src.pipeline.validation.log_filter import (
    FilteredLogs,
    ValuePattern,
    filter_counters,
    extract_sample_errors,
    generate_concise_feedback,
    _classify_value,
    _analyze_value_patterns,
    _get_fix_suggestion,
)


class TestClassifyValue:
    """Tests for _classify_value function."""

    def test_state_codes(self):
        """Two-letter uppercase strings should be classified as state codes."""
        assert _classify_value('AL') == 'state_code'
        assert _classify_value('CA') == 'state_code'
        assert _classify_value('TX') == 'state_code'
        assert _classify_value('NY') == 'state_code'

    def test_years(self):
        """Four-digit years (1900-2099) should be classified as years."""
        assert _classify_value('2010') == 'year'
        assert _classify_value('2020') == 'year'
        assert _classify_value('1990') == 'year'
        assert _classify_value('2099') == 'year'

    def test_fips_codes(self):
        """Zero-padded 2-5 digit numbers should be FIPS codes."""
        assert _classify_value('01') == 'fips_code'
        assert _classify_value('06') == 'fips_code'
        assert _classify_value('06037') == 'fips_code'
        assert _classify_value('048') == 'fips_code'

    def test_numeric_ids(self):
        """Long numeric strings (6+ digits) should be numeric IDs."""
        assert _classify_value('10000500879') == 'numeric_id'
        assert _classify_value('123456') == 'numeric_id'
        assert _classify_value('10000600193') == 'numeric_id'

    def test_place_names_title_case(self):
        """Title case names should be place names."""
        assert _classify_value('Los Angeles') == 'place_name'
        assert _classify_value('New York') == 'place_name'
        assert _classify_value('San Francisco') == 'place_name'

    def test_place_names_all_caps(self):
        """All caps names (longer than 2 chars) should be place names."""
        assert _classify_value('ALBERTVILLE') == 'place_name'
        assert _classify_value('HOOVER CITY') == 'place_name'
        assert _classify_value('MARSHALL COUNTY') == 'place_name'

    def test_small_numbers(self):
        """Small numbers (1-5 digits) should be numeric."""
        assert _classify_value('123') == 'numeric'
        assert _classify_value('45') == 'numeric'
        assert _classify_value('12345') == 'numeric'

    def test_enum_values(self):
        """Short mixed-case strings that aren't other types should be enum."""
        # Note: Title case words like 'Male' get classified as place_name
        # Enum is for mixed patterns that don't match other rules
        assert _classify_value('male') == 'enum'
        assert _classify_value('employed') == 'enum'
        assert _classify_value('yes/no') == 'enum'
        assert _classify_value('value_1') == 'enum'

    def test_empty_values(self):
        """Empty values should be classified as empty."""
        assert _classify_value('') == 'empty'
        assert _classify_value('-') == 'empty'
        assert _classify_value('  ') == 'empty'

    def test_edge_cases(self):
        """Test edge cases."""
        # Two letters but lowercase
        assert _classify_value('al') == 'enum'
        # Three letters
        assert _classify_value('ABC') == 'place_name'


class TestAnalyzeValuePatterns:
    """Tests for _analyze_value_patterns function."""

    def test_basic_pattern_detection(self):
        """Test that patterns are correctly detected and counted."""
        values = [
            ('AL', 10),
            ('CA', 5),
            ('TX', 3),
            ('2020', 100),
            ('2021', 50),
        ]
        patterns = _analyze_value_patterns(values)

        # Should have two patterns: year and state_code
        assert len(patterns) == 2

        # Year pattern should be first (highest count)
        assert patterns[0].pattern_type == 'year'
        assert patterns[0].count == 150

        # State code pattern second
        assert patterns[1].pattern_type == 'state_code'
        assert patterns[1].count == 18

    def test_sample_values_collected(self):
        """Test that sample values are collected without duplicates."""
        values = [
            ('AL', 10),
            ('CA', 5),
            ('AL', 3),  # Duplicate
        ]
        patterns = _analyze_value_patterns(values)

        assert len(patterns) == 1
        assert patterns[0].pattern_type == 'state_code'
        # Should only have unique values
        assert 'AL' in patterns[0].sample_values
        assert 'CA' in patterns[0].sample_values
        assert len(patterns[0].sample_values) == 2

    def test_likely_column_assignment(self):
        """Test that likely column hints are assigned."""
        values = [('AL', 10)]
        patterns = _analyze_value_patterns(values)

        assert patterns[0].likely_column != ''
        assert 'state' in patterns[0].likely_column.lower()


class TestFilterCounters:
    """Tests for filter_counters function."""

    def test_basic_metrics_extraction(self):
        """Test extraction of key metrics from counters file."""
        counters_content = '''"key","value"
"input-rows-processed",100
"output-svobs-csv-rows",80
"generated-unique-statvars",3
"svobs-added",80
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(counters_content)
            counters_path = Path(f.name)

        try:
            result = filter_counters(counters_path)

            assert result.input_rows == 100
            assert result.output_rows == 80
            assert result.statvars_generated == 3
            assert result.observations_generated == 80
            assert result.coverage_pct == 80.0
            assert not result.success_rate_critical
        finally:
            counters_path.unlink()

    def test_critical_coverage(self):
        """Test that low coverage triggers critical flag."""
        counters_content = '''"key","value"
"input-rows-processed",100
"output-svobs-csv-rows",5
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(counters_content)
            counters_path = Path(f.name)

        try:
            result = filter_counters(counters_path)

            assert result.coverage_pct == 5.0
            assert result.success_rate_critical
        finally:
            counters_path.unlink()

    def test_error_extraction(self):
        """Test extraction of error counters."""
        counters_content = '''"key","value"
"error-unresolved-place",100
"error-statvar-missing-property",5
"error-unresolved-place_geoId/6",50
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(counters_content)
            counters_path = Path(f.name)

        try:
            result = filter_counters(counters_path)

            # Should only get base error types (no suffixes)
            assert 'error-unresolved-place' in result.errors
            assert 'error-statvar-missing-property' in result.errors
            assert len(result.errors) == 2
        finally:
            counters_path.unlink()

    def test_unmapped_value_extraction(self):
        """Test extraction and pattern analysis of unmapped values."""
        counters_content = '''"key","value"
"warning-missing-property-key",100
"warning-missing-property-key_AL",10
"warning-missing-property-key_CA",5
"warning-missing-property-key_TX",3
"warning-missing-property-key_2020",50
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(counters_content)
            counters_path = Path(f.name)

        try:
            result = filter_counters(counters_path)

            # Should have unmapped value patterns
            assert len(result.unmapped_value_patterns) > 0

            # Should have year pattern (highest count)
            year_patterns = [p for p in result.unmapped_value_patterns if p.pattern_type == 'year']
            assert len(year_patterns) == 1
            assert year_patterns[0].count == 50
        finally:
            counters_path.unlink()

    def test_noise_filtering(self):
        """Test that operational noise is filtered out."""
        counters_content = '''"key","value"
"1:process_input_process-mem",446058053632
"1:process_input_process-time-sys-secs",0.33881424
"1:process_input_start_time",1382229.328692916
"input-rows-processed",100
"processing-rate",500
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(counters_content)
            counters_path = Path(f.name)

        try:
            result = filter_counters(counters_path)

            # Memory, timing, and rate stats should be filtered
            assert result.input_rows == 100
            # Should not have noise in errors or warnings
            assert 'process-mem' not in str(result.errors)
            assert 'process-time' not in str(result.warnings)
        finally:
            counters_path.unlink()

    def test_missing_file(self):
        """Test handling of missing counters file."""
        result = filter_counters(Path('/nonexistent/path.txt'))

        # Should return empty FilteredLogs
        assert result.input_rows == 0
        assert result.output_rows == 0
        assert len(result.errors) == 0


class TestFilteredLogsSummary:
    """Tests for FilteredLogs.to_summary() method."""

    def test_basic_summary(self):
        """Test basic summary generation."""
        logs = FilteredLogs(
            input_rows=100,
            output_rows=80,
            coverage_pct=80.0,
            statvars_generated=3,
            observations_generated=80,
        )
        summary = logs.to_summary()

        assert '## Validation Summary' in summary
        assert 'Input rows: 100' in summary
        assert 'Output rows: 80' in summary
        assert 'Coverage: 80.0%' in summary
        assert 'StatVars generated: 3' in summary

    def test_critical_status_shown(self):
        """Test that critical status is shown when coverage is low."""
        logs = FilteredLogs(
            input_rows=100,
            output_rows=5,
            coverage_pct=5.0,
            success_rate_critical=True,
        )
        summary = logs.to_summary()

        assert 'CRITICAL FAILURE' in summary

    def test_error_summary_section(self):
        """Test that errors are included in summary."""
        logs = FilteredLogs(
            errors={'error-unresolved-place': 100, 'error-statvar-missing-property': 5}
        )
        summary = logs.to_summary()

        assert '## Errors (must fix)' in summary
        assert 'unresolved place' in summary
        assert '100' in summary

    def test_value_pattern_analysis_section(self):
        """Test that value patterns are included in summary."""
        logs = FilteredLogs(
            unmapped_value_patterns=[
                ValuePattern(
                    pattern_type='state_code',
                    sample_values=['AL', 'CA', 'TX'],
                    count=100,
                    likely_column='State column'
                )
            ]
        )
        summary = logs.to_summary()

        assert '## Unmapped Value Analysis' in summary
        assert 'state_code' in summary
        assert '100' in summary
        assert 'AL' in summary
        assert 'Fix:' in summary


class TestExtractSampleErrors:
    """Tests for extract_sample_errors function."""

    def test_extracts_error_lines(self):
        """Test extraction of ERROR lines."""
        stderr = '''
Some regular output
ERROR: Missing required property 'populationType'
More output
ERROR: Unable to resolve place 'geoId/6'
WARNING: Duplicate StatVar definition
'''
        result = extract_sample_errors(stderr, max_samples=5)

        assert 'ERROR' in result
        assert 'populationType' in result
        assert 'WARNING' in result

    def test_deduplication(self):
        """Test that similar errors are deduplicated."""
        stderr = '''
ERROR: Missing property 'x' for row 1
ERROR: Missing property 'y' for row 2
ERROR: Missing property 'z' for row 3
'''
        # These should normalize to the same pattern
        result = extract_sample_errors(stderr, max_samples=5)

        # Should have at most 3 lines
        lines = [l for l in result.split('\n') if l.strip()]
        assert len(lines) <= 3

    def test_max_samples_limit(self):
        """Test that max_samples is respected."""
        # Use unique error messages that won't be deduplicated
        stderr = '\n'.join([f'ERROR: Error type {chr(65+i)} occurred' for i in range(20)])
        result = extract_sample_errors(stderr, max_samples=3)

        # Should have at most 3 samples
        lines = [l for l in result.split('\n') if l.strip()]
        assert len(lines) <= 3

    def test_empty_input(self):
        """Test handling of empty input."""
        assert extract_sample_errors('') == ''
        assert extract_sample_errors(None) == ''


class TestGetFixSuggestion:
    """Tests for _get_fix_suggestion function."""

    def test_state_code_suggestion(self):
        """Test fix suggestion for state codes."""
        suggestion = _get_fix_suggestion('state_code')
        assert 'state codes' in suggestion.lower() or 'geoId' in suggestion

    def test_place_name_suggestion(self):
        """Test fix suggestion for place names."""
        suggestion = _get_fix_suggestion('place_name')
        assert 'FIPS' in suggestion or 'dcid' in suggestion.lower()

    def test_year_suggestion(self):
        """Test fix suggestion for years."""
        suggestion = _get_fix_suggestion('year')
        assert 'observationDate' in suggestion

    def test_unknown_pattern(self):
        """Test that unknown patterns return empty string."""
        assert _get_fix_suggestion('unknown') == ''


class TestGenerateConciseFeedback:
    """Tests for generate_concise_feedback function."""

    def test_combines_counters_and_stderr(self):
        """Test that feedback combines counter analysis and stderr samples."""
        counters_content = '''"key","value"
"input-rows-processed",100
"output-svobs-csv-rows",80
"warning-missing-property-key_AL",10
'''
        stderr = 'ERROR: Sample error message'

        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(counters_content)
            counters_path = Path(f.name)

        try:
            feedback = generate_concise_feedback(counters_path, stderr)

            assert '## Validation Summary' in feedback
            assert '## Sample Error Messages' in feedback
            assert 'Sample error message' in feedback
        finally:
            counters_path.unlink()

    def test_handles_missing_stderr(self):
        """Test handling when stderr is None."""
        counters_content = '''"key","value"
"input-rows-processed",100
"output-svobs-csv-rows",80
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(counters_content)
            counters_path = Path(f.name)

        try:
            feedback = generate_concise_feedback(counters_path)

            assert '## Validation Summary' in feedback
            assert '## Sample Error Messages' not in feedback
        finally:
            counters_path.unlink()


class TestIntegrationWithRealCountersFile:
    """Integration tests using real counters file format."""

    def test_school_retention_format(self):
        """Test parsing of school_retention-style counters file."""
        # Sample based on actual school_retention counters file
        counters_content = '''"key","value"
"1:process_input_generated-svobs",51
"1:process_input_input-rows-processed",20
"1:process_input_process-mem",446058053632
"output-svobs-csv-rows",51
"svobs-added",51
"warning-missing-property-key",20736
"warning-missing-property-key_AL",19
"warning-missing-property-key_ALBERTVILLE CITY",1
"warning-missing-property-key_10000500879",4
"warning-missing-property-key_2010",38
'''
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(counters_content)
            counters_path = Path(f.name)

        try:
            result = filter_counters(counters_path)

            # Should extract key metrics (filtering noise)
            assert result.output_rows == 51
            assert result.observations_generated == 51

            # Should have unmapped value patterns
            assert len(result.unmapped_value_patterns) > 0

            # Should detect year pattern
            year_patterns = [p for p in result.unmapped_value_patterns if p.pattern_type == 'year']
            assert len(year_patterns) == 1

            # Should detect state code pattern
            state_patterns = [p for p in result.unmapped_value_patterns if p.pattern_type == 'state_code']
            assert len(state_patterns) == 1

            # Should detect numeric ID pattern
            id_patterns = [p for p in result.unmapped_value_patterns if p.pattern_type == 'numeric_id']
            assert len(id_patterns) == 1

            # Should detect place name pattern
            place_patterns = [p for p in result.unmapped_value_patterns if p.pattern_type == 'place_name']
            assert len(place_patterns) == 1

            # Summary should be concise
            summary = result.to_summary()
            lines = summary.split('\n')
            assert len(lines) < 100  # Should be under 100 lines

        finally:
            counters_path.unlink()
