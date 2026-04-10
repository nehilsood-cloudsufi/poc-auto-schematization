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
