"""
Helper functions for PVMAP generation.

These are simple Python functions (not agents) used by PVMAPGenerationAgent.
"""

import re
from pathlib import Path
from typing import Optional


def read_file_content(file_path: Path) -> str:
    """Read file content as string."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def build_prompt_with_feedback(
    template_path: Path,
    schema_content: Optional[str],
    sampled_data_content: str,
    metadata_content: str,
    error_feedback: Optional[str] = None
) -> str:
    """
    Build PVMAP generation prompt by populating template.

    Args:
        template_path: Path to improved_pvmap_prompt.txt template
        schema_content: Schema examples content (or None if not available)
        sampled_data_content: Sampled data CSV content
        metadata_content: Metadata config content
        error_feedback: Optional error feedback from previous attempt

    Returns:
        Populated prompt string

    Raises:
        FileNotFoundError: If template file doesn't exist
        ValueError: If required content is missing
    """
    if not template_path.exists():
        raise FileNotFoundError(f"Prompt template not found: {template_path}")

    if not sampled_data_content:
        raise ValueError("Sampled data content is required")

    if not metadata_content:
        raise ValueError("Metadata content is required")

    # Read template
    template = read_file_content(template_path)

    # Handle missing schema examples
    if not schema_content:
        schema_content = (
            "No schema example files found for this dataset category. "
            "Please generate the PVMAP based on the data structure and metadata "
            "provided below, using your knowledge of Data Commons schema conventions."
        )

    # Replace placeholders
    prompt = template.replace("{{SCHEMA_EXAMPLES}}", schema_content)
    prompt = prompt.replace("{{SAMPLED_DATA}}", sampled_data_content)
    prompt = prompt.replace("{{METADATA_CONFIG}}", metadata_content)

    # Add error feedback if retrying
    if error_feedback:
        prompt = (
            f"{prompt}\n\n"
            f"---\n\n"
            f"# PREVIOUS ERROR - PLEASE FIX\n\n"
            f"The previous PVMAP generation had errors during validation:\n\n"
            f"```\n{error_feedback}\n```\n\n"
            f"Please fix the PVMAP to address these errors."
        )

    return prompt


def extract_csv(output: str) -> Optional[str]:
    """
    Extract PVMAP CSV from LLM output.

    Handles multiple formats:
    - CSV in code blocks (```csv or ```)
    - Inline CSV without markers
    - Passthrough format (observationAbout header)
    - Comment lines starting with #
    - Empty lines within CSV

    Args:
        output: Full LLM response text

    Returns:
        Extracted CSV content as string, or None if not found
    """
    # First try: look for CSV in code blocks (most reliable)
    # Match CSV blocks starting with 'key' header OR passthrough format (observationAbout)
    code_block_pattern = r'```(?:csv)?\s*\n((?:key|observationAbout)[^\n]*\n.*?)```'
    matches = re.findall(code_block_pattern, output, re.DOTALL)

    if matches:
        # Take the longest match (most complete CSV)
        csv_content = max(matches, key=len).strip()

        # Normalize passthrough format by adding key header if missing
        if csv_content.startswith('observationAbout,observationAbout'):
            csv_content = 'key,property,value\n' + csv_content

        return csv_content

    # Second try: look for CSV without code block markers
    lines = output.split('\n')
    csv_lines = []
    in_csv = False
    consecutive_empty = 0

    for line in lines:
        stripped = line.strip()

        # Start of CSV (header row)
        if stripped.startswith('key,') or stripped == 'key':
            in_csv = True
            csv_lines = [stripped]
            consecutive_empty = 0
            continue

        # Also recognize passthrough format (pre-formatted data)
        if stripped.startswith('observationAbout,observationAbout'):
            in_csv = True
            # Prepend standard header for consistency
            csv_lines = ['key,property,value', stripped]
            consecutive_empty = 0
            continue

        if in_csv:
            # Comment lines are valid in PVMAP - include them
            if stripped.startswith('#'):
                csv_lines.append(stripped)
                consecutive_empty = 0
                continue

            # End of CSV: code block marker
            if stripped.startswith('```'):
                break

            # Track empty lines - 2+ consecutive empty lines likely means end of CSV
            if not stripped:
                consecutive_empty += 1
                if consecutive_empty >= 2:
                    break
                # Include single empty lines (might be intentional spacing)
                csv_lines.append('')
                continue

            # Regular data line
            consecutive_empty = 0
            csv_lines.append(stripped)

    if csv_lines:
        # Remove trailing empty lines
        while csv_lines and not csv_lines[-1]:
            csv_lines.pop()

        csv_content = '\n'.join(csv_lines)
        return csv_content

    # Could not find CSV
    return None
