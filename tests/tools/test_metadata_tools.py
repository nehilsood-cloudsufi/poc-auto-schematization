"""Unit tests for metadata_tools.py — deterministic config generation."""

import csv
import io
import os
import pytest
from pathlib import Path

from src.tools.metadata_tools import (
    extract_output_columns,
    count_mapped_rows,
    count_mapped_columns,
    detect_multi_value_properties,
    detect_header_rows,
    merge_with_existing,
    write_config_csv,
    generate_processor_config,
    VALID_SVOBS_PROPERTIES,
)


# ============================================================================
# Test Data
# ============================================================================

SIMPLE_PVMAP = """\
key,property,value,prop2,val2,prop3,val3
State,observationAbout,{Data},,,
Year,observationDate,{Data},,,
Population,value,{Number},populationType,Person,measuredProperty,count
"""

PVMAP_WITH_UNIT = """\
key,property,value,prop2,val2
Rate,value,{Number},unit,Percent
State,observationAbout,{Data},,
Year,observationDate,{Data},,
"""

PVMAP_WITH_SCALING_AND_PERIOD = """\
key,property,value,prop2,val2,prop3,val3
Year,observationDate,{Data},,,,
State,observationAbout,{Data},,,,
Count,value,{Number},scalingFactor,1000,observationPeriod,P1Y
"""

PASSTHROUGH_PVMAP = """\
key,property,value
observationAbout,observationAbout,{Data}
observationDate,observationDate,{Data}
variableMeasured,variableMeasured,{Data}
value,value,{Number}
"""

PVMAP_STATVAR_ONLY = """\
key,property,value,prop2,val2
Gender,gender,{Data},populationType,Person
AgeGroup,age,{Data},measuredProperty,count
"""


# ============================================================================
# TestExtractOutputColumns
# ============================================================================

class TestExtractOutputColumns:
    def test_simple_pvmap(self):
        """observationAbout + observationDate + value → standard columns."""
        result = extract_output_columns(SIMPLE_PVMAP)
        cols = result.split(",")
        assert "observationAbout" in cols
        assert "observationDate" in cols
        assert "value" in cols
        # populationType/measuredProperty are StatVar props, NOT in output
        assert "populationType" not in cols
        assert "measuredProperty" not in cols

    def test_pvmap_with_unit(self):
        """PVMAP with unit property → output_columns includes unit."""
        result = extract_output_columns(PVMAP_WITH_UNIT)
        cols = result.split(",")
        assert "unit" in cols
        assert "value" in cols

    def test_pvmap_with_scaling_and_period(self):
        """scalingFactor + observationPeriod → both in output_columns."""
        result = extract_output_columns(PVMAP_WITH_SCALING_AND_PERIOD)
        cols = result.split(",")
        assert "scalingFactor" in cols
        assert "observationPeriod" in cols

    def test_excludes_statvar_properties(self):
        """populationType, measuredProperty, gender, age → NOT in output_columns."""
        result = extract_output_columns(PVMAP_STATVAR_ONLY)
        cols = result.split(",")
        assert "populationType" not in cols
        assert "measuredProperty" not in cols
        assert "gender" not in cols
        assert "age" not in cols

    def test_passthrough_pvmap(self):
        """observationAbout,{Data} style → standard 4 columns."""
        result = extract_output_columns(PASSTHROUGH_PVMAP)
        cols = result.split(",")
        assert "observationAbout" in cols
        assert "observationDate" in cols
        assert "variableMeasured" in cols
        assert "value" in cols

    def test_empty_pvmap_returns_defaults(self):
        """Empty PVMAP → 4 required columns as default."""
        result = extract_output_columns("")
        cols = result.split(",")
        assert len(cols) == 4
        assert cols[0] == "observationAbout"

    def test_ordering(self):
        """Output columns follow canonical order."""
        result = extract_output_columns(PVMAP_WITH_SCALING_AND_PERIOD)
        cols = result.split(",")
        # observationDate should come before value
        assert cols.index("observationDate") < cols.index("value")
        # value should come before scalingFactor
        assert cols.index("value") < cols.index("scalingFactor")

    def test_required_columns_always_present(self):
        """4 required columns present even when PVMAP has none of them."""
        pvmap_no_svobs = "key,p,v\nFoo,gender,Male\nBar,age,25\n"
        result = extract_output_columns(pvmap_no_svobs)
        cols = result.split(",")
        assert "observationAbout" in cols
        assert "observationDate" in cols
        assert "variableMeasured" in cols
        assert "value" in cols

    def test_required_columns_present_with_empty_pvmap(self):
        """Empty PVMAP still returns all 4 required columns."""
        result = extract_output_columns("")
        cols = result.split(",")
        assert "variableMeasured" in cols

    def test_optional_unit_added_when_in_pvmap(self):
        """unit added only when PVMAP contains it."""
        result = extract_output_columns(PVMAP_WITH_UNIT)
        cols = result.split(",")
        assert "unit" in cols

    def test_optional_not_added_when_absent(self):
        """measurementMethod NOT in output when PVMAP doesn't use it."""
        result = extract_output_columns(SIMPLE_PVMAP)
        cols = result.split(",")
        assert "measurementMethod" not in cols


# ============================================================================
# TestCountMappedRows
# ============================================================================

class TestCountMappedRows:
    def test_counts_data_rows(self):
        """PVMAP with header + 3 data rows → mapped_rows=3."""
        assert count_mapped_rows(SIMPLE_PVMAP) == 3

    def test_skips_header(self):
        """Row starting with 'key' is excluded."""
        pvmap = "key,property,value\nFoo,bar,baz\n"
        assert count_mapped_rows(pvmap) == 1

    def test_empty_pvmap(self):
        """Empty content → 0."""
        assert count_mapped_rows("") == 0

    def test_header_only(self):
        """Header-only PVMAP → 0."""
        assert count_mapped_rows("key,property,value\n") == 0

    def test_passthrough_pvmap(self):
        """Passthrough has 4 data rows."""
        assert count_mapped_rows(PASSTHROUGH_PVMAP) == 4


# ============================================================================
# TestCountMappedColumns
# ============================================================================

class TestCountMappedColumns:
    def test_max_pairs(self):
        """Row with 3 prop-value pairs → mapped_columns=3."""
        assert count_mapped_columns(SIMPLE_PVMAP) == 3

    def test_passthrough(self):
        """Passthrough rows have 1 pair each."""
        assert count_mapped_columns(PASSTHROUGH_PVMAP) == 1

    def test_empty(self):
        """Empty → 0."""
        assert count_mapped_columns("") == 0

    def test_uneven_rows(self):
        """Returns max across all rows."""
        pvmap = "key,p1,v1\nA,observationAbout,{Data}\nB,value,{Number},unit,Percent\n"
        assert count_mapped_columns(pvmap) == 2


# ============================================================================
# TestDetectMultiValueProperties
# ============================================================================

class TestDetectMultiValueProperties:
    def test_no_multi_value(self):
        """Each property used by unique keys → empty list."""
        pvmap = "key,p,v\nA,observationAbout,x\nB,observationDate,y\n"
        result = detect_multi_value_properties(pvmap)
        assert result == []

    def test_multi_value_detected(self):
        """Same property 'value' in rows for different keys."""
        pvmap = "key,p,v\nPopulation,value,{Number}\nRate,value,{Number}\n"
        result = detect_multi_value_properties(pvmap)
        assert "value" in result

    def test_excludes_defaults(self):
        """Default multi-value properties (name, alternateName) are excluded."""
        pvmap = "key,p,v\nA,name,foo\nB,name,bar\n"
        result = detect_multi_value_properties(pvmap)
        # name is a default, should not appear
        assert "name" not in result


# ============================================================================
# TestDetectHeaderRows
# ============================================================================

class TestDetectHeaderRows:
    def test_from_data_context(self):
        """data_context has header_rows → use it."""
        result = detect_header_rows(data_context={"header_rows": 3})
        assert result == 3

    def test_default_is_1(self):
        """No context, no file → default 1."""
        result = detect_header_rows()
        assert result == 1

    def test_standard_csv(self, tmp_path):
        """1 text header + numeric data → 1."""
        csv_file = tmp_path / "test.csv"
        csv_file.write_text("Name,Value,Year\nAlice,100,2020\nBob,200,2021\n")
        result = detect_header_rows(input_file=str(csv_file))
        assert result == 1

    def test_minimum_is_1(self):
        """header_rows from context < 1 → clamp to 1."""
        result = detect_header_rows(data_context={"header_rows": 0})
        assert result == 1

    def test_nonexistent_file(self):
        """Nonexistent file → default 1."""
        result = detect_header_rows(input_file="/nonexistent/file.csv")
        assert result == 1


# ============================================================================
# TestMergeWithExisting
# ============================================================================

class TestMergeWithExisting:
    def test_user_overrides_auto(self, tmp_path):
        """User header_rows=3, auto=1 → result=3."""
        meta = tmp_path / "metadata.csv"
        meta.write_text("header_rows,3\n")
        auto = {"header_rows": 1, "output_columns": "a,b,c"}
        result = merge_with_existing(auto, str(meta))
        assert result["header_rows"] == "3"  # String from CSV read

    def test_auto_fills_gaps(self, tmp_path):
        """User has header_rows only, auto adds output_columns."""
        meta = tmp_path / "metadata.csv"
        meta.write_text("header_rows,2\n")
        auto = {"header_rows": 1, "output_columns": "a,b,c"}
        result = merge_with_existing(auto, str(meta))
        assert result["output_columns"] == "a,b,c"
        assert result["header_rows"] == "2"

    def test_no_existing(self):
        """No existing file → returns auto as-is."""
        auto = {"header_rows": 1}
        result = merge_with_existing(auto, None)
        assert result == auto

    def test_nonexistent_file(self):
        """Nonexistent path → returns auto."""
        auto = {"header_rows": 1}
        result = merge_with_existing(auto, "/nonexistent/file.csv")
        assert result == auto


# ============================================================================
# TestWriteConfigCsv
# ============================================================================

class TestWriteConfigCsv:
    def test_writes_csv(self, tmp_path):
        """Writes 2-column CSV."""
        path = str(tmp_path / "config.csv")
        result_path = write_config_csv({"header_rows": 1, "output_columns": "a,b"}, path)
        assert Path(result_path).exists()
        content = Path(result_path).read_text()
        assert "header_rows" in content

    def test_creates_parent_dirs(self, tmp_path):
        """Creates parent directories if needed."""
        path = str(tmp_path / "sub" / "dir" / "config.csv")
        write_config_csv({"key": "val"}, path)
        assert Path(path).exists()


# ============================================================================
# TestGenerateProcessorConfig
# ============================================================================

class TestGenerateProcessorConfig:
    def test_end_to_end(self, tmp_path):
        """PVMAP + data_context → valid config CSV on disk."""
        result = generate_processor_config(
            pvmap_csv_content=SIMPLE_PVMAP,
            data_context={"header_rows": 1},
            output_dir=str(tmp_path),
        )
        assert result["success"] is True
        assert result["config_path"] is not None
        assert Path(result["config_path"]).exists()

        params = result["parameters"]
        assert "output_columns" in params
        assert "mapped_rows" in params
        assert params["mapped_rows"] == 3

    def test_writes_to_output_dir(self, tmp_path):
        """File at output/{dataset}/output_metadata.csv."""
        result = generate_processor_config(
            pvmap_csv_content=SIMPLE_PVMAP,
            output_dir=str(tmp_path),
        )
        assert result["config_path"].endswith("output_metadata.csv")

    def test_empty_pvmap(self):
        """Empty PVMAP → graceful error."""
        result = generate_processor_config(pvmap_csv_content="")
        assert result["success"] is False
        assert "Empty" in result["error"]

    def test_no_output_dir(self):
        """No output_dir → config_path is None but params generated."""
        result = generate_processor_config(pvmap_csv_content=SIMPLE_PVMAP)
        assert result["success"] is True
        assert result["config_path"] is None
        assert result["parameters"]["mapped_rows"] == 3

    def test_llm_enrichment_merged(self, tmp_path):
        """LLM enrichment params merge into config."""
        result = generate_processor_config(
            pvmap_csv_content=SIMPLE_PVMAP,
            output_dir=str(tmp_path),
            llm_enrichment={"schemaless": True, "description": "Test dataset"},
        )
        assert result["success"] is True
        assert result["parameters"]["schemaless"] is True
        assert result["parameters"]["description"] == "Test dataset"

    def test_existing_metadata_overrides(self, tmp_path):
        """Existing metadata values override auto-generated ones."""
        meta = tmp_path / "existing.csv"
        meta.write_text("header_rows,5\nmapped_rows,99\n")
        result = generate_processor_config(
            pvmap_csv_content=SIMPLE_PVMAP,
            output_dir=str(tmp_path),
            existing_metadata_path=str(meta),
        )
        assert result["success"] is True
        # Existing values win
        assert result["parameters"]["header_rows"] == "5"
        assert result["parameters"]["mapped_rows"] == "99"

    def test_passthrough_pvmap(self, tmp_path):
        """Passthrough PVMAP generates correct params."""
        result = generate_processor_config(
            pvmap_csv_content=PASSTHROUGH_PVMAP,
            output_dir=str(tmp_path),
        )
        assert result["success"] is True
        cols = result["parameters"]["output_columns"].split(",")
        assert "observationAbout" in cols
        assert "variableMeasured" in cols
        assert result["parameters"]["mapped_rows"] == 4
        assert result["parameters"]["mapped_columns"] == 1
