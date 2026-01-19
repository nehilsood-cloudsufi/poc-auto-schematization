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

import os
import sys
from pathlib import Path

# Load environment variables FIRST before any other imports
from dotenv import load_dotenv

# Constants - set BASE_DIR first
BASE_DIR = Path(__file__).parent.resolve()

# Load .env file at module level
load_dotenv(BASE_DIR / ".env")

# Add paths from PYTHONPATH to sys.path for imports
pythonpath = os.getenv('PYTHONPATH', '')
if pythonpath:
    for path in pythonpath.split(':'):
        if path and path not in sys.path:
            sys.path.insert(0, path)

# Now import everything else
import argparse
import csv
import glob
import logging
import random
import subprocess
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# Import data sampler for Phase 2 integration
from tools.data_sampler import sample_csv_file as data_sample_csv_file

# Import schema selector for Phase 2.5 integration
from tools import schema_selector
INPUT_DIR = BASE_DIR / "input"
OUTPUT_DIR = BASE_DIR / "output"
TOOLS_DIR = BASE_DIR / "tools"
LOGS_DIR = BASE_DIR / "logs"
SCHEMA_BASE_DIR = BASE_DIR / "schema_example_files"
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
        self.schema_mcf: Optional[Path] = None
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

        # Find schema MCF files
        schema_mcf_files = list(dataset_path.glob("scripts_statvar_llm_config_vertical_*.mcf"))
        if schema_mcf_files:
            dataset.schema_mcf = schema_mcf_files[0]

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


def prepare_dataset(
    dataset: DatasetInfo,
    logger: logging.Logger,
    skip_sampling: bool = False,
    force_resample: bool = False,
    skip_schema_selection: bool = False,
    force_schema_selection: bool = False,
    schema_base_dir: Path = None
) -> bool:
    """Prepare dataset by combining/merging files as needed (integrates Phase 2 sampling and Phase 2.5 schema selection)."""
    logger.info(f"Preparing dataset: {dataset.name}")

    # Create output directory
    dataset.output_dir.mkdir(parents=True, exist_ok=True)

    # [PHASE 2 INTEGRATION] Sample data if needed
    if not skip_sampling:
        if not sample_dataset_files(dataset, logger, force_resample):
            logger.error(f"Failed to sample data for {dataset.name}")
            return False

    # [PHASE 2.5 INTEGRATION] Select and copy schema files
    if not skip_schema_selection:
        if schema_base_dir is None:
            schema_base_dir = SCHEMA_BASE_DIR
        if not select_schema_for_dataset(dataset, logger, schema_base_dir, force_schema_selection):
            logger.error(f"Failed to select schema for {dataset.name}")
            return False

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


def sample_dataset_files(
    dataset: DatasetInfo,
    logger: logging.Logger,
    force_resample: bool = False
) -> bool:
    """Sample input data files if needed (Phase 2 integration).

    Args:
        dataset: DatasetInfo object
        logger: Logger instance
        force_resample: If True, resample even if files exist

    Returns:
        True if sampling successful or skipped, False if error
    """
    # Check if sampled files already exist
    existing_sampled = list(dataset.test_data_path.glob("*_sampled_data.csv"))
    existing_sampled = [f for f in existing_sampled if not f.name.startswith("combined_")]

    if existing_sampled and not force_resample:
        logger.info(f"Using existing sampled data: {[f.name for f in existing_sampled]}")
        dataset.sampled_data_files = existing_sampled
        return True

    if not dataset.input_data_files:
        logger.warning(f"No input data files found for sampling in {dataset.name}")
        return False

    # Sample each input file
    logger.info(f"Sampling {len(dataset.input_data_files)} input file(s)...")
    sampled_files = []

    # Default sampler configuration (matching README Phase 2)
    sampler_config = {
        'sampler_output_rows': 100,
        'sampler_rows_per_key': 5,
        'sampler_categorical_threshold': 0.1,
        'sampler_max_aggregation_rows': 2,
        'sampler_ensure_coverage': True,
        'sampler_smart_columns': True,
        'sampler_detect_aggregation': True,
        'sampler_auto_detect_categorical': True,
    }

    for input_file in dataset.input_data_files:
        try:
            # Generate output path: {input_basename}_sampled_data.csv
            output_name = f"{input_file.stem}_sampled_data.csv"
            output_path = dataset.test_data_path / output_name

            logger.info(f"  Sampling {input_file.name} → {output_name}")

            # Call data sampler
            result = data_sample_csv_file(
                input_file=str(input_file),
                output_file=str(output_path),
                config=sampler_config
            )

            if result and Path(result).exists():
                sampled_files.append(Path(result))
                logger.info(f"  ✓ Sampled {input_file.name} ({Path(result).stat().st_size} bytes)")
            else:
                logger.error(f"  ✗ Failed to sample {input_file.name}")
                return False

        except Exception as e:
            logger.error(f"  ✗ Error sampling {input_file.name}: {e}")
            return False

    dataset.sampled_data_files = sampled_files
    logger.info(f"Successfully sampled {len(sampled_files)} file(s)")
    return True


def select_schema_for_dataset(
    dataset: DatasetInfo,
    logger: logging.Logger,
    schema_base_dir: Path,
    force: bool = False
) -> bool:
    """
    Select and copy appropriate schema files for a dataset.

    Args:
        dataset: DatasetInfo object with dataset details
        logger: Logger instance for tracking progress
        schema_base_dir: Path to schema_example_files directory
        force: If True, re-select schema even if files exist

    Returns:
        bool: True if successful or skipped, False if error
    """
    logger.info(f"Phase 2.5: Selecting schema for {dataset.name}...")

    # Check if schema files already exist
    has_schema, existing_files = schema_selector.check_schema_files_exist(dataset.path)
    if has_schema:
        if not force:
            logger.info(f"  ✓ Schema files already exist (use --force-schema-selection to re-select)")
            return True
        else:
            # Clean up existing schema files before re-selection
            logger.info(f"  Removing {len(existing_files)} existing schema file(s) for re-selection...")
            for old_file in existing_files:
                try:
                    old_file.unlink()
                    logger.debug(f"    Removed: {old_file.name}")
                except Exception as e:
                    logger.warning(f"    Could not remove {old_file.name}: {e}")

    # Validate schema base directory
    if not schema_base_dir.exists():
        logger.error(f"  ✗ Schema base directory not found: {schema_base_dir}")
        return False

    # Validate input directory and get metadata files
    try:
        success, error_msg, metadata_files = schema_selector.validate_input_directory(dataset.path)
        if not success:
            logger.error(f"  ✗ Directory validation failed: {error_msg}")
            return False
    except ValueError as e:
        logger.error(f"  ✗ Directory validation failed: {e}")
        return False

    # Merge metadata files if multiple
    combined_metadata_path = None
    try:
        if len(metadata_files) > 1:
            logger.info(f"  Found {len(metadata_files)} metadata files, merging...")
            combined_metadata_path = dataset.path / "combined_metadata_temp.csv"
            schema_selector.merge_metadata_files(metadata_files, combined_metadata_path)
            metadata_file = combined_metadata_path
        else:
            metadata_file = metadata_files[0]
    except Exception as e:
        logger.error(f"  ✗ Failed to merge metadata files: {e}")
        return False

    # Generate data preview
    try:
        logger.info("  Generating data preview from sampled data...")
        data_preview = schema_selector.generate_data_preview(dataset.path, max_rows=15)
    except Exception as e:
        logger.error(f"  ✗ Failed to generate data preview: {e}")
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        return False

    # Get category information
    category_info = schema_selector.get_category_info()
    if not category_info:
        logger.error(f"  ✗ No schema categories found")
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        return False

    # Generate schema previews
    try:
        schema_previews = schema_selector.generate_schema_previews(schema_base_dir)
    except Exception as e:
        logger.error(f"  ✗ Failed to generate schema previews: {e}")
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        return False

    # Read metadata content
    try:
        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata_content = f.read()
    except Exception as e:
        logger.error(f"  ✗ Failed to read metadata file: {e}")
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        return False

    # Build Claude prompt
    prompt = schema_selector.build_claude_prompt(
        metadata_content,
        data_preview,
        category_info,
        schema_previews
    )

    # Invoke Claude CLI
    try:
        logger.info("  Invoking Claude CLI to select schema category...")
        success, result = schema_selector.invoke_claude_cli(prompt)

        if not success:
            logger.error(f"  ✗ Failed to select schema category: {result}")
            if combined_metadata_path and combined_metadata_path.exists():
                combined_metadata_path.unlink()
            return False

        selected_category = result
        logger.info(f"  ✓ Selected schema category: {selected_category}")
    except Exception as e:
        logger.error(f"  ✗ Claude CLI invocation failed: {e}")
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        return False

    # Copy schema files
    try:
        success, copied_files = schema_selector.copy_schema_files(
            selected_category,    # arg 1: category
            schema_base_dir,      # arg 2: schema_base_dir
            dataset.path,         # arg 3: input_dir
            dry_run=False         # arg 4: dry_run
        )

        if not success:
            logger.error(f"  ✗ Failed to copy schema files for category: {selected_category}")
            if combined_metadata_path and combined_metadata_path.exists():
                combined_metadata_path.unlink()
            return False

        if copied_files:
            logger.info(f"  ✓ Successfully copied {len(copied_files)} schema file(s):")
            for file in copied_files:
                logger.info(f"    - {file.name}")
        else:
            logger.warning(f"  ⚠ No schema files were copied for category: {selected_category}")
    except Exception as e:
        logger.error(f"  ✗ Failed to copy schema files: {e}")
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        return False
    finally:
        # Clean up temporary combined metadata file
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
            logger.debug("  Cleaned up temporary metadata file")

    logger.info(f"✓ Phase 2.5: Schema selection completed for {dataset.name}")
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


def is_pvmap_filename(filename: str) -> bool:
    """Check if filename appears to be a PVMAP file.

    Args:
        filename: Name of file to check

    Returns:
        True if filename matches PVMAP pattern
    """
    f_lower = filename.lower()
    return (
        f_lower.endswith('.csv') and
        ('pvmap' in f_lower or 'pv_map' in f_lower or 'pv-map' in f_lower)
    )


def find_ground_truth_pvmap(
    dataset_name: str,
    source_repo: Optional[Path] = None,
    explicit_pvmap: Optional[Path] = None,
    search_dir: Optional[Path] = None
) -> Optional[Path]:
    """Find ground truth PVMAP with three-tier precedence.

    Args:
        dataset_name: Name of dataset (e.g., 'bis_bis_central_bank_policy_rate')
        source_repo: Path to datacommonsorg-data repo (auto-discovery)
        explicit_pvmap: Path to explicit PVMAP file (highest precedence)
        search_dir: Path to directory to search for PVMAP (medium precedence)

    Returns:
        Path to ground truth PVMAP if found, None otherwise

    Precedence:
        1. explicit_pvmap (if provided and exists)
        2. search_dir (if provided, search by dataset name)
        3. source_repo (existing auto-discovery logic)
    """
    # Tier 1: Explicit single file (highest precedence)
    if explicit_pvmap:
        if explicit_pvmap.exists():
            return explicit_pvmap
        else:
            return None

    # Tier 2: Directory search (medium precedence)
    if search_dir:
        if not search_dir.exists():
            return None

        # Search strategy:
        # 1. Direct file search: Look for *{dataset_name}*pvmap*.csv
        # 2. Subdirectory search: Look for subdirs matching dataset name, then pvmap files

        # Direct file search in directory
        pvmap_candidates = []
        for file in search_dir.iterdir():
            if file.is_file() and is_pvmap_filename(file.name):
                # Check if filename contains dataset name (partial match)
                if dataset_name.lower() in file.name.lower():
                    pvmap_candidates.append(file)

        if pvmap_candidates:
            # Prefer exact match, then shortest name
            pvmap_candidates.sort(key=lambda f: (
                dataset_name.lower() not in f.stem.lower(),  # Exact match first
                len(f.name)  # Then shortest
            ))
            return pvmap_candidates[0]

        # Subdirectory search (1 level deep)
        for subdir in search_dir.iterdir():
            if subdir.is_dir() and dataset_name.lower() in subdir.name.lower():
                # Look for pvmap files in this subdirectory
                for file in subdir.iterdir():
                    if file.is_file() and is_pvmap_filename(file.name):
                        return file

        return None

    # Tier 3: Auto-discovery (lowest precedence)
    if not source_repo or not source_repo.exists():
        return None

    # Strategy 1: Flat directory structure (e.g., ground_truth/{dataset}/*_pvmap.csv)
    # Look for subdirectory matching dataset name
    for subdir in source_repo.iterdir():
        if subdir.is_dir() and dataset_name.lower() in subdir.name.lower():
            # Look for pvmap files in this subdirectory
            for file in subdir.iterdir():
                if file.is_file() and is_pvmap_filename(file.name):
                    return file

    # Strategy 2: Nested structure with statvar_imports (e.g., repo/statvar_imports/{category}/{dataset}/*_pvmap.csv)
    statvar_imports = source_repo / "statvar_imports"
    if statvar_imports.exists():
        # Extract category from dataset name (e.g., 'bis' from 'bis_bis_central_bank_policy_rate')
        parts = dataset_name.split('_')

        # Strategy 2a: Direct folder match
        if parts:
            category_path = statvar_imports / parts[0]
            if category_path.exists():
                for potential_folder in category_path.iterdir():
                    if potential_folder.is_dir():
                        pvmap_files = list(potential_folder.glob("*_pvmap.csv"))
                        if pvmap_files and dataset_name.lower() in potential_folder.name.lower():
                            return pvmap_files[0]

        # Strategy 2b: Substring match across all categories
        for category_folder in statvar_imports.iterdir():
            if not category_folder.is_dir():
                continue
            for dataset_folder in category_folder.iterdir():
                if not dataset_folder.is_dir():
                    continue
                # Check if dataset name matches folder
                if dataset_name.lower() in dataset_folder.name.lower():
                    pvmap_files = list(dataset_folder.glob("*_pvmap.csv"))
                    if pvmap_files:
                        return pvmap_files[0]

    return None


def evaluate_generated_pvmap(
    dataset: DatasetInfo,
    logger: logging.Logger,
    source_repo: Optional[Path] = None,
    skip_eval: bool = False,
    explicit_pvmap: Optional[Path] = None,
    search_dir: Optional[Path] = None
) -> Tuple[bool, Optional[Dict]]:
    """Evaluate generated PVMAP against ground truth (Phase 5 integration).

    Args:
        dataset: DatasetInfo object
        logger: Logger instance
        source_repo: Path to datacommonsorg-data repo (auto-discovery)
        skip_eval: If True, skip evaluation
        explicit_pvmap: Path to explicit ground truth PVMAP file
        search_dir: Path to directory to search for ground truth PVMAP

    Returns:
        Tuple of (success, metrics_dict or None)
    """
    if skip_eval:
        logger.info("Evaluation skipped (--skip-evaluation)")
        return True, None

    if not dataset.pvmap_path.exists():
        logger.warning("Generated PVMAP not found, skipping evaluation")
        return True, None

    try:
        # Find ground truth with new precedence logic
        gt_pvmap_path = find_ground_truth_pvmap(
            dataset.name,
            source_repo=source_repo,
            explicit_pvmap=explicit_pvmap,
            search_dir=search_dir
        )

        if not gt_pvmap_path:
            # Enhanced logging to show which method was attempted
            if explicit_pvmap:
                logger.info(f"Explicit PVMAP not found: {explicit_pvmap}")
            elif search_dir:
                logger.info(f"Ground truth PVMAP not found in directory: {search_dir}")
            else:
                logger.info(f"Ground truth PVMAP not found in repo for {dataset.name}")
            logger.info("Skipping evaluation")
            return True, None

        logger.info(f"Found ground truth: {gt_pvmap_path.name}")
        logger.info(f"  Source: {gt_pvmap_path.parent}")

        # Lazy import evaluation function
        try:
            from evaluate_pvmap_diff import compare_pvmaps_diff
        except ImportError:
            logger.warning("evaluate_pvmap_diff module not available, skipping evaluation")
            return True, None

        # Create evaluation output directory
        eval_dir = dataset.output_dir / "eval_results"
        eval_dir.mkdir(parents=True, exist_ok=True)

        # Run comparison
        logger.info(f"Evaluating PVMAP against ground truth...")
        counters, diff_str = compare_pvmaps_diff(
            str(dataset.pvmap_path),
            str(gt_pvmap_path),
            str(eval_dir)
        )

        # Calculate and log metrics
        nodes_gt = counters.get('nodes-ground-truth', 0)
        nodes_matched = counters.get('nodes-matched', 0)
        pvs_matched = counters.get('PVs-matched', 0)
        pvs_total = pvs_matched + counters.get('pvs-modified', 0) + counters.get('pvs-deleted', 0)

        node_accuracy = (nodes_matched / nodes_gt * 100) if nodes_gt > 0 else 0
        pv_accuracy = (pvs_matched / pvs_total * 100) if pvs_total > 0 else 0

        logger.info(f"Evaluation complete: Node Acc={node_accuracy:.1f}%, PV Acc={pv_accuracy:.1f}%")

        # Return metrics for aggregate reporting
        return True, {
            'node_accuracy': node_accuracy,
            'pv_accuracy': pv_accuracy,
            'nodes_matched': nodes_matched,
            'nodes_ground_truth': nodes_gt,
            'pvs_matched': pvs_matched,
            'pvs_total': pvs_total
        }

    except FileNotFoundError as e:
        logger.warning(f"Evaluation failed - file not found: {e}")
        return True, None
    except Exception as e:
        logger.warning(f"Evaluation failed (non-critical): {e}")
        return True, None


def process_dataset(
    dataset: DatasetInfo,
    logger: logging.Logger,
    dataset_logger: logging.Logger,
    dry_run: bool = False,
    skip_sampling: bool = False,
    force_resample: bool = False,
    skip_schema_selection: bool = False,
    force_schema_selection: bool = False,
    schema_base_dir: Optional[Path] = None,
    skip_evaluation: bool = False,
    ground_truth_repo: Optional[Path] = None,
    ground_truth_pvmap: Optional[Path] = None,
    ground_truth_dir: Optional[Path] = None
) -> Tuple[bool, Optional[Dict]]:
    """Process a single dataset through the full pipeline (integrates Phase 2, 2.5 & 5).

    Returns:
        Tuple of (success, eval_metrics_dict or None)
    """
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
        return True, None

    # Step 1: Prepare dataset (combine/merge files, includes Phase 2 sampling & Phase 2.5 schema selection)
    if not prepare_dataset(
        dataset,
        dataset_logger,
        skip_sampling,
        force_resample,
        skip_schema_selection,
        force_schema_selection,
        schema_base_dir or SCHEMA_BASE_DIR
    ):
        logger.error(f"Failed to prepare dataset: {dataset.name}")
        return False, None

    # Step 2: Populate prompt
    prompt = populate_prompt(dataset, dataset_logger)
    if not prompt:
        logger.error(f"Failed to populate prompt for: {dataset.name}")
        return False, None

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
                return False, None

        # Step 4: Automated validation
        valid, error = run_validation(dataset, dataset_logger)

        if valid:
            # [PHASE 5 INTEGRATION] Evaluate against ground truth
            eval_success, eval_metrics = evaluate_generated_pvmap(
                dataset,
                dataset_logger,
                source_repo=ground_truth_repo,
                skip_eval=skip_evaluation,
                explicit_pvmap=ground_truth_pvmap,
                search_dir=ground_truth_dir
            )

            logger.info(f"Dataset completed successfully: {dataset.name}")
            return True, eval_metrics
        else:
            # Retry with error feedback
            logger.warning(f"Validation failed, will retry with error feedback")
            error_feedback = error
            if attempt >= MAX_RETRIES:
                logger.error(f"Max retries exceeded for: {dataset.name}")
                return False, None

    return False, None


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
    parser.add_argument(
        '--skip-sampling',
        action='store_true',
        help='Skip sampling phase (use existing sampled data)'
    )
    parser.add_argument(
        '--force-resample',
        action='store_true',
        help='Force re-sampling even if sampled data exists'
    )
    parser.add_argument(
        '--skip-schema-selection',
        action='store_true',
        help='Skip schema selection phase (use existing schema files)'
    )
    parser.add_argument(
        '--force-schema-selection',
        action='store_true',
        help='Force re-selection of schema files even if they exist'
    )
    parser.add_argument(
        '--schema-base-dir',
        type=str,
        default=str(BASE_DIR / "schema_example_files"),
        help='Path to schema files directory (default: schema_example_files/)'
    )
    parser.add_argument(
        '--skip-evaluation',
        action='store_true',
        help='Skip evaluation phase (Phase 5)'
    )
    parser.add_argument(
        '--ground-truth-repo',
        type=str,
        default=os.environ.get('GROUND_TRUTH_REPO', str(BASE_DIR.parent / "datacommonsorg-data" / "ground_truth")),
        help='Path to datacommonsorg-data repo for ground truth PVMAPs (default: $GROUND_TRUTH_REPO or ../datacommonsorg-data/ground_truth)'
    )
    parser.add_argument(
        '--ground-truth-pvmap',
        type=str,
        help='Path to a single ground truth PVMAP file (takes precedence over --ground-truth-dir and --ground-truth-repo)'
    )
    parser.add_argument(
        '--ground-truth-dir',
        type=str,
        help='Path to directory containing ground truth PVMAP files (searched by dataset name, takes precedence over --ground-truth-repo)'
    )
    parser.add_argument(
        '--input-dir',
        type=str,
        default='input',
        help='Input directory containing datasets (default: input/)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default='output',
        help='Output directory for generated PVMAPs (default: output/)'
    )

    args = parser.parse_args()

    # Override INPUT_DIR and OUTPUT_DIR from command-line arguments
    global INPUT_DIR, OUTPUT_DIR
    INPUT_DIR = BASE_DIR / args.input_dir
    OUTPUT_DIR = BASE_DIR / args.output_dir

    # Setup logging
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger, log_file = setup_logging(timestamp)

    # Validate contradictory flag combinations
    if args.skip_schema_selection and args.force_schema_selection:
        logger.warning(
            "--skip-schema-selection and --force-schema-selection are contradictory. "
            "--skip-schema-selection takes precedence."
        )
    if args.skip_sampling and args.force_resample:
        logger.warning(
            "--skip-sampling and --force-resample are contradictory. "
            "--skip-sampling takes precedence."
        )

    # Convert ground truth paths
    ground_truth_pvmap_path = Path(args.ground_truth_pvmap) if args.ground_truth_pvmap else None
    ground_truth_dir_path = Path(args.ground_truth_dir) if args.ground_truth_dir else None

    # Validate paths exist
    if ground_truth_pvmap_path and not ground_truth_pvmap_path.exists():
        logger.error(f"Ground truth PVMAP file not found: {ground_truth_pvmap_path}")
        sys.exit(1)

    if ground_truth_dir_path and not ground_truth_dir_path.exists():
        logger.error(f"Ground truth directory not found: {ground_truth_dir_path}")
        sys.exit(1)

    # Warn about conflicting arguments
    if ground_truth_pvmap_path and ground_truth_dir_path:
        logger.warning(
            "Both --ground-truth-pvmap and --ground-truth-dir provided. "
            "--ground-truth-pvmap takes precedence."
        )

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

    # Warn about single file with multiple datasets
    if ground_truth_pvmap_path and not args.dataset and len(datasets) > 1:
        logger.warning(
            f"--ground-truth-pvmap provided with {len(datasets)} datasets. "
            f"The single file will only be used for the first dataset. "
            f"Evaluation will be skipped for remaining datasets."
        )

    # Process datasets
    results = {
        'processed': 0,
        'successful': 0,
        'failed': 0,
        'skipped': 0,
        'evaluated': 0
    }

    # Track evaluation metrics for aggregate reporting
    eval_metrics_list = []
    ground_truth_repo_path = Path(args.ground_truth_repo) if args.ground_truth_repo else None

    # Determine schema base directory
    schema_base_dir_path = Path(args.schema_base_dir) if args.schema_base_dir else SCHEMA_BASE_DIR
    if not schema_base_dir_path.exists():
        logger.warning(f"Schema base directory not found: {schema_base_dir_path}")
        logger.warning("Schema selection may fail for some datasets")

    # Track if explicit pvmap has been used
    explicit_pvmap_used = False

    for dataset in datasets:
        # Setup per-dataset logging
        dataset_logger = setup_dataset_logging(dataset.name, timestamp)

        # Handle single-file-multiple-datasets scenario
        current_ground_truth_pvmap = None
        current_ground_truth_dir = ground_truth_dir_path

        if ground_truth_pvmap_path:
            if not explicit_pvmap_used:
                # First dataset: use the explicit file
                current_ground_truth_pvmap = ground_truth_pvmap_path
                explicit_pvmap_used = True
                logger.info(
                    f"Using explicit ground truth PVMAP for {dataset.name}: "
                    f"{ground_truth_pvmap_path.name}"
                )
            else:
                # Subsequent datasets: skip evaluation by passing None
                logger.info(
                    f"Skipping evaluation for {dataset.name} "
                    f"(explicit PVMAP already used for first dataset)"
                )
                current_ground_truth_pvmap = None
                current_ground_truth_dir = None
                # Note: ground_truth_repo will still be passed, but won't be used
                # since we're explicitly setting the other params to None

        try:
            # Determine ground_truth_repo: pass None if we're using explicit file or dir
            # (or if subsequent dataset after explicit file was used)
            current_ground_truth_repo = ground_truth_repo_path
            if ground_truth_pvmap_path or ground_truth_dir_path:
                current_ground_truth_repo = None

            success, eval_metrics = process_dataset(
                dataset,
                logger,
                dataset_logger,
                dry_run=args.dry_run,
                skip_sampling=args.skip_sampling,
                force_resample=args.force_resample,
                skip_schema_selection=args.skip_schema_selection,
                force_schema_selection=args.force_schema_selection,
                schema_base_dir=schema_base_dir_path,
                skip_evaluation=args.skip_evaluation,
                ground_truth_repo=current_ground_truth_repo,
                ground_truth_pvmap=current_ground_truth_pvmap,
                ground_truth_dir=current_ground_truth_dir
            )

            results['processed'] += 1
            if success:
                results['successful'] += 1
                if eval_metrics:
                    results['evaluated'] += 1
                    eval_metrics_list.append(eval_metrics)
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

    # Add evaluation metrics summary (Phase 5 integration)
    if eval_metrics_list:
        avg_node_acc = sum(m['node_accuracy'] for m in eval_metrics_list) / len(eval_metrics_list)
        avg_pv_acc = sum(m['pv_accuracy'] for m in eval_metrics_list) / len(eval_metrics_list)
        logger.info(f"\nEvaluation Metrics:")
        logger.info(f"  Evaluated: {results['evaluated']}/{results['processed']} datasets")
        logger.info(f"  Avg Node Accuracy: {avg_node_acc:.1f}%")
        logger.info(f"  Avg PV Accuracy: {avg_pv_acc:.1f}%")
    elif not args.skip_evaluation:
        logger.info(f"\nEvaluation: 0 datasets evaluated (no ground truth found)")

    logger.info(f"\nCompleted: {datetime.now().isoformat()}")
    logger.info(f"Log file: {log_file}")

    return 0 if results['failed'] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())