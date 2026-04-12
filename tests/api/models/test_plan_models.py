"""Tests for enriched mapping plan models."""
import json

import pytest

from src.api.models.plan import (
    ColumnRelationship,
    EnrichedMappingPlan,
    MappingPlan,
    PlaceResolution,
    RelationshipType,
    StatVarBlueprint,
    TimeResolution,
    TransformationStrategy,
    ValueDictionary,
    ValueMapping,
    DatasetUnderstanding,
    ColumnMapping,
    ColumnRole,
    PropertyValueCandidate,
    CandidateSource,
    StaticProperty,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def base_mapping_plan_kwargs():
    """Minimal kwargs to construct a MappingPlan (also used by EnrichedMappingPlan)."""
    return dict(
        dataset_name="test_dataset",
        understanding=DatasetUnderstanding(
            archetype="wide",
            observation_grain="country-year",
            key_insight="GDP per country per year",
        ),
        active_columns=[
            ColumnMapping(
                column_name="country",
                role=ColumnRole.OBSERVATION_ABOUT,
                candidates=[
                    PropertyValueCandidate(
                        property="observationAbout",
                        value_expression="{country}",
                        confidence=0.95,
                        source=CandidateSource.SCHEMA_ORG,
                        reason="geographic entity",
                    )
                ],
                evidence="Country column maps to observationAbout",
            )
        ],
        ignored_columns=[],
        static_properties=[
            StaticProperty(
                property_name="populationType",
                candidates=[
                    PropertyValueCandidate(
                        property="populationType",
                        value_expression="dcs:Person",
                        confidence=0.9,
                        source=CandidateSource.LLM,
                        reason="default population type",
                    )
                ],
            )
        ],
        global_notes=["Wide-format dataset"],
    )


@pytest.fixture
def sample_statvar_blueprint():
    return StatVarBlueprint(
        base_properties={"populationType": "dcs:Person", "measuredProperty": "dcs:count"},
        constraint_columns=["age", "gender"],
        measure_columns=["value"],
    )


# ---------------------------------------------------------------------------
# RelationshipType enum
# ---------------------------------------------------------------------------

class TestRelationshipType:
    def test_all_enum_values_exist(self):
        expected = {
            "co_referent", "cross_product", "qualifier", "hierarchical",
            "value_error", "temporal", "obs_status", "independent",
        }
        actual = {e.value for e in RelationshipType}
        assert actual == expected

    def test_enum_is_str(self):
        assert isinstance(RelationshipType.CO_REFERENT, str)
        assert RelationshipType.CO_REFERENT == "co_referent"


# ---------------------------------------------------------------------------
# ColumnRelationship
# ---------------------------------------------------------------------------

class TestColumnRelationship:
    def test_creation(self):
        cr = ColumnRelationship(
            column_a="age",
            column_b="age_group",
            relationship=RelationshipType.HIERARCHICAL,
            strength=0.85,
            evidence="age_group is derived from age",
            pvmap_implication="Use age_group as constraint property",
        )
        assert cr.column_a == "age"
        assert cr.column_b == "age_group"
        assert cr.relationship == RelationshipType.HIERARCHICAL
        assert cr.strength == 0.85

    def test_strength_bounds(self):
        with pytest.raises(Exception):
            ColumnRelationship(
                column_a="a", column_b="b",
                relationship=RelationshipType.INDEPENDENT,
                strength=1.5,
                evidence="x", pvmap_implication="y",
            )
        with pytest.raises(Exception):
            ColumnRelationship(
                column_a="a", column_b="b",
                relationship=RelationshipType.INDEPENDENT,
                strength=-0.1,
                evidence="x", pvmap_implication="y",
            )


# ---------------------------------------------------------------------------
# ValueMapping
# ---------------------------------------------------------------------------

class TestValueMapping:
    def test_map_action(self):
        vm = ValueMapping(
            raw_value="Male",
            dcid="dcs:Male",
            action="MAP",
            reason="Direct mapping to DC enum",
        )
        assert vm.action == "MAP"
        assert vm.dcid == "dcs:Male"

    def test_drop_constraint_action(self):
        vm = ValueMapping(
            raw_value="Total",
            dcid=None,
            action="DROP_CONSTRAINT",
            reason="Aggregate row, remove constraint",
        )
        assert vm.action == "DROP_CONSTRAINT"
        assert vm.dcid is None


# ---------------------------------------------------------------------------
# ValueDictionary
# ---------------------------------------------------------------------------

class TestValueDictionary:
    def test_with_mappings_and_total_indicators(self):
        vd = ValueDictionary(
            column_name="gender",
            dc_property="gender",
            mappings=[
                ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="male"),
                ValueMapping(raw_value="F", dcid="dcs:Female", action="MAP", reason="female"),
                ValueMapping(raw_value="Total", dcid=None, action="DROP_CONSTRAINT", reason="agg"),
            ],
            total_indicators=["Total", "All"],
        )
        assert len(vd.mappings) == 3
        assert vd.total_indicators == ["Total", "All"]

    def test_default_total_indicators(self):
        vd = ValueDictionary(
            column_name="col",
            dc_property="prop",
            mappings=[],
        )
        assert vd.total_indicators == []


# ---------------------------------------------------------------------------
# PlaceResolution
# ---------------------------------------------------------------------------

class TestPlaceResolution:
    def test_with_pad_zeros(self):
        pr = PlaceResolution(
            column_name="fips",
            format_detected="US FIPS code",
            prefix_rule="geoId/",
            pad_zeros=5,
            resolution_rate=0.92,
        )
        assert pr.pad_zeros == 5
        assert pr.resolution_rate == 0.92

    def test_without_pad_zeros(self):
        pr = PlaceResolution(
            column_name="country",
            format_detected="ISO 3166-1 alpha-3",
            prefix_rule="country/",
            resolution_rate=0.99,
        )
        assert pr.pad_zeros is None


# ---------------------------------------------------------------------------
# TimeResolution
# ---------------------------------------------------------------------------

class TestTimeResolution:
    def test_single_column(self):
        tr = TimeResolution(
            columns=["year"],
            format_detected="YYYY",
            normalization_rule="Use as-is",
        )
        assert tr.columns == ["year"]

    def test_multiple_columns(self):
        tr = TimeResolution(
            columns=["year", "quarter"],
            format_detected="YYYY-QN",
            normalization_rule="Combine year + quarter into YYYY-QN",
        )
        assert len(tr.columns) == 2


# ---------------------------------------------------------------------------
# StatVarBlueprint
# ---------------------------------------------------------------------------

class TestStatVarBlueprint:
    def test_base_properties(self, sample_statvar_blueprint):
        bp = sample_statvar_blueprint
        assert bp.base_properties["populationType"] == "dcs:Person"
        assert bp.base_properties["measuredProperty"] == "dcs:count"
        assert bp.constraint_columns == ["age", "gender"]
        assert bp.measure_columns == ["value"]


# ---------------------------------------------------------------------------
# TransformationStrategy
# ---------------------------------------------------------------------------

class TestTransformationStrategy:
    def test_long_archetype(self):
        ts = TransformationStrategy(archetype="long")
        assert ts.archetype == "long"
        assert ts.action is None
        assert ts.id_vars == []
        assert ts.value_vars == []

    def test_wide_archetype_with_melt(self):
        ts = TransformationStrategy(
            archetype="wide",
            action="melt",
            id_vars=["country", "year"],
            value_vars=["gdp_2020", "gdp_2021"],
        )
        assert ts.action == "melt"
        assert len(ts.id_vars) == 2
        assert len(ts.value_vars) == 2


# ---------------------------------------------------------------------------
# EnrichedMappingPlan
# ---------------------------------------------------------------------------

class TestEnrichedMappingPlan:
    def test_extends_mapping_plan(self):
        assert issubclass(EnrichedMappingPlan, MappingPlan)

    def test_creation_with_all_fields(self, base_mapping_plan_kwargs, sample_statvar_blueprint):
        emp = EnrichedMappingPlan(
            **base_mapping_plan_kwargs,
            column_relationships=[
                ColumnRelationship(
                    column_a="age", column_b="age_group",
                    relationship=RelationshipType.HIERARCHICAL,
                    strength=0.85,
                    evidence="derived", pvmap_implication="use age_group",
                ),
            ],
            statvar_blueprint=sample_statvar_blueprint,
            value_dictionaries=[
                ValueDictionary(
                    column_name="gender", dc_property="gender",
                    mappings=[
                        ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="male"),
                    ],
                ),
            ],
            place_resolution=PlaceResolution(
                column_name="fips", format_detected="FIPS",
                prefix_rule="geoId/", pad_zeros=5, resolution_rate=0.95,
            ),
            time_resolution=TimeResolution(
                columns=["year"], format_detected="YYYY",
                normalization_rule="as-is",
            ),
            composite_key=["country", "year", "gender"],
            transformation_strategy=TransformationStrategy(archetype="long"),
        )
        # Base fields
        assert emp.dataset_name == "test_dataset"
        assert len(emp.active_columns) == 1
        assert len(emp.static_properties) == 1
        # New fields
        assert len(emp.column_relationships) == 1
        assert emp.statvar_blueprint.base_properties["populationType"] == "dcs:Person"
        assert len(emp.value_dictionaries) == 1
        assert emp.place_resolution.pad_zeros == 5
        assert emp.time_resolution.columns == ["year"]
        assert emp.composite_key == ["country", "year", "gender"]
        assert emp.transformation_strategy.archetype == "long"

    def test_defaults_for_optional_fields(self, base_mapping_plan_kwargs, sample_statvar_blueprint):
        emp = EnrichedMappingPlan(
            **base_mapping_plan_kwargs,
            statvar_blueprint=sample_statvar_blueprint,
        )
        assert emp.column_relationships == []
        assert emp.value_dictionaries == []
        assert emp.place_resolution is None
        assert emp.time_resolution is None
        assert emp.composite_key == []
        assert emp.transformation_strategy is None

    def test_json_roundtrip(self, base_mapping_plan_kwargs, sample_statvar_blueprint):
        emp = EnrichedMappingPlan(
            **base_mapping_plan_kwargs,
            column_relationships=[
                ColumnRelationship(
                    column_a="a", column_b="b",
                    relationship=RelationshipType.CO_REFERENT,
                    strength=0.7,
                    evidence="co-ref", pvmap_implication="merge",
                ),
            ],
            statvar_blueprint=sample_statvar_blueprint,
            value_dictionaries=[
                ValueDictionary(
                    column_name="sex", dc_property="gender",
                    mappings=[
                        ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="m"),
                    ],
                    total_indicators=["Total"],
                ),
            ],
            place_resolution=PlaceResolution(
                column_name="geo", format_detected="ISO2",
                prefix_rule="country/", resolution_rate=0.98,
            ),
            time_resolution=TimeResolution(
                columns=["year", "month"],
                format_detected="YYYY-MM",
                normalization_rule="concat",
            ),
            composite_key=["geo", "year"],
            transformation_strategy=TransformationStrategy(
                archetype="wide", action="melt",
                id_vars=["geo"], value_vars=["v1", "v2"],
            ),
        )
        # Serialize to JSON string
        json_str = emp.model_dump_json()
        data = json.loads(json_str)

        # Deserialize back
        restored = EnrichedMappingPlan.model_validate(data)

        assert restored.dataset_name == emp.dataset_name
        assert restored.column_relationships[0].relationship == RelationshipType.CO_REFERENT
        assert restored.statvar_blueprint.base_properties == emp.statvar_blueprint.base_properties
        assert restored.value_dictionaries[0].mappings[0].dcid == "dcs:Male"
        assert restored.place_resolution.resolution_rate == 0.98
        assert restored.time_resolution.columns == ["year", "month"]
        assert restored.composite_key == ["geo", "year"]
        assert restored.transformation_strategy.action == "melt"
        assert restored.transformation_strategy.value_vars == ["v1", "v2"]
