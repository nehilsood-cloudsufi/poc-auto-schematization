"""Tests for schema.org ADK tool functions."""

import pytest
from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab
from src.tools.schemaorg_tools import (
    lookup_schemaorg_type,
    lookup_schemaorg_property,
    search_schemaorg_vocabulary,
    validate_pvmap_property,
    get_schemaorg_type_hierarchy,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    SchemaOrgVocab.reset()
    yield
    SchemaOrgVocab.reset()


class TestLookupType:
    def test_known_type(self):
        result = lookup_schemaorg_type("Person")
        assert result["success"] is True
        assert result["data"] is not None
        assert "Thing" in result["data"]["parent"]

    def test_dc_type_mapping(self):
        result = lookup_schemaorg_type("BLSEstablishment")
        assert result["success"] is True
        assert "note" in result
        assert "Organization" in result["note"]

    def test_unknown_type(self):
        result = lookup_schemaorg_type("TotallyFakeXYZ")
        assert result["success"] is False
        assert result["error"] is not None


class TestLookupProperty:
    def test_known_property(self):
        result = lookup_schemaorg_property("gender")
        assert result["success"] is True
        assert result["data"] is not None

    def test_dc_only_property(self):
        result = lookup_schemaorg_property("age")
        assert result["success"] is True
        assert result["data"]["dc_only"] is True

    def test_unknown_property(self):
        result = lookup_schemaorg_property("totallyFakePropXYZ")
        assert result["success"] is False


class TestSearchVocabulary:
    def test_search_types(self):
        result = search_schemaorg_vocabulary("Person", search_type="types")
        assert result["success"] is True
        assert len(result["data"]["types"]) > 0

    def test_search_properties(self):
        result = search_schemaorg_vocabulary("gender", search_type="properties")
        assert result["success"] is True
        assert len(result["data"]["properties"]) > 0

    def test_search_both(self):
        result = search_schemaorg_vocabulary("education")
        assert result["success"] is True

    def test_search_no_results(self):
        result = search_schemaorg_vocabulary("zzzzxxyy999nonexistent")
        assert result["success"] is False


class TestValidateProperty:
    def test_gender_valid_for_person(self):
        result = validate_pvmap_property("gender", "Person")
        assert result["success"] is True
        assert result["data"]["compatible"] is True

    def test_dc_extension_property(self):
        result = validate_pvmap_property("age", "Person")
        assert result["success"] is True
        assert result["data"]["property_known"] is True
        assert result["data"]["compatible"] is True

    def test_dc_type_validation(self):
        result = validate_pvmap_property("gender", "BLSEstablishment")
        assert result["success"] is True
        assert result["data"]["type_known"] is True

    def test_unknown_property(self):
        result = validate_pvmap_property("fakePropXYZ", "Person")
        assert result["success"] is True
        assert result["data"]["property_known"] is False

    def test_unknown_type(self):
        result = validate_pvmap_property("gender", "FakeTypeXYZ")
        assert result["success"] is True
        assert result["data"]["type_known"] is False


class TestGetTypeHierarchy:
    def test_known_type(self):
        result = get_schemaorg_type_hierarchy("Person")
        assert result["success"] is True
        assert "Person" in result["data"]["hierarchy"]
        assert "Thing" in result["data"]["hierarchy"]

    def test_dc_type(self):
        result = get_schemaorg_type_hierarchy("BLSEstablishment")
        assert result["success"] is True
        assert "note" in result

    def test_unknown_type(self):
        result = get_schemaorg_type_hierarchy("TotallyFakeXYZ")
        assert result["success"] is False
        assert result["error"] is not None
