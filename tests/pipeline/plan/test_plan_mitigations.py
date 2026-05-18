"""Tests for plan_mitigations — programmatic safeguards between plan approval and PVMAP generation."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pandas as pd
import pytest

from src.api.models.plan import (
    StatVarProperty,
    CandidateSource,
    ColumnMapping,
    ColumnRole,
    DatasetUnderstanding,
    EnrichedMappingPlan,
    PlaceResolution,
    PropertyValueCandidate,
    StatVarBlueprint,
    ValueDictionary,
    ValueMapping,
)
from src.pipeline.plan.plan_mitigations import (
    TOTAL_INDICATORS,
    apply_mitigations,
    check_column_alignment,
    normalize_place_formats,
    normalize_time_formats,
    strip_total_indicators,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_candidate(
    prop: str = "measuredProperty",
    value: str = "[DATA]",
    confidence: float = 0.9,
) -> PropertyValueCandidate:
    return PropertyValueCandidate(
        property=prop,
        value_expression=value,
        confidence=confidence,
        source=CandidateSource.LLM,
        reason="test",
    )


def _make_column(
    name: str,
    role: ColumnRole = ColumnRole.DIMENSION,
    prop: str = "measuredProperty",
) -> ColumnMapping:
    return ColumnMapping(
        column_name=name,
        role=role,
        candidates=[_make_candidate(prop=prop)],
        evidence="test evidence",
    )


def _make_plan(
    active_columns: list[ColumnMapping] | None = None,
    ignored_columns: list[ColumnMapping] | None = None,
    value_dictionaries: list[ValueDictionary] | None = None,
    place_resolution: PlaceResolution | None = None,
) -> EnrichedMappingPlan:
    return EnrichedMappingPlan(
        dataset_name="test_dataset",
        understanding=DatasetUnderstanding(
            archetype="flat",
            observation_grain="row-per-observation",
            key_insight="test",
        ),
        active_columns=active_columns or [_make_column("col_a", ColumnRole.MEASURE)],
        ignored_columns=ignored_columns or [],
        static_properties=[],
        global_notes=[],
        statvar_blueprint=StatVarBlueprint(
            base_properties=[StatVarProperty(name="populationType", value="Person")],
            constraint_columns=[],
            measure_columns=["col_a"],
        ),
        value_dictionaries=value_dictionaries or [],
        composite_key=[],
        place_resolution=place_resolution,
    )


def _make_csv(columns: list[str], rows: list[list] | None = None) -> str:
    """Write a temp CSV and return the path."""
    df = pd.DataFrame(
        rows or [["x"] * len(columns)],
        columns=columns,
    )
    fd, path = tempfile.mkstemp(suffix=".csv")
    os.close(fd)
    df.to_csv(path, index=False)
    return path


# ---------------------------------------------------------------------------
# strip_total_indicators
# ---------------------------------------------------------------------------

class TestStripTotalIndicators:
    def test_marks_total_as_drop_constraint(self):
        vd = ValueDictionary(
            column_name="sex",
            dc_property="gender",
            mappings=[
                ValueMapping(raw_value="T", dcid="dcid:Male", action="MAP", reason="original"),
                ValueMapping(raw_value="Male", dcid="dcid:Male", action="MAP", reason="male"),
            ],
        )
        plan = _make_plan(value_dictionaries=[vd])
        result = strip_total_indicators(plan)

        t_mapping = result.value_dictionaries[0].mappings[0]
        assert t_mapping.action == "DROP_CONSTRAINT"
        assert t_mapping.dcid is None
        assert "total indicator" in t_mapping.reason.lower()

    def test_preserves_non_total_values(self):
        vd = ValueDictionary(
            column_name="sex",
            dc_property="gender",
            mappings=[
                ValueMapping(raw_value="Male", dcid="dcid:Male", action="MAP", reason="male"),
                ValueMapping(raw_value="Female", dcid="dcid:Female", action="MAP", reason="female"),
            ],
        )
        plan = _make_plan(value_dictionaries=[vd])
        result = strip_total_indicators(plan)

        for m in result.value_dictionaries[0].mappings:
            assert m.action == "MAP"
            assert m.dcid is not None

    def test_handles_whitespace_in_raw_value(self):
        vd = ValueDictionary(
            column_name="race",
            dc_property="race",
            mappings=[
                ValueMapping(raw_value="  Total  ", dcid="dcid:Total", action="MAP", reason="x"),
            ],
        )
        plan = _make_plan(value_dictionaries=[vd])
        result = strip_total_indicators(plan)

        assert result.value_dictionaries[0].mappings[0].action == "DROP_CONSTRAINT"

    def test_handles_empty_value_dictionaries(self):
        plan = _make_plan(value_dictionaries=[])
        result = strip_total_indicators(plan)
        assert result.value_dictionaries == []

    def test_case_sensitive_matching(self):
        """TOTAL_INDICATORS uses exact match — 'total' (lowercase) is not in the set."""
        vd = ValueDictionary(
            column_name="dim",
            dc_property="prop",
            mappings=[
                ValueMapping(raw_value="total", dcid="dcid:X", action="MAP", reason="x"),
            ],
        )
        plan = _make_plan(value_dictionaries=[vd])
        result = strip_total_indicators(plan)

        # "total" is not in the set; "Total" is. Verify behavior matches constants.
        if "total" in TOTAL_INDICATORS:
            assert result.value_dictionaries[0].mappings[0].action == "DROP_CONSTRAINT"
        else:
            assert result.value_dictionaries[0].mappings[0].action == "MAP"

    def test_all_known_total_indicators(self):
        """Every value in TOTAL_INDICATORS should be caught."""
        for indicator in TOTAL_INDICATORS:
            vd = ValueDictionary(
                column_name="dim",
                dc_property="prop",
                mappings=[
                    ValueMapping(raw_value=indicator, dcid="dcid:X", action="MAP", reason="x"),
                ],
            )
            plan = _make_plan(value_dictionaries=[vd])
            result = strip_total_indicators(plan)
            assert result.value_dictionaries[0].mappings[0].action == "DROP_CONSTRAINT", (
                f"Expected DROP_CONSTRAINT for indicator '{indicator}'"
            )


# ---------------------------------------------------------------------------
# check_column_alignment
# ---------------------------------------------------------------------------

class TestCheckColumnAlignment:
    def test_matching_columns_no_issues(self):
        plan = _make_plan(
            active_columns=[_make_column("col_a"), _make_column("col_b")],
            ignored_columns=[_make_column("col_c", ColumnRole.IGNORED)],
        )
        csv_path = _make_csv(["col_a", "col_b", "col_c"])
        try:
            issues = check_column_alignment(plan, csv_path)
            assert issues == []
        finally:
            os.unlink(csv_path)

    def test_missing_column_in_csv(self):
        plan = _make_plan(
            active_columns=[_make_column("col_a"), _make_column("col_missing")],
        )
        csv_path = _make_csv(["col_a", "col_b"])
        try:
            issues = check_column_alignment(plan, csv_path)
            assert len(issues) >= 1
            assert any("col_missing" in issue for issue in issues)
        finally:
            os.unlink(csv_path)

    def test_new_unmapped_column_in_csv(self):
        plan = _make_plan(
            active_columns=[_make_column("col_a")],
            ignored_columns=[],
        )
        csv_path = _make_csv(["col_a", "col_extra"])
        try:
            issues = check_column_alignment(plan, csv_path)
            assert len(issues) >= 1
            assert any("col_extra" in issue for issue in issues)
        finally:
            os.unlink(csv_path)

    def test_both_missing_and_unmapped(self):
        plan = _make_plan(
            active_columns=[_make_column("col_a"), _make_column("col_missing")],
            ignored_columns=[],
        )
        csv_path = _make_csv(["col_a", "col_extra"])
        try:
            issues = check_column_alignment(plan, csv_path)
            assert len(issues) >= 2
            missing_issues = [i for i in issues if "col_missing" in i]
            unmapped_issues = [i for i in issues if "col_extra" in i]
            assert len(missing_issues) >= 1
            assert len(unmapped_issues) >= 1
        finally:
            os.unlink(csv_path)


# ---------------------------------------------------------------------------
# normalize_place_formats
# ---------------------------------------------------------------------------

class TestNormalizePlaceFormats:
    def test_updates_value_expression_with_prefix(self):
        place_col = _make_column("geo", ColumnRole.OBSERVATION_ABOUT, prop="observationAbout")
        plan = _make_plan(
            active_columns=[place_col],
            place_resolution=PlaceResolution(
                column_name="geo",
                format_detected="ISO 3166-1 alpha-2",
                prefix_rule="country/",
                resolution_rate=0.95,
            ),
        )
        result = normalize_place_formats(plan)

        geo_col = next(c for c in result.active_columns if c.column_name == "geo")
        selected = geo_col.candidates[geo_col.selected_index]
        assert "country/" in selected.value_expression
        assert "[DATA]" in selected.value_expression

    def test_no_place_resolution_returns_plan_unchanged(self):
        plan = _make_plan(place_resolution=None)
        result = normalize_place_formats(plan)
        assert result == plan

    def test_no_double_prefix(self):
        """If the expression already has the prefix, don't add it again."""
        place_col = ColumnMapping(
            column_name="geo",
            role=ColumnRole.OBSERVATION_ABOUT,
            candidates=[_make_candidate(prop="observationAbout", value="country/[DATA]")],
            evidence="test",
        )
        plan = _make_plan(
            active_columns=[place_col],
            place_resolution=PlaceResolution(
                column_name="geo",
                format_detected="ISO alpha-2",
                prefix_rule="country/",
                resolution_rate=0.95,
            ),
        )
        result = normalize_place_formats(plan)

        geo_col = next(c for c in result.active_columns if c.column_name == "geo")
        selected = geo_col.candidates[geo_col.selected_index]
        # Should not become "country/country/[DATA]"
        assert selected.value_expression.count("country/") == 1


# ---------------------------------------------------------------------------
# normalize_time_formats
# ---------------------------------------------------------------------------

class TestNormalizeTimeFormats:
    def test_returns_plan_unchanged(self):
        plan = _make_plan()
        result = normalize_time_formats(plan)
        assert result == plan


# ---------------------------------------------------------------------------
# apply_mitigations (integration)
# ---------------------------------------------------------------------------

class TestApplyMitigations:
    def test_runs_all_mitigations(self):
        vd = ValueDictionary(
            column_name="sex",
            dc_property="gender",
            mappings=[
                ValueMapping(raw_value="T", dcid="dcid:Male", action="MAP", reason="x"),
                ValueMapping(raw_value="Male", dcid="dcid:Male", action="MAP", reason="male"),
            ],
        )
        place_col = _make_column("geo", ColumnRole.OBSERVATION_ABOUT, prop="observationAbout")
        plan = _make_plan(
            active_columns=[_make_column("col_a"), place_col, _make_column("sex")],
            value_dictionaries=[vd],
            place_resolution=PlaceResolution(
                column_name="geo",
                format_detected="ISO alpha-2",
                prefix_rule="country/",
                resolution_rate=0.95,
            ),
        )
        csv_path = _make_csv(["col_a", "geo", "sex"])
        try:
            result = apply_mitigations(plan, csv_path)

            # strip_total_indicators ran
            t_mapping = result.value_dictionaries[0].mappings[0]
            assert t_mapping.action == "DROP_CONSTRAINT"

            # normalize_place_formats ran
            geo_col = next(c for c in result.active_columns if c.column_name == "geo")
            selected = geo_col.candidates[geo_col.selected_index]
            assert "country/" in selected.value_expression

        finally:
            os.unlink(csv_path)

    def test_alignment_issues_do_not_raise(self):
        """Alignment issues should be logged as warnings, not raise exceptions."""
        plan = _make_plan(
            active_columns=[_make_column("col_a"), _make_column("col_missing")],
        )
        csv_path = _make_csv(["col_a", "col_extra"])
        try:
            # Should not raise
            result = apply_mitigations(plan, csv_path)
            assert result is not None
        finally:
            os.unlink(csv_path)
