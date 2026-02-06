"""
Backward compatibility layer for util/ and tools/ imports.

This module provides backward compatibility during the migration from flat
util/ and tools/ directories to the structured src/ hierarchy.

Usage:
    # Old code can still import from util/
    from util.gemini_client import GeminiClient

For sampling, use the agentic interface:
    from src.pipeline.sampling.sampling_interface import sample_dataset
"""
