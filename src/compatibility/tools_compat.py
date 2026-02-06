"""
Backward compatibility for tools/ imports.

This file provides re-exports from the new src/pipeline/ and src/processing/ locations
to maintain backward compatibility during migration.

For sampling, use the agentic sampling interface:
    from src.pipeline.sampling.sampling_interface import sample_dataset, SamplingResult

    result = sample_dataset(
        input_files=[Path(input_file)],
        output_dir=Path(output_dir)
    )
    # result.sampled_file - Path to output
    # result.skeleton_summary - Markdown for LLM prompts
    # result.data_context - Structural analysis dict

Recommended (new paths):
    from src.pipeline.sampling.sampling_interface import sample_dataset, SamplingResult
    from src.processing.mapping.property_value_mapper import PropertyValueMapper
"""

import warnings

# Emit deprecation warning when this module is imported
warnings.warn(
    "The tools/ directory compatibility layer is active. "
    "Please update imports to use src/ paths. "
    "For sampling, use: from src.pipeline.sampling.sampling_interface import sample_dataset",
    DeprecationWarning,
    stacklevel=2
)

# Pipeline layer re-exports (sampling via interface only)
from src.pipeline.sampling.sampling_interface import sample_dataset, SamplingResult

# Processing mapping re-exports
try:
    from src.processing.mapping.property_value_mapper import PropertyValueMapper
except ImportError:
    PropertyValueMapper = None

# Column analyzer
try:
    from src.pipeline.sampling.column_analyzer import ColumnAnalyzer, ColumnAnalysisResult
except ImportError:
    ColumnAnalyzer = None
    ColumnAnalysisResult = None

__all__ = [
    # Pipeline - sampling (agentic only)
    'sample_dataset', 'SamplingResult',
    'ColumnAnalyzer', 'ColumnAnalysisResult',
    # Processing - mapping
    'PropertyValueMapper',
]
