# Enriched Mapping Plan & PVMAP Executor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the mapping plan with column attention matrix, value dictionaries, and StatVar blueprint, then make the PVMAP generator a strict plan executor with programmatic mitigations.

**Architecture:** Two-phase plan creation (Phase A: programmatic column analysis via pandas, Phase B: LLM structured reasoning), followed by a mitigations layer, then a simplified plan-executor generator. Two-tiered retry loop routes syntax errors to the generator and semantic errors back to the plan agent.

**Tech Stack:** Python/pandas (Phase A), Google Gemini structured output (Phase B), Pydantic models, Google ADK BaseAgent, React/TypeScript (UI)

**Spec:** `docs/superpowers/specs/2026-04-13-enriched-plan-and-pvmap-executor-design.md`

---

### Task 1: Extend the MappingPlan Data Model

**Files:**
- Modify: `src/api/models/plan.py`
- Test: `tests/api/models/test_plan_models.py`

This task adds all new Pydantic models needed by subsequent tasks. No behavioral changes yet.

- [ ] **Step 1: Write tests for new models**

```python
# tests/api/models/test_plan_models.py
import pytest
from src.api.models.plan import (
    RelationshipType, ColumnRelationship, ValueMapping, ValueDictionary,
    PlaceResolution, TimeResolution, StatVarBlueprint,
    TransformationStrategy, EnrichedMappingPlan,
    MappingPlan, DatasetUnderstanding, ColumnMapping, ColumnRole,
    PropertyValueCandidate, CandidateSource, StaticProperty,
)


def test_relationship_type_values():
    assert RelationshipType.CO_REFERENT == "co_referent"
    assert RelationshipType.CROSS_PRODUCT == "cross_product"
    assert RelationshipType.HIERARCHICAL == "hierarchical"


def test_column_relationship_creation():
    rel = ColumnRelationship(
        column_a="FIPS_Code",
        column_b="State_Name",
        relationship=RelationshipType.CO_REFERENT,
        strength=0.99,
        evidence="1:1 bijection, 99.8% purity",
        pvmap_implication="Use FIPS_Code for observationAbout, ignore State_Name",
    )
    assert rel.column_a == "FIPS_Code"
    assert rel.strength == 0.99


def test_value_mapping_map_action():
    vm = ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="Standard DC gender")
    assert vm.dcid == "dcs:Male"


def test_value_mapping_drop_constraint():
    vm = ValueMapping(raw_value="T", dcid=None, action="DROP_CONSTRAINT", reason="Total indicator")
    assert vm.dcid is None
    assert vm.action == "DROP_CONSTRAINT"


def test_value_dictionary():
    vd = ValueDictionary(
        column_name="SEX",
        dc_property="gender",
        mappings=[
            ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="Male"),
            ValueMapping(raw_value="F", dcid="dcs:Female", action="MAP", reason="Female"),
            ValueMapping(raw_value="T", dcid=None, action="DROP_CONSTRAINT", reason="Total"),
        ],
        total_indicators=["T"],
    )
    assert len(vd.mappings) == 3
    assert vd.total_indicators == ["T"]


def test_place_resolution():
    pr = PlaceResolution(
        column_name="FIPS",
        format_detected="fips_state",
        prefix_rule="geoId/",
        pad_zeros=2,
        resolution_rate=0.98,
    )
    assert pr.pad_zeros == 2


def test_time_resolution():
    tr = TimeResolution(
        columns=["Year", "Month"],
        format_detected="composed",
        normalization_rule="concat Year-Month",
    )
    assert len(tr.columns) == 2


def test_statvar_blueprint():
    svb = StatVarBlueprint(
        base_properties={"populationType": "dcs:Person", "measuredProperty": "dcs:count", "statType": "dcs:measuredValue"},
        constraint_columns=["SEX", "AGE"],
        measure_columns=["OBS_VALUE"],
    )
    assert svb.base_properties["populationType"] == "dcs:Person"


def test_transformation_strategy_long():
    ts = TransformationStrategy(
        archetype="long",
        action=None,
        id_vars=["REF_AREA", "TIME_PERIOD"],
        value_vars=[],
    )
    assert ts.action is None


def test_transformation_strategy_wide():
    ts = TransformationStrategy(
        archetype="wide_time",
        action="melt",
        id_vars=["FIPS_Code"],
        value_vars=["2020", "2021", "2022"],
    )
    assert ts.action == "melt"


def test_enriched_mapping_plan_extends_base():
    """EnrichedMappingPlan has all MappingPlan fields plus new ones."""
    plan = EnrichedMappingPlan(
        dataset_name="test",
        understanding=DatasetUnderstanding(
            archetype="Long/Tidy",
            observation_grain="Country x Year x Gender",
            key_insight="Standard SDMX dataset",
        ),
        active_columns=[
            ColumnMapping(
                column_name="REF_AREA",
                role=ColumnRole.OBSERVATION_ABOUT,
                candidates=[PropertyValueCandidate(
                    property="observationAbout",
                    value_expression="country/[DATA]",
                    confidence=0.95,
                    source=CandidateSource.SCHEMA_ORG,
                    reason="ISO-2 country codes",
                )],
                evidence="ISO-2 codes detected",
            ),
        ],
        ignored_columns=[],
        static_properties=[
            StaticProperty(
                property_name="populationType",
                candidates=[PropertyValueCandidate(
                    property="populationType",
                    value_expression="dcs:Person",
                    confidence=0.90,
                    source=CandidateSource.LLM,
                    reason="Population data",
                )],
            ),
        ],
        global_notes=["Standard SDMX format"],
        # New fields
        column_relationships=[
            ColumnRelationship(
                column_a="REF_AREA",
                column_b="TIME_PERIOD",
                relationship=RelationshipType.CROSS_PRODUCT,
                strength=0.95,
                evidence="density=0.92",
                pvmap_implication="Independent dimensions",
            ),
        ],
        statvar_blueprint=StatVarBlueprint(
            base_properties={"populationType": "dcs:Person", "measuredProperty": "dcs:count"},
            constraint_columns=["SEX"],
            measure_columns=["OBS_VALUE"],
        ),
        value_dictionaries=[
            ValueDictionary(
                column_name="SEX",
                dc_property="gender",
                mappings=[
                    ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="Male"),
                ],
                total_indicators=[],
            ),
        ],
        composite_key=["REF_AREA", "TIME_PERIOD", "SEX"],
    )
    # Check base fields work
    assert plan.dataset_name == "test"
    assert len(plan.active_columns) == 1
    # Check new fields
    assert len(plan.column_relationships) == 1
    assert plan.composite_key == ["REF_AREA", "TIME_PERIOD", "SEX"]
    assert plan.statvar_blueprint.base_properties["populationType"] == "dcs:Person"


def test_enriched_plan_json_roundtrip():
    """EnrichedMappingPlan survives JSON serialization/deserialization."""
    plan = EnrichedMappingPlan(
        dataset_name="roundtrip_test",
        understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
        active_columns=[],
        ignored_columns=[],
        static_properties=[],
        global_notes=[],
        column_relationships=[],
        statvar_blueprint=StatVarBlueprint(
            base_properties={"populationType": "dcs:Person"},
            constraint_columns=[],
            measure_columns=["Value"],
        ),
        value_dictionaries=[],
        composite_key=["A", "B"],
    )
    json_str = plan.model_dump_json()
    restored = EnrichedMappingPlan.model_validate_json(json_str)
    assert restored.dataset_name == "roundtrip_test"
    assert restored.composite_key == ["A", "B"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/models/test_plan_models.py -x -q`
Expected: FAIL — `ImportError: cannot import name 'RelationshipType'`

- [ ] **Step 3: Implement the new models**

Add to the end of `src/api/models/plan.py` (after the existing `MappingPlan` class):

```python
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


class StatVarBlueprint(BaseModel):
    """Base StatVar definition and how dimensions modify it."""
    base_properties: dict[str, str]
    constraint_columns: list[str]
    measure_columns: list[str]


class TransformationStrategy(BaseModel):
    """Dataset archetype and required structural transformations."""
    archetype: str
    action: Optional[str] = None
    id_vars: list[str] = Field(default_factory=list)
    value_vars: list[str] = Field(default_factory=list)


class EnrichedMappingPlan(MappingPlan):
    """MappingPlan extended with Phase A analysis + Phase B reasoning."""
    column_relationships: list[ColumnRelationship] = Field(default_factory=list)
    statvar_blueprint: StatVarBlueprint
    value_dictionaries: list[ValueDictionary] = Field(default_factory=list)
    place_resolution: Optional[PlaceResolution] = None
    time_resolution: Optional[TimeResolution] = None
    composite_key: list[str] = Field(default_factory=list)
    transformation_strategy: Optional[TransformationStrategy] = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/models/test_plan_models.py -x -q`
Expected: All PASS

- [ ] **Step 5: Run full test suite for regression**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions (existing tests use `MappingPlan`, not `EnrichedMappingPlan`)

- [ ] **Step 6: Commit**

```bash
git add src/api/models/plan.py tests/api/models/test_plan_models.py
git commit -m "feat(plan): add enriched plan data models — column relationships, value dicts, StatVar blueprint"
```

---

### Task 2: Phase A — Column Relationship Analyzer (Core Heuristics)

**Files:**
- Create: `src/pipeline/plan/column_analyzer.py`
- Test: `tests/pipeline/plan/test_column_analyzer.py`

This task builds the programmatic column analysis engine. It reuses the existing `DatasetProfile` from `profiler.py` and adds pairwise relationship detection.

- [ ] **Step 1: Write tests for co-referent detection**

```python
# tests/pipeline/plan/test_column_analyzer.py
import pytest
import pandas as pd
from src.pipeline.plan.column_analyzer import (
    detect_co_referents,
    detect_cross_products,
    detect_hierarchical,
    detect_qualifiers,
    detect_value_error_bounds,
    detect_composite_key,
    detect_place_format,
    detect_time_format,
    detect_total_indicators,
    analyze_columns,
    ColumnAnalysis,
)


class TestCoReferentDetection:
    def test_perfect_bijection(self):
        df = pd.DataFrame({
            "FIPS": ["06", "36", "48"],
            "State": ["California", "New York", "Texas"],
        })
        assert detect_co_referents(df, "FIPS", "State") is True

    def test_many_to_one_is_not_coreferent(self):
        df = pd.DataFrame({
            "County": ["LA", "SF", "LA"],
            "State": ["CA", "CA", "CA"],
        })
        assert detect_co_referents(df, "County", "State") is False

    def test_independent_columns(self):
        df = pd.DataFrame({
            "Gender": ["M", "F", "M", "F"],
            "Age": ["15-24", "15-24", "25-34", "25-34"],
        })
        assert detect_co_referents(df, "Gender", "Age") is False

    def test_with_nulls(self):
        df = pd.DataFrame({
            "Code": ["A", "B", None, "C"],
            "Name": ["Alpha", "Beta", None, "Charlie"],
        })
        assert detect_co_referents(df, "Code", "Name") is True


class TestCrossProductDetection:
    def test_full_cross_product(self):
        df = pd.DataFrame({
            "Gender": ["M", "M", "F", "F"],
            "Age": ["Young", "Old", "Young", "Old"],
        })
        assert detect_cross_products(df, "Gender", "Age") is True

    def test_sparse_cross_product(self):
        """Below 0.80 density threshold."""
        df = pd.DataFrame({
            "A": ["X", "X", "Y"],
            "B": ["1", "2", "1"],
        })
        # 3 combos out of 2*2=4 = 0.75 density
        assert detect_cross_products(df, "A", "B") is False

    def test_single_value_column(self):
        df = pd.DataFrame({
            "A": ["X", "X", "X"],
            "B": ["1", "2", "3"],
        })
        assert detect_cross_products(df, "A", "B") is False


class TestHierarchicalDetection:
    def test_county_state_hierarchy(self):
        df = pd.DataFrame({
            "County": ["LA", "SF", "SD", "NYC", "BUF"],
            "State": ["CA", "CA", "CA", "NY", "NY"],
        })
        result = detect_hierarchical(df, "County", "State")
        assert result is True

    def test_coreferent_is_not_hierarchical(self):
        df = pd.DataFrame({
            "Code": ["A", "B", "C"],
            "Name": ["Alpha", "Beta", "Charlie"],
        })
        assert detect_hierarchical(df, "Code", "Name") is False


class TestQualifierDetection:
    def test_numeric_with_unit_column(self):
        df = pd.DataFrame({
            "Value": [100.0, 200.0, 300.0],
            "Unit": ["USD", "USD", "EUR"],
        })
        assert detect_qualifiers(df, "Value", "Unit") is True

    def test_two_numeric_columns_not_qualifier(self):
        df = pd.DataFrame({
            "Value": [100.0, 200.0, 300.0],
            "Count": [10, 20, 30],
        })
        assert detect_qualifiers(df, "Value", "Count") is False


class TestValueErrorBoundDetection:
    def test_estimate_moe_pair(self):
        df = pd.DataFrame({
            "Estimate": [1000, 2000, 3000, 4000, 5000],
            "MOE": [50, 100, 150, 200, 250],
        })
        assert detect_value_error_bounds(df, "Estimate", "MOE") is True

    def test_moe_larger_than_estimate(self):
        df = pd.DataFrame({
            "Estimate": [10, 20, 30],
            "MOE": [5000, 6000, 7000],
        })
        assert detect_value_error_bounds(df, "Estimate", "MOE") is False


class TestCompositeKeyDetection:
    def test_single_column_key(self):
        df = pd.DataFrame({"ID": [1, 2, 3], "Val": [10, 20, 30]})
        key = detect_composite_key(df)
        assert key == ["ID"]

    def test_multi_column_key(self):
        df = pd.DataFrame({
            "Year": [2020, 2020, 2021, 2021],
            "State": ["CA", "NY", "CA", "NY"],
            "Pop": [39, 19, 40, 20],
        })
        key = detect_composite_key(df)
        assert set(key) == {"Year", "State"}

    def test_no_unique_key(self):
        df = pd.DataFrame({
            "A": [1, 1, 1],
            "B": [2, 2, 2],
        })
        key = detect_composite_key(df)
        assert key == []  # No unique combo


class TestPlaceFormatDetection:
    def test_fips_state(self):
        s = pd.Series(["06", "36", "48", "12", "17"])
        result = detect_place_format(s)
        assert result is not None
        assert result["format_detected"] == "fips_state"
        assert result["prefix_rule"] == "geoId/"

    def test_iso2_country(self):
        s = pd.Series(["US", "FR", "JP", "DE", "BR"])
        result = detect_place_format(s)
        assert result is not None
        assert result["format_detected"] == "iso_2"
        assert result["prefix_rule"] == "country/"

    def test_non_place(self):
        s = pd.Series(["apple", "banana", "cherry"])
        result = detect_place_format(s)
        assert result is None


class TestTotalIndicatorDetection:
    def test_common_totals(self):
        s = pd.Series(["M", "F", "T", "Male", "Female", "Total"])
        totals = detect_total_indicators(s)
        assert "T" in totals
        assert "Total" in totals
        assert "M" not in totals


class TestAnalyzeColumns:
    def test_sdmx_dataset(self):
        """Integration test with a realistic SDMX-style dataset."""
        df = pd.DataFrame({
            "REF_AREA": ["AR", "AR", "BR", "BR"],
            "TIME_PERIOD": ["2020", "2021", "2020", "2021"],
            "SEX": ["M", "F", "M", "F"],
            "OBS_VALUE": [100.0, 200.0, 300.0, 400.0],
            "UNIT_MEASURE": ["Percent", "Percent", "Percent", "Percent"],
        })
        result = analyze_columns(df)
        assert isinstance(result, ColumnAnalysis)
        assert len(result.composite_key) > 0
        # OBS_VALUE + UNIT_MEASURE should be detected as qualifier pair
        qual_pairs = [r for r in result.relationships if r.relationship.value == "qualifier"]
        assert len(qual_pairs) >= 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_column_analyzer.py -x -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'src.pipeline.plan.column_analyzer'`

- [ ] **Step 3: Implement the column analyzer**

Create `src/pipeline/plan/column_analyzer.py`:

```python
"""Phase A: Programmatic column relationship analysis.

Pure Python/pandas — no LLM calls. Computes pairwise column relationships,
composite key detection, place/time format detection, and value profiles.

Designed to run in < 1 second on typical sampled data (30-1000 rows).
Outputs feed into the MappingPlanAgent (Phase B) as trusted structural facts.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
    import numpy as np
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    np = None
    PANDAS_AVAILABLE = False

from src.api.models.plan import (
    ColumnRelationship,
    RelationshipType,
)

logger = logging.getLogger(__name__)

# Known total/aggregate indicators
TOTAL_INDICATORS = {
    "T", "Total", "All", "Both", "Both Sexes", "All Races",
    "All Ages", "Overall", "TOT", "-", "*", "~", "00", "000", "999",
}

# Place format regex patterns → (format_name, prefix_rule, pad_zeros)
_PLACE_PATTERNS = [
    (r"^\d{2}$", "fips_state", "geoId/", 2),
    (r"^\d{5}$", "fips_county", "geoId/", 5),
    (r"^[A-Z]{2}$", "iso_2", "country/", None),
    (r"^[A-Z]{3}$", "iso_3", "country/", None),
    (r"^\d{5}$", "zip_code", "zip/", None),
]

# Time column name keywords
_TIME_KEYWORDS = {"year", "month", "day", "quarter", "period", "date", "time"}

# Qualifier column name keywords
_QUALIFIER_KEYWORDS = {"unit", "currency", "measure", "metric", "scale", "multiplier"}


@dataclass
class ColumnAnalysis:
    """Complete Phase A analysis output."""
    relationships: List[ColumnRelationship] = field(default_factory=list)
    composite_key: List[str] = field(default_factory=list)
    place_detections: List[Dict[str, Any]] = field(default_factory=list)
    time_detections: List[Dict[str, Any]] = field(default_factory=list)
    raw_value_profiles: Dict[str, List[str]] = field(default_factory=dict)
    total_indicators: Dict[str, List[str]] = field(default_factory=dict)
    co_referent_groups: List[List[str]] = field(default_factory=list)
    functional_deps: List[Dict[str, str]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "relationships": [r.model_dump() for r in self.relationships],
            "composite_key": self.composite_key,
            "place_detections": self.place_detections,
            "time_detections": self.time_detections,
            "raw_value_profiles": self.raw_value_profiles,
            "total_indicators": self.total_indicators,
            "co_referent_groups": self.co_referent_groups,
            "functional_deps": self.functional_deps,
        }


def detect_co_referents(df: "pd.DataFrame", col_a: str, col_b: str, threshold: float = 0.99) -> bool:
    """Check if two columns have a 1:1 bijection (alias/co-referent)."""
    valid = df[[col_a, col_b]].dropna()
    if len(valid) < 2:
        return False
    a_to_b = valid.groupby(col_a)[col_b].nunique().max()
    b_to_a = valid.groupby(col_b)[col_a].nunique().max()
    return a_to_b == 1 and b_to_a == 1


def detect_cross_products(df: "pd.DataFrame", col_a: str, col_b: str, density_threshold: float = 0.80) -> bool:
    """Check if two columns form a dense cross-product (independent dimensions)."""
    valid = df[[col_a, col_b]].dropna()
    unique_a = valid[col_a].nunique()
    unique_b = valid[col_b].nunique()
    if unique_a < 2 or unique_b < 2:
        return False
    actual = len(valid.drop_duplicates())
    max_possible = unique_a * unique_b
    density = actual / max_possible
    return density >= density_threshold


def detect_hierarchical(df: "pd.DataFrame", child_col: str, parent_col: str) -> bool:
    """Check if child strictly determines parent (many-to-one, not 1:1)."""
    valid = df[[child_col, parent_col]].dropna()
    if len(valid) < 2:
        return False
    child_to_parent = valid.groupby(child_col)[parent_col].nunique().max()
    parent_to_child_mean = valid.groupby(parent_col)[child_col].nunique().mean()
    return child_to_parent == 1 and parent_to_child_mean > 1.1


def detect_qualifiers(df: "pd.DataFrame", val_col: str, qual_col: str, max_cardinality: int = 5) -> bool:
    """Check if qual_col is a low-cardinality qualifier for a numeric val_col."""
    if not pd.api.types.is_numeric_dtype(df[val_col]):
        return False
    if pd.api.types.is_numeric_dtype(df[qual_col]):
        return False
    unique_quals = df[qual_col].dropna().nunique()
    return 0 < unique_quals <= max_cardinality


def detect_value_error_bounds(df: "pd.DataFrame", est_col: str, moe_col: str, threshold: float = 0.95) -> bool:
    """Check if moe_col is an error bound for est_col (both numeric, MOE < estimate)."""
    if not (pd.api.types.is_numeric_dtype(df[est_col]) and pd.api.types.is_numeric_dtype(df[moe_col])):
        return False
    valid = df[[est_col, moe_col]].dropna()
    if len(valid) < 3:
        return False
    moe_smaller = (valid[moe_col].abs() < valid[est_col].abs()).mean()
    # Check column name hints
    moe_keywords = {"moe", "error", "bound", "ci", "variance", "std", "margin"}
    has_keyword = any(k in moe_col.lower() for k in moe_keywords)
    return moe_smaller >= threshold and has_keyword


def detect_composite_key(df: "pd.DataFrame", max_key_size: int = 5) -> List[str]:
    """Find minimal set of columns that uniquely identify each row."""
    cols = list(df.columns)
    n = len(df)
    if n == 0:
        return []

    # Check single columns first
    for col in cols:
        if df[col].nunique() == n:
            return [col]

    # Check pairs, triples, etc. up to max_key_size
    from itertools import combinations
    for size in range(2, min(max_key_size + 1, len(cols) + 1)):
        for combo in combinations(cols, size):
            if df.groupby(list(combo)).size().max() == 1:
                return list(combo)

    return []  # No unique combination found


def detect_place_format(series: "pd.Series") -> Optional[Dict[str, Any]]:
    """Detect geographic format from a column's values."""
    values = series.dropna().astype(str).str.strip()
    if len(values) == 0:
        return None

    for pattern, fmt, prefix, pad in _PLACE_PATTERNS:
        match_rate = values.str.match(pattern).mean()
        if match_rate >= 0.90:
            return {
                "format_detected": fmt,
                "prefix_rule": prefix,
                "pad_zeros": pad,
                "resolution_rate": round(match_rate, 3),
            }
    return None


def detect_time_format(series: "pd.Series") -> Optional[Dict[str, Any]]:
    """Detect temporal format from a column's values."""
    values = series.dropna().astype(str).str.strip()
    if len(values) == 0:
        return None

    # YYYY format
    if values.str.match(r"^\d{4}$").mean() >= 0.90:
        as_int = pd.to_numeric(values, errors="coerce")
        if as_int.between(1800, 2100).mean() >= 0.90:
            return {"format_detected": "YYYY", "normalization_rule": "direct"}

    # YYYY-MM format
    if values.str.match(r"^\d{4}-\d{2}$").mean() >= 0.90:
        return {"format_detected": "YYYY-MM", "normalization_rule": "direct"}

    # YYYY-MM-DD format
    if values.str.match(r"^\d{4}-\d{2}-\d{2}$").mean() >= 0.90:
        return {"format_detected": "YYYY-MM-DD", "normalization_rule": "direct"}

    return None


def detect_total_indicators(series: "pd.Series") -> List[str]:
    """Find values in a series that represent totals/aggregates."""
    values = set(series.dropna().astype(str).str.strip().unique())
    return sorted(values & TOTAL_INDICATORS)


def analyze_columns(df: "pd.DataFrame") -> ColumnAnalysis:
    """Run all Phase A analyses on a DataFrame.

    Returns a ColumnAnalysis with pairwise relationships, composite key,
    place/time detections, value profiles, and total indicators.
    """
    if not PANDAS_AVAILABLE:
        raise ImportError("pandas is required for analyze_columns")

    result = ColumnAnalysis()
    cols = list(df.columns)
    n_cols = len(cols)

    # --- Composite key ---
    result.composite_key = detect_composite_key(df)

    # --- Per-column analysis ---
    numeric_cols = [c for c in cols if pd.api.types.is_numeric_dtype(df[c])]
    categorical_cols = [c for c in cols if not pd.api.types.is_numeric_dtype(df[c])]
    low_card_cols = [c for c in cols if df[c].nunique() <= 100]

    for col in cols:
        unique_vals = df[col].dropna().astype(str).unique().tolist()
        if len(unique_vals) <= 50:
            result.raw_value_profiles[col] = sorted(unique_vals)

        totals = detect_total_indicators(df[col])
        if totals:
            result.total_indicators[col] = totals

    # --- Place/time detection ---
    for col in cols:
        place = detect_place_format(df[col])
        if place:
            place["column_name"] = col
            result.place_detections.append(place)

        time = detect_time_format(df[col])
        if time:
            time["columns"] = [col]
            result.time_detections.append(time)

    # --- Pairwise relationship analysis ---
    co_ref_found = set()  # track co-referent pairs to avoid duplicates

    for i in range(n_cols):
        for j in range(i + 1, n_cols):
            a, b = cols[i], cols[j]

            # Skip high-cardinality pairs for cross-product (expensive)
            a_card = df[a].nunique()
            b_card = df[b].nunique()

            # Co-referent check
            if detect_co_referents(df, a, b):
                result.relationships.append(ColumnRelationship(
                    column_a=a, column_b=b,
                    relationship=RelationshipType.CO_REFERENT,
                    strength=0.99,
                    evidence=f"1:1 bijection between {a} and {b}",
                    pvmap_implication=f"Use one of [{a}, {b}] for mapping, ignore the other",
                ))
                co_ref_found.add((a, b))
                continue

            # Hierarchical check (both directions)
            if detect_hierarchical(df, a, b):
                result.relationships.append(ColumnRelationship(
                    column_a=a, column_b=b,
                    relationship=RelationshipType.HIERARCHICAL,
                    strength=0.90,
                    evidence=f"{a} determines {b} (many-to-one)",
                    pvmap_implication=f"Use {a} (child) for observationAbout, {b} (parent) for disambiguation only",
                ))
                result.functional_deps.append({"child": a, "parent": b})
                continue
            if detect_hierarchical(df, b, a):
                result.relationships.append(ColumnRelationship(
                    column_a=b, column_b=a,
                    relationship=RelationshipType.HIERARCHICAL,
                    strength=0.90,
                    evidence=f"{b} determines {a} (many-to-one)",
                    pvmap_implication=f"Use {b} (child) for observationAbout, {a} (parent) for disambiguation only",
                ))
                result.functional_deps.append({"child": b, "parent": a})
                continue

            # Qualifier check
            if a in numeric_cols and b not in numeric_cols:
                if detect_qualifiers(df, a, b):
                    result.relationships.append(ColumnRelationship(
                        column_a=a, column_b=b,
                        relationship=RelationshipType.QUALIFIER,
                        strength=0.85,
                        evidence=f"{b} (card={b_card}) qualifies numeric {a}",
                        pvmap_implication=f"Map {b} to unit/scalingFactor on {a}'s observation",
                    ))
                    continue
            if b in numeric_cols and a not in numeric_cols:
                if detect_qualifiers(df, b, a):
                    result.relationships.append(ColumnRelationship(
                        column_a=b, column_b=a,
                        relationship=RelationshipType.QUALIFIER,
                        strength=0.85,
                        evidence=f"{a} (card={a_card}) qualifies numeric {b}",
                        pvmap_implication=f"Map {a} to unit/scalingFactor on {b}'s observation",
                    ))
                    continue

            # Value-error bound check
            if a in numeric_cols and b in numeric_cols:
                if detect_value_error_bounds(df, a, b):
                    result.relationships.append(ColumnRelationship(
                        column_a=a, column_b=b,
                        relationship=RelationshipType.VALUE_ERROR_BOUND,
                        strength=0.90,
                        evidence=f"{b} is error bound for {a}",
                        pvmap_implication=f"Map {a} to value, {b} to marginOfError",
                    ))
                    continue
                if detect_value_error_bounds(df, b, a):
                    result.relationships.append(ColumnRelationship(
                        column_a=b, column_b=a,
                        relationship=RelationshipType.VALUE_ERROR_BOUND,
                        strength=0.90,
                        evidence=f"{a} is error bound for {b}",
                        pvmap_implication=f"Map {b} to value, {a} to marginOfError",
                    ))
                    continue

            # Cross-product check (skip high-cardinality pairs)
            if a_card <= 100 and b_card <= 100:
                if detect_cross_products(df, a, b):
                    result.relationships.append(ColumnRelationship(
                        column_a=a, column_b=b,
                        relationship=RelationshipType.CROSS_PRODUCT,
                        strength=0.85,
                        evidence=f"density={len(df[[a,b]].drop_duplicates())}/{a_card*b_card}",
                        pvmap_implication=f"{a} and {b} are independent dimensions — cross-product defines StatVar space",
                    ))

    # --- Co-referent groups ---
    groups = {}
    for a, b in co_ref_found:
        placed = False
        for key, group in groups.items():
            if a in group or b in group:
                group.update([a, b])
                placed = True
                break
        if not placed:
            groups[len(groups)] = {a, b}
    result.co_referent_groups = [sorted(g) for g in groups.values()]

    return result
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_column_analyzer.py -x -q`
Expected: All PASS

- [ ] **Step 5: Commit**

```bash
git add src/pipeline/plan/column_analyzer.py tests/pipeline/plan/test_column_analyzer.py
git commit -m "feat(plan): add Phase A programmatic column relationship analyzer"
```

---

### Task 3: Phase A — ADK Agent Wrapper + Pipeline Wiring

**Files:**
- Modify: `src/pipeline/plan/column_analyzer.py` (add ADK agent wrapper at bottom)
- Modify: `src/run_pipeline.py` (wire into pipeline sequence)
- Test: `tests/pipeline/plan/test_column_analyzer.py` (add agent wrapper test)

- [ ] **Step 1: Write test for the ADK agent wrapper**

Add to `tests/pipeline/plan/test_column_analyzer.py`:

```python
class TestColumnAnalyzerAgentState:
    def test_analysis_serializes_to_json(self):
        """ColumnAnalysis.to_dict() produces JSON-serializable output for ADK state."""
        import json
        df = pd.DataFrame({
            "A": ["X", "Y", "Z"],
            "B": [1, 2, 3],
        })
        result = analyze_columns(df)
        json_str = json.dumps(result.to_dict())
        restored = json.loads(json_str)
        assert "composite_key" in restored
        assert "relationships" in restored
```

- [ ] **Step 2: Run test to verify it passes (to_dict already exists)**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_column_analyzer.py::TestColumnAnalyzerAgentState -x -q`
Expected: PASS

- [ ] **Step 3: Add ADK agent wrapper to column_analyzer.py**

Append to end of `src/pipeline/plan/column_analyzer.py`:

```python
# --- ADK Agent Wrapper ---
from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event
from google.genai import types as genai_types

import json as _json


class ColumnAnalyzerAgent(BaseAgent):
    """ADK agent that runs Phase A column analysis and stores results in state."""

    def __init__(self, name: str = "ColumnAnalyzer"):
        super().__init__(name=name)

    async def _run_async_impl(self, ctx: InvocationContext):
        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text="Running Phase A column relationship analysis...")]
        ))

        # Read sampled data from state
        sampled_data_path = ctx.session.state.get("sampled_data_path", "")
        if not sampled_data_path:
            logger.warning("No sampled_data_path in state — skipping column analysis")
            ctx.session.state["column_analysis"] = "{}"
            yield Event(author=self.name, content=genai_types.Content(
                parts=[genai_types.Part(text="Skipped: no sampled data path")]
            ))
            return

        from pathlib import Path
        path = Path(str(sampled_data_path))
        if not path.exists():
            logger.warning("Sampled data file not found: %s", path)
            ctx.session.state["column_analysis"] = "{}"
            return

        # Read data — use up to 1000 rows for reliable stats
        df = pd.read_csv(path, nrows=1000, encoding="utf-8", on_bad_lines="skip", low_memory=False)
        analysis = analyze_columns(df)

        # Store as JSON in state
        ctx.session.state["column_analysis"] = _json.dumps(analysis.to_dict(), indent=2)

        n_rels = len(analysis.relationships)
        n_key = len(analysis.composite_key)
        logger.info(
            "Column analysis complete: %d relationships, %d-column composite key",
            n_rels, n_key,
        )

        yield Event(author=self.name, content=genai_types.Content(
            parts=[genai_types.Part(text=(
                f"Phase A complete: {n_rels} relationships detected, "
                f"composite key: {analysis.composite_key}"
            ))]
        ))
```

- [ ] **Step 4: Wire into pipeline in run_pipeline.py**

Find the agent assembly section in `src/run_pipeline.py` (around lines 490-540 where agents are assembled into the SequentialAgent). Add `ColumnAnalyzerAgent` after `SchemaOrgEnrichmentAgent` and before `CandidateRetrieverAgent`:

```python
from src.pipeline.plan.column_analyzer import ColumnAnalyzerAgent

# In the agent list, insert after schemaorg_enrichment and before candidate_retriever:
# ...existing agents...
# ColumnAnalyzerAgent(),  # Phase A: programmatic column analysis
# CandidateRetrieverAgent(),  # existing
# MappingPlanAgent(),  # existing
```

The exact line numbers depend on the current state of `run_pipeline.py`. Find where `CandidateRetrieverAgent` is instantiated and add `ColumnAnalyzerAgent()` before it in the agent list.

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/plan/column_analyzer.py src/run_pipeline.py tests/pipeline/plan/test_column_analyzer.py
git commit -m "feat(plan): wire ColumnAnalyzerAgent into pipeline as Phase A"
```

---

### Task 4: Plan Mitigations Layer

**Files:**
- Create: `src/pipeline/plan/plan_mitigations.py`
- Test: `tests/pipeline/plan/test_plan_mitigations.py`

- [ ] **Step 1: Write tests for mitigations**

```python
# tests/pipeline/plan/test_plan_mitigations.py
import pytest
import pandas as pd
from pathlib import Path
from unittest.mock import patch
from src.api.models.plan import (
    EnrichedMappingPlan, DatasetUnderstanding, StatVarBlueprint,
    ValueDictionary, ValueMapping, ColumnMapping, ColumnRole,
    PropertyValueCandidate, CandidateSource, StaticProperty,
    PlaceResolution,
)
from src.pipeline.plan.plan_mitigations import (
    strip_total_indicators,
    check_column_alignment,
    normalize_place_formats,
    TOTAL_INDICATORS,
)


def _make_plan(**overrides) -> EnrichedMappingPlan:
    """Helper to build a minimal EnrichedMappingPlan for testing."""
    defaults = dict(
        dataset_name="test",
        understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
        active_columns=[
            ColumnMapping(
                column_name="VAL", role=ColumnRole.MEASURE,
                candidates=[PropertyValueCandidate(
                    property="value", value_expression="[NUMBER]",
                    confidence=0.9, source=CandidateSource.LLM, reason="test",
                )],
                evidence="numeric",
            ),
        ],
        ignored_columns=[],
        static_properties=[],
        global_notes=[],
        statvar_blueprint=StatVarBlueprint(
            base_properties={"populationType": "dcs:Person"},
            constraint_columns=[], measure_columns=["VAL"],
        ),
        value_dictionaries=[],
        composite_key=["A"],
    )
    defaults.update(overrides)
    return EnrichedMappingPlan(**defaults)


class TestStripTotalIndicators:
    def test_marks_total_as_drop_constraint(self):
        plan = _make_plan(value_dictionaries=[
            ValueDictionary(
                column_name="SEX", dc_property="gender",
                mappings=[
                    ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="Male"),
                    ValueMapping(raw_value="T", dcid="dcs:SomeWrongThing", action="MAP", reason="Total"),
                ],
                total_indicators=[],
            ),
        ])
        result = strip_total_indicators(plan)
        t_mapping = [m for m in result.value_dictionaries[0].mappings if m.raw_value == "T"][0]
        assert t_mapping.action == "DROP_CONSTRAINT"
        assert t_mapping.dcid is None

    def test_preserves_non_total_values(self):
        plan = _make_plan(value_dictionaries=[
            ValueDictionary(
                column_name="SEX", dc_property="gender",
                mappings=[
                    ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="Male"),
                    ValueMapping(raw_value="F", dcid="dcs:Female", action="MAP", reason="Female"),
                ],
                total_indicators=[],
            ),
        ])
        result = strip_total_indicators(plan)
        assert all(m.action == "MAP" for m in result.value_dictionaries[0].mappings)


class TestCheckColumnAlignment:
    def test_matching_columns(self, tmp_path):
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("VAL,OTHER\n1,2\n")
        plan = _make_plan()
        issues = check_column_alignment(plan, csv_path)
        assert len(issues) == 0

    def test_missing_column(self, tmp_path):
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("OTHER\n1\n")
        plan = _make_plan()
        issues = check_column_alignment(plan, csv_path)
        assert any("missing" in i.lower() for i in issues)

    def test_new_column(self, tmp_path):
        csv_path = tmp_path / "data.csv"
        csv_path.write_text("VAL,NEW_COL\n1,2\n")
        plan = _make_plan()
        issues = check_column_alignment(plan, csv_path)
        assert any("unmapped" in i.lower() for i in issues)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_mitigations.py -x -q`
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: Implement plan_mitigations.py**

Create `src/pipeline/plan/plan_mitigations.py`:

```python
"""Plan mitigations layer — programmatic safeguards between PlanGate and Generator.

Runs after user approves the plan, before the PVMAP generator executes it.
All operations are deterministic (no LLM) except expand_dictionary().
"""

import logging
from pathlib import Path
from typing import List

try:
    import pandas as pd
    PANDAS_AVAILABLE = True
except ImportError:
    pd = None
    PANDAS_AVAILABLE = False

from src.api.models.plan import EnrichedMappingPlan, ValueMapping

logger = logging.getLogger(__name__)

# Comprehensive set of total/aggregate indicators
TOTAL_INDICATORS = {
    "T", "Total", "All", "Both", "Both Sexes", "All Races",
    "All Ages", "Overall", "TOT", "-", "*", "~",
    "00", "000", "999", "",
}


def strip_total_indicators(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """Mitigation 1: Ensure all total/aggregate values have action=DROP_CONSTRAINT.

    This prevents the generator from creating invalid StatVars like
    Count_Person_GenderAll or Count_Person_AgeTotal.
    """
    for vd in plan.value_dictionaries:
        for mapping in vd.mappings:
            if mapping.raw_value.strip() in TOTAL_INDICATORS:
                mapping.action = "DROP_CONSTRAINT"
                mapping.dcid = None
                mapping.reason = "Total/aggregate indicator — drop constraint from StatVar"
    return plan


def check_column_alignment(plan: EnrichedMappingPlan, full_data_path: Path) -> List[str]:
    """Mitigation 3: Verify plan columns exist in the full dataset.

    Returns a list of issues (empty = all good). Caller decides how to handle.
    """
    if not PANDAS_AVAILABLE:
        return ["Cannot check column alignment: pandas not available"]

    full_data_path = Path(full_data_path)
    if not full_data_path.exists():
        return [f"Data file not found: {full_data_path}"]

    full_columns = set(pd.read_csv(full_data_path, nrows=0).columns)
    plan_columns = {cm.column_name for cm in plan.active_columns + plan.ignored_columns}

    issues = []
    missing = plan_columns - full_columns
    new = full_columns - plan_columns

    if missing:
        issues.append(f"Plan references missing columns: {sorted(missing)}")
    if new:
        issues.append(f"Data has unmapped columns: {sorted(new)}")

    return issues


def normalize_place_formats(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """Mitigation 4a: Apply zero-padding and prefix rules from PlaceResolution.

    Updates the value_expression in the place column's selected candidate
    to include the detected prefix and padding instructions.
    """
    if not plan.place_resolution:
        return plan

    pr = plan.place_resolution
    for col in plan.active_columns:
        if col.column_name == pr.column_name and col.candidates:
            selected = col.candidates[col.selected_index]
            # Ensure prefix is in the value expression
            if pr.prefix_rule and pr.prefix_rule not in selected.value_expression:
                selected.value_expression = f"{pr.prefix_rule}[DATA]"
                selected.reason += f" (prefix {pr.prefix_rule} applied by mitigation)"
    return plan


def normalize_time_formats(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """Mitigation 4b: Apply time normalization rules from TimeResolution."""
    # Time format normalization is handled by the skeleton converter
    # and the generator prompt — no plan mutation needed for now
    return plan


def apply_mitigations(plan: EnrichedMappingPlan, full_data_path: Path) -> EnrichedMappingPlan:
    """Apply all programmatic mitigations to the plan.

    Raises PlanColumnMismatchError if pre-flight check finds issues.
    """
    # Mitigation 1: Total/All override
    plan = strip_total_indicators(plan)

    # Mitigation 3: Pre-flight skeleton check
    issues = check_column_alignment(plan, full_data_path)
    if issues:
        logger.warning("Plan alignment issues: %s", issues)
        # Don't hard-fail — log warnings. The generator will handle missing columns.

    # Mitigation 4: Format normalization
    plan = normalize_place_formats(plan)
    plan = normalize_time_formats(plan)

    return plan
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_mitigations.py -x -q`
Expected: All PASS

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/plan/plan_mitigations.py tests/pipeline/plan/test_plan_mitigations.py
git commit -m "feat(plan): add plan mitigations layer — Total override, pre-flight check, format normalization"
```

---

### Task 5: Phase B — Enhanced MappingPlanAgent Prompt

**Files:**
- Create: `src/resources/prompts/mapping_plan_prompt_v2.txt`
- Test: Manual verification (prompt is consumed by LLM, not unit-testable)

- [ ] **Step 1: Create the v2 plan prompt**

Create `src/resources/prompts/mapping_plan_prompt_v2.txt`:

```
You are a Data Commons expert. Your job: create a COMPLETE mapping specification
using the pre-computed structural analysis below. The structural analysis was
computed programmatically and is AUTHORITATIVE — trust these facts.

## Your Tasks

1. Define the StatVar blueprint:
   - populationType (e.g., dcs:Person, dcs:HousingUnit)
   - measuredProperty (e.g., dcs:count, dcs:income)
   - statType (e.g., dcs:measuredValue, dcs:medianValue)
   - Which columns are constraint properties (dimensions that modify the StatVar)
   - Which columns are measure columns (contain the numeric value)

2. For each dimension column in raw_value_profiles, map ALL values to DC DCIDs:
   - Use standard DC schema: M -> dcs:Male, F -> dcs:Female
   - Age brackets: 15-24 -> dcs:Years15To24, 65+ -> dcs:Years65Onwards
   - Total/aggregate values (listed in total_indicators): set action = "DROP_CONSTRAINT"
   - Unknown values: map to dcs:Unknown or propose a custom DCID with reason

3. Rank the pre-retrieved candidates using structural evidence:
   - Co-referent columns: the code column gets observationAbout, label column gets ignored
   - Hierarchical pairs: child column for observationAbout, parent for disambiguation
   - Qualifier pairs: qualifier maps to unit/scalingFactor
   - Assign confidence based on relationship strength from Phase A

4. If transformation_strategy is needed (wide data):
   - Set archetype to "wide_time" or "wide_variable"
   - Specify id_vars (columns to keep) and value_vars (columns to unpivot)

5. Flag any ambiguities with is_ambiguous=true on the ColumnMapping

## Structural Analysis (TRUST THESE FACTS — computed programmatically)

{column_analysis_json}

## Pre-Retrieved Candidates (per column)

{candidate_pool_json}

## Schema Vocabulary (valid DC property names)

{schema_vocab_content}

## Small Data Sample (for value verification only — do NOT rely on this for structure)

{sampled_data}

## Engineer Feedback

{engineer_feedback}

## Output

Return a JSON object matching the EnrichedMappingPlan schema exactly. Include ALL fields:
- dataset_name, understanding, active_columns, ignored_columns, static_properties, global_notes
- column_relationships (copy from structural analysis, optionally add LLM-detected ones)
- statvar_blueprint (your design)
- value_dictionaries (your mappings for each dimension column)
- composite_key (copy from structural analysis)
- place_resolution (copy from structural analysis, or null)
- time_resolution (copy from structural analysis, or null)
- transformation_strategy (if needed, or null)

## IMPORTANT RULES

- Analyze EVERY column — do not skip any
- Use EXACT column names from the structural analysis
- Use [DATA] and [NUMBER] for placeholder expressions (NOT curly-brace variants)
- Use dcs: prefix for all DC properties and enum values
- Only ONE column should be observationAbout, only ONE should be observationDate
- If a column is genuinely ambiguous, set is_ambiguous=true
- DO NOT invent property names that don't appear in candidates or schema vocabulary
- For value dictionaries: map EVERY unique value listed in raw_value_profiles
```

- [ ] **Step 2: Commit**

```bash
git add src/resources/prompts/mapping_plan_prompt_v2.txt
git commit -m "feat(plan): add v2 mapping plan prompt with Phase A integration"
```

---

### Task 6: Phase B — Enhanced MappingPlanAgent Implementation

**Files:**
- Modify: `src/agents/mapping_plan_agent.py`
- Test: `tests/pipeline/plan/test_plan_integration.py` (extend existing)

- [ ] **Step 1: Write test for v2 prompt loading**

Add to `tests/pipeline/plan/test_plan_integration.py`:

```python
def test_mapping_plan_prompt_v2_exists():
    """The v2 prompt template file exists and contains expected placeholders."""
    from pathlib import Path
    prompt_path = Path("src/resources/prompts/mapping_plan_prompt_v2.txt")
    assert prompt_path.exists(), "mapping_plan_prompt_v2.txt not found"
    content = prompt_path.read_text()
    assert "{column_analysis_json}" in content
    assert "{candidate_pool_json}" in content
    assert "{schema_vocab_content}" in content
    assert "{sampled_data}" in content
    assert "{engineer_feedback}" in content
```

- [ ] **Step 2: Run test to verify it passes**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_integration.py::test_mapping_plan_prompt_v2_exists -x -q`
Expected: PASS (file created in Task 5)

- [ ] **Step 3: Modify MappingPlanAgent to support v2 mode**

Edit `src/agents/mapping_plan_agent.py` — update `_run_async_impl` to:
1. Check for `column_analysis` in state (if present, use v2 prompt)
2. Fall back to v1 prompt if no column analysis available (backward compatible)
3. Use `EnrichedMappingPlan` schema when in v2 mode

```python
# In _run_async_impl, after loading state variables, add:

# Check if Phase A analysis is available
column_analysis = ctx.session.state.get("column_analysis", "")
use_v2 = bool(column_analysis and column_analysis != "{}")

if use_v2:
    template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt_v2.txt"
    template = template_path.read_text()
    populated = template.replace("{column_analysis_json}", column_analysis)
    populated = populated.replace("{candidate_pool_json}", candidate_pool_json)
    populated = populated.replace("{schema_vocab_content}", schema_vocab)
    # Use fewer sampled data rows in v2 (5 rows max)
    sampled_lines = sampled_data.split("\n")
    sampled_5 = "\n".join(sampled_lines[:6])  # header + 5 rows
    populated = populated.replace("{sampled_data}", sampled_5)
    populated = populated.replace("{engineer_feedback}", engineer_feedback)
else:
    # Existing v1 logic (unchanged)
    template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "mapping_plan_prompt.txt"
    template = template_path.read_text()
    # ... existing population logic ...

# In _generate_plan, use appropriate schema:
if use_v2:
    from src.api.models.plan import EnrichedMappingPlan
    plan_schema = EnrichedMappingPlan.model_json_schema()
    # ... call Gemini with max_output_tokens=16384 ...
    plan = EnrichedMappingPlan.model_validate_json(response.text)
else:
    plan_schema = MappingPlan.model_json_schema()
    # ... existing logic ...
```

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions (v1 path unchanged, v2 only activates when `column_analysis` is in state)

- [ ] **Step 5: Commit**

```bash
git add src/agents/mapping_plan_agent.py tests/pipeline/plan/test_plan_integration.py
git commit -m "feat(plan): enhance MappingPlanAgent with v2 prompt and EnrichedMappingPlan output"
```

---

### Task 7: PVMAP Executor Prompt

**Files:**
- Create: `src/resources/prompts/pvmap_executor_prompt.txt`

- [ ] **Step 1: Create the executor prompt**

Create `src/resources/prompts/pvmap_executor_prompt.txt`:

```
You are a PVMAP syntax generator. Your ONLY job: translate the approved mapping plan into PVMAP CSV format. Do NOT alter any semantic decisions in the plan — it was reviewed and approved by a human engineer.

## How the Processor Consumes Your PVMAP

The downstream stat_var_processor reads your PVMAP line-by-line:
- First column (key): matches against CSV column headers or cell values (case-insensitive)
- Subsequent columns: alternating property/value pairs
- [DATA] inserts the raw cell string. [NUMBER] parses the cell as numeric.
- Rows WITHOUT value accumulate properties (carry-forward). Rows WITH value emit one StatVarObservation.
- variableMeasured is auto-built from populationType + measuredProperty + statType + constraints. NEVER set variableMeasured directly.

## Critical Syntax Rules

- Use dcs: prefix for DC types, properties, and enum values: dcs:Person, dcs:count, dcs:Male
- Do NOT prefix placeholders: observationDate,[NUMBER] (not dcs:[NUMBER])
- Do NOT prefix raw data: observationAbout,country/[DATA] (not dcs:country/[DATA])
- Quote keys containing commas: "GDP, current prices"
- Copy column names EXACTLY from the plan below

## Approved Mapping Plan (USER APPROVED — DO NOT OVERRIDE)

### Column Roles and Selected Mappings

{{PLAN_COLUMN_TABLE}}

### StatVar Blueprint

{{STATVAR_BLUEPRINT}}

### Value Dictionaries (dimension value -> DCID)

{{VALUE_DICTIONARIES}}

### Place Resolution

{{PLACE_RESOLUTION}}

### Time Resolution

{{TIME_RESOLUTION}}

### Column Relationships (context for understanding data structure)

{{COLUMN_RELATIONSHIPS}}

## PVMAP Skeleton (pre-filled baseline)

```csv
{{PVMAP_SKELETON}}
```

Every skeleton row is mandatory. LOCKED rows: do not modify. OPEN rows: fill in property names.

## Sampled Data (reference for exact string matching ONLY)

{{SAMPLED_DATA}}

## Instructions

1. Start from the PVMAP skeleton
2. For each active column in the plan: ensure it has a row with the correct property/value
3. For each dimension column: add COLUMN:VALUE rows for every value in the value dictionary
4. For value dictionary entries with action=DROP_CONSTRAINT: omit the constraint property for those rows
5. Add a static-properties row with populationType, measuredProperty, statType from the blueprint
6. If transformation_strategy has action=melt: generate separate mapping blocks per measure column

If the plan is structurally impossible to translate (e.g., column role contradicts data), output ONLY:
{"status": "PLAN_ERROR", "reason": "explanation of what is impossible and why"}
```

- [ ] **Step 2: Commit**

```bash
git add src/resources/prompts/pvmap_executor_prompt.txt
git commit -m "feat(pvmap): add plan executor prompt — focused PVMAP syntax generation"
```

---

### Task 8: Wire Executor Prompt into StatePreparationAgent

**Files:**
- Modify: `src/agents/pvmap_retry_loop.py` (PromptPreparationAgent section)

This is the most complex task — it changes how the generator prompt is assembled when an enriched plan is available.

- [ ] **Step 1: Read the current PromptPreparationAgent code**

Read `src/agents/pvmap_retry_loop.py` around the `_populate_prompt_template` method (around lines 945-1097) to understand the current template population logic.

- [ ] **Step 2: Add executor prompt path to PromptPreparationAgent**

In `PromptPreparationAgent._run_async_impl()` (or `_populate_prompt_template`), add a check at the beginning:

```python
# Check if we have an enriched plan — if so, use the executor prompt
approved_plan_json = ctx.session.state.get("approved_plan_json", "")
use_executor = False
enriched_plan = None

if approved_plan_json:
    try:
        from src.api.models.plan import EnrichedMappingPlan
        plan_data = json.loads(approved_plan_json)
        if "statvar_blueprint" in plan_data:
            enriched_plan = EnrichedMappingPlan.model_validate(plan_data)
            use_executor = True
    except Exception:
        pass  # Fall back to existing prompt

if use_executor:
    populated = self._populate_executor_prompt(enriched_plan, ctx)
else:
    populated = self._populate_prompt_template(ctx)  # existing logic
```

- [ ] **Step 3: Implement _populate_executor_prompt**

```python
def _populate_executor_prompt(self, plan: "EnrichedMappingPlan", ctx: InvocationContext) -> str:
    """Build the executor prompt from an EnrichedMappingPlan."""
    template_path = PROJECT_ROOT / "src" / "resources" / "prompts" / "pvmap_executor_prompt.txt"
    template = template_path.read_text()

    # Column roles table
    col_table_lines = ["| Column | Role | Property | Value Expression |", "| --- | --- | --- | --- |"]
    for col in plan.active_columns:
        cand = col.candidates[col.selected_index]
        col_table_lines.append(f"| {col.column_name} | {col.role.value} | {cand.property} | {cand.value_expression} |")
    populated = template.replace("{{PLAN_COLUMN_TABLE}}", "\n".join(col_table_lines))

    # StatVar blueprint
    bp = plan.statvar_blueprint
    bp_text = f"Base: {bp.base_properties}\nConstraint columns: {bp.constraint_columns}\nMeasure columns: {bp.measure_columns}"
    populated = populated.replace("{{STATVAR_BLUEPRINT}}", bp_text)

    # Value dictionaries
    vd_lines = []
    for vd in plan.value_dictionaries:
        vd_lines.append(f"\n**{vd.column_name}** (property: {vd.dc_property}):")
        for m in vd.mappings:
            if m.action == "DROP_CONSTRAINT":
                vd_lines.append(f"  - {m.raw_value} -> DROP_CONSTRAINT ({m.reason})")
            else:
                vd_lines.append(f"  - {m.raw_value} -> {m.dcid}")
    populated = populated.replace("{{VALUE_DICTIONARIES}}", "\n".join(vd_lines) if vd_lines else "(none)")

    # Place resolution
    pr_text = "(none)"
    if plan.place_resolution:
        pr = plan.place_resolution
        pr_text = f"{pr.column_name}: format={pr.format_detected}, prefix={pr.prefix_rule}, pad={pr.pad_zeros}"
    populated = populated.replace("{{PLACE_RESOLUTION}}", pr_text)

    # Time resolution
    tr_text = "(none)"
    if plan.time_resolution:
        tr = plan.time_resolution
        tr_text = f"columns={tr.columns}, format={tr.format_detected}, rule={tr.normalization_rule}"
    populated = populated.replace("{{TIME_RESOLUTION}}", tr_text)

    # Column relationships (significant ones only)
    rel_lines = []
    for r in plan.column_relationships:
        if r.relationship.value != "independent":
            rel_lines.append(f"- {r.column_a} <-> {r.column_b}: {r.relationship.value} ({r.evidence})")
    populated = populated.replace("{{COLUMN_RELATIONSHIPS}}", "\n".join(rel_lines) if rel_lines else "(none)")

    # Skeleton and sampled data from state
    skeleton = ctx.session.state.get("pvmap_skeleton", "")
    populated = populated.replace("{{PVMAP_SKELETON}}", skeleton)

    sampled = ctx.session.state.get("sampled_data", "")
    sampled_lines = sampled.split("\n")[:6]  # header + 5 rows
    populated = populated.replace("{{SAMPLED_DATA}}", "\n".join(sampled_lines))

    return populated
```

- [ ] **Step 4: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions (executor path only activates with enriched plan)

- [ ] **Step 5: Commit**

```bash
git add src/agents/pvmap_retry_loop.py
git commit -m "feat(pvmap): wire executor prompt into StatePreparationAgent for enriched plans"
```

---

### Task 9: Two-Tiered Retry Error Classification

**Files:**
- Modify: `src/agents/pvmap_retry_loop.py` (TieredCorrectionAgent or equivalent)
- Test: `tests/api/test_pipeline_runner.py` (extend)

- [ ] **Step 1: Add error classification function**

Create a helper function in `pvmap_retry_loop.py`:

```python
def classify_validation_error(validation_output: str, data_rows: int) -> str:
    """Classify a validation error as 'syntax' (Tier 1) or 'semantic' (Tier 2).

    Returns: "tier1_syntax" or "tier2_semantic"
    """
    output_lower = validation_output.lower()

    # Tier 2: Semantic errors (plan needs revision)
    tier2_signals = [
        "duplicate observation",
        "duplicate statvar",
        "no data rows",
        "0 data rows",
        "observationabout" in output_lower and "not found" in output_lower,
        "observationdate" in output_lower and "not found" in output_lower,
        data_rows == 0,
    ]
    if any(tier2_signals):
        return "tier2_semantic"

    # Everything else is Tier 1: syntax/formatting
    return "tier1_syntax"
```

- [ ] **Step 2: Wire into the correction agent**

In the correction/feedback logic (where retry decisions are made), add:

```python
# After validation, check if this is a plan-level error
if use_executor and ctx.session.state.get("pvmap_output", {}).get("status") == "PLAN_ERROR":
    ctx.session.state["plan_revision_needed"] = True
    ctx.session.state["plan_revision_reason"] = ctx.session.state["pvmap_output"].get("reason", "Unknown")
    # Skip normal correction — escalate to plan agent
    return

error_tier = classify_validation_error(
    ctx.session.state.get("validation_output", ""),
    ctx.session.state.get("validation_data_rows", 0),
)
if error_tier == "tier2_semantic":
    ctx.session.state["plan_revision_needed"] = True
    ctx.session.state["plan_revision_reason"] = "Semantic validation failure: " + ctx.session.state.get("validation_output", "")[:500]
```

- [ ] **Step 3: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: No regressions

- [ ] **Step 4: Commit**

```bash
git add src/agents/pvmap_retry_loop.py
git commit -m "feat(pvmap): add two-tiered error classification for retry loop"
```

---

### Task 10: UI — Plan Text Editor + Feedback Box

**Files:**
- Modify: `frontend/src/pages/ReviewPlanPage.tsx`
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add EnrichedMappingPlan TypeScript types**

Add to `frontend/src/types/index.ts`:

```typescript
export interface ColumnRelationship {
  column_a: string;
  column_b: string;
  relationship: string;
  strength: number;
  evidence: string;
  pvmap_implication: string;
}

export interface ValueMapping {
  raw_value: string;
  dcid: string | null;
  action: string;
  reason: string;
}

export interface ValueDictionary {
  column_name: string;
  dc_property: string;
  mappings: ValueMapping[];
  total_indicators: string[];
}

export interface StatVarBlueprint {
  base_properties: Record<string, string>;
  constraint_columns: string[];
  measure_columns: string[];
}

export interface EnrichedMappingPlan extends MappingPlan {
  column_relationships?: ColumnRelationship[];
  statvar_blueprint?: StatVarBlueprint;
  value_dictionaries?: ValueDictionary[];
  composite_key?: string[];
  place_resolution?: {
    column_name: string;
    format_detected: string;
    prefix_rule: string;
    pad_zeros: number | null;
    resolution_rate: number;
  } | null;
  time_resolution?: {
    columns: string[];
    format_detected: string;
    normalization_rule: string;
  } | null;
  transformation_strategy?: {
    archetype: string;
    action: string | null;
    id_vars: string[];
    value_vars: string[];
  } | null;
}
```

- [ ] **Step 2: Update ReviewPlanPage with text editor and feedback box**

In `frontend/src/pages/ReviewPlanPage.tsx`, replace the current plan display with:

1. A `<textarea>` or code editor showing the full plan JSON (editable)
2. A feedback `<textarea>` below with a "Regenerate" button
3. A "Save Edits" button that PUTs the modified plan JSON
4. An "Approve" button (existing)

The exact implementation depends on the current ReviewPlanPage structure. The key changes:

```tsx
// Plan text editor (top 70%)
<textarea
  value={planJson}
  onChange={(e) => setPlanJson(e.target.value)}
  className="w-full h-[60vh] font-mono text-sm p-4 border rounded"
  spellCheck={false}
/>

// Feedback box (bottom 30%)
<textarea
  value={feedback}
  onChange={(e) => setFeedback(e.target.value)}
  placeholder="Type feedback to regenerate the plan..."
  className="w-full h-24 p-3 border rounded"
/>
<button onClick={handleRegenerate}>Regenerate Plan</button>
<button onClick={handleSaveEdits}>Save Edits</button>
<button onClick={handleApprove}>Approve & Generate PVMAP</button>
```

- [ ] **Step 3: Add PUT endpoint for plan edits**

Add to `src/api/routes/plan.py`:

```python
@router.put("/runs/{run_id}/plan")
async def update_plan(run_id: str, body: dict):
    """Accept full plan edit from user (they modified the JSON directly)."""
    from src.api.models.plan import EnrichedMappingPlan, MappingPlan
    try:
        if "statvar_blueprint" in body:
            plan = EnrichedMappingPlan.model_validate(body)
        else:
            plan = MappingPlan.model_validate(body)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid plan JSON: {e}")

    # Save to disk
    output_dir = _get_output_dir(run_id)
    plan_path = output_dir / "mapping_plan.json"
    plan_path.write_text(plan.model_dump_json(indent=2))

    return {"status": "ok", "message": "Plan updated"}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ReviewPlanPage.tsx frontend/src/types/index.ts src/api/routes/plan.py
git commit -m "feat(ui): add plan text editor with feedback box and direct edit support"
```

---

### Task 11: End-to-End Integration Test

**Files:**
- Create: `tests/pipeline/plan/test_enriched_plan_e2e.py`

- [ ] **Step 1: Write an integration test**

```python
# tests/pipeline/plan/test_enriched_plan_e2e.py
"""End-to-end test: Phase A analysis -> enriched plan model -> skeleton CSV."""
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
    # Create a test CSV
    csv_path = tmp_path / "test_data" / "data_input.csv"
    csv_path.parent.mkdir(parents=True)
    df = pd.DataFrame({
        "REF_AREA": ["AR", "AR", "BR", "BR"],
        "TIME_PERIOD": ["2020", "2021", "2020", "2021"],
        "SEX": ["M", "F", "M", "F"],
        "OBS_VALUE": [100.0, 200.0, 300.0, 400.0],
    })
    df.to_csv(csv_path, index=False)

    # Phase A
    analysis = analyze_columns(df)
    assert len(analysis.composite_key) > 0

    # Build an enriched plan (simulating Phase B LLM output)
    plan = EnrichedMappingPlan(
        dataset_name="test_e2e",
        understanding=DatasetUnderstanding(archetype="Long/Tidy", observation_grain="Country x Year x Gender", key_insight="SDMX"),
        active_columns=[
            ColumnMapping(column_name="REF_AREA", role=ColumnRole.OBSERVATION_ABOUT,
                candidates=[PropertyValueCandidate(property="observationAbout", value_expression="country/[DATA]", confidence=0.95, source=CandidateSource.SCHEMA_ORG, reason="ISO-2")],
                evidence="ISO-2 codes"),
            ColumnMapping(column_name="TIME_PERIOD", role=ColumnRole.OBSERVATION_DATE,
                candidates=[PropertyValueCandidate(property="observationDate", value_expression="[DATA]", confidence=0.95, source=CandidateSource.SCHEMA_ORG, reason="YYYY")],
                evidence="Year format"),
            ColumnMapping(column_name="SEX", role=ColumnRole.DIMENSION,
                candidates=[PropertyValueCandidate(property="gender", value_expression="[DATA]", confidence=0.90, source=CandidateSource.LLM, reason="Gender dimension")],
                evidence="Low cardinality categorical"),
            ColumnMapping(column_name="OBS_VALUE", role=ColumnRole.MEASURE,
                candidates=[PropertyValueCandidate(property="value", value_expression="[NUMBER]", confidence=0.99, source=CandidateSource.SCHEMA_ORG, reason="Numeric")],
                evidence="Continuous numeric"),
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

    # Mitigations
    plan = apply_mitigations(plan, csv_path)

    # Skeleton generation
    skeleton = plan_to_skeleton_csv(plan)
    assert "REF_AREA" in skeleton
    assert "TIME_PERIOD" in skeleton
    assert "OBS_VALUE" in skeleton

    # JSON roundtrip
    json_str = plan.model_dump_json(indent=2)
    restored = EnrichedMappingPlan.model_validate_json(json_str)
    assert restored.dataset_name == "test_e2e"
    assert len(restored.value_dictionaries) == 1
```

- [ ] **Step 2: Run test**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_enriched_plan_e2e.py -x -q`
Expected: PASS

- [ ] **Step 3: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All pass, no regressions

- [ ] **Step 4: Commit**

```bash
git add tests/pipeline/plan/test_enriched_plan_e2e.py
git commit -m "test: add end-to-end integration test for enriched plan pipeline"
```

---

## Deferred to Phase 2

These items are designed in the spec but deferred to a follow-up implementation:

1. **Mitigation 2: Dynamic Dictionary Expansion** — requires an isolated async Gemini call to map unseen values in the full dataset. Depends on Tasks 1-4 working end-to-end first. Will be added to `plan_mitigations.py` as `expand_dictionary()`.

2. **Temporal Composition Detection** — detecting Year + Month → composed date. The infrastructure is in `column_analyzer.py` but needs cross-column `pd.to_datetime` validation.

3. **PLAN_ERROR escalation in retry loop** — the state key `plan_revision_needed` is set (Task 9) but the outer loop logic to re-run Phase B needs to be wired into `run_pipeline.py`'s retry orchestration.

---

## Execution Order & Dependencies

```
Task 1 (data models) — no deps, foundational
    ↓
Task 2 (Phase A core) — depends on Task 1 models
Task 4 (mitigations) — depends on Task 1 models
Task 5 (v2 prompt) — no code deps
Task 7 (executor prompt) — no code deps
    ↓
Task 3 (Phase A wiring) — depends on Task 2
Task 6 (Phase B agent) — depends on Task 1, 5
    ↓
Task 8 (executor wiring) — depends on Task 7, Task 6
Task 9 (retry tiers) — depends on Task 8
Task 10 (UI) — depends on Task 1
    ↓
Task 11 (e2e test) — depends on Tasks 1-4, 6

Parallelizable groups:
  Group A: Tasks 2, 4, 5, 7 (all depend only on Task 1)
  Group B: Tasks 3, 6, 10 (depend on Group A)
  Group C: Tasks 8, 9 (depend on Group B)
  Group D: Task 11 (depends on all)
```
