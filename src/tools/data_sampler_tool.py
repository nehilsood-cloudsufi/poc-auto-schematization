"""
Data sampler tool wrapper for ADK agents.

Wraps tools.data_sampler.sample_csv_file for use in ADK pipeline.
Now includes data context generation for enhanced pipeline understanding.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pipeline.sampling.data_sampler import sample_csv_file, sample_csv_with_context


def sample_data(
    input_file: str,
    output_file: str,
    generate_context: bool = True,
    metadata: Dict[str, Any] = None,
    dataset_name: str = ""
) -> Dict[str, Any]:
    """
    Sample a CSV file using smart sampling strategy.

    Wraps tools.data_sampler.sample_csv_file with standard config.
    Optionally generates DataContext for downstream pipeline agents.

    Args:
        input_file: Path to input CSV file (as string)
        output_file: Path to output sampled CSV file (as string)
        generate_context: Whether to generate DataContext (default: True)
        metadata: Optional metadata dictionary for context generation
        dataset_name: Optional dataset name for context generation

    Returns:
        Dictionary with:
            - success: bool indicating success
            - output_file: str path to generated sampled file
            - rows_sampled: int number of rows in output
            - error: str error message if failed, None otherwise
            - data_context: dict with structural analysis (if generate_context=True)
            - skeleton_summary: str markdown summary for LLM prompts
    """
    # Validate input
    input_path = Path(input_file)
    if not input_path.exists():
        return {
            "success": False,
            "error": f"Input file not found: {input_file}",
            "output_file": "",
            "rows_sampled": 0,
            "data_context": None,
            "skeleton_summary": "",
        }

    # Default sampler config from run_pvmap_pipeline.py:375-384
    # Always use defaults - no custom config support to keep tool schema simple
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

    try:
        if generate_context:
            # Use new context-generating function
            result = sample_csv_with_context(
                input_file=str(input_path),
                output_file=str(output_file),
                config=sampler_config,
                metadata=metadata,
                dataset_name=dataset_name
            )

            if not result.get('success'):
                return {
                    "success": False,
                    "error": result.get('error', 'Sampling failed'),
                    "output_file": "",
                    "rows_sampled": 0,
                    "data_context": None,
                    "skeleton_summary": "",
                }

            # Extract data context metadata for state
            data_context = result.get('data_context')
            metadata_dict = result.get('metadata_dict', {})

            return {
                "success": True,
                "output_file": result.get('output_file', ''),
                "rows_sampled": result.get('rows_sampled', 0),
                "error": "",
                "data_context": metadata_dict,  # Serializable dict version
                "skeleton_summary": result.get('skeleton_summary', ''),
            }

        else:
            # Use basic sampling without context
            result_path = sample_csv_file(
                input_file=str(input_path),
                output_file=str(output_file),
                config=sampler_config
            )

            if result_path is None:
                return {
                    "success": False,
                    "error": "Sampling failed: sample_csv_file returned None",
                    "output_file": "",
                    "rows_sampled": 0,
                    "data_context": None,
                    "skeleton_summary": "",
                }

            # Count rows in output (optional, for reporting)
            output_path = Path(result_path)
            rows_sampled = 0
            if output_path.exists():
                try:
                    with open(output_path, 'r') as f:
                        rows_sampled = sum(1 for _ in f)
                except Exception:
                    # Row counting is optional, don't fail on error
                    rows_sampled = 0

            return {
                "success": True,
                "output_file": str(result_path),
                "rows_sampled": rows_sampled,
                "error": "",
                "data_context": None,
                "skeleton_summary": "",
            }

    except ValueError as e:
        return {
            "success": False,
            "error": f"Validation error: {str(e)}",
            "output_file": "",
            "rows_sampled": 0,
            "data_context": None,
            "skeleton_summary": "",
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Sampling failed: {str(e)}",
            "output_file": "",
            "rows_sampled": 0,
            "data_context": None,
            "skeleton_summary": "",
        }


def get_default_sampler_config() -> Dict[str, Any]:
    """
    Get default sampler configuration.

    Returns pipeline default config from run_pvmap_pipeline.py:375-384.

    Returns:
        Dictionary with default sampler parameters
    """
    return {
        'sampler_output_rows': 100,
        'sampler_rows_per_key': 5,
        'sampler_categorical_threshold': 0.1,
        'sampler_max_aggregation_rows': 2,
        'sampler_ensure_coverage': True,
        'sampler_smart_columns': True,
        'sampler_detect_aggregation': True,
        'sampler_auto_detect_categorical': True,
    }
