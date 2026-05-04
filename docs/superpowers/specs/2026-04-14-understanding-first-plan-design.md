# Understanding-First Plan (v4)

**Date:** 2026-04-14
**Status:** Draft
**Scope:** Plan prompt + model refinement — no architectural changes

## Problem

Plans are shallow lookup tables. They assign column roles but don't explain WHY. Columns are aggressively "ignored" when they should serve purposes like entity resolution, StatVar annotation, or observation qualification. A human reviewing the plan can't understand the data from it.

## Solution

The plan becomes a **two-layer document**:
- **Layer 1 (Understanding):** Executive summary + per-column narratives in natural language
- **Layer 2 (Execution):** Roles with purpose, indicator columns, mapping rules with PVMAP rows

No column is ever "ignored." Every column gets a **role** (technical, for the generator) and a **purpose** (semantic, for the human).

## Layer 1: Understanding (Human-Readable)

### Executive Summary

A freeform paragraph explaining the dataset like you're briefing a colleague who's never seen it. Covers: domain, source, what's being measured, geographic/temporal scope, key structural characteristics.

Example:
> "This UNIDO dataset tracks industrial economic indicators for India and USA across 2014-2023. For each country-year combination, it measures 7 economic metrics (Output, Employees, Value Added, etc.) across 37 industrial sectors classified by ISIC Rev.4 codes. Each monetary measurement comes in both local currency and USD. Non-monetary metrics (like employee counts) are marked with UnitType='N'."

### Column Narratives

For EVERY column, a plain-English explanation:
- What it contains
- How it relates to other columns
- What purpose it serves in the mapping
- Why it was assigned its role

Example:
> **UnitType** (purpose: Observation Qualifier)
> "Indicates whether Value is a monetary amount (M) or a count (N). This fundamentally changes the StatVar design: M means measuredProperty=amount with a currency unit, N means measuredProperty=count. Must not be ignored — it drives the StatVar blueprint."

## Layer 2: Execution (Machine-Readable)

### Column Purposes (replaces binary map/ignore)

Every column gets ONE of 5 purposes (from Gemini's Data Commons expert analysis):

| Purpose | Description | Example |
|---------|-------------|---------|
| **Structural Dimension** | Defines the observation space (place, time, key dimensions) | Year, CountryCode, ActivityCode |
| **Observation Qualifier** | Modifies the measurement (unit, scale, method) | UnitType, Multiplier, MeasurementMethod |
| **Entity Resolution Helper** | Human-readable name for a coded column | Country (for CountryCode), Activity (for ActivityCode) |
| **StatVar Annotator** | Provides meaning/description for coded dimensions | Variable (explains what UnconsolidatedVariableCode means) |
| **Value** | The actual numeric measurement | Value, ValueUSD |

No column gets purpose "ignored." Only truly useless columns (Row_ID, empty columns) can be excluded, and they still get a narrative explaining why.

### Roles + Purpose Combined

Each column carries both:
- `role`: technical role for PVMAP generation (observationAbout, observationDate, measure, dimension, metadata)
- `purpose`: semantic purpose explaining WHY (one of the 5 above)
- `narrative`: plain-English explanation

Example for UNIDO dataset:

| Column | Role | Purpose | Narrative |
|--------|------|---------|-----------|
| CountryCode | observationAbout | Structural Dimension | ISO numeric code, used for DCID resolution |
| Country | dimension | Entity Resolution Helper | Human name, fallback for place resolution |
| Year | observationDate | Structural Dimension | YYYY format, direct passthrough |
| Variable | dimension | StatVar Annotator | Explains what UnconsolidatedVariableCode values mean |
| UnconsolidatedVariableCode | dimension | Structural Dimension | Finer-grained metric identifier, part of composite key |
| ActivityCode | dimension | Structural Dimension | ISIC Rev.4 codes defining industrial sectors |
| Activity | dimension | Entity Resolution Helper | Human-readable industry names for ActivityCode |
| Value | measure | Value | Primary measurement in local currency |
| ValueUSD | measure | Value | Same measurement converted to USD |
| UnitType | dimension | Observation Qualifier | M=monetary, N=count — determines StatVar measuredProperty |
| Metadata | metadata | Observation Qualifier | Data quality notes (non-response adjustments) |

### Indicator Columns + Mapping Rules + PVMAP Rows

Kept from v3 — no changes. The understanding layer sits ON TOP of the execution layer.

## Model Changes

### DatasetUnderstanding — add `executive_summary`

```python
class DatasetUnderstanding(BaseModel):
    archetype: str
    observation_grain: str
    key_insight: str
    executive_summary: str = ""  # NEW
```

### ColumnMapping — add `purpose` and `narrative`

```python
class ColumnMapping(BaseModel):
    column_name: str
    role: ColumnRole
    candidates: list[PropertyValueCandidate]
    selected_index: int = 0
    evidence: str
    dc_match: Optional[str] = None
    is_ambiguous: bool = False
    purpose: str = ""     # NEW: "Structural Dimension", "Entity Resolution Helper", etc.
    narrative: str = ""   # NEW: plain-English explanation
```

### ColumnRole — remove IGNORED

The `IGNORED` value is removed from `ColumnRole` enum. Former "ignored" columns now get `role=dimension` or `role=metadata` with their purpose explaining the semantic function.

**Migration:** Existing plans with `role="ignored"` still parse (Pydantic is lenient with string enums) but new plans won't use it.

## Prompt Changes

### New preamble instruction

Before any role assignment steps, add:

```
UNDERSTANDING FIRST: Before assigning any roles, write two things:

1. executive_summary: A paragraph explaining this dataset in plain English.
   What domain? What's being measured? What's the geographic and temporal scope?
   Write it like you're briefing a colleague who's never seen this data.

2. For EVERY column, write a narrative (2-3 sentences) explaining:
   - What this column contains
   - How it relates to other columns  
   - What purpose it serves (one of: Structural Dimension, Observation Qualifier,
     Entity Resolution Helper, StatVar Annotator, Value)

THEN derive roles from your narratives. The narrative comes first, the role follows.
```

### Updated role assignment

Replace the "ignored" logic with:

```
NO COLUMN IS IGNORED. Every column serves a purpose:

- Structural Dimension: observationAbout, observationDate, or dimension columns 
  that define the observation space
- Observation Qualifier: columns providing unit, scale, method — role=dimension 
  or role=metadata, but they MODIFY the measurement
- Entity Resolution Helper: human-readable alias for a coded column — role=dimension, 
  used for DCID resolution fallback and human readability
- StatVar Annotator: provides meaning for coded dimensions — role=dimension, 
  used to generate StatVar names and descriptions
- Value: the numeric measurement — role=measure

Only exclude columns that are truly empty or internal database artifacts (Row_ID, timestamps).
```

## Files to Change

| File | Change |
|---|---|
| `src/api/models/plan.py` | Add `executive_summary` to `DatasetUnderstanding`. Add `purpose`, `narrative` to `ColumnMapping`. Remove `IGNORED` from `ColumnRole`. |
| `src/resources/prompts/mapping_plan_prompt_v2.txt` | Add understanding-first preamble, update role assignment to remove "ignored", add column purpose/narrative instructions |
| `src/agents/mapping_plan_agent.py` | Update `_plan_to_markdown()` to render executive summary and column narratives |
| `tests/api/models/test_plan_models.py` | Tests for new fields |
| `tests/pipeline/plan/test_plan_markdown.py` | Tests for new markdown sections |

## What Stays the Same

- Phase A column analyzer — untouched
- Mitigations layer — untouched  
- PVMAP executor prompt — untouched
- Skeleton converter — untouched
- Mapping rules + indicator columns (v3) — kept
- UI markdown view — automatically renders new sections
- All existing v3 fields — backward compatible

## Success Criteria

1. Plan executive summary reads like a data briefing a human can understand
2. Every column has a narrative explaining its meaning and relationships
3. No column has role="ignored" — all have a purpose
4. Human reviewer can read the plan and fully understand the dataset without seeing the raw CSV
5. Existing tests pass (backward compatible)
