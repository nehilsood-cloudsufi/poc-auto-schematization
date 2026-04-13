"""Pydantic models for the structured mapping plan."""
from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class CandidateSource(str, Enum):
    SCHEMA_ORG = "from Schema.org"
    MCP = "from MCP"
    SCHEMA_VOCAB = "from schema_vocab"
    LLM = "LLM suggestion"
    USER_OVERRIDE = "user override"


class ColumnRole(str, Enum):
    OBSERVATION_ABOUT = "observationAbout"
    OBSERVATION_DATE = "observationDate"
    MEASURE = "measure"
    DIMENSION = "dimension"
    METADATA = "metadata"
    IGNORED = "ignored"


class CandidateValidation(BaseModel):
    """DC API validation results for a candidate."""
    property_exists: bool = False
    place_resolution_rate: Optional[float] = None
    existing_statvar: Optional[str] = None
    notes: str = ""


class PropertyValueCandidate(BaseModel):
    """One possible mapping for a column or static property."""
    property: str
    value_expression: str
    confidence: float = Field(ge=0.0, le=1.0)
    source: CandidateSource
    reason: str
    validation: Optional[CandidateValidation] = None


class ColumnMapping(BaseModel):
    """Plan for a single column."""
    column_name: str
    role: ColumnRole
    candidates: list[PropertyValueCandidate]
    selected_index: int = 0
    evidence: str
    dc_match: Optional[str] = None
    is_ambiguous: bool = False


class StaticProperty(BaseModel):
    """A global property like populationType, unit, etc."""
    property_name: str
    candidates: list[PropertyValueCandidate]
    selected_index: int = 0


class DatasetUnderstanding(BaseModel):
    """High-level dataset classification."""
    archetype: str
    observation_grain: str
    key_insight: str


class MappingPlan(BaseModel):
    """The complete structured plan."""
    dataset_name: str
    understanding: DatasetUnderstanding
    active_columns: list[ColumnMapping]
    ignored_columns: list[ColumnMapping]
    static_properties: list[StaticProperty]
    global_notes: list[str]
    engineer_notes: list[str] = Field(default_factory=list)


class RelationshipType(str, Enum):
    CO_REFERENT = "co_referent"
    CROSS_PRODUCT = "cross_product"
    QUALIFIER = "qualifier"
    HIERARCHICAL = "hierarchical"
    VALUE_ERROR_BOUND = "value_error"
    TEMPORAL_COMPOSITION = "temporal"
    OBSERVATION_STATUS = "obs_status"
    INDEPENDENT = "independent"


class ColumnRelationship(BaseModel):
    """Pairwise relationship between two columns (the 'attention matrix')."""
    column_a: str
    column_b: str
    relationship: RelationshipType
    strength: float = Field(ge=0.0, le=1.0)
    evidence: str
    pvmap_implication: str


class ValueMapping(BaseModel):
    """Single raw-value to DCID mapping."""
    raw_value: str
    dcid: Optional[str] = None
    action: str  # "MAP", "DROP_CONSTRAINT", "DROP_ROW"
    reason: str


class ValueDictionary(BaseModel):
    """Per-column dimension value mappings."""
    column_name: str
    dc_property: str
    mappings: list[ValueMapping]
    total_indicators: list[str] = Field(default_factory=list)


class PlaceResolution(BaseModel):
    """Detected geographic format and resolution rules."""
    column_name: str
    format_detected: str
    prefix_rule: str
    pad_zeros: Optional[int] = None
    resolution_rate: float = Field(ge=0.0, le=1.0)


class TimeResolution(BaseModel):
    """Detected temporal format and normalization rules."""
    columns: list[str]
    format_detected: str
    normalization_rule: str


class StatVarProperty(BaseModel):
    """A single base property for the StatVar blueprint."""
    name: str
    value: str


class StatVarBlueprint(BaseModel):
    """Base StatVar definition and how dimensions modify it."""
    base_properties: list[StatVarProperty]
    constraint_columns: list[str]
    measure_columns: list[str]


class TransformationStrategy(BaseModel):
    """Dataset archetype and required structural transformations."""
    archetype: str
    action: Optional[str] = None
    id_vars: list[str] = Field(default_factory=list)
    value_vars: list[str] = Field(default_factory=list)


class IndicatorValueMapping(BaseModel):
    """Maps a single indicator value to StatVar properties."""
    raw_value: str
    population_type: str
    measured_property: str
    stat_type: str
    extra_properties: list[StatVarProperty] = Field(default_factory=list)
    reason: str


class IndicatorColumn(BaseModel):
    """Column whose distinct values each define a different StatVar."""
    column_name: str
    value_mappings: list[IndicatorValueMapping]


class ObservationTemplate(BaseModel):
    """How to extract the observation triple (about, date, value)."""
    about_column: str
    about_expression: str
    date_column: str
    date_expression: str
    value_column: str
    value_expression: str
    unit: Optional[str] = None
    unit_column: Optional[str] = None


class MappingRule(BaseModel):
    """One logical mapping rule that produces a set of PVMAP rows."""
    rule_id: str
    measure_column: str
    description: str
    observation: ObservationTemplate
    indicator_column: Optional[str] = None
    constraint_columns: list[str] = Field(default_factory=list)
    static_properties: list[StatVarProperty] = Field(default_factory=list)
    pvmap_rows: list[str] = Field(default_factory=list)


class EnrichedMappingPlan(MappingPlan):
    """MappingPlan extended with Phase A analysis + Phase B reasoning."""
    column_relationships: list[ColumnRelationship] = Field(default_factory=list)
    statvar_blueprint: StatVarBlueprint
    value_dictionaries: list[ValueDictionary] = Field(default_factory=list)
    place_resolution: Optional[PlaceResolution] = None
    time_resolution: Optional[TimeResolution] = None
    composite_key: list[str] = Field(default_factory=list)
    transformation_strategy: Optional[TransformationStrategy] = None
    indicator_columns: list[IndicatorColumn] = Field(default_factory=list)
    mapping_rules: list[MappingRule] = Field(default_factory=list)
