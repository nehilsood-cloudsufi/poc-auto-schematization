#!/usr/bin/env python3
"""
PVMAP Generation & Validation Pipeline

This script automates the PVMAP generation workflow:
1. Discovers datasets in input/ folder
2. Combines/merges multiple input files if needed
3. Populates prompt template with dataset files
4. Calls Claude Code CLI to generate PVMAP
5. Provides human-in-the-loop validation with retry logic

Usage:
    python3 run_pvmap_pipeline.py                     # Process all datasets
    python3 run_pvmap_pipeline.py --dataset=bis      # Process specific dataset
    python3 run_pvmap_pipeline.py --resume-from=edu  # Resume from dataset
    python3 run_pvmap_pipeline.py --dry-run          # Show what would be processed
"""

import argparse
import csv
import glob
import logging
import os
import random
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Constants
BASE_DIR = Path(__file__).parent.resolve()
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
TOOLS_DIR = BASE_DIR / "tools"
LOGS_DIR = BASE_DIR / "logs"
PROMPT_TEMPLATE = TOOLS_DIR / "improved_pvmap_prompt.txt"

MAX_RETRIES = 2


class DatasetInfo:
    """Information about a dataset and its files."""

    def __init__(self, name: str, path: Path):
        self.name = name
        self.path = path
        self.test_data_path = path / "test_data"

        # Files to be discovered
        self.schema_examples: Optional[Path] = None
        self.metadata_files: List[Path] = []
        self.sampled_data_files: List[Path] = []
        self.input_data_files: List[Path] = []

        # Combined/merged file paths (created during preparation)
        self.combined_metadata: Optional[Path] = None
        self.combined_sampled_data: Optional[Path] = None
        self.combined_input_data: Optional[Path] = None

        # Output paths
        self.output_dir = OUTPUT_DIR / name
        self.pvmap_path = self.output_dir / "generated_pvmap.csv"
        self.notes_path = self.output_dir / "generation_notes.md"


def setup_logging(timestamp: str) -> Tuple[logging.Logger, Path]:
    """Set up logging for the pipeline."""
    LOGS_DIR.mkdir(exist_ok=True)

    log_file = LOGS_DIR / f"pipeline_{timestamp}.log"

    # Create logger
    logger = logging.getLogger("pvmap_pipeline")
    logger.setLevel(logging.DEBUG)

    # File handler - detailed logs
    fh = logging.FileHandler(log_file)
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))

    # Console handler - summary logs
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(logging.Formatter('%(message)s'))

    logger.addHandler(fh)
    logger.addHandler(ch)

    return logger, log_file


def setup_dataset_logging(dataset_name: str, timestamp: str) -> logging.Logger:
    """Set up per-dataset logging."""
    dataset_log_dir = LOGS_DIR / dataset_name
    dataset_log_dir.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(f"pvmap_pipeline.{dataset_name}")
    logger.setLevel(logging.DEBUG)
    logger.propagate = False  # Don't propagate to parent logger

    # Generation log
    gen_handler = logging.FileHandler(
        dataset_log_dir / f"generation_{timestamp}.log"
    )
    gen_handler.setLevel(logging.DEBUG)
    gen_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    ))
    logger.addHandler(gen_handler)

    return logger


def discover_datasets(input_dir: Path) -> List[DatasetInfo]:
    """Discover all datasets in the input directory."""
    datasets = []

    for dataset_path in sorted(input_dir.iterdir()):
        if not dataset_path.is_dir():
            continue

        dataset = DatasetInfo(dataset_path.name, dataset_path)

        # Find schema examples
        schema_files = list(dataset_path.glob("scripts_*_schema_examples_*.txt"))
        if schema_files:
            dataset.schema_examples = schema_files[0]

        # Find metadata files
        dataset.metadata_files = list(dataset_path.glob("*_metadata.csv"))

        # Find test data files
        if dataset.test_data_path.exists():
            # Exclude combined_* files to avoid infinite loops when re-running
            dataset.sampled_data_files = [
                f for f in dataset.test_data_path.glob("*_sampled_data.csv")
                if not f.name.startswith("combined_")
            ]
            dataset.input_data_files = [
                f for f in dataset.test_data_path.glob("*_input.csv")
                if not f.name.startswith("combined_")
            ]

        datasets.append(dataset)

    return datasets


def combine_csv_files(files: List[Path], output_path: Path, logger: logging.Logger) -> bool:
    """Combine multiple CSV files into one, preserving headers from first file."""
    if not files:
        return False

    if len(files) == 1:
        # Just copy single file
        import shutil
        shutil.copy(files[0], output_path)
        logger.debug(f"Copied single file: {files[0].name} -> {output_path.name}")
        return True

    logger.info(f"Combining {len(files)} files into {output_path.name}")

    try:
        with open(output_path, 'w', newline='', encoding='utf-8') as outfile:
            writer = None
            header_written = False

            for i, filepath in enumerate(files):
                with open(filepath, 'r', encoding='utf-8') as infile:
                    reader = csv.reader(infile)
                    header = next(reader, None)

                    if header is None:
                        logger.warning(f"Empty file: {filepath.name}")
                        continue

                    if not header_written:
                        writer = csv.writer(outfile)
                        writer.writerow(header)
                        header_written = True
                        logger.debug(f"Using header from: {filepath.name}")

                    for row in reader:
                        writer.writerow(row)

                logger.debug(f"Added data from: {filepath.name}")

        return True

    except Exception as e:
        logger.error(f"Error combining files: {e}")
        return False


def merge_metadata_files(files: List[Path], output_path: Path, logger: logging.Logger) -> bool:
    """Merge multiple metadata config files into one."""
    if not files:
        return False

    if len(files) == 1:
        import shutil
        shutil.copy(files[0], output_path)
        logger.debug(f"Copied single metadata: {files[0].name}")
        return True

    logger.info(f"Merging {len(files)} metadata files into {output_path.name}")

    try:
        merged_params = {}

        for filepath in files:
            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.reader(f)
                for row in reader:
                    if len(row) >= 2:
                        param, value = row[0], row[1]
                        if param not in merged_params:
                            merged_params[param] = value
                        elif merged_params[param] != value:
                            logger.warning(
                                f"Conflicting value for '{param}': "
                                f"'{merged_params[param]}' vs '{value}'"
                            )

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for param, value in merged_params.items():
                writer.writerow([param, value])

        logger.debug(f"Merged {len(merged_params)} parameters")
        return True

    except Exception as e:
        logger.error(f"Error merging metadata: {e}")
        return False


def prepare_dataset(dataset: DatasetInfo, logger: logging.Logger) -> bool:
    """Prepare dataset by combining/merging files as needed."""
    logger.info(f"Preparing dataset: {dataset.name}")

    # Create output directory
    dataset.output_dir.mkdir(parents=True, exist_ok=True)

    # Combine sampled data files
    if dataset.sampled_data_files:
        combined_path = dataset.test_data_path / "combined_sampled_data.csv"
        if combine_csv_files(dataset.sampled_data_files, combined_path, logger):
            dataset.combined_sampled_data = combined_path
        else:
            logger.error(f"Failed to combine sampled data for {dataset.name}")
            return False
    else:
        logger.warning(f"No sampled data files found for {dataset.name}")
        return False

    # Combine input data files
    if dataset.input_data_files:
        combined_path = dataset.test_data_path / "combined_input.csv"
        if combine_csv_files(dataset.input_data_files, combined_path, logger):
            dataset.combined_input_data = combined_path
    else:
        logger.warning(f"No input data files found for {dataset.name}")

    # Merge metadata files
    if dataset.metadata_files:
        combined_path = dataset.path / f"{dataset.name}_combined_metadata.csv"
        if merge_metadata_files(dataset.metadata_files, combined_path, logger):
            dataset.combined_metadata = combined_path
        else:
            logger.error(f"Failed to merge metadata for {dataset.name}")
            return False
    else:
        logger.warning(f"No metadata files found for {dataset.name}")
        return False

    logger.info(f"Dataset {dataset.name} prepared successfully")
    return True


def read_file_content(filepath: Path) -> str:
    """Read and return file content."""
    with open(filepath, 'r', encoding='utf-8') as f:
        return f.read()


def populate_prompt(dataset: DatasetInfo, logger: logging.Logger) -> Optional[str]:
    """Populate the prompt template with dataset files."""
    logger.info("Populating prompt template")

    try:
        # Read template
        template = read_file_content(PROMPT_TEMPLATE)

        # Read schema examples
        if dataset.schema_examples:
            schema_content = read_file_content(dataset.schema_examples)
            logger.debug(f"Schema examples: {len(schema_content)} chars")
        else:
            schema_content = "No schema examples available."
            logger.warning("No schema examples found")

        # Read sampled data
        if dataset.combined_sampled_data:
            sampled_content = read_file_content(dataset.combined_sampled_data)
            logger.debug(f"Sampled data: {len(sampled_content)} chars")
        else:
            logger.error("No sampled data available")
            return None

        # Read metadata
        if dataset.combined_metadata:
            metadata_content = read_file_content(dataset.combined_metadata)
            logger.debug(f"Metadata: {len(metadata_content)} chars")
        else:
            logger.error("No metadata available")
            return None

        # Replace placeholders
        prompt = template.replace("{{SCHEMA_EXAMPLES}}", schema_content)
        prompt = prompt.replace("{{SAMPLED_DATA}}", sampled_content)
        prompt = prompt.replace("{{METADATA_CONFIG}}", metadata_content)

        logger.info(f"Prompt populated: {len(prompt)} chars total")
        return prompt

    except Exception as e:
        logger.error(f"Error populating prompt: {e}")
        return None


def generate_pvmap(
    dataset: DatasetInfo,
    prompt: str,
    logger: logging.Logger,
    error_feedback: Optional[str] = None,
    attempt: int = 0
) -> Tuple[bool, str]:
    """
    Call Claude Code CLI to generate PVMAP.

    Returns:
        Tuple of (success, output_content)
    """
    logger.info("Calling Claude Code CLI to generate PVMAP")

    # Add error feedback to prompt if retrying
    if error_feedback:
        prompt = (
            f"{prompt}\n\n"
            f"---\n\n"
            f"# PREVIOUS ERROR - PLEASE FIX\n\n"
            f"The previous PVMAP generation had errors during validation:\n\n"
            f"```\n{error_feedback}\n```\n\n"
            f"Please fix the PVMAP to address these errors."
        )
        logger.info("Added error feedback to prompt")

    # Write prompt to temp file (prompts can be very large)
    prompt_file = dataset.output_dir / "populated_prompt.txt"
    with open(prompt_file, 'w', encoding='utf-8') as f:
        f.write(prompt)

    try:
        # Call Claude Code CLI using stdin piping for large prompts
        # The --print flag makes Claude output directly without interactive mode
        # Using stdin pipe avoids shell argument length limits with large prompts
        logger.debug(f"Running Claude Code with prompt from: {prompt_file}")

        with open(prompt_file, 'r', encoding='utf-8') as prompt_f:
            result = subprocess.run(
                ['claude', '--dangerously-skip-permissions', '--print', '--model', 'sonnet', '-p', '-'],
                stdin=prompt_f,
                capture_output=True,
                text=True,
                timeout=900,  # 15 minute timeout for larger datasets
                cwd=str(BASE_DIR)
            )

        output = result.stdout

        if result.returncode != 0:
            logger.error(f"Claude Code returned error: {result.stderr}")
            return False, result.stderr

        logger.info(f"Claude Code completed, output: {len(output)} chars")

        # Save full Claude output for this attempt (includes reasoning)
        response_dir = dataset.output_dir / "generated_response"
        response_dir.mkdir(parents=True, exist_ok=True)
        attempt_file = response_dir / f"attempt_{attempt}.md"
        with open(attempt_file, 'w', encoding='utf-8') as f:
            f.write(f"# {dataset.name} - Claude Response (Attempt {attempt})\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            if error_feedback:
                f.write("## Error Feedback Provided\n\n")
                f.write(f"```\n{error_feedback[:2000]}\n```\n\n")
            f.write("## Claude's Full Response\n\n")
            f.write(output)
        logger.info(f"Claude response saved to: {attempt_file}")

        # Also update the main notes file with latest attempt
        with open(dataset.notes_path, 'w', encoding='utf-8') as f:
            f.write(f"# {dataset.name} - PVMAP Generation Notes\n\n")
            f.write(f"Generated: {datetime.now().isoformat()}\n\n")
            f.write(f"Total attempts: {attempt + 1}\n\n")
            f.write("---\n\n")
            f.write(output)

        # Try to extract CSV from output
        pvmap_csv = extract_pvmap_csv(output, logger)

        if pvmap_csv:
            with open(dataset.pvmap_path, 'w', encoding='utf-8') as f:
                f.write(pvmap_csv)
            logger.info(f"PVMAP saved to: {dataset.pvmap_path}")
            return True, output
        else:
            logger.error("Could not extract PVMAP CSV from output")
            return False, "Could not extract PVMAP CSV from output"

    except subprocess.TimeoutExpired:
        logger.error("Claude Code timed out after 15 minutes")
        return False, "Timeout"
    except Exception as e:
        logger.error(f"Error running Claude Code: {e}")
        return False, str(e)


def extract_pvmap_csv(output: str, logger: logging.Logger) -> Optional[str]:
    """Extract the PVMAP CSV from Claude's output."""
    # Look for CSV content starting with "key"
    lines = output.split('\n')
    csv_lines = []
    in_csv = False

    for line in lines:
        stripped = line.strip()

        # Start of CSV (header row)
        if stripped.startswith('key,') or stripped == 'key':
            in_csv = True
            csv_lines = [stripped]
            continue

        if in_csv:
            # End of CSV (empty line or markdown)
            if not stripped or stripped.startswith('#') or stripped.startswith('```'):
                if csv_lines:
                    break
            else:
                csv_lines.append(stripped)

    if csv_lines:
        csv_content = '\n'.join(csv_lines)
        logger.debug(f"Extracted CSV with {len(csv_lines)} rows")
        return csv_content

    # Fallback: look for CSV in code blocks
    import re
    code_block_pattern = r'```(?:csv)?\n(key[,\n].*?)```'
    matches = re.findall(code_block_pattern, output, re.DOTALL)

    if matches:
        logger.debug("Found CSV in code block")
        return matches[0].strip()

    logger.warning("Could not find PVMAP CSV in output")
    return None


def extract_log_samples(log_output: str, tail_lines: int = 50, sample_count: int = 10, sample_size: int = 5) -> str:
    """
    Extract meaningful log samples for error feedback.

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
                result_parts.append(f"\n--- Sample {i+1} (lines {start_idx+1}-{start_idx+sample_size}) ---\n" + '\n'.join(sample))

    return '\n'.join(result_parts)


def get_validation_command(dataset: DatasetInfo) -> str:
    """Generate the stat_var_processor validation command."""
    input_file = dataset.combined_input_data or dataset.input_data_files[0] if dataset.input_data_files else "INPUT_FILE_NOT_FOUND"
    metadata_file = dataset.combined_metadata or dataset.metadata_files[0] if dataset.metadata_files else "METADATA_NOT_FOUND"

    cmd = (
        f'PYTHONPATH="$PYTHONPATH:$(pwd):$(pwd)/tools:$(pwd)/util" '
        f'python3 tools/stat_var_processor.py \\\n'
        f'    --input_data="{input_file}" \\\n'
        f'    --pv_map="{dataset.pvmap_path}" \\\n'
        f'    --config_file="{metadata_file}" \\\n'
        f'    --generate_statvar_name=True \\\n'
        f'    --output_path="{dataset.output_dir}/processed"'
    )
    return cmd


def run_validation(dataset: DatasetInfo, logger: logging.Logger) -> Tuple[bool, Optional[str]]:
    """Run stat_var_processor.py automatically and return success/error."""
    logger.info("Running stat_var_processor validation...")

    # Set up environment with PYTHONPATH
    env = os.environ.copy()
    pythonpath_parts = [
        str(BASE_DIR),
        str(TOOLS_DIR),
        str(BASE_DIR / "util"),
        env.get('PYTHONPATH', '')
    ]
    env['PYTHONPATH'] = ':'.join(filter(None, pythonpath_parts))

    # Determine input files
    input_file = dataset.combined_input_data or (
        dataset.input_data_files[0] if dataset.input_data_files else None
    )
    metadata_file = dataset.combined_metadata or (
        dataset.metadata_files[0] if dataset.metadata_files else None
    )

    if not input_file or not metadata_file:
        error_msg = "Missing input_data or metadata file for validation"
        logger.error(error_msg)
        return False, error_msg

    # Build command - use venv python if available
    venv_python = BASE_DIR / 'venv' / 'bin' / 'python3'
    python_cmd = str(venv_python) if venv_python.exists() else 'python3'

    cmd = [
        python_cmd,
        str(TOOLS_DIR / 'stat_var_processor.py'),
        f'--input_data={input_file}',
        f'--pv_map={dataset.pvmap_path}',
        f'--config_file={metadata_file}',
        '--generate_statvar_name=True',
        f'--output_path={dataset.output_dir}/processed'
    ]

    logger.debug(f"Validation command: {' '.join(cmd)}")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,  # 5 minute timeout
            cwd=str(BASE_DIR),
            env=env
        )

        # Log output
        if result.stdout:
            logger.debug(f"Validation stdout: {result.stdout[:500]}...")
        if result.stderr:
            logger.debug(f"Validation stderr: {result.stderr[:500]}...")

        if result.returncode == 0:
            # Check if output file has data (not just header)
            output_file = dataset.output_dir / "processed.csv"
            if output_file.exists():
                with open(output_file, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                # Filter out empty lines
                data_lines = [l for l in lines if l.strip()]
                if len(data_lines) <= 1:  # Only header or empty
                    # Include stderr/stdout for debugging with better sampling
                    processor_output = result.stderr or result.stdout or ""
                    # Extract meaningful log samples: last 50 lines + 10 random samples of 5 lines each
                    sampled_logs = extract_log_samples(processor_output, tail_lines=50, sample_count=10, sample_size=5)
                    error_msg = (
                        f"Validation produced empty output (no data rows). "
                        f"The PVMAP may have incorrect column mappings or key names that don't match the input data.\n\n"
                        f"Processor logs:\n{sampled_logs}"
                    )
                    logger.error(f"Validation FAILED: {error_msg}")
                    return False, error_msg
                logger.info(f"Validation PASSED ({len(data_lines) - 1} data rows)")
            else:
                error_msg = "Validation did not produce output file"
                logger.error(f"Validation FAILED: {error_msg}")
                return False, error_msg
            return True, result.stdout
        else:
            raw_error = result.stderr or result.stdout or "Unknown validation error"
            # Extract meaningful log samples for better debugging
            sampled_logs = extract_log_samples(raw_error, tail_lines=50, sample_count=10, sample_size=5)
            error_msg = f"Validation FAILED (exit code {result.returncode}).\n\nProcessor logs:\n{sampled_logs}"
            logger.error(f"Validation FAILED (exit code {result.returncode})")
            logger.error(f"Error: {raw_error[:200]}...")
            return False, error_msg

    except subprocess.TimeoutExpired:
        error_msg = "Validation timed out after 5 minutes"
        logger.error(error_msg)
        return False, error_msg
    except Exception as e:
        error_msg = f"Validation error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def process_dataset(
    dataset: DatasetInfo,
    logger: logging.Logger,
    dataset_logger: logging.Logger,
    dry_run: bool = False
) -> bool:
    """Process a single dataset through the full pipeline."""
    logger.info(f"\n{'='*60}")
    logger.info(f"Processing dataset: {dataset.name}")
    logger.info(f"{'='*60}")

    # Log discovered files (to both file logger and main logger for console)
    logger.info(f"Schema examples: {dataset.schema_examples}")
    logger.info(f"Metadata files: {[f.name for f in dataset.metadata_files]}")
    logger.info(f"Sampled data files: {[f.name for f in dataset.sampled_data_files]}")
    logger.info(f"Input data files: {[f.name for f in dataset.input_data_files]}")

    # Also log to dataset-specific file
    dataset_logger.info(f"Schema examples: {dataset.schema_examples}")
    dataset_logger.info(f"Metadata files: {[f.name for f in dataset.metadata_files]}")
    dataset_logger.info(f"Sampled data files: {[f.name for f in dataset.sampled_data_files]}")
    dataset_logger.info(f"Input data files: {[f.name for f in dataset.input_data_files]}")

    if dry_run:
        logger.info("[DRY RUN] Would process this dataset")
        return True

    # Step 1: Prepare dataset (combine/merge files)
    if not prepare_dataset(dataset, dataset_logger):
        logger.error(f"Failed to prepare dataset: {dataset.name}")
        return False

    # Step 2: Populate prompt
    prompt = populate_prompt(dataset, dataset_logger)
    if not prompt:
        logger.error(f"Failed to populate prompt for: {dataset.name}")
        return False

    # Step 3: Generate PVMAP (with retry logic)
    error_feedback = None
    for attempt in range(MAX_RETRIES + 1):
        if attempt > 0:
            logger.info(f"Retry attempt {attempt}/{MAX_RETRIES}")

        success, output = generate_pvmap(dataset, prompt, dataset_logger, error_feedback, attempt)

        if not success:
            logger.error(f"PVMAP generation failed: {output}")
            if attempt < MAX_RETRIES:
                error_feedback = output
                continue
            else:
                logger.error(f"Max retries exceeded for: {dataset.name}")
                return False

        # Step 4: Automated validation
        valid, error = run_validation(dataset, dataset_logger)

        if valid:
            logger.info(f"Dataset completed successfully: {dataset.name}")
            return True
        else:
            # Retry with error feedback
            logger.warning(f"Validation failed, will retry with error feedback")
            error_feedback = error
            if attempt >= MAX_RETRIES:
                logger.error(f"Max retries exceeded for: {dataset.name}")
                return False

    return False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="PVMAP Generation & Validation Pipeline"
    )
    parser.add_argument(
        '--dataset',
        type=str,
        help='Process specific dataset (partial name match)'
    )
    parser.add_argument(
        '--resume-from',
        type=str,
        help='Resume from specific dataset (skip earlier ones)'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without executing'
    )

    args = parser.parse_args()

    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger, log_file = setup_logging(timestamp)

    logger.info("=" * 70)
    logger.info("PVMAP Generation & Validation Pipeline")
    logger.info(f"Started: {datetime.now().isoformat()}")
    logger.info(f"Log file: {log_file}")
    logger.info("=" * 70)

    # Discover datasets
    datasets = discover_datasets(INPUT_DIR)
    logger.info(f"Discovered {len(datasets)} datasets")

    # Filter datasets if needed
    if args.dataset:
        datasets = [d for d in datasets if args.dataset.lower() in d.name.lower()]
        logger.info(f"Filtered to {len(datasets)} datasets matching '{args.dataset}'")

    if args.resume_from:
        resume_idx = None
        for i, d in enumerate(datasets):
            if args.resume_from.lower() in d.name.lower():
                resume_idx = i
                break
        if resume_idx is not None:
            datasets = datasets[resume_idx:]
            logger.info(f"Resuming from dataset {resume_idx + 1}")
        else:
            logger.warning(f"Could not find dataset matching '{args.resume_from}'")

    # Process datasets
    results = {
        'processed': 0,
        'successful': 0,
        'failed': 0,
        'skipped': 0
    }

    for dataset in datasets:
        # Setup per-dataset logging
        dataset_logger = setup_dataset_logging(dataset.name, timestamp)

        try:
            success = process_dataset(
                dataset, logger, dataset_logger, dry_run=args.dry_run
            )

            results['processed'] += 1
            if success:
                results['successful'] += 1
            else:
                results['failed'] += 1

        except KeyboardInterrupt:
            logger.info("\nPipeline interrupted by user")
            break
        except Exception as e:
            logger.error(f"Error processing {dataset.name}: {e}")
            results['failed'] += 1

    # Summary
    logger.info("\n" + "=" * 70)
    logger.info("Pipeline Summary")
    logger.info("=" * 70)
    logger.info(f"Total datasets: {len(datasets)}")
    logger.info(f"Processed: {results['processed']}")
    logger.info(f"Successful: {results['successful']}")
    logger.info(f"Failed: {results['failed']}")
    logger.info(f"Completed: {datetime.now().isoformat()}")
    logger.info(f"Log file: {log_file}")

    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())