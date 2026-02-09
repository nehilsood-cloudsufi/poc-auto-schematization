"""
Tests for dc_query_agent.py enrichment and error resolver factories.

Tests:
- create_enrichment_agent() broad + refinement modes
- create_error_resolver_agent() creation
- parse_statvars() parsing logic
- run_mcp_query() helper (mocked)
- MCP_TOOLS_INSTRUCTION constant
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from src.agents.dc_query_agent import (
    create_enrichment_agent,
    create_error_resolver_agent,
    parse_statvars,
    run_mcp_query,
    MCP_TOOLS_INSTRUCTION,
    ENRICHMENT_BROAD_INSTRUCTION,
    ENRICHMENT_REFINEMENT_INSTRUCTION,
    ERROR_RESOLVER_INSTRUCTION,
    _build_context_section,
)


# =============================================================================
# create_enrichment_agent() tests
# =============================================================================

class TestCreateEnrichmentAgent:
    """Tests for create_enrichment_agent factory."""

    @patch("src.agents.dc_query_agent.create_dc_mcp_toolset")
    def test_broad_discovery_attempt_0(self, mock_toolset):
        """Attempt 0 creates broad discovery agent."""
        mock_toolset.return_value = MagicMock()

        agent = create_enrichment_agent(
            mcp_url="http://localhost:3000/mcp",
            model="gemini-2.5-pro",
            data_context={"population_type": "Person"},
            attempt=0,
        )

        assert agent.name == "EnrichmentBroad"
        assert "Person" in agent.instruction

    @patch("src.agents.dc_query_agent.create_dc_mcp_toolset")
    def test_refinement_attempt_1(self, mock_toolset):
        """Attempt 1+ creates refinement agent with error context."""
        mock_toolset.return_value = MagicMock()

        agent = create_enrichment_agent(
            mcp_url="http://localhost:3000/mcp",
            model="gemini-2.5-pro",
            attempt=1,
            error_feedback="Missing observationAbout mapping",
            validation_error="Key 'State' not found",
        )

        assert "EnrichmentRefine_1" == agent.name
        assert "Missing observationAbout mapping" in agent.instruction
        assert "Key 'State' not found" in agent.instruction

    @patch("src.agents.dc_query_agent.create_dc_mcp_toolset")
    def test_refinement_no_errors(self, mock_toolset):
        """Refinement agent uses defaults when no errors provided."""
        mock_toolset.return_value = MagicMock()

        agent = create_enrichment_agent(
            mcp_url="http://localhost:3000/mcp",
            attempt=2,
        )

        assert "EnrichmentRefine_2" == agent.name
        assert "(no validation error)" in agent.instruction

    @patch("src.agents.dc_query_agent.create_dc_mcp_toolset")
    def test_broad_with_full_data_context(self, mock_toolset):
        """Broad agent includes data_context details."""
        mock_toolset.return_value = MagicMock()

        data_ctx = {
            "population_type": "Person",
            "statvar_pattern": "Count_Person_{Gender}",
            "dimension_columns": ["Gender", "Age"],
            "dimension_domains": {"Gender": ["Male", "Female"]},
        }

        agent = create_enrichment_agent(
            mcp_url="http://localhost:3000/mcp",
            data_context=data_ctx,
            attempt=0,
        )

        assert "Person" in agent.instruction
        assert "Count_Person_{Gender}" in agent.instruction
        assert "Gender" in agent.instruction

    @patch("src.agents.dc_query_agent.create_dc_mcp_toolset")
    def test_mcp_toolset_attached(self, mock_toolset):
        """Agent has MCP toolset attached."""
        mock_ts = MagicMock()
        mock_toolset.return_value = mock_ts

        agent = create_enrichment_agent(
            mcp_url="http://localhost:3000/mcp",
            attempt=0,
        )

        assert mock_ts in agent.tools


# =============================================================================
# create_error_resolver_agent() tests
# =============================================================================

class TestCreateErrorResolverAgent:
    """Tests for create_error_resolver_agent factory."""

    @patch("src.agents.dc_query_agent.create_dc_mcp_toolset")
    def test_basic_creation(self, mock_toolset):
        """Creates error resolver with validation error and PVMAP."""
        mock_toolset.return_value = MagicMock()

        agent = create_error_resolver_agent(
            mcp_url="http://localhost:3000/mcp",
            validation_error="Key 'State' not found in data",
            pvmap_csv="key,property,value\nState,observationAbout,dcid:geoId/{Data}",
        )

        assert agent.name == "ErrorResolver"
        assert "Key 'State' not found" in agent.instruction
        assert "key,property,value" in agent.instruction

    @patch("src.agents.dc_query_agent.create_dc_mcp_toolset")
    def test_empty_inputs(self, mock_toolset):
        """Handles empty validation_error and pvmap_csv."""
        mock_toolset.return_value = MagicMock()

        agent = create_error_resolver_agent(
            mcp_url="http://localhost:3000/mcp",
        )

        assert "(no validation error)" in agent.instruction
        assert "(no PVMAP available)" in agent.instruction


# =============================================================================
# parse_statvars() tests
# =============================================================================

class TestParseStatvars:
    """Tests for parse_statvars parsing function."""

    def test_standard_format(self):
        """Parse standard DCID/Description/Confidence format."""
        text = """
- DCID: Count_Person
  Description: Total population count
  Match confidence: HIGH

- DCID: Count_Person_Female
  Description: Female population count
  Match confidence: MEDIUM
"""
        result = parse_statvars(text)
        assert len(result) == 2
        assert result[0]["dcid"] == "Count_Person"
        assert result[0]["description"] == "Total population count"
        assert result[0]["confidence"] == "HIGH"
        assert result[1]["dcid"] == "Count_Person_Female"
        assert result[1]["confidence"] == "MEDIUM"

    def test_with_fixes_field(self):
        """Parse format with Fixes field (refinement output)."""
        text = """
- DCID: Count_Person_Employed
  Name: Employed persons
  Match confidence: HIGH
  Fixes: Resolves missing employment variable mapping
"""
        result = parse_statvars(text)
        assert len(result) == 1
        assert result[0]["fixes"] == "Resolves missing employment variable mapping"

    def test_with_observation_check(self):
        """Parse format with Observation check field."""
        text = """
- DCID: Count_Person
  Description: Population
  Match confidence: HIGH
  Observation check: CONFIRMED
"""
        result = parse_statvars(text)
        assert len(result) == 1
        assert result[0]["observation_check"] == "CONFIRMED"

    def test_empty_text(self):
        """Empty text returns empty list."""
        assert parse_statvars("") == []

    def test_no_dcids(self):
        """Text without DCIDs returns empty list."""
        text = "No matches found for the dataset."
        assert parse_statvars(text) == []

    def test_case_insensitive_dcid(self):
        """DCID label is case-insensitive."""
        text = "dcid: Count_Person\ndescription: Total pop"
        result = parse_statvars(text)
        assert len(result) == 1
        assert result[0]["dcid"] == "Count_Person"

    def test_default_confidence(self):
        """Missing confidence defaults to MEDIUM."""
        text = "- DCID: Count_Person\n  Description: Pop"
        result = parse_statvars(text)
        assert result[0]["confidence"] == "MEDIUM"


# =============================================================================
# run_mcp_query() tests
# =============================================================================

class TestRunMcpQuery:
    """Tests for run_mcp_query helper.

    Note: run_mcp_query uses lazy imports inside the function body,
    so we test at a higher level using integration-style mocking.
    """

    def test_function_signature(self):
        """run_mcp_query has correct signature (async, 3 params)."""
        import inspect
        sig = inspect.signature(run_mcp_query)
        params = list(sig.parameters.keys())
        assert params == ["mcp_url", "agent", "query"]
        assert inspect.iscoroutinefunction(run_mcp_query)

    @pytest.mark.asyncio
    async def test_query_failure_graceful(self):
        """Failed query returns error string instead of raising."""
        mock_agent = MagicMock()

        # Mock at the google.adk level (where Runner is imported from inside the function)
        mock_runner_cls = MagicMock()
        runner_instance = MagicMock()
        runner_instance.run.side_effect = Exception("Connection refused")
        mock_runner_cls.return_value = runner_instance

        with patch.dict("sys.modules", {
            "google.adk": MagicMock(Runner=mock_runner_cls),
        }):
            # Re-import to pick up the patched module
            import importlib
            import src.agents.dc_query_agent as dqa
            # Direct call - the lazy import will get the mocked Runner
            result = await run_mcp_query("http://localhost:3000/mcp", mock_agent, "Find pop")

            assert "MCP query failed" in result


# =============================================================================
# Instruction template tests
# =============================================================================

class TestInstructionTemplates:
    """Tests for instruction template constants."""

    def test_enrichment_broad_has_placeholders(self):
        """Broad instruction has context_section placeholder."""
        assert "{context_section}" in ENRICHMENT_BROAD_INSTRUCTION

    def test_enrichment_refinement_has_placeholders(self):
        """Refinement instruction has error placeholders."""
        assert "{context_section}" in ENRICHMENT_REFINEMENT_INSTRUCTION
        assert "{validation_error}" in ENRICHMENT_REFINEMENT_INSTRUCTION
        assert "{error_feedback}" in ENRICHMENT_REFINEMENT_INSTRUCTION

    def test_error_resolver_has_placeholders(self):
        """Error resolver instruction has error and pvmap placeholders."""
        assert "{validation_error}" in ERROR_RESOLVER_INSTRUCTION
        assert "{pvmap_csv}" in ERROR_RESOLVER_INSTRUCTION

    def test_mcp_tools_instruction_content(self):
        """MCP tools instruction mentions both tools."""
        assert "search_indicators" in MCP_TOOLS_INSTRUCTION
        assert "get_observations" in MCP_TOOLS_INSTRUCTION


# =============================================================================
# _build_context_section() tests
# =============================================================================

class TestBuildContextSection:
    """Tests for _build_context_section helper."""

    def test_empty_context(self):
        """Empty dict returns empty string."""
        assert _build_context_section({}) == ""

    def test_none_context(self):
        """None returns empty string."""
        assert _build_context_section(None) == ""

    def test_full_context(self):
        """Full data_context produces expected section."""
        ctx = {
            "population_type": "Person",
            "statvar_pattern": "Count_Person_{Gender}",
            "dimension_columns": ["Gender"],
            "dimension_domains": {"Gender": ["Male", "Female"]},
        }
        section = _build_context_section(ctx)
        assert "Population Type: Person" in section
        assert "Count_Person_{Gender}" in section
        assert "Gender" in section
        assert "Male" in section
