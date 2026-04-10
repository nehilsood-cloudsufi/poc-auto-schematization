"""Integration test: full flow from column profiles -> candidates -> plan -> skeleton."""
import json

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
from src.pipeline.plan.candidate_retriever import CandidateRetriever
from src.pipeline.plan.skeleton_converter import plan_to_skeleton_csv


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_col(
    name: str,
    dtype: str = "String",
    semantic_type: str = None,
    cardinality: int = 10,
    cardinality_ratio: float = 0.1,
    looks_like_place: bool = False,
    looks_like_date: bool = False,
    sample_values: list = None,
    **extra,
) -> dict:
    """Build a minimal column profile dict."""
    d = {
        "name": name,
        "dtype": dtype,
        "semantic_type": semantic_type,
        "cardinality": cardinality,
        "cardinality_ratio": cardinality_ratio,
        "looks_like_place": looks_like_place,
        "looks_like_date": looks_like_date,
        "null_pct": 0.0,
        "top_values": [],
        "sample_values": sample_values or [],
    }
    d.update(extra)
    return d


class TestEndToEndFlow:
    """End-to-end integration: columns -> CandidateRetriever -> MappingPlan -> skeleton CSV."""

    def test_bis_columns_to_skeleton(self):
        """Simulate the BIS dataset flow: columns -> candidates -> plan -> skeleton."""
        retriever = CandidateRetriever()

        # Simplified BIS column profiles (dict keyed by column name)
        columns = {
            "REF_AREA:Reference area": _make_col(
                name="REF_AREA:Reference area",
                dtype="String",
                semantic_type="place",
                cardinality=50,
                cardinality_ratio=0.1,
                sample_values=["GB: United Kingdom", "AR: Argentina"],
            ),
            "TIME_PERIOD:Time period": _make_col(
                name="TIME_PERIOD:Time period",
                dtype="Date",
                semantic_type="date",
                cardinality=100,
                cardinality_ratio=0.5,
                sample_values=["2020-01", "2021-06"],
            ),
            "OBS_VALUE:Observation Value": _make_col(
                name="OBS_VALUE:Observation Value",
                dtype="Float",
                semantic_type=None,
                cardinality=500,
                cardinality_ratio=0.8,
                sample_values=["1.5", "3.2"],
            ),
            "FREQ:Frequency": _make_col(
                name="FREQ:Frequency",
                dtype="String",
                semantic_type=None,
                cardinality=2,
                cardinality_ratio=0.001,
                sample_values=["M: Monthly", "D: Daily"],
            ),
            "STRUCTURE": _make_col(
                name="STRUCTURE",
                dtype="String",
                semantic_type=None,
                cardinality=1,
                cardinality_ratio=0.001,
                sample_values=["dataflow"],
            ),
        }

        # Step 1: Retrieve candidates
        results = retriever.retrieve_all(columns)
        assert len(results) == 5
        assert results["REF_AREA:Reference area"][0] == ColumnRole.OBSERVATION_ABOUT
        assert results["TIME_PERIOD:Time period"][0] == ColumnRole.OBSERVATION_DATE
        assert results["OBS_VALUE:Observation Value"][0] == ColumnRole.MEASURE
        assert results["STRUCTURE"][0] == ColumnRole.IGNORED

        # Step 2: Build a plan (simulating LLM output that selects from candidates)
        # Columns with no candidates and IGNORED role go to ignored_columns.
        # Columns with candidates go to active_columns.
        # In the real pipeline the LLM would fill in candidates for ambiguous
        # columns, but here we only include columns that the retriever grounded.
        active = []
        ignored = []
        for col_name, col_dict in columns.items():
            role, candidates, evidence = results[col_name]
            mapping = ColumnMapping(
                column_name=col_name,
                role=role,
                candidates=candidates,
                evidence=evidence,
            )
            if role == ColumnRole.IGNORED or len(candidates) == 0:
                ignored.append(mapping)
            else:
                active.append(mapping)

        plan = MappingPlan(
            dataset_name="bis_central_bank",
            understanding=DatasetUnderstanding(
                archetype="Flat",
                observation_grain="one row per country per period",
                key_insight="Central bank policy rates",
            ),
            active_columns=active,
            ignored_columns=ignored,
            static_properties=[
                StaticProperty(
                    property_name="populationType",
                    candidates=[PropertyValueCandidate(
                        property="populationType",
                        value_expression="InterestRate",
                        confidence=0.9,
                        source=CandidateSource.MCP,
                        reason="financial data",
                    )],
                ),
            ],
            global_notes=["Place resolution needed"],
        )

        # Step 3: Convert to skeleton CSV
        skeleton = plan_to_skeleton_csv(plan)
        assert "REF_AREA:Reference area" in skeleton
        assert "TIME_PERIOD:Time period" in skeleton
        assert "OBS_VALUE:Observation Value" in skeleton
        # Ignored columns (STRUCTURE: constant, FREQ: no candidates) excluded
        assert "STRUCTURE" not in skeleton
        assert "FREQ:Frequency" not in skeleton
        assert "populationType" in skeleton

        # Step 4: JSON roundtrip preserves the plan
        plan_json = plan.model_dump_json()
        restored = MappingPlan.model_validate_json(plan_json)
        assert len(restored.active_columns) == len(active)
        assert len(restored.ignored_columns) == len(ignored)
        assert restored.dataset_name == "bis_central_bank"
        assert restored.understanding.archetype == "Flat"

    def test_wide_dataset_flow(self):
        """Test a wide dataset with multiple measure columns."""
        retriever = CandidateRetriever()
        columns = {
            "State": _make_col(
                name="State",
                dtype="String",
                semantic_type="us_state_name",
                cardinality=50,
                cardinality_ratio=0.1,
                sample_values=["CA", "TX"],
            ),
            "Year": _make_col(
                name="Year",
                dtype="Date",
                semantic_type="yyyy",
                cardinality=20,
                cardinality_ratio=0.04,
                sample_values=["2020", "2021"],
            ),
            "Population": _make_col(
                name="Population",
                dtype="Integer",
                semantic_type=None,
                cardinality=1000,
                cardinality_ratio=0.9,
                sample_values=["39538223", "29145505"],
            ),
            "Median_Income": _make_col(
                name="Median_Income",
                dtype="Float",
                semantic_type=None,
                cardinality=800,
                cardinality_ratio=0.7,
                sample_values=["75235.0", "64034.0"],
            ),
        }

        results = retriever.retrieve_all(columns)
        assert results["State"][0] == ColumnRole.OBSERVATION_ABOUT
        assert results["Year"][0] == ColumnRole.OBSERVATION_DATE
        assert results["Population"][0] == ColumnRole.MEASURE
        assert results["Median_Income"][0] == ColumnRole.MEASURE

        # Build plan from candidates and convert to skeleton
        active = []
        for col_name, col_dict in columns.items():
            role, candidates, evidence = results[col_name]
            active.append(ColumnMapping(
                column_name=col_name,
                role=role,
                candidates=candidates,
                evidence=evidence,
            ))

        plan = MappingPlan(
            dataset_name="wide_census",
            understanding=DatasetUnderstanding(
                archetype="Wide",
                observation_grain="one row per state per year",
                key_insight="State-level demographics with multiple measures",
            ),
            active_columns=active,
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )

        skeleton = plan_to_skeleton_csv(plan)
        # All four columns should appear in skeleton (no ignored columns)
        assert "State" in skeleton
        assert "Year" in skeleton
        assert "Population" in skeleton
        assert "Median_Income" in skeleton

    def test_dimension_column_gets_candidates_from_vocab(self):
        """A dimension column should pick up candidates from schema vocab."""
        retriever = CandidateRetriever()
        vocab = json.dumps({
            "category": "Economy",
            "stat_var_skeletons": {
                "Person": ["gender", "age"],
            },
            "property_vocabulary": {
                "gender": ["Female", "Male"],
                "age": ["Years15Onwards"],
            },
        })
        columns = {
            "gender": _make_col(
                name="gender",
                dtype="String",
                cardinality=3,
                cardinality_ratio=0.01,
            ),
        }
        results = retriever.retrieve_all(columns, schema_vocab=vocab)
        role, candidates, evidence = results["gender"]
        assert role == ColumnRole.DIMENSION

        # Should have at least one candidate from vocab
        vocab_cands = [c for c in candidates if c.source == CandidateSource.SCHEMA_VOCAB]
        assert len(vocab_cands) >= 1
        assert any(c.property == "gender" for c in vocab_cands)

        # Build plan and convert to skeleton
        plan = MappingPlan(
            dataset_name="test_vocab",
            understanding=DatasetUnderstanding(
                archetype="Flat",
                observation_grain="n/a",
                key_insight="n/a",
            ),
            active_columns=[
                ColumnMapping(
                    column_name="gender",
                    role=role,
                    candidates=candidates,
                    evidence=evidence,
                ),
            ],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )
        skeleton = plan_to_skeleton_csv(plan)
        assert "gender" in skeleton

    def test_plan_with_no_candidates_is_valid_model(self):
        """A column with no candidates can exist in the plan model but won't appear in skeleton."""
        plan = MappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(
                archetype="Flat",
                observation_grain="n/a",
                key_insight="n/a",
            ),
            active_columns=[
                ColumnMapping(
                    column_name="known_col",
                    role=ColumnRole.MEASURE,
                    candidates=[PropertyValueCandidate(
                        property="value",
                        value_expression="{Number}",
                        confidence=0.85,
                        source=CandidateSource.SCHEMA_ORG,
                        reason="numeric column",
                    )],
                    evidence="numeric, high cardinality",
                ),
            ],
            ignored_columns=[
                ColumnMapping(
                    column_name="mystery_col",
                    role=ColumnRole.IGNORED,
                    candidates=[],
                    evidence="constant column, 1 unique value",
                ),
            ],
            static_properties=[],
            global_notes=[],
        )

        # The plan is structurally valid
        assert len(plan.active_columns) == 1
        assert len(plan.ignored_columns) == 1

        # Skeleton includes only active columns with candidates
        skeleton = plan_to_skeleton_csv(plan)
        assert "known_col" in skeleton
        assert "mystery_col" not in skeleton

        # JSON roundtrip preserves empty candidate list
        restored = MappingPlan.model_validate_json(plan.model_dump_json())
        assert len(restored.ignored_columns[0].candidates) == 0

    def test_full_roundtrip_preserves_all_fields(self):
        """Verify that JSON serialization roundtrip preserves every field accurately."""
        candidate = PropertyValueCandidate(
            property="observationAbout",
            value_expression="country/{Data}",
            confidence=0.95,
            source=CandidateSource.SCHEMA_ORG,
            reason="identified as place column",
        )
        plan = MappingPlan(
            dataset_name="roundtrip_test",
            understanding=DatasetUnderstanding(
                archetype="Dimension/Row",
                observation_grain="one row per entity per date per dimension",
                key_insight="Coded dimensions need decomposition",
            ),
            active_columns=[
                ColumnMapping(
                    column_name="REF_AREA",
                    role=ColumnRole.OBSERVATION_ABOUT,
                    candidates=[candidate],
                    selected_index=0,
                    evidence="place column",
                    dc_match="dcid:Country",
                    is_ambiguous=False,
                ),
            ],
            ignored_columns=[],
            static_properties=[
                StaticProperty(
                    property_name="unit",
                    candidates=[PropertyValueCandidate(
                        property="unit",
                        value_expression="dcid:Percent",
                        confidence=0.9,
                        source=CandidateSource.MCP,
                        reason="unit from context",
                    )],
                    selected_index=0,
                ),
            ],
            global_notes=["Place resolution needed", "Monthly frequency"],
        )

        plan_json = plan.model_dump_json()
        restored = MappingPlan.model_validate_json(plan_json)

        assert restored.dataset_name == plan.dataset_name
        assert restored.understanding.archetype == "Dimension/Row"
        assert restored.understanding.observation_grain == plan.understanding.observation_grain
        assert len(restored.active_columns) == 1
        assert restored.active_columns[0].dc_match == "dcid:Country"
        assert restored.active_columns[0].candidates[0].confidence == 0.95
        assert restored.active_columns[0].candidates[0].source == CandidateSource.SCHEMA_ORG
        assert len(restored.static_properties) == 1
        assert restored.static_properties[0].candidates[0].value_expression == "dcid:Percent"
        assert restored.global_notes == ["Place resolution needed", "Monthly frequency"]
