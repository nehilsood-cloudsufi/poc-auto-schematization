"""
Logging utility tools for ADK agents.

Provides log sampling and extraction utilities.
"""

import random
from typing import Dict, Any


def extract_log_samples(
    log_output: str,
    tail_lines: int = 50,
    sample_count: int = 10,
    sample_size: int = 5
) -> Dict[str, Any]:
    """
    Extract meaningful log samples for error feedback.

    Migrated from run_pvmap_pipeline.py:813-854.

    Extracts both:
    - Last N lines (tail) for most recent context
    - Random samples from earlier in the log for broader context

    Args:
        log_output: Full log output string
        tail_lines: Number of lines to include from the end (default: 50)
        sample_count: Number of random samples to take from the middle (default: 10)
        sample_size: Number of consecutive lines per sample (default: 5)

    Returns:
        Dictionary with:
            - success: bool indicating extraction succeeded
            - sampled_text: str with formatted samples
            - tail_count: int number of tail lines included
            - sample_count: int number of random samples included
            - error: str with error message if failed
    """
    try:
        # Filter empty lines
        lines = [l for l in log_output.split('\n') if l.strip()]

        if len(lines) <= tail_lines:
            # Log is short enough, return all of it
            return {
                "success": True,
                "sampled_text": log_output,
                "tail_count": len(lines),
                "sample_count": 0,
                "error": None
            }

        result_parts = []

        # Get last N lines (tail)
        tail_section = lines[-tail_lines:]
        result_parts.append("=== LAST {} LINES OF LOG ===\n{}".format(
            tail_lines, '\n'.join(tail_section)
        ))

        # Get random samples from the middle section (excluding tail)
        middle_lines = lines[:-tail_lines]
        actual_samples = 0

        if len(middle_lines) > sample_size * sample_count:
            result_parts.append("\n\n=== RANDOM SAMPLES FROM EARLIER IN LOG ===")

            # Take random samples
            for i in range(sample_count):
                # Pick a random starting position
                max_start = len(middle_lines) - sample_size
                if max_start > 0:
                    start_idx = random.randint(0, max_start)
                    sample = middle_lines[start_idx:start_idx + sample_size]
                    result_parts.append(
                        f"\n--- Sample {i+1} (lines {start_idx+1}-{start_idx+sample_size}) ---\n" +
                        '\n'.join(sample)
                    )
                    actual_samples += 1

        sampled_text = '\n'.join(result_parts)

        return {
            "success": True,
            "sampled_text": sampled_text,
            "tail_count": tail_lines,
            "sample_count": actual_samples,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "sampled_text": log_output,  # Return original on error
            "tail_count": 0,
            "sample_count": 0,
            "error": f"Log sampling failed: {str(e)}"
        }


def truncate_log(log_output: str, max_lines: int = 100) -> Dict[str, Any]:
    """
    Truncate log output to maximum number of lines.

    Args:
        log_output: Full log output string
        max_lines: Maximum number of lines to keep

    Returns:
        Dictionary with:
            - success: bool indicating truncation succeeded
            - truncated_text: str with truncated log
            - original_lines: int number of lines in original
            - truncated_lines: int number of lines in result
            - was_truncated: bool whether truncation occurred
            - error: str with error message if failed
    """
    try:
        lines = log_output.split('\n')
        original_count = len(lines)

        if original_count <= max_lines:
            return {
                "success": True,
                "truncated_text": log_output,
                "original_lines": original_count,
                "truncated_lines": original_count,
                "was_truncated": False,
                "error": None
            }

        # Keep last max_lines
        truncated = lines[-max_lines:]
        truncated_text = '\n'.join(truncated)

        return {
            "success": True,
            "truncated_text": truncated_text,
            "original_lines": original_count,
            "truncated_lines": max_lines,
            "was_truncated": True,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "truncated_text": log_output,
            "original_lines": 0,
            "truncated_lines": 0,
            "was_truncated": False,
            "error": f"Log truncation failed: {str(e)}"
        }
