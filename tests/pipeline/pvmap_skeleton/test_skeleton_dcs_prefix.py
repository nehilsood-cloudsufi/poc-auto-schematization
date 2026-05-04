"""Tests for dcs: prefix emission in skeleton generator value columns."""

import csv
import io
import pytest

from src.pipeline.pvmap_skeleton.skeleton_generator import generate_pvmap_skeleton


def _make_manifest(population_type="Person", measurement_type="Count", extra_value_kwargs=None):
    """Helper to build a minimal manifest + data_context for value column tests."""
    value_entry = {
        "column_name": "Value",
        "role": "value",
        "suggested_property": "value",
        "cardinality": 100,
        "sample_values": ["123", "456"],
    }
    if extra_value_kwargs:
        value_entry.update(extra_value_kwargs)

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
    """Parse skeleton CSV and return list of row dicts keyed by column name."""
    reader = csv.reader(io.StringIO(skeleton_csv))
    return list(reader)


class TestDcsPrefix:
    """Task 6: Value columns should emit dcs: prefix on populationType and measuredProperty."""

    def test_population_type_has_dcs_prefix(self):
        manifest, ctx = _make_manifest(population_type="Person", measurement_type="Count")
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        assert len(value_rows) == 1
        row = value_rows[0]
        # Find populationType value
        for i in range(1, len(row), 2):
            if row[i] == "populationType":
                assert row[i + 1] == "dcs:Person", f"Expected dcs:Person, got {row[i + 1]}"
                break
        else:
            pytest.fail("populationType not found in value row")

    def test_measured_property_has_dcs_prefix(self):
        manifest, ctx = _make_manifest(population_type="Person", measurement_type="Count")
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        row = value_rows[0]
        for i in range(1, len(row), 2):
            if row[i] == "measuredProperty":
                assert row[i + 1] == "dcs:count", f"Expected dcs:count, got {row[i + 1]}"
                break
        else:
            pytest.fail("measuredProperty not found in value row")

    def test_no_double_dcs_prefix(self):
        """Ensure we don't get dcs:dcs:Person."""
        manifest, ctx = _make_manifest(population_type="Person")
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        assert "dcs:dcs:" not in skeleton

    def test_todo_when_no_population_type(self):
        manifest, ctx = _make_manifest(population_type="", measurement_type="Count")
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        row = value_rows[0]
        for i in range(1, len(row), 2):
            if row[i] == "populationType":
                assert row[i + 1] == "TODO"
                break

    def test_todo_when_no_measurement_type(self):
        manifest, ctx = _make_manifest(population_type="Person", measurement_type="")
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        row = value_rows[0]
        for i in range(1, len(row), 2):
            if row[i] == "measuredProperty":
                assert row[i + 1] == "TODO"
                break

    def test_percent_measurement_gets_dcs_prefix(self):
        manifest, ctx = _make_manifest(population_type="Person", measurement_type="Percent")
        skeleton = generate_pvmap_skeleton(manifest, ctx)
        rows = _parse_skeleton_rows(skeleton)
        value_rows = [r for r in rows[1:] if r[0] == "Value"]
        row = value_rows[0]
        for i in range(1, len(row), 2):
            if row[i] == "measuredProperty":
                assert row[i + 1] == "dcs:percent"
                break
