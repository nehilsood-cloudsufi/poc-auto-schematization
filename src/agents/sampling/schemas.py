"""Pydantic schemas for structured sampling agent output.

These schemas define the contracts for the two LLM calls in the
programmatic sampling pipeline:
1. SemanticAnalysis — column classification + topology detection
2. RelationalSkeleton — dependency edges + StatVar pattern
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Literal, Optional


# ---------------------------------------------------------------------------
# Step 2 Output: Semantic Analysis
# ---------------------------------------------------------------------------

class ColumnClassification(BaseModel):
    """Classification of a single column's role in the dataset."""

    column_name: str = Field(
        description="Exact column header from the dataset (case-sensitive)"
    )
    role: Literal["place", "time", "dimension", "value", "metadata"] = Field(
        description=(
            "Column role: place (observationAbout), time (observationDate), "
            "dimension (StatVar qualifier), value (measurement), "
            "metadata (ignore in PVMAP)"
        )
    )
    semantic_type: Optional[str] = Field(
        default=None,
        description=(
            "Semantic subtype for place/time columns. "
            "Place: FIPS_STATE, FIPS_COUNTY, ISO_2, ISO_3, DC_DCID, NAME. "
            "Time: YYYY, YYYY-MM, YYYY-MM-DD, YYYY-Q. "
            "Other: Currency, NAICS, SOC, or None"
        )
    )
    confidence: Literal["high", "medium", "low"] = Field(
        description="Confidence in this classification based on evidence"
    )
    reasoning: str = Field(
        description="Brief explanation of why this role was assigned"
    )


class SemanticAnalysis(BaseModel):
    """Complete semantic analysis of a dataset's columns and structure."""

    topology: Literal["TIDY_LONG", "PIVOTED_WIDE", "HYBRID"] = Field(
        description=(
            "Dataset topology: TIDY_LONG (few value cols, many dim rows), "
            "PIVOTED_WIDE (many value cols as headers), "
            "HYBRID (mixed)"
        )
    )
    topology_reasoning: str = Field(
        description="Explanation of topology classification"
    )
    columns: List[ColumnClassification] = Field(
        description="Classification for every column in the dataset"
    )
    population_type: str = Field(
        description=(
            "Data Commons population type: Person, Household, Student, "
            "Worker, Establishment, Electricity, MedicalCondition, etc."
        )
    )
    measurement_type: str = Field(
        description=(
            "Measurement type: Count, Amount, Rate, Percent, Mean, Median, "
            "Index, Ratio, etc."
        )
    )
    is_preformatted_dc: bool = Field(
        description=(
            "True if data already has variableMeasured + observationAbout + "
            "value columns with existing DCIDs"
        )
    )


# ---------------------------------------------------------------------------
# Step 3 Output: Relational Skeleton
# ---------------------------------------------------------------------------

class DependencyEdge(BaseModel):
    """A dependency relationship between two columns."""

    source: str = Field(
        description="Source column name (e.g., 'Gender')"
    )
    target: str = Field(
        description="Target column name (e.g., 'Population')"
    )
    relationship: Literal["qualifier", "hierarchy", "unit", "temporal_qualifier"] = Field(
        description=(
            "Relationship type: qualifier (dimension qualifies value), "
            "hierarchy (parent-child geo), unit (determines unit), "
            "temporal_qualifier (time-varying dimension)"
        )
    )
    dc_property: Optional[str] = Field(
        default=None,
        description=(
            "Suggested Data Commons property name "
            "(e.g., 'gender', 'age', 'race')"
        )
    )


class AggregateFlag(BaseModel):
    """Aggregate/total values detected for a dimension column."""

    column_name: str = Field(
        description="Dimension column name"
    )
    aggregate_values: List[str] = Field(
        description="List of aggregate values (e.g., ['Total', 'All'])"
    )


class RelationalSkeleton(BaseModel):
    """Relational skeleton describing how columns interact to form StatVars."""

    edges: List[DependencyEdge] = Field(
        description="Dependency edges between columns"
    )
    statvar_pattern: str = Field(
        description=(
            "StatVar naming pattern using P+M+C formula. "
            "Example: Count_Person_[Gender]_[Age]"
        )
    )
    dimension_columns: List[str] = Field(
        description="Ordered list of dimension column names"
    )
    place_column: str = Field(
        description="Column used for observationAbout (geography)"
    )
    time_column: str = Field(
        description="Column used for observationDate (time)"
    )
    value_columns: List[str] = Field(
        description="Columns containing measurement values"
    )
    aggregate_flags: List[AggregateFlag] = Field(
        default_factory=list,
        description=(
            "Aggregate/total values per dimension column. "
            "Example: [{'column_name': 'Gender', 'aggregate_values': ['Total']}]"
        )
    )

    def get_aggregate_flags_dict(self) -> Dict[str, List[str]]:
        """Convert aggregate_flags list to dict for backward compatibility."""
        return {f.column_name: f.aggregate_values for f in self.aggregate_flags}
