"""Tests for plan_to_skeleton_csv."""
from __future__ import annotations

import csv
import io

import pytest

from src.api.models.plan import (
    CandidateSource,
    ColumnMapping,
    ColumnRole,
    DatasetUnderstanding,
    MappingPlan,
    PropertyValueCandidate,
    StaticProperty,
)
from src.pipeline.plan.skeleton_converter import plan_to_skeleton_csv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _candidate(
    prop: str,
    value_expr: str,
    confidence: float = 0.9,
    source: CandidateSource = CandidateSource.LLM,
    reason: str = "test",
) -> PropertyValueCandidate:
    return PropertyValueCandidate(
        property=prop,
        value_expression=value_expr,
        confidence=confidence,
        source=source,
        reason=reason,
    )


def _col(
    name: str,
    role: ColumnRole,
    candidates: list[PropertyValueCandidate],
    selected_index: int = 0,
) -> ColumnMapping:
    return ColumnMapping(
        column_name=name,
        role=role,
        candidates=candidates,
        selected_index=selected_index,
        evidence="test evidence",
    )


def _static(
    prop_name: str,
    candidates: list[PropertyValueCandidate],
    selected_index: int = 0,
) -> StaticProperty:
    return StaticProperty(
        property_name=prop_name,
        candidates=candidates,
        selected_index=selected_index,
    )


def _understanding() -> DatasetUnderstanding:
    return DatasetUnderstanding(
        archetype="flat-wide",
        observation_grain="one row per observation",
        key_insight="simple dataset",
    )


def _make_plan(
    active_columns: list[ColumnMapping] | None = None,
    static_properties: list[StaticProperty] | None = None,
) -> MappingPlan:
    return MappingPlan(
        dataset_name="test_dataset",
        understanding=_understanding(),
        active_columns=active_columns or [],
        ignored_columns=[],
        static_properties=static_properties or [],
        global_notes=[],
    )


def _parse_csv(csv_string: str) -> list[list[str]]:
    """Parse CSV string into list of rows."""
    reader = csv.reader(io.StringIO(csv_string))
    return list(reader)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBasicConversion:
    """test_basic_conversion: verify output has header + correct number of rows."""

    def test_header_plus_column_rows_and_static_row(self):
        plan = _make_plan(
            active_columns=[
                _col("REF_AREA:Reference area", ColumnRole.OBSERVATION_ABOUT,
                     [_candidate("observationAbout", "country/[DATA]")]),
                _col("TIME_PERIOD:Time period", ColumnRole.OBSERVATION_DATE,
                     [_candidate("observationDate", "[DATA]")]),
                _col("OBS_VALUE:Observation Value", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
            ],
            static_properties=[
                _static("populationType",
                         [_candidate("populationType", "InterestRate")]),
                _static("statType",
                         [_candidate("statType", "measuredValue")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        # header + 3 columns + 1 static row = 5
        assert len(rows) == 5
        assert rows[0][0] == "key"

    def test_no_static_properties_omits_static_row(self):
        plan = _make_plan(
            active_columns=[
                _col("COL_A", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        # header + 1 column, no static row
        assert len(rows) == 2


class TestColumnRowsHaveCorrectKeys:
    """test_column_rows_have_correct_keys: verify exact column names."""

    def test_keys_match_column_names(self):
        plan = _make_plan(
            active_columns=[
                _col("REF_AREA:Reference area", ColumnRole.OBSERVATION_ABOUT,
                     [_candidate("observationAbout", "[DATA]")]),
                _col("TIME_PERIOD:Time period", ColumnRole.OBSERVATION_DATE,
                     [_candidate("observationDate", "[DATA]")]),
                _col("OBS_VALUE:Observation Value", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
                _col("FREQ:Frequency", ColumnRole.DIMENSION,
                     [_candidate("observationPeriod", "[DATA]")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        keys = [row[0] for row in rows[1:]]  # skip header
        assert keys == [
            "REF_AREA:Reference area",
            "TIME_PERIOD:Time period",
            "OBS_VALUE:Observation Value",
            "FREQ:Frequency",
        ]

    def test_static_row_has_empty_key(self):
        plan = _make_plan(
            active_columns=[
                _col("COL_A", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
            ],
            static_properties=[
                _static("unit", [_candidate("unit", "dcid:Percent")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        # Last data row is the static properties row
        static_row = rows[-1]
        assert static_row[0] == ""


class TestSelectedCandidateUsed:
    """test_selected_candidate_used: default selected_index=0 uses first candidate."""

    def test_default_uses_first_candidate(self):
        plan = _make_plan(
            active_columns=[
                _col(
                    "REF_AREA:Reference area",
                    ColumnRole.OBSERVATION_ABOUT,
                    candidates=[
                        _candidate("observationAbout", "country/[DATA]"),
                        _candidate("observationAbout", "wikidataId/[DATA]"),
                    ],
                    selected_index=0,
                ),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        col_row = rows[1]
        assert col_row[1] == "observationAbout"
        assert col_row[2] == "country/{Data}"


class TestAlternateSelection:
    """test_alternate_selection: selected_index=1 uses second candidate."""

    def test_second_candidate_selected(self):
        plan = _make_plan(
            active_columns=[
                _col(
                    "REF_AREA:Reference area",
                    ColumnRole.OBSERVATION_ABOUT,
                    candidates=[
                        _candidate("observationAbout", "country/[DATA]"),
                        _candidate("observationAbout", "wikidataId/[DATA]"),
                    ],
                    selected_index=1,
                ),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        col_row = rows[1]
        assert col_row[1] == "observationAbout"
        assert col_row[2] == "wikidataId/{Data}"


class TestStaticPropertiesInOutput:
    """test_static_properties_in_output: verify populationType, statType, unit present."""

    def test_all_static_properties_present(self):
        plan = _make_plan(
            active_columns=[
                _col("OBS_VALUE", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
            ],
            static_properties=[
                _static("populationType",
                         [_candidate("populationType", "InterestRate")]),
                _static("statType",
                         [_candidate("statType", "measuredValue")]),
                _static("unit",
                         [_candidate("unit", "dcid:Percent")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        # Static properties row is the last row
        static_row = rows[-1]
        assert static_row[0] == ""

        # Flatten the pairs: [prop1, val1, prop2, val2, ...]
        pairs = static_row[1:]
        # Remove trailing empty cells
        while pairs and pairs[-1] == "":
            pairs.pop()

        assert "populationType" in pairs
        assert "InterestRate" in pairs
        assert "statType" in pairs
        assert "measuredValue" in pairs
        assert "unit" in pairs
        assert "dcid:Percent" in pairs

    def test_static_properties_as_pairs(self):
        plan = _make_plan(
            active_columns=[
                _col("COL_A", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
            ],
            static_properties=[
                _static("populationType",
                         [_candidate("populationType", "Person")]),
                _static("unit",
                         [_candidate("unit", "dcid:Percent")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        static_row = rows[-1]
        # key is empty, then property-value pairs
        assert static_row[0] == ""
        assert static_row[1] == "populationType"
        assert static_row[2] == "Person"
        assert static_row[3] == "unit"
        assert static_row[4] == "dcid:Percent"


class TestPlaceholdersConverted:
    """test_placeholders_converted: verify [DATA]->{Data}, [NUMBER]->{Number}."""

    def test_data_placeholder(self):
        plan = _make_plan(
            active_columns=[
                _col("TIME_PERIOD", ColumnRole.OBSERVATION_DATE,
                     [_candidate("observationDate", "[DATA]")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)
        assert rows[1][2] == "{Data}"

    def test_number_placeholder(self):
        plan = _make_plan(
            active_columns=[
                _col("OBS_VALUE", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)
        assert rows[1][2] == "{Number}"

    def test_compound_expression(self):
        plan = _make_plan(
            active_columns=[
                _col("REF_AREA", ColumnRole.OBSERVATION_ABOUT,
                     [_candidate("observationAbout", "country/[DATA]")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)
        assert rows[1][2] == "country/{Data}"

    def test_no_placeholder_untouched(self):
        plan = _make_plan(
            static_properties=[
                _static("unit",
                         [_candidate("unit", "dcid:Percent")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)
        static_row = rows[-1]
        assert "dcid:Percent" in static_row


class TestEmptyPlan:
    """test_empty_plan: verify empty plan produces just header."""

    def test_empty_plan_header_only(self):
        plan = _make_plan()
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        assert len(rows) == 1
        assert rows[0][0] == "key"

    def test_empty_plan_valid_csv(self):
        plan = _make_plan()
        csv_str = plan_to_skeleton_csv(plan)
        # Should be parseable and non-empty
        assert csv_str.strip() != ""


class TestFullEndToEnd:
    """Mimics the BIS PVMAP example from the task description."""

    def test_bis_like_plan(self):
        plan = _make_plan(
            active_columns=[
                _col("REF_AREA:Reference area", ColumnRole.OBSERVATION_ABOUT,
                     [_candidate("observationAbout", "country/[DATA]")]),
                _col("TIME_PERIOD:Time period", ColumnRole.OBSERVATION_DATE,
                     [_candidate("observationDate", "[DATA]")]),
                _col("OBS_VALUE:Observation Value", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
                _col("FREQ:Frequency", ColumnRole.DIMENSION,
                     [_candidate("observationPeriod", "[DATA]")]),
            ],
            static_properties=[
                _static("populationType",
                         [_candidate("populationType", "InterestRate")]),
                _static("statType",
                         [_candidate("statType", "measuredValue")]),
                _static("unit",
                         [_candidate("unit", "dcid:Percent")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        # 1 header + 4 columns + 1 static = 6 rows
        assert len(rows) == 6

        # Header
        assert rows[0][0] == "key"

        # Column rows in order
        assert rows[1][0] == "REF_AREA:Reference area"
        assert rows[1][1] == "observationAbout"
        assert rows[1][2] == "country/{Data}"

        assert rows[2][0] == "TIME_PERIOD:Time period"
        assert rows[2][1] == "observationDate"
        assert rows[2][2] == "{Data}"

        assert rows[3][0] == "OBS_VALUE:Observation Value"
        assert rows[3][1] == "value"
        assert rows[3][2] == "{Number}"

        assert rows[4][0] == "FREQ:Frequency"
        assert rows[4][1] == "observationPeriod"
        assert rows[4][2] == "{Data}"

        # Static row
        assert rows[5][0] == ""
        assert rows[5][1] == "populationType"
        assert rows[5][2] == "InterestRate"
        assert rows[5][3] == "statType"
        assert rows[5][4] == "measuredValue"
        assert rows[5][5] == "unit"
        assert rows[5][6] == "dcid:Percent"

    def test_all_rows_same_width(self):
        """All rows should be padded to the same width for valid CSV."""
        plan = _make_plan(
            active_columns=[
                _col("COL_A", ColumnRole.MEASURE,
                     [_candidate("value", "[NUMBER]")]),
            ],
            static_properties=[
                _static("populationType",
                         [_candidate("populationType", "Person")]),
                _static("statType",
                         [_candidate("statType", "measuredValue")]),
                _static("unit",
                         [_candidate("unit", "dcid:Percent")]),
            ],
        )
        csv_str = plan_to_skeleton_csv(plan)
        rows = _parse_csv(csv_str)

        widths = {len(row) for row in rows}
        assert len(widths) == 1, f"Not all rows have the same width: {widths}"
