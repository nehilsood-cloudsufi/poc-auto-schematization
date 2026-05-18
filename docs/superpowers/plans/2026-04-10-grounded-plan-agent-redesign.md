# Grounded Plan Agent Redesign — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the freeform LLM-generated mapping plan with a retrieve-then-rank pipeline that grounds every property-value candidate in Schema.org, MCP, or schema vocabulary, and makes the plan binding on PVMAP generation.

**Architecture:** Three new components: CandidateRetriever (programmatic grounding per column), MappingPlanAgent v2 (LLM ranks candidates via Gemini structured output), PlanValidator (DC API validation). The approved plan is converted to a partial PVMAP CSV skeleton that constrains the generator. Frontend renders structured JSON as an interactive form with selectable options.

**Tech Stack:** Python/Pydantic (backend models), Gemini structured output (response_schema), FastAPI (API), React/TypeScript (frontend), DC REST API (validation)

**Spec:** `docs/superpowers/specs/2026-04-10-grounded-plan-agent-redesign.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `src/api/models/plan.py` | Pydantic data models (MappingPlan, ColumnMapping, etc.) |
| `src/pipeline/plan/__init__.py` | Package init |
| `src/pipeline/plan/candidate_retriever.py` | Per-column grounding from Schema.org + MCP + schema_vocab |
| `src/pipeline/plan/plan_validator.py` | DC API validation of candidates |
| `src/pipeline/plan/skeleton_converter.py` | Approved plan -> partial PVMAP CSV |
| `tests/api/test_plan_models.py` | Pydantic model tests |
| `tests/pipeline/plan/__init__.py` | Package init |
| `tests/pipeline/plan/test_candidate_retriever.py` | Retriever tests |
| `tests/pipeline/plan/test_plan_validator.py` | Validator tests |
| `tests/pipeline/plan/test_skeleton_converter.py` | Converter tests |
| `frontend/src/components/PlanReview/ActiveMappingsTable.tsx` | Table of active column mappings |
| `frontend/src/components/PlanReview/ColumnDetail.tsx` | Expandable detail panel with options |
| `frontend/src/components/PlanReview/StaticProperties.tsx` | Static property selection |
| `frontend/src/components/PlanReview/IgnoredColumns.tsx` | Collapsed list of ignored columns |

### Modified Files
| File | Change |
|------|--------|
| `src/agents/mapping_plan_agent.py` | Replace with v2 (structured output, ranker) |
| `src/resources/prompts/mapping_plan_prompt.txt` | New prompt (rank candidates) |
| `src/run_pipeline.py:494-505` | Wire CandidateRetriever + PlanValidator |
| `src/api/routes/plan.py` | Add GET /plan, POST /plan/approve endpoints |
| `src/api/services/pipeline_runner.py:111-136` | Save structured plan JSON in phase1_state |
| `frontend/src/pages/ReviewPlanPage.tsx` | Replace markdown dump with interactive form |
| `frontend/src/types/index.ts` | Add MappingPlan TypeScript types |
| `frontend/src/lib/api.ts` | Add getPlan(), approvePlan() functions |

---

## Phase 1: Backend Restructure

### Task 1: Pydantic Data Models

**Files:**
- Create: `src/api/models/plan.py`
- Create: `tests/api/test_plan_models.py`

- [ ] **Step 1: Write failing tests for plan models**

Create `tests/api/test_plan_models.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_plan_models.py -x -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'src.api.models.plan'`

- [ ] **Step 3: Implement Pydantic models**

Create `src/api/models/plan.py`:

```python
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_plan_models.py -x -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/api/models/plan.py tests/api/test_plan_models.py
git commit -m "feat(plan): add Pydantic data models for structured mapping plan"
```

---

### Task 2: CandidateRetriever — Schema.org + Schema Vocab Sources

**Files:**
- Create: `src/pipeline/plan/__init__.py`
- Create: `src/pipeline/plan/candidate_retriever.py`
- Create: `tests/pipeline/plan/__init__.py`
- Create: `tests/pipeline/plan/test_candidate_retriever.py`

- [ ] **Step 1: Write failing tests for CandidateRetriever (local sources)**

Create `tests/pipeline/plan/__init__.py` (empty).

Create `tests/pipeline/plan/test_candidate_retriever.py`:

```python
"""Tests for CandidateRetriever — local sources (Schema.org + schema_vocab)."""
import pytest
from unittest.mock import MagicMock, patch

from src.api.models.plan import CandidateSource, ColumnRole
from src.pipeline.plan.candidate_retriever import CandidateRetriever


@pytest.fixture
def retriever():
    return CandidateRetriever()


class TestRoleAssignment:
    """Role heuristics based on column profiles."""

    def test_place_column(self, retriever):
        col = {"name": "REF_AREA", "semantic_type": "place", "dtype": "String", "cardinality": 50, "cardinality_ratio": 0.1, "sample_values": ["GB", "AR"]}
        role = retriever._assign_role(col)
        assert role == ColumnRole.OBSERVATION_ABOUT

    def test_date_column(self, retriever):
        col = {"name": "TIME_PERIOD", "semantic_type": "date", "dtype": "Date", "cardinality": 100, "cardinality_ratio": 0.5, "sample_values": ["2020-01", "2021-06"]}
        role = retriever._assign_role(col)
        assert role == ColumnRole.OBSERVATION_DATE

    def test_numeric_measure(self, retriever):
        col = {"name": "OBS_VALUE", "semantic_type": None, "dtype": "Float", "cardinality": 500, "cardinality_ratio": 0.8, "sample_values": ["1.5", "3.2"]}
        role = retriever._assign_role(col)
        assert role == ColumnRole.MEASURE

    def test_constant_ignored(self, retriever):
        col = {"name": "STRUCTURE", "semantic_type": None, "dtype": "String", "cardinality": 1, "cardinality_ratio": 0.001, "sample_values": ["dataflow"]}
        role = retriever._assign_role(col)
        assert role == ColumnRole.IGNORED

    def test_empty_ignored(self, retriever):
        col = {"name": "EMPTY_COL", "semantic_type": None, "dtype": "Empty", "cardinality": 0, "cardinality_ratio": 0.0, "sample_values": []}
        role = retriever._assign_role(col)
        assert role == ColumnRole.IGNORED

    def test_string_dimension(self, retriever):
        col = {"name": "FREQ", "semantic_type": None, "dtype": "String", "cardinality": 3, "cardinality_ratio": 0.05, "sample_values": ["Monthly", "Daily"]}
        role = retriever._assign_role(col)
        assert role == ColumnRole.DIMENSION


class TestSchemaOrgCandidates:
    """Schema.org local vocabulary lookup."""

    def test_place_candidates(self, retriever):
        col = {"name": "REF_AREA", "semantic_type": "place"}
        candidates = retriever._get_schemaorg_candidates(col)
        props = [c.property for c in candidates]
        assert "observationAbout" in props
        for c in candidates:
            assert c.source == CandidateSource.SCHEMA_ORG

    def test_date_candidates(self, retriever):
        col = {"name": "TIME_PERIOD", "semantic_type": "date"}
        candidates = retriever._get_schemaorg_candidates(col)
        props = [c.property for c in candidates]
        assert "observationDate" in props

    def test_measure_candidates(self, retriever):
        col = {"name": "OBS_VALUE", "semantic_type": "measure"}
        candidates = retriever._get_schemaorg_candidates(col)
        props = [c.property for c in candidates]
        assert "value" in props

    def test_unknown_returns_search_results(self, retriever):
        col = {"name": "COMPILATION", "semantic_type": None}
        candidates = retriever._get_schemaorg_candidates(col)
        # May return 0 if no match — that's fine
        for c in candidates:
            assert c.source == CandidateSource.SCHEMA_ORG


class TestSchemaVocabCandidates:
    """Schema vocabulary lookup."""

    def test_with_vocab(self, retriever):
        vocab_json = '{"properties": ["observationAbout", "observationDate", "value", "observationPeriod", "measuredProperty"]}'
        col = {"name": "FREQ", "semantic_type": None, "role": ColumnRole.DIMENSION}
        candidates = retriever._get_vocab_candidates(col, vocab_json)
        for c in candidates:
            assert c.source == CandidateSource.SCHEMA_VOCAB

    def test_empty_vocab(self, retriever):
        candidates = retriever._get_vocab_candidates({"name": "X"}, "")
        assert candidates == []


class TestMergeCandidates:
    """Merge + dedup logic when same property from multiple sources."""

    def test_same_property_merged(self, retriever):
        from src.api.models.plan import PropertyValueCandidate
        c1 = PropertyValueCandidate(
            property="observationAbout", value_expression="[DATA]",
            confidence=0.8, source=CandidateSource.SCHEMA_ORG, reason="place type"
        )
        c2 = PropertyValueCandidate(
            property="observationAbout", value_expression="country/[DATA]",
            confidence=0.95, source=CandidateSource.MCP, reason="matches StatVar pattern"
        )
        merged = retriever._merge_candidates([c1, c2])
        assert len(merged) == 1
        assert merged[0].confidence == 0.95  # max
        assert merged[0].value_expression == "country/[DATA]"  # more specific

    def test_different_properties_not_merged(self, retriever):
        from src.api.models.plan import PropertyValueCandidate
        c1 = PropertyValueCandidate(
            property="observationAbout", value_expression="[DATA]",
            confidence=0.9, source=CandidateSource.SCHEMA_ORG, reason="place type"
        )
        c2 = PropertyValueCandidate(
            property="geoId", value_expression="[DATA]",
            confidence=0.7, source=CandidateSource.MCP, reason="from StatVar"
        )
        merged = retriever._merge_candidates([c1, c2])
        assert len(merged) == 2

    def test_sorted_by_confidence_desc(self, retriever):
        from src.api.models.plan import PropertyValueCandidate
        c1 = PropertyValueCandidate(
            property="a", value_expression="[DATA]",
            confidence=0.5, source=CandidateSource.SCHEMA_ORG, reason="low"
        )
        c2 = PropertyValueCandidate(
            property="b", value_expression="[DATA]",
            confidence=0.9, source=CandidateSource.MCP, reason="high"
        )
        merged = retriever._merge_candidates([c1, c2])
        assert merged[0].confidence >= merged[1].confidence
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_candidate_retriever.py -x -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement CandidateRetriever (local sources)**

Create `src/pipeline/plan/__init__.py` (empty).

Create `src/pipeline/plan/candidate_retriever.py`:

```python
"""CandidateRetriever — gathers grounding data per column from Schema.org, MCP, and schema vocab.

This is a purely programmatic component (no LLM). It runs BEFORE the plan agent
and produces a CandidatePool per column for the LLM to rank.
"""
from __future__ import annotations

import json
import logging
from typing import Optional

from src.api.models.plan import (
    CandidateSource,
    ColumnRole,
    PropertyValueCandidate,
)

logger = logging.getLogger(__name__)

# Semantic type -> DC property mapping (hardcoded, same as SchemaOrgEnrichmentAgent)
_SEMANTIC_ROLE_MAP = {
    "place": ColumnRole.OBSERVATION_ABOUT,
    "date": ColumnRole.OBSERVATION_DATE,
    "measure": ColumnRole.MEASURE,
}

_SEMANTIC_PROPERTY_MAP = {
    "place": [
        PropertyValueCandidate(
            property="observationAbout", value_expression="country/[DATA]",
            confidence=0.90, source=CandidateSource.SCHEMA_ORG,
            reason="place semantic type maps to observationAbout (from Observation.about)",
        ),
    ],
    "date": [
        PropertyValueCandidate(
            property="observationDate", value_expression="[DATA]",
            confidence=0.92, source=CandidateSource.SCHEMA_ORG,
            reason="date semantic type maps to observationDate",
        ),
    ],
    "measure": [
        PropertyValueCandidate(
            property="value", value_expression="[NUMBER]",
            confidence=0.93, source=CandidateSource.SCHEMA_ORG,
            reason="numeric measure maps to value (from QuantitativeValue)",
        ),
    ],
}


class CandidateRetriever:
    """Gathers grounding candidates per column from local + remote sources."""

    def _assign_role(self, col: dict) -> ColumnRole:
        """Assign a column role based on heuristics."""
        sem = col.get("semantic_type")
        if sem in _SEMANTIC_ROLE_MAP:
            return _SEMANTIC_ROLE_MAP[sem]

        dtype = col.get("dtype", "")
        cardinality = col.get("cardinality", 0)

        if cardinality == 0 or dtype == "Empty":
            return ColumnRole.IGNORED
        if cardinality == 1:
            return ColumnRole.IGNORED
        if dtype in ("Float", "Integer") and col.get("cardinality_ratio", 0) > 0.3:
            return ColumnRole.MEASURE

        return ColumnRole.DIMENSION

    def _get_schemaorg_candidates(self, col: dict) -> list[PropertyValueCandidate]:
        """Look up candidates from local Schema.org vocabulary."""
        sem = col.get("semantic_type")
        if sem in _SEMANTIC_PROPERTY_MAP:
            return [c.model_copy() for c in _SEMANTIC_PROPERTY_MAP[sem]]

        # For unknown semantic types, search by column name
        try:
            from src.data_commons.schema.schemaorg_vocab import SchemaOrgVocab
            vocab = SchemaOrgVocab.instance()
            results = vocab.search_properties(col["name"], limit=3)
            candidates = []
            for r in results:
                candidates.append(PropertyValueCandidate(
                    property=r.get("name", r.get("id", "")),
                    value_expression="[DATA]",
                    confidence=0.50,
                    source=CandidateSource.SCHEMA_ORG,
                    reason=f"Schema.org search match: {r.get('description', '')[:80]}",
                ))
            return candidates
        except Exception as e:
            logger.warning("Schema.org lookup failed for %s: %s", col["name"], e)
            return []

    def _get_vocab_candidates(self, col: dict, schema_vocab: str) -> list[PropertyValueCandidate]:
        """Look up candidates from the selected schema category vocabulary."""
        if not schema_vocab:
            return []

        try:
            vocab = json.loads(schema_vocab) if isinstance(schema_vocab, str) else schema_vocab
            properties = vocab.get("properties", [])
            if not properties:
                return []

            # Simple fuzzy match: check if column name words appear in property names
            col_words = set(col["name"].lower().replace("_", " ").replace(":", " ").split())
            candidates = []
            for prop in properties:
                prop_lower = prop.lower()
                overlap = sum(1 for w in col_words if w in prop_lower)
                if overlap > 0:
                    candidates.append(PropertyValueCandidate(
                        property=prop,
                        value_expression="[DATA]",
                        confidence=min(0.4 + overlap * 0.15, 0.80),
                        source=CandidateSource.SCHEMA_VOCAB,
                        reason=f"schema vocab property match ({overlap} word overlap)",
                    ))
            return sorted(candidates, key=lambda c: c.confidence, reverse=True)[:3]
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning("Schema vocab parse failed: %s", e)
            return []

    def _merge_candidates(self, candidates: list[PropertyValueCandidate]) -> list[PropertyValueCandidate]:
        """Merge candidates with the same property. Keep highest confidence + most specific value_expression."""
        by_prop: dict[str, PropertyValueCandidate] = {}
        for c in candidates:
            existing = by_prop.get(c.property)
            if existing is None:
                by_prop[c.property] = c.model_copy()
            else:
                # Merge: max confidence, most specific value_expression, combined sources
                if c.confidence > existing.confidence:
                    existing.confidence = c.confidence
                if len(c.value_expression) > len(existing.value_expression):
                    existing.value_expression = c.value_expression
                if c.source.value not in existing.source.value:
                    existing.reason = f"{existing.reason}; {c.reason}"

        return sorted(by_prop.values(), key=lambda c: c.confidence, reverse=True)

    def retrieve_for_column(
        self,
        col: dict,
        schema_vocab: str = "",
    ) -> tuple[ColumnRole, list[PropertyValueCandidate], str]:
        """Retrieve candidates for a single column from local sources.

        Returns (role, candidates, evidence_str).
        """
        role = self._assign_role(col)

        all_candidates = []
        all_candidates.extend(self._get_schemaorg_candidates(col))
        all_candidates.extend(self._get_vocab_candidates(col, schema_vocab))

        merged = self._merge_candidates(all_candidates)
        evidence = f"{col.get('cardinality', '?')} unique, {col.get('dtype', '?')}, samples: {', '.join(col.get('sample_values', [])[:3])}"

        return role, merged, evidence

    def retrieve_all(
        self,
        columns: list[dict],
        schema_vocab: str = "",
    ) -> dict[str, tuple[ColumnRole, list[PropertyValueCandidate], str]]:
        """Retrieve candidates for all columns. Returns {col_name: (role, candidates, evidence)}."""
        results = {}
        for col in columns:
            role, candidates, evidence = self.retrieve_for_column(col, schema_vocab)
            results[col["name"]] = (role, candidates, evidence)
            logger.info("Retrieved %d candidates for %s (role=%s)", len(candidates), col["name"], role.value)
        return results
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_candidate_retriever.py -x -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/plan/ tests/pipeline/plan/
git commit -m "feat(plan): add CandidateRetriever with Schema.org + schema_vocab sources"
```

---

### Task 3: PlanValidator — DC API Validation

**Files:**
- Create: `src/pipeline/plan/plan_validator.py`
- Create: `tests/pipeline/plan/test_plan_validator.py`

- [ ] **Step 1: Write failing tests for PlanValidator**

Create `tests/pipeline/plan/test_plan_validator.py`:

```python
"""Tests for PlanValidator — DC API validation of candidates."""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from src.api.models.plan import (
    CandidateSource,
    ColumnMapping,
    ColumnRole,
    MappingPlan,
    DatasetUnderstanding,
    PropertyValueCandidate,
    StaticProperty,
)
from src.pipeline.plan.plan_validator import PlanValidator


def _make_plan():
    return MappingPlan(
        dataset_name="test",
        understanding=DatasetUnderstanding(
            archetype="Flat", observation_grain="one row per entity per date", key_insight="test data"
        ),
        active_columns=[
            ColumnMapping(
                column_name="REF_AREA",
                role=ColumnRole.OBSERVATION_ABOUT,
                candidates=[
                    PropertyValueCandidate(
                        property="observationAbout", value_expression="country/[DATA]",
                        confidence=0.9, source=CandidateSource.SCHEMA_ORG, reason="place"
                    ),
                    PropertyValueCandidate(
                        property="fakeProperty", value_expression="[DATA]",
                        confidence=0.5, source=CandidateSource.LLM, reason="guess"
                    ),
                ],
                evidence="2 unique",
            )
        ],
        ignored_columns=[],
        static_properties=[
            StaticProperty(
                property_name="populationType",
                candidates=[PropertyValueCandidate(
                    property="populationType", value_expression="InterestRate",
                    confidence=0.9, source=CandidateSource.MCP, reason="from DC"
                )],
            )
        ],
        global_notes=[],
    )


class TestPropertyExistence:
    @pytest.mark.asyncio
    async def test_valid_property_marked_true(self):
        validator = PlanValidator()
        # Mock the DC API call
        with patch.object(validator, "_check_property_exists", new_callable=AsyncMock, return_value=True):
            result = await validator._validate_candidate(
                PropertyValueCandidate(
                    property="observationAbout", value_expression="[DATA]",
                    confidence=0.9, source=CandidateSource.SCHEMA_ORG, reason="test"
                )
            )
            assert result.property_exists is True

    @pytest.mark.asyncio
    async def test_invalid_property_marked_false(self):
        validator = PlanValidator()
        with patch.object(validator, "_check_property_exists", new_callable=AsyncMock, return_value=False):
            result = await validator._validate_candidate(
                PropertyValueCandidate(
                    property="fakeProperty", value_expression="[DATA]",
                    confidence=0.5, source=CandidateSource.LLM, reason="guess"
                )
            )
            assert result.property_exists is False


class TestPlanValidation:
    @pytest.mark.asyncio
    async def test_validate_plan_populates_validation_field(self):
        validator = PlanValidator()
        plan = _make_plan()
        # Mock all DC API calls
        with patch.object(validator, "_check_property_exists", new_callable=AsyncMock, return_value=True):
            validated = await validator.validate(plan)
            for col in validated.active_columns:
                for c in col.candidates:
                    assert c.validation is not None
                    assert c.validation.property_exists is True

    @pytest.mark.asyncio
    async def test_api_failure_degrades_gracefully(self):
        validator = PlanValidator()
        plan = _make_plan()
        with patch.object(validator, "_check_property_exists", new_callable=AsyncMock, side_effect=Exception("API down")):
            validated = await validator.validate(plan)
            # Should not raise — validation is best-effort
            for col in validated.active_columns:
                for c in col.candidates:
                    assert c.validation is not None
                    assert "error" in c.validation.notes.lower() or c.validation.notes == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_validator.py -x -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement PlanValidator**

Create `src/pipeline/plan/plan_validator.py`:

```python
"""PlanValidator — validates candidate property-value pairs against the live DC API.

Runs after MappingPlanAgent v2, before serving plan to the UI.
Validation is best-effort: if DC API is down, plan still works (validation=None).
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

import httpx

from src.api.models.plan import (
    CandidateValidation,
    MappingPlan,
    PropertyValueCandidate,
)

logger = logging.getLogger(__name__)

DC_API_BASE = "https://api.datacommons.org/v2"

# Cache property existence checks (property name -> bool)
_property_cache: dict[str, bool] = {}


class PlanValidator:
    """Validates plan candidates against the live Data Commons API."""

    def __init__(self, timeout: float = 5.0):
        self._timeout = timeout

    async def _check_property_exists(self, property_name: str) -> bool:
        """Check if a DC property exists via the API. Results are cached."""
        if property_name in _property_cache:
            return _property_cache[property_name]

        # Well-known DC properties that always exist
        well_known = {
            "observationAbout", "observationDate", "value", "variableMeasured",
            "observationPeriod", "measuredProperty", "populationType", "statType",
            "unit", "measurementQualifier", "measurementDenominator", "scalingFactor",
            "geoId", "containedInPlace",
        }
        if property_name in well_known:
            _property_cache[property_name] = True
            return True

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                resp = await client.get(
                    f"{DC_API_BASE}/node",
                    params={"nodes": f"dcid:{property_name}", "property": "->*"},
                )
                exists = resp.status_code == 200 and bool(resp.json().get("data", {}))
                _property_cache[property_name] = exists
                return exists
        except Exception as e:
            logger.warning("DC API check failed for %s: %s", property_name, e)
            return False  # Assume exists on failure (best-effort)

    async def _validate_candidate(self, candidate: PropertyValueCandidate) -> CandidateValidation:
        """Validate a single candidate."""
        try:
            exists = await self._check_property_exists(candidate.property)
            return CandidateValidation(
                property_exists=exists,
                notes="Property verified in DC" if exists else "Property not found in DC",
            )
        except Exception as e:
            return CandidateValidation(
                property_exists=False,
                notes=f"Validation error: {e}",
            )

    async def validate(self, plan: MappingPlan) -> MappingPlan:
        """Validate all candidates in the plan. Returns the plan with validation fields populated."""
        all_candidates = []
        for col in plan.active_columns:
            all_candidates.extend(col.candidates)
        for sp in plan.static_properties:
            all_candidates.extend(sp.candidates)

        # Run all validations in parallel
        tasks = [self._validate_candidate(c) for c in all_candidates]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Assign validation results back to candidates
        idx = 0
        for col in plan.active_columns:
            for c in col.candidates:
                r = results[idx]
                c.validation = r if isinstance(r, CandidateValidation) else CandidateValidation(
                    notes=f"Validation error: {r}"
                )
                idx += 1
        for sp in plan.static_properties:
            for c in sp.candidates:
                r = results[idx]
                c.validation = r if isinstance(r, CandidateValidation) else CandidateValidation(
                    notes=f"Validation error: {r}"
                )
                idx += 1

        return plan
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_validator.py -x -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/plan/plan_validator.py tests/pipeline/plan/test_plan_validator.py
git commit -m "feat(plan): add PlanValidator for DC API validation of candidates"
```

---

### Task 4: MappingPlanAgent v2 — Structured Output Ranker

**Files:**
- Modify: `src/agents/mapping_plan_agent.py`
- Modify: `src/resources/prompts/mapping_plan_prompt.txt`

- [ ] **Step 1: Write the new prompt template**

Replace `src/resources/prompts/mapping_plan_prompt.txt` with:

```text
You are a Data Commons expert analyst. Your job: RANK and REFINE pre-retrieved candidate property-value mappings for each column. You do NOT invent mappings from scratch — candidates have already been retrieved from Schema.org, MCP, and schema vocabulary.

## Your Task

For each column:
1. RANK the provided candidates by relevance (reorder if retrieval got priorities wrong)
2. Assign a confidence score (0.0-1.0) based on DATA EVIDENCE (cardinality, type, samples)
3. Confirm or adjust the proposed role (observationAbout, observationDate, measure, dimension, ignored)
4. If NO candidate fits, propose ONE novel mapping with source "LLM suggestion"

For static properties (populationType, measuredProperty, statType, unit):
- Propose top-3 options ranked by relevance

You MUST NOT invent property names that don't appear in the candidates or schema vocabulary.
You MUST base confidence scores on data evidence, not guesses.

## Dataset Columns

{skeleton_summary}

## Sampled Data

{sampled_data}

## Pre-Retrieved Candidates (per column)

{candidate_pool_json}

## Schema Vocabulary (valid property names)

{schema_vocab_content}

## Data Commons Discovery Results

{statvar_summary}

## Output

Return a JSON object matching the MappingPlan schema exactly. Include:
- dataset_name: the dataset identifier
- understanding: archetype (Wide/Flat/Dimension-Row), observation_grain, key_insight
- active_columns: columns with actual mappings (observationAbout, observationDate, measure, dimension)
- ignored_columns: columns to skip (constant values, empty, metadata)
- static_properties: populationType, measuredProperty, statType, unit with ranked candidates
- global_notes: warnings, edge cases, ambiguities

## IMPORTANT RULES
- Analyze EVERY column — do not skip any
- Use EXACT column names (copy from the candidates section)
- Use [DATA] and [NUMBER] for placeholder expressions (NOT curly-brace variants)
- Cross-column reasoning: only ONE column should be observationAbout, only ONE should be observationDate
- If a column is genuinely ambiguous, set is_ambiguous=true
```

- [ ] **Step 2: Rewrite MappingPlanAgent to use structured output**

Replace `src/agents/mapping_plan_agent.py`:

```python
"""MappingPlanAgent v2 — ranks pre-retrieved candidates via Gemini structured output.

Runs after CandidateRetriever. Receives candidate pools per column and uses the LLM
to rank, adjust confidence scores, assign roles, and propose static properties.

ADK State Inputs:
    - skeleton_summary: str
    - schema_vocab_content: str
    - sampled_data: str
    - statvar_summary: str
    - candidate_pool: str (JSON of per-column candidates from CandidateRetriever)
    - output_dir: str
    - dataset_name: str

ADK State Outputs:
    - mapping_plan: str (JSON of MappingPlan)
    - mapping_plan_json: str (same, for API serving)
"""
import json
import logging
import os
from pathlib import Path
from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types
from google import genai

from src.api.models.plan import MappingPlan

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()


def _plan_to_markdown(plan: MappingPlan) -> str:
    """Convert structured plan to human-readable markdown for logs."""
    lines = [f"# Mapping Plan: {plan.dataset_name}", ""]
    lines.append("## Dataset Understanding")
    lines.append(f"- **Format:** {plan.understanding.archetype}")
    lines.append(f"- **Observation grain:** {plan.understanding.observation_grain}")
    lines.append(f"- **Key insight:** {plan.understanding.key_insight}")
    lines.append("")

    lines.append("## Active Column Mappings")
    for col in plan.active_columns:
        selected = col.candidates[col.selected_index] if col.candidates else None
        lines.append(f"### Column: `{col.column_name}`")
        lines.append(f"- **Role:** {col.role.value}")
        if selected:
            lines.append(f"- **Mapping:** `{selected.property}` -> `{selected.value_expression}`")
            lines.append(f"- **Confidence:** {selected.confidence:.0%} ({selected.source.value})")
        lines.append(f"- **Evidence:** {col.evidence}")
        if col.dc_match:
            lines.append(f"- **DC Match:** {col.dc_match}")
        if col.is_ambiguous:
            lines.append("- **WARNING:** Ambiguous — human review recommended")
        if len(col.candidates) > 1:
            lines.append("- **Alternatives:**")
            for i, c in enumerate(col.candidates):
                if i == col.selected_index:
                    continue
                lines.append(f"  - {c.property} -> {c.value_expression} ({c.confidence:.0%}, {c.source.value})")
        lines.append("")

    lines.append("## Static Properties")
    for sp in plan.static_properties:
        selected = sp.candidates[sp.selected_index] if sp.candidates else None
        if selected:
            lines.append(f"- **{sp.property_name}:** `{selected.value_expression}` ({selected.confidence:.0%})")
    lines.append("")

    lines.append("## Ignored Columns")
    for col in plan.ignored_columns:
        lines.append(f"- `{col.column_name}` — {col.evidence}")
    lines.append("")

    if plan.global_notes:
        lines.append("## Global Notes")
        for note in plan.global_notes:
            lines.append(f"- {note}")

    return "\n".join(lines)


class MappingPlanAgent(BaseAgent):
    """Ranks pre-retrieved candidates via Gemini structured output."""

    def __init__(self, name: str = "MappingPlanAgent", model: str = None):
        super().__init__(name=name)
        self._model_name = model or os.getenv("MAPPING_PLAN_MODEL", "gemini-3.1-pro-preview")

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text="Generating structured mapping plan...")]
        ))

        # Load prompt template
        template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt.txt"
        template = template_path.read_text()

        # Populate template from state
        populated = template.replace("{skeleton_summary}", ctx.session.state.get("skeleton_summary", ""))
        populated = populated.replace("{schema_vocab_content}", ctx.session.state.get("schema_vocab_content", ""))
        populated = populated.replace("{sampled_data}", ctx.session.state.get("sampled_data", ""))
        populated = populated.replace("{statvar_summary}", ctx.session.state.get("statvar_summary", ""))
        populated = populated.replace("{candidate_pool_json}", ctx.session.state.get("candidate_pool", "{}"))

        # Generate plan via Gemini structured output
        plan = await self._generate_plan(populated)

        # Save to state as JSON
        plan_json = plan.model_dump_json(indent=2)
        ctx.session.state["mapping_plan"] = plan_json
        ctx.session.state["mapping_plan_json"] = plan_json

        # Save to disk: JSON (source of truth) + markdown (for logs)
        output_dir = Path(ctx.session.state.get("output_dir", "."))
        output_dir.mkdir(parents=True, exist_ok=True)

        (output_dir / "mapping_plan.json").write_text(plan_json)
        (output_dir / "mapping_plan.md").write_text(_plan_to_markdown(plan))

        dataset_name = ctx.session.state.get("dataset_name", "unknown")
        logger.info("Structured plan generated for %s (%d active, %d ignored columns)",
                    dataset_name, len(plan.active_columns), len(plan.ignored_columns))

        yield Event(author=self.name, content=types.Content(
            parts=[types.Part(text=f"Mapping plan generated ({len(plan.active_columns)} active, {len(plan.ignored_columns)} ignored columns)")]
        ))

    async def _generate_plan(self, prompt: str) -> MappingPlan:
        """Call Gemini with structured output to generate the plan."""
        client = genai.Client()
        response = await client.aio.models.generate_content(
            model=self._model_name,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.2,
                max_output_tokens=8192,
                response_mime_type="application/json",
                response_schema=MappingPlan,
            ),
        )
        return MappingPlan.model_validate_json(response.text)


__all__ = ["MappingPlanAgent"]
```

- [ ] **Step 3: Run full test suite to verify no regressions**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All existing tests PASS (MappingPlanAgent tests may need updates if they mock the old interface)

- [ ] **Step 4: Commit**

```bash
git add src/agents/mapping_plan_agent.py src/resources/prompts/mapping_plan_prompt.txt
git commit -m "feat(plan): rewrite MappingPlanAgent v2 with structured output and candidate ranking"
```

---

### Task 5: Wire CandidateRetriever + PlanValidator into Pipeline

**Files:**
- Modify: `src/run_pipeline.py:494-505`
- Modify: `src/api/services/pipeline_runner.py:111-136`

- [ ] **Step 1: Create CandidateRetrieverAgent (ADK wrapper)**

The CandidateRetriever is pure Python, but the pipeline uses ADK agents. Create a thin ADK wrapper. Add to `src/pipeline/plan/candidate_retriever.py` at the bottom:

```python
# --- ADK Agent Wrapper ---

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types


class CandidateRetrieverAgent(BaseAgent):
    """ADK agent wrapper for CandidateRetriever. Runs before MappingPlanAgent."""

    def __init__(self, name: str = "CandidateRetriever"):
        super().__init__(name=name)

    async def _run_async_impl(self, ctx: InvocationContext):
        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text="Retrieving grounding candidates per column...")]
        ))

        retriever = CandidateRetriever()

        # Parse column profiles from skeleton_summary
        skeleton = ctx.session.state.get("skeleton_summary", "")
        columns = self._parse_columns_from_skeleton(skeleton)

        schema_vocab = ctx.session.state.get("schema_vocab_content", "")

        results = retriever.retrieve_all(columns, schema_vocab)

        # Format as JSON for the plan agent
        import json
        pool = {}
        for col_name, (role, candidates, evidence) in results.items():
            pool[col_name] = {
                "proposed_role": role.value,
                "evidence": evidence,
                "candidates": [c.model_dump() for c in candidates],
            }

        ctx.session.state["candidate_pool"] = json.dumps(pool, indent=2)
        logger.info("Candidate retrieval complete: %d columns, %d total candidates",
                    len(pool), sum(len(v["candidates"]) for v in pool.values()))

        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text=f"Retrieved candidates for {len(pool)} columns")]
        ))

    @staticmethod
    def _parse_columns_from_skeleton(skeleton: str) -> list[dict]:
        """Parse column info from skeleton_summary table.

        The skeleton has a markdown table with columns:
        | Column | Type | Unique | Semantic | Samples | ...
        """
        columns = []
        in_table = False
        for line in skeleton.split("\n"):
            if "|" not in line:
                if in_table:
                    break
                continue
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]  # remove empty from leading/trailing |
            if not cells:
                continue
            if cells[0].startswith("---") or cells[0].startswith("Column"):
                in_table = True
                continue
            if len(cells) >= 4:
                name = cells[0].strip("`")
                dtype = cells[1] if len(cells) > 1 else "String"
                cardinality = int(cells[2]) if len(cells) > 2 and cells[2].isdigit() else 0
                semantic = cells[3] if len(cells) > 3 and cells[3] != "-" else None

                # Detect semantic type from the table
                sem_type = None
                if semantic:
                    sem_lower = semantic.lower()
                    if any(k in sem_lower for k in ["place", "geo", "country", "state", "fips", "iso"]):
                        sem_type = "place"
                    elif any(k in sem_lower for k in ["date", "year", "time", "period"]):
                        sem_type = "date"

                # Detect measure from dtype
                if dtype in ("Float", "Integer") and not sem_type:
                    cardinality_ratio = 0.5  # estimate
                else:
                    cardinality_ratio = 0.05

                samples = cells[4].split(", ")[:3] if len(cells) > 4 else []

                columns.append({
                    "name": name,
                    "dtype": dtype,
                    "semantic_type": sem_type,
                    "cardinality": cardinality,
                    "cardinality_ratio": cardinality_ratio,
                    "sample_values": samples,
                })

        return columns
```

- [ ] **Step 2: Create PlanValidatorAgent (ADK wrapper)**

Add to `src/pipeline/plan/plan_validator.py` at the bottom:

```python
# --- ADK Agent Wrapper ---

import asyncio
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types


class PlanValidatorAgent(BaseAgent):
    """ADK agent wrapper for PlanValidator. Runs after MappingPlanAgent."""

    def __init__(self, name: str = "PlanValidator"):
        super().__init__(name=name)

    async def _run_async_impl(self, ctx: InvocationContext):
        plan_json = ctx.session.state.get("mapping_plan_json", "")
        if not plan_json:
            yield Event(author=self.name, content=genai_types.Content(
                parts=[genai_types.Part(text="No plan to validate — skipping")]
            ))
            return

        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text="Validating plan against DC API...")]
        ))

        from src.api.models.plan import MappingPlan
        plan = MappingPlan.model_validate_json(plan_json)

        validator = PlanValidator()
        validated = await validator.validate(plan)

        # Update state with validated plan
        validated_json = validated.model_dump_json(indent=2)
        ctx.session.state["mapping_plan"] = validated_json
        ctx.session.state["mapping_plan_json"] = validated_json

        # Overwrite the JSON file on disk
        output_dir = Path(ctx.session.state.get("output_dir", "."))
        json_path = output_dir / "mapping_plan.json"
        if json_path.exists():
            json_path.write_text(validated_json)

        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text="Plan validation complete")]
        ))
```

- [ ] **Step 3: Wire into run_pipeline.py**

Modify `src/run_pipeline.py` lines 494-505. Replace:

```python
    # Add MappingPlanAgent and PlanGateAgent (unless loading from existing plan)
    if not from_plan:
        from src.agents.mapping_plan_agent import MappingPlanAgent
        plan_agent = MappingPlanAgent(name="MappingPlan", model=model)
        sub_agents.append(plan_agent)
        logger.info("MappingPlanAgent added to pipeline")

        gate_agent = PlanGateAgent(name="PlanGate")
        sub_agents.append(gate_agent)
        logger.info("PlanGateAgent added to pipeline")
    else:
        logger.info("MappingPlanAgent skipped (--from-plan provided)")
```

With:

```python
    # Add CandidateRetriever + MappingPlanAgent + PlanValidator + PlanGate (unless loading from existing plan)
    if not from_plan:
        from src.pipeline.plan.candidate_retriever import CandidateRetrieverAgent
        from src.agents.mapping_plan_agent import MappingPlanAgent
        from src.pipeline.plan.plan_validator import PlanValidatorAgent

        retriever_agent = CandidateRetrieverAgent(name="CandidateRetriever")
        sub_agents.append(retriever_agent)
        logger.info("CandidateRetrieverAgent added to pipeline")

        plan_agent = MappingPlanAgent(name="MappingPlan", model=model)
        sub_agents.append(plan_agent)
        logger.info("MappingPlanAgent added to pipeline")

        validator_agent = PlanValidatorAgent(name="PlanValidator")
        sub_agents.append(validator_agent)
        logger.info("PlanValidatorAgent added to pipeline")

        gate_agent = PlanGateAgent(name="PlanGate")
        sub_agents.append(gate_agent)
        logger.info("PlanGateAgent added to pipeline")
    else:
        logger.info("MappingPlanAgent skipped (--from-plan provided)")
```

- [ ] **Step 4: Update pipeline_runner.py to save structured plan**

Modify `src/api/services/pipeline_runner.py` lines 111-136. In the `phase1_state` dict (around line 115), add the `mapping_plan_json` key:

```python
            phase1_state = {
                "dataset_name": config.dataset_name,
                "skeleton_summary": result.get("skeleton_summary", ""),
                "schema_category": result.get("schema_category", ""),
                "schema_vocab_content": result.get("schema_vocab_content", ""),
                "mapping_plan": result.get("mapping_plan", ""),
                "mapping_plan_json": result.get("mapping_plan_json", ""),
                "sampled_data_path": result.get("sampled_data_path", ""),
                "data_context": result.get("data_context", {}),
                "schemaorg_column_mappings": result.get("schemaorg_column_mappings", ""),
            }
```

And after saving `mapping_plan.md` (around line 133), also save the JSON:

```python
            mapping_plan_json = result.get("mapping_plan_json", "")
            if mapping_plan_json:
                (dataset_output_dir / "mapping_plan.json").write_text(mapping_plan_json)
```

- [ ] **Step 5: Update PLAN_PHASES in frontend types**

In `frontend/src/types/index.ts`, update `PLAN_PHASES` to include the new agents:

```typescript
export const PLAN_PHASES = [
  "StatePrep",
  "Sampling",
  "SchemaSelectionAgent",
  "SchemaOrgEnrichment",
  "CandidateRetriever",
  "MappingPlan",
  "PlanValidator",
] as const;
```

And add to `PHASE_LABELS`:

```typescript
  CandidateRetriever: "Retrieving grounding candidates",
  PlanValidator: "Validating against DC API",
```

- [ ] **Step 6: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests PASS

- [ ] **Step 7: Commit**

```bash
git add src/run_pipeline.py src/pipeline/plan/candidate_retriever.py src/pipeline/plan/plan_validator.py src/api/services/pipeline_runner.py frontend/src/types/index.ts
git commit -m "feat(plan): wire CandidateRetriever + PlanValidator into pipeline sequence"
```

---

### Task 6: API Endpoints — GET /plan + POST /plan/approve

> **Dependency:** Task 7 (SkeletonConverter) must be completed before POST /plan/approve works. Implement Task 7 first if doing tasks out of order.

**Files:**
- Modify: `src/api/routes/plan.py`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add GET /plan and POST /plan/approve to plan.py**

Add these endpoints to `src/api/routes/plan.py` after the imports:

```python
from src.api.models.plan import MappingPlan


@router.get("/runs/{run_id}/plan")
async def get_plan(run_id: str):
    """Return the structured mapping plan as JSON."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_dir = Path(run.run_dir)
    dataset_name = run.dataset_name

    # Try structured JSON first, fall back to phase1_state
    json_path = run_dir / "output" / dataset_name / "mapping_plan.json"
    if json_path.exists():
        plan = MappingPlan.model_validate_json(json_path.read_text())
        return plan.model_dump()

    # Fall back: check phase1_state.json
    phase1_path = run_dir / "phase1_state.json"
    if phase1_path.exists():
        phase1 = json.loads(phase1_path.read_text())
        plan_json = phase1.get("mapping_plan_json", "")
        if plan_json:
            plan = MappingPlan.model_validate_json(plan_json)
            return plan.model_dump()

    raise HTTPException(status_code=404, detail="No structured plan found for this run")


class ApprovePlanRequest(BaseModel):
    plan: dict  # MappingPlan JSON with updated selected_index values


@router.post("/runs/{run_id}/plan/approve")
async def approve_plan(run_id: str, body: ApprovePlanRequest):
    """Save the engineer's plan selections and prepare for Phase 2."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    # Validate the plan structure
    plan = MappingPlan.model_validate(body.plan)

    run_dir = Path(run.run_dir)
    dataset_name = run.dataset_name
    output_dir = run_dir / "output" / dataset_name
    output_dir.mkdir(parents=True, exist_ok=True)

    # Save approved plan JSON
    (output_dir / "approved_plan.json").write_text(plan.model_dump_json(indent=2))

    # Generate PVMAP skeleton from selections
    from src.pipeline.plan.skeleton_converter import plan_to_skeleton_csv
    skeleton_csv = plan_to_skeleton_csv(plan)
    (output_dir / "pvmap_skeleton.csv").write_text(skeleton_csv)

    return {"status": "approved", "skeleton_rows": skeleton_csv.count("\n")}
```

- [ ] **Step 2: Add frontend API functions**

Add to `frontend/src/lib/api.ts` after the `generatePvmap` function:

```typescript
export async function getPlan(
  runId: string
): Promise<import("@/types").MappingPlan> {
  return request(`/runs/${runId}/plan`);
}

export async function approvePlan(
  runId: string,
  plan: import("@/types").MappingPlan
): Promise<{ status: string; skeleton_rows: number }> {
  return request(`/runs/${runId}/plan/approve`, {
    method: "POST",
    body: JSON.stringify({ plan }),
  });
}
```

- [ ] **Step 3: Update the generatePvmap call to use approved plan**

Modify the `generate_pvmap` endpoint in `src/api/routes/plan.py`. In the `extra_state` dict (line 82), add:

```python
        "approved_plan_json": (output_dir / "approved_plan.json").read_text() if (output_dir / "approved_plan.json").exists() else "",
        "pvmap_skeleton": (output_dir / "pvmap_skeleton.csv").read_text() if (output_dir / "pvmap_skeleton.csv").exists() else "",
```

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/plan.py frontend/src/lib/api.ts
git commit -m "feat(api): add GET /plan and POST /plan/approve endpoints"
```

---

### Task 7: SkeletonConverter — Plan to Partial PVMAP CSV

**Files:**
- Create: `src/pipeline/plan/skeleton_converter.py`
- Create: `tests/pipeline/plan/test_skeleton_converter.py`

- [ ] **Step 1: Write failing tests**

Create `tests/pipeline/plan/test_skeleton_converter.py`:

```python
"""Tests for plan_to_skeleton_csv conversion."""
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
from src.pipeline.plan.skeleton_converter import plan_to_skeleton_csv


def _make_plan():
    return MappingPlan(
        dataset_name="bis_central_bank",
        understanding=DatasetUnderstanding(
            archetype="Flat", observation_grain="one per country per period", key_insight="rates"
        ),
        active_columns=[
            ColumnMapping(
                column_name="REF_AREA:Reference area",
                role=ColumnRole.OBSERVATION_ABOUT,
                candidates=[PropertyValueCandidate(
                    property="observationAbout", value_expression="country/[DATA]",
                    confidence=0.95, source=CandidateSource.MCP, reason="place"
                )],
                evidence="2 unique",
                selected_index=0,
            ),
            ColumnMapping(
                column_name="TIME_PERIOD:Time period",
                role=ColumnRole.OBSERVATION_DATE,
                candidates=[PropertyValueCandidate(
                    property="observationDate", value_expression="[DATA]",
                    confidence=0.92, source=CandidateSource.SCHEMA_ORG, reason="date"
                )],
                evidence="30 unique",
                selected_index=0,
            ),
            ColumnMapping(
                column_name="OBS_VALUE:Observation Value",
                role=ColumnRole.MEASURE,
                candidates=[PropertyValueCandidate(
                    property="value", value_expression="[NUMBER]",
                    confidence=0.93, source=CandidateSource.SCHEMA_ORG, reason="measure"
                )],
                evidence="15 unique",
                selected_index=0,
            ),
            ColumnMapping(
                column_name="FREQ:Frequency",
                role=ColumnRole.DIMENSION,
                candidates=[
                    PropertyValueCandidate(
                        property="observationPeriod", value_expression="[DATA]",
                        confidence=0.85, source=CandidateSource.MCP, reason="frequency"
                    ),
                    PropertyValueCandidate(
                        property="measurementQualifier", value_expression="[DATA]",
                        confidence=0.60, source=CandidateSource.LLM, reason="alt"
                    ),
                ],
                evidence="2 unique",
                selected_index=0,
            ),
        ],
        ignored_columns=[],
        static_properties=[
            StaticProperty(
                property_name="populationType",
                candidates=[PropertyValueCandidate(
                    property="populationType", value_expression="InterestRate",
                    confidence=0.90, source=CandidateSource.MCP, reason="from DC"
                )],
                selected_index=0,
            ),
            StaticProperty(
                property_name="statType",
                candidates=[PropertyValueCandidate(
                    property="statType", value_expression="measuredValue",
                    confidence=0.88, source=CandidateSource.SCHEMA_VOCAB, reason="standard"
                )],
                selected_index=0,
            ),
            StaticProperty(
                property_name="unit",
                candidates=[PropertyValueCandidate(
                    property="unit", value_expression="dcid:Percent",
                    confidence=0.92, source=CandidateSource.MCP, reason="from data"
                )],
                selected_index=0,
            ),
        ],
        global_notes=[],
    )


class TestSkeletonConverter:
    def test_basic_conversion(self):
        plan = _make_plan()
        csv = plan_to_skeleton_csv(plan)
        lines = csv.strip().split("\n")
        # First line is header
        assert lines[0].startswith("key,")
        # Should have rows for each active column + 1 static property row
        assert len(lines) >= 5

    def test_column_rows_have_correct_keys(self):
        plan = _make_plan()
        csv = plan_to_skeleton_csv(plan)
        assert "REF_AREA:Reference area" in csv
        assert "TIME_PERIOD:Time period" in csv
        assert "OBS_VALUE:Observation Value" in csv
        assert "FREQ:Frequency" in csv

    def test_selected_candidate_used(self):
        plan = _make_plan()
        # FREQ has 2 candidates, selected_index=0 should use observationPeriod
        csv = plan_to_skeleton_csv(plan)
        assert "observationPeriod" in csv

    def test_alternate_selection(self):
        plan = _make_plan()
        # Change FREQ selection to index 1 (measurementQualifier)
        plan.active_columns[3].selected_index = 1
        csv = plan_to_skeleton_csv(plan)
        assert "measurementQualifier" in csv
        assert "observationPeriod" not in csv

    def test_static_properties_in_output(self):
        plan = _make_plan()
        csv = plan_to_skeleton_csv(plan)
        assert "populationType" in csv
        assert "InterestRate" in csv
        assert "statType" in csv
        assert "measuredValue" in csv

    def test_placeholders_converted(self):
        """[DATA] and [NUMBER] should become {Data} and {Number} in PVMAP CSV."""
        plan = _make_plan()
        csv = plan_to_skeleton_csv(plan)
        assert "{Data}" in csv or "[DATA]" not in csv
        assert "{Number}" in csv or "[NUMBER]" not in csv

    def test_empty_plan(self):
        plan = MappingPlan(
            dataset_name="empty",
            understanding=DatasetUnderstanding(archetype="Flat", observation_grain="n/a", key_insight="n/a"),
            active_columns=[],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )
        csv = plan_to_skeleton_csv(plan)
        assert csv.startswith("key,")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_skeleton_converter.py -x -q`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement SkeletonConverter**

Create `src/pipeline/plan/skeleton_converter.py`:

```python
"""Convert an approved MappingPlan to a partial PVMAP CSV skeleton.

The skeleton contains locked rows from engineer selections. The PVMAP
generator fills in gaps (formatting, COLUMN:VALUE sub-mappings) but
cannot override locked rows.
"""
from __future__ import annotations

from src.api.models.plan import ColumnRole, MappingPlan


def _to_pvmap_placeholder(expr: str) -> str:
    """Convert [DATA]/[NUMBER] notation to {Data}/{Number} for PVMAP CSV."""
    return expr.replace("[DATA]", "{Data}").replace("[NUMBER]", "{Number}")


def plan_to_skeleton_csv(plan: MappingPlan) -> str:
    """Convert approved plan selections to PVMAP CSV rows.

    Returns a CSV string in PVMAP format:
        key,property1,value1[,property2,value2,...]
    """
    rows: list[str] = []

    # Determine max property pairs needed per row
    max_pairs = 1
    for col in plan.active_columns:
        if not col.candidates:
            continue
        selected = col.candidates[col.selected_index]
        # Measure columns need: value + (nothing else per row usually)
        # But some roles need property,value pair
        pairs = 1
        max_pairs = max(max_pairs, pairs)

    # Generate header (we'll use enough columns for the widest row)
    # PVMAP format: key,property1,value1,property2,value2,...
    # Static property row may have multiple pairs
    static_pairs = len(plan.static_properties)
    total_pairs = max(max_pairs, static_pairs, 1)
    header_parts = ["key"]
    for i in range(total_pairs):
        header_parts.extend([f"property{i+1}", f"value{i+1}"])
    rows.append(",".join(header_parts))

    # Column mapping rows
    for col in plan.active_columns:
        if not col.candidates:
            continue
        selected = col.candidates[col.selected_index]
        value_expr = _to_pvmap_placeholder(selected.value_expression)

        # Build row: key, property, value
        parts = [col.column_name, selected.property, value_expr]
        # Pad to full width
        while len(parts) < len(header_parts):
            parts.append("")
        rows.append(",".join(parts))

    # Static properties row (empty key)
    if plan.static_properties:
        parts = [""]  # empty key for static row
        for sp in plan.static_properties:
            if sp.candidates:
                selected = sp.candidates[sp.selected_index]
                parts.extend([sp.property_name, _to_pvmap_placeholder(selected.value_expression)])
        # Pad to full width
        while len(parts) < len(header_parts):
            parts.append("")
        rows.append(",".join(parts))

    return "\n".join(rows) + "\n"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_skeleton_converter.py -x -q`
Expected: All tests PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/plan/skeleton_converter.py tests/pipeline/plan/test_skeleton_converter.py
git commit -m "feat(plan): add SkeletonConverter to turn approved plan into partial PVMAP CSV"
```

---

## Phase 2: Interactive Frontend

### Task 8: TypeScript Types + API Functions

**Files:**
- Modify: `frontend/src/types/index.ts`
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add MappingPlan types to frontend/src/types/index.ts**

Add after the `PreviewResponse` interface:

```typescript
// ── Structured Plan Types ─────────────────────────────────

export type CandidateSource = "from Schema.org" | "from MCP" | "from schema_vocab" | "LLM suggestion" | "user override";
export type ColumnRole = "observationAbout" | "observationDate" | "measure" | "dimension" | "metadata" | "ignored";

export interface CandidateValidation {
  property_exists: boolean;
  place_resolution_rate: number | null;
  existing_statvar: string | null;
  notes: string;
}

export interface PropertyValueCandidate {
  property: string;
  value_expression: string;
  confidence: number;
  source: CandidateSource;
  reason: string;
  validation: CandidateValidation | null;
}

export interface ColumnMapping {
  column_name: string;
  role: ColumnRole;
  candidates: PropertyValueCandidate[];
  selected_index: number;
  evidence: string;
  dc_match: string | null;
  is_ambiguous: boolean;
}

export interface StaticProperty {
  property_name: string;
  candidates: PropertyValueCandidate[];
  selected_index: number;
}

export interface DatasetUnderstanding {
  archetype: string;
  observation_grain: string;
  key_insight: string;
}

export interface MappingPlan {
  dataset_name: string;
  understanding: DatasetUnderstanding;
  active_columns: ColumnMapping[];
  ignored_columns: ColumnMapping[];
  static_properties: StaticProperty[];
  global_notes: string[];
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts frontend/src/lib/api.ts
git commit -m "feat(ui): add MappingPlan TypeScript types and API functions"
```

---

### Task 9: PlanReview Components

**Files:**
- Create: `frontend/src/components/PlanReview/ActiveMappingsTable.tsx`
- Create: `frontend/src/components/PlanReview/ColumnDetail.tsx`
- Create: `frontend/src/components/PlanReview/StaticProperties.tsx`
- Create: `frontend/src/components/PlanReview/IgnoredColumns.tsx`

- [ ] **Step 1: Create ColumnDetail component**

Create `frontend/src/components/PlanReview/ColumnDetail.tsx`:

```tsx
import { useState } from "react";
import { Input } from "@/components/ui/input";
import type { ColumnMapping, PropertyValueCandidate } from "@/types";

interface ColumnDetailProps {
  column: ColumnMapping;
  onSelectionChange: (selectedIndex: number) => void;
  onCustomOverride: (property: string, valueExpression: string) => void;
}

export function ColumnDetail({ column, onSelectionChange, onCustomOverride }: ColumnDetailProps) {
  const [customInput, setCustomInput] = useState("");

  const handleCustomSubmit = () => {
    const parts = customInput.split("->").map(s => s.trim());
    if (parts.length === 2 && parts[0] && parts[1]) {
      onCustomOverride(parts[0], parts[1]);
      setCustomInput("");
    }
  };

  return (
    <div className="px-4 py-3 space-y-3 border-t bg-muted/20">
      <div className="text-sm text-muted-foreground">{column.evidence}</div>
      {column.dc_match && (
        <div className="text-sm">DC Match: <code className="text-xs">{column.dc_match}</code></div>
      )}

      <div className="space-y-1.5">
        <div className="text-sm font-medium">Options:</div>
        {column.candidates.map((c: PropertyValueCandidate, i: number) => (
          <label key={i} className="flex items-start gap-2 text-sm cursor-pointer">
            <input
              type="radio"
              name={`col-${column.column_name}`}
              checked={column.selected_index === i}
              onChange={() => onSelectionChange(i)}
              className="mt-0.5"
            />
            <div>
              <span className="font-mono">{c.property}</span>
              <span className="text-muted-foreground"> -> </span>
              <span className="font-mono">{c.value_expression}</span>
              <span className="text-muted-foreground ml-2">
                {(c.confidence * 100).toFixed(0)}% ({c.source})
              </span>
              {c.validation && (
                <span className="text-muted-foreground ml-1">
                  {c.validation.property_exists ? " [verified]" : " [not in DC]"}
                </span>
              )}
              <div className="text-xs text-muted-foreground">{c.reason}</div>
            </div>
          </label>
        ))}
      </div>

      <div className="flex gap-2 items-center">
        <Input
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          placeholder="Custom: property -> value_expression"
          className="text-sm font-mono h-8"
          onKeyDown={(e) => e.key === "Enter" && handleCustomSubmit()}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Create ActiveMappingsTable component**

Create `frontend/src/components/PlanReview/ActiveMappingsTable.tsx`:

```tsx
import { useState } from "react";
import { ColumnDetail } from "./ColumnDetail";
import type { ColumnMapping } from "@/types";

interface ActiveMappingsTableProps {
  columns: ColumnMapping[];
  onUpdate: (columnName: string, updates: Partial<ColumnMapping>) => void;
}

export function ActiveMappingsTable({ columns, onUpdate }: ActiveMappingsTableProps) {
  const [expandedCol, setExpandedCol] = useState<string | null>(
    // Auto-expand first ambiguous column
    columns.find(c => c.is_ambiguous)?.column_name ?? null
  );

  const handleSelectionChange = (colName: string, selectedIndex: number) => {
    onUpdate(colName, { selected_index: selectedIndex });
  };

  const handleCustomOverride = (colName: string, property: string, valueExpression: string) => {
    const col = columns.find(c => c.column_name === colName);
    if (!col) return;
    const newCandidate = {
      property,
      value_expression: valueExpression,
      confidence: 1.0,
      source: "user override" as const,
      reason: "Manual override by engineer",
      validation: null,
    };
    const newCandidates = [...col.candidates, newCandidate];
    onUpdate(colName, {
      candidates: newCandidates,
      selected_index: newCandidates.length - 1,
    });
  };

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="px-4 py-2 bg-muted/30 border-b">
        <span className="text-sm font-medium">Active Mappings ({columns.length} columns)</span>
      </div>
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b bg-muted/10">
            <th className="text-left px-4 py-2 font-medium">Column</th>
            <th className="text-left px-4 py-2 font-medium">Role</th>
            <th className="text-left px-4 py-2 font-medium">Mapping</th>
          </tr>
        </thead>
        <tbody>
          {columns.map((col) => {
            const selected = col.candidates[col.selected_index];
            const isExpanded = expandedCol === col.column_name;
            return (
              <tr key={col.column_name} className="group">
                <td colSpan={3} className="p-0">
                  <div
                    className="flex items-center px-4 py-2 cursor-pointer hover:bg-muted/20 border-b"
                    onClick={() => setExpandedCol(isExpanded ? null : col.column_name)}
                  >
                    <div className="flex-1 font-mono text-xs">{col.column_name}</div>
                    <div className="w-36 text-muted-foreground">{col.role}</div>
                    <div className="flex-1 font-mono text-xs">
                      {selected ? `${selected.property} -> ${selected.value_expression}` : "—"}
                    </div>
                    {col.is_ambiguous && <span className="text-amber-500 ml-2" title="Ambiguous">!</span>}
                  </div>
                  {isExpanded && (
                    <ColumnDetail
                      column={col}
                      onSelectionChange={(idx) => handleSelectionChange(col.column_name, idx)}
                      onCustomOverride={(p, v) => handleCustomOverride(col.column_name, p, v)}
                    />
                  )}
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}
```

- [ ] **Step 3: Create StaticProperties component**

Create `frontend/src/components/PlanReview/StaticProperties.tsx`:

```tsx
import type { StaticProperty } from "@/types";

interface StaticPropertiesProps {
  properties: StaticProperty[];
  onUpdate: (propName: string, selectedIndex: number) => void;
}

export function StaticProperties({ properties, onUpdate }: StaticPropertiesProps) {
  if (properties.length === 0) return null;

  return (
    <div className="border rounded-lg overflow-hidden">
      <div className="px-4 py-2 bg-muted/30 border-b">
        <span className="text-sm font-medium">Static Properties</span>
      </div>
      <div className="p-4 space-y-3">
        {properties.map((sp) => (
          <div key={sp.property_name} className="space-y-1">
            <div className="text-sm font-medium">{sp.property_name}</div>
            <div className="space-y-1 ml-4">
              {sp.candidates.map((c, i) => (
                <label key={i} className="flex items-center gap-2 text-sm cursor-pointer">
                  <input
                    type="radio"
                    name={`sp-${sp.property_name}`}
                    checked={sp.selected_index === i}
                    onChange={() => onUpdate(sp.property_name, i)}
                  />
                  <span className="font-mono">{c.value_expression}</span>
                  <span className="text-muted-foreground">
                    {(c.confidence * 100).toFixed(0)}% ({c.source})
                  </span>
                </label>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Create IgnoredColumns component**

Create `frontend/src/components/PlanReview/IgnoredColumns.tsx`:

```tsx
import { useState } from "react";
import type { ColumnMapping } from "@/types";

interface IgnoredColumnsProps {
  columns: ColumnMapping[];
}

export function IgnoredColumns({ columns }: IgnoredColumnsProps) {
  const [expanded, setExpanded] = useState(false);

  if (columns.length === 0) return null;

  return (
    <div className="border rounded-lg overflow-hidden">
      <div
        className="px-4 py-2 bg-muted/30 border-b cursor-pointer hover:bg-muted/40 flex items-center justify-between"
        onClick={() => setExpanded(!expanded)}
      >
        <span className="text-sm font-medium text-muted-foreground">
          Ignored Columns ({columns.length})
        </span>
        <span className="text-xs text-muted-foreground">{expanded ? "collapse" : "expand"}</span>
      </div>
      {expanded && (
        <div className="p-4 space-y-1">
          {columns.map((col) => (
            <div key={col.column_name} className="text-sm text-muted-foreground">
              <code className="text-xs">{col.column_name}</code>
              <span className="ml-2">— {col.evidence}</span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/PlanReview/
git commit -m "feat(ui): add PlanReview components (ActiveMappingsTable, ColumnDetail, StaticProperties, IgnoredColumns)"
```

---

### Task 10: Rewrite ReviewPlanPage with Interactive Form

**Files:**
- Modify: `frontend/src/pages/ReviewPlanPage.tsx`

- [ ] **Step 1: Rewrite ReviewPlanPage**

Replace `frontend/src/pages/ReviewPlanPage.tsx`:

```tsx
/**
 * Wizard Step 3: Interactive plan review with selectable options per column.
 */
import { useEffect, useState, useCallback } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ActiveMappingsTable } from "@/components/PlanReview/ActiveMappingsTable";
import { StaticProperties } from "@/components/PlanReview/StaticProperties";
import { IgnoredColumns } from "@/components/PlanReview/IgnoredColumns";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getPlan, approvePlan, generatePvmap, stopRun } from "@/lib/api";
import { toast } from "sonner";
import { PLAN_PHASES } from "@/types";
import type { MappingPlan, ColumnMapping } from "@/types";
import { ChevronLeft, Play, Square, CheckCircle2 } from "lucide-react";

interface ReviewPlanPageProps {
  datasetName: string;
  startTime: number;
  onGenerateStarted: () => void;
  onError: (event: import("@/types").ProgressEvent) => void;
}

export function ReviewPlanPage({
  datasetName, startTime, onGenerateStarted, onError,
}: ReviewPlanPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [plan, setPlan] = useState<MappingPlan | null>(null);
  const [planReady, setPlanReady] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [stopping, setStopping] = useState(false);

  const { events } = useWebSocket({
    runId: runId ?? null,
    enabled: !planReady,
    onComplete: (event) => {
      if (event.result?.phase === "plan") {
        setPlanReady(true);
        toast.info("Plan ready for review");
      } else {
        navigate(`/runs/${runId}/results`);
      }
    },
    onError,
  });

  // Load structured plan when ready
  useEffect(() => {
    if (!planReady || !runId) return;
    setLoadingPlan(true);
    getPlan(runId)
      .then(setPlan)
      .catch(() => toast.error("Failed to load plan"))
      .finally(() => setLoadingPlan(false));
  }, [planReady, runId]);

  // Check if plan already exists (page refresh)
  useEffect(() => {
    if (!runId) return;
    getPlan(runId)
      .then((p) => { setPlan(p); setPlanReady(true); })
      .catch(() => {});
  }, [runId]);

  const handleColumnUpdate = useCallback((columnName: string, updates: Partial<ColumnMapping>) => {
    if (!plan) return;
    setPlan({
      ...plan,
      active_columns: plan.active_columns.map((col) =>
        col.column_name === columnName ? { ...col, ...updates } : col
      ),
    });
  }, [plan]);

  const handleStaticUpdate = useCallback((propName: string, selectedIndex: number) => {
    if (!plan) return;
    setPlan({
      ...plan,
      static_properties: plan.static_properties.map((sp) =>
        sp.property_name === propName ? { ...sp, selected_index: selectedIndex } : sp
      ),
    });
  }, [plan]);

  const handleApprove = async () => {
    if (!runId || !plan) return;
    setSubmitting(true);
    try {
      await approvePlan(runId, plan);
      await generatePvmap(runId);
      onGenerateStarted();
      navigate(`/runs/${runId}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start generation");
    } finally {
      setSubmitting(false);
    }
  };

  const handleStop = async () => {
    if (!runId || stopping) return;
    if (!window.confirm("Stop this run?")) return;
    setStopping(true);
    try {
      await stopRun(runId);
      navigate(`/runs/${runId}/results`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to stop");
      setStopping(false);
    }
  };

  // Loading state: plan being generated
  if (!planReady) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <WizardStepper currentStep={2} />
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">Preparing Your Plan</h1>
          <Button
            variant="outline" size="sm" onClick={handleStop} disabled={stopping}
            className="text-destructive border-destructive/50 hover:bg-destructive/10 gap-1.5"
          >
            <Square className="w-3.5 h-3.5" />
            {stopping ? "Stopping..." : "Stop"}
          </Button>
        </div>
        <ProgressTracker events={events} startTime={startTime} phases={PLAN_PHASES} />
        <Card className="shadow-sm mt-4">
          <CardContent className="pt-6">
            <div className="space-y-3">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${50 + Math.random() * 50}%` }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loadingPlan || !plan) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <WizardStepper currentStep={2} />
        <Card className="shadow-sm mt-6">
          <CardContent className="pt-6">
            <div className="space-y-3">
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${40 + Math.random() * 60}%` }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto space-y-4">
      <WizardStepper currentStep={2} />

      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">Review Mapping Plan</h1>
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-500" />
          <span className="text-sm text-green-600 dark:text-green-400 font-medium">Plan Ready</span>
        </div>
      </div>

      {/* Dataset Understanding */}
      <Card className="shadow-sm">
        <CardContent className="pt-4">
          <div className="text-sm space-y-1">
            <div><strong>Dataset:</strong> <code>{plan.dataset_name}</code></div>
            <div><strong>Format:</strong> {plan.understanding.archetype}</div>
            <div><strong>Grain:</strong> {plan.understanding.observation_grain}</div>
            <div><strong>Insight:</strong> {plan.understanding.key_insight}</div>
          </div>
        </CardContent>
      </Card>

      {/* Active Mappings */}
      <ActiveMappingsTable columns={plan.active_columns} onUpdate={handleColumnUpdate} />

      {/* Static Properties */}
      <StaticProperties properties={plan.static_properties} onUpdate={handleStaticUpdate} />

      {/* Ignored Columns */}
      <IgnoredColumns columns={plan.ignored_columns} />

      {/* Global Notes / Warnings */}
      {plan.global_notes.length > 0 && (
        <Card className="shadow-sm border-amber-200 dark:border-amber-800">
          <CardContent className="pt-4">
            <div className="text-sm font-medium mb-2">Warnings</div>
            <ul className="text-sm space-y-1 list-disc ml-4">
              {plan.global_notes.map((note, i) => (
                <li key={i} className="text-muted-foreground">{note}</li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* Actions */}
      <div className="flex justify-between pt-2">
        <Button variant="ghost" onClick={() => navigate("/configure")} className="gap-1.5">
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>
        <Button onClick={handleApprove} disabled={submitting} size="lg" className="gap-2">
          {submitting ? "Starting..." : "Approve & Generate PVMAP"}
          {!submitting && <Play className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

Run: `cd frontend && npm run build`
Expected: Build succeeds with no TypeScript errors

- [ ] **Step 3: Commit**

```bash
git add frontend/src/pages/ReviewPlanPage.tsx
git commit -m "feat(ui): rewrite ReviewPlanPage with interactive structured plan form"
```

---

## Phase 3: Constrained PVMAP Generation

### Task 11: Wire Approved Plan Skeleton into PVMAP Generator

**Files:**
- Modify: `src/run_pipeline.py` (PlanGateAgent)
- Modify: `src/api/routes/plan.py` (generate endpoint)

- [ ] **Step 1: Update PlanGateAgent to handle structured plan**

In `src/run_pipeline.py`, modify the `PlanGateAgent._run_async_impl` method. After the existing `plan_only` check, add handling for structured JSON plans:

```python
    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        plan_only = ctx.session.state.get("plan_only", False)
        mapping_plan = ctx.session.state.get("mapping_plan", "")

        if plan_only:
            yield Event(author=self.name, actions=EventActions(escalate=True),
                        content=types.Content(parts=[types.Part(text="Plan generated — awaiting human review.")]))
            return

        if mapping_plan:
            # Check if it's structured JSON (new format) or markdown (legacy)
            try:
                import json
                plan_data = json.loads(mapping_plan)
                # Structured plan — generate skeleton and store both
                from src.api.models.plan import MappingPlan
                from src.pipeline.plan.skeleton_converter import plan_to_skeleton_csv
                plan_obj = MappingPlan.model_validate(plan_data)
                skeleton = plan_to_skeleton_csv(plan_obj)
                ctx.session.state["pvmap_skeleton"] = skeleton
                ctx.session.state["approved_plan_json"] = mapping_plan
                # Also generate markdown for backward compatibility
                ctx.session.state["approved_mapping_plan"] = escape_pvmap_placeholders(
                    _plan_to_markdown_from_json(mapping_plan)
                )
                logger.info("Structured plan approved — skeleton: %d rows", skeleton.count("\n"))
            except (json.JSONDecodeError, Exception):
                # Legacy markdown plan
                escaped = escape_pvmap_placeholders(mapping_plan)
                ctx.session.state["approved_mapping_plan"] = escaped

            yield Event(author=self.name, content=types.Content(
                parts=[types.Part(text="Plan approved — proceeding to PVMAP generation.")]
            ))
```

Add the helper function above the class:

```python
def _plan_to_markdown_from_json(plan_json: str) -> str:
    """Convert structured plan JSON to markdown for backward compat."""
    from src.agents.mapping_plan_agent import _plan_to_markdown
    from src.api.models.plan import MappingPlan
    plan = MappingPlan.model_validate_json(plan_json)
    return _plan_to_markdown(plan)
```

- [ ] **Step 2: Update generate endpoint to pass skeleton**

In `src/api/routes/plan.py`, update the `generate_pvmap` endpoint's `extra_state` dict to include skeleton and approved plan JSON:

```python
    config.extra_state = {
        "from_plan": str(plan_path),
        "skeleton_summary": phase1.get("skeleton_summary", ""),
        "schema_category": phase1.get("schema_category", ""),
        "schema_vocab_content": phase1.get("schema_vocab_content", ""),
        "sampled_data_path": phase1.get("sampled_data_path", ""),
        "data_context": phase1.get("data_context", {}),
        "schemaorg_column_mappings": phase1.get("schemaorg_column_mappings", ""),
        "approved_plan_json": (output_dir / "approved_plan.json").read_text() if (output_dir / "approved_plan.json").exists() else "",
        "pvmap_skeleton": (output_dir / "pvmap_skeleton.csv").read_text() if (output_dir / "pvmap_skeleton.csv").exists() else "",
    }
```

- [ ] **Step 3: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests PASS

- [ ] **Step 4: Commit**

```bash
git add src/run_pipeline.py src/api/routes/plan.py
git commit -m "feat(plan): wire approved plan skeleton into PVMAP generation pipeline"
```

---

### Task 12: Integration Test — End-to-End Plan Flow

**Files:**
- Create: `tests/pipeline/plan/test_plan_integration.py`

- [ ] **Step 1: Write integration test**

Create `tests/pipeline/plan/test_plan_integration.py`:

```python
"""Integration test: full flow from column profiles → candidates → plan → skeleton."""
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


class TestEndToEndFlow:
    def test_bis_columns_to_skeleton(self):
        """Simulate the BIS dataset flow: columns → candidates → plan → skeleton."""
        retriever = CandidateRetriever()

        # Simplified BIS column profiles
        columns = [
            {"name": "REF_AREA:Reference area", "dtype": "String", "semantic_type": "place", "cardinality": 50, "cardinality_ratio": 0.1, "sample_values": ["GB: United Kingdom", "AR: Argentina"]},
            {"name": "TIME_PERIOD:Time period", "dtype": "Date", "semantic_type": "date", "cardinality": 100, "cardinality_ratio": 0.5, "sample_values": ["2020-01", "2021-06"]},
            {"name": "OBS_VALUE:Observation Value", "dtype": "Float", "semantic_type": None, "cardinality": 500, "cardinality_ratio": 0.8, "sample_values": ["1.5", "3.2"]},
            {"name": "FREQ:Frequency", "dtype": "String", "semantic_type": None, "cardinality": 2, "cardinality_ratio": 0.001, "sample_values": ["M: Monthly", "D: Daily"]},
            {"name": "STRUCTURE", "dtype": "String", "semantic_type": None, "cardinality": 1, "cardinality_ratio": 0.001, "sample_values": ["dataflow"]},
        ]

        # Step 1: Retrieve candidates
        results = retriever.retrieve_all(columns)
        assert len(results) == 5
        assert results["REF_AREA:Reference area"][0] == ColumnRole.OBSERVATION_ABOUT
        assert results["TIME_PERIOD:Time period"][0] == ColumnRole.OBSERVATION_DATE
        assert results["OBS_VALUE:Observation Value"][0] == ColumnRole.MEASURE
        assert results["STRUCTURE"][0] == ColumnRole.IGNORED

        # Step 2: Build a plan (simulating LLM output)
        active = []
        ignored = []
        for col in columns:
            role, candidates, evidence = results[col["name"]]
            mapping = ColumnMapping(
                column_name=col["name"],
                role=role,
                candidates=candidates,
                evidence=evidence,
            )
            if role == ColumnRole.IGNORED:
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
                        property="populationType", value_expression="InterestRate",
                        confidence=0.9, source=CandidateSource.MCP, reason="financial data"
                    )],
                ),
            ],
            global_notes=["Place resolution needed"],
        )

        # Step 3: Convert to skeleton
        skeleton = plan_to_skeleton_csv(plan)
        assert "REF_AREA:Reference area" in skeleton
        assert "TIME_PERIOD:Time period" in skeleton
        assert "OBS_VALUE:Observation Value" in skeleton
        assert "STRUCTURE" not in skeleton  # ignored columns not in skeleton
        assert "populationType" in skeleton

        # Step 4: JSON roundtrip
        plan_json = plan.model_dump_json()
        restored = MappingPlan.model_validate_json(plan_json)
        assert len(restored.active_columns) == len(active)
        assert len(restored.ignored_columns) == len(ignored)
```

- [ ] **Step 2: Run integration test**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_integration.py -x -v`
Expected: All tests PASS

- [ ] **Step 3: Run full test suite for regressions**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests PASS, report count

- [ ] **Step 4: Commit**

```bash
git add tests/pipeline/plan/test_plan_integration.py
git commit -m "test(plan): add end-to-end integration test for grounded plan flow"
```

---

## Summary

| Phase | Tasks | What it delivers |
|-------|-------|-----------------|
| **Phase 1** | Tasks 1-7 | Structured backend: Pydantic models, CandidateRetriever, PlanValidator, MappingPlanAgent v2, SkeletonConverter, API endpoints |
| **Phase 2** | Tasks 8-10 | Interactive frontend: TypeScript types, PlanReview components, rewritten ReviewPlanPage |
| **Phase 3** | Tasks 11-12 | Binding plan: skeleton wired into PVMAP generator, integration tests |

Total: 12 tasks, each independently testable and committable.
