"""
Tests for logging_tools module.

Tests log sampling and truncation utilities.
"""

import pytest

from src.tools.logging_tools import (
    extract_log_samples,
    truncate_log
)


def test_extract_log_samples_short_log():
    """Test log extraction with short log (returns all)."""
    log = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"

    result = extract_log_samples(log, tail_lines=50)

    assert result['success'] is True
    assert result['sampled_text'] == log
    assert result['tail_count'] == 5
    assert result['sample_count'] == 0
    assert result['error'] is None


def test_extract_log_samples_long_log():
    """Test log extraction with long log (samples tail and random)."""
    # Create a log with 200 lines
    lines = [f"Log line {i}" for i in range(200)]
    log = '\n'.join(lines)

    result = extract_log_samples(log, tail_lines=50, sample_count=5, sample_size=3)

    assert result['success'] is True
    assert result['tail_count'] == 50
    assert result['sample_count'] > 0

    # Should contain last 50 lines
    assert "LAST 50 LINES OF LOG" in result['sampled_text']
    assert "Log line 199" in result['sampled_text']  # Last line

    # Should contain random samples
    assert "RANDOM SAMPLES" in result['sampled_text']
    assert "Sample 1" in result['sampled_text']


def test_extract_log_samples_with_empty_lines():
    """Test log extraction filters empty lines."""
    log = "Line 1\n\n\nLine 2\n\n\nLine 3\n\n"

    result = extract_log_samples(log, tail_lines=10)

    assert result['success'] is True
    # Empty lines should be filtered
    assert "Line 1" in result['sampled_text']
    assert "Line 2" in result['sampled_text']
    assert "Line 3" in result['sampled_text']


def test_extract_log_samples_custom_parameters():
    """Test log extraction with custom parameters."""
    lines = [f"Error {i}: Something went wrong" for i in range(100)]
    log = '\n'.join(lines)

    result = extract_log_samples(
        log,
        tail_lines=20,
        sample_count=3,
        sample_size=2
    )

    assert result['success'] is True
    assert result['tail_count'] == 20
    assert result['sample_count'] <= 3  # May be less if not enough lines


def test_extract_log_samples_medium_log():
    """Test log with lines between tail and sample threshold."""
    # Log with 60 lines (more than tail but not enough for samples)
    lines = [f"Line {i}" for i in range(60)]
    log = '\n'.join(lines)

    result = extract_log_samples(log, tail_lines=50, sample_count=10, sample_size=5)

    assert result['success'] is True
    # Should have tail but minimal/no samples
    assert "LAST 50 LINES" in result['sampled_text']


def test_extract_log_samples_empty_log():
    """Test extraction with empty log."""
    log = ""

    result = extract_log_samples(log, tail_lines=50)

    assert result['success'] is True
    assert result['tail_count'] == 0
    assert result['sample_count'] == 0


def test_extract_log_samples_single_line():
    """Test extraction with single line log."""
    log = "Single error line"

    result = extract_log_samples(log, tail_lines=50)

    assert result['success'] is True
    assert result['sampled_text'] == log
    assert result['tail_count'] == 1


def test_truncate_log_short():
    """Test truncating log that's already short enough."""
    log = "Line 1\nLine 2\nLine 3"

    result = truncate_log(log, max_lines=100)

    assert result['success'] is True
    assert result['truncated_text'] == log
    assert result['original_lines'] == 3
    assert result['truncated_lines'] == 3
    assert result['was_truncated'] is False


def test_truncate_log_long():
    """Test truncating long log."""
    lines = [f"Line {i}" for i in range(200)]
    log = '\n'.join(lines)

    result = truncate_log(log, max_lines=50)

    assert result['success'] is True
    assert result['original_lines'] == 200
    assert result['truncated_lines'] == 50
    assert result['was_truncated'] is True

    # Should contain last 50 lines
    assert "Line 199" in result['truncated_text']
    assert "Line 150" in result['truncated_text']

    # Should NOT contain early lines
    assert "Line 0" not in result['truncated_text']
    assert "Line 100" not in result['truncated_text']


def test_truncate_log_exact_limit():
    """Test truncating log at exact limit."""
    lines = [f"Line {i}" for i in range(100)]
    log = '\n'.join(lines)

    result = truncate_log(log, max_lines=100)

    assert result['success'] is True
    assert result['original_lines'] == 100
    assert result['truncated_lines'] == 100
    assert result['was_truncated'] is False


def test_truncate_log_empty():
    """Test truncating empty log."""
    log = ""

    result = truncate_log(log, max_lines=100)

    assert result['success'] is True
    assert result['truncated_text'] == log
    assert result['was_truncated'] is False


def test_truncate_log_single_line():
    """Test truncating single line log."""
    log = "Single line"

    result = truncate_log(log, max_lines=50)

    assert result['success'] is True
    assert result['truncated_text'] == log
    assert result['original_lines'] == 1
    assert result['was_truncated'] is False


def test_extract_log_samples_with_special_chars():
    """Test log extraction with special characters."""
    lines = [
        "ERROR: KeyError on line 45",
        "  File '/path/to/file.py', line 123",
        "    raise KeyError('missing_key')",
        "Traceback (most recent call last):",
        "  at function_name (args=...)"
    ] * 20  # Repeat to make it long enough
    log = '\n'.join(lines)

    result = extract_log_samples(log, tail_lines=30)

    assert result['success'] is True
    assert "KeyError" in result['sampled_text']
    assert "Traceback" in result['sampled_text']


def test_truncate_log_preserves_newlines():
    """Test that truncation preserves line structure."""
    lines = [f"Line {i}" for i in range(150)]
    log = '\n'.join(lines)

    result = truncate_log(log, max_lines=100)

    assert result['success'] is True
    # Check line count in result
    result_lines = result['truncated_text'].split('\n')
    assert len(result_lines) == 100
