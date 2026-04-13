"""End-to-end test: Phase A analysis -> enriched plan model -> mitigations -> skeleton CSV."""
import json
import pandas as pd
import pytest

from src.pipeline.plan.column_analyzer import analyze_columns
from src.pipeline.plan.plan_mitigations import strip_total_indicators, apply_mitigations
from src.pipeline.plan.skeleton_converter import plan_to_skeleton_csv
from src.api.models.plan import (
    EnrichedMappingPlan, DatasetUnderstanding, ColumnMapping, ColumnRole,
    PropertyValueCandidate, CandidateSource, StaticProperty,
    StatVarBlueprint, ValueDictionary, ValueMapping,
)


def test_phase_a_to_skeleton_roundtrip(tmp_path):
    """Phase A analysis + enriched plan + mitigations + skeleton generation."""
    # 1. Create a test CSV
    csv_path = tmp_path / "test_data" / "data_input.csv"
    csv_path.parent.mkdir(parents=True)
    df = pd.DataFrame({
        "REF_AREA": ["AR", "AR", "BR", "BR"],
        "TIME_PERIOD": ["2020", "2021", "2020", "2021"],
        "SEX": ["M", "F", "M", "F"],
        "OBS_VALUE": [100.0, 200.0, 300.0, 400.0],
    })
    df.to_csv(csv_path, index=False)

    # 2. Run Phase A analysis
    analysis = analyze_columns(df)
    assert len(analysis.composite_key) > 0
    # Should detect place format for REF_AREA (ISO-2)
    # Should detect time format for TIME_PERIOD (YYYY)

    # 3. Build enriched plan (simulates Phase B LLM output)
    plan = EnrichedMappingPlan(
        dataset_name="test_e2e",
        understanding=DatasetUnderstanding(
            archetype="Long/Tidy",
            observation_grain="Country x Year x Gender",
            key_insight="Standard SDMX dataset",
        ),
        active_columns=[
            ColumnMapping(column_name="REF_AREA", role=ColumnRole.OBSERVATION_ABOUT,
                candidates=[PropertyValueCandidate(property="observationAbout", value_expression="country/[DATA]", confidence=0.95, source=CandidateSource.SCHEMA_ORG, reason="ISO-2")],
                evidence="ISO-2 codes"),
            ColumnMapping(column_name="TIME_PERIOD", role=ColumnRole.OBSERVATION_DATE,
                candidates=[PropertyValueCandidate(property="observationDate", value_expression="[DATA]", confidence=0.95, source=CandidateSource.SCHEMA_ORG, reason="YYYY")],
                evidence="Year format"),
            ColumnMapping(column_name="SEX", role=ColumnRole.DIMENSION,
                candidates=[PropertyValueCandidate(property="gender", value_expression="[DATA]", confidence=0.90, source=CandidateSource.LLM, reason="Gender")],
                evidence="Categorical"),
            ColumnMapping(column_name="OBS_VALUE", role=ColumnRole.MEASURE,
                candidates=[PropertyValueCandidate(property="value", value_expression="[NUMBER]", confidence=0.99, source=CandidateSource.SCHEMA_ORG, reason="Numeric")],
                evidence="Continuous"),
        ],
        ignored_columns=[],
        static_properties=[
            StaticProperty(property_name="populationType",
                candidates=[PropertyValueCandidate(property="populationType", value_expression="dcs:Person", confidence=0.90, source=CandidateSource.LLM, reason="Population")]),
        ],
        global_notes=[],
        column_relationships=analysis.relationships,
        statvar_blueprint=StatVarBlueprint(
            base_properties={"populationType": "dcs:Person", "measuredProperty": "dcs:count"},
            constraint_columns=["SEX"],
            measure_columns=["OBS_VALUE"],
        ),
        value_dictionaries=[
            ValueDictionary(column_name="SEX", dc_property="gender", mappings=[
                ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="Male"),
                ValueMapping(raw_value="F", dcid="dcs:Female", action="MAP", reason="Female"),
            ], total_indicators=[]),
        ],
        composite_key=analysis.composite_key,
    )

    # 4. Apply mitigations
    plan = apply_mitigations(plan, csv_path)

    # 5. Generate skeleton
    skeleton = plan_to_skeleton_csv(plan)
    assert "REF_AREA" in skeleton
    assert "TIME_PERIOD" in skeleton
    assert "OBS_VALUE" in skeleton
    assert "SEX" in skeleton

    # 6. JSON roundtrip
    json_str = plan.model_dump_json(indent=2)
    restored = EnrichedMappingPlan.model_validate_json(json_str)
    assert restored.dataset_name == "test_e2e"
    assert len(restored.value_dictionaries) == 1
    assert len(restored.column_relationships) >= 0
    assert restored.composite_key == analysis.composite_key

    # 7. Verify analysis serializes cleanly for ADK state
    analysis_json = json.dumps(analysis.to_dict())
    analysis_restored = json.loads(analysis_json)
    assert "composite_key" in analysis_restored
    assert "relationships" in analysis_restored


def test_total_indicator_mitigation_e2e(tmp_path):
    """Total indicators in value dictionaries get stripped to DROP_CONSTRAINT."""
    csv_path = tmp_path / "data.csv"
    df = pd.DataFrame({"SEX": ["M", "F", "T"], "VAL": [1, 2, 3]})
    df.to_csv(csv_path, index=False)

    plan = EnrichedMappingPlan(
        dataset_name="test_totals",
        understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
        active_columns=[
            ColumnMapping(column_name="VAL", role=ColumnRole.MEASURE,
                candidates=[PropertyValueCandidate(property="value", value_expression="[NUMBER]", confidence=0.9, source=CandidateSource.LLM, reason="test")],
                evidence="numeric"),
        ],
        ignored_columns=[],
        static_properties=[],
        global_notes=[],
        statvar_blueprint=StatVarBlueprint(
            base_properties={"populationType": "dcs:Person"},
            constraint_columns=["SEX"], measure_columns=["VAL"],
        ),
        value_dictionaries=[
            ValueDictionary(column_name="SEX", dc_property="gender", mappings=[
                ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="Male"),
                ValueMapping(raw_value="F", dcid="dcs:Female", action="MAP", reason="Female"),
                ValueMapping(raw_value="T", dcid="dcs:SomeWrongThing", action="MAP", reason="Wrong"),
            ], total_indicators=["T"]),
        ],
        composite_key=["SEX"],
    )

    plan = apply_mitigations(plan, csv_path)

    # T should now be DROP_CONSTRAINT
    t_mapping = [m for m in plan.value_dictionaries[0].mappings if m.raw_value == "T"][0]
    assert t_mapping.action == "DROP_CONSTRAINT"
    assert t_mapping.dcid is None

    # M and F should be unchanged
    m_mapping = [m for m in plan.value_dictionaries[0].mappings if m.raw_value == "M"][0]
    assert m_mapping.action == "MAP"
    assert m_mapping.dcid == "dcs:Male"
