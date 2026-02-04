"""
Tests for sampling_tools module.

Tests each of the 5 sampling tools that the agentic SamplingAgent uses:
1. preview_data - Preview CSV file structure
2. analyze_columns - Column analysis for classification
3. sample_rows - Execute sampling strategies
4. check_coverage - Validate dimension hypothesis
5. generate_context - Create DataContext for PVMAP
"""

import pytest
from pathlib import Path
import tempfile
import csv
import os

from src.tools.sampling_tools import (
    preview_data,
    analyze_columns,
    sample_rows,
    check_coverage,
    generate_context,
    get_sampling_tools,
    SAMPLING_TOOLS,
    _detect_dtype,
    _looks_like_place,
    _looks_like_date,
    _get_sample_values,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def simple_csv():
    """Create a simple CSV file for testing."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['ID', 'Name', 'Value'])
        for i in range(10):
            writer.writerow([i, f'Item{i}', i * 100])
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def population_csv():
    """Create a population-style CSV with place/time/dimensions/values."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['StateFIPS', 'Year', 'Gender', 'AgeGroup', 'Population'])
        for state in ['06', '48', '36']:  # CA, TX, NY
            for year in ['2020', '2021']:
                for gender in ['Male', 'Female']:
                    for age in ['Under18', '18to64', '65Plus']:
                        pop = hash(f'{state}{year}{gender}{age}') % 1000000 + 100000
                        writer.writerow([state, year, gender, age, pop])
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def dc_formatted_csv():
    """Create a pre-formatted Data Commons style CSV."""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        writer = csv.writer(f)
        writer.writerow(['observationAbout', 'observationDate', 'variableMeasured', 'value'])
        writer.writerow(['geoId/06', '2020', 'Count_Person_Male', '19500000'])
        writer.writerow(['geoId/06', '2020', 'Count_Person_Female', '19800000'])
        writer.writerow(['geoId/48', '2020', 'Count_Person_Male', '14200000'])
        f.flush()
        yield f.name
    os.unlink(f.name)


@pytest.fixture
def output_path():
    """Create a temporary output path."""
    with tempfile.NamedTemporaryFile(suffix='.csv', delete=False) as f:
        yield f.name
    if os.path.exists(f.name):
        os.unlink(f.name)


# ============================================================================
# Tool Registry Tests
# ============================================================================

def test_get_sampling_tools():
    """Test that get_sampling_tools returns 5 tools."""
    tools = get_sampling_tools()
    assert len(tools) == 5


def test_sampling_tools_constant():
    """Test SAMPLING_TOOLS constant."""
    assert len(SAMPLING_TOOLS) == 5


# ============================================================================
# preview_data Tests
# ============================================================================

def test_preview_data_basic(simple_csv):
    """Test basic preview_data functionality."""
    result = preview_data(simple_csv)

    assert result['success'] is True
    assert result['headers'] == ['ID', 'Name', 'Value']
    assert len(result['sample_rows']) == 10  # All rows
    assert result['total_columns'] == 3


def test_preview_data_limited_rows(population_csv):
    """Test preview_data with row limit."""
    result = preview_data(population_csv, n_rows=5)

    assert result['success'] is True
    assert len(result['sample_rows']) == 5
    assert result['total_rows'] > 5


def test_preview_data_file_not_found():
    """Test preview_data with non-existent file."""
    result = preview_data('/nonexistent/path.csv')

    assert result['success'] is False
    assert 'not found' in result['error'].lower()


def test_preview_data_file_size(simple_csv):
    """Test that file size is reported."""
    result = preview_data(simple_csv)

    assert result['success'] is True
    assert result['file_size_kb'] > 0


# ============================================================================
# analyze_columns Tests
# ============================================================================

def test_analyze_columns_basic(simple_csv):
    """Test basic column analysis."""
    result = analyze_columns(simple_csv)

    assert result['success'] is True
    assert result['total_rows'] == 10
    assert len(result['columns']) == 3


def test_analyze_columns_detects_place(population_csv):
    """Test that FIPS codes are detected as place."""
    result = analyze_columns(population_csv)

    assert result['success'] is True
    state_col = result['columns']['StateFIPS']
    assert state_col['looks_like_place'] is True


def test_analyze_columns_detects_date(population_csv):
    """Test that Year column is detected as date."""
    result = analyze_columns(population_csv)

    assert result['success'] is True
    year_col = result['columns']['Year']
    assert year_col['looks_like_date'] is True


def test_analyze_columns_detects_numeric(population_csv):
    """Test numeric type detection."""
    result = analyze_columns(population_csv)

    assert result['success'] is True
    pop_col = result['columns']['Population']
    assert pop_col['dtype'] == 'Integer'


def test_analyze_columns_cardinality(population_csv):
    """Test cardinality calculation."""
    result = analyze_columns(population_csv)

    assert result['success'] is True
    # Gender should have cardinality 2
    gender_col = result['columns']['Gender']
    assert gender_col['cardinality'] == 2


def test_analyze_columns_sample_values(population_csv):
    """Test sample values are returned."""
    result = analyze_columns(population_csv)

    assert result['success'] is True
    gender_col = result['columns']['Gender']
    assert len(gender_col['sample_values']) > 0
    assert 'Male' in gender_col['sample_values'] or 'Female' in gender_col['sample_values']


# ============================================================================
# sample_rows Tests
# ============================================================================

def test_sample_rows_head(population_csv, output_path):
    """Test head sampling mode."""
    import json
    result = sample_rows(
        population_csv,
        output_path,
        json.dumps({'mode': 'head', 'target_rows': 10})
    )

    assert result['success'] is True
    assert result['rows_sampled'] == 10
    assert result['strategy_used'] == 'head'
    assert os.path.exists(output_path)


def test_sample_rows_random(population_csv, output_path):
    """Test random sampling mode."""
    import json
    result = sample_rows(
        population_csv,
        output_path,
        json.dumps({'mode': 'random', 'target_rows': 15})
    )

    assert result['success'] is True
    assert result['rows_sampled'] == 15
    assert result['strategy_used'] == 'random'


def test_sample_rows_stratified(population_csv, output_path):
    """Test stratified sampling mode."""
    import json
    result = sample_rows(
        population_csv,
        output_path,
        json.dumps({'mode': 'stratified', 'target_rows': 20, 'stratify_by': ['Gender']})
    )

    assert result['success'] is True
    assert result['strategy_used'] == 'stratified'
    # Should have rows from both genders
    import pandas as pd
    df = pd.read_csv(output_path)
    assert len(df['Gender'].unique()) == 2


def test_sample_rows_fixed_pivot(population_csv, output_path):
    """Test fixed_pivot sampling mode."""
    import json
    result = sample_rows(
        population_csv,
        output_path,
        json.dumps({
            'mode': 'fixed_pivot',
            'target_rows': 10,
            'pivot_config': {
                'fix': {'StateFIPS': '06', 'Year': '2020'},
                'vary': ['Gender', 'AgeGroup']
            }
        })
    )

    assert result['success'] is True
    assert result['strategy_used'] == 'fixed_pivot'


def test_sample_rows_file_not_found(output_path):
    """Test error handling for missing input file."""
    import json
    result = sample_rows(
        '/nonexistent/file.csv',
        output_path,
        json.dumps({'mode': 'head', 'target_rows': 10})
    )

    assert result['success'] is False
    assert 'not found' in result['error'].lower()


# ============================================================================
# check_coverage Tests
# ============================================================================

def test_check_coverage_unique(population_csv):
    """Test coverage check with correct dimensions."""
    result = check_coverage(
        population_csv,
        place_col='StateFIPS',
        time_col='Year',
        dimension_columns=['Gender', 'AgeGroup']
    )

    assert result['success'] is True
    assert result['is_unique'] is True


def test_check_coverage_missing_dimension(population_csv):
    """Test coverage check detects missing dimensions."""
    result = check_coverage(
        population_csv,
        place_col='StateFIPS',
        time_col='Year',
        dimension_columns=['Gender']  # Missing AgeGroup
    )

    assert result['success'] is True
    # Should detect duplicates since we're missing AgeGroup
    assert result['is_unique'] is False or result['duplicate_count'] > 0


def test_check_coverage_per_dimension(population_csv):
    """Test per-dimension coverage statistics."""
    result = check_coverage(
        population_csv,
        place_col='StateFIPS',
        time_col='Year',
        dimension_columns=['Gender', 'AgeGroup']
    )

    assert result['success'] is True
    assert 'Gender' in result['per_dimension']
    assert result['per_dimension']['Gender']['covered'] == 2


# ============================================================================
# generate_context Tests
# ============================================================================

def test_generate_context_basic(population_csv):
    """Test basic context generation."""
    import json
    result = generate_context(
        population_csv,
        column_roles_json=json.dumps({
            'StateFIPS': 'place',
            'Year': 'time',
            'Gender': 'dimension',
            'AgeGroup': 'dimension',
            'Population': 'value'
        }),
        dimension_columns=['Gender', 'AgeGroup'],
        metadata_json=json.dumps({'datasetname': 'Test Population'})
    )

    assert result['success'] is True
    assert result['data_context'] is not None
    assert result['skeleton_summary'] != ''
    assert len(result['skeleton_sample']) > 0


def test_generate_context_statvar_pattern(population_csv):
    """Test StatVar pattern generation."""
    import json
    result = generate_context(
        population_csv,
        column_roles_json=json.dumps({
            'StateFIPS': 'place',
            'Year': 'time',
            'Gender': 'dimension',
            'Population': 'value'
        }),
        dimension_columns=['Gender'],
        metadata_json=""
    )

    assert result['success'] is True
    assert result['statvar_pattern'] != ''
    assert '{Gender}' in result['statvar_pattern']


def test_generate_context_dc_formatted(dc_formatted_csv):
    """Test context generation for pre-formatted DC data."""
    import json
    result = generate_context(
        dc_formatted_csv,
        column_roles_json=json.dumps({
            'observationAbout': 'place',
            'observationDate': 'time',
            'variableMeasured': 'dimension',
            'value': 'value'
        }),
        dimension_columns=['variableMeasured'],
        metadata_json=""
    )

    assert result['success'] is True


# ============================================================================
# Helper Function Tests
# ============================================================================

def test_detect_dtype_integer():
    """Test integer detection."""
    assert _detect_dtype(['1', '2', '3', '100', '200']) == 'Integer'


def test_detect_dtype_float():
    """Test float detection."""
    assert _detect_dtype(['1.5', '2.7', '3.14', '100.0', '200.5']) == 'Float'


def test_detect_dtype_string():
    """Test string detection."""
    assert _detect_dtype(['hello', 'world', 'test', 'abc']) == 'String'


def test_detect_dtype_date():
    """Test date pattern detection.

    Note: The function checks integer first, so pure year values like '2020'
    are detected as Integer (since they're valid integers). Date detection
    happens via date regex only if int() fails. YYYY-MM is detected as Date
    because it fails int() and matches the date regex.
    """
    # YYYY-MM format fails int(), matches date regex -> Date
    assert _detect_dtype(['2020-01', '2021-02', '2022-03', '2023-04']) == 'Date'
    # Plain years are valid integers -> Integer
    assert _detect_dtype(['2020', '2021', '2022', '2023']) == 'Integer'
    # Quarter format fails int(), matches date regex -> Date
    assert _detect_dtype(['2020Q1', '2020Q2', '2020Q3', '2020Q4']) == 'Date'


def test_looks_like_place_fips():
    """Test FIPS code detection."""
    assert _looks_like_place('state_fips', ['06', '48', '36']) is True
    assert _looks_like_place('StateFIPS', ['06', '48', '36']) is True


def test_looks_like_place_geoid():
    """Test geoId detection."""
    assert _looks_like_place('location', ['geoId/06', 'geoId/48']) is True


def test_looks_like_place_iso():
    """Test ISO country code detection."""
    assert _looks_like_place('country', ['US', 'CA', 'MX']) is True


def test_looks_like_date_year():
    """Test year column detection."""
    assert _looks_like_date('year', ['2020', '2021', '2022']) is True


def test_looks_like_date_date_column():
    """Test date column name detection."""
    assert _looks_like_date('observation_date', ['2020-01-01']) is True


def test_get_sample_values():
    """Test sample value selection."""
    values = ['a', 'a', 'a', 'b', 'b', 'c', 'd', 'e', 'f', 'g']
    samples = _get_sample_values(values, max_frequent=3, max_random=2)

    # Should include 'a' (most frequent)
    assert 'a' in samples
    # Should have at most 5 values
    assert len(samples) <= 5
