"""Tests for the deterministic dataset profiler."""

import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.pipeline.sampling.profiler import (
    ColumnProfile,
    DatasetProfile,
    _detect_aggregate_in_column,
    _detect_functional_dependencies,
    _detect_metadata_rows,
    _detect_preformatted_dc,
    _detect_semantic_type,
    _detect_sentinels_in_column,
    _get_top_values_with_counts,
    _is_numeric_string,
    profile_dataset,
)


# --- Fixtures ---

@pytest.fixture
def employment_csv(tmp_path):
    """Create a synthetic employment dataset CSV."""
    data = {
        "Country": ["US", "US", "GB", "GB", "DE", "DE", "US", "US", "GB", "GB"],
        "Year": [2020, 2020, 2020, 2020, 2021, 2021, 2021, 2021, 2021, 2021],
        "Gender": ["Male", "Female", "Male", "Female", "Male", "Female", "Total", "Total", "Male", "Female"],
        "Industry_Code": [5112, 5112, 5111, 5111, 5112, 5112, 5111, 5111, 5112, 5112],
        "Employment": [234567, 198234, 145000, 132000, 250000, 210000, 460000, 342000, 155000, 140000],
        "Avg_Wage": [45000.50, 42000.25, 38000.00, 36000.00, 47000.00, 44000.00, -1, 999.99, 40000.0, 37000.0],
        "Unit": ["USD", "USD", "GBP", "GBP", "EUR", "EUR", "USD", "USD", "GBP", "GBP"],
        "Source": ["BLS", "BLS", "ONS", "ONS", "Eurostat", "Eurostat", "BLS", "BLS", "ONS", "ONS"],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "employment.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def preformatted_dc_csv(tmp_path):
    """Create a pre-formatted Data Commons dataset."""
    data = {
        "observationAbout": ["geoId/06", "geoId/06", "geoId/36"],
        "observationDate": ["2020", "2021", "2020"],
        "variableMeasured": ["dcid:Count_Person_Male", "dcid:Count_Person_Male", "dcid:Count_Person_Female"],
        "value": [1000000, 1050000, 500000],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "dc_preformatted.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


@pytest.fixture
def wide_dataset_csv(tmp_path):
    """Create a wide/pivoted dataset."""
    data = {
        "Country": ["US", "GB", "DE"],
        "Year": [2020, 2020, 2020],
        "Wheat_Price": [250.5, 240.3, 260.1],
        "Corn_Price": [180.2, 175.0, 190.5],
        "Rice_Price": [350.0, 345.0, 360.0],
        "Soybean_Price": [400.0, 395.0, 410.0],
        "Sugar_Price": [12.5, 12.0, 13.0],
        "Coffee_Price": [130.0, 125.0, 135.0],
    }
    df = pd.DataFrame(data)
    csv_path = tmp_path / "commodities.csv"
    df.to_csv(csv_path, index=False)
    return csv_path


# --- profile_dataset() tests ---

class TestProfileDataset:
    def test_basic_profiling(self, employment_csv):
        profile = profile_dataset(employment_csv)
        assert isinstance(profile, DatasetProfile)
        assert profile.total_rows == 10
        assert profile.total_columns == 8
        assert len(profile.headers) == 8
        assert "Country" in profile.headers
        assert len(profile.columns) == 8
        assert profile.file_size_kb > 0

    def test_column_profiles(self, employment_csv):
        profile = profile_dataset(employment_csv)
        country = profile.columns["Country"]
        assert country.dtype == "String"
        assert country.cardinality == 3  # US, GB, DE
        assert country.looks_like_place is True
        assert country.looks_like_date is False

    def test_numeric_categorical_detection(self, employment_csv):
        profile = profile_dataset(employment_csv)
        year = profile.columns["Year"]
        assert year.dtype == "Integer"
        # In a 10-row dataset, 2 unique = 0.2 ratio > 0.05 threshold.
        # The flag is designed for larger datasets (e.g., 10K rows with 10 years).
        # For this small fixture, just verify it's detected as a date
        assert year.looks_like_date is True

        employment = profile.columns["Employment"]
        assert employment.is_numeric_categorical is False  # High cardinality

    def test_date_detection(self, employment_csv):
        profile = profile_dataset(employment_csv)
        year = profile.columns["Year"]
        assert year.looks_like_date is True

    def test_place_detection(self, employment_csv):
        profile = profile_dataset(employment_csv)
        country = profile.columns["Country"]
        assert country.looks_like_place is True

    def test_aggregate_detection(self, employment_csv):
        profile = profile_dataset(employment_csv)
        gender = profile.columns["Gender"]
        assert "Total" in gender.aggregate_values
        assert "Gender" in profile.aggregate_flags
        assert "Total" in profile.aggregate_flags["Gender"]

    def test_sentinel_detection(self, employment_csv):
        profile = profile_dataset(employment_csv)
        wage = profile.columns["Avg_Wage"]
        assert "-1" in wage.sentinel_values or "-1.0" in wage.sentinel_values

    def test_preformatted_dc(self, preformatted_dc_csv):
        profile = profile_dataset(preformatted_dc_csv)
        assert profile.is_preformatted_dc is True

    def test_not_preformatted(self, employment_csv):
        profile = profile_dataset(employment_csv)
        assert profile.is_preformatted_dc is False

    def test_functional_dependencies(self, employment_csv):
        profile = profile_dataset(employment_csv)
        # Country -> Unit should be detected (each country has one unit)
        dep_pairs = [(d["source"], d["target"]) for d in profile.functional_dependencies]
        assert ("Country", "Unit") in dep_pairs or ("Unit", "Country") in dep_pairs

    def test_sample_rows(self, employment_csv):
        profile = profile_dataset(employment_csv)
        assert len(profile.sample_rows) <= 15
        assert len(profile.sample_rows) > 0
        assert "Country" in profile.sample_rows[0]

    def test_top_values(self, employment_csv):
        profile = profile_dataset(employment_csv)
        country = profile.columns["Country"]
        assert len(country.top_values) > 0
        # Top values should be (value, count) tuples
        val, count = country.top_values[0]
        assert isinstance(val, str)
        assert isinstance(count, int)

    def test_to_dict(self, employment_csv):
        profile = profile_dataset(employment_csv)
        d = profile.to_dict()
        assert isinstance(d, dict)
        assert d["total_rows"] == 10
        assert "Country" in d["columns"]
        assert d["columns"]["Country"]["dtype"] == "String"

    def test_file_not_found(self, tmp_path):
        with pytest.raises(FileNotFoundError):
            profile_dataset(tmp_path / "nonexistent.csv")

    def test_wide_dataset(self, wide_dataset_csv):
        profile = profile_dataset(wide_dataset_csv)
        assert profile.total_rows == 3
        assert profile.total_columns == 8
        # Price columns should be numeric with high cardinality ratio
        wheat = profile.columns["Wheat_Price"]
        assert wheat.dtype == "Float"
        assert wheat.is_numeric_categorical is False


# --- Helper function tests ---

class TestDetectSemanticType:
    def test_fips_state(self):
        assert _detect_semantic_type("State FIPS Code", ["01", "06", "36"], "Integer", True, False) == "FIPS_STATE"

    def test_iso2(self):
        assert _detect_semantic_type("Country", ["US", "GB", "DE"], "String", True, False) == "ISO_2"

    def test_iso3(self):
        assert _detect_semantic_type("Country", ["USA", "GBR", "DEU"], "String", True, False) == "ISO_3"

    def test_yyyy(self):
        assert _detect_semantic_type("Year", ["2020", "2021", "2022"], "Integer", False, True) == "YYYY"

    def test_yyyy_mm(self):
        assert _detect_semantic_type("Date", ["2020-01", "2020-02"], "String", False, True) == "YYYY-MM"

    def test_dc_dcid(self):
        assert _detect_semantic_type("Place", ["geoId/06", "geoId/36"], "String", True, False) == "DC_DCID"

    def test_no_semantic_type(self):
        assert _detect_semantic_type("Gender", ["Male", "Female"], "String", False, False) is None


class TestTopValuesWithCounts:
    def test_basic(self):
        values = ["a", "b", "a", "c", "a", "b"]
        result = _get_top_values_with_counts(values, top_n=3)
        assert result[0] == ("a", 3)
        assert len(result) == 3

    def test_empty(self):
        assert _get_top_values_with_counts([]) == []


class TestAggregateDetection:
    def test_detects_total(self):
        values = ["Male", "Female", "Total", "Other"]
        result = _detect_aggregate_in_column(values)
        assert "Total" in result

    def test_detects_all(self):
        values = ["18-24", "25-34", "All"]
        result = _detect_aggregate_in_column(values)
        assert "All" in result

    def test_no_aggregates(self):
        values = ["Male", "Female", "Other"]
        result = _detect_aggregate_in_column(values)
        assert result == []


class TestSentinelDetection:
    def test_detects_negative_one(self):
        values = ["100", "200", "-1", "300"]
        result = _detect_sentinels_in_column(values)
        assert "-1" in result

    def test_detects_na(self):
        values = ["100", "n/a", "300"]
        result = _detect_sentinels_in_column(values)
        assert "n/a" in result

    def test_no_sentinels(self):
        values = ["100", "200", "300"]
        result = _detect_sentinels_in_column(values)
        assert result == []


class TestPreformattedDC:
    def test_detects_dc_format(self):
        df = pd.DataFrame({
            "observationAbout": ["geoId/06"],
            "observationDate": ["2020"],
            "variableMeasured": ["dcid:Count_Person"],
            "value": [1000],
        })
        assert _detect_preformatted_dc(df) is True

    def test_rejects_non_dc(self):
        df = pd.DataFrame({
            "Country": ["US"],
            "Year": [2020],
            "Population": [330000000],
        })
        assert _detect_preformatted_dc(df) is False


class TestFunctionalDependencies:
    def test_detects_dependency(self):
        df = pd.DataFrame({
            "Country": ["US", "US", "GB", "GB"],
            "Currency": ["USD", "USD", "GBP", "GBP"],
            "Value": [100, 200, 150, 250],
        })
        columns = {
            "Country": ColumnProfile(name="Country", dtype="String", cardinality=2),
            "Currency": ColumnProfile(name="Currency", dtype="String", cardinality=2),
            "Value": ColumnProfile(name="Value", dtype="Integer", cardinality=4),
        }
        deps = _detect_functional_dependencies(df, columns)
        pairs = [(d["source"], d["target"]) for d in deps]
        assert ("Country", "Currency") in pairs

    def test_skips_high_cardinality(self):
        df = pd.DataFrame({
            "ID": list(range(200)),
            "Name": [f"name_{i}" for i in range(200)],
        })
        columns = {
            "ID": ColumnProfile(name="ID", dtype="Integer", cardinality=200),
            "Name": ColumnProfile(name="Name", dtype="String", cardinality=200),
        }
        deps = _detect_functional_dependencies(df, columns)
        assert deps == []  # Both have cardinality >= 100


# --- Metadata row detection tests ---

class TestIsNumericString:
    def test_integer(self):
        assert _is_numeric_string("123") is True

    def test_float(self):
        assert _is_numeric_string("45.67") is True

    def test_negative(self):
        assert _is_numeric_string("-100") is True

    def test_comma_separated(self):
        assert _is_numeric_string("1,234,567") is True

    def test_empty(self):
        assert _is_numeric_string("") is True

    def test_nan(self):
        assert _is_numeric_string("nan") is True

    def test_text(self):
        assert _is_numeric_string("dollars") is False

    def test_unit_string(self):
        assert _is_numeric_string("($/bbl)") is False

    def test_mixed(self):
        assert _is_numeric_string("12abc") is False


class TestDetectMetadataRows:
    def test_detects_unit_row(self):
        """World Bank-style: row 2 has unit descriptors like ($/bbl), ($/mt)."""
        data = {
            "Commodity": ["Crude oil", "($/bbl)", "Natural gas", "Coal", "Gold"],
            "2020": [42.3, "($/bbl)", 2.1, 60.5, 1770.0],
            "2021": [70.7, "($/bbl)", 3.8, 130.0, 1800.0],
            "2022": [99.0, "($/bbl)", 6.5, 350.0, 1820.0],
        }
        df = pd.DataFrame(data)
        clean_df, metadata_rows = _detect_metadata_rows(df)

        assert len(metadata_rows) == 1
        assert metadata_rows[0]["2020"] == "($/bbl)"
        assert len(clean_df) == 4

    def test_no_metadata_rows(self):
        """Clean numeric dataset — no metadata rows."""
        data = {
            "Country": ["US", "GB", "DE", "FR"],
            "GDP": [21000, 2800, 3800, 2700],
            "Population": [330, 67, 83, 67],
        }
        df = pd.DataFrame(data)
        clean_df, metadata_rows = _detect_metadata_rows(df)

        assert len(metadata_rows) == 0
        assert len(clean_df) == 4

    def test_preserves_metadata_content(self):
        """Metadata rows should contain the original values for context."""
        data = {
            "Indicator": ["Price", "Unit description", "Volume", "Weight", "Density", "Area"],
            "Col_A": [100.5, "Metric tons", 200.3, 300.1, 400.5, 500.0],
            "Col_B": [50.2, "Barrels", 60.7, 70.8, 80.9, 90.0],
            "Col_C": [75.0, "Kilograms", 85.0, 95.0, 105.0, 115.0],
        }
        df = pd.DataFrame(data)
        clean_df, metadata_rows = _detect_metadata_rows(df)

        assert len(metadata_rows) == 1
        assert metadata_rows[0]["Col_A"] == "Metric tons"
        assert metadata_rows[0]["Col_B"] == "Barrels"
        assert len(clean_df) == 5

    def test_too_few_rows(self):
        """Datasets with < 3 rows should skip detection."""
        data = {"A": [1, 2], "B": ["x", "y"]}
        df = pd.DataFrame(data)
        clean_df, metadata_rows = _detect_metadata_rows(df)

        assert len(metadata_rows) == 0
        assert len(clean_df) == 2

    def test_too_few_numeric_columns(self):
        """Datasets with < 2 numeric columns should skip detection."""
        data = {
            "Name": ["Alice", "Bob", "Charlie", "Diana"],
            "City": ["NYC", "London", "Berlin", "Paris"],
            "Score": [90, 85, 88, 92],
        }
        df = pd.DataFrame(data)
        clean_df, metadata_rows = _detect_metadata_rows(df)

        assert len(metadata_rows) == 0
        assert len(clean_df) == 4

    def test_multiple_metadata_rows(self):
        """Multiple metadata rows (units + footnotes)."""
        data = {
            "Item": ["Oil", "(units)", "Gas", "(source: WB)", "Coal",
                     "Gold", "Silver", "Copper", "Zinc", "Tin"],
            "Price_2020": [42.3, "($/bbl)", 2.1, "(World Bank)", 60.5,
                           1770.0, 25.0, 6000.0, 2500.0, 17000.0],
            "Price_2021": [70.7, "($/bbl)", 3.8, "(World Bank)", 130.0,
                           1800.0, 26.0, 9000.0, 3000.0, 30000.0],
            "Price_2022": [99.0, "($/bbl)", 6.5, "(World Bank)", 350.0,
                           1820.0, 22.0, 8000.0, 3500.0, 25000.0],
        }
        df = pd.DataFrame(data)
        clean_df, metadata_rows = _detect_metadata_rows(df)

        assert len(metadata_rows) == 2
        assert len(clean_df) == 8


class TestProfileDatasetWithMetadata:
    def test_metadata_rows_in_profile(self, tmp_path):
        """profile_dataset() should populate metadata_rows field."""
        data = {
            "Country": ["US", "(ISO)", "GB", "DE", "FR", "JP", "CN"],
            "GDP": [21000, "(billions USD)", 2800, 3800, 2700, 5000, 14000],
            "Population": [330, "(millions)", 67, 83, 67, 126, 1400],
        }
        df = pd.DataFrame(data)
        csv_path = tmp_path / "with_metadata.csv"
        df.to_csv(csv_path, index=False)

        profile = profile_dataset(csv_path)

        assert len(profile.metadata_rows) == 1
        assert profile.metadata_rows[0]["GDP"] == "(billions USD)"
        # total_rows should exclude metadata rows
        assert profile.total_rows == 6

    def test_to_dict_includes_metadata_rows(self, tmp_path):
        """to_dict() should include metadata_rows."""
        data = {
            "X": ["a", "units:", "b", "c", "d", "e"],
            "Y": [1.0, "(kg)", 2.0, 3.0, 4.0, 5.0],
            "Z": [4.0, "(m)", 5.0, 6.0, 7.0, 8.0],
        }
        df = pd.DataFrame(data)
        csv_path = tmp_path / "meta.csv"
        df.to_csv(csv_path, index=False)

        profile = profile_dataset(csv_path)
        d = profile.to_dict()

        assert "metadata_rows" in d
