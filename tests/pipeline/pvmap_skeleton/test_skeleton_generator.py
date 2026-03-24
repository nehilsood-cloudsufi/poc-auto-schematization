"""Tests for PVMAP skeleton generation."""

import csv
import io
import pytest

from src.pipeline.pvmap_skeleton.skeleton_generator import (
    build_column_manifest,
    generate_pvmap_skeleton,
    format_completeness_report,
    MAX_DIMENSION_VALUES,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def basic_data_context():
    """A typical data_context with place, time, dimension, value, metadata."""
    return {
        "all_columns": ["State", "Year", "Gender", "Age", "Population", "Source"],
        "column_roles": {
            "State": "place",
            "Year": "time",
            "Gender": "dimension",
            "Age": "dimension",
            "Population": "value",
            "Source": "metadata",
        },
        "column_stats": {
            "State": {"cardinality": 50, "sample_values": ["CA", "NY", "TX"]},
            "Year": {"cardinality": 10, "sample_values": ["2020", "2021"]},
            "Gender": {"cardinality": 3, "sample_values": ["Male", "Female", "Total"]},
            "Age": {"cardinality": 5, "sample_values": ["0-4", "5-14", "15-24", "25-64", "65+"]},
            "Population": {"cardinality": 1000, "sample_values": ["12345", "67890"]},
            "Source": {"cardinality": 2, "sample_values": ["Census", "ACS"]},
        },
        "dimension_domains": {
            "Gender": ["Male", "Female", "Total"],
            "Age": ["0-4", "5-14", "15-24", "25-64", "65+"],
        },
        "geography": {"column": "State", "format": "FIPS_STATE", "sample_values": ["06", "36"]},
        "time": {"column": "Year", "format": "YYYY", "sample_values": ["2020", "2021"]},
        "value_columns": [{"name": "Population", "stat_type": "Count"}],
        "population_type": "Person",
        "measurement_type": "Count",
    }


@pytest.fixture
def iso_data_context():
    """Data context with ISO country codes."""
    return {
        "all_columns": ["REF_AREA", "TIME_PERIOD", "OBS_VALUE"],
        "column_roles": {
            "REF_AREA": "place",
            "TIME_PERIOD": "time",
            "OBS_VALUE": "value",
        },
        "column_stats": {
            "REF_AREA": {"cardinality": 30, "sample_values": ["US", "GB", "DE"]},
            "TIME_PERIOD": {"cardinality": 20, "sample_values": ["2020-01", "2020-02"]},
            "OBS_VALUE": {"cardinality": 500, "sample_values": ["1.5", "2.3"]},
        },
        "dimension_domains": {},
        "geography": {"column": "REF_AREA", "format": "ISO_2", "sample_values": ["US", "GB"]},
        "time": {"column": "TIME_PERIOD", "format": "YYYY-MM", "sample_values": ["2020-01"]},
        "value_columns": [{"name": "OBS_VALUE", "stat_type": "Rate"}],
        "population_type": "",
        "measurement_type": "Rate",
    }


# ---------------------------------------------------------------------------
# build_column_manifest tests
# ---------------------------------------------------------------------------

class TestBuildColumnManifest:

    def test_classifies_all_roles(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)

        must_map_names = {e["column_name"] for e in manifest["must_map"]}
        can_ignore_names = {e["column_name"] for e in manifest["can_ignore"]}

        assert must_map_names == {"State", "Year", "Gender", "Age", "Population"}
        assert can_ignore_names == {"Source"}
        assert manifest["all_columns"] == basic_data_context["all_columns"]

    def test_place_column_suggested_property(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        place_entry = next(e for e in manifest["must_map"] if e["role"] == "place")
        assert place_entry["suggested_property"] == "observationAbout"

    def test_time_column_suggested_property(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        time_entry = next(e for e in manifest["must_map"] if e["role"] == "time")
        assert time_entry["suggested_property"] == "observationDate"

    def test_value_column_suggested_property(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        value_entry = next(e for e in manifest["must_map"] if e["role"] == "value")
        assert value_entry["suggested_property"] == "value"

    def test_dimension_has_domain_values(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        gender = next(e for e in manifest["must_map"] if e["column_name"] == "Gender")
        assert gender["suggested_property"] == "dimension"
        assert gender["domain_values"] == ["Male", "Female", "Total"]
        assert gender["domain_truncated"] is False

    def test_dimension_truncation(self, basic_data_context):
        """Dimensions with >100 values should be truncated."""
        basic_data_context["dimension_domains"]["BigDim"] = [f"val_{i}" for i in range(150)]
        basic_data_context["all_columns"].append("BigDim")
        basic_data_context["column_roles"]["BigDim"] = "dimension"
        basic_data_context["column_stats"]["BigDim"] = {"cardinality": 150, "sample_values": []}

        manifest = build_column_manifest(basic_data_context)
        big_dim = next(e for e in manifest["must_map"] if e["column_name"] == "BigDim")
        assert len(big_dim["domain_values"]) == MAX_DIMENSION_VALUES
        assert big_dim["domain_truncated"] is True

    def test_empty_data_context(self):
        manifest = build_column_manifest({})
        assert manifest["must_map"] == []
        assert manifest["can_ignore"] == []
        assert manifest["all_columns"] == []

    def test_unknown_role_treated_as_must_map(self):
        ctx = {
            "all_columns": ["Mystery"],
            "column_roles": {"Mystery": "unknown_role"},
            "column_stats": {"Mystery": {"cardinality": 5, "sample_values": ["a"]}},
            "dimension_domains": {},
        }
        manifest = build_column_manifest(ctx)
        assert len(manifest["must_map"]) == 1
        assert manifest["must_map"][0]["column_name"] == "Mystery"

    def test_missing_role_treated_as_must_map(self):
        """Column not in column_roles at all should be must-map."""
        ctx = {
            "all_columns": ["Orphan"],
            "column_roles": {},
            "column_stats": {},
            "dimension_domains": {},
        }
        manifest = build_column_manifest(ctx)
        assert len(manifest["must_map"]) == 1


# ---------------------------------------------------------------------------
# generate_pvmap_skeleton tests
# ---------------------------------------------------------------------------

class TestGeneratePvmapSkeleton:

    def test_skeleton_valid_csv(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        skeleton = generate_pvmap_skeleton(manifest, basic_data_context)

        # Should be parseable CSV
        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        assert len(rows) > 1  # header + data rows
        assert rows[0][0] == "key"
        assert rows[0][1] == "prop"
        assert rows[0][2] == "val"

    def test_skeleton_place_fips(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        skeleton = generate_pvmap_skeleton(manifest, basic_data_context)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        place_row = next(r for r in rows if r[0] == "State")
        assert place_row[1] == "observationAbout"
        assert place_row[2] == "geoId/{Data}"

    def test_skeleton_place_iso(self, iso_data_context):
        manifest = build_column_manifest(iso_data_context)
        skeleton = generate_pvmap_skeleton(manifest, iso_data_context)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        place_row = next(r for r in rows if r[0] == "REF_AREA")
        assert place_row[1] == "observationAbout"
        assert place_row[2] == "country/{Data}"

    def test_skeleton_place_name(self):
        ctx = {
            "all_columns": ["City"],
            "column_roles": {"City": "place"},
            "column_stats": {"City": {"cardinality": 10, "sample_values": ["Boston"]}},
            "dimension_domains": {},
            "geography": {"column": "City", "format": "NAME"},
            "time": {},
        }
        manifest = build_column_manifest(ctx)
        skeleton = generate_pvmap_skeleton(manifest, ctx)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        place_row = next(r for r in rows if r[0] == "City")
        assert place_row[2] == "{Data}"

    def test_skeleton_time_yyyy(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        skeleton = generate_pvmap_skeleton(manifest, basic_data_context)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        time_row = next(r for r in rows if r[0] == "Year")
        assert time_row[1] == "observationDate"
        assert time_row[2] == "{Number}"

    def test_skeleton_time_formatted(self, iso_data_context):
        manifest = build_column_manifest(iso_data_context)
        skeleton = generate_pvmap_skeleton(manifest, iso_data_context)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        time_row = next(r for r in rows if r[0] == "TIME_PERIOD")
        assert time_row[1] == "observationDate"
        assert time_row[2] == "{Data}"

    def test_skeleton_value_column_with_population(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        skeleton = generate_pvmap_skeleton(manifest, basic_data_context)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        value_row = next(r for r in rows if r[0] == "Population")
        assert value_row[1] == "value"
        assert value_row[2] == "{Number}"
        # Should have populationType and measuredProperty
        assert "populationType" in value_row
        assert "Person" in value_row

    def test_skeleton_value_column_todo_when_no_population(self):
        ctx = {
            "all_columns": ["Amount"],
            "column_roles": {"Amount": "value"},
            "column_stats": {"Amount": {"cardinality": 100, "sample_values": ["100"]}},
            "dimension_domains": {},
            "geography": {},
            "time": {},
            "population_type": "",
            "measurement_type": "",
        }
        manifest = build_column_manifest(ctx)
        skeleton = generate_pvmap_skeleton(manifest, ctx)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        value_row = next(r for r in rows if r[0] == "Amount")
        assert "TODO" in value_row

    def test_skeleton_dimension_enumeration(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        skeleton = generate_pvmap_skeleton(manifest, basic_data_context)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        gender_rows = [r for r in rows if r[0].startswith("Gender:")]
        assert len(gender_rows) == 3  # Male, Female, Total
        assert any("Male" in r[0] for r in gender_rows)
        assert any("Female" in r[0] for r in gender_rows)
        assert any("Total" in r[0] for r in gender_rows)

    def test_skeleton_dimension_cardinality_cap(self, basic_data_context):
        """Dimensions with >100 values should be capped in skeleton."""
        big_domain = [f"val_{i}" for i in range(150)]
        basic_data_context["dimension_domains"]["BigDim"] = big_domain
        basic_data_context["all_columns"].append("BigDim")
        basic_data_context["column_roles"]["BigDim"] = "dimension"
        basic_data_context["column_stats"]["BigDim"] = {"cardinality": 150, "sample_values": []}

        manifest = build_column_manifest(basic_data_context)
        skeleton = generate_pvmap_skeleton(manifest, basic_data_context)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        big_dim_rows = [r for r in rows if r[0].startswith("BigDim:")]
        assert len(big_dim_rows) == MAX_DIMENSION_VALUES

    def test_skeleton_metadata_ignore(self, basic_data_context):
        manifest = build_column_manifest(basic_data_context)
        skeleton = generate_pvmap_skeleton(manifest, basic_data_context)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        source_row = next(r for r in rows if r[0] == "Source")
        assert source_row[1] == "#ignore"

    def test_skeleton_empty_manifest(self):
        manifest = {"must_map": [], "can_ignore": [], "all_columns": []}
        skeleton = generate_pvmap_skeleton(manifest, {})
        assert skeleton == ""

    def test_skeleton_dimension_no_domain(self):
        """Dimension with no known domain values gets a placeholder row."""
        ctx = {
            "all_columns": ["Category"],
            "column_roles": {"Category": "dimension"},
            "column_stats": {"Category": {"cardinality": 5, "sample_values": ["A", "B"]}},
            "dimension_domains": {},
            "geography": {},
            "time": {},
        }
        manifest = build_column_manifest(ctx)
        skeleton = generate_pvmap_skeleton(manifest, ctx)

        reader = csv.reader(io.StringIO(skeleton))
        rows = list(reader)
        cat_row = next(r for r in rows[1:] if r[0] == "Category")
        assert cat_row[1] == ""
        assert cat_row[2] == "{Data}"


# ---------------------------------------------------------------------------
# format_completeness_report tests
# ---------------------------------------------------------------------------

class TestFormatCompletenessReport:

    def test_ok_severity(self):
        result = format_completeness_report({
            "severity": "ok",
            "coverage_ratio": 1.0,
            "missing_must_map": [],
        })
        assert "All must-map columns are present" in result

    def test_critical_severity(self):
        result = format_completeness_report({
            "severity": "critical",
            "coverage_ratio": 0.6,
            "missing_must_map": [
                {"column": "State", "role": "place", "suggested_property": "observationAbout"},
            ],
        })
        assert "CRITICAL" in result
        assert "`State`" in result
        assert "PLACE" in result

    def test_warning_severity(self):
        result = format_completeness_report({
            "severity": "warning",
            "coverage_ratio": 0.8,
            "missing_must_map": [
                {"column": "Gender", "role": "dimension", "suggested_property": "dimension"},
            ],
        })
        assert "WARNING" in result
        assert "`Gender`" in result

    def test_empty_input(self):
        assert format_completeness_report({}) == ""
        assert format_completeness_report(None) == ""
