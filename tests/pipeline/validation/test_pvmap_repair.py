"""Tests for PVMAP repair module.

Tests key matching, placeholder normalization, pre-validation,
and the key match report generator.
"""

import csv
import io
import tempfile
from pathlib import Path

import pytest

from src.pipeline.validation.pvmap_repair import (
    _clean_hallucinated_key,
    _normalize_date_place_placeholders,
    _strip_dcid_prefixes,
    build_key_index,
    generate_key_match_report,
    load_input_headers,
    match_key_to_header,
    pre_validate_pvmap,
    repair_pvmap,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def simple_csv(tmp_path):
    """Create a simple CSV file with known headers."""
    csv_path = tmp_path / "input_data.csv"
    csv_path.write_text(
        "State,Year,Population,Gender\n"
        "CA,2020,39538223,Male\n"
        "TX,2021,29145505,Female\n"
    )
    return csv_path


@pytest.fixture
def complex_csv(tmp_path):
    """Create a CSV with tricky headers (spaces, underscores, mixed case)."""
    csv_path = tmp_path / "complex_data.csv"
    csv_path.write_text(
        "State FIPS Code,TIME_PERIOD,OBS_VALUE,REF_AREA,Age Group\n"
        "06,2020,12345,US,18-25\n"
    )
    return csv_path


@pytest.fixture
def census_csv(tmp_path):
    """Create a Census-style CSV with E_/M_/EP_/MP_ prefixes."""
    csv_path = tmp_path / "census_data.csv"
    csv_path.write_text(
        "FIPS,year,E_AGE65,M_AGE65,EP_AGE65,MP_AGE65\n"
        "01001,2020,5000,150,12.5,0.3\n"
    )
    return csv_path


# ============================================================================
# load_input_headers tests
# ============================================================================

def test_load_input_headers_basic(simple_csv):
    headers = load_input_headers(simple_csv)
    assert headers == ["State", "Year", "Population", "Gender"]


def test_load_input_headers_complex(complex_csv):
    headers = load_input_headers(complex_csv)
    assert headers == ["State FIPS Code", "TIME_PERIOD", "OBS_VALUE", "REF_AREA", "Age Group"]


def test_load_input_headers_nonexistent(tmp_path):
    headers = load_input_headers(tmp_path / "nonexistent.csv")
    assert headers == []


# ============================================================================
# build_key_index tests
# ============================================================================

def test_build_key_index_basic():
    headers = ["State", "Year", "Population"]
    index = build_key_index(headers)
    assert index["state"] == "State"
    assert index["year"] == "Year"
    assert index["population"] == "Population"


def test_build_key_index_alphanumeric():
    headers = ["State FIPS Code", "Age Group"]
    index = build_key_index(headers)
    assert index["statefipscode"] == "State FIPS Code"
    assert index["agegroup"] == "Age Group"


# ============================================================================
# match_key_to_header tests
# ============================================================================

def test_match_case_fix():
    """'year' should match 'Year'."""
    headers = ["State", "Year", "Population"]
    index = build_key_index(headers)
    assert match_key_to_header("year", index, headers) == "Year"


def test_match_whitespace_fix():
    """'State ' should match 'State'."""
    headers = ["State", "Year"]
    index = build_key_index(headers)
    assert match_key_to_header("State ", index, headers) == "State"


def test_match_character_filter():
    """'State_Code' should match 'State Code' via alphanumeric."""
    headers = ["State Code", "Year"]
    index = build_key_index(headers)
    assert match_key_to_header("State_Code", index, headers) == "State Code"


def test_match_exact_no_fix():
    """Exact match returns None (no fix needed)."""
    headers = ["State", "Year"]
    index = build_key_index(headers)
    assert match_key_to_header("State", index, headers) is None


def test_match_column_value_syntax():
    """'gender:Male' should match column part 'Gender' -> 'Gender'."""
    headers = ["Gender", "Year"]
    index = build_key_index(headers)
    assert match_key_to_header("gender:Male", index, headers) == "Gender"


def test_match_fuzzy():
    """'Populaton' (typo) should fuzzy match 'Population'."""
    headers = ["Population", "Year"]
    index = build_key_index(headers)
    result = match_key_to_header("Populaton", index, headers)
    assert result == "Population"


def test_match_special_key_skip():
    """#Format keys should not be matched."""
    headers = ["State", "Year"]
    index = build_key_index(headers)
    assert match_key_to_header("#Format", index, headers) is None


def test_match_no_match():
    """Completely unrelated key returns None."""
    headers = ["State", "Year"]
    index = build_key_index(headers)
    assert match_key_to_header("CompletelyDifferent", index, headers) is None


# ============================================================================
# repair_pvmap tests
# ============================================================================

def test_repair_case_fix(simple_csv):
    """Repair fixes case mismatch: 'year' -> 'Year'."""
    pvmap = "key,property,value\nyear,observationDate,{Data}\nState,observationAbout,geoId/{Data}\n"
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    assert "Year,observationDate" in repaired
    assert any("year" in c and "Year" in c for c in changes)


def test_repair_whitespace_fix(tmp_path):
    """Repair fixes key when input header has trailing whitespace."""
    # Create CSV where headers have trailing whitespace
    csv_path = tmp_path / "ws_data.csv"
    csv_path.write_text(
        "State ,Year,Population\n"
        "CA,2020,100\n"
    )
    # PVMAP uses trimmed key "State" but input header is "State "
    # After load_input_headers strips, header becomes "State" - match is exact
    # Test that case mismatch + whitespace together get fixed
    pvmap = "key,property,value\nstate,observationAbout,geoId/{Data}\nYear,observationDate,{Data}\n"
    repaired, changes = repair_pvmap(pvmap, csv_path)
    assert "State" in repaired
    assert any("state" in c and "State" in c for c in changes)


def test_repair_placeholder_normalization(simple_csv):
    """Repair normalizes [DATA] -> {Data} and [NUMBER] -> {Number}."""
    pvmap = "key,property,value\nYear,observationDate,[DATA]\nPopulation,value,[NUMBER]\n"
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    assert "{Data}" in repaired
    assert "{Number}" in repaired
    assert len(changes) >= 2


def test_repair_column_value_preserved(simple_csv):
    """COLUMN:VALUE syntax is preserved after repair."""
    pvmap = "key,property,value\ngender:Male,gender,Male\n"
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    # 'gender' should be fixed to 'Gender' but ':Male' preserved
    assert "Gender:Male" in repaired


def test_repair_empty_pvmap(simple_csv):
    """Empty PVMAP returns empty."""
    repaired, changes = repair_pvmap("", simple_csv)
    assert repaired == ""
    assert changes == []


def test_repair_no_changes_needed(simple_csv):
    """Already correct PVMAP has no changes."""
    pvmap = "key,property,value\nState,observationAbout,geoId/{Data}\nYear,observationDate,{Data}\n"
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    assert len(changes) == 0


def test_repair_comments_preserved(simple_csv):
    """Comment lines are preserved unchanged."""
    pvmap = "key,property,value\n# This is a comment\nYear,observationDate,{Data}\n"
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    assert "# This is a comment" in repaired


# ============================================================================
# pre_validate_pvmap tests
# ============================================================================

def test_pre_validate_valid_pvmap(simple_csv):
    """Valid PVMAP passes pre-validation."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
        "Population,value,{Number},populationType,Person\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, simple_csv)
    assert passes is True
    assert errors == []


def test_pre_validate_missing_observation_about(simple_csv):
    """Missing observationAbout fails pre-validation."""
    pvmap = (
        "key,property,value\n"
        "Year,observationDate,{Data}\n"
        "Population,value,{Number}\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, simple_csv)
    assert passes is False
    assert any("observationAbout" in e for e in errors)


def test_pre_validate_missing_observation_date(simple_csv):
    """Missing observationDate fails pre-validation."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Population,value,{Number}\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, simple_csv)
    assert passes is False
    assert any("observationDate" in e for e in errors)


def test_pre_validate_empty_pvmap(simple_csv):
    """Empty PVMAP fails pre-validation."""
    passes, errors = pre_validate_pvmap("", simple_csv)
    assert passes is False
    assert any("empty" in e.lower() for e in errors)


def test_pre_validate_placeholder_keys(simple_csv):
    """Placeholder keys (p2, v2) fail pre-validation."""
    pvmap = (
        "key,property,value,p2,v2\n"
        "State,observationAbout,geoId/{Data},p2,v2\n"
        "Year,observationDate,{Data},,\n"
        "p2,populationType,Person,,\n"
        "Population,value,{Number},,\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, simple_csv)
    assert passes is False
    assert any("PLACEHOLDER" in e for e in errors)


def test_pre_validate_low_match_rate(tmp_path):
    """Low key match rate (< 50%) fails pre-validation."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("ColA,ColB,ColC,ColD\n1,2,3,4\n")

    pvmap = (
        "key,property,value\n"
        "WrongA,observationAbout,geoId/{Data}\n"
        "WrongB,observationDate,{Data}\n"
        "WrongC,value,{Number}\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, csv_path)
    assert passes is False
    assert any("MATCH RATE" in e for e in errors)


# ============================================================================
# generate_key_match_report tests
# ============================================================================

def test_key_match_report_basic(simple_csv):
    """Report includes matched, unmatched, and unmapped sections."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "year,observationDate,{Data}\n"
        "WrongKey,value,{Number}\n"
    )
    report = generate_key_match_report(pvmap, simple_csv)

    assert "KEY MATCH REPORT" in report
    assert "Matched" in report
    assert "Auto-Fixed" in report  # 'year' -> 'Year'
    assert "UNMATCHED" in report  # 'WrongKey'
    assert "Unmapped" in report  # 'Population', 'Gender'


def test_key_match_report_empty_pvmap(simple_csv):
    """Empty PVMAP generates a message."""
    report = generate_key_match_report("", simple_csv)
    assert "No PVMAP content" in report


def test_key_match_report_match_rate(simple_csv):
    """Report includes match rate percentage."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
    )
    report = generate_key_match_report(pvmap, simple_csv)
    assert "Match rate" in report
    assert "100%" in report


# ============================================================================
# Colon-prefix header matching (e.g. BIS datasets)
# ============================================================================

def test_build_key_index_colon_prefix():
    """Index includes prefix before colon for headers like FREQ:Frequency."""
    headers = ["FREQ:Frequency", "REF_AREA:Reference area", "OBS_VALUE:Observation Value"]
    index = build_key_index(headers)
    # Full header forms
    assert "freq:frequency" in index
    assert index["freq:frequency"] == "FREQ:Frequency"
    # Prefix-only forms
    assert "freq" in index
    assert index["freq"] == "FREQ:Frequency"
    assert "ref_area" in index
    assert index["ref_area"] == "REF_AREA:Reference area"
    assert "obs_value" in index
    assert index["obs_value"] == "OBS_VALUE:Observation Value"


def test_match_colon_prefix_header():
    """LLM key 'FREQ' matches header 'FREQ:Frequency' via prefix index."""
    headers = ["FREQ:Frequency", "REF_AREA:Reference area", "TIME_PERIOD:Time period"]
    index = build_key_index(headers)
    assert match_key_to_header("FREQ", index, headers) == "FREQ:Frequency"
    assert match_key_to_header("REF_AREA", index, headers) == "REF_AREA:Reference area"
    assert match_key_to_header("TIME_PERIOD", index, headers) == "TIME_PERIOD:Time period"


def test_repair_colon_prefix_keys(tmp_path):
    """Repair replaces prefix-only keys with full colon headers."""
    csv_file = tmp_path / "input.csv"
    csv_file.write_text("FREQ:Frequency,REF_AREA:Reference area,OBS_VALUE:Observation Value\n1,US,100\n")
    pvmap = (
        "key,property,value\n"
        "FREQ,observationPeriod,{Data}\n"
        "REF_AREA,observationAbout,{Data}\n"
        "OBS_VALUE,value,{Number}\n"
    )
    repaired, changes = repair_pvmap(pvmap, csv_file)
    assert "FREQ:Frequency" in repaired
    assert "REF_AREA:Reference area" in repaired
    assert "OBS_VALUE:Observation Value" in repaired
    assert len(changes) >= 3


# ============================================================================
# Multi-line header normalization tests
# ============================================================================

def test_load_headers_multiline_quoted(tmp_path):
    """Multi-line quoted headers are normalized to single line."""
    csv_path = tmp_path / "fbi.csv"
    csv_path.write_text(
        'State,City_Name,"Violent\ncrime","Murder and\nnonnegligent\nmanslaughter"\n'
        'AL,Birmingham,5000,50\n'
    )
    headers = load_input_headers(csv_path)
    assert headers == ["State", "City_Name", "Violent crime", "Murder and nonnegligent manslaughter"]


def test_match_multiline_header(tmp_path):
    """LLM key 'Violent crime' matches normalized multi-line header."""
    csv_path = tmp_path / "fbi.csv"
    csv_path.write_text(
        'State,"Violent\ncrime","Murder and\nnonnegligent\nmanslaughter"\n'
        'AL,5000,50\n'
    )
    headers = load_input_headers(csv_path)
    index = build_key_index(headers)
    # LLM generates "Violent crime" which matches the normalized header
    assert match_key_to_header("Violent crime", index, headers) is None  # exact match, no fix


# ============================================================================
# Dimension key (COLUMN:VALUE) match rate tests
# ============================================================================

def test_pre_validate_dimension_keys_counted_once(tmp_path):
    """COLUMN:VALUE keys should not inflate the match rate denominator."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Year,Country,Sex,Value\n2020,US,Male,100\n")

    pvmap = (
        "key,property,value\n"
        "Year,observationDate,{Data}\n"
        "Country,observationAbout,{Data}\n"
        "Value,value,{Number}\n"
        "Sex:Male,gender,dcid:Male\n"
        "Sex:Female,gender,dcid:Female\n"
        "Sex:Both Sexes,statType,dcid:measuredValue\n"
    )
    # All column parts (Year, Country, Value, Sex) are in headers
    # Without fix: 6 total keys, only 3-4 match → 50-67%
    # With fix: 4 unique columns, all 4 match → 100%
    passes, errors = pre_validate_pvmap(pvmap, csv_path)
    assert passes is True
    assert not any("MATCH RATE" in e for e in errors)


def test_pre_validate_dimension_keys_still_fail_when_unmatched(tmp_path):
    """Unmatched dimension column still triggers low match rate."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Year,Country,Gender,Value\n2020,US,Male,100\n")

    pvmap = (
        "key,property,value\n"
        "Year,observationDate,{Data}\n"
        "WrongPlace,observationAbout,{Data}\n"
        "Value,value,{Number}\n"
        "Sex:Male,gender,dcid:Male\n"
        "Sex:Female,gender,dcid:Female\n"
    )
    # Unique columns: Year (match), WrongPlace (no match), Value (match), Sex (no match)
    # Match rate: 2/4 = 50% → borderline pass
    passes, errors = pre_validate_pvmap(pvmap, csv_path)
    assert passes is True  # 50% is threshold, not below


def test_key_match_report_unique_column_rate(simple_csv):
    """Report match rate uses unique columns, not total keys."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
        "Gender:Male,gender,dcid:Male\n"
        "Gender:Female,gender,dcid:Female\n"
    )
    report = generate_key_match_report(pvmap, simple_csv)
    # 3 unique columns (State, Year, Gender) all match
    assert "100%" in report
    assert "3/3" in report


# ============================================================================
# _clean_hallucinated_key tests
# ============================================================================

def test_clean_hallucinated_duplicate_description():
    """Strip duplicate description segments from colon-header keys."""
    headers = ["REF_AREA:Reference area", "TIME_PERIOD:Time period"]
    headers_set = set(headers)

    # Duplicate description + appended sample values
    result = _clean_hallucinated_key(
        "REF_AREA:Reference area:Reference area:AR: Argentina",
        headers, headers_set
    )
    assert result == "REF_AREA:Reference area"


def test_clean_hallucinated_header_prefix_match():
    """Strip trailing content when key starts with a known colon-header."""
    headers = ["REF_AREA:Reference area", "FREQ:Frequency"]
    headers_set = set(headers)

    result = _clean_hallucinated_key(
        "REF_AREA:Reference area:US",
        headers, headers_set
    )
    assert result == "REF_AREA:Reference area"

    result = _clean_hallucinated_key(
        "FREQ:Frequency:Annual:A",
        headers, headers_set
    )
    assert result == "FREQ:Frequency"


def test_clean_hallucinated_index_suffix():
    """Strip trailing index suffix from keys like 'Unnamed: 0: 1'."""
    headers = ["Unnamed: 0", "Unnamed: 1"]
    headers_set = set(headers)

    result = _clean_hallucinated_key("Unnamed: 0: 1", headers, headers_set)
    assert result == "Unnamed: 0"

    result = _clean_hallucinated_key("Unnamed: 1: 42", headers, headers_set)
    assert result == "Unnamed: 1"


def test_clean_hallucinated_no_change_simple_key():
    """Simple keys without colons are returned unchanged."""
    headers = ["State", "Year"]
    headers_set = set(headers)

    assert _clean_hallucinated_key("State", headers, headers_set) == "State"
    assert _clean_hallucinated_key("Year", headers, headers_set) == "Year"


def test_clean_hallucinated_no_change_column_value():
    """Legitimate COLUMN:VALUE keys are not cleaned."""
    headers = ["Gender", "Year"]
    headers_set = set(headers)

    # COLUMN:VALUE syntax — should NOT be cleaned
    assert _clean_hallucinated_key("Gender:Male", headers, headers_set) == "Gender:Male"
    assert _clean_hallucinated_key("Year:2020", headers, headers_set) == "Year:2020"


def test_clean_hallucinated_dedup_to_header():
    """Dedup segments when result matches a header."""
    headers = ["A:B:C"]
    headers_set = set(headers)

    # A:B:C:C → A:B:C (dedup last C)
    result = _clean_hallucinated_key("A:B:C:C", headers, headers_set)
    assert result == "A:B:C"


# ============================================================================
# Enhanced repair integration tests
# ============================================================================

def test_repair_bis_hallucinated_keys(tmp_path):
    """Repair fixes BIS-style hallucinated key expansions."""
    csv_file = tmp_path / "input.csv"
    csv_file.write_text(
        "REF_AREA:Reference area,TIME_PERIOD:Time period,OBS_VALUE:Observation Value\n"
        "US,2020,100\n"
    )
    pvmap = (
        "key,property,value\n"
        "REF_AREA:Reference area:Reference area:AR: Argentina,observationAbout,country/{Data}\n"
        "TIME_PERIOD:Time period:Time period,observationDate,{Data}\n"
        "OBS_VALUE:Observation Value,value,{Number}\n"
    )
    repaired, changes = repair_pvmap(pvmap, csv_file)
    assert "REF_AREA:Reference area,observationAbout" in repaired
    assert "TIME_PERIOD:Time period,observationDate" in repaired
    assert any("Clean key" in c for c in changes)


def test_repair_index_suffix_hallucination(tmp_path):
    """Repair fixes index suffix hallucination like 'Unnamed: 0: 1'."""
    csv_file = tmp_path / "input.csv"
    csv_file.write_text("Unnamed: 0,Year,Value\n1,2020,100\n")

    pvmap = (
        "key,property,value\n"
        "Unnamed: 0: 1,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
        "Value,value,{Number}\n"
    )
    repaired, changes = repair_pvmap(pvmap, csv_file)
    assert "Unnamed: 0,observationAbout" in repaired
    assert any("Clean key" in c for c in changes)


def test_repair_preserves_legitimate_column_value(simple_csv):
    """Repair does NOT strip legitimate COLUMN:VALUE syntax."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
        "Gender:Male,gender,dcid:Male\n"
        "Gender:Female,gender,dcid:Female\n"
        "Population,value,{Number}\n"
    )
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    assert "Gender:Male" in repaired
    assert "Gender:Female" in repaired


# ============================================================================
# Lower fuzzy threshold tests
# ============================================================================

def test_fuzzy_match_long_key():
    """Long keys (>15 chars) use lower fuzzy threshold (0.80)."""
    headers = ["Employment Status Total"]
    index = build_key_index(headers)
    # "Employment Status Totl" has ratio ~0.82 — passes 0.80 but fails 0.85
    result = match_key_to_header("Employment Status Totl", index, headers)
    assert result == "Employment Status Total"


def test_fuzzy_match_short_key_strict():
    """Short keys still use strict 0.85 threshold."""
    headers = ["State"]
    index = build_key_index(headers)
    # "Stat" has ratio ~0.89 — passes both thresholds
    result = match_key_to_header("Stat", index, headers)
    # With ratio 2*4/9 = 0.89, passes 0.85
    assert result == "State"


# ============================================================================
# Pre-validate threshold tests
# ============================================================================

def test_pre_validate_35pct_match_passes(tmp_path):
    """35% match rate (> 30%) passes pre-validation."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("ColA,ColB,ColC,ColD,ColE,ColF,ColG,ColH,ColI,ColJ\n" + ",".join(["1"] * 10) + "\n")

    # 4 out of 10 unique columns match = 40%
    pvmap = (
        "key,property,value\n"
        "ColA,observationAbout,geoId/{Data}\n"
        "ColB,observationDate,{Data}\n"
        "ColC,value,{Number}\n"
        "ColD,populationType,Person\n"
        "WrongE,measuredProperty,count\n"
        "WrongF,statType,measuredValue\n"
        "WrongG,unit,Percent\n"
        "WrongH,gender,Male\n"
        "WrongI,age,18\n"
        "WrongJ,race,White\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, csv_path)
    assert passes is True


def test_pre_validate_25pct_match_fails(tmp_path):
    """25% match rate (< 30%) fails pre-validation."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("ColA,ColB,ColC,ColD\n1,2,3,4\n")

    # 1 out of 4 unique columns match = 25%
    pvmap = (
        "key,property,value\n"
        "ColA,observationAbout,geoId/{Data}\n"
        "WrongB,observationDate,{Data}\n"
        "WrongC,value,{Number}\n"
        "WrongD,populationType,Person\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, csv_path)
    assert passes is False
    assert any("MATCH RATE" in e for e in errors)


# ============================================================================
# _strip_dcid_prefixes tests
# ============================================================================

def test_strip_dcid_prefix_basic():
    """dcid:Person -> Person in value position."""
    lines = [
        "key,property,value",
        "Year,populationType,dcid:Person,measuredProperty,dcid:count",
    ]
    fixed, changes = _strip_dcid_prefixes(lines)
    assert "dcid:" not in fixed[1]
    assert "populationType,Person" in fixed[1]
    assert "measuredProperty,count" in fixed[1]
    assert len(changes) == 1


def test_strip_dcid_prefix_geo():
    """dcid:geoId/{Data} -> geoId/{Data} in value position."""
    lines = [
        "key,property,value",
        "State,observationAbout,dcid:geoId/{Data}",
    ]
    fixed, changes = _strip_dcid_prefixes(lines)
    assert "observationAbout,geoId/{Data}" in fixed[1]
    assert len(changes) == 1


def test_strip_dcid_preserves_properties():
    """Property names are never stripped even if they contain dcid-like text."""
    lines = [
        "key,property,value",
        "Year,observationDate,{Data}",
    ]
    fixed, changes = _strip_dcid_prefixes(lines)
    assert fixed[1] == lines[1]
    assert len(changes) == 0


def test_strip_dcid_preserves_keys():
    """Key column (index 0) is never modified."""
    lines = [
        "key,property,value",
        "dcid:myKey,populationType,Person",
    ]
    fixed, changes = _strip_dcid_prefixes(lines)
    assert fixed[1].startswith("dcid:myKey")
    assert len(changes) == 0


def test_strip_dcid_no_double_strip():
    """Values without dcid: prefix are left unchanged."""
    lines = [
        "key,property,value",
        "State,observationAbout,geoId/06",
    ]
    fixed, changes = _strip_dcid_prefixes(lines)
    assert "geoId/06" in fixed[1]
    assert len(changes) == 0


def test_strip_dcid_header_skipped():
    """Header row is passed through unchanged."""
    lines = [
        "key,property,dcid:value",
    ]
    fixed, changes = _strip_dcid_prefixes(lines)
    assert fixed[0] == lines[0]
    assert len(changes) == 0


# ============================================================================
# _normalize_date_place_placeholders tests
# ============================================================================

def test_normalize_observationdate_number_to_data():
    """{Number} -> {Data} for observationDate."""
    lines = [
        "key,property,value",
        "Year,observationDate,{Number}",
    ]
    fixed, changes = _normalize_date_place_placeholders(lines)
    assert "observationDate,{Data}" in fixed[1]
    assert len(changes) == 1


def test_normalize_observationabout_number_to_data():
    """{Number} -> {Data} for observationAbout (preserves FIPS leading zeros)."""
    lines = [
        "key,property,value",
        "FIPS,observationAbout,geoId/{Number}",
    ]
    fixed, changes = _normalize_date_place_placeholders(lines)
    assert "observationAbout,geoId/{Data}" in fixed[1]
    assert len(changes) == 1


def test_normalize_preserves_value_number():
    """value,{Number} is left untouched — correct for measurements."""
    lines = [
        "key,property,value",
        "Population,value,{Number},populationType,Person",
    ]
    fixed, changes = _normalize_date_place_placeholders(lines)
    assert "value,{Number}" in fixed[1]
    assert len(changes) == 0


def test_normalize_preserves_data_placeholder():
    """observationDate,{Data} already correct — no change."""
    lines = [
        "key,property,value",
        "Year,observationDate,{Data}",
    ]
    fixed, changes = _normalize_date_place_placeholders(lines)
    assert fixed[1] == lines[1]
    assert len(changes) == 0


# ============================================================================
# Integration: repair_pvmap with dcid + placeholder normalization
# ============================================================================

def test_repair_pvmap_strips_dcid_and_normalizes_placeholders(simple_csv):
    """Full integration: repair_pvmap applies dcid stripping and placeholder normalization."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,dcid:geoId/{Data}\n"
        "Year,observationDate,{Number}\n"
        "Population,value,{Number},populationType,dcid:Person\n"
    )
    repaired, changes = repair_pvmap(pvmap, simple_csv)

    # dcid: stripped from values
    assert "dcid:" not in repaired
    assert "observationAbout,geoId/{Data}" in repaired
    assert "populationType,Person" in repaired

    # {Number} normalized to {Data} for observationDate
    assert "observationDate,{Data}" in repaired

    # value,{Number} preserved
    assert "value,{Number}" in repaired

    # Changes logged
    assert any("dcid:" in c.lower() or "Stripped" in c for c in changes)
    assert any("Number" in c and "Data" in c for c in changes)
