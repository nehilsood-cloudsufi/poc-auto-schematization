"""Tests for Schema.org MCP server tools (unit tests, no server required)."""

import pytest
from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab


@pytest.fixture(autouse=True)
def reset_singleton():
    SchemaOrgVocab.reset()
    yield
    SchemaOrgVocab.reset()


class TestLookupType:
    """Test the lookup_type MCP tool function."""

    def test_known_type(self):
        from src.data_commons.api.schemaorg_mcp_server import lookup_type
        result = lookup_type("Person")
        assert result["found"] is True
        assert result["type"] == "Person"
        assert "Thing" in result["parent"]
        assert len(result["properties"]) > 0

    def test_dc_type_mapping(self):
        from src.data_commons.api.schemaorg_mcp_server import lookup_type
        result = lookup_type("BLSEstablishment")
        assert result["found"] is True
        assert "Organization" in result.get("note", "")

    def test_unknown_type(self):
        from src.data_commons.api.schemaorg_mcp_server import lookup_type
        result = lookup_type("TotallyFakeXYZ")
        assert result["found"] is False


class TestLookupProperty:
    """Test the lookup_property MCP tool function."""

    def test_known_property(self):
        from src.data_commons.api.schemaorg_mcp_server import lookup_property
        result = lookup_property("gender")
        assert result["found"] is True
        assert "Person" in result["domain"]

    def test_dc_only_property(self):
        from src.data_commons.api.schemaorg_mcp_server import lookup_property
        result = lookup_property("age")
        assert result["found"] is True
        assert result.get("dc_only") is True

    def test_unknown_property(self):
        from src.data_commons.api.schemaorg_mcp_server import lookup_property
        result = lookup_property("totallyFakeXYZ")
        assert result["found"] is False


class TestSearchVocabulary:
    """Test the search_vocabulary MCP tool function."""

    def test_search_types(self):
        from src.data_commons.api.schemaorg_mcp_server import search_vocabulary
        result = search_vocabulary("Person", search_in="types")
        assert result["matches"] > 0

    def test_search_both(self):
        from src.data_commons.api.schemaorg_mcp_server import search_vocabulary
        result = search_vocabulary("education")
        assert result["matches"] > 0


class TestValidateMapping:
    """Test the validate_mapping MCP tool function."""

    def test_valid_mapping(self):
        from src.data_commons.api.schemaorg_mcp_server import validate_mapping
        result = validate_mapping("gender", "Person")
        assert result["property_known"] is True
        assert result["type_known"] is True
        assert result["compatible"] is True

    def test_dc_extension(self):
        from src.data_commons.api.schemaorg_mcp_server import validate_mapping
        result = validate_mapping("age", "Person")
        assert result["property_known"] is True
        assert result["compatible"] is True

    def test_unknown_property(self):
        from src.data_commons.api.schemaorg_mcp_server import validate_mapping
        result = validate_mapping("fakeXYZ", "Person")
        assert result["property_known"] is False


class TestGetTypeHierarchy:
    """Test the get_type_hierarchy MCP tool function."""

    def test_person_hierarchy(self):
        from src.data_commons.api.schemaorg_mcp_server import get_type_hierarchy
        result = get_type_hierarchy("Person")
        assert result["found"] is True
        assert "Person" in result["hierarchy"]
        assert "Thing" in result["hierarchy"]

    def test_dc_type_hierarchy(self):
        from src.data_commons.api.schemaorg_mcp_server import get_type_hierarchy
        result = get_type_hierarchy("School")
        assert result["found"] is True

    def test_unknown_type(self):
        from src.data_commons.api.schemaorg_mcp_server import get_type_hierarchy
        result = get_type_hierarchy("TotallyFakeXYZ")
        assert result["found"] is False


class TestToolsetFactory:
    """Test the toolset factory (import only, no server needed)."""

    def test_factory_creates_toolset(self):
        from src.data_commons.api.schemaorg_mcp_toolset_factory import create_schemaorg_mcp_toolset
        toolset = create_schemaorg_mcp_toolset()
        assert toolset is not None


class TestManagerInit:
    """Test manager initialization (no server start)."""

    def test_manager_init(self):
        from src.data_commons.api.schemaorg_mcp_manager import SchemaOrgMCPManager
        manager = SchemaOrgMCPManager(port=3001)
        assert manager.port == 3001
        assert manager.mcp_url == "http://localhost:3001/mcp"
        assert manager.process is None
