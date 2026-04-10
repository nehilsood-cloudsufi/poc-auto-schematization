"""Tests for MappingPlan Pydantic models."""
import pytest
from src.api.models.plan import (
    CandidateSource,
    CandidateValidation,
    ColumnMapping,
    ColumnRole,
    DatasetUnderstanding,
    MappingPlan,
    PropertyValueCandidate,
    StaticProperty,
)


def _make_candidate(**overrides):
    defaults = {
        "property": "observationAbout",
        "value_expression": "country/[DATA]",
        "confidence": 0.9,
        "source": CandidateSource.SCHEMA_ORG,
        "reason": "place semantic type",
    }
    defaults.update(overrides)
    return PropertyValueCandidate(**defaults)


def _make_column(**overrides):
    defaults = {
        "column_name": "REF_AREA",
        "role": ColumnRole.OBSERVATION_ABOUT,
        "candidates": [_make_candidate()],
        "evidence": "2 unique, String, 'GB', 'AR'",
    }
    defaults.update(overrides)
    return ColumnMapping(**defaults)


class TestPropertyValueCandidate:
    def test_valid_candidate(self):
        c = _make_candidate()
        assert c.property == "observationAbout"
        assert c.confidence == 0.9
        assert c.source == CandidateSource.SCHEMA_ORG

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            _make_candidate(confidence=1.5)
        with pytest.raises(Exception):
            _make_candidate(confidence=-0.1)

    def test_all_sources(self):
        for source in CandidateSource:
            c = _make_candidate(source=source)
            assert c.source == source


class TestColumnMapping:
    def test_defaults(self):
        col = _make_column()
        assert col.selected_index == 0
        assert col.dc_match is None
        assert col.is_ambiguous is False

    def test_selected_index_within_bounds(self):
        col = _make_column(candidates=[_make_candidate(), _make_candidate(property="geoId")])
        col.selected_index = 1
        assert col.candidates[col.selected_index].property == "geoId"

    def test_all_roles(self):
        for role in ColumnRole:
            col = _make_column(role=role)
            assert col.role == role


class TestMappingPlan:
    def test_full_plan(self):
        plan = MappingPlan(
            dataset_name="bis_central_bank",
            understanding=DatasetUnderstanding(
                archetype="Flat",
                observation_grain="one row per country per period",
                key_insight="Central bank policy rates over time",
            ),
            active_columns=[_make_column()],
            ignored_columns=[
                _make_column(
                    column_name="STRUCTURE",
                    role=ColumnRole.IGNORED,
                    candidates=[],
                    evidence="1 unique, constant 'dataflow'",
                )
            ],
            static_properties=[
                StaticProperty(
                    property_name="populationType",
                    candidates=[_make_candidate(property="populationType", value_expression="InterestRate")],
                )
            ],
            global_notes=["Place resolution needed for REF_AREA"],
        )
        assert plan.dataset_name == "bis_central_bank"
        assert len(plan.active_columns) == 1
        assert len(plan.ignored_columns) == 1

    def test_json_roundtrip(self):
        plan = MappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(
                archetype="Wide", observation_grain="one row per state per year", key_insight="Test data"
            ),
            active_columns=[_make_column()],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )
        json_str = plan.model_dump_json()
        restored = MappingPlan.model_validate_json(json_str)
        assert restored.dataset_name == plan.dataset_name
        assert restored.active_columns[0].column_name == "REF_AREA"

    def test_validation_field_optional(self):
        c = _make_candidate()
        assert c.validation is None
        c_with = _make_candidate()
        c_with.validation = CandidateValidation(
            property_exists=True,
            notes="verified",
        )
        assert c_with.validation.property_exists is True


class TestEngineerNotes:
    def test_default_empty(self):
        plan = MappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(
                archetype="Flat", observation_grain="n/a", key_insight="n/a"
            ),
            active_columns=[],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )
        assert plan.engineer_notes == []

    def test_notes_persist_roundtrip(self):
        plan = MappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(
                archetype="Flat", observation_grain="n/a", key_insight="n/a"
            ),
            active_columns=[],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
            engineer_notes=["Date format is YYYY-MM", "Use wikidataId for places"],
        )
        restored = MappingPlan.model_validate_json(plan.model_dump_json())
        assert restored.engineer_notes == ["Date format is YYYY-MM", "Use wikidataId for places"]

    def test_backward_compat_no_notes_field(self):
        old_json = '{"dataset_name":"test","understanding":{"archetype":"Flat","observation_grain":"n/a","key_insight":"n/a"},"active_columns":[],"ignored_columns":[],"static_properties":[],"global_notes":[]}'
        plan = MappingPlan.model_validate_json(old_json)
        assert plan.engineer_notes == []
