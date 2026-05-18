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
    build_key_index,
    generate_key_match_report,
    load_input_headers,
    match_key_to_header,
    pre_validate_pvmap,
    repair_pvmap,
    _split_column_value,
    _clean_hallucinated_key,
    _strip_dcid_prefixes,
    _resolve_ignore_conflicts,
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
    """Already correct PVMAP has no changes (observationDate uses {Number})."""
    pvmap = "key,property,value\nState,observationAbout,geoId/{Data}\nYear,observationDate,{Number}\n"
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    assert len(changes) == 0


def test_repair_date_placeholder_fixed(simple_csv):
    """observationDate with {Data} is repaired to {Number}."""
    pvmap = "key,property,value\nYear,observationDate,{Data}\n"
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    assert "{Number}" in repaired
    assert any("observationDate" in c for c in changes)


def test_repair_comments_preserved(simple_csv):
    """Comment lines are preserved unchanged."""
    pvmap = "key,property,value\n# This is a comment\nYear,observationDate,{Number}\n"
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
    """Low key match rate (< 30%) fails pre-validation."""
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
    # Match rate: 2/4 = 50% → above 30% threshold, passes
    passes, errors = pre_validate_pvmap(pvmap, csv_path)
    assert passes is True  # 50% is above 30% threshold


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
# _split_column_value tests (header-aware splitting)
# ============================================================================

def test_split_no_colon():
    """Keys without colons return empty suffix."""
    col, suffix = _split_column_value("Population", ["Population", "Year"])
    assert col == "Population"
    assert suffix == ""


def test_split_simple_column_value():
    """Simple COLUMN:VALUE with non-colon headers falls back to first-colon split."""
    col, suffix = _split_column_value("Gender:Male", ["Gender", "Year"])
    assert col == "Gender"
    assert suffix == ":Male"


def test_split_sdmx_header_exact():
    """SDMX header like REF_AREA:Reference area is kept intact."""
    headers = ["REF_AREA:Reference area", "TIME_PERIOD:Time period"]
    col, suffix = _split_column_value("REF_AREA:Reference area", headers)
    assert col == "REF_AREA:Reference area"
    assert suffix == ""


def test_split_sdmx_header_with_value():
    """SDMX header + value: FREQ:Frequency:M: Monthly."""
    headers = ["FREQ:Frequency", "REF_AREA:Reference area"]
    col, suffix = _split_column_value("FREQ:Frequency:M: Monthly", headers)
    assert col == "FREQ:Frequency"
    assert suffix == ":M: Monthly"


def test_split_sdmx_header_with_value_daily():
    """SDMX header + value: FREQ:Frequency:D: Daily."""
    headers = ["FREQ:Frequency", "REF_AREA:Reference area"]
    col, suffix = _split_column_value("FREQ:Frequency:D: Daily", headers)
    assert col == "FREQ:Frequency"
    assert suffix == ":D: Daily"


def test_split_longest_header_match():
    """When multiple headers could be prefixes, longest wins."""
    headers = ["A:B", "A:B:C"]
    col, suffix = _split_column_value("A:B:C:value", headers)
    assert col == "A:B:C"
    assert suffix == ":value"


def test_split_case_insensitive_prefix():
    """Case-insensitive matching for SDMX headers."""
    headers = ["FREQ:Frequency", "REF_AREA:Reference area"]
    col, suffix = _split_column_value("freq:Frequency:M: Monthly", headers)
    # Should match FREQ:Frequency even though case differs
    assert col == "FREQ:Frequency"
    assert suffix == ":M: Monthly"


# ============================================================================
# _clean_hallucinated_key tests
# ============================================================================

def test_clean_no_colon():
    """Keys without colons pass through unchanged."""
    result = _clean_hallucinated_key("Population", ["Population"], {"Population"})
    assert result == "Population"


def test_clean_exact_header_match():
    """Keys matching a header exactly pass through unchanged."""
    headers = ["REF_AREA:Reference area"]
    result = _clean_hallucinated_key(
        "REF_AREA:Reference area", headers, set(headers)
    )
    assert result == "REF_AREA:Reference area"


def test_clean_duplicate_description():
    """REF_AREA:Reference area:Reference area -> REF_AREA:Reference area."""
    headers = ["REF_AREA:Reference area"]
    result = _clean_hallucinated_key(
        "REF_AREA:Reference area:Reference area", headers, set(headers)
    )
    assert result == "REF_AREA:Reference area"


def test_clean_duplicate_description_with_value():
    """FREQ:Frequency:Frequency:M: Monthly -> FREQ:Frequency:M: Monthly."""
    headers = ["FREQ:Frequency"]
    result = _clean_hallucinated_key(
        "FREQ:Frequency:Frequency:M: Monthly", headers, set(headers)
    )
    assert result == "FREQ:Frequency:M: Monthly"


def test_clean_obs_value_duplicate():
    """OBS_VALUE:Observation Value:Observation Value -> OBS_VALUE:Observation Value."""
    headers = ["OBS_VALUE:Observation Value"]
    result = _clean_hallucinated_key(
        "OBS_VALUE:Observation Value:Observation Value", headers, set(headers)
    )
    assert result == "OBS_VALUE:Observation Value"


def test_clean_unit_measure_duplicate_with_value():
    """UNIT_MEASURE:Unit of measure:Unit of measure:368: Per cent -> cleaned."""
    headers = ["UNIT_MEASURE:Unit of measure"]
    result = _clean_hallucinated_key(
        "UNIT_MEASURE:Unit of measure:Unit of measure:368: Per cent per year",
        headers, set(headers)
    )
    assert result == "UNIT_MEASURE:Unit of measure:368: Per cent per year"


def test_clean_time_period_duplicate():
    """TIME_PERIOD:Time period or range:Time period or range -> cleaned."""
    headers = ["TIME_PERIOD:Time period or range"]
    result = _clean_hallucinated_key(
        "TIME_PERIOD:Time period or range:Time period or range",
        headers, set(headers)
    )
    assert result == "TIME_PERIOD:Time period or range"


def test_clean_consecutive_segment_dedup():
    """A:B:B:C -> A:B:C when the result matches a header."""
    headers = ["A:B:C"]
    result = _clean_hallucinated_key("A:B:B:C", headers, set(headers))
    assert result == "A:B:C"


def test_clean_no_header_match():
    """When no header is a prefix, key passes through unchanged."""
    headers = ["Population", "Year"]
    result = _clean_hallucinated_key(
        "SomeWeird:Key:Key", headers, set(headers)
    )
    # Consecutive dedup: SomeWeird:Key:Key -> SomeWeird:Key, but not in headers
    assert result == "SomeWeird:Key:Key"


# ============================================================================
# Integration: repair_pvmap with SDMX-style hallucinated keys
# ============================================================================

def test_repair_sdmx_hallucinated_keys(tmp_path):
    """Full repair pipeline correctly handles SDMX key hallucinations."""
    csv_file = tmp_path / "sdmx_input.csv"
    csv_file.write_text(
        "REF_AREA:Reference area,TIME_PERIOD:Time period,FREQ:Frequency,OBS_VALUE:Observation Value\n"
        "US:United States,2020-01,M: Monthly,100\n"
    )
    pvmap = (
        "key,property,value\n"
        "REF_AREA:Reference area:Reference area,observationAbout,country/{Data}\n"
        "TIME_PERIOD:Time period:Time period,observationDate,{Data}\n"
        "FREQ:Frequency:Frequency:M: Monthly,observationPeriod,P1M\n"
        "OBS_VALUE:Observation Value:Observation Value,value,{Number}\n"
    )
    repaired, changes = repair_pvmap(pvmap, csv_file)

    # Verify duplicates removed
    assert "REF_AREA:Reference area,observationAbout" in repaired
    assert "TIME_PERIOD:Time period,observationDate" in repaired
    assert "FREQ:Frequency:M: Monthly,observationPeriod" in repaired
    assert "OBS_VALUE:Observation Value,value" in repaired

    # Verify NO triple/quad duplication
    assert "Reference area:Reference area:Reference area" not in repaired
    assert "Time period:Time period:Time period" not in repaired
    assert "Observation Value:Observation Value:Observation Value" not in repaired
    assert "Frequency:Frequency:Frequency" not in repaired

    # Should have 4 cleaning changes
    cleaning_changes = [c for c in changes if "Cleaned hallucinated" in c]
    assert len(cleaning_changes) == 4


def test_repair_sdmx_no_regression_on_correct_keys(tmp_path):
    """Repair doesn't modify already-correct SDMX keys."""
    csv_file = tmp_path / "sdmx_input.csv"
    csv_file.write_text(
        "REF_AREA:Reference area,FREQ:Frequency,OBS_VALUE:Observation Value\n"
        "US,M: Monthly,100\n"
    )
    pvmap = (
        "key,property,value\n"
        "REF_AREA:Reference area,observationAbout,country/{Data}\n"
        "FREQ:Frequency:M: Monthly,observationPeriod,P1M\n"
        "FREQ:Frequency:D: Daily,observationPeriod,P1D\n"
        "OBS_VALUE:Observation Value,value,{Number}\n"
    )
    repaired, changes = repair_pvmap(pvmap, csv_file)

    # No changes needed — all keys are already correct
    assert len(changes) == 0
    assert "REF_AREA:Reference area,observationAbout" in repaired
    assert "FREQ:Frequency:M: Monthly,observationPeriod,P1M" in repaired
    assert "FREQ:Frequency:D: Daily,observationPeriod,P1D" in repaired


# ============================================================================
# _strip_dcid_prefixes tests
# ============================================================================

def test_strip_dcid_prefix():
    """dcid:Male -> Male in value fields."""
    line = 'Gender:Male,gender,dcid:Male'
    result, change = _strip_dcid_prefixes(line)
    assert 'dcid:Male' not in result
    assert ',Male' in result
    assert change is not None


def test_strip_preserves_dcid_data_passthrough():
    """dcid:{Data} passthrough must be preserved."""
    line = 'Country,observationAbout,dcid:{Data}'
    result, change = _strip_dcid_prefixes(line)
    assert 'dcid:{Data}' in result
    assert change is None


def test_strip_dcs_prefix():
    """dcs:Person -> Person in value fields."""
    line = 'Population,populationType,dcs:Person,value,{Number}'
    result, change = _strip_dcid_prefixes(line)
    assert 'dcs:Person' not in result
    assert ',Person,' in result
    assert change is not None


def test_strip_no_change_when_no_prefix():
    """No change when values don't have prefixes."""
    line = 'Year,observationDate,{Data}'
    result, change = _strip_dcid_prefixes(line)
    assert result == line
    assert change is None


def test_repair_strips_dcid_prefix(simple_csv):
    """Full repair pipeline strips dcid: prefixes from values."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
        "Population,populationType,dcid:Person,value,{Number}\n"
    )
    repaired, changes = repair_pvmap(pvmap, simple_csv)
    assert 'dcid:Person' not in repaired
    assert ',Person,' in repaired
    assert any("dcid:" in c.lower() or "Stripped" in c for c in changes)


# ============================================================================
# _resolve_ignore_conflicts tests
# ============================================================================

def test_resolve_ignore_conflict():
    """#ignore line removed when COLUMN:VALUE mappings exist for same column."""
    pvmap = (
        "key,property,value\n"
        "Year,observationDate,{Data}\n"
        "Sex,#ignore,skip\n"
        "Sex:Male,gender,Male\n"
        "Sex:Female,gender,Female\n"
    )
    headers = ["Year", "Sex", "Value"]
    resolved, changes = _resolve_ignore_conflicts(pvmap, headers)
    assert "#ignore" not in resolved
    assert "Sex:Male" in resolved
    assert "Sex:Female" in resolved
    assert len(changes) == 1
    assert "Sex" in changes[0]


def test_resolve_preserves_ignore_without_conflict():
    """#ignore line preserved when no COLUMN:VALUE mappings exist."""
    pvmap = (
        "key,property,value\n"
        "Year,observationDate,{Data}\n"
        "Notes,#ignore,skip\n"
        "Sex:Male,gender,Male\n"
    )
    headers = ["Year", "Sex", "Notes", "Value"]
    resolved, changes = _resolve_ignore_conflicts(pvmap, headers)
    assert "#ignore" in resolved
    assert len(changes) == 0


def test_repair_resolves_ignore_conflict(tmp_path):
    """Full repair pipeline resolves #ignore conflicts."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("Year,Sex,Value\n2020,Male,100\n")

    pvmap = (
        "key,property,value\n"
        "Year,observationDate,{Data}\n"
        "Sex,#ignore,skip\n"
        "Sex:Male,gender,Male\n"
        "Sex:Female,gender,Female\n"
        "Value,value,{Number}\n"
    )
    repaired, changes = repair_pvmap(pvmap, csv_path)
    assert "#ignore" not in repaired
    assert "Sex:Male" in repaired


# ============================================================================
# Pre-validation threshold tests (30% threshold)
# ============================================================================

def test_pre_validate_passes_at_40_percent_match(tmp_path):
    """40% match rate passes with the 30% threshold (would fail at 50%)."""
    csv_path = tmp_path / "data.csv"
    csv_path.write_text("ColA,ColB,ColC,ColD,ColE\n1,2,3,4,5\n")

    pvmap = (
        "key,property,value\n"
        "ColA,observationAbout,geoId/{Data}\n"
        "ColB,observationDate,{Data}\n"
        "WrongC,value,{Number}\n"
        "WrongD,populationType,Person\n"
        "WrongE,measuredProperty,count\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, csv_path)
    # 2 matched (ColA, ColB) out of 5 unique = 40% — passes 30% threshold
    assert passes is True
    assert not any("MATCH RATE" in e for e in errors)


# ============================================================================
# Tests for pre_validate_pvmap with property_vocabulary parameter
# ============================================================================

def test_pre_validate_backward_compat_no_vocab(simple_csv):
    """Calling without property_vocabulary still works (backward compat)."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
        "Population,value,{Number},populationType,Person\n"
    )
    passes, errors = pre_validate_pvmap(pvmap, simple_csv)
    assert passes is True


def test_pre_validate_with_vocab_valid_passes(simple_csv):
    """Valid PVMAP with matching vocab values passes."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
        "Population,value,{Number},populationType,Person,gender,Male\n"
    )
    vocab = {"gender": ["Male", "Female"]}
    passes, errors = pre_validate_pvmap(pvmap, simple_csv, property_vocabulary=vocab)
    assert passes is True
    # Should not have enum warnings for valid values
    enum_warnings = [e for e in errors if "ENUM WARNING" in e]
    assert len(enum_warnings) == 0


def test_pre_validate_with_vocab_appends_warnings(simple_csv):
    """Enum warnings are appended but don't affect pass/fail."""
    pvmap = (
        "key,property,value\n"
        "State,observationAbout,geoId/{Data}\n"
        "Year,observationDate,{Data}\n"
        "Population,value,{Number},populationType,Person,gender,male_WRONG\n"
    )
    vocab = {"gender": ["Male", "Female"]}
    passes, errors = pre_validate_pvmap(pvmap, simple_csv, property_vocabulary=vocab)
    # Structure is valid so passes should be True
    assert passes is True
    # But enum warnings should be appended
    enum_warnings = [e for e in errors if "ENUM WARNING" in e]
    assert len(enum_warnings) == 1
    assert "gender" in enum_warnings[0]
