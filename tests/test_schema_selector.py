"""
Tests for the schema selector module.

Tests src/pipeline/schema_selection/schema_selector.py including:
- Category info retrieval
- Data preview generation
- Prompt building
- Category response parsing
- Gemini API invocation (mocked)
- Schema file copying
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import tempfile
import csv
import shutil


@pytest.fixture
def schema_base_dir(temp_dir):
    """Create a mock schema base directory with category folders."""
    schema_dir = temp_dir / "schema_examples"
    schema_dir.mkdir()

    # Create category directories with schema files
    for category in ['Demographics', 'Economy', 'Education', 'Employment', 'Energy', 'Health']:
        cat_dir = schema_dir / category
        cat_dir.mkdir()

        # Create txt file
        txt_file = cat_dir / f"scripts_statvar_llm_config_schema_examples_dc_topic_{category}.txt"
        with open(txt_file, 'w') as f:
            f.write(f"Schema examples for {category}\n")
            f.write("Line 2\n")
            f.write("Line 3\n")

        # Create mcf file
        mcf_file = cat_dir / f"scripts_statvar_{category.lower()}_vertical_{category.lower()}.mcf"
        with open(mcf_file, 'w') as f:
            f.write(f"MCF definitions for {category}\n")

    # Create School directory (no txt file)
    school_dir = schema_dir / "School"
    school_dir.mkdir()

    return schema_dir


@pytest.fixture
def input_dir_with_data(temp_dir):
    """Create an input directory with test data."""
    input_dir = temp_dir / "test_dataset"
    input_dir.mkdir()

    # Create metadata file
    metadata_file = input_dir / "test_metadata.csv"
    with open(metadata_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['parameter', 'value'])
        writer.writerow(['dataset_name', 'test_dataset'])
        writer.writerow(['source', 'Test Source'])

    # Create test_data directory
    test_data_dir = input_dir / "test_data"
    test_data_dir.mkdir()

    # Create sampled data file
    sampled_file = test_data_dir / "test_sampled_data.csv"
    with open(sampled_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['location', 'year', 'population'])
        writer.writerow(['USA', '2020', '331000000'])
        writer.writerow(['Canada', '2020', '38000000'])

    return input_dir


class TestGetCategoryInfo:
    """Tests for get_category_info function."""

    def test_get_category_info_returns_dict(self):
        """Test that get_category_info returns a dictionary."""
        from src.pipeline.schema_selection.schema_selector import get_category_info

        info = get_category_info()

        assert isinstance(info, dict)
        assert len(info) == 7

    def test_get_category_info_all_categories_present(self):
        """Test that all expected categories are present."""
        from src.pipeline.schema_selection.schema_selector import get_category_info

        info = get_category_info()

        expected_categories = ['Demographics', 'Economy', 'Education',
                              'Employment', 'Energy', 'Health', 'School']
        for category in expected_categories:
            assert category in info
            assert isinstance(info[category], str)
            assert len(info[category]) > 0


class TestValidateInputDirectory:
    """Tests for validate_input_directory function."""

    def test_validate_input_directory_success(self, input_dir_with_data):
        """Test successful validation of input directory."""
        from src.pipeline.schema_selection.schema_selector import validate_input_directory

        success, error, metadata_files = validate_input_directory(input_dir_with_data)

        assert success is True
        assert error is None
        assert len(metadata_files) >= 1

    def test_validate_input_directory_not_exists(self, temp_dir):
        """Test validation with non-existent directory."""
        from src.pipeline.schema_selection.schema_selector import validate_input_directory

        nonexistent = temp_dir / "nonexistent"

        success, error, metadata_files = validate_input_directory(nonexistent)

        assert success is False
        assert error is not None
        assert 'does not exist' in error

    def test_validate_input_directory_not_a_dir(self, temp_dir):
        """Test validation when path is a file, not directory."""
        from src.pipeline.schema_selection.schema_selector import validate_input_directory

        file_path = temp_dir / "not_a_dir.txt"
        file_path.write_text("content")

        success, error, metadata_files = validate_input_directory(file_path)

        assert success is False
        assert 'not a directory' in error


class TestGenerateDataPreview:
    """Tests for generate_data_preview function."""

    def test_generate_data_preview_success(self, input_dir_with_data):
        """Test successful data preview generation."""
        from src.pipeline.schema_selection.schema_selector import generate_data_preview

        preview = generate_data_preview(input_dir_with_data, max_rows=10)

        assert 'location' in preview
        assert 'USA' in preview
        assert 'ERROR' not in preview

    def test_generate_data_preview_no_test_data_dir(self, temp_dir):
        """Test preview generation when test_data dir is missing."""
        from src.pipeline.schema_selection.schema_selector import generate_data_preview

        empty_dir = temp_dir / "empty_dataset"
        empty_dir.mkdir()

        preview = generate_data_preview(empty_dir, max_rows=10)

        assert 'ERROR' in preview

    def test_generate_data_preview_max_rows(self, temp_dir):
        """Test that max_rows parameter is respected."""
        from src.pipeline.schema_selection.schema_selector import generate_data_preview

        # Create input dir with many rows
        input_dir = temp_dir / "many_rows"
        input_dir.mkdir()
        test_data_dir = input_dir / "test_data"
        test_data_dir.mkdir()

        sampled_file = test_data_dir / "data_sampled_data.csv"
        with open(sampled_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['col1', 'col2'])
            for i in range(100):
                writer.writerow([f'val_{i}', str(i)])

        preview = generate_data_preview(input_dir, max_rows=5)

        # Count rows in preview (header + limited data)
        lines = preview.split('\n')
        csv_lines = [l for l in lines if ',' in l and l.strip()]
        assert len(csv_lines) <= 6  # header + max 5 data rows


class TestGenerateSchemaPreviews:
    """Tests for generate_schema_previews function."""

    def test_generate_schema_previews(self, schema_base_dir):
        """Test schema preview generation."""
        from src.pipeline.schema_selection.schema_selector import generate_schema_previews

        previews = generate_schema_previews(schema_base_dir, preview_lines=5)

        assert isinstance(previews, dict)
        assert 'Demographics' in previews
        assert 'Economy' in previews

    def test_generate_schema_previews_school_category(self, schema_base_dir):
        """Test that School category is handled correctly (no txt file)."""
        from src.pipeline.schema_selection.schema_selector import generate_schema_previews

        previews = generate_schema_previews(schema_base_dir, preview_lines=5)

        assert 'School' in previews
        assert 'No .txt file' in previews['School'] or 'MCF only' in previews['School']


class TestBuildPrompt:
    """Tests for build_prompt function."""

    def test_build_prompt_structure(self):
        """Test that build_prompt creates proper prompt structure."""
        from src.pipeline.schema_selection.schema_selector import build_prompt

        metadata = "parameter,value\ndataset_name,test"
        data_preview = "col1,col2\nval1,val2"
        category_info = {'Demographics': 'Population data', 'Economy': 'Economic data'}
        schema_previews = {'Demographics': 'Schema preview', 'Economy': 'Schema preview'}

        prompt = build_prompt(metadata, data_preview, category_info, schema_previews)

        assert 'Dataset Metadata' in prompt
        assert 'Sample Data' in prompt
        assert 'Available Schema Categories' in prompt
        assert 'Demographics' in prompt
        assert 'Selected Category' in prompt

    def test_build_prompt_includes_all_sections(self):
        """Test that prompt includes all required sections."""
        from src.pipeline.schema_selection.schema_selector import build_prompt

        metadata = "test metadata"
        data_preview = "test preview"
        category_info = {'Cat1': 'Desc1'}
        schema_previews = {'Cat1': 'Preview1'}

        prompt = build_prompt(metadata, data_preview, category_info, schema_previews)

        assert 'test metadata' in prompt
        assert 'test preview' in prompt
        assert 'Cat1' in prompt
        assert 'Desc1' in prompt


class TestParseCategoryResponse:
    """Tests for parse_category_response function."""

    def test_parse_exact_match(self):
        """Test parsing exact category match."""
        from src.pipeline.schema_selection.schema_selector import parse_category_response

        valid_categories = ['Demographics', 'Economy', 'Education', 'Employment',
                           'Energy', 'Health', 'School']

        result = parse_category_response('Demographics', valid_categories)
        assert result == 'Demographics'

    def test_parse_case_insensitive(self):
        """Test case-insensitive parsing."""
        from src.pipeline.schema_selection.schema_selector import parse_category_response

        valid_categories = ['Demographics', 'Economy', 'Education']

        result = parse_category_response('demographics', valid_categories)
        assert result == 'Demographics'

        result = parse_category_response('ECONOMY', valid_categories)
        assert result == 'Economy'

    def test_parse_with_trailing_punctuation(self):
        """Test parsing with trailing punctuation."""
        from src.pipeline.schema_selection.schema_selector import parse_category_response

        valid_categories = ['Demographics', 'Economy']

        result = parse_category_response('Demographics.', valid_categories)
        assert result == 'Demographics'

        result = parse_category_response('Economy!', valid_categories)
        assert result == 'Economy'

    def test_parse_multiline_response(self):
        """Test parsing response with multiple lines."""
        from src.pipeline.schema_selection.schema_selector import parse_category_response

        valid_categories = ['Demographics', 'Economy', 'Health']

        response = "Based on the data columns...\nHealth"
        result = parse_category_response(response, valid_categories)
        assert result == 'Health'

    def test_parse_fuzzy_match(self):
        """Test fuzzy matching for common variations."""
        from src.pipeline.schema_selection.schema_selector import parse_category_response

        valid_categories = ['Demographics', 'Economy', 'Employment']

        result = parse_category_response('economic', valid_categories)
        assert result == 'Economy'

        result = parse_category_response('demographic', valid_categories)
        assert result == 'Demographics'

    def test_parse_invalid_response(self):
        """Test parsing invalid response."""
        from src.pipeline.schema_selection.schema_selector import parse_category_response

        valid_categories = ['Demographics', 'Economy']

        result = parse_category_response('InvalidCategory', valid_categories)
        assert result is None

    def test_parse_empty_response(self):
        """Test parsing empty response."""
        from src.pipeline.schema_selection.schema_selector import parse_category_response

        valid_categories = ['Demographics', 'Economy']

        result = parse_category_response('', valid_categories)
        assert result is None

        result = parse_category_response('   \n  \n  ', valid_categories)
        assert result is None


class TestInvokeGemini:
    """Tests for invoke_gemini function."""

    @patch('src.pipeline.schema_selection.schema_selector.GeminiClient')
    def test_invoke_gemini_success(self, mock_client_class):
        """Test successful Gemini API invocation."""
        from src.pipeline.schema_selection.schema_selector import invoke_gemini

        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.generate_content.return_value = 'Demographics'

        success, result = invoke_gemini('Test prompt')

        assert success is True
        assert result == 'Demographics'

    @patch('src.pipeline.schema_selection.schema_selector.GeminiClient')
    def test_invoke_gemini_invalid_response(self, mock_client_class):
        """Test Gemini returning invalid category."""
        from src.pipeline.schema_selection.schema_selector import invoke_gemini

        mock_client = Mock()
        mock_client_class.return_value = mock_client
        mock_client.generate_content.return_value = 'InvalidCategory'

        success, result = invoke_gemini('Test prompt')

        assert success is False
        assert 'Could not parse' in result

    @patch('src.pipeline.schema_selection.schema_selector.GeminiClient')
    def test_invoke_gemini_exception(self, mock_client_class):
        """Test Gemini API exception handling."""
        from src.pipeline.schema_selection.schema_selector import invoke_gemini

        mock_client_class.side_effect = Exception('API error')

        success, result = invoke_gemini('Test prompt')

        assert success is False
        assert 'Error invoking Gemini' in result


class TestCopySchemaFiles:
    """Tests for copy_schema_files function."""

    def test_copy_schema_files_success(self, schema_base_dir, temp_dir):
        """Test successful schema file copying to schema/ subfolder."""
        from src.pipeline.schema_selection.schema_selector import copy_schema_files

        input_dir = temp_dir / "target"
        input_dir.mkdir()

        success, copied = copy_schema_files('Demographics', schema_base_dir, input_dir, dry_run=False)

        assert success is True
        assert len(copied) >= 1

        # Verify file was copied to schema/ subfolder
        expected_file = input_dir / "schema" / "scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt"
        assert expected_file.exists()

    def test_copy_schema_files_dry_run(self, schema_base_dir, temp_dir):
        """Test dry run mode."""
        from src.pipeline.schema_selection.schema_selector import copy_schema_files

        input_dir = temp_dir / "target"
        input_dir.mkdir()

        success, copied = copy_schema_files('Economy', schema_base_dir, input_dir, dry_run=True)

        assert success is True
        assert len(copied) >= 1

        # File should NOT be copied in dry run (schema/ dir not created)
        expected_file = input_dir / "schema" / "scripts_statvar_llm_config_schema_examples_dc_topic_Economy.txt"
        assert not expected_file.exists()

    def test_copy_schema_files_school_category(self, schema_base_dir, temp_dir):
        """Test School category (no txt file)."""
        from src.pipeline.schema_selection.schema_selector import copy_schema_files

        input_dir = temp_dir / "target"
        input_dir.mkdir()

        success, copied = copy_schema_files('School', schema_base_dir, input_dir, dry_run=False)

        assert success is True
        assert len(copied) == 0  # School has no schema files

    def test_copy_schema_files_missing_source(self, temp_dir):
        """Test with missing source schema directory."""
        from src.pipeline.schema_selection.schema_selector import copy_schema_files

        empty_schema_dir = temp_dir / "empty_schemas"
        empty_schema_dir.mkdir()

        input_dir = temp_dir / "target"
        input_dir.mkdir()

        success, copied = copy_schema_files('Demographics', empty_schema_dir, input_dir, dry_run=False)

        # Should succeed with empty list (tolerant behavior)
        assert success is True
        assert len(copied) == 0


class TestCheckSchemaFilesExist:
    """Tests for check_schema_files_exist function."""

    def test_check_schema_files_exist_true(self, temp_dir):
        """Test when schema files do exist."""
        from src.pipeline.schema_selection.schema_selector import check_schema_files_exist

        input_dir = temp_dir / "dataset"
        input_dir.mkdir()

        # Create a schema file
        schema_file = input_dir / "scripts_statvar_llm_config_schema_examples_dc_topic_Demographics.txt"
        schema_file.write_text("content")

        exists, files = check_schema_files_exist(input_dir)

        assert exists is True
        assert len(files) == 1

    def test_check_schema_files_exist_false(self, temp_dir):
        """Test when schema files don't exist."""
        from src.pipeline.schema_selection.schema_selector import check_schema_files_exist

        input_dir = temp_dir / "empty_dataset"
        input_dir.mkdir()

        exists, files = check_schema_files_exist(input_dir)

        assert exists is False
        assert len(files) == 0


class TestMergeMetadataFiles:
    """Tests for merge_metadata_files function."""

    def test_merge_single_file(self, temp_dir):
        """Test merging single metadata file (just copy)."""
        from src.pipeline.schema_selection.schema_selector import merge_metadata_files

        # Create single metadata file
        meta_file = temp_dir / "metadata.csv"
        with open(meta_file, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['param1', 'value1'])
            writer.writerow(['param2', 'value2'])

        output_file = temp_dir / "merged.csv"

        success = merge_metadata_files([meta_file], output_file)

        assert success is True
        assert output_file.exists()

    def test_merge_multiple_files(self, temp_dir):
        """Test merging multiple metadata files."""
        from src.pipeline.schema_selection.schema_selector import merge_metadata_files

        # Create multiple metadata files
        meta1 = temp_dir / "meta1.csv"
        with open(meta1, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['param1', 'value1'])

        meta2 = temp_dir / "meta2.csv"
        with open(meta2, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['param2', 'value2'])

        output_file = temp_dir / "merged.csv"

        success = merge_metadata_files([meta1, meta2], output_file)

        assert success is True
        assert output_file.exists()

        # Read merged file
        with open(output_file, 'r') as f:
            reader = csv.reader(f)
            rows = list(reader)

        params = [row[0] for row in rows]
        assert 'param1' in params
        assert 'param2' in params

    def test_merge_empty_list(self, temp_dir):
        """Test merging empty list of files."""
        from src.pipeline.schema_selection.schema_selector import merge_metadata_files

        output_file = temp_dir / "merged.csv"

        success = merge_metadata_files([], output_file)

        assert success is False


class TestSchemaCategories:
    """Tests for SCHEMA_CATEGORIES constant."""

    def test_schema_categories_list(self):
        """Test that SCHEMA_CATEGORIES contains expected values."""
        from src.pipeline.schema_selection.schema_selector import SCHEMA_CATEGORIES

        assert isinstance(SCHEMA_CATEGORIES, list)
        assert len(SCHEMA_CATEGORIES) == 7
        assert 'Demographics' in SCHEMA_CATEGORIES
        assert 'Economy' in SCHEMA_CATEGORIES
        assert 'Education' in SCHEMA_CATEGORIES
        assert 'Employment' in SCHEMA_CATEGORIES
        assert 'Energy' in SCHEMA_CATEGORIES
        assert 'Health' in SCHEMA_CATEGORIES
        assert 'School' in SCHEMA_CATEGORIES
