"""
Validation tool wrapper for ADK agents.

Wraps stat_var_processor.py subprocess execution for PVMAP validation.

Enhanced Features:
- Smart log filtering: Uses log_filter.py for value pattern detection
- Concise feedback: Produces ~50-80 line feedback instead of 500+ lines
- Value pattern analysis: Identifies failing columns from unmapped value types
"""

import logging
import os
import re
import subprocess
import random
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple
from collections import Counter, defaultdict

logger = logging.getLogger(__name__)

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


def _extract_statvar_summary(output_path: str, max_lines: int = 40) -> str:
    """
    Extract a concise StatVar analysis from generated MCF output.

    Parses the processed_stat_vars.mcf file and produces a summary showing
    property→value distributions and flagging potential issues (raw strings
    on dimension properties, corrupted values, etc.).

    Args:
        output_path: Base output path (e.g., "output/dataset/processed").
                     The MCF file is expected at "{output_path}_stat_vars.mcf".
        max_lines: Maximum lines in the summary (default: 40).

    Returns:
        Formatted markdown summary, or empty string if MCF not found.
    """
    mcf_path = Path(f"{output_path}_stat_vars.mcf")
    if not mcf_path.exists():
        return ""

    try:
        mcf_text = mcf_path.read_text(encoding="utf-8")
    except Exception:
        logger.warning("Failed to read MCF file for StatVar analysis: %s", mcf_path)
        return ""

    # Skip properties that are structural, not semantic
    SKIP_PROPS = {"typeOf", "name", "dcid"}

    # Parse MCF nodes
    # Nodes are separated by blank lines and start with "Node:"
    nodes = []
    current_node: Dict[str, str] = {}
    for line in mcf_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            if current_node:
                nodes.append(current_node)
                current_node = {}
            continue
        if line.startswith("Node:"):
            if current_node:
                nodes.append(current_node)
            current_node = {"_node": line.split(":", 1)[1].strip()}
            continue
        if ":" in line:
            prop, _, val = line.partition(":")
            prop = prop.strip()
            val = val.strip()
            if prop not in SKIP_PROPS:
                current_node[prop] = val
    if current_node:
        nodes.append(current_node)

    if not nodes:
        return ""

    # Aggregate property→value counts
    prop_values: Dict[str, Counter] = defaultdict(Counter)
    for node in nodes:
        for prop, val in node.items():
            if prop == "_node":
                continue
            prop_values[prop][val] += 1

    # Identify core vs dimension properties
    core_props = {"populationType", "measuredProperty", "statType", "measurementPeriod"}
    dimension_props = {p for p in prop_values if p not in core_props}

    # Build summary lines
    lines = [f"## Generated StatVar Analysis ({len(nodes)} unique StatVars)"]
    lines.append("")
    lines.append("Properties used:")

    # Core properties first
    for prop in ["populationType", "measuredProperty", "statType"]:
        if prop in prop_values:
            vals = prop_values[prop].most_common(5)
            val_strs = [f"{v} ({c})" for v, c in vals]
            lines.append(f"- {prop}: {', '.join(val_strs)}")

    # Dimension properties
    for prop in sorted(dimension_props):
        vals = prop_values[prop]
        top = vals.most_common(5)
        val_strs = [f"{v} ({c})" for v, c in top]
        suffix = f" (+{len(vals) - 5} more)" if len(vals) > 5 else ""

        # Flag raw strings (no dcid: prefix on values that probably need one)
        has_raw = any(not v.startswith("dcid:") for v, _ in top)
        flag = ""
        if has_raw and prop not in {"measurementPeriod"}:
            flag = " [RAW STRING - may need DCID mapping]"

        lines.append(f"- {prop}: {', '.join(val_strs)}{suffix}{flag}")

    # Detect potential issues
    issues = []
    for prop in sorted(dimension_props):
        vals = prop_values[prop]
        sample_vals = [v for v, _ in vals.most_common(3)]

        # Flag values with special characters suggesting broken CSV parsing
        for v in sample_vals:
            if re.search(r'[$–—/\\]', v) and not v.startswith("dcid:"):
                issues.append(
                    f"- {prop}: Values contain special characters (e.g., '{v[:60]}') "
                    f"— likely broken CSV parsing or need DCID enum mappings"
                )
                break

        # Flag single-value dimensions
        if len(vals) == 1:
            only_val = list(vals.keys())[0]
            issues.append(
                f"- {prop}: Only 1 unique value ('{only_val[:40]}') — may be missing category breakdowns"
            )

        # Flag raw strings on dimension properties
        raw_count = sum(c for v, c in vals.items() if not v.startswith("dcid:"))
        if raw_count > 0 and raw_count == sum(vals.values()):
            issues.append(
                f"- {prop}: All {len(vals)} values are raw strings — likely need DCID enum mappings from schema vocab"
            )

    if issues:
        lines.append("")
        lines.append("Potential Issues:")
        # Deduplicate: keep first mention per property
        seen_props = set()
        for issue in issues:
            prop_name = issue.split(":")[1].strip() if ":" in issue else ""
            if prop_name not in seen_props:
                lines.append(issue)
                seen_props.add(prop_name)

    # Cap output
    result = "\n".join(lines[:max_lines])
    return result


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
            "data_rows": 0,
            "counter_summary": "",
        }

    if metadata_file and not Path(metadata_file).exists():
        return {
            "success": False,
            "error": f"Metadata file not found: {metadata_file}",
            "error_logs": None,
            "output_file": None,
            "data_rows": 0,
            "counter_summary": "",
        }

    if not pvmap_path or not Path(pvmap_path).exists():
        return {
            "success": False,
            "error": f"PVMAP file not found: {pvmap_path}",
            "error_logs": None,
            "output_file": None,
            "data_rows": 0,
            "counter_summary": "",
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
        logger.info("Running validation subprocess: timeout=%ds, pvmap=%s", timeout, pvmap_path)
        logger.debug("Subprocess cmd: %s", " ".join(cmd))
        start_time = time.monotonic()
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(PROJECT_ROOT),
            env=env
        )
        elapsed = time.monotonic() - start_time
        logger.info(
            "Validation subprocess finished: returncode=%d, elapsed=%.1fs",
            result.returncode, elapsed,
        )

        # Write raw logs to file (overwrite on each retry — always reflects latest attempt).
        # Cap at 1MB to avoid multi-GB log files from verbose datasets.
        MAX_RAW_LOG_CHARS = 1_000_000
        raw_log_path = Path(output_dir) / "statvar_processor_raw_logs.txt"
        raw_log_content = ""
        if result.stdout:
            raw_log_content += "=== STDOUT ===\n" + result.stdout + "\n"
        if result.stderr:
            raw_log_content += "=== STDERR ===\n" + result.stderr + "\n"
        if not raw_log_content:
            raw_log_content = "(no output captured)\n"
        if len(raw_log_content) > MAX_RAW_LOG_CHARS:
            # Keep first 200K + last 800K (errors/summary usually at the end)
            head = raw_log_content[:200_000]
            tail = raw_log_content[-800_000:]
            raw_log_content = (
                head
                + f"\n\n... [{len(raw_log_content) - MAX_RAW_LOG_CHARS:,} chars truncated] ...\n\n"
                + tail
            )
        raw_log_path.write_text(raw_log_content, encoding="utf-8")

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
                    "returncode": result.returncode,
                    "counter_summary": filtered_logs.to_summary() if filtered_logs else "",
                }

            # Validation passed
            logger.info("Validation PASSED: %d data rows in output", data_rows)
            counter_summary = filtered_logs.to_summary() if filtered_logs else ""

            # Extract StatVar analysis from MCF output
            statvar_analysis = _extract_statvar_summary(
                str(Path(output_dir) / "processed")
            )

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
                "returncode": result.returncode,
                "counter_summary": counter_summary,
                "statvar_analysis": statvar_analysis,
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
                "returncode": result.returncode,
                "counter_summary": filtered_logs.to_summary() if filtered_logs else "",
            }

    except subprocess.TimeoutExpired:
        logger.error("Validation subprocess timed out after %d seconds", timeout)
        return {
            "success": False,
            "error": f"Validation timed out after {timeout} seconds",
            "error_logs": None,
            "structured_feedback": None,
            "counters": {},
            "output_file": None,
            "data_rows": 0,
            "returncode": -1,
            "counter_summary": "",
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
            "returncode": -1,
            "counter_summary": "",
        }
