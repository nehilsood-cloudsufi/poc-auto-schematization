"""
Schema selection tool wrappers for ADK agents.

Wraps tools.schema_selector functions for use in ADK pipeline.
"""

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.schema_selection.schema_selector import (
    get_category_info as _get_category_info,
    generate_data_preview as _generate_data_preview,
    build_prompt as _build_prompt,
    invoke_gemini as _invoke_gemini,
    copy_schema_files as _copy_schema_files,
    generate_schema_previews as _generate_schema_previews,
    read_schema_vocab as _read_schema_vocab,
    format_schema_vocab_for_prompt as _format_schema_vocab_for_prompt,
    SCHEMA_CATEGORIES
)


def get_schema_categories() -> Dict[str, str]:
    """
    Get available schema categories and their descriptions.

    Returns:
        Dictionary mapping category names to descriptions
        Example: {'Demographics': 'Population, age, gender...', ...}
    """
    return _get_category_info()


def generate_data_preview(
    input_dir: str,
    max_rows: int = 15
) -> Dict[str, Any]:
    """
    Generate preview of dataset for schema selection.

    Args:
        input_dir: Path to dataset input directory (as string)
        max_rows: Maximum number of rows to include in preview

    Returns:
        Dictionary with:
            - success: bool indicating success
            - preview: str with formatted CSV preview
            - error: str with error message if failed
    """
    try:
        preview_text = _generate_data_preview(Path(input_dir), max_rows)

        if preview_text.startswith("ERROR"):
            return {
                "success": False,
                "preview": None,
                "error": preview_text
            }

        return {
            "success": True,
            "preview": preview_text,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "preview": None,
            "error": f"Failed to generate data preview: {str(e)}"
        }


def build_prompt(
    metadata_content: str,
    data_preview: str,
    schema_base_dir: str,
    preview_lines: int = 8
) -> Dict[str, Any]:
    """
    Build prompt for schema category selection.

    Args:
        metadata_content: Content of metadata.csv file
        data_preview: Preview of dataset (from generate_data_preview)
        schema_base_dir: Path to schema files directory (as string)
        preview_lines: Number of lines to include in schema previews

    Returns:
        Dictionary with:
            - success: bool indicating success
            - prompt: str with complete prompt text
            - error: str with error message if failed
    """
    try:
        # Get category descriptions
        category_info = _get_category_info()

        # Generate schema file previews
        schema_previews = _generate_schema_previews(Path(schema_base_dir), preview_lines)

        # Build the prompt
        prompt_text = _build_prompt(
            metadata_content=metadata_content,
            data_preview=data_preview,
            category_info=category_info,
            schema_previews=schema_previews
        )

        return {
            "success": True,
            "prompt": prompt_text,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "prompt": None,
            "error": f"Failed to build prompt: {str(e)}"
        }


def select_schema_category(
    prompt: str,
    model_name: Optional[str] = None,
    timeout: int = 180
) -> Dict[str, Any]:
    """
    Invoke Gemini API to select schema category.

    Args:
        prompt: Complete prompt for schema selection
        model_name: Optional Gemini model name (default from GeminiClient)
        timeout: Timeout in seconds (for API compatibility)

    Returns:
        Dictionary with:
            - success: bool indicating success
            - category: str with selected category name
            - error: str with error message if failed
    """
    try:
        success, result = _invoke_gemini(prompt, timeout, model_name)

        if not success:
            return {
                "success": False,
                "category": None,
                "error": result  # result contains error message
            }

        return {
            "success": True,
            "category": result,  # result contains category name
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "category": None,
            "error": f"Schema selection failed: {str(e)}"
        }


def copy_schema_files(
    category: str,
    schema_base_dir: str,
    input_dir: str,
    dry_run: bool = False
) -> Dict[str, Any]:
    """
    Copy schema files to input directory.

    Also reads and returns compressed schema vocab if available.

    Args:
        category: Selected schema category name
        schema_base_dir: Path to schema files directory (as string)
        input_dir: Path to dataset input directory (as string)
        dry_run: If True, only report what would be copied

    Returns:
        Dictionary with:
            - success: bool indicating success
            - files_copied: List[str] of copied file paths
            - schema_vocab_content: str with formatted vocab for PVMAP prompt (or None)
            - error: str with error message if failed
    """
    try:
        # Validate input directory exists
        input_path = Path(input_dir)
        if not input_path.exists():
            return {
                "success": False,
                "files_copied": [],
                "schema_vocab_content": None,
                "error": f"Input directory not found: {input_dir}"
            }

        success, copied_files = _copy_schema_files(
            category=category,
            schema_base_dir=Path(schema_base_dir),
            input_dir=Path(input_dir),
            dry_run=dry_run
        )

        # Convert Path objects to strings
        copied_files_str = [str(f) for f in copied_files]

        # Read and format compressed vocab for downstream prompt injection
        schema_vocab_content = None
        vocab = _read_schema_vocab(category, Path(schema_base_dir))
        if vocab:
            schema_vocab_content = _format_schema_vocab_for_prompt(vocab)

        if not success:
            return {
                "success": False,
                "files_copied": copied_files_str,
                "schema_vocab_content": schema_vocab_content,
                "error": "File copy operation failed"
            }

        return {
            "success": True,
            "files_copied": copied_files_str,
            "schema_vocab_content": schema_vocab_content,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "files_copied": [],
            "schema_vocab_content": None,
            "error": f"Failed to copy schema files: {str(e)}"
        }


def read_schema_vocab(
    category: str,
    schema_base_dir: str = ""
) -> Dict[str, Any]:
    """
    Read compressed schema vocabulary JSON for a category.

    Args:
        category: Schema category name (e.g., 'Health', 'Economy')
        schema_base_dir: Path to schema files directory (as string, optional)

    Returns:
        Dictionary with:
            - success: bool indicating success
            - vocab: dict with parsed vocab JSON
            - formatted: str with human-readable prompt section
            - error: str with error message if failed
    """
    try:
        base_dir = Path(schema_base_dir) if schema_base_dir else None
        vocab = _read_schema_vocab(category, base_dir)

        if vocab is None:
            return {
                "success": False,
                "vocab": None,
                "formatted": None,
                "error": f"Schema vocab not found for category: {category}"
            }

        formatted = _format_schema_vocab_for_prompt(vocab)

        return {
            "success": True,
            "vocab": vocab,
            "formatted": formatted,
            "error": None
        }

    except Exception as e:
        return {
            "success": False,
            "vocab": None,
            "formatted": None,
            "error": f"Failed to read schema vocab: {str(e)}"
        }


def get_available_categories() -> List[str]:
    """
    Get list of available schema category names.

    Returns:
        List of category names (e.g., ['Demographics', 'Economy', ...])
    """
    return list(SCHEMA_CATEGORIES)
