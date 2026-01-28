"""
Tests for PVMAP generation helper functions.

Tests simple Python functions (not agents).
"""

import pytest
from pathlib import Path
from src.agents.pvmap_generation.helpers import (
    build_prompt_with_feedback,
    extract_csv,
    read_file_content
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
    """Test prompt building with error feedback injection."""
    template_path = temp_dir / "template.txt"
    template_path.write_text("Generate PVMAP for {{SAMPLED_DATA}}")
    
    error_feedback = "Error: Missing property mapping for column 'population'"
    
    prompt = build_prompt_with_feedback(
        template_path=template_path,
        schema_content="schema",
        sampled_data_content="data",
        metadata_content="metadata",
        error_feedback=error_feedback
    )
    
    assert "PREVIOUS ERROR - PLEASE FIX" in prompt
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
