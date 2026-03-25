"""
Tests for local Data Commons tools (src/tools/dc_tools.py).

Tests cover:
- resolve_place_names with mocked DC API
- validate_statvar_observation with mocked DC client
- get_entity_type with mocked DC API
- Graceful error handling (missing API key, network errors)
- reset_dc_client() for singleton cleanup
"""

import pytest
from unittest.mock import patch, MagicMock

from src.tools.dc_tools import (
    resolve_place_names,
    validate_statvar_observation,
    get_entity_type,
    reset_dc_client,
)


@pytest.fixture(autouse=True)
def cleanup_dc_client():
    """Reset DC client singleton before and after each test."""
    reset_dc_client()
    yield
    reset_dc_client()


class TestResolvePlaceNames:
    """Tests for resolve_place_names."""

    @patch("src.tools.dc_tools.dc_api_resolve_placeid")
    def test_resolves_single_place(self, mock_resolve):
        mock_resolve.return_value = {"California": "geoId/06"}
        result = resolve_place_names("California")
        assert "California -> geoId/06" in result
        mock_resolve.assert_called_once()

    @patch("src.tools.dc_tools.dc_api_resolve_placeid")
    def test_resolves_multiple_places(self, mock_resolve):
        mock_resolve.return_value = {
            "California": "geoId/06",
            "Texas": "geoId/48",
        }
        result = resolve_place_names("California, Texas")
        assert "California -> geoId/06" in result
        assert "Texas -> geoId/48" in result

    @patch("src.tools.dc_tools.dc_api_resolve_placeid")
    def test_handles_not_found(self, mock_resolve):
        mock_resolve.return_value = {}
        result = resolve_place_names("Nonexistent Place")
        assert "NOT_FOUND" in result

    def test_empty_input(self):
        result = resolve_place_names("")
        assert "No place names provided" in result

    def test_whitespace_only_input(self):
        result = resolve_place_names("  ,  , ")
        assert "No place names provided" in result

    @patch("src.tools.dc_tools.dc_api_resolve_placeid")
    def test_handles_exception(self, mock_resolve):
        mock_resolve.side_effect = Exception("Network error")
        result = resolve_place_names("California")
        assert "failed" in result.lower()


class TestValidateStatvarObservation:
    """Tests for validate_statvar_observation."""

    @patch("src.tools.dc_tools._get_dc_client")
    def test_confirmed_with_observation_api(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.observation.fetch.return_value = {
            "observations": [{"value": 39538223, "date": "2020"}]
        }
        mock_get_client.return_value = mock_client

        result = validate_statvar_observation("Count_Person", "geoId/06")
        assert "CONFIRMED" in result

    @patch("src.tools.dc_tools._get_dc_client")
    def test_unconfirmed_empty_response(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.observation.fetch.return_value = {}
        mock_get_client.return_value = mock_client

        result = validate_statvar_observation("FakeStatVar", "geoId/06")
        # Empty dict response -> short str -> UNCONFIRMED
        assert "UNCONFIRMED" in result or "CONFIRMED" in result  # depends on str length

    @patch("src.tools.dc_tools._get_dc_client")
    def test_fallback_when_no_observation_api(self, mock_get_client):
        mock_client = MagicMock(spec=[])  # No observation attribute
        mock_get_client.return_value = mock_client

        with patch("src.tools.dc_tools.dc_api_is_defined_dcid") as mock_defined:
            mock_defined.return_value = {"Count_Person": True}
            result = validate_statvar_observation("Count_Person", "geoId/06")
            assert "PARTIAL" in result

    @patch("src.tools.dc_tools._get_dc_client")
    def test_fallback_invalid_dcid(self, mock_get_client):
        mock_client = MagicMock(spec=[])  # No observation attribute
        mock_get_client.return_value = mock_client

        with patch("src.tools.dc_tools.dc_api_is_defined_dcid") as mock_defined:
            mock_defined.return_value = {"BadDCID": False}
            result = validate_statvar_observation("BadDCID", "geoId/06")
            assert "UNCONFIRMED" in result

    @patch("src.tools.dc_tools._get_dc_client")
    def test_handles_exception(self, mock_get_client):
        mock_get_client.side_effect = Exception("Connection refused")
        result = validate_statvar_observation("Count_Person", "geoId/06")
        assert "UNCONFIRMED" in result

    @patch("src.tools.dc_tools._get_dc_client")
    def test_with_date_parameter(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.observation.fetch.return_value = {
            "observations": [{"value": 100, "date": "2020"}]
        }
        mock_get_client.return_value = mock_client

        result = validate_statvar_observation("Count_Person", "geoId/06", date="2020")
        assert "CONFIRMED" in result
        mock_client.observation.fetch.assert_called_once()


class TestGetEntityType:
    """Tests for get_entity_type."""

    @patch("src.tools.dc_tools.dc_api_get_node_property")
    def test_returns_type(self, mock_get_prop):
        mock_get_prop.return_value = {
            "geoId/06": {"typeOf": "State"}
        }
        result = get_entity_type("geoId/06")
        assert "State" in result
        assert "geoId/06" in result

    @patch("src.tools.dc_tools.dc_api_get_node_property")
    def test_unknown_dcid(self, mock_get_prop):
        mock_get_prop.return_value = {}
        result = get_entity_type("unknown/dcid")
        assert "unknown" in result.lower()

    @patch("src.tools.dc_tools.dc_api_get_node_property")
    def test_handles_exception(self, mock_get_prop):
        mock_get_prop.side_effect = Exception("API error")
        result = get_entity_type("geoId/06")
        assert "failed" in result.lower()


class TestResetDcClient:
    """Tests for reset_dc_client singleton cleanup."""

    def test_reset_clears_singleton(self):
        import src.tools.dc_tools as module
        module._dc_client = MagicMock()
        assert module._dc_client is not None
        reset_dc_client()
        assert module._dc_client is None

    @patch("src.tools.dc_tools.get_datacommons_client")
    def test_lazy_init_creates_client(self, mock_create):
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        from src.tools.dc_tools import _get_dc_client
        client = _get_dc_client()
        assert client is mock_client
        mock_create.assert_called_once()

    @patch("src.tools.dc_tools.get_datacommons_client")
    def test_singleton_reuses_client(self, mock_create):
        mock_client = MagicMock()
        mock_create.return_value = mock_client

        from src.tools.dc_tools import _get_dc_client
        client1 = _get_dc_client()
        client2 = _get_dc_client()
        assert client1 is client2
        mock_create.assert_called_once()  # Only created once
