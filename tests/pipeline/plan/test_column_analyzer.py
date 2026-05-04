"""Tests for the Phase A column relationship analyzer.

Tests are organized by function, matching the module's public API.
"""

import pandas as pd
import pytest

from src.pipeline.plan.column_analyzer import (
    ColumnAnalysis,
    analyze_columns,
    detect_co_referents,
    detect_composite_key,
    detect_cross_products,
    detect_hierarchical,
    detect_place_format,
    detect_qualifiers,
    detect_time_format,
    detect_total_indicators,
    detect_value_error_bounds,
)
from src.api.models.plan import RelationshipType


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bijection_df():
    """Two columns with perfect 1:1 bijection (code <-> name)."""
    return pd.DataFrame({
        "country_code": ["US", "GB", "DE", "FR", "JP"],
        "country_name": ["United States", "United Kingdom", "Germany", "France", "Japan"],
    })


@pytest.fixture
def many_to_one_df():
    """Child strictly determines parent, but not 1:1."""
    return pd.DataFrame({
        "county": ["Cook", "DuPage", "LA", "San Diego", "Harris", "Dallas"],
        "state": ["IL", "IL", "CA", "CA", "TX", "TX"],
    })


@pytest.fixture
def cross_product_df():
    """Full cross product of sex x age group."""
    sexes = ["Male", "Female"]
    ages = ["0-17", "18-64", "65+"]
    rows = [{"sex": s, "age": a} for s in sexes for a in ages]
    return pd.DataFrame(rows)


@pytest.fixture
def sdmx_df():
    """SDMX-style dataset with multiple relationship types."""
    return pd.DataFrame({
        "REF_AREA": ["US", "US", "US", "GB", "GB", "GB"],
        "INDICATOR": ["CPI", "CPI", "GDP", "CPI", "CPI", "GDP"],
        "TIME_PERIOD": ["2020", "2021", "2020", "2020", "2021", "2020"],
        "OBS_VALUE": [100.0, 102.5, 21000.0, 99.0, 101.0, 2800.0],
        "UNIT_MEASURE": ["Index", "Index", "Billion USD", "Index", "Index", "Billion GBP"],
    })


@pytest.fixture
def estimate_moe_df():
    """Estimate column with its margin-of-error companion."""
    return pd.DataFrame({
        "estimate": [1000, 2000, 500, 3000, 1500],
        "moe": [50, 100, 30, 150, 80],
    })


# ---------------------------------------------------------------------------
# detect_co_referents
# ---------------------------------------------------------------------------


class TestDetectCoReferents:

    def test_perfect_bijection(self, bijection_df):
        assert detect_co_referents(bijection_df, "country_code", "country_name") is True

    def test_many_to_one_is_not_coreferent(self, many_to_one_df):
        """County -> State is many-to-one, not a bijection."""
        assert detect_co_referents(many_to_one_df, "county", "state") is False

    def test_independent_columns_not_coreferent(self, sdmx_df):
        """REF_AREA and INDICATOR are independent dimensions."""
        assert detect_co_referents(sdmx_df, "REF_AREA", "INDICATOR") is False

    def test_with_nulls(self):
        """Nulls should be excluded; remaining rows still form bijection."""
        df = pd.DataFrame({
            "a": ["X", "Y", None, "Z"],
            "b": [1, 2, None, 3],
        })
        assert detect_co_referents(df, "a", "b") is True

    def test_too_few_valid_rows(self):
        """Fewer than 2 valid rows -> skip (False)."""
        df = pd.DataFrame({
            "a": [None, None, "X"],
            "b": [None, None, 1],
        })
        # Only 1 valid row after dropping NaN
        assert detect_co_referents(df, "a", "b") is False


# ---------------------------------------------------------------------------
# detect_cross_products
# ---------------------------------------------------------------------------


class TestDetectCrossProducts:

    def test_full_cross_product(self, cross_product_df):
        assert detect_cross_products(cross_product_df, "sex", "age") is True

    def test_sparse_not_cross_product(self):
        """Sparse combinations below 80% density -> False."""
        df = pd.DataFrame({
            "dim_a": ["X", "X", "Y", "Y", "Z"],
            "dim_b": ["1", "2", "1", "2", "1"],
            # Missing Z-2 => 5/6 ≈ 0.83 -- borderline
        })
        assert detect_cross_products(df, "dim_a", "dim_b") is True

        # More sparse: 4/9 ≈ 0.44
        df2 = pd.DataFrame({
            "dim_a": ["X", "X", "Y", "Z"],
            "dim_b": ["1", "2", "1", "1"],
        })
        assert detect_cross_products(df2, "dim_a", "dim_b") is False

    def test_single_value_column(self):
        """Column with < 2 unique values -> skip."""
        df = pd.DataFrame({
            "a": ["X", "X", "X"],
            "b": ["1", "2", "3"],
        })
        assert detect_cross_products(df, "a", "b") is False


# ---------------------------------------------------------------------------
# detect_hierarchical
# ---------------------------------------------------------------------------


class TestDetectHierarchical:

    def test_county_to_state(self, many_to_one_df):
        assert detect_hierarchical(many_to_one_df, "county", "state") is True

    def test_coreferent_is_not_hierarchical(self, bijection_df):
        """1:1 bijection is co-referent, not hierarchical."""
        assert detect_hierarchical(bijection_df, "country_code", "country_name") is False

    def test_independent_columns(self):
        """Independent columns are not hierarchical."""
        df = pd.DataFrame({
            "sex": ["M", "F", "M", "F"],
            "age": ["20", "30", "30", "20"],
        })
        assert detect_hierarchical(df, "sex", "age") is False


# ---------------------------------------------------------------------------
# detect_qualifiers
# ---------------------------------------------------------------------------


class TestDetectQualifiers:

    def test_numeric_with_unit(self):
        df = pd.DataFrame({
            "value": [100, 200, 300, 400, 500],
            "unit": ["kg", "kg", "lb", "lb", "kg"],
        })
        assert detect_qualifiers(df, "value", "unit") is True

    def test_two_numerics_not_qualifier(self):
        df = pd.DataFrame({
            "value": [100, 200, 300],
            "other_value": [1.0, 2.0, 3.0],
        })
        assert detect_qualifiers(df, "value", "other_value") is False

    def test_high_cardinality_not_qualifier(self):
        """qual_col with > 5 unique values is not a qualifier."""
        df = pd.DataFrame({
            "value": list(range(10)),
            "label": [f"cat_{i}" for i in range(10)],
        })
        assert detect_qualifiers(df, "value", "label") is False


# ---------------------------------------------------------------------------
# detect_value_error_bounds
# ---------------------------------------------------------------------------


class TestDetectValueErrorBounds:

    def test_estimate_and_moe(self, estimate_moe_df):
        assert detect_value_error_bounds(estimate_moe_df, "estimate", "moe") is True

    def test_moe_larger_than_estimate(self):
        """When MOE exceeds estimate for > 5% rows, not an error bound."""
        df = pd.DataFrame({
            "estimate": [10, 20, 30, 40, 50],
            "moe": [100, 200, 300, 400, 500],  # All larger
        })
        assert detect_value_error_bounds(df, "estimate", "moe") is False

    def test_name_keyword_required(self):
        """Even if numeric relationship holds, column name must match."""
        df = pd.DataFrame({
            "estimate": [1000, 2000, 500],
            "other_col": [50, 100, 30],  # No MOE keyword in name
        })
        assert detect_value_error_bounds(df, "estimate", "other_col") is False

    def test_non_numeric(self):
        """Non-numeric columns -> False."""
        df = pd.DataFrame({
            "name": ["Alice", "Bob"],
            "moe": ["X", "Y"],
        })
        assert detect_value_error_bounds(df, "name", "moe") is False


# ---------------------------------------------------------------------------
# detect_composite_key
# ---------------------------------------------------------------------------


class TestDetectCompositeKey:

    def test_single_column_key(self):
        df = pd.DataFrame({
            "id": [1, 2, 3, 4],
            "value": [10, 10, 20, 20],
        })
        assert detect_composite_key(df) == ["id"]

    def test_multi_column_key(self, sdmx_df):
        key = detect_composite_key(sdmx_df)
        # REF_AREA + INDICATOR + TIME_PERIOD should uniquely identify rows
        assert set(key) == {"REF_AREA", "INDICATOR", "TIME_PERIOD"}

    def test_no_unique_key(self):
        """Fully duplicated rows -> no key found."""
        df = pd.DataFrame({
            "a": ["X", "X", "X"],
            "b": ["Y", "Y", "Y"],
        })
        assert detect_composite_key(df) == []

    def test_returns_minimal_key(self):
        """Should return smallest set of columns."""
        df = pd.DataFrame({
            "pk": [1, 2, 3],
            "extra": ["a", "b", "c"],
            "value": [10, 20, 30],
        })
        # pk alone is unique, so should pick that
        key = detect_composite_key(df)
        assert len(key) == 1
        assert key[0] in ("pk", "extra", "value")  # any single unique col


# ---------------------------------------------------------------------------
# detect_place_format
# ---------------------------------------------------------------------------


class TestDetectPlaceFormat:

    def test_fips_state(self):
        s = pd.Series(["01", "06", "12", "36", "48"])
        result = detect_place_format(s)
        assert result is not None
        assert result["format_detected"] == "fips_state"
        assert result["prefix_rule"] == "geoId/"
        assert result["resolution_rate"] >= 0.9

    def test_iso_2_country(self):
        s = pd.Series(["US", "GB", "DE", "FR", "JP"])
        result = detect_place_format(s)
        assert result is not None
        assert result["format_detected"] == "iso_2"
        assert result["prefix_rule"] == "country/"

    def test_iso_3_country(self):
        s = pd.Series(["USA", "GBR", "DEU", "FRA", "JPN"])
        result = detect_place_format(s)
        assert result is not None
        assert result["format_detected"] == "iso_3"

    def test_fips_county(self):
        s = pd.Series(["06037", "06059", "17031", "48201", "36061"])
        result = detect_place_format(s)
        assert result is not None
        assert result["format_detected"] == "fips_county"
        assert result["prefix_rule"] == "geoId/"

    def test_non_place(self):
        s = pd.Series(["hello", "world", "foo", "bar"])
        result = detect_place_format(s)
        assert result is None

    def test_mixed_with_low_match_rate(self):
        """Below 90% match -> None."""
        s = pd.Series(["US", "GB", "not_a_code", "???", "12345"])
        result = detect_place_format(s)
        assert result is None


# ---------------------------------------------------------------------------
# detect_time_format
# ---------------------------------------------------------------------------


class TestDetectTimeFormat:

    def test_yyyy(self):
        s = pd.Series(["2020", "2021", "2022", "2023"])
        result = detect_time_format(s)
        assert result is not None
        assert result["format_detected"] == "YYYY"

    def test_yyyy_mm(self):
        s = pd.Series(["2020-01", "2020-02", "2020-03", "2020-04"])
        result = detect_time_format(s)
        assert result is not None
        assert result["format_detected"] == "YYYY-MM"

    def test_yyyy_mm_dd(self):
        s = pd.Series(["2020-01-15", "2020-02-20", "2020-03-10"])
        result = detect_time_format(s)
        assert result is not None
        assert result["format_detected"] == "YYYY-MM-DD"

    def test_non_time(self):
        s = pd.Series(["hello", "world", "foo"])
        result = detect_time_format(s)
        assert result is None


# ---------------------------------------------------------------------------
# detect_total_indicators
# ---------------------------------------------------------------------------


class TestDetectTotalIndicators:

    def test_common_totals_detected(self):
        s = pd.Series(["Male", "Female", "Total", "Both Sexes"])
        result = detect_total_indicators(s)
        assert "Total" in result
        assert "Both Sexes" in result

    def test_non_totals_excluded(self):
        s = pd.Series(["Category A", "Category B", "Category C"])
        result = detect_total_indicators(s)
        assert result == []

    def test_case_insensitive(self):
        s = pd.Series(["total", "TOTAL", "Total"])
        result = detect_total_indicators(s)
        # Should deduplicate to unique raw values
        assert len(result) >= 1

    def test_special_symbols(self):
        s = pd.Series(["Active", "-", "*", "~", "Inactive"])
        result = detect_total_indicators(s)
        assert "-" in result
        assert "*" in result
        assert "~" in result

    def test_numeric_totals(self):
        s = pd.Series(["01", "02", "00", "999", "03"])
        result = detect_total_indicators(s)
        assert "00" in result
        assert "999" in result


# ---------------------------------------------------------------------------
# analyze_columns (integration)
# ---------------------------------------------------------------------------


class TestAnalyzeColumns:

    def test_sdmx_dataset(self, sdmx_df):
        result = analyze_columns(sdmx_df)
        assert isinstance(result, ColumnAnalysis)

        # Should find composite key
        assert len(result.composite_key) > 0

        # Should detect place format for REF_AREA
        place_cols = [p["column"] for p in result.place_detections]
        assert "REF_AREA" in place_cols

        # Should detect time format for TIME_PERIOD
        time_cols = [t["column"] for t in result.time_detections]
        assert "TIME_PERIOD" in time_cols

        # Should have relationships
        assert len(result.relationships) > 0

        # UNIT_MEASURE should be detected as a qualifier for OBS_VALUE
        qualifier_rels = [
            r for r in result.relationships
            if r.relationship == RelationshipType.QUALIFIER
        ]
        assert len(qualifier_rels) > 0

    def test_to_dict_serialization(self, sdmx_df):
        result = analyze_columns(sdmx_df)
        d = result.to_dict()

        assert isinstance(d, dict)
        assert "relationships" in d
        assert "composite_key" in d
        assert "place_detections" in d
        assert "time_detections" in d
        assert "raw_value_profiles" in d
        assert "total_indicators" in d
        assert "co_referent_groups" in d
        assert "functional_deps" in d

        # Relationships should be serializable dicts
        for r in d["relationships"]:
            assert isinstance(r, dict)
            assert "column_a" in r
            assert "relationship" in r

    def test_empty_dataframe(self):
        df = pd.DataFrame()
        result = analyze_columns(df)
        assert result.relationships == []
        assert result.composite_key == []

    def test_single_column(self):
        df = pd.DataFrame({"x": [1, 2, 3]})
        result = analyze_columns(df)
        # No pairwise relationships possible
        assert result.relationships == []

    def test_coreferent_groups(self, bijection_df):
        result = analyze_columns(bijection_df)
        # Should find one co-referent group
        assert len(result.co_referent_groups) > 0
        group = result.co_referent_groups[0]
        assert "country_code" in group
        assert "country_name" in group

    def test_functional_deps(self, many_to_one_df):
        result = analyze_columns(many_to_one_df)
        # Should find county -> state functional dependency
        assert len(result.functional_deps) > 0
        dep = result.functional_deps[0]
        assert dep["child"] == "county"
        assert dep["parent"] == "state"

    def test_raw_value_profiles(self, cross_product_df):
        result = analyze_columns(cross_product_df)
        # Both columns have <= 50 unique values
        assert "sex" in result.raw_value_profiles
        assert "age" in result.raw_value_profiles
        assert set(result.raw_value_profiles["sex"]) == {"Male", "Female"}

    def test_high_cardinality_skipped_for_cross_product(self):
        """Columns with > 100 unique values should skip cross-product check."""
        df = pd.DataFrame({
            "id": list(range(200)),
            "category": ["A", "B"] * 100,
        })
        result = analyze_columns(df)
        # Should not have any cross-product relationship for id column
        cross_rels = [
            r for r in result.relationships
            if r.relationship == RelationshipType.CROSS_PRODUCT
            and ("id" in (r.column_a, r.column_b))
        ]
        assert len(cross_rels) == 0
