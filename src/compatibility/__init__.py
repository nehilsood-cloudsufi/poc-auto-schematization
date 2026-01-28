"""
Backward compatibility layer for util/ and tools/ imports.

This module provides backward compatibility during the migration from flat
util/ and tools/ directories to the structured src/ hierarchy.

Usage:
    # Old code can still import from util/ and tools/
    from util.gemini_client import GeminiClient
    from tools.data_sampler import sample_csv_file

During migration, imports are gradually updated to new paths:
    from src.data_commons.api.gemini_client import GeminiClient
    from src.pipeline.sampling.data_sampler import sample_csv_file
"""
