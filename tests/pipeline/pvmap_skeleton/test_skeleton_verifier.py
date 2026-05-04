"""Tests for skeleton property verification."""

import pytest
from src.pipeline.pvmap_skeleton.skeleton_verifier import (
    verify_skeleton_properties,
    _extract_properties_from_skeleton,
    ALWAYS_VALID_PROPERTIES,
)


class TestExtractProperties:

    def test_extracts_dimension_property(self):
        manifest = {
            "must_map": [
                {"column_name": "Gender", "role": "dimension"},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nGender:Male,gender,Male,\nGender:Female,gender,Female,\n'
        props = _extract_properties_from_skeleton(skeleton, manifest)
        assert "Gender" in props
        assert props["Gender"]["property"] == "gender"
        assert props["Gender"]["role"] == "dimension"

    def test_extracts_place_property(self):
        manifest = {
            "must_map": [
                {"column_name": "State", "role": "place"},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nState,observationAbout,geoId/{Data},\n'
        props = _extract_properties_from_skeleton(skeleton, manifest)
        assert "State" in props
        assert props["State"]["role"] == "place"

    def test_skips_ignore_columns(self):
        manifest = {
            "must_map": [],
            "can_ignore": [{"column_name": "Source", "role": "metadata"}],
        }
        skeleton = 'key,,,\nSource,#ignore,,\n'
        props = _extract_properties_from_skeleton(skeleton, manifest)
        assert "Source" not in props

    def test_first_property_per_column(self):
        """Only tracks the first property seen per column."""
        manifest = {
            "must_map": [
                {"column_name": "Age", "role": "dimension"},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nAge:0-4,age,child,\nAge:5-14,age,teen,\n'
        props = _extract_properties_from_skeleton(skeleton, manifest)
        assert len(props) == 1
        assert props["Age"]["property"] == "age"

    def test_empty_skeleton(self):
        props = _extract_properties_from_skeleton("", {"must_map": [], "can_ignore": []})
        assert props == {}


class TestSchemaOrgVerification:

    def test_known_property_passes(self):
        """Properties like 'gender' exist in Schema.org."""
        manifest = {
            "must_map": [
                {"column_name": "Gender", "role": "dimension",
                 "suggested_property": "dimension", "domain_values": ["Male", "Female"]},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nGender:Male,gender,Male,\nGender:Female,gender,Female,\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        gender_col = result["columns"]["Gender"]
        assert gender_col["property_verified"] is True
        assert gender_col["verification_source"] in ("schema_org", "dc_extension", "dc_built_in")

    def test_unknown_property_flagged(self):
        """Non-existent properties should be flagged."""
        manifest = {
            "must_map": [
                {"column_name": "Freq", "role": "dimension",
                 "suggested_property": "dimension", "domain_values": ["Daily"]},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nFreq:Daily,zzNonExistentProperty,Daily,\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        freq_col = result["columns"]["Freq"]
        assert freq_col["property_verified"] is False

    def test_place_column_always_valid(self):
        """Place columns use observationAbout — always verified."""
        manifest = {
            "must_map": [
                {"column_name": "State", "role": "place", "suggested_property": "observationAbout"},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nState,observationAbout,geoId/{Data},\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        assert result["columns"]["State"]["property_verified"] is True
        assert result["columns"]["State"]["confidence"] == "high"

    def test_time_column_always_valid(self):
        manifest = {
            "must_map": [
                {"column_name": "Year", "role": "time", "suggested_property": "observationDate"},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nYear,observationDate,{Number},\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        assert result["columns"]["Year"]["property_verified"] is True

    def test_value_column_always_valid(self):
        manifest = {
            "must_map": [
                {"column_name": "Pop", "role": "value", "suggested_property": "value"},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,,,\nPop,value,{Number},populationType,Person\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        assert result["columns"]["Pop"]["property_verified"] is True

    def test_ignore_columns_skipped(self):
        """Metadata #ignore columns should not appear in results."""
        manifest = {
            "must_map": [],
            "can_ignore": [{"column_name": "Source", "role": "metadata"}],
        }
        skeleton = 'key,,,\nSource,#ignore,,\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        assert "Source" not in result["columns"]

    def test_empty_property_unverified(self):
        """Empty property cells (for LLM to fill) should be unverified."""
        manifest = {
            "must_map": [
                {"column_name": "Category", "role": "dimension",
                 "suggested_property": "dimension", "domain_values": ["A", "B"]},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nCategory:A,,A,\nCategory:B,,B,\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        cat_col = result["columns"]["Category"]
        assert cat_col["property_verified"] is False
        assert cat_col["verification_source"] == "unverified"

    def test_dc_builtin_property_passes(self):
        """DC built-in properties like observationPeriod should pass."""
        manifest = {
            "must_map": [
                {"column_name": "Freq", "role": "dimension",
                 "domain_values": ["Daily"]},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nFreq:Daily,observationPeriod,P1D,\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        assert result["columns"]["Freq"]["property_verified"] is True
        assert result["columns"]["Freq"]["verification_source"] == "dc_built_in"

    def test_properties_count(self):
        """Verify properties_checked and properties_valid counts."""
        manifest = {
            "must_map": [
                {"column_name": "State", "role": "place"},
                {"column_name": "Year", "role": "time"},
                {"column_name": "Gender", "role": "dimension", "domain_values": ["M"]},
            ],
            "can_ignore": [],
        }
        skeleton = 'key,,,\nState,observationAbout,{Data},\nYear,observationDate,{Number},\nGender:M,gender,M,\n'
        result = verify_skeleton_properties(skeleton, manifest, data_context={})
        assert result["properties_checked"] == 3
        assert result["properties_valid"] >= 2  # place + time always valid
        assert "schema_org" in result["verification_sources"]

    def test_verification_sources_list(self):
        manifest = {"must_map": [], "can_ignore": []}
        result = verify_skeleton_properties("key,,,\n", manifest, data_context={})
        assert "schema_org" in result["verification_sources"]
