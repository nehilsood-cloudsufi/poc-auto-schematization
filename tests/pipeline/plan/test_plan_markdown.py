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
    IndicatorValueMapping,
    IndicatorColumn,
    ObservationTemplate,
    MappingRule,
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
        assert "## Indicator Columns" not in md
        assert "## Mapping Rules" not in md


class TestIndicatorColumnsMarkdown:
    """_plan_to_markdown() renders Indicator Columns section."""

    def test_enriched_plan_includes_indicator_columns(self):
        base = _make_base_plan()
        plan = EnrichedMappingPlan(
            **base.model_dump(),
            statvar_blueprint=StatVarBlueprint(
                base_properties=[
                    StatVarProperty(name="populationType", value="dcid:Person"),
                ],
                constraint_columns=[],
                measure_columns=["Value"],
            ),
            indicator_columns=[
                IndicatorColumn(
                    column_name="Metric",
                    value_mappings=[
                        IndicatorValueMapping(
                            raw_value="Population",
                            population_type="dcid:Person",
                            measured_property="dcid:count",
                            stat_type="measuredValue",
                            reason="Total population count",
                        ),
                        IndicatorValueMapping(
                            raw_value="GDP",
                            population_type="dcid:EconomicActivity",
                            measured_property="dcid:amount",
                            stat_type="measuredValue",
                            reason="Gross domestic product",
                        ),
                    ],
                ),
            ],
        )
        md = _plan_to_markdown(plan)

        # Section header
        assert "## Indicator Columns" in md
        assert "These columns change the core StatVar definition" in md

        # Column sub-header
        assert "### `Metric`" in md

        # Table header
        assert "| Value | populationType | measuredProperty | statType | Reason |" in md

        # Row content
        assert "| `Population` | `dcid:Person` | `dcid:count` | `measuredValue` | Total population count |" in md
        assert "| `GDP` | `dcid:EconomicActivity` | `dcid:amount` | `measuredValue` | Gross domestic product |" in md


class TestExecutiveSummaryMarkdown:
    """_plan_to_markdown() renders executive summary when present."""

    def test_executive_summary_in_markdown(self):
        plan = _make_base_plan()
        plan.understanding.executive_summary = "This dataset tracks industrial indicators for 2 countries over 10 years."
        md = _plan_to_markdown(plan)
        assert "## Executive Summary" in md
        assert "industrial indicators" in md

    def test_no_executive_summary_when_empty(self):
        plan = _make_base_plan()
        md = _plan_to_markdown(plan)
        assert "## Executive Summary" not in md


class TestColumnPurposeNarrativeMarkdown:
    """_plan_to_markdown() renders purpose and narrative for columns."""

    def test_column_purpose_and_narrative_in_markdown(self):
        plan = MappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
            active_columns=[
                ColumnMapping(
                    column_name="Country", role=ColumnRole.DIMENSION,
                    candidates=[PropertyValueCandidate(
                        property="observationAbout", value_expression="country/[DATA]",
                        confidence=0.9, source=CandidateSource.SCHEMA_ORG, reason="test",
                    )],
                    evidence="2 countries",
                    purpose="Entity Resolution Helper",
                    narrative="Human-readable country name for DCID resolution fallback.",
                ),
            ],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )
        md = _plan_to_markdown(plan)
        assert "Entity Resolution Helper" in md
        assert "Human-readable country name" in md


class TestMappingRulesMarkdown:
    """_plan_to_markdown() renders Mapping Rules section."""

    def test_enriched_plan_includes_mapping_rules(self):
        base = _make_base_plan()
        plan = EnrichedMappingPlan(
            **base.model_dump(),
            statvar_blueprint=StatVarBlueprint(
                base_properties=[
                    StatVarProperty(name="populationType", value="dcid:Person"),
                ],
                constraint_columns=["Gender"],
                measure_columns=["Value"],
            ),
            mapping_rules=[
                MappingRule(
                    rule_id="R1",
                    measure_column="Value",
                    description="Map population value by gender",
                    observation=ObservationTemplate(
                        about_column="Country",
                        about_expression="[Country]",
                        date_column="Year",
                        date_expression="[Year]",
                        value_column="Value",
                        value_expression="[Value]",
                        unit="dcid:SDG_GH",
                        unit_column=None,
                    ),
                    indicator_column="Metric",
                    constraint_columns=["Gender"],
                    pvmap_rows=[
                        "Country,observationAbout,[Country]",
                        "Year,observationDate,[Year]",
                        "Value,value,[Value]",
                    ],
                ),
                MappingRule(
                    rule_id="R2",
                    measure_column="Amount",
                    description="Map amount with unit column",
                    observation=ObservationTemplate(
                        about_column="Region",
                        about_expression="[Region]",
                        date_column="Date",
                        date_expression="[Date]",
                        value_column="Amount",
                        value_expression="[Amount]",
                        unit=None,
                        unit_column="UnitCol",
                    ),
                    indicator_column=None,
                    constraint_columns=[],
                    pvmap_rows=[],
                ),
            ],
        )
        md = _plan_to_markdown(plan)

        # Section header
        assert "## Mapping Rules" in md

        # Rule 1 details
        assert "### Rule: `R1` — Map population value by gender" in md
        assert "**Measure column:** `Value`" in md
        assert "**observationAbout:** `Country` = `[Country]`" in md
        assert "**observationDate:** `Year` = `[Year]`" in md
        assert "**value:** `Value` = `[Value]`" in md
        assert "**unit:** `dcid:SDG_GH`" in md
        assert "**indicator column:** `Metric`" in md
        assert "**constraints:** `Gender`" in md

        # PVMAP rows in code block
        assert "**Target PVMAP rows:**" in md
        assert "```csv" in md
        assert "Country,observationAbout,[Country]" in md
        assert "Value,value,[Value]" in md

        # Rule 2 details
        assert "### Rule: `R2` — Map amount with unit column" in md
        assert "**unit (from column):** `UnitCol`" in md

        # Rule 2 should NOT have indicator or constraints
        r2_section = md.split("### Rule: `R2`")[1]
        assert "**indicator column:**" not in r2_section
        assert "**constraints:**" not in r2_section
