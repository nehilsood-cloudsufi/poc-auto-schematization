"""Data sampling utilities for the pipeline.

This module provides agentic (LLM-driven) data sampling for PVMAP generation.

Modules:
- sampling_interface: Agentic sampling interface (RECOMMENDED)
- column_analyzer: Column classification and analysis
- data_context: DataContext generation for understanding dataset structure
- combination_tracker: Track dimension combination coverage

Usage:
    from src.pipeline.sampling.sampling_interface import sample_dataset, SamplingResult

    result = sample_dataset(
        input_files=[Path("input.csv")],
        output_dir=Path("output/")
    )
    print(result.skeleton_summary)  # Markdown for PVMAP prompt
"""

# Export agentic sampling interface
from src.pipeline.sampling.sampling_interface import (
    SamplingResult,
    sample_dataset,
)

__all__ = [
    # Agentic interface
    'SamplingResult',
    'sample_dataset',
    # Submodules
    'column_analyzer',
    'data_context',
    'combination_tracker',
    'sampling_interface',
]
