"""
Backward compatibility for tools/ imports.

This file provides re-exports from the new src/pipeline/ and src/processing/ locations
to maintain backward compatibility during migration.

Current Status: Week 9 Complete - All modules migrated

Usage (deprecated - update to new paths):
    from src.compatibility.tools_compat import sample_csv_file, PropertyValueMapper

Recommended (new paths):
    from src.pipeline.sampling.data_sampler import sample_csv_file
    from src.processing.mapping.property_value_mapper import PropertyValueMapper
"""

import warnings

# Emit deprecation warning when this module is imported
warnings.warn(
    "The tools/ directory compatibility layer is active. "
    "Please update imports to use src/ paths. "
    "Example: from src.pipeline.sampling.data_sampler import sample_csv_file",
    DeprecationWarning,
    stacklevel=2
)

# Week 5: Pipeline layer re-exports
from src.pipeline.sampling.data_sampler import sample_csv_file, DataSamplerConfig
from src.pipeline.sampling.column_analyzer import ColumnAnalyzer, ColumnAnalysisResult

# Week 5: Processing mapping re-exports
from src.processing.mapping.property_value_mapper import PropertyValueMapper
from src.processing.mapping.property_value_utils import get_property_value_map

# Week 5: Processing evaluation re-exports
from src.processing.evaluation.eval_functions import evaluate_expression

# Week 6: Filtering re-exports
from src.processing.filtering.filter_data_outliers import filter_outliers

# Week 6: Transformation re-exports
from src.processing.transformation.json_to_csv import json_to_csv

# Week 6: Processing utils re-exports
from src.processing.utils import get_column_values

__all__ = [
    # Pipeline - sampling
    'sample_csv_file', 'DataSamplerConfig',
    'ColumnAnalyzer', 'ColumnAnalysisResult',
    # Processing - mapping
    'PropertyValueMapper', 'get_property_value_map',
    # Processing - evaluation
    'evaluate_expression',
    # Processing - filtering
    'filter_outliers',
    # Processing - transformation
    'json_to_csv',
    # Processing - utils
    'get_column_values',
]
