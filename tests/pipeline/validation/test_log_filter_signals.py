"""Tests for enriched counter signal extraction in log_filter.py."""
import csv
import io
import tempfile
from pathlib import Path

import pytest

from src.pipeline.validation.log_filter import filter_counters, FilteredLogs


def _write_counters(tmp_path: Path, rows: list[tuple[str, int]]) -> Path:
    """Write a counters CSV file and return its path."""
    p = tmp_path / "processed_counters.txt"
    buf = io.StringIO()
    writer = csv.writer(buf)
    for key, val in rows:
        writer.writerow([key, val])
    p.write_text(buf.getvalue())
    return p


class TestPropertyCardinalityParsing:
    """filter_counters should populate property_cardinality from output-svobs-unique-* counters."""

    def test_parses_output_svobs_unique_counters(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("output-svobs-csv-rows", 80),
            ("output-svobs-unique-observationAbout", 5),
            ("output-svobs-unique-observationDate", 10),
            ("output-svobs-unique-variableMeasured", 20),
            ("output-svobs-unique-value", 75),
        ])
        result = filter_counters(counters)
        assert result.property_cardinality == {
            "observationAbout": 5,
            "observationDate": 10,
            "variableMeasured": 20,
            "value": 75,
        }

    def test_empty_counters_gives_empty_cardinality(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 50),
        ])
        result = filter_counters(counters)
        assert result.property_cardinality == {}


class TestDroppedStatvarParsing:
    """filter_counters should populate dropped_statvars from dropped-invalid-statvars_* counters."""

    def test_parses_dropped_invalid_statvars(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("dropped-invalid-statvars", 3),
            ("dropped-invalid-statvars_Count_Person_Male", 1),
            ("dropped-invalid-statvars_Count_Person_Female", 1),
            ("dropped-invalid-statvars_Count_Person_Total", 1),
        ])
        result = filter_counters(counters)
        assert set(result.dropped_statvars) == {
            "Count_Person_Male",
            "Count_Person_Female",
            "Count_Person_Total",
        }

    def test_parses_dropped_statvars_without_svobs(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("dropped-statvars-without-svobs", 2),
            ("dropped-statvars-without-svobs_Count_Empty", 1),
            ("dropped-statvars-without-svobs_Count_Other", 1),
        ])
        result = filter_counters(counters)
        assert "Count_Empty" in result.dropped_statvars
        assert "Count_Other" in result.dropped_statvars


class TestPerStatvarObsCounts:
    """filter_counters should populate statvars_with_obs from generated-svobs_* counters."""

    def test_parses_generated_svobs_per_statvar(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("generated-svobs", 50),
            ("generated-svobs_Count_Person_Male", 25),
            ("generated-svobs_Count_Person_Female", 25),
        ])
        result = filter_counters(counters)
        assert ("Count_Person_Male", 25) in result.statvars_with_obs
        assert ("Count_Person_Female", 25) in result.statvars_with_obs


class TestCollisionTupleParsing:
    """filter_counters should parse error-mismatched-svobs detail counters."""

    def test_parses_mismatched_svobs_details(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("error-mismatched-svobs", 10),
            ("error-mismatched-svobs_Count_Person", 5),
            ("error-mismatched-svobs_Count_Household", 5),
        ])
        result = filter_counters(counters)
        assert "error-mismatched-svobs" in result.error_examples
        examples = result.error_examples["error-mismatched-svobs"]
        values = [v for v, _ in examples]
        assert "Count_Person" in values


class TestDroppedObservationParsing:
    """filter_counters should parse dropped-invalid-svobs detail counters."""

    def test_parses_dropped_svobs_with_tuple_details(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("dropped-invalid-svobs", 2),
            ("dropped-invalid-svobs_observationAbout=geoId/06;observationDate=2020;variableMeasured=dcid:Count_Person", 1),
            ("dropped-invalid-svobs_observationAbout=geoId/01;observationDate=2020;variableMeasured=dcid:Count_Person", 1),
        ])
        result = filter_counters(counters)
        assert "dropped-invalid-svobs" in result.error_examples
        examples = result.error_examples["dropped-invalid-svobs"]
        assert len(examples) == 2


class TestUniversalDebugMining:
    """filter_counters should mine debug examples for ALL error types, not just 7 hardcoded ones."""

    def test_mines_unknown_error_type_examples(self, tmp_path):
        counters = _write_counters(tmp_path, [
            ("input-rows-processed", 100),
            ("error-some-new-type", 5),
            ("error-some-new-type_BadValue", 3),
            ("error-some-new-type_OtherBad", 2),
        ])
        result = filter_counters(counters)
        assert "error-some-new-type" in result.error_examples
        examples = result.error_examples["error-some-new-type"]
        values = [v for v, _ in examples]
        assert "BadValue" in values
        assert "OtherBad" in values
