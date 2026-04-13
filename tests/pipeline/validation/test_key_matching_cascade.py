"""Tests for the normalization-first key matching cascade in pvmap_repair.py."""
import pytest

from src.pipeline.validation.pvmap_repair import (
    match_key_to_header,
    build_key_index,
)


@pytest.fixture
def census_headers():
    return [
        "year", "statefips", "countyfips", "geocat",
        "agecat", "racecat", "sexcat", "iprcat",
        "NIPR", "NUI", "NIC", "PCTUI", "PCTIC",
        "state_name", "county_name",
    ]


@pytest.fixture
def census_index(census_headers):
    return build_key_index(census_headers)


class TestExactMatch:
    def test_exact_match_returns_none(self, census_headers, census_index):
        """Exact match = already correct, returns None."""
        assert match_key_to_header("year", census_index, census_headers) is None

    def test_case_mismatch_returns_correct(self, census_headers, census_index):
        assert match_key_to_header("Year", census_index, census_headers) == "year"
        assert match_key_to_header("YEAR", census_index, census_headers) == "year"


class TestNormalizedMatch:
    def test_underscore_vs_space(self):
        headers = ["State FIPS Code", "County Name"]
        index = build_key_index(headers)
        assert match_key_to_header("state_fips_code", index, headers) == "State FIPS Code"

    def test_extra_whitespace(self):
        headers = ["Population Count"]
        index = build_key_index(headers)
        assert match_key_to_header("Population  Count", index, headers) == "Population Count"


class TestTokenSetMatch:
    def test_permuted_tokens(self):
        headers = ["Female Population"]
        index = build_key_index(headers)
        assert match_key_to_header("Population Female", index, headers) == "Female Population"

    def test_partial_token_overlap(self):
        headers = ["Total Population Male"]
        index = build_key_index(headers)
        assert match_key_to_header("Male Total Population", index, headers) == "Total Population Male"


class TestNumericGuard:
    """Matches that differ ONLY in digits must be REJECTED to prevent data corruption."""

    def test_rejects_numeric_difference(self):
        headers = ["Age 15-19", "Age 20-24", "Age 25-29"]
        index = build_key_index(headers)
        assert match_key_to_header("Age 15-29", index, headers) is None

    def test_rejects_digit_only_change(self):
        headers = ["Income_50k_to_75k", "Income_75k_to_100k"]
        index = build_key_index(headers)
        assert match_key_to_header("Income_50k_to_100k", index, headers) is None

    def test_allows_non_numeric_fuzzy(self):
        headers = ["Population_Count"]
        index = build_key_index(headers)
        assert match_key_to_header("Populaton_Count", index, headers) == "Population_Count"


class TestColumnValueKeys:
    """COLUMN:VALUE keys should only match the column portion."""

    def test_column_value_key_matches_column(self):
        headers = ["racecat"]
        index = build_key_index(headers)
        assert match_key_to_header("racecat:White", index, headers) is None

    def test_mismatched_column_part_gets_fixed(self):
        headers = ["Race Category"]
        index = build_key_index(headers)
        assert match_key_to_header("race_category:White", index, headers) == "Race Category"
