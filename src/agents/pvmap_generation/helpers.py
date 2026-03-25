"""
Helper functions for PVMAP generation.

These are simple Python functions (not agents) used by the PVMAP generation pipeline.
"""

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from .schemas import PVMAPOutput


def read_file_content(file_path: Path) -> str:
    """Read file content as string."""
    with open(file_path, 'r', encoding='utf-8') as f:
        return f.read()


def build_prompt_with_feedback(
    template_path: Path,
    schema_content: Optional[str],
    sampled_data_content: str,
    metadata_content: str,
    error_feedback: Optional[str] = None,
    discovered_statvars: Optional[str] = None,
    data_context: Optional[str] = None
) -> str:
    """
    Build PVMAP generation prompt by populating template.

    Args:
        template_path: Path to improved_pvmap_prompt.txt template
        schema_content: Schema examples content (or None if not available)
        sampled_data_content: Sampled data CSV content
        metadata_content: Metadata config content
        error_feedback: Optional error feedback from previous attempt
        discovered_statvars: Optional discovered StatVars from MCP discovery
        data_context: Optional skeleton summary markdown from DataContext

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

    # Handle data context - provide default if not available
    if not data_context:
        data_context = (
            "_Data context analysis not available. "
            "Please analyze the sampled data below to understand the dataset structure._"
        )

    # Replace all template placeholders
    prompt = template.replace("{{DATA_CONTEXT}}", data_context)
    prompt = prompt.replace("{{SCHEMA_EXAMPLES}}", schema_content)
    prompt = prompt.replace("{{SAMPLED_DATA}}", sampled_data_content)
    prompt = prompt.replace("{{METADATA_CONFIG}}", metadata_content)
    prompt = prompt.replace("{{ERROR_FEEDBACK}}", error_feedback or "")
    prompt = prompt.replace("{{STATVAR_SUMMARY}}", discovered_statvars or "")
    prompt = prompt.replace("{{MCP_TOOLS_INSTRUCTION}}", "")

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


def save_populated_prompt(output_dir: Path, prompt: str) -> Path:
    """
    Save the populated prompt to output directory.

    Args:
        output_dir: Directory to save prompt
        prompt: The populated prompt content

    Returns:
        Path to saved prompt file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = output_dir / "populated_prompt.txt"
    with open(prompt_path, 'w', encoding='utf-8') as f:
        f.write(prompt)
    return prompt_path


def save_attempt_response(
    output_dir: Path,
    attempt: int,
    llm_result: Dict[str, Any],
    error_feedback: Optional[str] = None,
    pvmap_csv: Optional[str] = None,
    validation_result: Optional[Dict[str, Any]] = None
) -> Dict[str, Path]:
    """
    Save attempt response files (md, json, thinking.txt).

    Args:
        output_dir: Base output directory
        attempt: Attempt number (0-indexed)
        llm_result: Result dict from generate_content_with_metadata()
        error_feedback: Error feedback from previous attempt (if any)
        pvmap_csv: Extracted PVMAP CSV content (if successful)
        validation_result: Validation result dict (if available)

    Returns:
        Dict with paths to saved files
    """
    response_dir = output_dir / "generated_response"
    response_dir.mkdir(parents=True, exist_ok=True)

    saved_paths = {}

    # Save attempt_*.md (markdown with response details)
    md_path = response_dir / f"attempt_{attempt}.md"
    md_content = _build_attempt_markdown(attempt, llm_result, error_feedback, pvmap_csv, validation_result)
    with open(md_path, 'w', encoding='utf-8') as f:
        f.write(md_content)
    saved_paths['md'] = md_path

    # Save attempt_*.json (metadata)
    json_path = response_dir / f"attempt_{attempt}.json"
    json_content = {
        'attempt': attempt,
        'model': llm_result.get('model'),
        'temperature': llm_result.get('temperature'),
        'max_tokens': llm_result.get('max_tokens'),
        'start_time': llm_result.get('start_time'),
        'end_time': llm_result.get('end_time'),
        'duration_ms': llm_result.get('duration_ms'),
        'prompt_tokens': llm_result.get('prompt_tokens'),
        'response_tokens': llm_result.get('response_tokens'),
        'total_tokens': llm_result.get('total_tokens'),
        'thoughts_tokens': llm_result.get('thoughts_tokens'),
        'has_thinking_content': bool(llm_result.get('thinking_content')),
        'had_error_feedback': bool(error_feedback),
        'validation_success': validation_result.get('success') if validation_result else None
    }
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_content, f, indent=2)
    saved_paths['json'] = json_path

    # Save attempt_*_thinking.txt (if thinking content available)
    thinking_content = llm_result.get('thinking_content', [])
    if thinking_content:
        thinking_path = response_dir / f"attempt_{attempt}_thinking.txt"
        with open(thinking_path, 'w', encoding='utf-8') as f:
            f.write('\n\n---\n\n'.join(thinking_content))
        saved_paths['thinking'] = thinking_path

    return saved_paths


def _build_attempt_markdown(
    attempt: int,
    llm_result: Dict[str, Any],
    error_feedback: Optional[str],
    pvmap_csv: Optional[str],
    validation_result: Optional[Dict[str, Any]]
) -> str:
    """Build markdown content for attempt file."""
    lines = [
        f"# PVMAP Generation Attempt {attempt + 1}",
        "",
        "## Metadata",
        "",
        f"- **Model**: {llm_result.get('model', 'unknown')}",
        f"- **Temperature**: {llm_result.get('temperature', 'unknown')}",
        f"- **Start Time**: {llm_result.get('start_time', 'unknown')}",
        f"- **End Time**: {llm_result.get('end_time', 'unknown')}",
        f"- **Duration**: {llm_result.get('duration_ms', 'unknown')} ms",
        "",
        "## Token Usage",
        "",
        f"- **Prompt Tokens**: {llm_result.get('prompt_tokens', 'N/A')}",
        f"- **Response Tokens**: {llm_result.get('response_tokens', 'N/A')}",
        f"- **Total Tokens**: {llm_result.get('total_tokens', 'N/A')}",
        f"- **Thoughts Tokens**: {llm_result.get('thoughts_tokens', 'N/A')}",
        "",
    ]

    if error_feedback:
        lines.extend([
            "## Error Feedback (from previous attempt)",
            "",
            "```",
            error_feedback[:2000] + ("..." if len(error_feedback) > 2000 else ""),
            "```",
            "",
        ])

    lines.extend([
        "## LLM Response",
        "",
        "```",
        llm_result.get('text', '(no response text)')[:10000],
        "```",
        "",
    ])

    if pvmap_csv:
        lines.extend([
            "## Extracted PVMAP CSV",
            "",
            "```csv",
            pvmap_csv[:5000] + ("..." if len(pvmap_csv) > 5000 else ""),
            "```",
            "",
        ])

    if validation_result:
        lines.extend([
            "## Validation Result",
            "",
            f"- **Success**: {validation_result.get('success', False)}",
        ])
        if validation_result.get('error'):
            lines.extend([
                "",
                "### Error",
                "",
                "```",
                str(validation_result.get('error', ''))[:2000],
                "```",
            ])

    return '\n'.join(lines)


def append_llm_call_log(
    output_dir: Path,
    attempt: int,
    llm_result: Dict[str, Any],
    prompt_length: int,
    validation_success: Optional[bool] = None
) -> Path:
    """
    Append LLM call metadata to llm_calls.jsonl.

    Args:
        output_dir: Output directory
        attempt: Attempt number
        llm_result: Result dict from generate_content_with_metadata()
        prompt_length: Length of prompt in characters
        validation_success: Whether validation passed (if available)

    Returns:
        Path to llm_calls.jsonl file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    log_path = output_dir / "llm_calls.jsonl"

    log_entry = {
        'timestamp': datetime.now().isoformat(),
        'attempt': attempt,
        'model': llm_result.get('model'),
        'temperature': llm_result.get('temperature'),
        'max_tokens': llm_result.get('max_tokens'),
        'prompt_length': prompt_length,
        'start_time': llm_result.get('start_time'),
        'end_time': llm_result.get('end_time'),
        'duration_ms': llm_result.get('duration_ms'),
        'prompt_tokens': llm_result.get('prompt_tokens'),
        'response_tokens': llm_result.get('response_tokens'),
        'total_tokens': llm_result.get('total_tokens'),
        'thoughts_tokens': llm_result.get('thoughts_tokens'),
        'response_length': len(llm_result.get('text', '') or ''),
        'has_thinking': bool(llm_result.get('thinking_content')),
        'validation_success': validation_success
    }

    with open(log_path, 'a', encoding='utf-8') as f:
        f.write(json.dumps(log_entry) + '\n')

    return log_path


def update_generation_notes(
    output_dir: Path,
    dataset_name: str,
    attempt: int,
    llm_result: Dict[str, Any],
    pvmap_csv: Optional[str] = None,
    validation_result: Optional[Dict[str, Any]] = None,
    final_status: Optional[str] = None
) -> Path:
    """
    Update generation_notes.md with attempt summary.

    Creates the file on first attempt, appends on subsequent attempts.

    Args:
        output_dir: Output directory
        dataset_name: Name of the dataset
        attempt: Attempt number (0-indexed)
        llm_result: Result dict from generate_content_with_metadata()
        pvmap_csv: Extracted PVMAP CSV (if successful)
        validation_result: Validation result dict
        final_status: Final status message (for last attempt)

    Returns:
        Path to generation_notes.md file
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    notes_path = output_dir / "generation_notes.md"

    # Initialize file on first attempt
    if attempt == 0 or not notes_path.exists():
        header = [
            f"# PVMAP Generation Notes: {dataset_name}",
            "",
            f"**Generated**: {datetime.now().isoformat()}",
            "",
            "---",
            "",
        ]
        with open(notes_path, 'w', encoding='utf-8') as f:
            f.write('\n'.join(header))

    # Append attempt summary
    attempt_summary = [
        f"## Attempt {attempt + 1}",
        "",
        f"- **Model**: {llm_result.get('model', 'unknown')}",
        f"- **Duration**: {llm_result.get('duration_ms', 'unknown')} ms",
        f"- **Tokens**: {llm_result.get('total_tokens', 'N/A')} total "
        f"({llm_result.get('prompt_tokens', 'N/A')} prompt, "
        f"{llm_result.get('response_tokens', 'N/A')} response)",
    ]

    if validation_result:
        success = validation_result.get('success', False)
        attempt_summary.append(f"- **Validation**: {'✅ Passed' if success else '❌ Failed'}")
        if not success and validation_result.get('error'):
            error_preview = str(validation_result.get('error', ''))[:200]
            attempt_summary.extend([
                "",
                "**Error Preview**:",
                f"```",
                error_preview + ("..." if len(str(validation_result.get('error', ''))) > 200 else ""),
                "```",
            ])

    attempt_summary.extend(["", "---", ""])

    with open(notes_path, 'a', encoding='utf-8') as f:
        f.write('\n'.join(attempt_summary))

    # Add final status if provided
    if final_status:
        with open(notes_path, 'a', encoding='utf-8') as f:
            f.write(f"\n## Final Status\n\n{final_status}\n")

    return notes_path


# =============================================================================
# Structured Output Conversion Functions
# =============================================================================


def escape_csv_value(value: str) -> str:
    """
    Escape a value for CSV format.

    Translates escaped PVMAP placeholders back to brace syntax:
    - [DATA] / [DATA:format] -> {Data} / {Data:format}
    - [NUMBER] / [NUMBER:format] -> {Number} / {Number:format}
    - [KEY] -> {Key}
    - [Year], [Month], [Fips], etc. -> {Year}, {Month}, {Fips}

    Also strips dcid:/dcs: prefixes (processor adds these automatically).

    Args:
        value: The string value to escape

    Returns:
        Properly escaped CSV value
    """
    if not value:
        return ""

    # Legacy placeholder syntax
    value = value.replace("PASSTHROUGH_DATA", "{Data}")
    value = value.replace("PASSTHROUGH_NUMBER", "{Number}")

    # Convert escaped PVMAP placeholders back to brace syntax.
    # escape_pvmap_placeholders converts {Data}→[DATA], {Number}→[NUMBER],
    # {Year}→[Year], etc. This reverses that transformation.
    # Safe: age brackets like [65 - Years] start with digit/hyphen → not matched.
    def _unescape_bracket(m: re.Match) -> str:
        content = m.group(1)
        # Special case: DATA → Data (escape_pvmap_placeholders uppercases it)
        if content == "DATA" or content.startswith("DATA:"):
            return '{' + content.replace("DATA", "Data", 1) + '}'
        # Special case: NUMBER → Number
        if content == "NUMBER" or content.startswith("NUMBER:"):
            return '{' + content.replace("NUMBER", "Number", 1) + '}'
        # Special case: KEY → Key
        if content == "KEY":
            return '{Key}'
        # All other named variables: preserve case as-is
        return '{' + content + '}'

    value = re.sub(
        r'\[([A-Za-z][A-Za-z0-9_]*(?::[^\]]*)?)\]',
        _unescape_bracket,
        value
    )

    # Strip dcid: and dcs: prefixes — the processor adds these automatically.
    # LLMs often add them despite instructions not to.
    if value.startswith("dcid:") and not value.startswith("dcid:{"):
        value = value[5:]
    elif value.startswith("dcs:") and not value.startswith("dcs:{"):
        value = value[4:]

    # Quote if contains comma, quote, or newline
    if ',' in value or '"' in value or '\n' in value:
        return '"' + value.replace('"', '""') + '"'
    return value


def convert_pvmap_output_to_csv(output: "PVMAPOutput") -> str:
    """
    Convert structured PVMAPOutput to CSV format.

    This is deterministic - no LLM involved, guaranteed correct formatting.

    Args:
        output: PVMAPOutput object from structured LLM response

    Returns:
        CSV string with proper formatting
    """
    if not output.pvmap_rows:
        return "key,property,value\n"

    # Find max number of property-value pairs across all rows
    max_pairs = max(len(row.mappings) for row in output.pvmap_rows)

    # Build header - use standard naming: property, value, property2, value2, etc.
    header_parts = ["key"]
    for i in range(max_pairs):
        if i == 0:
            header_parts.extend(["property", "value"])
        else:
            header_parts.extend([f"property{i + 1}", f"value{i + 1}"])

    lines = [",".join(header_parts)]

    # Build data rows
    for row in output.pvmap_rows:
        parts = [escape_csv_value(row.key)]

        for mapping in row.mappings:
            parts.append(escape_csv_value(mapping.property))
            # Strip dcid:/dcs: prefix before escaping (defense-in-depth;
            # escape_csv_value also strips, but we catch it early here
            # so the raw PVMAPOutput object is clean for any other consumers).
            val = mapping.value
            if val.startswith("dcid:") and not val.startswith("dcid:{"):
                val = val[5:]
            elif val.startswith("dcs:") and not val.startswith("dcs:{"):
                val = val[4:]
            parts.append(escape_csv_value(val))

        # Pad with empty values if fewer mappings than max
        # Note: We could trim trailing empty columns, but keeping them
        # ensures consistent CSV structure
        while len(parts) < len(header_parts):
            parts.append("")

        lines.append(",".join(parts))

    return "\n".join(lines)


def validate_pvmap_structure(output: "PVMAPOutput") -> List[str]:
    """
    Validate PVMAP structure before conversion.

    Checks for common issues that indicate the LLM generated incorrect mappings.

    Args:
        output: PVMAPOutput object to validate

    Returns:
        List of warning/error messages (empty if valid)
    """
    issues = []

    if not output.pvmap_rows:
        issues.append("PVMAP has no rows")
        return issues

    has_observation_about = False
    has_value_mapping = False

    for i, row in enumerate(output.pvmap_rows):
        # Check for hallucinated keys (keys with too many colons often indicate
        # the LLM included descriptions that aren't in the input)
        if ":" in row.key and row.key.count(":") > 2:
            issues.append(
                f"Row {i}: Key may contain extra descriptions (too many colons): "
                f"{row.key[:50]}..."
            )

        # Check for proper DCID format in values that should have them
        for mapping in row.mappings:
            prop = mapping.property
            val = mapping.value

            # Track required properties
            if prop == "observationAbout":
                has_observation_about = True
            if prop == "value":
                has_value_mapping = True

            # Warn if dcid: prefix is present — the processor adds these
            # automatically, and including them causes validation issues
            if val.startswith("dcid:") or val.startswith("dcs:"):
                issues.append(
                    f"Row {i}: {prop} value '{val}' has dcid:/dcs: prefix "
                    f"which should be removed (processor adds it automatically)"
                )

    # Check for required mappings
    if not has_observation_about:
        issues.append("CRITICAL: No observationAbout mapping found - validation will fail")

    if not has_value_mapping:
        issues.append("WARNING: No value mapping found - may be intentional for dimension-only rows")

    return issues


def parse_structured_json_response(response_text: str) -> Optional["PVMAPOutput"]:
    """
    Parse structured JSON response from LLM into PVMAPOutput.

    This handles cases where the LLM returns JSON (either raw or in code blocks).

    Args:
        response_text: Raw LLM response text

    Returns:
        PVMAPOutput object if parsing succeeds, None otherwise
    """
    from .schemas import PVMAPOutput, PVMAPRow, PropertyValuePair

    # Try to extract JSON from code blocks
    json_pattern = r'```(?:json)?\s*\n(.*?)```'
    matches = re.findall(json_pattern, response_text, re.DOTALL)

    json_str = None
    if matches:
        # Take the longest match
        json_str = max(matches, key=len).strip()
    else:
        # Try to parse the whole response as JSON
        # First, try to find JSON object boundaries
        start = response_text.find('{')
        if start != -1:
            # Find matching closing brace
            depth = 0
            for i, char in enumerate(response_text[start:], start):
                if char == '{':
                    depth += 1
                elif char == '}':
                    depth -= 1
                    if depth == 0:
                        json_str = response_text[start:i + 1]
                        break

    if not json_str:
        return None

    try:
        data = json.loads(json_str)

        # Build PVMAPOutput from parsed JSON
        pvmap_rows = []
        for row_data in data.get("pvmap_rows", []):
            mappings = []
            for m in row_data.get("mappings", []):
                mappings.append(PropertyValuePair(
                    property=m.get("property", ""),
                    value=m.get("value", "")
                ))
            pvmap_rows.append(PVMAPRow(
                key=row_data.get("key", ""),
                mappings=mappings
            ))

        return PVMAPOutput(
            format_detected=data.get("format_detected", "raw"),
            pvmap_rows=pvmap_rows,
            validation_notes=data.get("validation_notes", ""),
            confidence=data.get("confidence", "medium")
        )

    except (json.JSONDecodeError, KeyError, TypeError) as e:
        # JSON parsing failed
        return None
