"""Tests for fix_missing_required_props using column_manifest."""
import pytest

from src.pipeline.validation.log_filter import FilteredLogs
from src.pipeline.validation.pvmap_corrector import apply_correction_rules


def _make_filtered_logs(**overrides) -> FilteredLogs:
    logs = FilteredLogs()
    for k, v in overrides.items():
        setattr(logs, k, v)
    return logs


class TestInjectMissingObservationAbout:
    def test_injects_place_row_from_manifest(self):
        pvmap = "Year,observationDate,{Data}\nPopulation,value,{Number}"
        logs = _make_filtered_logs(
            errors={"error-svobs-missing-property": 100},
            error_examples={"error-svobs-missing-property": [("observationAbout", 100)]},
        )
        manifest = {
            "must_map": [
                {"column_name": "State FIPS", "role": "place", "sample_values": ["01", "06"]},
            ],
            "can_ignore": [],
        }
        corrected, changes = apply_correction_rules(
            pvmap_csv=pvmap,
            filtered_logs=logs,
            key_match_report="",
            input_data_path=None,
            column_manifest=manifest,
        )
        assert "State FIPS" in corrected
        assert "observationAbout" in corrected
        assert any("fix_missing_required" in c for c in changes)


class TestInjectMissingObservationDate:
    def test_injects_date_row_from_manifest(self):
        pvmap = "State,observationAbout,dcid:geoId/{Data}\nPop,value,{Number}"
        logs = _make_filtered_logs(
            errors={"error-svobs-missing-property": 50},
            error_examples={"error-svobs-missing-property": [("observationDate", 50)]},
        )
        manifest = {
            "must_map": [
                {"column_name": "Year", "role": "time", "sample_values": ["2020", "2021"]},
            ],
            "can_ignore": [],
        }
        corrected, changes = apply_correction_rules(
            pvmap_csv=pvmap,
            filtered_logs=logs,
            key_match_report="",
            input_data_path=None,
            column_manifest=manifest,
        )
        assert "Year" in corrected
        assert "observationDate" in corrected


class TestNoManifestNoInjection:
    def test_no_manifest_no_change(self):
        pvmap = "Year,observationDate,{Data}"
        logs = _make_filtered_logs(
            errors={"error-svobs-missing-property": 10},
            error_examples={"error-svobs-missing-property": [("observationAbout", 10)]},
        )
        corrected, changes = apply_correction_rules(
            pvmap_csv=pvmap,
            filtered_logs=logs,
            key_match_report="",
            input_data_path=None,
            column_manifest=None,
        )
        # Without manifest, can't inject
        assert not any("fix_missing_required_from_manifest" in c for c in changes)
