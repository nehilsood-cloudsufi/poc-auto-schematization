"""Tests for named capture pre-population in skeleton generator (sentinel columns)."""

import csv
import io
import pytest

from src.pipeline.pvmap_skeleton.skeleton_generator import generate_pvmap_skeleton


def _make_manifest(sentinel_values=None, population_type="Person", measurement_type="Count"):
    """Helper to build manifest + data_context with optional sentinel values."""
    value_entry = {
        "column_name": "Value",
        "role": "value",
        "suggested_property": "value",
        "cardinality": 100,
        "sample_values": ["123", "456"],
    }
    if sentinel_values is not None:
        value_entry["sentinel_values"] = sentinel_values

    manifest = {
        "must_map": [
            {"column_name": "Country", "role": "place", "suggested_property": "observationAbout"},
            {"column_name": "Year", "role": "time", "suggested_property": "observationDate"},
            value_entry,
        ],
        "can_ignore": [],
        "all_columns": ["Country", "Year", "Value"],
    }
    data_context = {
        "geography": {"format": "ISO_2"},
        "time": {"format": "YYYY"},
        "population_type": population_type,
        "measurement_type": measurement_type,
    }
    return manifest, data_context


def _parse_skeleton_rows(skeleton_csv):
    reader = csv.reader(io.StringIO(skeleton_csv))
    return list(reader)


class TestNamedCapture:
    """Task 8: Value columns with sentinel values should use named captures."""

    def test_value_column_with_sentinels_uses_named_capture(self):
        manifest, ctx = _make_manifest(sentinel_values=["NA", "N/A"])
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        assert len(value_rows) == 1
        row = value_rows[0]
        assert row[1] == "Value_Attr", f"Expected named capture 'Value_Attr', got '{row[1]}'"
        assert row[2] == "{Number}"

    def test_value_column_without_sentinels_uses_direct(self):
        manifest, ctx = _make_manifest(sentinel_values=None)
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        assert len(value_rows) == 1
        row = value_rows[0]
        assert row[1] == "value"
        assert row[2] == "{Number}"

    def test_empty_sentinels_uses_direct(self):
        """Empty sentinel list should behave like no sentinels."""
        manifest, ctx = _make_manifest(sentinel_values=[])
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        row = value_rows[0]
        assert row[1] == "value"

    def test_named_capture_with_spaces_in_column_name(self):
        """Spaces in column names should be replaced with underscores."""
        value_entry = {
            "column_name": "Obs Value",
            "role": "value",
            "suggested_property": "value",
            "cardinality": 100,
            "sample_values": ["123"],
            "sentinel_values": [".."],
        }
        manifest = {
            "must_map": [
                {"column_name": "Country", "role": "place", "suggested_property": "observationAbout"},
                {"column_name": "Year", "role": "time", "suggested_property": "observationDate"},
                value_entry,
            ],
            "can_ignore": [],
            "all_columns": ["Country", "Year", "Obs Value"],
        }
        data_context = {
            "geography": {"format": "ISO_2"},
            "time": {"format": "YYYY"},
            "population_type": "Person",
            "measurement_type": "Count",
        }
        skeleton = generate_pvmap_skeleton(manifest, data_context)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Obs Value"]
        assert len(value_rows) == 1
        assert value_rows[0][1] == "Obs_Value_Attr"

    def test_named_capture_still_has_dcs_prefix(self):
        """Named capture rows should still get dcs: prefixed populationType/measuredProperty."""
        manifest, ctx = _make_manifest(sentinel_values=["NA"], population_type="Person", measurement_type="Count")
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        row = value_rows[0]
        # Should have named capture AND dcs: prefix
        assert row[1] == "Value_Attr"
        for i in range(1, len(row), 2):
            if row[i] == "populationType":
                assert row[i + 1] == "dcs:Person"
                break


class TestVerifierNamedCapture:
    """Skeleton verifier should recognize named captures as valid."""

    def test_named_capture_recognized_as_valid(self):
        from src.pipeline.pvmap_skeleton.skeleton_verifier import _verify_via_schemaorg

        column_properties = {
            "Value": {
                "property": "Value_Attr",
                "role": "dimension",  # verifier sees non-place/time/value roles
                "key": "Value",
                "property_verified": False,
                "verification_source": "unverified",
                "alternatives": [],
                "confidence": "low",
            }
        }
        result = {"columns": {}, "place_verified": False}
        _verify_via_schemaorg(column_properties, result)

        assert result["columns"]["Value"]["property_verified"] is True
        assert result["columns"]["Value"]["verification_source"] == "named_capture"
