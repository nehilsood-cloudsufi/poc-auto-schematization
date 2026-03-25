"""Unit tests for feedback_tracker module.

Tests the FeedbackEffectivenessTracker for tracking retry effectiveness.
"""

import pytest

from src.pipeline.validation.feedback_tracker import (
    FeedbackEffectivenessTracker,
    AttemptRecord,
)


# ============================================================================
# Test AttemptRecord
# ============================================================================

class TestAttemptRecord:
    """Tests for AttemptRecord dataclass."""

    def test_to_dict(self):
        """Should convert record to dictionary."""
        record = AttemptRecord(
            attempt_number=0,
            errors={'error-unresolved-place': 100},
            feedback_given='Fix place mapping',
            pvmap_hash='abcd1234',
            quality_score=25.0,
            validation_passed=True
        )

        d = record.to_dict()

        assert d['attempt_number'] == 0
        assert d['errors'] == {'error-unresolved-place': 100}
        assert d['feedback_given_length'] == len('Fix place mapping')
        assert d['pvmap_hash'] == 'abcd1234'
        assert d['quality_score'] == 25.0
        assert d['validation_passed'] is True


# ============================================================================
# Test FeedbackEffectivenessTracker
# ============================================================================

class TestFeedbackEffectivenessTracker:
    """Tests for FeedbackEffectivenessTracker class."""

    def test_record_attempt(self):
        """Should record an attempt."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(
            attempt_number=0,
            errors={'error-unresolved-place': 100},
            feedback_given='',
            pvmap_csv='key,prop,val\n',
            quality_score=0.0,
            validation_passed=False
        )

        assert len(tracker.attempts) == 1
        assert tracker.attempts[0].attempt_number == 0
        assert tracker.attempts[0].errors == {'error-unresolved-place': 100}

    def test_pvmap_hash_generated(self):
        """Should generate hash of PVMAP content."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(
            attempt_number=0,
            errors={},
            feedback_given='',
            pvmap_csv='key,prop,val\nYear,observationDate,{Data}',
            quality_score=0.0
        )

        assert len(tracker.attempts[0].pvmap_hash) == 8  # MD5 first 8 chars

    def test_different_pvmap_different_hash(self):
        """Different PVMAP content should have different hash."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(
            attempt_number=0,
            errors={},
            feedback_given='',
            pvmap_csv='key,prop,val\nYear,observationDate,{Data}',
            quality_score=0.0
        )
        tracker.record_attempt(
            attempt_number=1,
            errors={},
            feedback_given='Fix',
            pvmap_csv='key,prop,val\nState,observationAbout,{Data}',
            quality_score=0.0
        )

        assert tracker.attempts[0].pvmap_hash != tracker.attempts[1].pvmap_hash


# ============================================================================
# Test Effectiveness Analysis
# ============================================================================

class TestEffectivenessAnalysis:
    """Tests for analyze_effectiveness method."""

    def test_insufficient_data_with_single_attempt(self):
        """Should return insufficient_data with < 2 attempts."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')
        tracker.record_attempt(0, {}, '', 'pvmap', 0.0)

        analysis = tracker.analyze_effectiveness()

        assert analysis['status'] == 'insufficient_data'

    def test_tracks_improved_errors(self):
        """Should detect when errors improve."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-unresolved-place': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-unresolved-place': 50}, 'Fix places', 'pv2', 25.0)

        analysis = tracker.analyze_effectiveness()

        assert 'error-unresolved-place' in analysis['error_changes']['improved']
        assert analysis['error_changes']['improved']['error-unresolved-place']['from'] == 100
        assert analysis['error_changes']['improved']['error-unresolved-place']['to'] == 50

    def test_tracks_fixed_errors(self):
        """Should detect when errors are completely fixed."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-unresolved-place': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {}, 'Fix places', 'pv2', 80.0)

        analysis = tracker.analyze_effectiveness()

        assert 'error-unresolved-place' in analysis['error_changes']['fixed']

    def test_tracks_worsened_errors(self):
        """Should detect when errors worsen."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-unresolved-place': 50}, '', 'pv1', 50.0)
        tracker.record_attempt(1, {'error-unresolved-place': 100}, 'Bad fix', 'pv2', 25.0)

        analysis = tracker.analyze_effectiveness()

        assert 'error-unresolved-place' in analysis['error_changes']['worsened']
        assert analysis['error_changes']['worsened']['error-unresolved-place']['increase'] == 50

    def test_tracks_new_errors(self):
        """Should detect when new errors are introduced."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-unresolved-place': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-unresolved-place': 50, 'error-mismatched-svobs': 10}, 'Fix', 'pv2', 20.0)

        analysis = tracker.analyze_effectiveness()

        assert 'error-mismatched-svobs' in analysis['error_changes']['new_errors']

    def test_net_change_calculation(self):
        """Should calculate net change in error count."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-a': 100, 'error-b': 50}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-a': 80}, 'Fix', 'pv2', 30.0)

        analysis = tracker.analyze_effectiveness()

        # 150 total -> 80 total = -70
        assert analysis['error_changes']['net_change'] == -70


# ============================================================================
# Test Feedback Addressed Check
# ============================================================================

class TestFeedbackAddressed:
    """Tests for _check_feedback_addressed method."""

    def test_pvmap_changed_detected(self):
        """Should detect when PVMAP changed."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-a': 100}, '', 'pvmap1', 0.0)
        tracker.record_attempt(1, {'error-a': 50}, 'Fix', 'pvmap2_different', 25.0)

        analysis = tracker.analyze_effectiveness()

        assert analysis['feedback_addressed']['pvmap_changed'] is True

    def test_pvmap_unchanged_detected(self):
        """Should detect when PVMAP didn't change."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        same_pvmap = 'key,prop,val\n'
        tracker.record_attempt(0, {'error-a': 100}, '', same_pvmap, 0.0)
        tracker.record_attempt(1, {'error-a': 100}, 'Fix', same_pvmap, 0.0)

        analysis = tracker.analyze_effectiveness()

        assert analysis['feedback_addressed']['pvmap_changed'] is False

    def test_primary_error_improved_detected(self):
        """Should detect when primary error improved."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-unresolved-place': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-unresolved-place': 50}, 'Fix', 'pv2', 25.0)

        analysis = tracker.analyze_effectiveness()

        assert analysis['feedback_addressed']['primary_error'] == 'error-unresolved-place'
        assert analysis['feedback_addressed']['primary_improved'] is True
        assert analysis['feedback_addressed']['feedback_effective'] is True


# ============================================================================
# Test Alternative Strategy
# ============================================================================

class TestAlternativeStrategy:
    """Tests for get_alternative_strategy method."""

    def test_no_strategy_with_single_attempt(self):
        """Should return None with single attempt."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')
        tracker.record_attempt(0, {}, '', 'pvmap', 0.0)

        strategy = tracker.get_alternative_strategy()

        assert strategy is None

    def test_strategy_when_not_improving(self):
        """Should suggest alternative when errors not decreasing."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-a': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-a': 100}, 'Fix', 'pv2', 0.0)  # Same errors

        strategy = tracker.get_alternative_strategy()

        assert strategy is not None
        assert 'Alternative Strategy' in strategy
        assert 'minimal' in strategy.lower() or 'fix one error' in strategy.lower()

    def test_no_strategy_when_improving(self):
        """Should not suggest alternative when improving."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-a': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-a': 50}, 'Fix', 'pv2', 25.0)  # Improving

        strategy = tracker.get_alternative_strategy()

        assert strategy is None

    def test_strategy_when_errors_increase(self):
        """Should suggest alternative when errors increase."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-a': 50}, '', 'pv1', 30.0)
        tracker.record_attempt(1, {'error-a': 100}, 'Fix', 'pv2', 0.0)  # Got worse

        strategy = tracker.get_alternative_strategy()

        assert strategy is not None


# ============================================================================
# Test Recommendations
# ============================================================================

class TestRecommendations:
    """Tests for _generate_recommendations method."""

    def test_recommendation_when_pvmap_unchanged(self):
        """Should recommend incorporating feedback when PVMAP unchanged."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        same_pvmap = 'key,prop,val\n'
        tracker.record_attempt(0, {'error-a': 100}, '', same_pvmap, 0.0)
        tracker.record_attempt(1, {'error-a': 100}, 'Fix', same_pvmap, 0.0)

        analysis = tracker.analyze_effectiveness()

        recs = analysis['recommendations']
        assert any('did not change' in r.lower() for r in recs)

    def test_recommendation_when_primary_not_addressed(self):
        """Should recommend focusing on primary error."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-unresolved-place': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-unresolved-place': 100, 'error-new': 10}, 'Fix', 'pv2', 0.0)

        analysis = tracker.analyze_effectiveness()

        recs = analysis['recommendations']
        assert any('primary error' in r.lower() or 'error-unresolved-place' in r for r in recs)

    def test_positive_recommendation_when_fixed(self):
        """Should give positive feedback when errors fixed."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-a': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {}, 'Fix', 'pv2', 80.0)

        analysis = tracker.analyze_effectiveness()

        recs = analysis['recommendations']
        assert any('progress' in r.lower() or 'fixed' in r.lower() for r in recs)


# ============================================================================
# Test Report Formatting
# ============================================================================

class TestReportFormatting:
    """Tests for format_effectiveness_report method."""

    def test_insufficient_data_message(self):
        """Should return message with insufficient data."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')
        tracker.record_attempt(0, {}, '', 'pvmap', 0.0)

        report = tracker.format_effectiveness_report()

        assert 'Insufficient' in report

    def test_report_includes_attempt_number(self):
        """Report should include attempt number."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-a': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-a': 50}, 'Fix', 'pv2', 25.0)

        report = tracker.format_effectiveness_report()

        assert 'Attempt 2' in report or 'attempt 2' in report.lower()

    def test_report_includes_error_changes(self):
        """Report should include error changes."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {'error-unresolved-place': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-unresolved-place': 50}, 'Fix', 'pv2', 25.0)

        report = tracker.format_effectiveness_report()

        assert '100' in report
        assert '50' in report

    def test_report_includes_quality_change(self):
        """Report should include quality score change."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')

        tracker.record_attempt(0, {}, '', 'pv1', 20.0)
        tracker.record_attempt(1, {}, '', 'pv2', 50.0)

        report = tracker.format_effectiveness_report()

        assert '+30' in report or '30' in report


# ============================================================================
# Test Serialization
# ============================================================================

class TestSerialization:
    """Tests for to_dict method."""

    def test_to_dict_structure(self):
        """Should return correct dictionary structure."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test_dataset')

        tracker.record_attempt(0, {'error-a': 100}, '', 'pv1', 0.0)
        tracker.record_attempt(1, {'error-a': 50}, 'Fix', 'pv2', 25.0)

        d = tracker.to_dict()

        assert d['dataset_name'] == 'test_dataset'
        assert d['attempt_count'] == 2
        assert len(d['attempts']) == 2
        assert d['analysis'] is not None

    def test_to_dict_no_analysis_with_single_attempt(self):
        """Should not include analysis with single attempt."""
        tracker = FeedbackEffectivenessTracker(dataset_name='test')
        tracker.record_attempt(0, {}, '', 'pvmap', 0.0)

        d = tracker.to_dict()

        assert d['analysis'] is None
