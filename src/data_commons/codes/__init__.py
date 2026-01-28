"""Industry and occupation code mappings.

This module provides code-to-name mappings for various classification systems.

Main components:
- naics_codes: NAICS industry classification codes
- soc_codes_names: SOC occupation classification codes
"""

from src.data_commons.codes.soc_codes_names import SOC_MAP
from src.data_commons.codes.naics_codes import NAICS_CODES

__all__ = ['SOC_MAP', 'NAICS_CODES']
