"""Tests for src/agents/retry_config.py."""

import pytest
from unittest.mock import patch, MagicMock


class TestDefaultRetryOptions:
    """Test DEFAULT_RETRY_OPTIONS configuration."""

    def test_retry_options_values(self):
        from src.agents.retry_config import DEFAULT_RETRY_OPTIONS

        assert DEFAULT_RETRY_OPTIONS.attempts == 7
        assert DEFAULT_RETRY_OPTIONS.initial_delay == 5.0
        assert DEFAULT_RETRY_OPTIONS.max_delay == 60.0
        assert DEFAULT_RETRY_OPTIONS.exp_base == 2.0
        assert DEFAULT_RETRY_OPTIONS.jitter == 1.0

    def test_retry_options_status_codes(self):
        from src.agents.retry_config import DEFAULT_RETRY_OPTIONS

        expected_codes = [408, 429, 500, 502, 503, 504]
        assert list(DEFAULT_RETRY_OPTIONS.http_status_codes) == expected_codes

    def test_retry_options_includes_429(self):
        """429 (rate limit) must be retried."""
        from src.agents.retry_config import DEFAULT_RETRY_OPTIONS

        assert 429 in DEFAULT_RETRY_OPTIONS.http_status_codes

    def test_retry_options_includes_500(self):
        """500 (internal server error) must be retried."""
        from src.agents.retry_config import DEFAULT_RETRY_OPTIONS

        assert 500 in DEFAULT_RETRY_OPTIONS.http_status_codes


class TestCreateResilientModel:
    """Test create_resilient_model factory."""

    def test_returns_gemini_instance(self):
        from google.adk.models import Gemini
        from src.agents.retry_config import create_resilient_model

        result = create_resilient_model("gemini-2.5-flash")
        assert isinstance(result, Gemini)

    def test_model_name_preserved(self):
        from src.agents.retry_config import create_resilient_model

        result = create_resilient_model("gemini-2.5-flash")
        assert result.model == "gemini-2.5-flash"

    def test_retry_options_attached(self):
        from src.agents.retry_config import create_resilient_model, DEFAULT_RETRY_OPTIONS

        result = create_resilient_model("gemini-2.5-flash")
        assert result.retry_options is DEFAULT_RETRY_OPTIONS

    def test_different_model_names(self):
        from google.adk.models import Gemini
        from src.agents.retry_config import create_resilient_model

        for model_name in ["gemini-2.5-flash", "gemini-2.5-pro", "gemini-3-pro-preview"]:
            result = create_resilient_model(model_name)
            assert isinstance(result, Gemini)
            assert result.model == model_name


class TestAgentIntegration:
    """Test that agent factories accept create_resilient_model output."""

    def test_pvmap_generator_uses_resilient_model(self):
        """Verify create_pvmap_generator uses create_resilient_model."""
        import inspect
        from src.agents.pvmap_generator_agent import create_pvmap_generator

        source = inspect.getsource(create_pvmap_generator)
        assert "create_resilient_model" in source

    def test_feedback_agent_uses_resilient_model(self):
        """Verify create_feedback_agent uses create_resilient_model."""
        import inspect
        from src.agents.feedback_agent import create_feedback_agent

        source = inspect.getsource(create_feedback_agent)
        assert "create_resilient_model" in source

    def test_schema_selection_agent_uses_resilient_model(self):
        """Verify create_schema_selection_agent uses create_resilient_model."""
        import inspect
        from src.agents.schema_selection_agent import create_schema_selection_agent

        source = inspect.getsource(create_schema_selection_agent)
        assert "create_resilient_model" in source

    def test_sampling_agent_uses_resilient_model(self):
        """Verify create_sampling_agent uses create_resilient_model."""
        import inspect
        from src.agents.sampling_agent import create_sampling_agent

        source = inspect.getsource(create_sampling_agent)
        assert "create_resilient_model" in source

    def test_metadata_enrichment_agent_uses_resilient_model(self):
        """Verify _create_enrichment_agent uses create_resilient_model."""
        import inspect
        from src.agents.metadata_generation_agent import _create_enrichment_agent

        source = inspect.getsource(_create_enrichment_agent)
        assert "create_resilient_model" in source

    def test_dc_query_agent_uses_resilient_model(self):
        """Verify create_dc_query_agent uses create_resilient_model."""
        import inspect
        from src.agents.dc_query_agent import create_dc_query_agent

        source = inspect.getsource(create_dc_query_agent)
        assert "create_resilient_model" in source

    def test_enrichment_agent_uses_resilient_model(self):
        """Verify create_enrichment_agent uses create_resilient_model."""
        import inspect
        from src.agents.dc_query_agent import create_enrichment_agent

        source = inspect.getsource(create_enrichment_agent)
        assert "create_resilient_model" in source

    def test_error_resolver_agent_uses_resilient_model(self):
        """Verify create_error_resolver_agent uses create_resilient_model."""
        import inspect
        from src.agents.dc_query_agent import create_error_resolver_agent

        source = inspect.getsource(create_error_resolver_agent)
        assert "create_resilient_model" in source


class TestGeminiClientRetry:
    """Test that GeminiClient has retry options configured."""

    def test_gemini_client_uses_shared_retry_config(self):
        """Verify GeminiClient imports and uses DEFAULT_RETRY_OPTIONS."""
        import inspect
        from src.data_commons.api.gemini_client import GeminiClient

        source = inspect.getsource(GeminiClient.__init__)
        assert "DEFAULT_RETRY_OPTIONS" in source
        assert "retry_options" in source

    def test_gemini_client_retry_config_values(self):
        """Verify the shared retry config has expected values."""
        from src.agents.retry_config import DEFAULT_RETRY_OPTIONS

        assert DEFAULT_RETRY_OPTIONS.attempts == 7
        assert DEFAULT_RETRY_OPTIONS.initial_delay == 5.0
        assert DEFAULT_RETRY_OPTIONS.max_delay == 60.0
        assert 429 in DEFAULT_RETRY_OPTIONS.http_status_codes
        assert 500 in DEFAULT_RETRY_OPTIONS.http_status_codes
