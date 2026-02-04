"""
Pytest configuration for MCP tests.

This module provides:
- Pytest markers for integration tests
- Skip conditions for tests requiring MCP server
- Shared fixtures for MCP testing
"""

import os
import pytest


def pytest_configure(config):
    """Register custom markers."""
    config.addinivalue_line(
        "markers",
        "mcp_integration: mark test as requiring MCP server (deselect with '-m \"not mcp_integration\"')"
    )
    config.addinivalue_line(
        "markers",
        "requires_api_keys: mark test as requiring API keys (GEMINI_API_KEY, DC_API_KEY)"
    )


# Skip conditions
requires_mcp_server = pytest.mark.skipif(
    os.getenv("RUN_MCP_INTEGRATION_TESTS", "").lower() != "true",
    reason="MCP integration tests disabled. Set RUN_MCP_INTEGRATION_TESTS=true to enable."
)

requires_api_keys = pytest.mark.skipif(
    not (os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")) or not os.getenv("DC_API_KEY"),
    reason="Requires GEMINI_API_KEY/GOOGLE_API_KEY and DC_API_KEY environment variables"
)

requires_input_datasets = pytest.mark.skipif(
    not os.path.exists("input") or not any(
        d.is_dir() for d in (os.scandir("input") if os.path.exists("input") else [])
    ),
    reason="Requires datasets in input/ directory"
)
