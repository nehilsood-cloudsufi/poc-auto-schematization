"""
Data sampler tool wrapper for ADK agents.

Wraps tools.data_sampler.sample_csv_file for use in ADK pipeline.
"""

import sys
from pathlib import Path
from typing import Dict, Any, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
# Add tools directory to path
tools_dir = PROJECT_ROOT / "tools"
if str(tools_dir) not in sys.path:
    sys.path.insert(0, str(tools_dir))

from data_sampler import sample_csv_file


def sample_data(
    input_file: str,
    output_file: str
) -> Dict[str, Any]:
    """
    Sample a CSV file using smart sampling strategy.

    Wraps tools.data_sampler.sample_csv_file with standard config.
    Uses default config from run_pvmap_pipeline.py:375-384.

    Args:
        input_file: Path to input CSV file (as string)
        output_file: Path to output sampled CSV file (as string)

    Returns:
        Dictionary with:
            - success: bool indicating success
            - output_file: str path to generated sampled file
            - rows_sampled: int number of rows in output
            - error: str error message if failed, None otherwise
    """
    # Validate input
    input_path = Path(input_file)
    if not input_path.exists():
        return {
            "success": False,
            "error": f"Input file not found: {input_file}",
            "output_file": "",
            "rows_sampled": 0
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
        # Call the original sampler function
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
                "rows_sampled": 0
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
            "error": ""
        }

    except ValueError as e:
        return {
            "success": False,
            "error": f"Validation error: {str(e)}",
            "output_file": "",
            "rows_sampled": 0
        }
    except Exception as e:
        return {
            "success": False,
            "error": f"Sampling failed: {str(e)}",
            "output_file": "",
            "rows_sampled": 0
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
