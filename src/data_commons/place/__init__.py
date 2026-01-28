"""Place resolution utilities.

This module provides utilities for resolving place names to Data Commons DCIDs.

Main components:
- place_resolver: Resolve places to DCIDs using multiple strategies
- place_name_matcher: Match place names using approximate string matching
- wiki_place_resolver: Resolve places via Wikipedia/Wikidata
"""

__all__ = ['place_resolver', 'place_name_matcher', 'wiki_place_resolver']
