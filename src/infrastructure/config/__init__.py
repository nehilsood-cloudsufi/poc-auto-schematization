"""Configuration management utilities.

This module provides configuration loading and management.

Main components:
- ConfigMap: Class for loading and managing configuration parameters
- config_flags: Command-line flag definitions and config initialization
  Note: Import config_flags directly to avoid flag definition conflicts
"""

from src.infrastructure.config.config_map import ConfigMap

__all__ = ['ConfigMap']
