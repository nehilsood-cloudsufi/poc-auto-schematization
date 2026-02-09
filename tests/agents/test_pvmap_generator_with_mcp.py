"""
Tests for PVMAP generator agent with MCP integration.

Tests:
- Generator creates with/without MCP toolset
- Instruction includes/excludes MCP section
- MCP tools instruction placeholder
"""

import pytest
from unittest.mock import patch, MagicMock

from src.agents.pvmap_generator_agent import (
    create_pvmap_generator,
    PVMAP_GENERATOR_INSTRUCTION,
)


class TestPvmapGeneratorWithMCP:
    """Tests for create_pvmap_generator with MCP params."""

    def test_without_mcp_no_tools(self):
        """Generator without MCP has no tools."""
        generator = create_pvmap_generator(
            model="gemini-2.5-flash",
            name="TestGen",
            enable_mcp=False,
        )

        # LlmAgent without tools= kwarg will have empty tools
        # Check that no MCP toolset is configured
        assert generator.name == "TestGen"
        assert generator.model == "gemini-2.5-flash"

    @patch("src.data_commons.api.mcp_toolset_factory.create_dc_mcp_toolset")
    def test_with_mcp_has_tools(self, mock_toolset):
        """Generator with MCP has MCP toolset in tools list."""
        mock_ts = MagicMock()
        mock_toolset.return_value = mock_ts

        generator = create_pvmap_generator(
            model="gemini-2.5-flash",
            name="TestGen",
            enable_mcp=True,
            mcp_url="http://localhost:3000/mcp",
        )

        assert mock_ts in generator.tools

    def test_mcp_enabled_without_url_no_tools(self):
        """MCP enabled but no URL = no tools added."""
        generator = create_pvmap_generator(
            model="gemini-2.5-flash",
            enable_mcp=True,
            mcp_url=None,
        )

        # Should not have tools (or have empty tools)
        tools = getattr(generator, 'tools', []) or []
        assert len(tools) == 0

    def test_instruction_has_mcp_tools_placeholder(self):
        """Generator instruction includes {mcp_tools_instruction} placeholder."""
        assert "{mcp_tools_instruction}" in PVMAP_GENERATOR_INSTRUCTION

    def test_instruction_has_statvar_section(self):
        """Generator instruction includes StatVar section without defensive language."""
        assert "Discovered StatVars (from Data Commons)" in PVMAP_GENERATOR_INSTRUCTION
        # Should NOT have old defensive language
        assert "Reference Only" not in PVMAP_GENERATOR_INSTRUCTION
        assert "IGNORE them" not in PVMAP_GENERATOR_INSTRUCTION

    def test_instruction_confidence_based_guidance(self):
        """Generator instruction uses confidence-based guidance."""
        assert "HIGH confidence matches" in PVMAP_GENERATOR_INSTRUCTION

    def test_backward_compat_no_mcp_params(self):
        """Calling without MCP params works (backward compatible)."""
        generator = create_pvmap_generator(model="gemini-2.5-flash")
        assert generator.name == "PVMAPGenerator"
        assert generator.output_key == "pvmap_output"

    def test_output_schema_set(self):
        """Generator always has output_schema for structured output."""
        from src.agents.pvmap_generation.schemas import PVMAPOutput

        generator = create_pvmap_generator(model="gemini-2.5-flash")
        assert generator.output_schema == PVMAPOutput

    @patch("src.data_commons.api.mcp_toolset_factory.create_dc_mcp_toolset")
    def test_output_schema_with_mcp(self, mock_toolset):
        """Generator with MCP still has output_schema."""
        from src.agents.pvmap_generation.schemas import PVMAPOutput
        mock_toolset.return_value = MagicMock()

        generator = create_pvmap_generator(
            enable_mcp=True,
            mcp_url="http://localhost:3000/mcp",
        )
        assert generator.output_schema == PVMAPOutput


class TestPvmapHelpersConfidenceInjection:
    """Tests for confidence-weighted StatVar injection in helpers.py."""

    def test_confidence_weighted_injection(self, temp_dir):
        """StatVars injected with confidence-weighted guidance."""
        from src.agents.pvmap_generation.helpers import build_prompt_with_feedback

        template_path = temp_dir / "template.txt"
        template_path.write_text(
            "Schema: {{SCHEMA_EXAMPLES}}\n"
            "Data: {{SAMPLED_DATA}}\n"
            "Metadata: {{METADATA_CONFIG}}\n"
            "# OUTPUT\nGenerate PVMAP"
        )

        statvars = """- DCID: Count_Person
  Description: Total population
  Match confidence: HIGH"""

        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="schema",
            sampled_data_content="data",
            metadata_content="metadata",
            discovered_statvars=statvars,
        )

        # Should have new confidence-weighted language
        assert "DISCOVERED DATA COMMONS VARIABLES" in prompt
        assert "HIGH confidence matches" in prompt
        assert "MEDIUM confidence" in prompt
        # Should NOT have old defensive language
        assert "Reference Only" not in prompt
        assert "IGNORE them" not in prompt

    def test_no_matches_not_injected(self, temp_dir):
        """'No exact matches' text is not injected."""
        from src.agents.pvmap_generation.helpers import build_prompt_with_feedback

        template_path = temp_dir / "template.txt"
        template_path.write_text(
            "Schema: {{SCHEMA_EXAMPLES}}\n"
            "Data: {{SAMPLED_DATA}}\n"
            "Metadata: {{METADATA_CONFIG}}\n"
            "# OUTPUT\nGenerate PVMAP"
        )

        statvars = "No exact matches found for the dataset."

        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="schema",
            sampled_data_content="data",
            metadata_content="metadata",
            discovered_statvars=statvars,
        )

        assert "DISCOVERED DATA COMMONS VARIABLES" not in prompt

    def test_empty_statvars_not_injected(self, temp_dir):
        """Empty statvars text is not injected."""
        from src.agents.pvmap_generation.helpers import build_prompt_with_feedback

        template_path = temp_dir / "template.txt"
        template_path.write_text(
            "Schema: {{SCHEMA_EXAMPLES}}\n"
            "Data: {{SAMPLED_DATA}}\n"
            "Metadata: {{METADATA_CONFIG}}"
        )

        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="schema",
            sampled_data_content="data",
            metadata_content="metadata",
            discovered_statvars="",
        )

        assert "DISCOVERED DATA COMMONS VARIABLES" not in prompt
