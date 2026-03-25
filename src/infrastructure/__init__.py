"""Infrastructure layer - Core platform services.

This package contains foundational utilities used by other modules:

Subpackages:
- io: File I/O abstraction (local files, GCS, Google Sheets)
- config: Configuration management
- logging: Logging infrastructure
- metrics: Counters and timing utilities
- utils: Shared utility functions
"""

__all__ = ['io', 'config', 'logging', 'metrics', 'utils']
