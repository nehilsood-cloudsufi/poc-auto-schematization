"""Unit tests for error_context module.

Tests the enhanced error context data structures for row-level error tracking.
"""

import json
import pytest

from src.infrastructure.metrics.error_context import (
    FailingRowSample,
    ErrorTypeContext,
    EnhancedErrorContext,
)


# ============================================================================
# Test FailingRowSample
# ============================================================================

class TestFailingRowSample:
    """Tests for FailingRowSample dataclass."""

    def test_basic_creation(self):
        """Should create sample with required fields."""
        sample = FailingRowSample(
            row_number=5,
            original_values={'State': 'CA', 'Year': '2020'},
        )

        assert sample.row_number == 5
        assert sample.original_values == {'State': 'CA', 'Year': '2020'}
        assert sample.transformed_values == {}
        assert sample.error_stage == ''
        assert sample.error_message == ''

    def test_full_creation(self):
        """Should create sample with all fields."""
        sample = FailingRowSample(
            row_number=10,
            original_values={'State FIPS': '6'},
            transformed_values={'observationAbout': 'geoId/6'},
            error_stage='place_resolution',
            error_message='Unable to resolve "geoId/6"'
        )

        assert sample.row_number == 10
        assert sample.original_values == {'State FIPS': '6'}
        assert sample.transformed_values == {'observationAbout': 'geoId/6'}
        assert sample.error_stage == 'place_resolution'
        assert 'Unable to resolve' in sample.error_message

    def test_to_dict(self):
        """Should convert to dictionary."""
        sample = FailingRowSample(
            row_number=5,
            original_values={'col': 'val'},
            transformed_values={'prop': 'val2'},
            error_stage='test',
            error_message='test error'
        )

        d = sample.to_dict()

        assert d['row_number'] == 5
        assert d['original_values'] == {'col': 'val'}
        assert d['transformed_values'] == {'prop': 'val2'}
        assert d['error_stage'] == 'test'
        assert d['error_message'] == 'test error'


# ============================================================================
# Test ErrorTypeContext
# ============================================================================

class TestErrorTypeContext:
    """Tests for ErrorTypeContext dataclass."""

    def test_basic_creation(self):
        """Should create context with error type."""
        ctx = ErrorTypeContext(error_type='error-unresolved-place')

        assert ctx.error_type == 'error-unresolved-place'
        assert ctx.total_count == 0
        assert ctx.sample_rows == []

    def test_add_sample_increments_count(self):
        """Should increment total_count when adding samples."""
        ctx = ErrorTypeContext(error_type='error-test')
        sample = FailingRowSample(row_number=1, original_values={'col': 'val'})

        ctx.add_sample(sample)

        assert ctx.total_count == 1

    def test_add_sample_keeps_first_n_samples(self):
        """Should keep only first MAX_SAMPLES samples."""
        ctx = ErrorTypeContext(error_type='error-test')
        ctx.MAX_SAMPLES = 3

        for i in range(10):
            sample = FailingRowSample(row_number=i, original_values={'row': str(i)})
            ctx.add_sample(sample)

        assert ctx.total_count == 10
        assert len(ctx.sample_rows) == 3
        assert ctx.sample_rows[0].row_number == 0  # First sample kept

    def test_tracks_unique_failing_values(self):
        """Should track unique failing values per column."""
        ctx = ErrorTypeContext(error_type='error-test')

        ctx.add_sample(FailingRowSample(row_number=1, original_values={'State': 'CA'}))
        ctx.add_sample(FailingRowSample(row_number=2, original_values={'State': 'TX'}))
        ctx.add_sample(FailingRowSample(row_number=3, original_values={'State': 'CA'}))

        assert 'State' in ctx.unique_failing_values
        assert 'CA' in ctx.unique_failing_values['State']
        assert 'TX' in ctx.unique_failing_values['State']
        assert len(ctx.unique_failing_values['State']) == 2

    def test_limits_unique_values(self):
        """Should limit unique values per column."""
        ctx = ErrorTypeContext(error_type='error-test')
        ctx.MAX_UNIQUE_VALUES = 5

        for i in range(20):
            ctx.add_sample(FailingRowSample(row_number=i, original_values={'num': str(i)}))

        assert len(ctx.unique_failing_values['num']) == 5

    def test_to_dict(self):
        """Should convert to dictionary."""
        ctx = ErrorTypeContext(error_type='error-test')
        ctx.add_sample(FailingRowSample(row_number=1, original_values={'col': 'val'}))

        d = ctx.to_dict()

        assert d['error_type'] == 'error-test'
        assert d['total_count'] == 1
        assert len(d['sample_rows']) == 1
        assert 'col' in d['unique_failing_values']

    def test_detect_single_value_pattern(self):
        """Should detect single-value patterns."""
        ctx = ErrorTypeContext(error_type='error-test')

        for i in range(10):
            ctx.add_sample(FailingRowSample(row_number=i, original_values={'col': 'same_value'}))

        patterns = ctx.detect_patterns()

        assert len(patterns) > 0
        assert patterns[0]['type'] == 'single_value'
        assert patterns[0]['value'] == 'same_value'
        assert patterns[0]['confidence'] == 1.0

    def test_detect_few_values_pattern(self):
        """Should detect few-values patterns."""
        ctx = ErrorTypeContext(error_type='error-test')

        # 3 unique values for 15 errors
        for i in range(15):
            value = str(i % 3)  # 0, 1, 2, 0, 1, 2, ...
            ctx.add_sample(FailingRowSample(row_number=i, original_values={'col': value}))

        patterns = ctx.detect_patterns()

        # Should detect few_values pattern
        few_values_patterns = [p for p in patterns if p['type'] == 'few_values']
        assert len(few_values_patterns) > 0


# ============================================================================
# Test EnhancedErrorContext
# ============================================================================

class TestEnhancedErrorContext:
    """Tests for EnhancedErrorContext class."""

    def test_add_error_creates_context(self):
        """Should create ErrorTypeContext when adding new error type."""
        context = EnhancedErrorContext()

        sample = FailingRowSample(row_number=1, original_values={'col': 'val'})
        context.add_error('error-test', sample)

        assert 'error-test' in context.errors
        assert context.errors['error-test'].total_count == 1

    def test_add_error_reuses_context(self):
        """Should reuse existing context for same error type."""
        context = EnhancedErrorContext()

        context.add_error('error-test', FailingRowSample(row_number=1, original_values={}))
        context.add_error('error-test', FailingRowSample(row_number=2, original_values={}))

        assert len(context.errors) == 1
        assert context.errors['error-test'].total_count == 2

    def test_get_total_errors(self):
        """Should sum all errors across types."""
        context = EnhancedErrorContext()

        for i in range(5):
            context.add_error('error-a', FailingRowSample(row_number=i, original_values={}))
        for i in range(3):
            context.add_error('error-b', FailingRowSample(row_number=i, original_values={}))

        assert context.get_total_errors() == 8

    def test_get_primary_error(self):
        """Should return error type with highest count."""
        context = EnhancedErrorContext()

        for i in range(10):
            context.add_error('error-main', FailingRowSample(row_number=i, original_values={}))
        for i in range(3):
            context.add_error('error-minor', FailingRowSample(row_number=i, original_values={}))

        assert context.get_primary_error() == 'error-main'

    def test_get_primary_error_empty(self):
        """Should return None when no errors."""
        context = EnhancedErrorContext()

        assert context.get_primary_error() is None

    def test_to_dict(self):
        """Should convert to dictionary."""
        context = EnhancedErrorContext(
            pipeline_stage='validation',
            dataset_name='test_dataset'
        )
        context.add_error('error-test', FailingRowSample(row_number=1, original_values={'col': 'val'}))

        d = context.to_dict()

        assert d['pipeline_stage'] == 'validation'
        assert d['dataset_name'] == 'test_dataset'
        assert d['total_errors'] == 1
        assert d['primary_error'] == 'error-test'
        assert 'error-test' in d['errors']

    def test_to_json_basic(self):
        """Should serialize to JSON."""
        context = EnhancedErrorContext()
        context.add_error('error-test', FailingRowSample(row_number=1, original_values={'col': 'val'}))

        json_str = context.to_json()
        data = json.loads(json_str)

        assert 'errors' in data
        assert 'error-test' in data['errors']

    def test_to_json_respects_size_limit(self):
        """Should truncate to respect size limit."""
        context = EnhancedErrorContext()

        # Add many samples with long error messages
        for i in range(100):
            sample = FailingRowSample(
                row_number=i,
                original_values={'col': 'val' * 100},
                error_message='Long error message ' * 50
            )
            context.add_error('error-test', sample)

        json_str = context.to_json(max_size_kb=10)

        # Should be under 10KB
        assert len(json_str.encode('utf-8')) <= 10 * 1024


# ============================================================================
# Test Pattern Detection
# ============================================================================

class TestPatternDetection:
    """Tests for pattern detection in EnhancedErrorContext."""

    def test_detect_all_patterns(self):
        """Should detect patterns across all error types."""
        context = EnhancedErrorContext()

        # Add errors with pattern
        for i in range(10):
            context.add_error('error-a', FailingRowSample(
                row_number=i, original_values={'col': 'same_value'}
            ))

        patterns = context.detect_all_patterns()

        assert len(patterns) > 0
        assert all('error_type' in p for p in patterns)

    def test_patterns_sorted_by_confidence(self):
        """Should sort patterns by confidence descending."""
        context = EnhancedErrorContext()

        # Single value pattern (confidence 1.0)
        for i in range(10):
            context.add_error('error-single', FailingRowSample(
                row_number=i, original_values={'col': 'same'}
            ))

        # Few values pattern (confidence 0.8)
        for i in range(15):
            context.add_error('error-few', FailingRowSample(
                row_number=i, original_values={'col': str(i % 3)}
            ))

        patterns = context.detect_all_patterns()

        if len(patterns) >= 2:
            # First pattern should have higher or equal confidence
            assert patterns[0]['confidence'] >= patterns[1]['confidence']


# ============================================================================
# Test Feedback Formatting
# ============================================================================

class TestFeedbackFormatting:
    """Tests for feedback formatting methods."""

    def test_format_transformation_feedback_empty(self):
        """Should return empty string with no errors."""
        context = EnhancedErrorContext()

        feedback = context.format_transformation_feedback()

        assert feedback == ''

    def test_format_transformation_feedback_includes_before_after(self):
        """Should include before/after values."""
        context = EnhancedErrorContext()
        context.add_error('error-test', FailingRowSample(
            row_number=1,
            original_values={'State': 'CA'},
            transformed_values={'observationAbout': 'geoId/CA'},
            error_stage='place_resolution',
            error_message='Failed to resolve'
        ))

        feedback = context.format_transformation_feedback()

        assert 'BEFORE' in feedback
        assert 'AFTER' in feedback
        assert 'State' in feedback
        assert 'observationAbout' in feedback
        assert 'place_resolution' in feedback

    def test_format_pattern_feedback_empty(self):
        """Should return message when no patterns."""
        context = EnhancedErrorContext()

        feedback = context.format_pattern_feedback()

        assert 'No systematic patterns' in feedback

    def test_format_pattern_feedback_includes_action(self):
        """Should include action recommendations for patterns."""
        context = EnhancedErrorContext()

        for i in range(10):
            context.add_error('error-test', FailingRowSample(
                row_number=i, original_values={'col': 'same'}
            ))

        feedback = context.format_pattern_feedback()

        assert 'Pattern' in feedback
        assert 'Action' in feedback


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_original_values(self):
        """Should handle empty original values."""
        context = EnhancedErrorContext()
        context.add_error('error-test', FailingRowSample(row_number=1, original_values={}))

        assert context.get_total_errors() == 1

    def test_unicode_values(self):
        """Should handle unicode values."""
        context = EnhancedErrorContext()
        context.add_error('error-test', FailingRowSample(
            row_number=1,
            original_values={'Stadt': 'München'},
            error_message='Fehler bei der Ortsauflösung'
        ))

        json_str = context.to_json()
        data = json.loads(json_str)

        # Unicode may be escaped in JSON, check via parsed data
        assert data['errors']['error-test']['sample_rows'][0]['original_values']['Stadt'] == 'München'

    def test_special_characters_in_values(self):
        """Should handle special characters."""
        context = EnhancedErrorContext()
        context.add_error('error-test', FailingRowSample(
            row_number=1,
            original_values={'col': 'value with "quotes" and \n newlines'}
        ))

        json_str = context.to_json()
        # Should be valid JSON
        data = json.loads(json_str)
        assert data is not None
