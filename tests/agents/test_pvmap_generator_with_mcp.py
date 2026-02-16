"""
Tests for PVMAP generator agent with MCP integration.

Tests:
- Generator creates with/without MCP toolset
- Template file includes required sections and placeholders
- MCP tools instruction placeholder in template
"""

import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

from src.agents.pvmap_generator_agent import (
    create_pvmap_generator,
    PVMAP_GENERATOR_INSTRUCTION,
)


# Path to the prompt template (source of truth for generator instruction)
TEMPLATE_PATH = Path(__file__).parent.parent.parent / "src" / "resources" / "prompts" / "improved_pvmap_prompt.txt"


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
        # model is now a Gemini instance with retry options
        from google.adk.models import Gemini
        if isinstance(generator.model, Gemini):
            assert generator.model.model == "gemini-2.5-flash"
        else:
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

    def test_mcp_enabled_without_url_no_mcp_tools(self):
        """MCP enabled but no URL = no MCP toolset added (schema.org + local DC tools present)."""
        generator = create_pvmap_generator(
            model="gemini-2.5-flash",
            enable_mcp=True,
            mcp_url=None,
        )

        # Should have schema.org tools + local DC tools but no MCP toolset
        tools = getattr(generator, 'tools', []) or []
        assert len(tools) == 8  # 5 schema.org + 3 local DC tools
        tool_names = [t.__name__ for t in tools if callable(t)]
        assert "lookup_schemaorg_type" in tool_names
        assert "lookup_schemaorg_property" in tool_names
        assert "search_schemaorg_vocabulary" in tool_names
        assert "validate_pvmap_property" in tool_names
        assert "get_schemaorg_type_hierarchy" in tool_names
        assert "resolve_place_names" in tool_names
        assert "validate_statvar_observation" in tool_names
        assert "get_entity_type" in tool_names

    def test_instruction_references_populated_prompt(self):
        """Generator instruction references {populated_pvmap_prompt} state variable."""
        assert "{populated_pvmap_prompt}" in PVMAP_GENERATOR_INSTRUCTION

    def test_template_has_mcp_tools_placeholder(self):
        """Template file includes {{MCP_TOOLS_INSTRUCTION}} placeholder."""
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "{{MCP_TOOLS_INSTRUCTION}}" in template

    def test_template_has_statvar_section(self):
        """Template file includes StatVar discovery section."""
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "Discovered StatVars (from Data Commons)" in template
        # Should NOT have old defensive language
        assert "Reference Only" not in template
        assert "IGNORE them" not in template

    def test_template_has_confidence_based_guidance(self):
        """Template uses confidence-based guidance for StatVar matches."""
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "HIGH confidence matches" in template

    def test_template_has_all_placeholders(self):
        """Template has all required placeholders."""
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "{{DATA_CONTEXT}}" in template
        assert "{{SCHEMA_EXAMPLES}}" in template
        assert "{{SAMPLED_DATA}}" in template
        assert "{{METADATA_CONFIG}}" in template
        assert "{{ERROR_FEEDBACK}}" in template
        assert "{{STATVAR_SUMMARY}}" in template
        assert "{{MCP_TOOLS_INSTRUCTION}}" in template

    def test_template_has_no_dcid_rule(self):
        """Template bans dcid: prefix in Rule 1."""
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert "NO `dcid:` PREFIX" in template
        assert "dcid:Person" in template  # WRONG example
        assert "populationType,Person" in template  # CORRECT example

    def test_template_has_json_output_format(self):
        """Template describes JSON output format (not CSV)."""
        template = TEMPLATE_PATH.read_text(encoding="utf-8")
        assert '"format_detected"' in template
        assert '"pvmap_rows"' in template
        assert '"mappings"' in template

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


class TestPvmapHelpersPromptPopulation:
    """Tests for build_prompt_with_feedback template population."""

    def test_all_placeholders_replaced(self, temp_dir):
        """All template placeholders get replaced."""
        from src.agents.pvmap_generation.helpers import build_prompt_with_feedback

        template_path = temp_dir / "template.txt"
        template_path.write_text(
            "Context: {{DATA_CONTEXT}}\n"
            "Schema: {{SCHEMA_EXAMPLES}}\n"
            "Data: {{SAMPLED_DATA}}\n"
            "Metadata: {{METADATA_CONFIG}}\n"
            "Feedback: {{ERROR_FEEDBACK}}\n"
            "StatVars: {{STATVAR_SUMMARY}}\n"
            "MCP: {{MCP_TOOLS_INSTRUCTION}}\n"
        )

        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="my_schema",
            sampled_data_content="my_data",
            metadata_content="my_metadata",
            error_feedback="fix the key",
            discovered_statvars="Count_Person HIGH",
            data_context="column table here",
        )

        assert "my_schema" in prompt
        assert "my_data" in prompt
        assert "my_metadata" in prompt
        assert "fix the key" in prompt
        assert "Count_Person HIGH" in prompt
        assert "column table here" in prompt
        # No unreplaced placeholders
        assert "{{" not in prompt

    def test_empty_optionals(self, temp_dir):
        """Empty optional fields produce clean output."""
        from src.agents.pvmap_generation.helpers import build_prompt_with_feedback

        template_path = temp_dir / "template.txt"
        template_path.write_text(
            "Schema: {{SCHEMA_EXAMPLES}}\n"
            "Data: {{SAMPLED_DATA}}\n"
            "Metadata: {{METADATA_CONFIG}}\n"
            "Feedback: {{ERROR_FEEDBACK}}\n"
            "StatVars: {{STATVAR_SUMMARY}}\n"
        )

        prompt = build_prompt_with_feedback(
            template_path=template_path,
            schema_content="schema",
            sampled_data_content="data",
            metadata_content="metadata",
        )

        assert "Feedback: \n" in prompt  # Empty feedback
        assert "StatVars: \n" in prompt  # Empty statvars
