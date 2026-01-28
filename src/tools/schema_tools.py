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
# Add tools directory to path
tools_dir = PROJECT_ROOT / "tools"
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))

from schema_selector import (
    get_category_info as _get_category_info,
    generate_data_preview as _generate_data_preview,
    build_prompt as _build_prompt,
    invoke_gemini as _invoke_gemini,
    copy_schema_files as _copy_schema_files,
    generate_schema_previews as _generate_schema_previews,
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
                "preview": "",
                "error": preview_text
            }

        return {
            "success": True,
            "preview": preview_text,
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "preview": "",
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
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "prompt": "",
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
                "category": "",
                "error": result  # result contains error message
            }

        return {
            "success": True,
            "category": result,  # result contains category name
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "category": "",
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

    Args:
        category: Selected schema category name
        schema_base_dir: Path to schema files directory (as string)
        input_dir: Path to dataset input directory (as string)
        dry_run: If True, only report what would be copied

    Returns:
        Dictionary with:
            - success: bool indicating success
            - files_copied: List[str] of copied file paths
            - error: str with error message if failed
    """
    try:
        success, copied_files = _copy_schema_files(
            category=category,
            schema_base_dir=Path(schema_base_dir),
            input_dir=Path(input_dir),
            dry_run=dry_run
        )

        # Convert Path objects to strings
        copied_files_str = [str(f) for f in copied_files]

        if not success:
            return {
                "success": False,
                "files_copied": copied_files_str,  # May be partial list
                "error": "File copy operation failed"
            }

        return {
            "success": True,
            "files_copied": copied_files_str,
            "error": ""
        }

    except Exception as e:
        return {
            "success": False,
            "files_copied": [],
            "error": f"Failed to copy schema files: {str(e)}"
        }


def get_available_categories() -> List[str]:
    """
    Get list of available schema category names.

    Returns:
        List of category names (e.g., ['Demographics', 'Economy', ...])
    """
    return list(SCHEMA_CATEGORIES)
