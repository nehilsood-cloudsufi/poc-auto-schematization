"""Tests for SchemaOrgVocab class."""

import json
import pytest
from pathlib import Path

from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab, DEFAULT_CACHE_DIR


@pytest.fixture(autouse=True)
def reset_singleton():
    """Reset the singleton before each test."""
    SchemaOrgVocab.reset()
    yield
    SchemaOrgVocab.reset()


@pytest.fixture
def vocab():
    """Get a SchemaOrgVocab instance with real cache."""
    return SchemaOrgVocab.instance()


# =========================================================================
# Cache availability
# =========================================================================

class TestCacheAvailability:
    """Verify the cache files exist from build_schemaorg_cache.py."""

    def test_types_json_exists(self):
        assert (DEFAULT_CACHE_DIR / "types.json").exists()

    def test_properties_json_exists(self):
        assert (DEFAULT_CACHE_DIR / "properties.json").exists()

    def test_type_hierarchy_json_exists(self):
        assert (DEFAULT_CACHE_DIR / "type_hierarchy.json").exists()

    def test_dc_mapping_json_exists(self):
        assert (DEFAULT_CACHE_DIR / "dc_mapping.json").exists()


# =========================================================================
# Type lookups
# =========================================================================

class TestTypeLookup:
    """Test type lookups against real schema.org data."""

    def test_person_type(self, vocab):
        result = vocab.get_type("Person")
        assert result is not None
        assert "Thing" in result["parent"]
        assert isinstance(result["properties"], list)
        assert len(result["properties"]) > 10  # Person has many properties

    def test_place_type(self, vocab):
        result = vocab.get_type("Place")
        assert result is not None
        assert "Thing" in result["parent"]

    def test_observation_type(self, vocab):
        result = vocab.get_type("Observation")
        assert result is not None
        assert isinstance(result["properties"], list)

    def test_thing_type(self, vocab):
        result = vocab.get_type("Thing")
        assert result is not None
        assert result["parent"] == []  # Thing is the root

    def test_unknown_type_returns_none(self, vocab):
        result = vocab.get_type("NonExistentTypeXYZ")
        assert result is None

    def test_case_insensitive_type_lookup(self, vocab):
        result = vocab.get_type("person")
        assert result is not None
        assert "Thing" in result["parent"]

    def test_exact_case_priority(self, vocab):
        """Exact case match should work."""
        result1 = vocab.get_type("Person")
        result2 = vocab.get_type("person")
        assert result1 is not None
        assert result2 is not None


# =========================================================================
# Property lookups
# =========================================================================

class TestPropertyLookup:
    """Test property lookups against real schema.org data."""

    def test_gender_property(self, vocab):
        result = vocab.get_property("gender")
        assert result is not None
        assert "Person" in result["domain"]
        assert isinstance(result["range"], list)

    def test_name_property(self, vocab):
        result = vocab.get_property("name")
        assert result is not None
        assert "Thing" in result["domain"]

    def test_measured_property(self, vocab):
        result = vocab.get_property("measuredProperty")
        assert result is not None

    def test_unknown_property_returns_none(self, vocab):
        result = vocab.get_property("nonExistentPropXYZ")
        assert result is None

    def test_case_insensitive_property_lookup(self, vocab):
        result = vocab.get_property("Gender")
        assert result is not None

    def test_expected_range(self, vocab):
        result = vocab.get_expected_range("gender")
        assert result is not None
        assert isinstance(result, list)
        assert len(result) > 0


# =========================================================================
# Hierarchy
# =========================================================================

class TestHierarchy:
    """Test type hierarchy traversal."""

    def test_person_hierarchy(self, vocab):
        ancestors = vocab.get_type_hierarchy("Person")
        assert ancestors is not None
        assert "Thing" in ancestors

    def test_thing_hierarchy_empty(self, vocab):
        ancestors = vocab.get_type_hierarchy("Thing")
        assert ancestors is not None
        assert ancestors == []  # Thing is root

    def test_unknown_type_hierarchy_returns_none(self, vocab):
        ancestors = vocab.get_type_hierarchy("NonExistentTypeXYZ")
        assert ancestors is None

    def test_observation_has_ancestors(self, vocab):
        ancestors = vocab.get_type_hierarchy("Observation")
        assert ancestors is not None
        assert "Thing" in ancestors


# =========================================================================
# Property-for-type validation
# =========================================================================

class TestPropertyForType:
    """Test property-type compatibility checking."""

    def test_gender_valid_for_person(self, vocab):
        assert vocab.is_valid_property_for_type("gender", "Person") is True

    def test_name_valid_for_person(self, vocab):
        """name is on Thing, which Person inherits."""
        assert vocab.is_valid_property_for_type("name", "Person") is True

    def test_name_valid_for_place(self, vocab):
        """name is on Thing, which Place inherits."""
        assert vocab.is_valid_property_for_type("name", "Place") is True

    def test_properties_for_person(self, vocab):
        props = vocab.get_properties_for_type("Person", inherited=True)
        assert props is not None
        assert "gender" in props
        # Should include inherited properties from Thing
        assert "name" in props

    def test_properties_for_person_no_inherited(self, vocab):
        props = vocab.get_properties_for_type("Person", inherited=False)
        assert props is not None
        assert "gender" in props

    def test_properties_for_unknown_type_returns_none(self, vocab):
        props = vocab.get_properties_for_type("NonExistentTypeXYZ")
        assert props is None


# =========================================================================
# Search
# =========================================================================

class TestSearch:
    """Test fuzzy search functionality."""

    def test_search_types_person(self, vocab):
        results = vocab.search_types("Person")
        assert len(results) > 0
        assert results[0]["name"] == "Person"  # Exact match first

    def test_search_types_partial(self, vocab):
        results = vocab.search_types("Org", limit=5)
        assert len(results) > 0
        # Should find Organization
        names = [r["name"] for r in results]
        assert "Organization" in names

    def test_search_properties_gender(self, vocab):
        results = vocab.search_properties("gender")
        assert len(results) > 0
        assert results[0]["name"] == "gender"

    def test_search_properties_partial(self, vocab):
        results = vocab.search_properties("birth", limit=5)
        assert len(results) > 0
        names = [r["name"] for r in results]
        assert "birthDate" in names

    def test_search_nonsense_query_matches_nothing(self, vocab):
        results = vocab.search_types("zzzzxxyy999")
        assert results == []

    def test_search_respects_limit(self, vocab):
        results = vocab.search_types("a", limit=3)
        assert len(results) <= 3


# =========================================================================
# DC mapping bridge
# =========================================================================

class TestDCMapping:
    """Test Data Commons to schema.org mapping."""

    def test_person_maps_to_person(self, vocab):
        result = vocab.dc_type_to_schemaorg("Person")
        assert result == "Person"

    def test_bls_establishment_maps_to_organization(self, vocab):
        result = vocab.dc_type_to_schemaorg("BLSEstablishment")
        assert result == "Organization"

    def test_school_maps_to_educational_organization(self, vocab):
        result = vocab.dc_type_to_schemaorg("School")
        assert result == "EducationalOrganization"

    def test_unknown_dc_type_returns_none(self, vocab):
        result = vocab.dc_type_to_schemaorg("NonExistentDCType")
        assert result is None

    def test_gender_dc_property_maps(self, vocab):
        result = vocab.dc_property_to_schemaorg("gender")
        assert result == "gender"

    def test_age_is_dc_only(self, vocab):
        """age is DC-only (mapped to null in JSON)."""
        result = vocab.dc_property_to_schemaorg("age")
        assert result is None

    def test_race_is_dc_only(self, vocab):
        result = vocab.dc_property_to_schemaorg("race")
        assert result is None

    def test_naics_is_dc_only(self, vocab):
        result = vocab.dc_property_to_schemaorg("naics")
        assert result is None

    def test_is_known_dc_property(self, vocab):
        assert vocab.is_known_dc_property("age") is True
        assert vocab.is_known_dc_property("race") is True
        assert vocab.is_known_dc_property("gender") is True
        assert vocab.is_known_dc_property("totallyFakeProperty") is False

    def test_is_known_dc_type(self, vocab):
        assert vocab.is_known_dc_type("Person") is True
        assert vocab.is_known_dc_type("BLSEstablishment") is True
        assert vocab.is_known_dc_type("TotallyFakeType") is False

    def test_dc_enums(self, vocab):
        genders = vocab.get_dc_enums("GenderType")
        assert genders is not None
        assert "Male" in genders
        assert "Female" in genders

    def test_unknown_enum_returns_none(self, vocab):
        result = vocab.get_dc_enums("NonExistentEnum")
        assert result is None


# =========================================================================
# Combined known-property/type checks
# =========================================================================

class TestCombinedKnowledge:
    """Test combined schema.org + DC knowledge."""

    def test_gender_known_from_both(self, vocab):
        """gender is both a schema.org property and DC property."""
        assert vocab.is_known_property("gender") is True

    def test_age_known_from_dc_only(self, vocab):
        """age is DC-only, not in schema.org."""
        assert vocab.is_known_property("age") is True
        assert vocab.get_property("age") is None  # Not in schema.org
        assert vocab.is_known_dc_property("age") is True  # But known in DC

    def test_name_known_from_schemaorg(self, vocab):
        """name is a schema.org property."""
        assert vocab.is_known_property("name") is True

    def test_unknown_property_not_known(self, vocab):
        assert vocab.is_known_property("totallyFakePropertyXYZ") is False

    def test_person_known_type(self, vocab):
        assert vocab.is_known_type("Person") is True

    def test_bls_known_type(self, vocab):
        assert vocab.is_known_type("BLSEstablishment") is True

    def test_unknown_type_not_known(self, vocab):
        assert vocab.is_known_type("TotallyFakeTypeXYZ") is False


# =========================================================================
# Graceful degradation
# =========================================================================

class TestGracefulDegradation:
    """Test behavior when cache is missing."""

    def test_missing_cache_returns_none(self, tmp_path):
        """With empty cache dir, lookups return None gracefully."""
        SchemaOrgVocab.reset()
        vocab = SchemaOrgVocab(cache_dir=tmp_path)
        assert vocab.get_type("Person") is None
        assert vocab.get_property("gender") is None
        assert vocab.get_type_hierarchy("Person") is None
        assert vocab.search_types("Person") == []
        assert vocab.is_known_property("gender") is False
        assert vocab.is_known_type("Person") is False


# =========================================================================
# Singleton behavior
# =========================================================================

class TestSingleton:
    """Test singleton pattern."""

    def test_singleton_same_instance(self):
        v1 = SchemaOrgVocab.instance()
        v2 = SchemaOrgVocab.instance()
        assert v1 is v2

    def test_reset_creates_new_instance(self):
        v1 = SchemaOrgVocab.instance()
        SchemaOrgVocab.reset()
        v2 = SchemaOrgVocab.instance()
        assert v1 is not v2
