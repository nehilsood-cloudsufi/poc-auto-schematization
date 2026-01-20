#!/usr/bin/env python3
"""
Schema Selector Tool

Automatically selects the most appropriate schema category for a dataset using
Gemini API, then copies the corresponding schema files to the input directory.

Usage:
    python tools/schema_selector.py --input_dir=input/dataset_name/
    python tools/schema_selector.py --input_dir=input/dataset_name/ --dry_run
    python tools/schema_selector.py --input_dir=input/dataset_name/ --force
"""

import csv
import io
import shutil
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Add project root to path for util imports
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from util.gemini_client import GeminiClient

from absl import app
from absl import flags
from absl import logging

# Command-line flags
flags.DEFINE_string('input_dir', None,
                    'Path to input directory (e.g., input/dataset_name/). Required.')
flags.DEFINE_string('schema_base_dir', None,
                    'Path to schema files directory (default: schema_example_files/).')
flags.DEFINE_boolean('force', False,
                     'Force re-selection even if schema files already exist.')
flags.DEFINE_boolean('dry_run', False,
                     'Show what would be done without actually copying files.')
flags.DEFINE_integer('preview_rows', 15,
                     'Number of data rows to include in preview for Claude.')

flags.mark_flag_as_required('input_dir')

FLAGS = flags.FLAGS

# Constants
SCHEMA_CATEGORIES = ['Demographics', 'Economy', 'Education', 'Employment',
                     'Energy', 'Health', 'School']
BASE_DIR = Path(__file__).parent.parent.resolve()
DEFAULT_SCHEMA_DIR = BASE_DIR / "schema_example_files"


def merge_metadata_files(files: List[Path], output_path: Path) -> bool:
    """Merge multiple metadata config files into one.

    Args:
        files: List of metadata file paths to merge
        output_path: Path where merged metadata should be written

    Returns:
        True if merge successful, False otherwise
    """
    if not files:
        return False

    if len(files) == 1:
        shutil.copy(files[0], output_path)
        logging.debug(f"Copied single metadata: {files[0].name}")
        return True

    logging.info(f"Merging {len(files)} metadata files into {output_path.name}")

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
                            logging.warning(
                                f"Conflicting value for '{param}': "
                                f"'{merged_params[param]}' vs '{value}'"
                            )

        with open(output_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            for param, value in merged_params.items():
                writer.writerow([param, value])

        logging.debug(f"Merged {len(merged_params)} parameters")
        return True

    except Exception as e:
        logging.error(f"Error merging metadata: {e}")
        return False


def validate_input_directory(input_dir: Path) -> Tuple[bool, Optional[str], List[Path]]:
    """Validate input directory structure.

    Args:
        input_dir: Path to the input directory

    Returns:
        Tuple of (success, error_message, metadata_file_paths)
        If success is False, error_message contains the reason
        If success is True, metadata_file_paths contains list of metadata files
    """
    # Check if directory exists
    if not input_dir.exists():
        return False, f"Directory does not exist: {input_dir}", []

    if not input_dir.is_dir():
        return False, f"Path is not a directory: {input_dir}", []

    # Find metadata files (multiple patterns)
    # Pattern 1: *_metadata.csv (most common)
    metadata_files = list(input_dir.glob("*_metadata.csv"))

    # Pattern 2: metadata.csv (simple name)
    if len(metadata_files) == 0:
        metadata_csv = input_dir / "metadata.csv"
        if metadata_csv.exists():
            metadata_files = [metadata_csv]

    # Pattern 3: *metadata*.csv (like Estimatedmetadata.csv)
    if len(metadata_files) == 0:
        metadata_files = [f for f in input_dir.glob("*metadata*.csv")]

    if len(metadata_files) == 0:
        return False, f"No metadata file found in {input_dir}", []

    # Return all metadata files found (no longer error on multiple)

    # Log if multiple metadata files found
    if len(metadata_files) > 1:
        file_list = ", ".join(f.name for f in metadata_files)
        logging.info(f"Found {len(metadata_files)} metadata files: {file_list}")

    # Check for test_data directory
    test_data_dir = input_dir / "test_data"
    if not test_data_dir.exists():
        logging.warning(f"test_data directory not found in {input_dir}")
    else:
        # Check for data files
        sampled_files = list(test_data_dir.glob("*_sampled_data.csv"))
        input_files = list(test_data_dir.glob("*_input.csv"))

        if not sampled_files and not input_files:
            logging.warning(f"No CSV data files found in {test_data_dir}")

    return True, None, metadata_files


def check_schema_files_exist(input_dir: Path) -> Tuple[bool, List[Path]]:
    """Check if schema files already exist in the input directory.

    Args:
        input_dir: Path to the input directory

    Returns:
        Tuple of (files_exist, list_of_files)
    """
    existing_files = []

    # Check for TXT schema examples
    txt_files = list(input_dir.glob("scripts_statvar_llm_config_schema_examples_*.txt"))
    existing_files.extend(txt_files)

    return len(existing_files) > 0, existing_files


def get_category_info() -> Dict[str, str]:
    """Get descriptions for each schema category.

    Returns:
        Dictionary mapping category names to descriptions
    """
    return {
        'Demographics': 'Population, age, gender, race, household, nativity data',
        'Economy': 'GDP, business establishments, revenue, trade, commodities',
        'Education': 'School enrollment, degrees, educational attainment, literacy',
        'Employment': 'Labor force, jobs, wages, unemployment, occupations (BLS data)',
        'Energy': 'Power generation, consumption, renewable energy, infrastructure',
        'Health': 'Disease prevalence, mortality, healthcare access, medical conditions',
        'School': 'School-specific metrics, performance, facilities, student-teacher ratios'
    }


def generate_data_preview(input_dir: Path, max_rows: int) -> str:
    """Generate a preview of the dataset for Claude.

    Args:
        input_dir: Path to the input directory
        max_rows: Maximum number of rows to include (including header)

    Returns:
        Formatted CSV preview as string
    """
    test_data_dir = input_dir / "test_data"

    # Look for sampled data files first
    data_file = None

    if test_data_dir.exists():
        # Prefer combined_sampled_data.csv
        combined_sampled = test_data_dir / "combined_sampled_data.csv"
        if combined_sampled.exists():
            data_file = combined_sampled
        else:
            # Look for any sampled data file
            sampled_files = list(test_data_dir.glob("*_sampled_data.csv"))
            if sampled_files:
                data_file = sampled_files[0]
            else:
                # Fallback to input files
                input_files = list(test_data_dir.glob("*_input.csv"))
                if input_files:
                    data_file = input_files[0]

    if not data_file or not data_file.exists():
        return "ERROR: No data files found in test_data directory"

    try:
        # Read the file
        with open(data_file, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = []
            for i, row in enumerate(reader):
                if i >= max_rows:
                    break
                rows.append(row)

        # Format as CSV string
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerows(rows)
        csv_content = output.getvalue()

        # Add metadata
        preview = f"Showing {len(rows)} rows from {data_file.name}:\n\n{csv_content}"
        return preview

    except Exception as e:
        return f"ERROR reading data file {data_file}: {str(e)}"


def generate_schema_previews(schema_base_dir: Path, preview_lines: int = 8) -> Dict[str, str]:
    """Generate previews of each schema category's example file.

    Args:
        schema_base_dir: Path to the schema files directory
        preview_lines: Number of lines to include in each preview

    Returns:
        Dictionary mapping category names to preview text
    """
    previews = {}

    for category in SCHEMA_CATEGORIES:
        if category == 'School':
            # School category has no .txt file
            previews[category] = "Category: School\n(No .txt file - MCF only)"
            continue

        txt_file = (schema_base_dir / category /
                   f"scripts_statvar_llm_config_schema_examples_dc_topic_{category}.txt")

        if not txt_file.exists():
            previews[category] = f"Category: {category}\n(File not found: {txt_file.name})"
            continue

        try:
            with open(txt_file, 'r', encoding='utf-8') as f:
                lines = []
                for i, line in enumerate(f):
                    if i >= preview_lines:
                        break
                    lines.append(line.rstrip())

                preview_text = f"Category: {category}\n" + "\n".join(lines)
                if i >= preview_lines - 1:
                    preview_text += "\n..."

                previews[category] = preview_text
        except Exception as e:
            previews[category] = f"Category: {category}\n(Error reading file: {str(e)})"

    return previews


def build_claude_prompt(metadata_content: str, data_preview: str,
                       category_info: Dict[str, str],
                       schema_previews: Dict[str, str]) -> str:
    """Build the complete prompt for Claude.

    Args:
        metadata_content: Content of the metadata.csv file
        data_preview: Preview of the dataset
        category_info: Dictionary of category descriptions
        schema_previews: Dictionary of schema file previews

    Returns:
        Complete prompt string
    """
    prompt = """You are a data schema classification expert. Analyze this dataset and select the most appropriate schema category.

## Dataset Metadata Configuration:

"""
    prompt += metadata_content
    prompt += """

## Sample Data (first 15 rows):

"""
    prompt += data_preview
    prompt += """

## Available Schema Categories:

"""

    for i, (category, description) in enumerate(category_info.items(), 1):
        prompt += f"{i}. **{category}**: {description}\n"

    prompt += """
## Schema File Previews:

"""

    for category in SCHEMA_CATEGORIES:
        prompt += f"\n### {category}\n\n"
        prompt += schema_previews.get(category, "(No preview available)")
        prompt += "\n"

    prompt += """
## Task:

Based on the metadata, data columns, and schema patterns, select ONE category that best matches this dataset.

**Important:** Respond with ONLY the category name (Demographics, Economy, Education, Employment, Energy, Health, or School). No explanation, no punctuation - just the category name.

Selected Category: """

    return prompt


def parse_category_response(response: str, valid_categories: List[str]) -> Optional[str]:
    """Parse Claude's response to extract the category name.

    Args:
        response: Raw response from Claude
        valid_categories: List of valid category names

    Returns:
        Category name (with correct capitalization) or None if invalid
    """
    # Clean the response
    response = response.strip()

    # Get the last non-empty line (in case there's explanation)
    lines = [line.strip() for line in response.split('\n') if line.strip()]
    if not lines:
        return None

    last_line = lines[-1]

    # Strip common punctuation
    last_line = last_line.rstrip('.,;:!?')

    # Try exact match (case-insensitive)
    for category in valid_categories:
        if last_line.lower() == category.lower():
            return category

    # Try fuzzy matching for common variations
    fuzzy_map = {
        'demographic': 'Demographics',
        'economics': 'Economy',
        'economic': 'Economy',
        'labor': 'Employment',
    }

    last_line_lower = last_line.lower()
    if last_line_lower in fuzzy_map:
        return fuzzy_map[last_line_lower]

    # Try substring match as last resort
    for category in valid_categories:
        if category.lower() in last_line_lower or last_line_lower in category.lower():
            return category

    return None


def invoke_gemini(prompt: str, timeout: int = 180, model_name: Optional[str] = None) -> Tuple[bool, str]:
    """Invoke Gemini API to select the schema category.

    Args:
        prompt: The complete prompt to send to Gemini
        timeout: Timeout in seconds (kept for API compatibility)
        model_name: Optional Gemini model name to use

    Returns:
        Tuple of (success, category_or_error_message)
    """
    try:
        logging.debug("Invoking Gemini API for schema selection...")

        client = GeminiClient(model_name=model_name)
        response = client.generate_content(prompt, temperature=0.0)

        # Parse response
        category = parse_category_response(response, SCHEMA_CATEGORIES)

        if category is None:
            return False, f"Could not parse valid category from response:\n{response}"

        return True, category

    except Exception as e:
        return False, f"Error invoking Gemini API: {str(e)}"


def copy_schema_files(category: str, schema_base_dir: Path,
                     input_dir: Path, dry_run: bool) -> Tuple[bool, List[Path]]:
    """Copy schema files to the input directory.

    Args:
        category: Selected schema category
        schema_base_dir: Path to schema files directory
        input_dir: Path to input directory
        dry_run: If True, only show what would be copied

    Returns:
        Tuple of (success, list_of_copied_files)
    """
    copied_files = []

    # Determine source file path for schema examples
    if category == 'School':
        # School category is empty (no schema example files)
        logging.warning(f"School category has no schema example files - continuing without schema examples")
        return True, []  # Return success with empty list to allow pipeline to continue

    txt_file = (schema_base_dir / category /
               f"scripts_statvar_llm_config_schema_examples_dc_topic_{category}.txt")

    # Validate source file exists
    if not txt_file.exists():
        logging.warning(f"Schema example file not found: {txt_file} - continuing without schema examples")
        return True, []  # Return success with empty list to allow pipeline to continue

    files_to_copy = [txt_file]

    # If dry run, just log what would be copied
    if dry_run:
        logging.info("DRY RUN - Would copy the following files:")
        for src_file in files_to_copy:
            size_kb = src_file.stat().st_size / 1024
            dest_file = input_dir / src_file.name
            logging.info(f"  {src_file.name} ({size_kb:.1f} KB) -> {dest_file}")
        return True, [input_dir / f.name for f in files_to_copy]

    # Copy files
    try:
        for src_file in files_to_copy:
            dest_file = input_dir / src_file.name
            shutil.copy2(src_file, dest_file)
            size_kb = src_file.stat().st_size / 1024
            logging.info(f"Copied: {src_file.name} ({size_kb:.1f} KB)")
            copied_files.append(dest_file)

        return True, copied_files

    except PermissionError as e:
        logging.error(f"Permission denied: {str(e)}")
        logging.error("Check file permissions and try again")
        return False, copied_files
    except OSError as e:
        logging.error(f"OS error during file copy: {str(e)}")
        return False, copied_files
    except Exception as e:
        logging.error(f"Unexpected error during file copy: {str(e)}")
        return False, copied_files


def main(argv):
    """Main function."""
    del argv  # Unused

    # Setup logging
    logging.set_verbosity(logging.INFO)

    # Get input directory
    input_dir = Path(FLAGS.input_dir).resolve()

    # Determine schema base directory
    if FLAGS.schema_base_dir:
        schema_base_dir = Path(FLAGS.schema_base_dir).resolve()
    else:
        schema_base_dir = DEFAULT_SCHEMA_DIR

    logging.info(f"Processing dataset: {input_dir.name}")

    # Step 1: Validate input directory
    success, error_msg, metadata_files = validate_input_directory(input_dir)
    if not success:
        logging.error(f"Input validation failed: {error_msg}")
        sys.exit(1)

    if len(metadata_files) == 1:
        logging.debug(f"Found metadata file: {metadata_files[0].name}")
    else:
        logging.debug(f"Found {len(metadata_files)} metadata files")

    # Step 2: Check if schema files already exist
    files_exist, existing_files = check_schema_files_exist(input_dir)
    if files_exist and not FLAGS.force:
        logging.info("Schema files already exist in the input directory:")
        for file in existing_files:
            logging.info(f"  - {file.name}")
        logging.info("Use --force to re-select and overwrite")
        sys.exit(0)

    # Step 3: Merge metadata files if multiple, or use single file
    combined_metadata_path = None
    metadata_file_to_read = None

    try:
        if len(metadata_files) > 1:
            # Create combined metadata file
            combined_metadata_path = input_dir / f"{input_dir.name}_combined_metadata.csv"
            if not merge_metadata_files(metadata_files, combined_metadata_path):
                logging.error("Failed to merge metadata files")
                sys.exit(1)
            metadata_file_to_read = combined_metadata_path
        else:
            metadata_file_to_read = metadata_files[0]

        # Step 4: Load metadata content
        with open(metadata_file_to_read, 'r', encoding='utf-8') as f:
            metadata_content = f.read()
    except Exception as e:
        logging.error(f"Error reading metadata file: {str(e)}")
        # Clean up combined metadata file if it was created
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        sys.exit(1)

    # Step 5: Generate data preview
    logging.debug("Generating data preview...")
    data_preview = generate_data_preview(input_dir, FLAGS.preview_rows)

    # Step 6: Get category information
    category_info = get_category_info()

    # Step 7: Generate schema previews
    logging.debug("Generating schema previews...")
    schema_previews = generate_schema_previews(schema_base_dir)

    # Step 8: Build Claude prompt
    prompt = build_claude_prompt(metadata_content, data_preview,
                                 category_info, schema_previews)

    # Step 9: Invoke Gemini API
    logging.info("Invoking Gemini API to select schema category...")
    success, result = invoke_gemini(prompt)

    if not success:
        logging.error(f"Gemini API invocation failed: {result}")
        logging.error("You may need to manually select the schema category")
        # Clean up combined metadata file if it was created
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        sys.exit(2)

    category = result
    logging.info(f"Selected category: {category}")

    # Step 10: Copy schema files
    if FLAGS.dry_run:
        logging.info(f"\nDRY RUN: Would copy schema files for category '{category}'")
    else:
        logging.info(f"Copying schema files for category '{category}'...")

    success, copied_files = copy_schema_files(category, schema_base_dir,
                                             input_dir, FLAGS.dry_run)

    if not success:
        logging.error("Failed to copy schema files")
        # Clean up combined metadata file if it was created
        if combined_metadata_path and combined_metadata_path.exists():
            combined_metadata_path.unlink()
        sys.exit(3)

    # Step 11: Clean up temporary combined metadata file
    if combined_metadata_path and combined_metadata_path.exists():
        combined_metadata_path.unlink()
        logging.debug(f"Cleaned up temporary file: {combined_metadata_path.name}")

    # Step 12: Success summary
    if not FLAGS.dry_run:
        logging.info(f"\nSuccess! Copied {len(copied_files)} file(s):")
        for file in copied_files:
            logging.info(f"  - {file.name}")

    sys.exit(0)


if __name__ == '__main__':
    app.run(main)
