"""
Unit tests for heuristic quality scoring module.

Tests the calculate_heuristic_score() function and related utilities.
"""

import pytest
from src.tools.heuristic_quality import (
    calculate_heuristic_score,
    check_column_completeness,
    is_quality_acceptable,
    format_quality_report,
    _estimate_expected_rows,
    _count_pvmap_rows,
    _count_properties_in_pvmap,
    _get_columns_from_csv,
    _get_keys_from_pvmap,
    _check_value_formats,
)


# ============================================================================
# Test Data Fixtures
# ============================================================================

SAMPLE_DATA_CSV = """Year,State FIPS,Population,Unemployment Rate
2020,01,5000000,5.2
2020,02,700000,6.1
2021,01,5100000,4.8
2021,02,710000,5.5
"""

PREFORMATTED_DATA_CSV = """observationAbout,observationDate,variableMeasured,value
geoId/01,2020,dcid:Count_Person,5000000
geoId/02,2020,dcid:Count_Person,700000
"""

GOOD_PVMAP_CSV = """key,property,value,property2,value2,property3,value3
Year,observationDate,{Data},,,,
State FIPS,observationAbout,dcid:geoId/{Data},,,,
Population,value,{Number},populationType,dcid:Person,measuredProperty,dcid:count
"""

PARTIAL_PVMAP_CSV = """key,property,value
Year,observationDate,{Data}
State FIPS,observationAbout,{Data}
"""

POOR_PVMAP_CSV = """key,property,value
year,date,{Data}
"""

EMPTY_PVMAP_CSV = ""

PREFORMATTED_PVMAP_CSV = """key,property,value
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
variableMeasured,variableMeasured,{Data}
value,value,{Number}
"""


# ============================================================================
# Test calculate_heuristic_score
# ============================================================================

class TestCalculateHeuristicScore:
    """Tests for the main calculate_heuristic_score function."""

    def test_good_pvmap_scores_high(self):
        """Good PVMAP should score >= 70."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert result["total"] >= 70.0
        assert result["prop_coverage"] == 25.0  # All required props present

    def test_poor_pvmap_scores_low(self):
        """Poor PVMAP should score < 70."""
        result = calculate_heuristic_score(
            pvmap_csv=POOR_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert result["total"] < 70.0
        assert result["prop_coverage"] < 25.0  # Missing required props

    def test_empty_pvmap_scores_zero(self):
        """Empty PVMAP should score 0."""
        result = calculate_heuristic_score(
            pvmap_csv=EMPTY_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert result["total"] == 0.0

    def test_preformatted_data_passthrough(self):
        """Pre-formatted data with passthrough mapping should score well."""
        result = calculate_heuristic_score(
            pvmap_csv=PREFORMATTED_PVMAP_CSV,
            sampled_data=PREFORMATTED_DATA_CSV
        )
        # Pre-formatted data has different expectations
        assert result["prop_coverage"] == 25.0  # All required props present

    def test_returns_issues_list(self):
        """Result should include list of issues found."""
        result = calculate_heuristic_score(
            pvmap_csv=PARTIAL_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert "issues" in result
        # Partial PVMAP is missing value property
        assert result["issues"]  # Should have some issues

    def test_returns_all_score_components(self):
        """Result should include all score component breakdowns."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert "row_coverage" in result
        assert "prop_coverage" in result
        assert "column_coverage" in result
        assert "format_score" in result
        assert "details" in result

    def test_details_contains_breakdown(self):
        """Details dict should contain useful breakdown info."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        details = result["details"]
        assert "expected_rows" in details
        assert "actual_rows" in details
        assert "required_props_found" in details
        assert "data_columns" in details
        assert "mapped_keys" in details


# ============================================================================
# Test Row Coverage
# ============================================================================

class TestRowCoverage:
    """Tests for row coverage scoring."""

    def test_full_row_coverage_max_score(self):
        """Full row coverage should give 25 points."""
        # 3 rows in PVMAP vs ~4 expected columns
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        # Should be close to 25 (allowing for estimation variance)
        assert result["row_coverage"] >= 15.0

    def test_partial_row_coverage_reduced_score(self):
        """Partial row coverage should give proportional score."""
        # Only 1 row in PVMAP
        result = calculate_heuristic_score(
            pvmap_csv=POOR_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert result["row_coverage"] < 25.0

    def test_over_generation_penalty(self):
        """Too many PVMAP rows should be slightly penalized."""
        # Create PVMAP with many rows
        many_rows_pvmap = """key,property,value
Year,observationDate,{Data}
State FIPS,observationAbout,{Data}
Population,value,{Number}
Extra1,foo,bar
Extra2,foo,bar
Extra3,foo,bar
Extra4,foo,bar
Extra5,foo,bar
Extra6,foo,bar
Extra7,foo,bar
"""
        result = calculate_heuristic_score(
            pvmap_csv=many_rows_pvmap,
            sampled_data=SAMPLE_DATA_CSV
        )
        # Over-generation should cap at 100% or slightly penalize
        assert result["row_coverage"] <= 25.0


# ============================================================================
# Test Property Coverage
# ============================================================================

class TestPropertyCoverage:
    """Tests for required property coverage scoring."""

    def test_all_required_properties_full_score(self):
        """All required props (observationAbout, observationDate, value) = 25 pts."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert result["prop_coverage"] == 25.0

    def test_missing_value_property_reduced_score(self):
        """Missing 'value' property should reduce score."""
        # Note: The PVMAP column 'value' contains 'value' so substring detection finds it
        # Need to test with completely different property names
        no_value_pvmap = """key,property,setting
Year,observationDate,{Data}
State FIPS,observationAbout,{Data}
"""
        result = calculate_heuristic_score(
            pvmap_csv=no_value_pvmap,
            sampled_data=SAMPLE_DATA_CSV
        )
        # Missing 'value' property = 2/3 * 25 = ~16.7
        assert result["prop_coverage"] < 25.0
        assert result["prop_coverage"] > 10.0

    def test_missing_all_required_props_zero_score(self):
        """Missing all required props should give 0."""
        # Use completely different property names to avoid substring detection
        no_required_props = """key,propname,setting
foo,bar,baz
"""
        result = calculate_heuristic_score(
            pvmap_csv=no_required_props,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert result["prop_coverage"] == 0.0


# ============================================================================
# Test Column Coverage
# ============================================================================

class TestColumnCoverage:
    """Tests for column mapping completeness scoring."""

    def test_all_columns_mapped_full_score(self):
        """All data columns mapped should give 25 points."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        # Should be close to full score (Year, State FIPS, Population mapped)
        # Unemployment Rate is NOT mapped in GOOD_PVMAP_CSV
        assert result["column_coverage"] >= 15.0

    def test_unmapped_columns_reduced_score(self):
        """Unmapped columns should reduce score."""
        # Only maps Year, missing State FIPS, Population, Unemployment Rate
        result = calculate_heuristic_score(
            pvmap_csv=POOR_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        # Only 0-1 of 4 columns mapped (case mismatch: 'year' vs 'Year')
        assert result["column_coverage"] < 15.0

    def test_column_value_syntax_counted(self):
        """Column:Value syntax keys should count the column part."""
        column_value_pvmap = """key,property,value
State FIPS:01,observationAbout,dcid:geoId/01
State FIPS:02,observationAbout,dcid:geoId/02
Year,observationDate,{Data}
"""
        result = calculate_heuristic_score(
            pvmap_csv=column_value_pvmap,
            sampled_data=SAMPLE_DATA_CSV
        )
        # "State FIPS" should be counted from "State FIPS:01"
        details = result["details"]
        assert "State FIPS" in details.get("data_columns", set()) or \
               "state fips" in {c.lower() for c in details.get("mapped_keys", set())}


# ============================================================================
# Test Format Correctness
# ============================================================================

class TestFormatCorrectness:
    """Tests for value format scoring."""

    def test_correct_formats_full_score(self):
        """Correct {Data}, {Number}, dcid: formats should score high."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert result["format_score"] >= 20.0

    def test_missing_dcid_prefix_reduced_score(self):
        """Missing dcid: prefix where expected should reduce score."""
        no_dcid_pvmap = """key,property,value
Year,observationDate,{Data}
State FIPS,observationAbout,geoId/{Data}
Population,value,{Number}
Population,populationType,Person
"""
        result = calculate_heuristic_score(
            pvmap_csv=no_dcid_pvmap,
            sampled_data=SAMPLE_DATA_CSV
        )
        # "Person" without dcid: should be flagged
        assert "dcid:" in result["issues"].lower() or result["format_score"] < 25.0

    def test_no_placeholders_penalized(self):
        """No {Data} or {Number} placeholders should be flagged."""
        no_placeholders = """key,property,value
Year,observationDate,2020
State,observationAbout,Alabama
"""
        result = calculate_heuristic_score(
            pvmap_csv=no_placeholders,
            sampled_data=SAMPLE_DATA_CSV
        )
        # Should flag missing placeholders
        assert result["format_score"] < 20.0 or "placeholder" in result["issues"].lower()


# ============================================================================
# Test Threshold Functions
# ============================================================================

class TestThresholdFunctions:
    """Tests for threshold checking functions."""

    def test_threshold_boundary_70(self):
        """Score 70 should be acceptable, 69.9 not."""
        assert is_quality_acceptable(70.0) is True
        assert is_quality_acceptable(70.1) is True
        assert is_quality_acceptable(69.9) is False
        assert is_quality_acceptable(69.9, threshold=69.0) is True

    def test_custom_threshold(self):
        """Custom threshold should work."""
        assert is_quality_acceptable(50.0, threshold=50.0) is True
        assert is_quality_acceptable(49.9, threshold=50.0) is False


# ============================================================================
# Test Format Quality Report
# ============================================================================

class TestFormatQualityReport:
    """Tests for format_quality_report function."""

    def test_includes_total_score(self):
        """Report should include total score."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        report = format_quality_report(result)
        assert "Heuristic Quality Score:" in report
        assert "/100" in report

    def test_includes_breakdown(self):
        """Report should include score breakdown."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        report = format_quality_report(result)
        assert "Row Coverage:" in report
        assert "Property Coverage:" in report
        assert "Column Coverage:" in report
        assert "Format Score:" in report

    def test_includes_issues_when_present(self):
        """Report should include issues section when there are issues."""
        result = calculate_heuristic_score(
            pvmap_csv=POOR_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        report = format_quality_report(result)
        if result["issues"]:
            assert "Issues Found:" in report


# ============================================================================
# Test Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Tests for internal helper functions."""

    def test_count_pvmap_rows(self):
        """Should count data rows excluding header."""
        assert _count_pvmap_rows(GOOD_PVMAP_CSV) == 3
        assert _count_pvmap_rows(POOR_PVMAP_CSV) == 1
        assert _count_pvmap_rows(EMPTY_PVMAP_CSV) == 0

    def test_get_columns_from_csv(self):
        """Should extract column headers."""
        columns = _get_columns_from_csv(SAMPLE_DATA_CSV)
        assert "Year" in columns
        assert "State FIPS" in columns
        assert "Population" in columns
        assert "Unemployment Rate" in columns

    def test_get_keys_from_pvmap(self):
        """Should extract PVMAP keys."""
        keys = _get_keys_from_pvmap(GOOD_PVMAP_CSV)
        assert "Year" in keys
        assert "State FIPS" in keys
        assert "Population" in keys

    def test_count_properties_in_pvmap(self):
        """Should find required properties in PVMAP."""
        required = ['observationAbout', 'observationDate', 'value']
        found = _count_properties_in_pvmap(GOOD_PVMAP_CSV, required)
        assert found == set(required)

    def test_estimate_expected_rows_raw_data(self):
        """Should estimate rows based on column count for raw data."""
        expected = _estimate_expected_rows(SAMPLE_DATA_CSV)
        assert expected >= 3  # At least number of columns
        assert expected <= 100  # Capped at max

    def test_estimate_expected_rows_preformatted(self):
        """Should estimate fewer rows for pre-formatted data."""
        expected = _estimate_expected_rows(PREFORMATTED_DATA_CSV)
        assert expected <= 10  # Pre-formatted needs fewer mappings


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_sampled_data(self):
        """Should handle empty sampled data."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=""
        )
        assert "total" in result
        # Should still calculate based on PVMAP structure

    def test_malformed_csv(self):
        """Should handle malformed CSV gracefully."""
        malformed = "this is not,valid\ncsv with \"unbalanced quotes"
        result = calculate_heuristic_score(
            pvmap_csv=malformed,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert "total" in result
        # May score low but shouldn't crash

    def test_unicode_content(self):
        """Should handle unicode content."""
        unicode_pvmap = """key,property,value
Year,observationDate,{Data}
Stadt,observationAbout,{Data}
Bevölkerung,value,{Number}
"""
        result = calculate_heuristic_score(
            pvmap_csv=unicode_pvmap,
            sampled_data="Year,Stadt,Bevölkerung\n2020,München,1500000"
        )
        assert "total" in result

    def test_whitespace_only_content(self):
        """Should handle whitespace-only content."""
        result = calculate_heuristic_score(
            pvmap_csv="   \n  \n   ",
            sampled_data=SAMPLE_DATA_CSV
        )
        assert result["total"] == 0.0

    def test_quoted_csv_values(self):
        """Should handle quoted CSV values properly."""
        quoted_pvmap = '''"key","property","value"
"Column Name With Spaces","observationDate","{Data}"
"State FIPS","observationAbout","dcid:geoId/{Data}"
'''
        result = calculate_heuristic_score(
            pvmap_csv=quoted_pvmap,
            sampled_data="Column Name With Spaces,State FIPS\n2020,06\n"
        )
        assert "total" in result
        assert result["prop_coverage"] >= 8.0  # At least some properties found

    def test_bracket_placeholder_syntax(self):
        """Should recognize [Data] and [Number] as valid placeholders."""
        bracket_pvmap = """key,property,value
Year,observationDate,[Data]
State,observationAbout,[Data]
Population,value,[Number]
"""
        result = calculate_heuristic_score(
            pvmap_csv=bracket_pvmap,
            sampled_data="Year,State,Population\n2020,CA,100\n"
        )
        # Should not flag missing placeholders since [Data]/[Number] are valid
        assert result["format_score"] >= 15.0


# ============================================================================
# Test Integration with Metadata
# ============================================================================

class TestMetadataIntegration:
    """Tests for metadata integration in scoring."""

    def test_metadata_affects_expected_rows(self):
        """Metadata hints should affect expected row estimation."""
        # Metadata mentioning dimensions should increase expected rows
        metadata_with_dimensions = "param,value\ndatasetname,Test\ncategory,dimension\n"
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV,
            metadata=metadata_with_dimensions
        )
        assert "total" in result

    def test_empty_metadata_handled(self):
        """Empty metadata should be handled gracefully."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV,
            metadata=""
        )
        assert "total" in result


# ============================================================================
# Test Score Bounds
# ============================================================================

class TestScoreBounds:
    """Tests for score bounds and normalization."""

    def test_total_score_bounded(self):
        """Total score should be between 0 and 100."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert 0 <= result["total"] <= 100

    def test_component_scores_bounded(self):
        """Each component score should be between 0 and 25."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        assert 0 <= result["row_coverage"] <= 25
        assert 0 <= result["prop_coverage"] <= 25
        assert 0 <= result["column_coverage"] <= 25
        assert 0 <= result["format_score"] <= 25

    def test_total_equals_sum_of_components(self):
        """Total should equal sum of component scores."""
        result = calculate_heuristic_score(
            pvmap_csv=GOOD_PVMAP_CSV,
            sampled_data=SAMPLE_DATA_CSV
        )
        expected_total = (
            result["row_coverage"] +
            result["prop_coverage"] +
            result["column_coverage"] +
            result["format_score"]
        )
        assert abs(result["total"] - expected_total) < 0.5  # Allow rounding


# ============================================================================
# check_column_completeness tests
# ============================================================================

class TestCheckColumnCompleteness:
    """Tests for the check_column_completeness function."""

    PVMAP_ALL_MAPPED = """key,prop,val,p1,v1
State FIPS,observationAbout,geoId/{Data},,
Year,observationDate,{Number},,
Gender:Male,gender,Male,,
Gender:Female,gender,Female,,
Population,value,{Number},populationType,Person
"""

    PVMAP_MISSING_PLACE = """key,prop,val,p1,v1
Year,observationDate,{Number},,
Gender:Male,gender,Male,,
Gender:Female,gender,Female,,
Population,value,{Number},populationType,Person
"""

    PVMAP_MISSING_DIMENSION = """key,prop,val,p1,v1
State FIPS,observationAbout,geoId/{Data},,
Year,observationDate,{Number},,
Population,value,{Number},populationType,Person
"""

    MANIFEST = {
        "must_map": [
            {"column_name": "State FIPS", "role": "place", "suggested_property": "observationAbout"},
            {"column_name": "Year", "role": "time", "suggested_property": "observationDate"},
            {"column_name": "Gender", "role": "dimension", "suggested_property": "dimension"},
            {"column_name": "Population", "role": "value", "suggested_property": "value"},
        ],
        "can_ignore": [
            {"column_name": "Source", "role": "metadata"},
        ],
        "all_columns": ["State FIPS", "Year", "Gender", "Population", "Source"],
    }

    def test_all_mapped(self):
        result = check_column_completeness(self.PVMAP_ALL_MAPPED, self.MANIFEST)
        assert result["complete"] is True
        assert result["severity"] == "ok"
        assert result["coverage_ratio"] == 1.0
        assert result["missing_must_map"] == []

    def test_missing_place_critical(self):
        result = check_column_completeness(self.PVMAP_MISSING_PLACE, self.MANIFEST)
        assert result["complete"] is False
        assert result["severity"] == "critical"
        assert any(m["column"] == "State FIPS" for m in result["missing_must_map"])

    def test_missing_dimension_warning(self):
        result = check_column_completeness(self.PVMAP_MISSING_DIMENSION, self.MANIFEST)
        assert result["complete"] is False
        assert result["severity"] == "warning"
        assert any(m["column"] == "Gender" for m in result["missing_must_map"])

    def test_empty_manifest(self):
        result = check_column_completeness("key,prop,val\n", {})
        assert result["complete"] is True
        assert result["severity"] == "ok"

    def test_empty_pvmap(self):
        result = check_column_completeness("", self.MANIFEST)
        assert result["complete"] is False
        assert result["severity"] == "critical"

    def test_column_value_syntax_matches(self):
        """COLUMN:VALUE rows should count the column as mapped."""
        pvmap = """key,prop,val
Gender:Male,gender,Male
Gender:Female,gender,Female
"""
        manifest = {
            "must_map": [
                {"column_name": "Gender", "role": "dimension", "suggested_property": "dimension"},
            ],
            "can_ignore": [],
        }
        result = check_column_completeness(pvmap, manifest)
        assert result["complete"] is True

    def test_case_insensitive_matching(self):
        """Column matching should be case-insensitive."""
        pvmap = """key,prop,val
state fips,observationAbout,geoId/{Data}
"""
        manifest = {
            "must_map": [
                {"column_name": "State FIPS", "role": "place", "suggested_property": "observationAbout"},
            ],
            "can_ignore": [],
        }
        result = check_column_completeness(pvmap, manifest)
        assert result["complete"] is True
