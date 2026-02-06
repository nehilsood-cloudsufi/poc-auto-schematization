"""Feedback effectiveness tracker for PVMAP validation retry loop.

This module tracks feedback effectiveness across retry attempts:
- Records errors, feedback given, and quality scores per attempt
- Analyzes whether feedback is being addressed
- Detects when retries are not helping (stagnation)
- Suggests alternative strategies when stuck

Usage:
    from src.pipeline.validation.feedback_tracker import FeedbackEffectivenessTracker

    tracker = FeedbackEffectivenessTracker(dataset_name="my_dataset")

    # Record each attempt
    tracker.record_attempt(
        attempt_number=0,
        errors={'error-unresolved-place': 100},
        feedback_given='',
        pvmap_csv='...',
        quality_score=0.0
    )

    # Analyze effectiveness after second+ attempt
    analysis = tracker.analyze_effectiveness()

    # Get alternative strategy suggestion if stuck
    strategy = tracker.get_alternative_strategy()
"""

import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class AttemptRecord:
    """Record of a single retry attempt.

    Attributes:
        attempt_number: 0-indexed attempt number
        errors: Dict mapping error_type -> count
        feedback_given: Feedback text that was provided before this attempt
        pvmap_hash: Short hash of PVMAP content for detecting changes
        quality_score: Quality score (0-100) from evaluation
        validation_passed: Whether validation passed
    """
    attempt_number: int
    errors: Dict[str, int]
    feedback_given: str
    pvmap_hash: str
    quality_score: float
    validation_passed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'attempt_number': self.attempt_number,
            'errors': self.errors,
            'feedback_given_length': len(self.feedback_given),
            'pvmap_hash': self.pvmap_hash,
            'quality_score': self.quality_score,
            'validation_passed': self.validation_passed,
        }


@dataclass
class FeedbackEffectivenessTracker:
    """Tracks feedback effectiveness across retry attempts.

    Analyzes whether provided feedback is helping improve PVMAP quality
    and suggests alternative strategies when improvements stagnate.

    Attributes:
        dataset_name: Name of dataset being processed
        attempts: List of AttemptRecord instances
    """
    dataset_name: str
    attempts: List[AttemptRecord] = field(default_factory=list)

    def record_attempt(
        self,
        attempt_number: int,
        errors: Dict[str, int],
        feedback_given: str,
        pvmap_csv: str,
        quality_score: float,
        validation_passed: bool = False
    ) -> None:
        """Record an attempt with its results.

        Args:
            attempt_number: 0-indexed attempt number
            errors: Dict mapping error_type -> count
            feedback_given: Feedback text provided before this attempt
            pvmap_csv: PVMAP CSV content (for hash)
            quality_score: Quality score from evaluation
            validation_passed: Whether validation passed
        """
        # Create short hash of PVMAP for change detection
        pvmap_hash = hashlib.md5(pvmap_csv.encode()).hexdigest()[:8]

        record = AttemptRecord(
            attempt_number=attempt_number,
            errors=errors,
            feedback_given=feedback_given,
            pvmap_hash=pvmap_hash,
            quality_score=quality_score,
            validation_passed=validation_passed
        )
        self.attempts.append(record)

    def analyze_effectiveness(self) -> Dict[str, Any]:
        """Analyze whether feedback is helping.

        Compares the last two attempts to determine:
        - Which errors improved, worsened, or are new
        - Whether previous feedback was addressed
        - Net change in error count
        - Recommendations for next attempt

        Returns:
            Dictionary with analysis results
        """
        if len(self.attempts) < 2:
            return {'status': 'insufficient_data'}

        prev = self.attempts[-2]
        curr = self.attempts[-1]

        return {
            'error_changes': self._track_error_changes(prev, curr),
            'feedback_addressed': self._check_feedback_addressed(prev, curr),
            'quality_change': curr.quality_score - prev.quality_score,
            'pvmap_changed': prev.pvmap_hash != curr.pvmap_hash,
            'recommendations': self._generate_recommendations(prev, curr)
        }

    def _track_error_changes(
        self,
        prev: AttemptRecord,
        curr: AttemptRecord
    ) -> Dict[str, Any]:
        """Track which errors improved, worsened, or are new.

        Args:
            prev: Previous attempt record
            curr: Current attempt record

        Returns:
            Dictionary with categorized error changes
        """
        prev_errors = prev.errors or {}
        curr_errors = curr.errors or {}
        all_errors = set(prev_errors.keys()) | set(curr_errors.keys())

        improved = {}
        worsened = {}
        fixed = {}
        new_errors = {}

        for error in all_errors:
            prev_count = prev_errors.get(error, 0)
            curr_count = curr_errors.get(error, 0)

            if curr_count < prev_count and prev_count > 0:
                if curr_count == 0:
                    # Completely fixed
                    fixed[error] = prev_count
                else:
                    # Improved but not fixed
                    improved[error] = {
                        'from': prev_count,
                        'to': curr_count,
                        'reduction': prev_count - curr_count
                    }
            elif curr_count > prev_count:
                if prev_count == 0:
                    # New error introduced
                    new_errors[error] = curr_count
                else:
                    # Worsened
                    worsened[error] = {
                        'from': prev_count,
                        'to': curr_count,
                        'increase': curr_count - prev_count
                    }

        # Calculate net change
        prev_total = sum(prev_errors.values())
        curr_total = sum(curr_errors.values())
        net_change = curr_total - prev_total

        return {
            'improved': improved,
            'worsened': worsened,
            'fixed': fixed,
            'new_errors': new_errors,
            'net_change': net_change,
            'previous_total': prev_total,
            'current_total': curr_total,
        }

    def _check_feedback_addressed(
        self,
        prev: AttemptRecord,
        curr: AttemptRecord
    ) -> Dict[str, Any]:
        """Check if previous feedback was addressed.

        Args:
            prev: Previous attempt record
            curr: Current attempt record

        Returns:
            Dictionary indicating feedback effectiveness
        """
        # Did the PVMAP change at all?
        pvmap_changed = prev.pvmap_hash != curr.pvmap_hash

        # Check if the primary error from previous attempt was addressed
        prev_errors = prev.errors or {}
        curr_errors = curr.errors or {}

        if prev_errors:
            # Find the primary error from previous attempt
            primary_error = max(prev_errors.items(), key=lambda x: x[1])[0]
            prev_count = prev_errors.get(primary_error, 0)
            curr_count = curr_errors.get(primary_error, 0)

            primary_improved = curr_count < prev_count
            primary_fixed = curr_count == 0

            return {
                'pvmap_changed': pvmap_changed,
                'primary_error': primary_error,
                'primary_improved': primary_improved,
                'primary_fixed': primary_fixed,
                'feedback_effective': primary_improved
            }

        return {
            'pvmap_changed': pvmap_changed,
            'primary_error': None,
            'primary_improved': False,
            'primary_fixed': False,
            'feedback_effective': False
        }

    def _generate_recommendations(
        self,
        prev: AttemptRecord,
        curr: AttemptRecord
    ) -> List[str]:
        """Generate recommendations based on attempt analysis.

        Args:
            prev: Previous attempt record
            curr: Current attempt record

        Returns:
            List of recommendation strings
        """
        recommendations = []
        error_changes = self._track_error_changes(prev, curr)
        feedback_check = self._check_feedback_addressed(prev, curr)

        # Check if PVMAP didn't change
        if not feedback_check['pvmap_changed']:
            recommendations.append(
                "PVMAP did not change between attempts - ensure feedback is being "
                "incorporated into the generation prompt"
            )

        # Check if primary error wasn't addressed
        if feedback_check.get('primary_error') and not feedback_check.get('primary_improved'):
            recommendations.append(
                f"Primary error '{feedback_check['primary_error']}' was not addressed - "
                f"focus feedback more specifically on this issue"
            )

        # Check if new errors were introduced
        new_errors = error_changes.get('new_errors', {})
        if new_errors:
            error_names = list(new_errors.keys())[:3]
            recommendations.append(
                f"New errors introduced: {error_names}. Check if fixes caused regressions."
            )

        # Check for worsening
        worsened = error_changes.get('worsened', {})
        if worsened:
            recommendations.append(
                "Some errors got worse - the fix attempt may have been incorrect"
            )

        # Positive feedback
        fixed = error_changes.get('fixed', {})
        if fixed:
            recommendations.append(
                f"Good progress! Fixed errors: {list(fixed.keys())}"
            )

        improved = error_changes.get('improved', {})
        if improved:
            recommendations.append(
                f"Improving: {list(improved.keys())} - continue this approach"
            )

        return recommendations

    def get_alternative_strategy(self) -> Optional[str]:
        """Suggest alternative strategy when stuck.

        Called when normal feedback loop isn't making progress.

        Returns:
            Alternative strategy string, or None if not applicable
        """
        if len(self.attempts) < 2:
            return None

        analysis = self.analyze_effectiveness()
        error_changes = analysis.get('error_changes', {})
        net_change = error_changes.get('net_change', -1)

        # Check if we're not making progress (net errors same or worse)
        if net_change >= 0:
            return (
                "## Alternative Strategy: Feedback Not Helping\n\n"
                "The retry loop is not reducing errors. Consider:\n\n"
                "1. **Start minimal**: Generate a PVMAP with ONLY the three required "
                "mappings (observationAbout, observationDate, value) first\n\n"
                "2. **Fix ONE error type at a time**: Focus all feedback on the "
                "single highest-count error\n\n"
                "3. **Show exact format**: Include a corrected PVMAP snippet showing "
                "the EXACT expected format for failing rows\n\n"
                "4. **Check column names**: Verify PVMAP keys match CSV column headers "
                "EXACTLY (case-sensitive)\n\n"
                "5. **Simplify DCID references**: Use explicit dcid: prefixes rather "
                "than relying on inference"
            )

        # Check if quality is stagnating
        quality_change = analysis.get('quality_change', 0)
        if len(self.attempts) >= 3 and abs(quality_change) < 5.0:
            return (
                "## Alternative Strategy: Quality Stagnating\n\n"
                "Quality improvements have stalled. Consider:\n\n"
                "1. **Review ground truth**: Check the expected output format\n\n"
                "2. **Different approach**: Try pre-formatted passthrough if data "
                "looks pre-processed\n\n"
                "3. **Manual inspection**: Look at the specific failing rows to "
                "understand the pattern"
            )

        return None

    def format_effectiveness_report(self) -> str:
        """Format effectiveness analysis as human-readable report.

        Returns:
            Formatted string summarizing feedback effectiveness
        """
        if len(self.attempts) < 2:
            return "Insufficient data for effectiveness analysis."

        analysis = self.analyze_effectiveness()
        error_changes = analysis.get('error_changes', {})
        feedback_check = analysis.get('feedback_addressed', {})

        lines = [
            f"## Feedback Effectiveness (Attempt {len(self.attempts)})",
            ""
        ]

        # Error changes
        if error_changes.get('fixed'):
            lines.append(f"- Errors fixed: {list(error_changes['fixed'].keys())}")

        if error_changes.get('improved'):
            for error, change in error_changes['improved'].items():
                lines.append(
                    f"- {error}: {change['from']} -> {change['to']} (-{change['reduction']})"
                )

        if error_changes.get('worsened'):
            for error, change in error_changes['worsened'].items():
                lines.append(
                    f"- {error}: {change['from']} -> {change['to']} (+{change['increase']}) [WORSE]"
                )

        if error_changes.get('new_errors'):
            lines.append(f"- New errors: {list(error_changes['new_errors'].keys())}")

        lines.append(f"- Net change: {error_changes.get('net_change', 0):+d} errors")
        lines.append("")

        # Feedback effectiveness
        if feedback_check.get('feedback_effective'):
            lines.append(
                f"Previous feedback WAS addressed - {feedback_check.get('primary_error', 'errors')} improving."
            )
        elif feedback_check.get('pvmap_changed'):
            lines.append(
                "PVMAP changed but primary error not addressed - feedback may need refinement."
            )
        else:
            lines.append(
                "PVMAP did not change - feedback not being incorporated."
            )

        # Quality change
        quality_change = analysis.get('quality_change', 0)
        lines.append(f"- Quality change: {quality_change:+.1f}%")

        return '\n'.join(lines)

    def to_dict(self) -> Dict[str, Any]:
        """Convert tracker to dictionary for serialization."""
        return {
            'dataset_name': self.dataset_name,
            'attempt_count': len(self.attempts),
            'attempts': [a.to_dict() for a in self.attempts],
            'analysis': self.analyze_effectiveness() if len(self.attempts) >= 2 else None
        }


# ============================================================================
# Module exports
# ============================================================================

__all__ = [
    'AttemptRecord',
    'FeedbackEffectivenessTracker',
]
