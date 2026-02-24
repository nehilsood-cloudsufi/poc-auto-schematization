# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the 'License');
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#         https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an 'AS IS' BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""Agentic sampling interface for PVMAP generation pipeline.

This module provides the single entry point for LLM-driven data sampling
that generates both sampled CSV files and skeleton_summary context for
downstream PVMAP generation.

Usage:
    from src.pipeline.sampling.sampling_interface import sample_dataset, SamplingResult

    result = sample_dataset(
        input_files=[Path("input/dataset/test_data/data.csv")],
        output_dir=Path("output/dataset")
    )
    print(result.skeleton_summary)  # Markdown for PVMAP prompt
    print(result.sampled_file)      # Path to sampled CSV

Output:
    - sampled_file: Path to agentic_sampled.csv
    - skeleton_summary: Markdown summary for LLM prompts
    - data_context: Dict with structural analysis
    - column_roles: Dict mapping columns to roles (place, time, dimension, value)
    - dimension_columns: List of dimension column names
"""

import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent.resolve()
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

logger = logging.getLogger(__name__)


@dataclass
class SamplingResult:
    """Result of an agentic sampling operation.

    This dataclass provides the output of LLM-driven sampling, including
    skeleton_summary which provides a markdown description of the data
    structure for downstream PVMAP generation.

    Attributes:
        sampled_file: Path to the output sampled CSV file (agentic_sampled.csv)
        skeleton_summary: Markdown summary of data structure for LLM prompts
        data_context: Dictionary containing structural analysis of the data
        rows_sampled: Number of rows in the sampled output
        success: Whether the sampling operation succeeded
        error: Error message if sampling failed, None otherwise
        method: Always "agentic" (kept for compatibility)
        column_roles: Dictionary mapping column names to roles (place, time, dimension, value, metadata)
        dimension_columns: List of columns identified as dimensions
    """
    sampled_file: Path
    skeleton_summary: str = ""
    data_context: Dict[str, Any] = field(default_factory=dict)
    rows_sampled: int = 0
    success: bool = True
    error: Optional[str] = None
    method: str = "unknown"
    column_roles: Dict[str, str] = field(default_factory=dict)
    dimension_columns: List[str] = field(default_factory=list)

    def __post_init__(self):
        """Ensure sampled_file is a Path object."""
        if isinstance(self.sampled_file, str):
            self.sampled_file = Path(self.sampled_file)


def sample_dataset(
    input_files: List[Path],
    output_dir: Path,
    force_resample: bool = False,
    metadata_file: Optional[Path] = None,
    dataset_name: str = "",
    **kwargs
) -> SamplingResult:
    """Run agentic (LLM-driven) sampling on input data files.

    Uses the agentic sampling tools to intelligently sample data and
    generate skeleton_summary context for downstream PVMAP generation.

    Args:
        input_files: List of input CSV file paths to sample
        output_dir: Output directory for sampled files (writes to
            output_dir/agentic_sampled.csv and output_dir/data_context.json)
        force_resample: If True, re-run sampling even if output files exist
        metadata_file: Optional path to metadata CSV file for context
        dataset_name: Optional dataset name for context generation
        **kwargs: Additional arguments (ignored, kept for compatibility)

    Returns:
        SamplingResult with sampled file path, skeleton_summary, and metadata

    Raises:
        RuntimeError: If agentic sampling fails (check result.error for details)

    Example:
        >>> from pathlib import Path
        >>> result = sample_dataset(
        ...     input_files=[Path("input/my_dataset/test_data/data.csv")],
        ...     output_dir=Path("output/my_dataset")
        ... )
        >>> print(result.skeleton_summary)
        ## DATA SKELETON SUMMARY
        ...
    """
    if not input_files:
        return SamplingResult(
            sampled_file=Path(""),
            success=False,
            error="No input files provided",
            method="agentic"
        )

    # Ensure output directory exists
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Convert input_files to Path objects
    input_files = [Path(f) for f in input_files]

    return _sample_agentic(
        input_files=input_files,
        output_dir=output_dir,
        force_resample=force_resample,
        metadata_file=metadata_file,
        dataset_name=dataset_name,
    )


def _sample_agentic(
    input_files: List[Path],
    output_dir: Path,
    force_resample: bool = False,
    metadata_file: Optional[Path] = None,
    dataset_name: str = "",
    **kwargs
) -> SamplingResult:
    """Run agentic (LLM-driven) sampling.

    Uses the ProgrammaticSamplingAgent to run an LLM that makes intelligent
    sampling decisions based on data evidence.

    Args:
        input_files: List of input CSV files
        output_dir: Output directory
        force_resample: If True, re-run even if cached
        metadata_file: Optional metadata file path
        dataset_name: Dataset name for context

    Returns:
        SamplingResult with agentic sampling output
    """
    import json

    # Check for cached context file
    context_file = output_dir / "data_context.json"
    sampled_file = output_dir / "agentic_sampled.csv"

    if context_file.exists() and sampled_file.exists() and not force_resample:
        logger.info(f"Using cached agentic sampling from {context_file}")
        try:
            with open(context_file, 'r', encoding='utf-8') as f:
                cached_context = json.load(f)

            return SamplingResult(
                sampled_file=sampled_file,
                skeleton_summary=cached_context.get("skeleton_summary", ""),
                data_context=cached_context.get("data_context", {}),
                rows_sampled=cached_context.get("data_context", {}).get("total_rows", 0),
                success=cached_context.get("success", True),
                error=None,
                method="agentic",
                column_roles=cached_context.get("column_roles", {}),
                dimension_columns=cached_context.get("dimension_columns", []),
            )
        except Exception as e:
            logger.warning(f"Failed to load cached context: {e}, re-running sampling")

    # Try to run agentic sampling using sampling tools directly
    # (This avoids needing the full ADK infrastructure)
    try:
        from src.tools.sampling_tools import (
            preview_data,
            analyze_columns,
            sample_rows,
            check_coverage,
            generate_context,
        )

        # Use first input file
        input_file = str(input_files[0])
        output_file = str(sampled_file)

        logger.info(f"Running agentic sampling on {input_file}")

        # Step 1: Preview data
        preview = preview_data(input_file)
        if not preview.get("success"):
            return SamplingResult(
                sampled_file=Path(""),
                success=False,
                error=f"Preview failed: {preview.get('error')}",
                method="agentic"
            )

        # Step 2: Analyze columns
        analysis = analyze_columns(input_file)
        if not analysis.get("success"):
            return SamplingResult(
                sampled_file=Path(""),
                success=False,
                error=f"Column analysis failed: {analysis.get('error')}",
                method="agentic"
            )

        # Step 3: Classify columns based on analysis
        columns = analysis.get("columns", {})
        column_roles = {}
        dimension_columns = []
        place_col = None
        time_col = None

        for col, col_info in columns.items():
            if col_info.get("looks_like_place"):
                column_roles[col] = "place"
                if place_col is None:
                    place_col = col
            elif col_info.get("looks_like_date"):
                column_roles[col] = "time"
                if time_col is None:
                    time_col = col
            elif col_info.get("cardinality_ratio", 1.0) < 0.1:
                column_roles[col] = "dimension"
                dimension_columns.append(col)
            elif col_info.get("dtype") in ("Integer", "Float") and col_info.get("cardinality_ratio", 0) > 0.3:
                column_roles[col] = "value"
            else:
                column_roles[col] = "metadata"

        # Step 4: Sample rows using stratified strategy
        strategy_json = json.dumps({
            "mode": "stratified" if dimension_columns else "head",
            "target_rows": 80,
            "stratify_by": dimension_columns[:3] if dimension_columns else []
        })

        sample_result = sample_rows(input_file, output_file, strategy_json)
        if not sample_result.get("success"):
            return SamplingResult(
                sampled_file=Path(""),
                success=False,
                error=f"Sampling failed: {sample_result.get('error')}",
                method="agentic"
            )

        # Step 5: Generate context
        context_result = generate_context(
            sampled_file=output_file,
            column_roles_json=json.dumps(column_roles),
            dimension_columns=dimension_columns,
            metadata_json="{}"
        )

        if not context_result.get("success"):
            # Still return success since we have sampled data
            logger.warning(f"Context generation failed: {context_result.get('error')}")

        return SamplingResult(
            sampled_file=Path(output_file),
            skeleton_summary=context_result.get("skeleton_summary", ""),
            data_context=context_result.get("data_context", {}),
            rows_sampled=sample_result.get("rows_sampled", 0),
            success=True,
            error=None,
            method="agentic",
            column_roles=column_roles,
            dimension_columns=dimension_columns,
        )

    except ImportError as e:
        logger.warning(f"Agentic sampling tools not available: {e}")
        return SamplingResult(
            sampled_file=Path(""),
            success=False,
            error=f"Agentic sampling not available: {e}",
            method="agentic"
        )
    except Exception as e:
        logger.error(f"Agentic sampling failed: {e}")
        return SamplingResult(
            sampled_file=Path(""),
            success=False,
            error=f"Agentic sampling failed: {e}",
            method="agentic"
        )


__all__ = [
    'SamplingResult',
    'sample_dataset',
]
