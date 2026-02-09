"""
Tests for enriched DataContext and skeleton_summary.

Tests the 9-section enriched skeleton format, new helper methods, and
DataContext fields added for improved PVMAP generation.
"""

import pytest
import tempfile
import csv
import os
from pathlib import Path

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

from src.pipeline.sampling.data_context import (
    DataContext,
    DataContextGenerator,
    generate_data_context,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def population_df():
    """Create a population-style DataFrame with place/time/dimensions/values."""
    if not PANDAS_AVAILABLE:
        pytest.skip("pandas required")
    data = {
        'StateFIPS': ['06', '06', '06', '06', '48', '48', '48', '48'],
        'Year': ['2020', '2020', '2020', '2020', '2021', '2021', '2021', '2021'],
        'Gender': ['Male', 'Female', 'Male', 'Female', 'Male', 'Female', 'Male', 'Female'],
        'AgeGroup': ['Under18', 'Under18', '65Plus', '65Plus', 'Under18', 'Under18', '65Plus', '65Plus'],
        'Population': [1000, 1100, 500, 550, 2000, 2100, 600, 650],
        'Source': ['Census', 'Census', 'Census', 'Census', 'Census', 'Census', 'Census', 'Census'],
    }
    return pd.DataFrame(data)


@pytest.fixture
def aggregate_df():
    """DataFrame with aggregate values in dimension columns."""
    if not PANDAS_AVAILABLE:
        pytest.skip("pandas required")
    data = {
        'State': ['CA', 'CA', 'CA', 'TX', 'TX', 'TX'],
        'Year': ['2020', '2020', '2020', '2020', '2020', '2020'],
        'Gender': ['Male', 'Female', 'Total', 'Male', 'Female', 'Total'],
        'Count': [100, 110, 210, 200, 220, 420],
    }
    return pd.DataFrame(data)


@pytest.fixture
def dc_formatted_df():
    """Pre-formatted Data Commons DataFrame."""
    if not PANDAS_AVAILABLE:
        pytest.skip("pandas required")
    data = {
        'observationAbout': ['geoId/06', 'geoId/06', 'geoId/48'],
        'observationDate': ['2020', '2020', '2020'],
        'variableMeasured': ['Count_Person_Male', 'Count_Person_Female', 'Count_Person_Male'],
        'value': [19500000, 19800000, 14200000],
    }
    return pd.DataFrame(data)


@pytest.fixture
def fips_df():
    """DataFrame with FIPS state codes."""
    if not PANDAS_AVAILABLE:
        pytest.skip("pandas required")
    data = {
        'StateFIPS': ['06', '48', '36', '12', '17'],
        'Year': ['2020', '2020', '2020', '2020', '2020'],
        'Population': [39538223, 29145505, 20201249, 21538187, 12812508],
    }
    return pd.DataFrame(data)


@pytest.fixture
def generator():
    """Create a DataContextGenerator."""
    return DataContextGenerator()


# ============================================================================
# Enriched Skeleton Tests
# ============================================================================

def test_enriched_skeleton_has_all_columns(generator, population_df):
    """Verify section 1 lists ALL column headers (exact, case-sensitive)."""
    context = generator.generate(population_df, dataset_name="test_pop")
    summary = context.to_skeleton_summary()

    assert "## 1. TOPOLOGY & STRUCTURE" in summary
    # All column headers must be present
    for col in population_df.columns:
        assert f"`{col}`" in summary


def test_enriched_skeleton_has_ignored_columns(generator, population_df):
    """Verify metadata columns are listed under ignored."""
    context = generator.generate(population_df, dataset_name="test_pop")

    # Source column should be classified as metadata (low cardinality, keyword match)
    assert 'Source' in context.ignored_columns or context.column_roles.get('Source') == 'metadata'

    summary = context.to_skeleton_summary()
    # If there are ignored columns, they should appear in section 2
    if context.ignored_columns:
        assert "Ignored columns" in summary


def test_enriched_skeleton_aggregate_detection(generator, aggregate_df):
    """CSV with 'Total' in dimension, verify aggregate flag."""
    context = generator.generate(aggregate_df, dataset_name="test_agg")

    # Gender column should have 'Total' detected as aggregate
    assert 'Gender' in context.aggregate_values
    assert 'Total' in context.aggregate_values['Gender']

    summary = context.to_skeleton_summary()
    assert "Aggregate values detected" in summary


def test_enriched_skeleton_place_resolution(generator, fips_df):
    """CSV with FIPS codes, verify geoId/ hint."""
    context = generator.generate(fips_df, dataset_name="test_fips")

    # Should have place resolution hints
    assert len(context.place_resolution_hints) > 0

    # Check that at least one hint maps to geoId/
    dcid_values = [h['suggested_dcid'] for h in context.place_resolution_hints]
    assert any('geoId/' in d for d in dcid_values)

    summary = context.to_skeleton_summary()
    assert "Place" in summary and "DCID" in summary


def test_enriched_skeleton_one_shot_example(generator, population_df):
    """Verify mini PVMAP contains observationAbout, observationDate, value."""
    context = generator.generate(population_df, dataset_name="test_pop")

    assert context.one_shot_example != ""

    summary = context.to_skeleton_summary()
    assert "## 7. ONE-SHOT PVMAP EXAMPLE" in summary
    assert "key,property,value" in context.one_shot_example

    # Should contain observationDate mapping
    assert "observationDate" in context.one_shot_example
    # Should contain value mapping
    assert "value,{Number}" in context.one_shot_example


def test_enriched_skeleton_preformatted_detection(generator, dc_formatted_df):
    """DC-formatted CSV should have is_preformatted_dc=True."""
    context = generator.generate(dc_formatted_df, dataset_name="test_dc")

    assert context.is_preformatted_dc is True

    summary = context.to_skeleton_summary()
    assert "## 8. PRE-FORMATTED DATA COMMONS DETECTION" in summary
    assert "already in Data Commons format" in summary
    assert "passthrough mapping" in summary.lower()


def test_enriched_skeleton_not_preformatted(generator, population_df):
    """Regular CSV should not be detected as pre-formatted DC."""
    context = generator.generate(population_df, dataset_name="test_pop")
    assert context.is_preformatted_dc is False


def test_enriched_skeleton_dimension_values_expanded(generator, population_df):
    """Verify up to 15 values shown (vs old limit of 5)."""
    context = generator.generate(population_df, dataset_name="test_pop")
    summary = context.to_skeleton_summary()

    # Check section 4 header
    assert "## 4. DIMENSION DEEP DIVE" in summary

    # Gender should show both values (Male, Female)
    assert "Male" in summary
    assert "Female" in summary


def test_enriched_skeleton_all_nine_sections(generator, population_df):
    """Verify all 9 sections are present in the skeleton summary."""
    context = generator.generate(population_df, dataset_name="test_pop")
    summary = context.to_skeleton_summary()

    assert "## 1. TOPOLOGY & STRUCTURE" in summary
    assert "## 2. COLUMN CLASSIFICATIONS" in summary
    assert "## 3. ANCHOR ANALYSIS" in summary
    assert "## 4. DIMENSION DEEP DIVE" in summary
    assert "## 5. MEASUREMENT & UNITS" in summary
    assert "## 6. STATVAR PATTERN" in summary
    assert "## 7. ONE-SHOT PVMAP EXAMPLE" in summary
    assert "## 8. PRE-FORMATTED DATA COMMONS DETECTION" in summary
    assert "## 9. COVERAGE" in summary


def test_enriched_skeleton_coverage_reminder(generator, population_df):
    """Verify the generate-all reminder is present."""
    context = generator.generate(population_df, dataset_name="test_pop")
    summary = context.to_skeleton_summary()

    assert "Generate PVMAP for ALL dimension combinations" in summary


# ============================================================================
# New Helper Method Tests
# ============================================================================

def test_detect_aggregate_values_basic(generator, aggregate_df):
    """Test _detect_aggregate_values finds 'Total' keyword."""
    aggs = generator._detect_aggregate_values(aggregate_df, ['Gender'])
    assert 'Gender' in aggs
    assert 'Total' in aggs['Gender']


def test_detect_aggregate_values_no_aggregates(generator, population_df):
    """Test _detect_aggregate_values returns empty when no aggregates."""
    aggs = generator._detect_aggregate_values(population_df, ['Gender', 'AgeGroup'])
    # Neither dimension should have aggregate values
    assert not aggs.get('Gender', [])
    assert not aggs.get('AgeGroup', [])


def test_detect_preformatted_dc_positive(generator, dc_formatted_df):
    """Test _detect_preformatted_dc detects DC format."""
    assert generator._detect_preformatted_dc(dc_formatted_df) is True


def test_detect_preformatted_dc_negative(generator, population_df):
    """Test _detect_preformatted_dc returns False for regular data."""
    assert generator._detect_preformatted_dc(population_df) is False


def test_generate_place_resolution_hints_fips(generator, fips_df):
    """Test _generate_place_resolution_hints for FIPS state codes."""
    geo_info = {
        'column': 'StateFIPS',
        'format': 'FIPS_STATE',
        'sample_values': ['06', '48', '36'],
    }
    hints = generator._generate_place_resolution_hints(geo_info, fips_df)

    assert len(hints) > 0
    # 06 should map to geoId/06
    dcids = {h['raw_value']: h['suggested_dcid'] for h in hints}
    assert 'geoId/06' in dcids.values() or any('geoId/' in d for d in dcids.values())


def test_generate_place_resolution_hints_empty_geo(generator, population_df):
    """Test _generate_place_resolution_hints returns empty for no geo."""
    hints = generator._generate_place_resolution_hints({}, population_df)
    assert hints == []


def test_generate_one_shot_example(generator, population_df):
    """Test _generate_one_shot_example produces valid mini PVMAP."""
    context = generator.generate(population_df, dataset_name="test_pop")
    example = generator._generate_one_shot_example(context, population_df)

    assert "key,property,value" in example
    assert "observationDate" in example


def test_generate_one_shot_example_with_dimensions(generator, population_df):
    """Test one-shot example includes dimension value mappings."""
    context = generator.generate(population_df, dataset_name="test_pop")
    example = context.one_shot_example

    # Should enumerate Gender values since there are <= 10
    assert "Gender:" in example or "gender" in example.lower()


# ============================================================================
# to_metadata_dict Tests
# ============================================================================

def test_metadata_dict_includes_new_fields(generator, population_df):
    """Test that to_metadata_dict includes all new enriched fields."""
    context = generator.generate(population_df, dataset_name="test_pop")
    meta = context.to_metadata_dict()

    assert 'all_columns' in meta
    assert 'ignored_columns' in meta
    assert 'aggregate_values' in meta
    assert 'place_resolution_hints' in meta
    assert 'is_preformatted_dc' in meta

    # all_columns should match DataFrame columns
    assert meta['all_columns'] == list(population_df.columns)


# ============================================================================
# Convenience function test
# ============================================================================

def test_generate_data_context_convenience(population_df):
    """Test the convenience function returns enriched context."""
    context = generate_data_context(population_df, dataset_name="test")
    assert context.all_columns == list(population_df.columns)
    assert isinstance(context.aggregate_values, dict)
    assert isinstance(context.is_preformatted_dc, bool)
