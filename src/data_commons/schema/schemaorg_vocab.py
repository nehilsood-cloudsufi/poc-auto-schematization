"""
Schema.org vocabulary lookup API for Data Commons.

Provides a singleton class that lazily loads the local schema.org cache
and offers type/property lookup, hierarchy traversal, fuzzy search,
and DC-to-schema.org mapping.

Usage:
    from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab

    vocab = SchemaOrgVocab.instance()
    person = vocab.get_type("Person")
    props = vocab.get_properties_for_type("Person", inherited=True)
    valid = vocab.is_valid_property_for_type("gender", "Person")
"""

import json
import logging
from pathlib import Path
from typing import Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_CACHE_DIR = Path(__file__).parent.parent.parent / "resources" / "schema_org"


class SchemaOrgVocab:
    """Singleton schema.org vocabulary API backed by local JSON cache."""

    _instance: Optional["SchemaOrgVocab"] = None

    def __init__(self, cache_dir: Optional[Path] = None):
        self._cache_dir = cache_dir or DEFAULT_CACHE_DIR
        self._types: Optional[Dict[str, dict]] = None
        self._properties: Optional[Dict[str, dict]] = None
        self._hierarchy: Optional[Dict[str, List[str]]] = None
        self._dc_mapping: Optional[dict] = None

        # Case-insensitive lookup indexes (built lazily)
        self._type_index: Optional[Dict[str, str]] = None
        self._prop_index: Optional[Dict[str, str]] = None

    @classmethod
    def instance(cls, cache_dir: Optional[Path] = None) -> "SchemaOrgVocab":
        """Get or create the singleton instance."""
        if cls._instance is None:
            cls._instance = cls(cache_dir=cache_dir)
        return cls._instance

    @classmethod
    def reset(cls) -> None:
        """Reset the singleton (for testing)."""
        cls._instance = None

    # =========================================================================
    # Lazy loading
    # =========================================================================

    def _ensure_loaded(self) -> None:
        """Load cache files on first access."""
        if self._types is not None:
            return

        types_path = self._cache_dir / "types.json"
        props_path = self._cache_dir / "properties.json"
        hierarchy_path = self._cache_dir / "type_hierarchy.json"
        mapping_path = self._cache_dir / "dc_mapping.json"

        if not types_path.exists():
            logger.warning(
                f"Schema.org cache not found at {self._cache_dir}. "
                "Run: python tools/build_schemaorg_cache.py"
            )
            self._types = {}
            self._properties = {}
            self._hierarchy = {}
            self._dc_mapping = {"population_types": {}, "properties": {}, "enums": {}}
            self._type_index = {}
            self._prop_index = {}
            return

        try:
            self._types = json.loads(types_path.read_text(encoding="utf-8"))
            self._properties = json.loads(props_path.read_text(encoding="utf-8"))
            self._hierarchy = json.loads(hierarchy_path.read_text(encoding="utf-8"))
        except Exception as e:
            logger.error(f"Failed to load schema.org cache: {e}")
            self._types = {}
            self._properties = {}
            self._hierarchy = {}
            self._type_index = {}
            self._prop_index = {}

        try:
            if mapping_path.exists():
                self._dc_mapping = json.loads(mapping_path.read_text(encoding="utf-8"))
            else:
                self._dc_mapping = {"population_types": {}, "properties": {}, "enums": {}}
        except Exception as e:
            logger.warning(f"Failed to load DC mapping: {e}")
            self._dc_mapping = {"population_types": {}, "properties": {}, "enums": {}}

        # Build case-insensitive indexes
        self._type_index = {name.lower(): name for name in self._types}
        self._prop_index = {name.lower(): name for name in self._properties}

        logger.info(
            f"Schema.org vocab loaded: {len(self._types)} types, "
            f"{len(self._properties)} properties"
        )

    def _resolve_type_name(self, name: str) -> Optional[str]:
        """Resolve a type name with case-insensitive matching (exact-first)."""
        self._ensure_loaded()
        if name in self._types:
            return name
        return self._type_index.get(name.lower())

    def _resolve_prop_name(self, name: str) -> Optional[str]:
        """Resolve a property name with case-insensitive matching (exact-first)."""
        self._ensure_loaded()
        if name in self._properties:
            return name
        return self._prop_index.get(name.lower())

    # =========================================================================
    # Type lookups
    # =========================================================================

    def get_type(self, name: str) -> Optional[dict]:
        """
        Look up a schema.org type.

        Args:
            name: Type name (e.g., "Person", "Place", "Observation")

        Returns:
            Dict with {parent[], description, properties[]} or None
        """
        resolved = self._resolve_type_name(name)
        if resolved is None:
            return None
        return self._types[resolved]

    def get_type_hierarchy(self, name: str) -> Optional[List[str]]:
        """
        Get the ancestor chain for a type.

        Args:
            name: Type name

        Returns:
            List of ancestor types (e.g., ["Thing"] for Person) or None
        """
        self._ensure_loaded()
        resolved = self._resolve_type_name(name)
        if resolved is None:
            return None
        return self._hierarchy.get(resolved, [])

    def get_properties_for_type(self, name: str, inherited: bool = True) -> Optional[List[str]]:
        """
        Get all properties valid for a type.

        Args:
            name: Type name
            inherited: If True, include properties from ancestor types

        Returns:
            Sorted list of property names, or None if type not found
        """
        self._ensure_loaded()
        resolved = self._resolve_type_name(name)
        if resolved is None:
            return None

        props = set(self._types[resolved]["properties"])

        if inherited:
            ancestors = self._hierarchy.get(resolved, [])
            for ancestor in ancestors:
                if ancestor in self._types:
                    props.update(self._types[ancestor]["properties"])

        return sorted(props)

    # =========================================================================
    # Property lookups
    # =========================================================================

    def get_property(self, name: str) -> Optional[dict]:
        """
        Look up a schema.org property.

        Args:
            name: Property name (e.g., "gender", "name", "observationDate")

        Returns:
            Dict with {domain[], range[], description} or None
        """
        resolved = self._resolve_prop_name(name)
        if resolved is None:
            return None
        return self._properties[resolved]

    def get_expected_range(self, prop: str) -> Optional[List[str]]:
        """
        Get expected range types for a property.

        Args:
            prop: Property name

        Returns:
            List of expected range types, or None if property not found
        """
        info = self.get_property(prop)
        if info is None:
            return None
        return info.get("range", [])

    def is_valid_property_for_type(self, prop: str, type_name: str) -> bool:
        """
        Check if a property is valid for a given type (including ancestors).

        Args:
            prop: Property name
            type_name: Type name

        Returns:
            True if the property's domain includes the type or its ancestors
        """
        self._ensure_loaded()
        prop_info = self.get_property(prop)
        if prop_info is None:
            return False

        domains = set(prop_info.get("domain", []))
        if not domains:
            return True  # Properties with no domain are valid for all types

        resolved = self._resolve_type_name(type_name)
        if resolved is None:
            return False

        # Check direct type
        if resolved in domains:
            return True

        # Check ancestors
        ancestors = self._hierarchy.get(resolved, [])
        for ancestor in ancestors:
            if ancestor in domains:
                return True

        return False

    # =========================================================================
    # Search
    # =========================================================================

    def search_types(self, query: str, limit: int = 10) -> List[dict]:
        """
        Fuzzy keyword search for types.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of {name, description, parent[]} dicts
        """
        self._ensure_loaded()
        query_lower = query.lower()
        results = []

        for name, info in self._types.items():
            name_lower = name.lower()
            desc_lower = info.get("description", "").lower()

            # Score: exact prefix > contains in name > contains in description
            score = 0
            if name_lower == query_lower:
                score = 100
            elif name_lower.startswith(query_lower):
                score = 80
            elif query_lower in name_lower:
                score = 60
            elif query_lower in desc_lower:
                score = 30

            if score > 0:
                results.append((score, name, info))

        results.sort(key=lambda x: (-x[0], x[1]))
        return [
            {"name": name, "description": info.get("description", ""), "parent": info.get("parent", [])}
            for _, name, info in results[:limit]
        ]

    def search_properties(self, query: str, limit: int = 10) -> List[dict]:
        """
        Fuzzy keyword search for properties.

        Args:
            query: Search query
            limit: Max results

        Returns:
            List of {name, description, domain[], range[]} dicts
        """
        self._ensure_loaded()
        query_lower = query.lower()
        results = []

        for name, info in self._properties.items():
            name_lower = name.lower()
            desc_lower = info.get("description", "").lower()

            score = 0
            if name_lower == query_lower:
                score = 100
            elif name_lower.startswith(query_lower):
                score = 80
            elif query_lower in name_lower:
                score = 60
            elif query_lower in desc_lower:
                score = 30

            if score > 0:
                results.append((score, name, info))

        results.sort(key=lambda x: (-x[0], x[1]))
        return [
            {
                "name": name,
                "description": info.get("description", ""),
                "domain": info.get("domain", []),
                "range": info.get("range", []),
            }
            for _, name, info in results[:limit]
        ]

    # =========================================================================
    # Data Commons mapping bridge
    # =========================================================================

    def dc_type_to_schemaorg(self, dc_type: str) -> Optional[str]:
        """
        Map a Data Commons populationType to its schema.org equivalent.

        Args:
            dc_type: DC type name (e.g., "Person", "BLSEstablishment")

        Returns:
            Schema.org type name, or None if DC-only
        """
        self._ensure_loaded()
        pop_types = self._dc_mapping.get("population_types", {})
        return pop_types.get(dc_type)

    def dc_property_to_schemaorg(self, dc_prop: str) -> Optional[str]:
        """
        Map a Data Commons property to its schema.org equivalent.

        Args:
            dc_prop: DC property name (e.g., "gender", "age", "naics")

        Returns:
            Schema.org property name, or None if DC-only
        """
        self._ensure_loaded()
        props = self._dc_mapping.get("properties", {})
        return props.get(dc_prop)

    def is_known_dc_property(self, prop: str) -> bool:
        """Check if a property is known in DC mapping (even if DC-only)."""
        self._ensure_loaded()
        props = self._dc_mapping.get("properties", {})
        return prop in props

    def is_known_dc_type(self, type_name: str) -> bool:
        """Check if a type is known in DC mapping."""
        self._ensure_loaded()
        pop_types = self._dc_mapping.get("population_types", {})
        return type_name in pop_types

    def get_dc_enums(self, enum_type: str) -> Optional[List[str]]:
        """Get valid enum values for a DC enum type."""
        self._ensure_loaded()
        enums = self._dc_mapping.get("enums", {})
        return enums.get(enum_type)

    def is_known_property(self, prop: str) -> bool:
        """Check if a property is known in schema.org OR DC mapping."""
        return self.get_property(prop) is not None or self.is_known_dc_property(prop)

    def is_known_type(self, type_name: str) -> bool:
        """Check if a type is known in schema.org OR DC mapping."""
        return self.get_type(type_name) is not None or self.is_known_dc_type(type_name)
