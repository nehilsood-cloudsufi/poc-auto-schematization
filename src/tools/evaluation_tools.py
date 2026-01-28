"""
Evaluation tool wrappers for ADK agents.

Wraps PVMAP comparison and ground truth discovery functions.
"""

import sys
from pathlib import Path
from typing import Dict, Any, List, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Import evaluation function
from evaluate_pvmap_diff import compare_pvmaps_diff as _compare_pvmaps_diff


def is_pvmap_filename(filename: str) -> bool:
    """
    Check if filename looks like a PVMAP file.

    Args:
        filename: Filename to check

    Returns:
        True if filename matches PVMAP patterns
    """
    filename_lower = filename.lower()
    return (
        ('pvmap' in filename_lower or 'pv_map' in filename_lower) and
        filename_lower.endswith('.csv')
    )


def find_ground_truth_pvmaps(
    dataset_name: str,
    source_repo: str = "",
    explicit_pvmap: str = "",
    search_dir: str = ""
) -> Dict[str, Any]:
    """
    Find all ground truth PVMAP files for a dataset.

    Migrated from run_pvmap_pipeline.py:994-1041.
    Some datasets have multiple ground truth PVMAPs.

    Args:
        dataset_name: Name of dataset (e.g., 'brazil_sidra_ibge')
        source_repo: Path to ground_truth repo (e.g., datacommonsorg-data/ground_truth) as string
        explicit_pvmap: Path to explicit PVMAP file (highest precedence) as string
        search_dir: Path to directory to search for PVMAP as string

    Returns:
        Dictionary with:
            - success: bool indicating if any PVMAPs found
            - pvmaps: List[str] of ground truth PVMAP file paths
            - count: int number of PVMAPs found
            - error: str with error message if failed
    """
    pvmaps = []

    try:
        # If explicit file provided, just return that
        if explicit_pvmap:
            explicit_path = Path(explicit_pvmap)
            if explicit_path.exists():
                return {
                    "success": True,
                    "pvmaps": [str(explicit_path)],
                    "count": 1,
                    "error": ""
                }
            else:
                return {
                    "success": False,
                    "pvmaps": [],
                    "count": 0,
                    "error": f"Explicit PVMAP not found: {explicit_pvmap}"
                }

        # Search in search_dir if provided
        if search_dir:
            search_path = Path(search_dir)
            if search_path.exists():
                # Look for subdirectory matching dataset name
                for subdir in search_path.iterdir():
                    if subdir.is_dir() and dataset_name.lower() in subdir.name.lower():
                        for file in subdir.iterdir():
                            if file.is_file() and is_pvmap_filename(file.name):
                                pvmaps.append(str(file))
                if pvmaps:
                    return {
                        "success": True,
                        "pvmaps": pvmaps,
                        "count": len(pvmaps),
                        "error": ""
                    }

        # Search in source_repo (ground_truth directory)
        if source_repo:
            repo_path = Path(source_repo)
            if repo_path.exists():
                # Look for subdirectory matching dataset name
                for subdir in repo_path.iterdir():
                    if subdir.is_dir() and dataset_name.lower() in subdir.name.lower():
                        for file in subdir.iterdir():
                            if file.is_file() and is_pvmap_filename(file.name):
                                pvmaps.append(str(file))

        if pvmaps:
            return {
                "success": True,
                "pvmaps": pvmaps,
                "count": len(pvmaps),
                "error": ""
            }
        else:
            return {
                "success": False,
                "pvmaps": [],
                "count": 0,
                "error": f"No ground truth PVMAP found for dataset: {dataset_name}"
            }

    except Exception as e:
        return {
            "success": False,
            "pvmaps": [],
            "count": 0,
            "error": f"Error finding ground truth PVMAPs: {str(e)}"
        }


def compare_pvmaps(
    auto_pvmap_path: str,
    gt_pvmap_path: str,
    output_dir: str
) -> Dict[str, Any]:
    """
    Compare auto-generated PVMAP with ground truth using mcf_diff.

    Wraps evaluate_pvmap_diff.compare_pvmaps_diff.

    Args:
        auto_pvmap_path: Path to auto-generated PVMAP (as string)
        gt_pvmap_path: Path to ground truth PVMAP (as string)
        output_dir: Output directory for diff results (as string)

    Returns:
        Dictionary with:
            - success: bool indicating comparison succeeded
            - counters: Dict with diff counters (nodes-matched, PVs-matched, etc.)
            - diff_text: str with diff output
            - accuracy: float node-level accuracy percentage
            - pv_accuracy: float property-value accuracy percentage
            - error: str with error message if failed
    """
    try:
        # Validate inputs
        auto_path = Path(auto_pvmap_path)
        gt_path = Path(gt_pvmap_path)
        out_dir = Path(output_dir)

        if not auto_path.exists():
            return {
                "success": False,
                "error": f"Auto-generated PVMAP not found: {auto_pvmap_path}",
                "counters": {},
                "diff_text": "",
                "accuracy": 0.0,
                "pv_accuracy": 0.0
            }

        if not gt_path.exists():
            return {
                "success": False,
                "error": f"Ground truth PVMAP not found: {gt_pvmap_path}",
                "counters": {},
                "diff_text": "",
                "accuracy": 0.0,
                "pv_accuracy": 0.0
            }

        # Create output directory if needed
        out_dir.mkdir(parents=True, exist_ok=True)

        # Run comparison
        counters, diff_str = _compare_pvmaps_diff(
            auto_pvmap_path=str(auto_path),
            gt_pvmap_path=str(gt_path),
            output_dir=str(out_dir)
        )

        # Calculate accuracy metrics
        total_gt = counters.get('nodes-ground-truth', 0)
        matched = counters.get('nodes-matched', 0)
        accuracy = round(matched / total_gt * 100, 1) if total_gt > 0 else 0.0

        pvs_matched = counters.get('PVs-matched', 0)
        pvs_total = (
            pvs_matched +
            counters.get('pvs-modified', 0) +
            counters.get('pvs-deleted', 0)
        )
        pv_accuracy = round(pvs_matched / pvs_total * 100, 1) if pvs_total > 0 else 0.0

        return {
            "success": True,
            "error": "",
            "counters": counters,
            "diff_text": diff_str,
            "accuracy": accuracy,
            "pv_accuracy": pv_accuracy
        }

    except Exception as e:
        return {
            "success": False,
            "error": f"PVMAP comparison failed: {str(e)}",
            "counters": {},
            "diff_text": "",
            "accuracy": 0.0,
            "pv_accuracy": 0.0
        }


def select_best_ground_truth(
    auto_pvmap_path: str,
    gt_pvmaps: List[str],
    output_base_dir: str
) -> Dict[str, Any]:
    """
    Compare against multiple ground truth PVMAPs and select the best match.

    Migrated from run_pvmap_pipeline.py:1227-1245.

    Args:
        auto_pvmap_path: Path to auto-generated PVMAP (as string)
        gt_pvmaps: List of ground truth PVMAP paths (as strings)
        output_base_dir: Base directory for evaluation outputs (as string)

    Returns:
        Dictionary with:
            - success: bool indicating if comparison succeeded
            - best_pvmap: str path to best matching ground truth
            - best_accuracy: float best accuracy achieved
            - all_results: List[Dict] with all comparison results
            - error: str with error message if failed
    """
    if not gt_pvmaps:
        return {
            "success": False,
            "best_pvmap": "",
            "best_accuracy": 0.0,
            "all_results": [],
            "error": "No ground truth PVMAPs provided"
        }

    try:
        all_results = []
        best_accuracy = 0.0
        best_pvmap = ""
        best_counters = {}

        for gt_pvmap_str in gt_pvmaps:
            # Create output dir for this comparison
            gt_pvmap = Path(gt_pvmap_str)
            gt_name = gt_pvmap.stem
            output_dir = Path(output_base_dir) / f"eval_{gt_name}"

            # Run comparison
            result = compare_pvmaps(
                auto_pvmap_path=auto_pvmap_path,
                gt_pvmap_path=gt_pvmap_str,
                output_dir=str(output_dir)
            )

            if result['success']:
                all_results.append({
                    "gt_pvmap": gt_pvmap_str,
                    "gt_name": gt_name,
                    "accuracy": result['accuracy'],
                    "pv_accuracy": result['pv_accuracy'],
                    "counters": result['counters']
                })

                # Track best result
                if result['accuracy'] > best_accuracy:
                    best_accuracy = result['accuracy']
                    best_pvmap = gt_pvmap_str
                    best_counters = result['counters']

        if best_pvmap:
            return {
                "success": True,
                "best_pvmap": best_pvmap,
                "best_accuracy": best_accuracy,
                "best_counters": best_counters,
                "all_results": all_results,
                "error": ""
            }
        else:
            return {
                "success": False,
                "best_pvmap": "",
                "best_accuracy": 0.0,
                "all_results": all_results,
                "error": "All comparisons failed"
            }

    except Exception as e:
        return {
            "success": False,
            "best_pvmap": "",
            "best_accuracy": 0.0,
            "all_results": [],
            "error": f"Error selecting best ground truth: {str(e)}"
        }
