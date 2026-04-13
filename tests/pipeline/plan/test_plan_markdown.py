"""Tests for _plan_to_markdown() — base and enriched plan rendering."""

import pytest

from src.agents.mapping_plan_agent import _plan_to_markdown
from src.api.models.plan import (
    MappingPlan,
    EnrichedMappingPlan,
    DatasetUnderstanding,
    ColumnMapping,
    ColumnRole,
    PropertyValueCandidate,
    CandidateSource,
    StaticProperty,
    StatVarBlueprint,
    StatVarProperty,
    ValueDictionary,
    ValueMapping,
    ColumnRelationship,
    RelationshipType,
    PlaceResolution,
    TimeResolution,
)


def _make_base_plan() -> MappingPlan:
    """Helper: build a minimal valid MappingPlan."""
    return MappingPlan(
        dataset_name="test_dataset",
        understanding=DatasetUnderstanding(
            archetype="wide",
            observation_grain="country-year",
            key_insight="One row per country per year",
        ),
        active_columns=[
            ColumnMapping(
                column_name="Country",
                role=ColumnRole.OBSERVATION_ABOUT,
                candidates=[
                    PropertyValueCandidate(
                        property="observationAbout",
                        value_expression="[Country]",
                        confidence=0.95,
                        source=CandidateSource.LLM,
                        reason="Place column",
                    ),
                ],
                selected_index=0,
                evidence="Contains country names",
            ),
        ],
        ignored_columns=[],
        static_properties=[
            StaticProperty(
                property_name="unit",
                candidates=[
                    PropertyValueCandidate(
                        property="unit",
                        value_expression="dcid:SDG_GH",
                        confidence=0.8,
                        source=CandidateSource.SCHEMA_VOCAB,
                        reason="Greenhouse gas unit",
                    ),
                ],
                selected_index=0,
            ),
        ],
        global_notes=["Dataset has no missing values"],
    )


def _make_enriched_plan() -> EnrichedMappingPlan:
    """Helper: build an EnrichedMappingPlan with all enriched fields populated."""
    base = _make_base_plan()
    return EnrichedMappingPlan(
        **base.model_dump(),
        composite_key=["Country", "Year"],
        statvar_blueprint=StatVarBlueprint(
            base_properties=[
                StatVarProperty(name="populationType", value="dcid:Person"),
                StatVarProperty(name="measuredProperty", value="dcid:count"),
            ],
            constraint_columns=["Gender", "AgeGroup"],
            measure_columns=["Value"],
        ),
        value_dictionaries=[
            ValueDictionary(
                column_name="Gender",
                dc_property="gender",
                mappings=[
                    ValueMapping(
                        raw_value="M",
                        dcid="dcid:Male",
                        action="MAP",
                        reason="Standard mapping",
                    ),
                    ValueMapping(
                        raw_value="F",
                        dcid="dcid:Female",
                        action="MAP",
                        reason="Standard mapping",
                    ),
                    ValueMapping(
                        raw_value="Total",
                        dcid=None,
                        action="DROP_CONSTRAINT",
                        reason="Aggregate row",
                    ),
                ],
            ),
        ],
        column_relationships=[
            ColumnRelationship(
                column_a="Country",
                column_b="Region",
                relationship=RelationshipType.HIERARCHICAL,
                strength=0.9,
                evidence="Region is parent of Country",
                pvmap_implication="Use Country for observationAbout",
            ),
            ColumnRelationship(
                column_a="ColX",
                column_b="ColY",
                relationship=RelationshipType.INDEPENDENT,
                strength=0.1,
                evidence="No relationship",
                pvmap_implication="None",
            ),
        ],
        place_resolution=PlaceResolution(
            column_name="Country",
            format_detected="ISO 3166-1 alpha-2",
            prefix_rule="country/",
            resolution_rate=0.98,
        ),
        time_resolution=TimeResolution(
            columns=["Year"],
            format_detected="YYYY",
            normalization_rule="No change needed",
        ),
    )


class TestBasePlanMarkdown:
    """_plan_to_markdown() renders standard MappingPlan sections."""

    def test_base_plan_markdown(self):
        plan = _make_base_plan()
        md = _plan_to_markdown(plan)

        # Title
        assert "# Mapping Plan: test_dataset" in md

        # Dataset Understanding
        assert "## Dataset Understanding" in md
        assert "**Archetype:** wide" in md
        assert "**Observation grain:** country-year" in md
        assert "**Key insight:** One row per country per year" in md

        # Active Column Mappings
        assert "## Active Column Mappings" in md
        assert "### Column: `Country`" in md
        assert "**Role:** observationAbout" in md
        assert "**(selected)**" in md

        # Static Properties
        assert "## Static Properties" in md
        assert "### `unit`" in md

        # Global Notes
        assert "## Global Notes" in md
        assert "- Dataset has no missing values" in md


class TestEnrichedPlanMarkdown:
    """_plan_to_markdown() renders enriched sections when present."""

    def test_enriched_plan_includes_blueprint(self):
        plan = _make_enriched_plan()
        md = _plan_to_markdown(plan)

        # --- Composite Key ---
        assert "## Composite Key" in md
        assert "Country" in md
        assert "Year" in md

        # --- StatVar Blueprint ---
        assert "## StatVar Blueprint" in md
        assert "populationType" in md
        assert "dcid:Person" in md
        assert "measuredProperty" in md
        assert "dcid:count" in md
        assert "Constraint columns" in md
        assert "Gender" in md
        assert "Measure columns" in md
        assert "Value" in md

        # --- Value Dictionaries ---
        assert "## Value Dictionaries" in md
        assert "### Gender" in md
        assert "| Raw Value | Action | DCID | Reason |" in md
        assert "M" in md
        assert "dcid:Male" in md
        assert "DROP_CONSTRAINT" in md

        # --- Column Relationships ---
        assert "## Column Relationships" in md
        assert "| Column A | Relationship | Column B | Evidence |" in md
        assert "Country" in md
        assert "hierarchical" in md
        # Independent relationships should be filtered out
        assert "ColX" not in md
        assert "independent" not in md.split("## Column Relationships")[1].split("##")[0]

        # --- Place Resolution ---
        assert "## Place Resolution" in md
        assert "ISO 3166-1 alpha-2" in md
        assert "country/" in md
        assert "0.98" in md

        # --- Time Resolution ---
        assert "## Time Resolution" in md
        assert "YYYY" in md
        assert "No change needed" in md


class TestBasePlanNoEnrichedSections:
    """Base MappingPlan does NOT produce enriched sections."""

    def test_base_plan_no_enriched_sections(self):
        plan = _make_base_plan()
        md = _plan_to_markdown(plan)

        assert "## Composite Key" not in md
        assert "## StatVar Blueprint" not in md
        assert "## Value Dictionaries" not in md
        assert "## Column Relationships" not in md
        assert "## Place Resolution" not in md
        assert "## Time Resolution" not in md
