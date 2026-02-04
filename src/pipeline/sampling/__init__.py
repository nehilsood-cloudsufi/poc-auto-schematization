"""Data sampling utilities for the pipeline.

This module provides utilities for intelligently sampling CSV data files
and generating data context for downstream pipeline agents.

Modules:
- data_sampler: Core CSV sampling with categorical coverage
- column_analyzer: Column classification and analysis
- data_context: DataContext generation for understanding dataset structure
- dimension_detector: Dimension column detection using heuristics
- combination_tracker: Track dimension combination coverage
- skeleton_sampler: Fixed-Pivot strategic sampling
"""

__all__ = [
    'data_sampler',
    'column_analyzer',
    'data_context',
    'dimension_detector',
    'combination_tracker',
    'skeleton_sampler',
]
