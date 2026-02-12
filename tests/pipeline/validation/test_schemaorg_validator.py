"""Tests for schema.org PVMAP validator."""

import pytest
from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab
from src.pipeline.validation.schemaorg_validator import (
    validate_pvmap_properties,
    validate_pvmap_enum_values,
)


@pytest.fixture(autouse=True)
def reset_singleton():
    SchemaOrgVocab.reset()
    yield
    SchemaOrgVocab.reset()


VALID_PVMAP = """key,property,value,property,value
State FIPS,observationAbout,geoId/{Data},,
Year,observationDate,{Number},,
Population,populationType,Person,measuredProperty,count,value,{Number}
Gender:Male,gender,Male,,
Gender:Female,gender,Female,,
"""

PVMAP_WITH_UNKNOWN_PROP = """key,property,value
State,observationAbout,{Data}
Year,observationDate,{Number}
Population,populationType,Person,measuredProperty,count,value,{Number}
Category,fakePropertyXYZ123,SomeValue
"""

PVMAP_MISSING_REQUIRED = """key,property,value
Population,populationType,Person,measuredProperty,count,value,{Number}
Gender:Male,gender,Male
"""

PVMAP_WITH_DC_EXTENSIONS = """key,property,value
State,observationAbout,{Data}
Year,observationDate,{Number}
Pop,populationType,Person,measuredProperty,count,value,{Number}
AgeGroup,age,Years18To24
Race,race,WhiteAlone
"""


class TestValidPVMAP:
    def test_valid_pvmap_passes(self):
        valid, warnings = validate_pvmap_properties(VALID_PVMAP, "Person")
        # Should have no unknown-property or missing-required warnings
        unknown_warnings = [w for w in warnings if "Unknown properties" in w]
        assert len(unknown_warnings) == 0

    def test_empty_pvmap_passes(self):
        valid, warnings = validate_pvmap_properties("", "Person")
        assert valid is True
        assert warnings == []


class TestUnknownProperties:
    def test_unknown_property_flagged(self):
        valid, warnings = validate_pvmap_properties(PVMAP_WITH_UNKNOWN_PROP)
        schema_warnings = [w for w in warnings if "Unknown properties" in w]
        assert len(schema_warnings) > 0
        assert "fakePropertyXYZ123" in schema_warnings[0]


class TestMissingRequired:
    def test_missing_observation_about(self):
        valid, warnings = validate_pvmap_properties(PVMAP_MISSING_REQUIRED)
        about_warnings = [w for w in warnings if "observationAbout" in w]
        assert len(about_warnings) > 0

    def test_missing_observation_date(self):
        valid, warnings = validate_pvmap_properties(PVMAP_MISSING_REQUIRED)
        date_warnings = [w for w in warnings if "observationDate" in w]
        assert len(date_warnings) > 0


class TestDCExtensions:
    def test_dc_properties_not_flagged_as_unknown(self):
        """DC-only properties (age, race) should not be flagged as unknown."""
        valid, warnings = validate_pvmap_properties(PVMAP_WITH_DC_EXTENSIONS)
        unknown_warnings = [w for w in warnings if "Unknown properties" in w]
        assert len(unknown_warnings) == 0

    def test_known_pop_type(self):
        valid, warnings = validate_pvmap_properties(PVMAP_WITH_DC_EXTENSIONS)
        type_warnings = [w for w in warnings if "not a known" in w and "populationType" in w]
        assert len(type_warnings) == 0


class TestGracefulDegradation:
    def test_missing_vocab_returns_clean(self, tmp_path):
        """With no vocab cache, validation should pass gracefully."""
        SchemaOrgVocab.reset()
        # Create instance with empty cache
        vocab = SchemaOrgVocab(cache_dir=tmp_path)
        SchemaOrgVocab._instance = vocab

        valid, warnings = validate_pvmap_properties(VALID_PVMAP)
        assert valid is True
        assert warnings == []

        SchemaOrgVocab.reset()


class TestPopulationType:
    def test_unknown_population_type_warned(self):
        pvmap = """key,property,value
State,observationAbout,{Data}
Year,observationDate,{Number}
Pop,populationType,TotallyFakeTypeXYZ,value,{Number}
"""
        valid, warnings = validate_pvmap_properties(pvmap)
        type_warnings = [w for w in warnings if "TotallyFakeTypeXYZ" in w]
        assert len(type_warnings) > 0


# ============================================================================
# Tests for validate_pvmap_enum_values()
# ============================================================================

SAMPLE_VOCAB = {
    "gender": ["Female", "Male"],
    "race": ["WhiteAlone", "BlackOrAfricanAmericanAlone", "AsianAlone"],
    "healthInsurance": ["NoHealthInsurance", "WithHealthInsurance"],
}


class TestEnumValuesCorrect:
    def test_correct_enum_passes(self):
        pvmap = """key,property,value
Gender:Male,gender,Male
Gender:Female,gender,Female
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is True
        assert warnings == []

    def test_case_insensitive_match(self):
        """Case-insensitive match should NOT generate warning."""
        pvmap = """key,property,value
Gender:male,gender,male
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is True
        assert warnings == []


class TestEnumValuesWrong:
    def test_wrong_case_generates_warning_with_suggestion(self):
        """Wrong case that doesn't match case-insensitively should warn."""
        pvmap = """key,property,value
Gender:M,gender,M
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is False
        assert len(warnings) == 1
        assert "ENUM WARNING" in warnings[0]
        assert "gender" in warnings[0]

    def test_unknown_value_generates_warning(self):
        pvmap = """key,property,value
Race:Other,race,TotallyUnknownRace
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is False
        assert len(warnings) == 1
        assert "ENUM WARNING" in warnings[0]
        assert "race" in warnings[0]
        assert "TotallyUnknownRace" in warnings[0]


class TestEnumValuesSkipped:
    def test_structural_properties_skipped(self):
        """observationAbout, value, etc. should never be enum-checked."""
        pvmap = """key,property,value
State,observationAbout,SomeRandomPlace
Year,observationDate,2020
Pop,value,12345
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is True
        assert warnings == []

    def test_placeholders_skipped(self):
        pvmap = """key,property,value
Gender,gender,{Data}
Race,race,{Number}
Health,healthInsurance,[DATA]
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is True
        assert warnings == []

    def test_dcid_values_skipped(self):
        pvmap = """key,property,value
Gender,gender,dcid:Male
Race,race,dcs:WhiteAlone
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is True
        assert warnings == []

    def test_empty_vocab_returns_no_warnings(self):
        pvmap = """key,property,value
Gender:Male,gender,Male
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, {})
        assert valid is True
        assert warnings == []

    def test_property_not_in_vocab_skipped(self):
        """Property not in vocabulary should be silently skipped (no false positive)."""
        pvmap = """key,property,value
Category,someUnknownProp,SomeValue
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is True
        assert warnings == []

    def test_empty_pvmap_passes(self):
        valid, warnings = validate_pvmap_enum_values("", SAMPLE_VOCAB)
        assert valid is True
        assert warnings == []

    def test_empty_string_value_skipped(self):
        """Empty string values (used for totals) should be skipped."""
        pvmap = '''key,property,value
Gender:Total,gender,""
'''
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is True
        assert warnings == []


class TestEnumFuzzySuggestion:
    def test_close_match_suggests_correction(self):
        """A close misspelling should suggest the correct value."""
        pvmap = """key,property,value
Gender:Male,gender,Mala
"""
        valid, warnings = validate_pvmap_enum_values(pvmap, SAMPLE_VOCAB)
        assert valid is False
        assert len(warnings) == 1
        assert "Did you mean" in warnings[0]
        assert "Male" in warnings[0]
