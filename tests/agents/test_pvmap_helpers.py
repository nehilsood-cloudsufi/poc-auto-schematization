"""
Tests for PVMAP generation helper functions.

Tests simple Python functions (not agents).
"""

import pytest
from pathlib import Path
from src.agents.pvmap_generation.helpers import (
    build_prompt_with_feedback,
    convert_pvmap_output_to_csv,
    escape_csv_value,
    extract_csv,
    read_file_content
)
from src.agents.pvmap_generation.schemas import (
    PVMAP_OUTPUT_SCHEMA,
    PropertyValuePair,
    PVMAPOutput,
    PVMAPRow,
)


def test_read_file_content(temp_dir):
    """Test reading file content."""
    test_file = temp_dir / "test.txt"
    test_file.write_text("Hello World")
    
    content = read_file_content(test_file)
    assert content == "Hello World"


def test_build_prompt_with_feedback_basic(temp_dir):
    """Test basic prompt building without error feedback."""
    # Create template file
    template_path = temp_dir / "template.txt"
    template_path.write_text(
        "Schema: {{SCHEMA_EXAMPLES}}\n"
        "Data: {{SAMPLED_DATA}}\n"
        "Metadata: {{METADATA_CONFIG}}"
    )
    
    schema = "Example schema content"
    data = "col1,col2\n1,2"
    metadata = "param,value\nunit,Count"
    
    prompt = build_prompt_with_feedback(
        template_path=template_path,
        schema_content=schema,
        sampled_data_content=data,
        metadata_content=metadata
    )
    
    assert "Schema: Example schema content" in prompt
    assert "Data: col1,col2" in prompt
    assert "Metadata: param,value" in prompt


def test_build_prompt_with_feedback_missing_schema(temp_dir):
    """Test prompt building with missing schema (should use fallback)."""
    template_path = temp_dir / "template.txt"
    template_path.write_text("Schema: {{SCHEMA_EXAMPLES}}")
    
    prompt = build_prompt_with_feedback(
        template_path=template_path,
        schema_content=None,
        sampled_data_content="data",
        metadata_content="metadata"
    )
    
    assert "No schema example files found" in prompt
    assert "Data Commons schema conventions" in prompt


def test_build_prompt_with_error_feedback(temp_dir):
    """Test prompt building with error feedback injection via {{ERROR_FEEDBACK}}."""
    template_path = temp_dir / "template.txt"
    template_path.write_text(
        "Generate PVMAP for {{SAMPLED_DATA}}\n"
        "Feedback: {{ERROR_FEEDBACK}}"
    )

    error_feedback = "Error: Missing property mapping for column 'population'"

    prompt = build_prompt_with_feedback(
        template_path=template_path,
        schema_content="schema",
        sampled_data_content="data",
        metadata_content="metadata",
        error_feedback=error_feedback
    )

    assert "Missing property mapping" in prompt
    assert error_feedback in prompt


def test_build_prompt_missing_template(temp_dir):
    """Test prompt building with missing template file."""
    nonexistent = temp_dir / "nonexistent.txt"
    
    with pytest.raises(FileNotFoundError):
        build_prompt_with_feedback(
            template_path=nonexistent,
            schema_content="schema",
            sampled_data_content="data",
            metadata_content="metadata"
        )


def test_build_prompt_missing_required_content(temp_dir):
    """Test prompt building with missing required content."""
    template_path = temp_dir / "template.txt"
    template_path.write_text("Template")
    
    # Missing sampled_data_content
    with pytest.raises(ValueError, match="Sampled data content is required"):
        build_prompt_with_feedback(
            template_path=template_path,
            schema_content="schema",
            sampled_data_content="",
            metadata_content="metadata"
        )
    
    # Missing metadata_content
    with pytest.raises(ValueError, match="Metadata content is required"):
        build_prompt_with_feedback(
            template_path=template_path,
            schema_content="schema",
            sampled_data_content="data",
            metadata_content=""
        )


def test_extract_csv_from_code_block():
    """Test extracting CSV from code block marker."""
    output = """
Here's the PVMAP:

```csv
key,property,value
State,stateFIPS,{Data}
Year,observationDate,{Data}
Population,populationType,Person,measuredProperty,count,value,{Number}
```

This mapping covers all columns.
"""
    
    csv = extract_csv(output)
    assert csv is not None
    assert csv.startswith("key,property,value")
    assert "State,stateFIPS,{Data}" in csv
    assert "Population,populationType,Person" in csv


def test_extract_csv_from_code_block_without_csv_marker():
    """Test extracting CSV from code block without 'csv' marker."""
    output = """
```
key,property,value
Col1,prop1,{Data}
Col2,prop2,{Number}
```
"""
    
    csv = extract_csv(output)
    assert csv is not None
    assert csv.startswith("key,property,value")


def test_extract_csv_inline():
    """Test extracting inline CSV without code block."""
    output = """
Here is the PVMAP:

key,property,value
State,stateFIPS,{Data}
Year,observationDate,{Data}
Population,populationType,Person,measuredProperty,count,value,{Number}

That's all!
"""
    
    csv = extract_csv(output)
    assert csv is not None
    assert csv.startswith("key,property,value")
    assert "State,stateFIPS" in csv


def test_extract_csv_with_comments():
    """Test extracting CSV with comment lines."""
    output = """
```csv
key,property,value
# This is a comment
State,stateFIPS,{Data}
# Another comment
Year,observationDate,{Data}
```
"""
    
    csv = extract_csv(output)
    assert csv is not None
    assert "# This is a comment" in csv
    assert "# Another comment" in csv


def test_extract_csv_passthrough_format():
    """Test extracting CSV in passthrough format (observationAbout)."""
    output = """
```csv
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
variableMeasured,variableMeasured,{Data}
value,value,{Number}
```
"""
    
    csv = extract_csv(output)
    assert csv is not None
    # Should normalize by adding key,property,value header
    assert csv.startswith("key,property,value")
    assert "observationAbout,observationAbout,{Data}" in csv


def test_extract_csv_not_found():
    """Test extraction when no CSV is found."""
    output = """
This is just some text without any CSV content.
No key,property,value header anywhere.
Just plain text.
"""
    
    csv = extract_csv(output)
    assert csv is None


def test_extract_csv_with_empty_lines():
    """Test extracting CSV with empty lines."""
    output = """
key,property,value
State,stateFIPS,{Data}

Year,observationDate,{Data}

Population,populationType,Person
"""
    
    csv = extract_csv(output)
    assert csv is not None
    # Should stop at 2+ consecutive empty lines
    # So should only get first 3 rows
    lines = csv.split('\n')
    assert len(lines) >= 3


def test_extract_csv_multiple_code_blocks():
    """Test extracting CSV when multiple code blocks exist (takes longest)."""
    output = """
First attempt:
```csv
key,property,value
Col1,prop1,{Data}
```

Better version:
```csv
key,property,value
Col1,prop1,{Data}
Col2,prop2,{Number}
Col3,prop3,{Data}
```
"""

    csv = extract_csv(output)
    assert csv is not None
    # Should extract the longer (second) CSV
    assert "Col3,prop3,{Data}" in csv


def test_build_prompt_data_context_placeholder(temp_dir):
    """Verify {{DATA_CONTEXT}} is replaced in template."""
    template_path = temp_dir / "template.txt"
    template_path.write_text(
        "Before\n"
        "{{DATA_CONTEXT}}\n"
        "After\n"
        "Schema: {{SCHEMA_EXAMPLES}}\n"
        "Data: {{SAMPLED_DATA}}\n"
        "Metadata: {{METADATA_CONFIG}}"
    )

    data_context = "## 1. TOPOLOGY\n- This is enriched context"

    prompt = build_prompt_with_feedback(
        template_path=template_path,
        schema_content="schema",
        sampled_data_content="data",
        metadata_content="metadata",
        data_context=data_context,
    )

    assert "## 1. TOPOLOGY" in prompt
    assert "This is enriched context" in prompt
    assert "{{DATA_CONTEXT}}" not in prompt


def test_build_prompt_data_context_default(temp_dir):
    """Verify {{DATA_CONTEXT}} gets default fallback when not provided."""
    template_path = temp_dir / "template.txt"
    template_path.write_text(
        "Context: {{DATA_CONTEXT}}\n"
        "Schema: {{SCHEMA_EXAMPLES}}\n"
        "Data: {{SAMPLED_DATA}}\n"
        "Metadata: {{METADATA_CONFIG}}"
    )

    prompt = build_prompt_with_feedback(
        template_path=template_path,
        schema_content="schema",
        sampled_data_content="data",
        metadata_content="metadata",
        data_context=None,
    )

    assert "{{DATA_CONTEXT}}" not in prompt
    assert "Data context analysis not available" in prompt


# =============================================================================
# Phase 1 regression tests: dcid: prefix prevention
# =============================================================================


class TestDcidPrefixPrevention:
    """Regression tests for dcid: prefix hallucination bug."""

    def test_schema_description_no_dcid_xxx(self):
        """PVMAP_OUTPUT_SCHEMA must NOT contain 'dcid:XXX' pattern that teaches LLM to produce dcid: prefixes."""
        import json
        schema_str = json.dumps(PVMAP_OUTPUT_SCHEMA)
        assert "dcid:XXX" not in schema_str, (
            "PVMAP_OUTPUT_SCHEMA still contains 'dcid:XXX' — "
            "this teaches the LLM to produce dcid: prefixes"
        )

    def test_schema_description_says_no_dcid(self):
        """PVMAP_OUTPUT_SCHEMA value description should explicitly say NO dcid: prefix."""
        value_desc = (
            PVMAP_OUTPUT_SCHEMA["properties"]["pvmap_rows"]["items"]
            ["properties"]["mappings"]["items"]["properties"]["value"]["description"]
        )
        assert "NO dcid:" in value_desc or "no dcid:" in value_desc.lower()

    def test_pydantic_schema_no_dcid(self):
        """Pydantic PropertyValuePair description should not contain dcid:XXX."""
        field_info = PropertyValuePair.model_fields["value"]
        assert "dcid:XXX" not in field_info.description

    def test_convert_pvmap_output_strips_dcid_prefix(self):
        """convert_pvmap_output_to_csv must strip dcid: prefix from values."""
        output = PVMAPOutput(
            format_detected="raw",
            pvmap_rows=[
                PVMAPRow(key="Year", mappings=[
                    PropertyValuePair(property="observationDate", value="{Number}")
                ]),
                PVMAPRow(key="Population", mappings=[
                    PropertyValuePair(property="populationType", value="dcid:Person"),
                    PropertyValuePair(property="measuredProperty", value="dcid:count"),
                    PropertyValuePair(property="value", value="{Number}"),
                ]),
            ],
            validation_notes="test",
            confidence="high",
        )

        csv = convert_pvmap_output_to_csv(output)
        assert "dcid:Person" not in csv
        assert "dcid:count" not in csv
        assert "Person" in csv
        assert "count" in csv

    def test_convert_pvmap_output_strips_dcs_prefix(self):
        """convert_pvmap_output_to_csv must strip dcs: prefix from values."""
        output = PVMAPOutput(
            format_detected="raw",
            pvmap_rows=[
                PVMAPRow(key="Pop", mappings=[
                    PropertyValuePair(property="populationType", value="dcs:Person"),
                    PropertyValuePair(property="value", value="{Number}"),
                ]),
            ],
            validation_notes="test",
            confidence="high",
        )

        csv = convert_pvmap_output_to_csv(output)
        assert "dcs:Person" not in csv
        assert "Person" in csv

    def test_escape_csv_value_strips_dcid(self):
        """escape_csv_value must strip dcid: and dcs: prefixes."""
        assert escape_csv_value("dcid:Person") == "Person"
        assert escape_csv_value("dcs:Person") == "Person"
        # Should NOT strip when followed by { (placeholder)
        assert escape_csv_value("dcid:{Data}") == "dcid:{Data}"

    def test_convert_preserves_placeholders(self):
        """Ensure {Data} and {Number} placeholders survive conversion."""
        output = PVMAPOutput(
            format_detected="raw",
            pvmap_rows=[
                PVMAPRow(key="State", mappings=[
                    PropertyValuePair(property="observationAbout", value="{Data}")
                ]),
            ],
            validation_notes="test",
            confidence="high",
        )
        csv = convert_pvmap_output_to_csv(output)
        assert "{Data}" in csv


# =============================================================================
# Prompt v2 template validation
# =============================================================================


class TestPromptV2Template:
    """Validate the v2 prompt template has all required placeholders."""

    @pytest.fixture
    def v2_template(self):
        prompt_path = Path(__file__).parent.parent.parent / "src" / "resources" / "prompts" / "improved_pvmap_prompt_v2.txt"
        if not prompt_path.exists():
            pytest.skip("v2 prompt not yet created")
        return prompt_path.read_text(encoding="utf-8")

    def test_has_all_placeholders(self, v2_template):
        required = [
            "{{DATA_CONTEXT}}",
            "{{SCHEMA_EXAMPLES}}",
            "{{SAMPLED_DATA}}",
            "{{METADATA_CONFIG}}",
            "{{ERROR_FEEDBACK}}",
            "{{STATVAR_SUMMARY}}",
            "{{MCP_TOOLS_INSTRUCTION}}",
        ]
        for placeholder in required:
            assert placeholder in v2_template, f"Missing placeholder: {placeholder}"

    def test_has_xml_sections(self, v2_template):
        """v2 uses XML tags for structure."""
        for tag in ["<task>", "<rules>", "<examples>", "<guardrails>", "<output_format>", "<statvar_decision_tree>"]:
            assert tag in v2_template, f"Missing XML section: {tag}"

    def test_has_rule4_unit_scaling(self, v2_template):
        """v2 should have Rule 4 for unit/scaling extraction."""
        assert "Rule 4: UNIT & SCALING" in v2_template

    def test_has_standard_wide_example(self, v2_template):
        """v2 Example 1 should be Standard Wide (not SDMX BIS example)."""
        assert "Standard Wide" in v2_template
        assert "BIS Central Bank Policy Rate" not in v2_template  # Old example removed

    def test_syntax_reference_split(self, v2_template):
        """Syntax reference should separate core from advanced operators."""
        assert "Core)" in v2_template
        assert "Advanced Operators (rare" in v2_template

    def test_statvar_decision_tree_has_common_types(self, v2_template):
        """Decision tree should list common populationType values."""
        tree_start = v2_template.find("<statvar_decision_tree>")
        tree_end = v2_template.find("</statvar_decision_tree>")
        tree = v2_template[tree_start:tree_end]
        for val in ["Person", "Household", "EconomicActivity", "measuredProperty", "statType"]:
            assert val in tree, f"Decision tree missing: {val}"

    def test_no_dcid_in_rules(self, v2_template):
        """Rules section should not suggest using dcid: prefix."""
        # Find rules section
        rules_start = v2_template.find("<rules>")
        rules_end = v2_template.find("</rules>")
        rules = v2_template[rules_start:rules_end]
        # The rule ABOUT dcid: is fine, but examples should show WRONG/CORRECT
        assert "dcid:Person" in rules  # In the WRONG column
        assert "populationType,Person" in rules  # In the CORRECT column

    def test_shorter_than_v1(self, v2_template):
        v1_path = Path(__file__).parent.parent.parent / "src" / "resources" / "prompts" / "improved_pvmap_prompt.txt"
        if not v1_path.exists():
            pytest.skip("v1 prompt not found")
        v1 = v1_path.read_text(encoding="utf-8")
        assert len(v2_template) < len(v1), "v2 should be shorter than v1"

    def test_has_three_examples(self, v2_template):
        """v2 should have exactly 3 examples (down from 5)."""
        count = v2_template.count("## Example")
        assert count == 3, f"Expected 3 examples, found {count}"


# =============================================================================
# CLI parser prompt-version flag
# =============================================================================


class TestCliPromptVersion:
    """Test --prompt-version CLI flag."""

    def test_default_is_v2(self):
        from src.config.cli_parser import parse_args
        args = parse_args([])
        assert args.prompt_version == "v2"

    def test_v1_accepted(self):
        from src.config.cli_parser import parse_args
        args = parse_args(["--prompt-version", "v1"])
        assert args.prompt_version == "v1"

    def test_v2_accepted(self):
        from src.config.cli_parser import parse_args
        args = parse_args(["--prompt-version", "v2"])
        assert args.prompt_version == "v2"

    def test_invalid_rejected(self):
        from src.config.cli_parser import parse_args
        with pytest.raises(SystemExit):
            parse_args(["--prompt-version", "v3"])
