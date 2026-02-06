"""
Validation tool wrapper for ADK agents.

Wraps stat_var_processor.py subprocess execution for PVMAP validation.

Enhanced Features:
- Smart log filtering: Uses log_filter.py for value pattern detection
- Concise feedback: Produces ~50-80 line feedback instead of 500+ lines
- Value pattern analysis: Identifies failing columns from unmapped value types
"""

import os
import subprocess
import random
from pathlib import Path
from typing import Dict, Any, Optional, Tuple

# Base directories
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
SRC_DIR = PROJECT_ROOT / "src"
VALIDATION_DIR = SRC_DIR / "pipeline" / "validation"

# Import smart log filter module (replaces counter_feedback)
from src.pipeline.validation.log_filter import (
    filter_counters,
    generate_concise_feedback,
    extract_sample_errors,
)


def extract_log_samples(
    log_output: str,
    tail_lines: int = 50,
    sample_count: int = 10,
    sample_size: int = 5
) -> str:
    """
    Extract meaningful log samples for error feedback.

    Migrated from run_pvmap_pipeline.py:813-854.

    Args:
        log_output: Full log output string
        tail_lines: Number of lines to include from the end
        sample_count: Number of random samples to take from the middle
        sample_size: Number of consecutive lines per sample

    Returns:
        Formatted string with tail and random samples
    """
    lines = [l for l in log_output.split('\n') if l.strip()]

    if len(lines) <= tail_lines:
        # Log is short enough, return all of it
        return log_output

    result_parts = []

    # Get last N lines (tail)
    tail_section = lines[-tail_lines:]
    result_parts.append("=== LAST {} LINES OF LOG ===\n{}".format(
        tail_lines, '\n'.join(tail_section)
    ))

    # Get random samples from the middle section (excluding tail)
    middle_lines = lines[:-tail_lines]
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

    return '\n'.join(result_parts)


def build_validation_command(
    input_data: Path,
    pvmap_path: Path,
    metadata_file: Optional[Path],
    output_dir: Path,
    debug: bool = True
) -> Tuple[list, dict]:
    """
    Build subprocess command and environment for stat_var_processor.

    Migrated from run_pvmap_pipeline.py:878-913.

    Args:
        input_data: Path to input data CSV
        pvmap_path: Path to PVMAP CSV file
        metadata_file: Path to metadata config CSV (optional, omit --config_file if None)
        output_dir: Output directory for processed file
        debug: Enable debug counters for detailed error context (default: True)

    Returns:
        Tuple of (command_list, environment_dict)
    """
    # Set up environment with PYTHONPATH
    env = os.environ.copy()
    pythonpath_parts = [
        str(PROJECT_ROOT),
        str(SRC_DIR),
        env.get('PYTHONPATH', '')
    ]
    env['PYTHONPATH'] = ':'.join(filter(None, pythonpath_parts))

    # Build command - use .venv python if available
    venv_python = PROJECT_ROOT / '.venv' / 'bin' / 'python3'
    python_cmd = str(venv_python) if venv_python.exists() else 'python3'

    cmd = [
        python_cmd,
        str(VALIDATION_DIR / 'stat_var_processor.py'),
        f'--input_data={input_data}',
        f'--pv_map={pvmap_path}',
    ]

    if metadata_file:
        cmd.append(f'--config_file={metadata_file}')

    cmd.extend([
        '--generate_statvar_name=True',
        f'--output_path={output_dir}/processed'
    ])

    # Add debug flag to capture specific failing values in counters
    if debug:
        cmd.append('--debug=True')

    return cmd, env


def validate_output_file(output_file: Path) -> Tuple[bool, Optional[str], int]:
    """
    Validate that output file has data rows (not just header).

    Migrated from run_pvmap_pipeline.py:934-957.

    Args:
        output_file: Path to the processed output file

    Returns:
        Tuple of (has_data, error_message, data_row_count)
    """
    if not output_file.exists():
        return False, "Validation did not produce output file", 0

    try:
        with open(output_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()

        # Filter out empty lines
        data_lines = [l for l in lines if l.strip()]

        if len(data_lines) <= 1:  # Only header or empty
            return False, "Validation produced empty output (no data rows)", 0

        data_row_count = len(data_lines) - 1  # Exclude header
        return True, None, data_row_count

    except Exception as e:
        return False, f"Error reading output file: {str(e)}", 0


def run_validation(
    input_data: str,
    pvmap_path: str,
    metadata_file: str,
    output_dir: str,
    timeout: int = 300,
    attempt_number: int = 0
) -> Dict[str, Any]:
    """
    Run stat_var_processor validation subprocess.

    Wraps the entire validation flow from run_pvmap_pipeline.py:874-975.
    Enhanced with counter-based feedback for more actionable error diagnosis.

    Args:
        input_data: Path to input data CSV (as string)
        pvmap_path: Path to PVMAP CSV file (as string)
        metadata_file: Path to metadata config CSV (as string)
        output_dir: Output directory for processed file (as string)
        timeout: Subprocess timeout in seconds (default: 300 = 5 minutes)
        attempt_number: Current retry attempt (0-indexed) for iteration-specific advice

    Returns:
        Dictionary with:
            - success: bool indicating validation passed
            - output_file: str path to processed output file (if exists)
            - data_rows: Number of data rows in output
            - error_logs: Sampled error logs (if failed) - DEPRECATED, use structured_feedback
            - structured_feedback: Counter-based structured feedback (preferred)
            - counters: Parsed counter dictionary
            - error: Error message (if failed)
            - stdout: Process stdout
            - stderr: Process stderr
            - returncode: Process return code
    """
    # Validate inputs
    if not input_data or not Path(input_data).exists():
        return {
            "success": False,
            "error": f"Input data file not found: {input_data}",
            "error_logs": None,
            "output_file": None,
            "data_rows": 0
        }

    if metadata_file and not Path(metadata_file).exists():
        return {
            "success": False,
            "error": f"Metadata file not found: {metadata_file}",
            "error_logs": None,
            "output_file": None,
            "data_rows": 0
        }

    if not pvmap_path or not Path(pvmap_path).exists():
        return {
            "success": False,
            "error": f"PVMAP file not found: {pvmap_path}",
            "error_logs": None,
            "output_file": None,
            "data_rows": 0
        }

    # Build command and environment (with debug=True for detailed error context)
    cmd, env = build_validation_command(
        input_data=Path(input_data),
        pvmap_path=Path(pvmap_path),
        metadata_file=Path(metadata_file) if metadata_file else None,
        output_dir=Path(output_dir),
        debug=True
    )

    output_file = Path(output_dir) / "processed.csv"
    counters_file = Path(output_dir) / "processed_counters.txt"

    try:
        # Run subprocess
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=env
        )

        # Parse counters file using smart log filter (for structured feedback)
        filtered_logs = filter_counters(counters_file) if counters_file.exists() else None
        counters = {}  # Keep for backward compatibility

        # Check return code
        if result.returncode == 0:
            # Validate output file has data
            has_data, error_msg, data_rows = validate_output_file(output_file)

            if not has_data:
                # Use smart log filter for concise, actionable feedback
                processor_output = result.stderr or result.stdout or ""

                if filtered_logs:
                    # Use concise feedback with value pattern analysis
                    structured_feedback = generate_concise_feedback(
                        counters_path=counters_file,
                        stderr=processor_output,
                        max_error_samples=5
                    )
                    full_error = (
                        f"{error_msg}. "
                        f"The PVMAP may have incorrect column mappings or key names "
                        f"that don't match the input data.\n\n"
                        f"{structured_feedback}"
                    )
                    sampled_logs = None
                else:
                    # Fall back to random sampling if no counters
                    sampled_logs = extract_log_samples(
                        processor_output,
                        tail_lines=50,
                        sample_count=10,
                        sample_size=5
                    )
                    structured_feedback = None
                    full_error = (
                        f"{error_msg}. "
                        f"The PVMAP may have incorrect column mappings or key names "
                        f"that don't match the input data.\n\n"
                        f"Processor logs:\n{sampled_logs}"
                    )

                return {
                    "success": False,
                    "error": full_error,
                    "error_logs": sampled_logs,
                    "structured_feedback": structured_feedback,
                    "counters": counters,
                    "output_file": str(output_file) if output_file.exists() else None,
                    "data_rows": 0,
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "returncode": result.returncode
                }

            # Validation passed
            return {
                "success": True,
                "error": None,
                "error_logs": None,
                "structured_feedback": None,
                "counters": counters,
                "output_file": str(output_file),
                "data_rows": data_rows,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

        else:
            # Non-zero exit code - use smart log filter for feedback
            raw_error = result.stderr or result.stdout or "Unknown validation error"

            if filtered_logs:
                # Use concise feedback with value pattern analysis
                structured_feedback = generate_concise_feedback(
                    counters_path=counters_file,
                    stderr=raw_error,
                    max_error_samples=5
                )
                error_msg = (
                    f"Validation FAILED (exit code {result.returncode}).\n\n"
                    f"{structured_feedback}"
                )
                sampled_logs = None
            else:
                # Fall back to random sampling if no counters
                sampled_logs = extract_log_samples(
                    raw_error,
                    tail_lines=50,
                    sample_count=10,
                    sample_size=5
                )
                structured_feedback = None
                error_msg = (
                    f"Validation FAILED (exit code {result.returncode}).\n\n"
                    f"Processor logs:\n{sampled_logs}"
                )

            return {
                "success": False,
                "error": error_msg,
                "error_logs": sampled_logs,
                "structured_feedback": structured_feedback,
                "counters": counters,
                "output_file": str(output_file) if output_file.exists() else None,
                "data_rows": 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "returncode": result.returncode
            }

    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "error": f"Validation timed out after {timeout} seconds",
            "error_logs": None,
            "structured_feedback": None,
            "counters": {},
            "output_file": None,
            "data_rows": 0,
            "returncode": -1
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Validation error: {str(e)}",
            "error_logs": None,
            "structured_feedback": None,
            "counters": {},
            "output_file": None,
            "data_rows": 0,
            "returncode": -1
        }
