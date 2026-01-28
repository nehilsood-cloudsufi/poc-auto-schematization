"""Data Commons API integration.

This module provides API clients for external services.

Main components:
- gemini_client: Client for Google's Gemini API
- dc_api_wrapper: Wrapper for Data Commons API
"""

from src.data_commons.api.gemini_client import GeminiClient

# dc_api_wrapper has many exports, import selectively as needed
# from src.data_commons.api.dc_api_wrapper import dc_api_batched_wrapper, dc_api_wrapper

__all__ = ['GeminiClient']
