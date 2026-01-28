"""I/O utilities for file operations.

This module provides file I/O abstraction for local files, GCS, and Google Spreadsheets.

Main components:
- FileIO: Context manager for file operations
- file_util: Utility functions for file operations
- download_util: URL download utilities
"""

from src.infrastructure.io.file_util import FileIO, file_get_matching
from src.infrastructure.io.download_util import request_url

__all__ = ['FileIO', 'file_get_matching', 'request_url']
