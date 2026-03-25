"""
Tests for schema_tools module.

Tests wrappers around tools.schema_selector functions.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import csv

from src.tools.schema_tools import (
    get_schema_categories,
    generate_data_preview,
    build_prompt,
    select_schema_category,
    copy_schema_files,
    get_available_categories,
    read_schema_vocab
)


def test_get_schema_categories():
    """Test that get_schema_categories returns expected structure."""
    categories = get_schema_categories()

    assert isinstance(categories, dict)
    assert len(categories) > 0

    # Check expected categories exist
    expected = ['Demographics', 'Economy', 'Education', 'Employment',
                'Energy', 'Health', 'School']
    for category in expected:
        assert category in categories
        assert isinstance(categories[category], str)
        assert len(categories[category]) > 0


def test_get_available_categories():
    """Test that get_available_categories returns list."""
    categories = get_available_categories()

    assert isinstance(categories, list)
    assert len(categories) == 7
    assert 'Demographics' in categories
    assert 'Economy' in categories


def test_generate_data_preview_success(temp_dir):
    """Test successful data preview generation."""
    # Create test directory structure
    input_dir = temp_dir / "test_dataset"
    test_data_dir = input_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    # Create a sampled data file
    sampled_file = test_data_dir / "data_sampled_data.csv"
    with open(sampled_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['location', 'date', 'population'])
        writer.writerow(['USA', '2020', '331000000'])
        writer.writerow(['CAN', '2020', '38000000'])
        writer.writerow(['MEX', '2020', '128000000'])

    # Generate preview
    result = generate_data_preview(input_dir, max_rows=10)

    assert result['success'] is True
    assert result['error'] is None
    assert result['preview'] is not None
    assert 'location' in result['preview']
    assert 'USA' in result['preview']


def test_generate_data_preview_missing_directory(temp_dir):
    """Test data preview with missing directory."""
    nonexistent = temp_dir / "nonexistent"

    result = generate_data_preview(nonexistent, max_rows=10)

    # Should handle gracefully
    assert result['success'] is False
    assert result['error'] is not None
    assert result['preview'] is None


def test_generate_data_preview_no_data_files(temp_dir):
    """Test data preview when no data files exist."""
    input_dir = temp_dir / "empty_dataset"
    test_data_dir = input_dir / "test_data"
    test_data_dir.mkdir(parents=True)

    result = generate_data_preview(input_dir, max_rows=10)

    assert result['success'] is False
    assert 'ERROR' in result['error'] or 'not found' in result['error'].lower()


def test_build_prompt_success(temp_dir):
    """Test prompt building with valid inputs."""
    # Create schema base directory
    schema_dir = temp_dir / "schemas"
    schema_dir.mkdir()

    # Create a sample schema category directory
    demo_dir = schema_dir / "Demographics"
    demo_dir.mkdir()

    # Create schema example file
    schema_file = demo_dir / "scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt"
    with open(schema_file, 'w') as f:
        f.write("Example schema content\nfor Demographics\n")

    metadata_content = "parameter,value\ndataset_name,test_ds\n"
    data_preview = "location,value\nUSA,100\n"

    result = build_prompt(
        metadata_content=metadata_content,
        data_preview=data_preview,
        schema_base_dir=schema_dir,
        preview_lines=5
    )

    assert result['success'] is True
    assert result['error'] is None
    assert result['prompt'] is not None
    assert 'Demographics' in result['prompt']
    assert 'test_ds' in result['prompt']
    assert 'USA,100' in result['prompt']


def test_build_prompt_missing_schema_dir(temp_dir):
    """Test prompt building with missing schema directory."""
    nonexistent = temp_dir / "nonexistent_schemas"

    metadata_content = "param,val\n"
    data_preview = "a,b\n1,2\n"

    result = build_prompt(
        metadata_content=metadata_content,
        data_preview=data_preview,
        schema_base_dir=nonexistent,
        preview_lines=5
    )

    # Should still succeed but with warnings
    assert result['success'] is True
    assert result['prompt'] is not None


@patch('src.tools.schema_tools._invoke_gemini')
def test_select_schema_category_success(mock_invoke):
    """Test successful schema category selection."""
    # Mock successful Gemini response
    mock_invoke.return_value = (True, 'Demographics')

    result = select_schema_category(
        prompt="Test prompt",
        model_name="gemini-2.5-flash"
    )

    assert result['success'] is True
    assert result['category'] == 'Demographics'
    assert result['error'] is None

    # Verify mock was called
    mock_invoke.assert_called_once()


@patch('src.tools.schema_tools._invoke_gemini')
def test_select_schema_category_failure(mock_invoke):
    """Test failed schema category selection."""
    # Mock failed Gemini response
    mock_invoke.return_value = (False, 'API error: timeout')

    result = select_schema_category(
        prompt="Test prompt"
    )

    assert result['success'] is False
    assert result['category'] is None
    assert result['error'] is not None
    assert 'timeout' in result['error']


@patch('src.tools.schema_tools._invoke_gemini')
def test_select_schema_category_exception(mock_invoke):
    """Test schema selection with exception."""
    # Mock exception
    mock_invoke.side_effect = Exception("Network error")

    result = select_schema_category(prompt="Test")

    assert result['success'] is False
    assert result['category'] is None
    assert 'Network error' in result['error']


def test_copy_schema_files_success(temp_dir):
    """Test successful schema file copying."""
    # Create schema source directory
    schema_dir = temp_dir / "schemas"
    demo_dir = schema_dir / "Demographics"
    demo_dir.mkdir(parents=True)

    # Create schema file
    schema_file = demo_dir / "scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt"
    with open(schema_file, 'w') as f:
        f.write("Schema example content\n")

    # Create target directory
    input_dir = temp_dir / "dataset"
    input_dir.mkdir()

    # Copy files
    result = copy_schema_files(
        category='Demographics',
        schema_base_dir=schema_dir,
        input_dir=input_dir,
        dry_run=False
    )

    assert result['success'] is True
    assert result['error'] is None
    assert len(result['files_copied']) >= 1

    # Verify .txt file was actually copied (now goes to schema/ subfolder)
    copied_file = input_dir / "schema" / schema_file.name
    assert copied_file.exists()


def test_copy_schema_files_dry_run(temp_dir):
    """Test schema file copying in dry run mode."""
    # Create schema source directory
    schema_dir = temp_dir / "schemas"
    demo_dir = schema_dir / "Demographics"
    demo_dir.mkdir(parents=True)

    # Create schema file
    schema_file = demo_dir / "scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt"
    with open(schema_file, 'w') as f:
        f.write("Schema content\n")

    # Create target directory
    input_dir = temp_dir / "dataset"
    input_dir.mkdir()

    # Dry run
    result = copy_schema_files(
        category='Demographics',
        schema_base_dir=schema_dir,
        input_dir=input_dir,
        dry_run=True
    )

    assert result['success'] is True
    assert result['error'] is None

    # File should NOT be copied in dry run (check schema/ subfolder)
    copied_file = input_dir / "schema" / schema_file.name
    assert not copied_file.exists()


def test_copy_schema_files_school_category(temp_dir):
    """Test copying files for School category (which has no .txt files)."""
    schema_dir = temp_dir / "schemas"
    schema_dir.mkdir()

    input_dir = temp_dir / "dataset"
    input_dir.mkdir()

    # School category should succeed but copy no files
    result = copy_schema_files(
        category='School',
        schema_base_dir=schema_dir,
        input_dir=input_dir,
        dry_run=False
    )

    assert result['success'] is True
    assert len(result['files_copied']) == 0


def test_copy_schema_files_missing_source(temp_dir):
    """Test file copying when source file doesn't exist."""
    schema_dir = temp_dir / "schemas"
    schema_dir.mkdir()

    input_dir = temp_dir / "dataset"
    input_dir.mkdir()

    # Try to copy from non-existent category
    result = copy_schema_files(
        category='Demographics',
        schema_base_dir=schema_dir,
        input_dir=input_dir,
        dry_run=False
    )

    # Should succeed with empty list (tolerant behavior)
    assert result['success'] is True
    assert len(result['files_copied']) == 0


def test_copy_schema_files_invalid_input_dir(temp_dir):
    """Test file copying with invalid input directory."""
    schema_dir = temp_dir / "schemas"
    schema_dir.mkdir()

    # Non-existent input dir
    input_dir = temp_dir / "nonexistent"

    result = copy_schema_files(
        category='Demographics',
        schema_base_dir=schema_dir,
        input_dir=input_dir,
        dry_run=False
    )

    # Should fail
    assert result['success'] is False
    assert result['error'] is not None


def test_copy_schema_files_returns_vocab_content(temp_dir):
    """Test that copy_schema_files returns formatted vocab content when available."""
    import json

    # Create schema source directory with both .txt and vocab.json
    schema_dir = temp_dir / "schemas"
    health_dir = schema_dir / "Health"
    health_dir.mkdir(parents=True)

    # Create .txt file
    txt_file = health_dir / "scripts_statvar_llm_config_schema_examples_dc_topic_Health.txt"
    with open(txt_file, 'w') as f:
        f.write("Example --> populationType:MortalityEvent, causeOfDeath:ICD10/A00\n")

    # Create schema_vocab.json
    vocab = {
        "category": "Health",
        "stat_var_skeletons": {"MortalityEvent": ["causeOfDeath", "gender"]},
        "property_vocabulary": {"causeOfDeath": ["ICD10/A00"], "gender": ["Male", "Female"]},
        "examples": [{"label": "Test", "mapping": "populationType:MortalityEvent"}]
    }
    vocab_file = health_dir / "schema_vocab.json"
    with open(vocab_file, 'w') as f:
        json.dump(vocab, f)

    # Create target directory
    input_dir = temp_dir / "dataset"
    input_dir.mkdir()

    result = copy_schema_files(
        category='Health',
        schema_base_dir=schema_dir,
        input_dir=input_dir,
        dry_run=False
    )

    assert result['success'] is True
    assert result['schema_vocab_content'] is not None
    assert 'Schema Vocabulary: Health' in result['schema_vocab_content']
    assert 'MortalityEvent' in result['schema_vocab_content']


def test_copy_schema_files_no_vocab_returns_none(temp_dir):
    """Test that copy_schema_files returns None for vocab when no vocab file exists."""
    schema_dir = temp_dir / "schemas"
    demo_dir = schema_dir / "Demographics"
    demo_dir.mkdir(parents=True)

    # Create .txt file only (no vocab.json)
    txt_file = demo_dir / "scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt"
    with open(txt_file, 'w') as f:
        f.write("Example content\n")

    input_dir = temp_dir / "dataset"
    input_dir.mkdir()

    result = copy_schema_files(
        category='Demographics',
        schema_base_dir=schema_dir,
        input_dir=input_dir,
        dry_run=False
    )

    assert result['success'] is True
    assert result['schema_vocab_content'] is None


def test_read_schema_vocab_success(temp_dir):
    """Test reading schema vocab from file."""
    import json

    # Create vocab file
    schema_dir = temp_dir / "schemas"
    health_dir = schema_dir / "Health"
    health_dir.mkdir(parents=True)

    vocab = {
        "category": "Health",
        "stat_var_skeletons": {"MortalityEvent": ["causeOfDeath"]},
        "property_vocabulary": {"causeOfDeath": ["ICD10/A00", "Diabetes"]},
        "examples": [{"label": "Deaths", "mapping": "populationType:MortalityEvent"}]
    }
    with open(health_dir / "schema_vocab.json", 'w') as f:
        json.dump(vocab, f)

    result = read_schema_vocab(category='Health', schema_base_dir=str(schema_dir))

    assert result['success'] is True
    assert result['error'] is None
    assert result['vocab'] is not None
    assert result['vocab']['category'] == 'Health'
    assert 'MortalityEvent' in result['vocab']['stat_var_skeletons']

    # Check formatted output
    assert result['formatted'] is not None
    assert 'Schema Vocabulary: Health' in result['formatted']
    assert 'MortalityEvent' in result['formatted']
    assert 'causeOfDeath' in result['formatted']


def test_read_schema_vocab_missing_file(temp_dir):
    """Test reading vocab when file doesn't exist."""
    schema_dir = temp_dir / "schemas"
    schema_dir.mkdir()

    result = read_schema_vocab(category='NonExistent', schema_base_dir=str(schema_dir))

    assert result['success'] is False
    assert result['vocab'] is None
    assert result['formatted'] is None
    assert result['error'] is not None


def test_read_schema_vocab_default_base_dir():
    """Test reading vocab with real schema files (from project's schema_examples)."""
    # This tests against the actual generated vocab files
    result = read_schema_vocab(category='Health')

    assert result['success'] is True
    assert result['vocab'] is not None
    assert result['vocab']['category'] == 'Health'
    assert 'MortalityEvent' in result['vocab']['stat_var_skeletons']
    assert len(result['vocab']['examples']) > 0
    assert result['formatted'] is not None


def test_read_schema_vocab_formatted_output_structure(temp_dir):
    """Test that formatted vocab output has expected sections."""
    import json

    schema_dir = temp_dir / "schemas"
    eco_dir = schema_dir / "Economy"
    eco_dir.mkdir(parents=True)

    vocab = {
        "category": "Economy",
        "stat_var_skeletons": {
            "BLSEstablishment": ["naics"],
            "EconomicActivity": ["activitySource", "measuredProperty"]
        },
        "property_vocabulary": {
            "naics": ["NAICS/23", "NAICS/42"],
            "activitySource": ["GrossDomesticProduction"],
            "measuredProperty": ["amount", "count"]
        },
        "examples": [
            {"label": "Construction Establishments", "mapping": "naics:NAICS/23, populationType:BLSEstablishment"},
            {"label": "GDP", "mapping": "activitySource:GrossDomesticProduction, populationType:EconomicActivity"}
        ]
    }
    with open(eco_dir / "schema_vocab.json", 'w') as f:
        json.dump(vocab, f)

    result = read_schema_vocab(category='Economy', schema_base_dir=str(schema_dir))

    formatted = result['formatted']
    assert '### Schema Vocabulary: Economy' in formatted
    assert 'StatVar Skeletons' in formatted
    assert 'BLSEstablishment' in formatted
    assert 'EconomicActivity' in formatted
    assert 'VALID ENUM VALUES' in formatted
    assert 'Representative examples' in formatted
    assert 'Construction Establishments' in formatted
