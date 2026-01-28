"""
Backward compatibility for util/ imports.

This file provides re-exports from the new src/infrastructure/ location
to maintain backward compatibility during migration.

Current Status: Week 4 Complete - Schema & Place resolution migrated

Usage (deprecated - update to new paths):
    from src.compatibility.util_compat import FileIO, ConfigMap, Counters, Timer

Recommended (new paths):
    from src.infrastructure.io.file_util import FileIO
    from src.infrastructure.config.config_map import ConfigMap
    from src.infrastructure.metrics.counters import Counters
    from src.infrastructure.metrics.timer import Timer
"""

import warnings

# Emit deprecation warning when this module is imported
warnings.warn(
    "The util/ compatibility layer is active. "
    "Please update imports to use src/ paths. "
    "Example: from src.infrastructure.io.file_util import FileIO",
    DeprecationWarning,
    stacklevel=2
)

# Week 2: Infrastructure layer re-exports
from src.infrastructure.io.file_util import FileIO, file_get_matching
from src.infrastructure.config.config_map import ConfigMap, get_config_map_from_file
from src.infrastructure.metrics.counters import Counters, CounterOptions
from src.infrastructure.metrics.timer import Timer
from src.infrastructure.log.log_util import log_struct
from src.infrastructure.utils.aggregation_util import aggregate_dict, aggregate_value

# Week 3: Data Commons API re-exports
from src.data_commons.api.gemini_client import GeminiClient
from src.data_commons.statvar.statvar_dcid_generator import get_statvar_dcid
from src.data_commons.codes.naics_codes import NAICS_CODES
from src.data_commons.codes.soc_codes_names import SOC_MAP

__all__ = [
    # io/file_util
    'FileIO', 'file_get_matching',
    # config/config_map
    'ConfigMap', 'get_config_map_from_file',
    # metrics/counters
    'Counters', 'CounterOptions',
    # metrics/timer
    'Timer',
    # logging/log_util
    'log_struct',
    # utils/aggregation_util
    'aggregate_dict', 'aggregate_value',
    # api/gemini_client
    'GeminiClient',
    # statvar/statvar_dcid_generator
    'get_statvar_dcid',
    # codes
    'NAICS_CODES', 'SOC_MAP',
]
