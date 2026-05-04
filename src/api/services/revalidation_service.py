"""Revalidation service — run stat_var_processor on edited PVMAP."""
import logging
from pathlib import Path
from typing import Any, Dict, Optional

from src.tools.validation_tool import run_validation

logger = logging.getLogger(__name__)


def revalidate(
    input_data: Path,
    pvmap_path: Path,
    metadata_path: Optional[Path],
    output_dir: Path,
) -> Dict[str, Any]:
    """Run stat_var_processor validation on the current PVMAP.

    Args:
        input_data: Path to the original input CSV.
        pvmap_path: Path to generated_pvmap.csv (should already be saved to disk).
        metadata_path: Path to output_metadata.csv (or None if no metadata).
        output_dir: Dataset output directory for processed files.

    Returns:
        Result dict from run_validation() with keys: success, data_rows, error,
        counter_summary, etc.
    """
    logger.info(
        "Revalidating: input=%s, pvmap=%s, metadata=%s, output=%s",
        input_data, pvmap_path, metadata_path, output_dir,
    )

    result = run_validation(
        input_data=str(input_data),
        pvmap_path=str(pvmap_path),
        metadata_file=str(metadata_path) if metadata_path and metadata_path.exists() else "",
        output_dir=str(output_dir),
        timeout=300,
    )

    if result["success"]:
        logger.info("Revalidation passed: %d data rows", result.get("data_rows", 0))
    else:
        logger.warning("Revalidation failed: %s", result.get("error", "unknown"))

    return result
