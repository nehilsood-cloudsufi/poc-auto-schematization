# Understanding-First Plan (v4) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the mapping plan a two-layer document — human-readable understanding on top (executive summary + column narratives), machine-readable execution on the bottom (roles with purpose) — and eliminate "ignored" columns.

**Architecture:** Add `executive_summary` to `DatasetUnderstanding`, add `purpose` and `narrative` fields to `ColumnMapping`, remove `IGNORED` from `ColumnRole` enum (keep backward compat via string parsing), update the plan prompt to generate understanding before roles, update markdown rendering.

**Tech Stack:** Pydantic models, Gemini structured output prompt, Python

**Spec:** `docs/superpowers/specs/2026-04-14-understanding-first-plan-design.md`

---

## File Structure

| File | Change |
|------|--------|
| `src/api/models/plan.py` | Add fields to `DatasetUnderstanding` and `ColumnMapping`, deprecate `IGNORED` role |
| `src/agents/mapping_plan_agent.py` | Update `_plan_to_markdown()` for executive summary + column narratives |
| `src/resources/prompts/mapping_plan_prompt_v2.txt` | Add understanding-first preamble, purpose taxonomy, remove "ignored" logic |
| `tests/api/models/test_plan_models.py` | Tests for new fields |
| `tests/pipeline/plan/test_plan_markdown.py` | Tests for new markdown sections |

---

### Task 1: Add `executive_summary`, `purpose`, `narrative` fields to models

**Files:**
- Modify: `src/api/models/plan.py`
- Modify: `tests/api/models/test_plan_models.py`

- [ ] **Step 1: Write tests for new fields**

Add to `tests/api/models/test_plan_models.py`:

```python
class TestDatasetUnderstandingV4:
    def test_executive_summary_default_empty(self):
        du = DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test")
        assert du.executive_summary == ""

    def test_executive_summary_set(self):
        du = DatasetUnderstanding(
            archetype="Dimension-Row",
            observation_grain="Country x Year x Variable",
            key_insight="UNIDO industrial statistics",
            executive_summary="This dataset tracks industrial economic indicators for India and USA across 2014-2023.",
        )
        assert "industrial" in du.executive_summary


class TestColumnMappingV4:
    def test_purpose_and_narrative_default_empty(self):
        col = ColumnMapping(
            column_name="Year", role=ColumnRole.OBSERVATION_DATE,
            candidates=[PropertyValueCandidate(
                property="observationDate", value_expression="[NUMBER]",
                confidence=0.95, source=CandidateSource.SCHEMA_ORG, reason="test",
            )],
            evidence="YYYY format",
        )
        assert col.purpose == ""
        assert col.narrative == ""

    def test_purpose_and_narrative_set(self):
        col = ColumnMapping(
            column_name="Country",
            role=ColumnRole.DIMENSION,
            candidates=[],
            evidence="Human-readable name",
            purpose="Entity Resolution Helper",
            narrative="Human-readable country name used to resolve CountryCode to DC place DCIDs.",
        )
        assert col.purpose == "Entity Resolution Helper"
        assert "resolve" in col.narrative

    def test_purpose_on_former_ignored_column(self):
        """Columns that were 'ignored' now get a real role + purpose."""
        col = ColumnMapping(
            column_name="CountryCode_Label",
            role=ColumnRole.DIMENSION,
            candidates=[],
            evidence="Alias for CountryCode",
            purpose="Entity Resolution Helper",
            narrative="Co-referent with CountryCode. Provides human name for DCID fallback.",
        )
        assert col.role == ColumnRole.DIMENSION
        assert col.purpose == "Entity Resolution Helper"


class TestColumnRoleDeprecation:
    def test_ignored_still_parses(self):
        """Backward compat: existing plans with IGNORED still parse."""
        col = ColumnMapping(
            column_name="RowID",
            role=ColumnRole.IGNORED,
            candidates=[],
            evidence="Internal ID",
        )
        assert col.role == ColumnRole.IGNORED

    def test_metadata_role_exists(self):
        """Metadata role is preferred over ignored for qualifier columns."""
        col = ColumnMapping(
            column_name="UnitType",
            role=ColumnRole.METADATA,
            candidates=[],
            evidence="M=monetary, N=count",
            purpose="Observation Qualifier",
            narrative="Determines unit and measuredProperty of Value column.",
        )
        assert col.role == ColumnRole.METADATA
        assert col.purpose == "Observation Qualifier"


class TestV4JsonRoundtrip:
    def test_new_fields_survive_roundtrip(self):
        plan = MappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(
                archetype="Long", observation_grain="row", key_insight="test",
                executive_summary="A test dataset for roundtrip.",
            ),
            active_columns=[
                ColumnMapping(
                    column_name="Year", role=ColumnRole.OBSERVATION_DATE,
                    candidates=[PropertyValueCandidate(
                        property="observationDate", value_expression="[NUMBER]",
                        confidence=0.95, source=CandidateSource.SCHEMA_ORG, reason="test",
                    )],
                    evidence="YYYY",
                    purpose="Structural Dimension",
                    narrative="Year of observation.",
                ),
            ],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )
        json_str = plan.model_dump_json()
        restored = MappingPlan.model_validate_json(json_str)
        assert restored.understanding.executive_summary == "A test dataset for roundtrip."
        assert restored.active_columns[0].purpose == "Structural Dimension"
        assert restored.active_columns[0].narrative == "Year of observation."
```

- [ ] **Step 2: Run tests — verify FAIL**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/models/test_plan_models.py::TestDatasetUnderstandingV4 -x -q`
Expected: FAIL — `DatasetUnderstanding.__init__() got an unexpected keyword argument 'executive_summary'`

- [ ] **Step 3: Add fields to models**

In `src/api/models/plan.py`:

**DatasetUnderstanding** (line 63) — add `executive_summary`:
```python
class DatasetUnderstanding(BaseModel):
    """High-level dataset classification."""
    archetype: str
    observation_grain: str
    key_insight: str
    executive_summary: str = ""
```

**ColumnMapping** (line 45) — add `purpose` and `narrative`:
```python
class ColumnMapping(BaseModel):
    """Plan for a single column."""
    column_name: str
    role: ColumnRole
    candidates: list[PropertyValueCandidate]
    selected_index: int = 0
    evidence: str
    dc_match: Optional[str] = None
    is_ambiguous: bool = False
    purpose: str = ""
    narrative: str = ""
```

Do NOT remove `IGNORED` from `ColumnRole` — keep it for backward compatibility. New plans will simply not use it.

- [ ] **Step 4: Run tests — verify PASS**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/models/test_plan_models.py -x -q`

- [ ] **Step 5: Run full suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/api/models/plan.py tests/api/models/test_plan_models.py
git commit -m "feat(plan): add executive_summary, purpose, narrative fields for understanding-first plans"
```

---

### Task 2: Update `_plan_to_markdown()` for understanding layer

**Files:**
- Modify: `src/agents/mapping_plan_agent.py`
- Modify: `tests/pipeline/plan/test_plan_markdown.py`

- [ ] **Step 1: Write tests**

Add to `tests/pipeline/plan/test_plan_markdown.py`:

```python
def test_executive_summary_in_markdown():
    plan = MappingPlan(
        **_base_plan(),
    )
    # Override understanding with executive_summary
    plan.understanding.executive_summary = "This dataset tracks industrial indicators for 2 countries over 10 years."
    md = _plan_to_markdown(plan)
    assert "## Executive Summary" in md
    assert "industrial indicators" in md


def test_column_narratives_in_markdown():
    plan = MappingPlan(
        dataset_name="test",
        understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
        active_columns=[
            ColumnMapping(
                column_name="Country",
                role=ColumnRole.DIMENSION,
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
    # Column should show purpose and narrative
    assert "Entity Resolution Helper" in md
    assert "Human-readable country name" in md


def test_no_executive_summary_when_empty():
    plan = MappingPlan(**_base_plan())
    plan.understanding.executive_summary = ""
    md = _plan_to_markdown(plan)
    assert "## Executive Summary" not in md
```

- [ ] **Step 2: Run tests — verify FAIL**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_markdown.py::test_executive_summary_in_markdown -x -q`
Expected: FAIL — "Executive Summary" not in markdown

- [ ] **Step 3: Update `_plan_to_markdown()` in `src/agents/mapping_plan_agent.py`**

**After the title line** (line 49 `lines.append(f"# Mapping Plan: {plan.dataset_name}")`), add:

```python
    # Executive Summary (v4)
    if hasattr(plan.understanding, 'executive_summary') and plan.understanding.executive_summary:
        lines.append("")
        lines.append("## Executive Summary")
        lines.append("")
        lines.append(plan.understanding.executive_summary)
        lines.append("")
```

**In the Active Column Mappings loop** (where each column is rendered), after the evidence line, add purpose and narrative:

```python
        # After: lines.append(f"- **Evidence:** {col.evidence}")
        if hasattr(col, 'purpose') and col.purpose:
            lines.append(f"- **Purpose:** {col.purpose}")
        if hasattr(col, 'narrative') and col.narrative:
            lines.append(f"- **Narrative:** {col.narrative}")
```

Also add the same for ignored_columns section (they also have purpose/narrative now).

- [ ] **Step 4: Run tests — verify PASS**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_markdown.py -x -q`

- [ ] **Step 5: Run full suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/agents/mapping_plan_agent.py tests/pipeline/plan/test_plan_markdown.py
git commit -m "feat(plan): render executive summary and column narratives in plan markdown"
```

---

### Task 3: Update the plan prompt for understanding-first generation

**Files:**
- Modify: `src/resources/prompts/mapping_plan_prompt_v2.txt`

- [ ] **Step 1: Add understanding-first preamble**

Read the current prompt. Find the `## YOUR TASK: Build an EnrichedMappingPlan` section (around line 49). INSERT the following BEFORE Step 1:

```
### Step 0: Understand the Data (MUST DO FIRST)

Before assigning ANY roles, develop a comprehensive understanding of the data:

**Executive Summary:** Write a paragraph (3-5 sentences) explaining this dataset in plain English. Cover:
- What domain/topic does this data represent?
- What is being measured or tracked?
- What is the geographic and temporal scope?
- What makes this dataset structurally interesting or challenging?

Write it like you're briefing a colleague who's never seen this data. This paragraph goes in understanding.executive_summary.

**Column Narratives:** For EVERY column, write a narrative (2-3 sentences) explaining:
- What does this column contain? (data type, sample values, cardinality)
- How does it relate to other columns? (co-referent? hierarchical? qualifier?)
- What purpose does it serve? Assign exactly ONE purpose:
  - "Structural Dimension" — defines the observation space (place, time, core dimensions)
  - "Observation Qualifier" — modifies the measurement (unit, scale, method)
  - "Entity Resolution Helper" — human-readable name for a coded column
  - "StatVar Annotator" — provides meaning/description for coded dimensions
  - "Value" — the actual numeric measurement

These go in each column's purpose and narrative fields.

THEN derive roles from your narratives. The understanding comes first, the technical role follows.
```

- [ ] **Step 2: Update Step 2 (Column Role Assignment)**

Replace the "ignored" logic in Step 2. Find the lines about `role=ignored` and replace with:

```
NO COLUMN SHOULD BE IGNORED. Every column serves a purpose:

- Former "ignored co-referent" columns → role=dimension, purpose="Entity Resolution Helper"
  They provide human-readable names for coded columns and serve as DCID resolution fallback.
  
- Former "ignored parent" columns → role=dimension, purpose="StatVar Annotator"
  They provide semantic meaning for finer-grained coded children.
  
- Former "ignored metadata" columns → role=metadata, purpose="Observation Qualifier"
  They modify measurements (unit, scale, method) and are crucial for StatVar design.

Only truly useless columns (Row_ID, empty columns, import timestamps) can use role=metadata 
with purpose="" and narrative="Internal artifact, not relevant to observations."
```

- [ ] **Step 3: Update the JSON output example**

In the output JSON example, update `DatasetUnderstanding` to include `executive_summary`:

```json
  "understanding": {
    "archetype": "Dimension-Row",
    "observation_grain": "One observation per country-year-variable-activity combination",
    "key_insight": "UNIDO industrial statistics with hierarchical dimensions",
    "executive_summary": "This dataset from UNIDO tracks industrial economic indicators for India and USA across 2014-2023. For each country-year combination, it measures 7 economic metrics (Output, Employees, Value Added, etc.) across 37 industrial sectors classified by ISIC Rev.4 codes. Each monetary measurement comes in both local currency and USD equivalent."
  },
```

Update `active_columns` example to include `purpose` and `narrative`:

```json
  "active_columns": [
    {
      "column_name": "CountryCode",
      "role": "observationAbout",
      "candidates": [...],
      "selected_index": 0,
      "evidence": "ISO numeric country codes",
      "dc_match": null,
      "is_ambiguous": false,
      "purpose": "Structural Dimension",
      "narrative": "ISO-3166-1 numeric country code (356=India, 840=USA). Used for observationAbout DCID resolution via countryNumeric/ prefix."
    }
  ],
```

Update `ignored_columns` example to show purpose instead of just "ignored":

```json
  "ignored_columns": [
    {
      "column_name": "Country",
      "role": "dimension",
      "candidates": [],
      "selected_index": 0,
      "evidence": "Co-referent with CountryCode",
      "purpose": "Entity Resolution Helper",
      "narrative": "Human-readable country name (India, United States of America). Co-referent with CountryCode — use for display and DCID resolution fallback."
    }
  ],
```

- [ ] **Step 4: Commit**

```bash
git add src/resources/prompts/mapping_plan_prompt_v2.txt
git commit -m "feat(plan): add understanding-first instructions to prompt — executive summary, narratives, no ignored columns"
```

---

## Execution Order

```
Task 1 (model fields) — foundation
Task 2 (markdown rendering) — depends on Task 1
Task 3 (prompt update) — depends on Task 1
```

Tasks 2 and 3 are independent of each other.
