"""Pydantic schemas for LLM-as-Judge PVMAP evaluation.

Defines the structured output contract for the Gemini judge call.
The LLM produces 3 dimension scores + qualitative analysis;
overall_score is computed programmatically after the call.
"""

from pydantic import BaseModel, Field
from typing import List


class JudgeDimension(BaseModel):
    """Evaluation of a single quality dimension."""

    score: int = Field(
        description="Score from 1 to 5. 1=poor, 3=acceptable, 5=excellent",
        ge=1,
        le=5,
    )
    explanation: str = Field(
        description="2-3 sentence explanation of why this score was given"
    )
    issues: List[str] = Field(
        default_factory=list,
        description="Specific problems found in this dimension",
    )


class LLMJudgeReport(BaseModel):
    """Complete LLM judge evaluation report.

    Note: overall_score is NOT included here — it is computed
    programmatically as the simple average of the 3 dimension scores.
    """

    structural_quality: JudgeDimension = Field(
        description=(
            "Structural completeness: column coverage, required triples "
            "(observationAbout, observationDate, value), archetype identification, "
            "row count appropriateness"
        )
    )
    semantic_accuracy: JudgeDimension = Field(
        description=(
            "Semantic correctness: Data Commons property choices, schema vocabulary "
            "compliance, DCID validity, decomposed properties vs variableMeasured"
        )
    )
    value_mapping_quality: JudgeDimension = Field(
        description=(
            "Value mapping: placeholder usage ({Data}, {Number}), column reference "
            "exactness, enum value validity, unit/scaling handling"
        )
    )
    top_issues: List[str] = Field(
        description="Top 3 issues ranked by impact on PVMAP quality",
        max_length=5,
    )
    improvement_suggestions: List[str] = Field(
        description="Actionable fixes to improve the PVMAP",
        max_length=5,
    )
    summary: str = Field(
        description="2-3 sentence overall assessment of the PVMAP quality"
    )
