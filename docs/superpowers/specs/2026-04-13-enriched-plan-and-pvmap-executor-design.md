# Enriched Mapping Plan & PVMAP Executor Design

**Date:** 2026-04-13
**Status:** Draft
**Scope:** Plan Agent enhancement + PVMAP Generator restructuring

## Problem Statement

The current mapping plan agent is shallow — it ranks pre-retrieved property candidates per column but lacks structural reasoning about column interdependencies, value normalization needs, and StatVar design. The PVMAP generator drifts from the plan because it competes with data context for attention in a 120K char prompt. Users can't see top-K candidates to make informed choices.

### Current Architecture

```
CandidateRetriever → MappingPlanAgent → PlanValidator → PlanGate → PVMAPGenerator (120K prompt)
```

**Problems:**
1. Plan lacks deep structural reasoning (column relationships, value dictionaries, StatVar blueprint)
2. Generator drifts from the plan (context dilution in large prompt)
3. Top-K candidates hidden from user (auto-selected, only winner shown)

## Approach: Two-Phase Plan + Hard-Constraint Generator + Programmatic Mitigations

Validated by Gemini (the same model used in agents) across 8 targeted consultations:

- **Phase A** (Python/pandas, no LLM): Compute column relationships, composite key, place/time format detection, value profiles — deterministic facts
- **Phase B** (LLM structured output): Takes Phase A analysis + candidates → produces StatVar blueprint, value dictionaries, top-K candidates, archetype classification — domain reasoning
- **Generator**: Strict plan executor — translates the approved plan into PVMAP CSV syntax. No overriding plan decisions.
- **Mitigations Layer**: Programmatic safeguards (Total/All override, dictionary expansion, pre-flight check, format normalization) handle edge cases without giving the generator flexibility to drift.

### Why This Approach

| Alternative | Verdict | Reason |
|---|---|---|
| Enrich plan, same architecture | Rejected | Context dilution unsolved; band-aid |
| Plan = spec, generator = executor (LLM-only plan) | Good flow, flawed execution | LLM can't reliably compute structural analysis |
| **Two-Phase + hard constraint (chosen)** | **Recommended** | Programmatic analysis for facts, LLM for reasoning, generator executes |

Gemini's assessment: "The only approach that respects the mathematical reality of Data Commons dimension analysis."

---

## Architecture

```
ProgrammaticSamplingAgent (existing)
    ↓ skeleton_summary, data_context, sampled_data_path

SchemaSelectionAgent (existing)
    ↓ schema_category, schema_vocab_content

[NEW] ColumnRelationshipAnalyzer (Phase A — Python/pandas)
    ↓ column_analysis (relationships, composite_key, place/time detection, value_profiles)

[ENHANCED] CandidateRetriever (uses Phase A to improve candidates)
    ↓ candidate_pool (enriched with relationship context)

[ENHANCED] MappingPlanAgent (Phase B — LLM structured output)
    ↓ EnrichedMappingPlan (StatVar blueprint, value dicts, attention matrix, top-K)

PlanValidator (existing)
    ↓ validates candidates against DC API

PlanGate (existing, enhanced to produce richer skeleton)
    ↓ approved_plan, pvmap_skeleton

[NEW] MitigationsLayer (programmatic + isolated LLM)
    ├── Pre-flight: verify full data columns match plan
    ├── Total/All: strip aggregate indicators from dimensions
    ├── Dict expansion: map unseen values (isolated LLM call)
    └── Format cleanup: zero-pad FIPS, normalize dates
    ↓ cleaned, expanded plan

[SIMPLIFIED] PVMAPGenerator (strict executor — plan → CSV syntax)
    ↓ on failure:
    ├── Tier 1 (syntax error) → retry generator
    └── Tier 2 (semantic error) → re-run Phase B plan agent
```

---

## Data Model: EnrichedMappingPlan

### New Enums

```python
class RelationshipType(str, Enum):
    CO_REFERENT = "co_referent"         # alias columns (FIPS + State_Name)
    CROSS_PRODUCT = "cross_product"     # dimension intersection (Age x Sex)
    QUALIFIER = "qualifier"             # unit/currency modifying value
    HIERARCHICAL = "hierarchical"       # parent-child (County -> State)
    VALUE_ERROR_BOUND = "value_error"   # estimate + margin of error
    TEMPORAL_COMPOSITION = "temporal"   # Year + Month -> date
    OBSERVATION_STATUS = "obs_status"   # data quality flags
    INDEPENDENT = "independent"         # no structural relationship
```

### New Models

```python
class ColumnRelationship(BaseModel):
    column_a: str
    column_b: str
    relationship: RelationshipType
    strength: float              # 0.0-1.0 confidence
    evidence: str                # "1:1 bijection, 99.8% purity"
    pvmap_implication: str       # "Use column_a for observationAbout, ignore column_b"

class ValueMapping(BaseModel):
    raw_value: str
    dcid: Optional[str]          # "dcs:Male" or None
    action: str                  # "MAP", "DROP_CONSTRAINT", "DROP_ROW"
    reason: str

class ValueDictionary(BaseModel):
    column_name: str
    dc_property: str             # "gender", "age", "race"
    mappings: list[ValueMapping]
    total_indicators: list[str]  # auto-detected: ["T", "Total", "All"]

class PlaceResolution(BaseModel):
    column_name: str
    format_detected: str         # "fips_state", "iso_2", "country_name"
    prefix_rule: str             # "geoId/", "country/"
    pad_zeros: Optional[int]     # 2 for state FIPS, 5 for county
    resolution_rate: float       # % of values matching the pattern

class TimeResolution(BaseModel):
    columns: list[str]           # ["Year"] or ["Year", "Month"]
    format_detected: str         # "YYYY", "YYYY-MM", "composed"
    normalization_rule: str      # "direct" or "concat Year-Month"

class StatVarBlueprint(BaseModel):
    base_properties: dict[str, str]  # {populationType: "dcs:Person", ...}
    constraint_columns: list[str]    # columns that modify the StatVar
    measure_columns: list[str]       # value columns (1 for long, N for wide)

class TransformationStrategy(BaseModel):
    archetype: str               # "long", "wide_time", "wide_variable", "cross_tabulated"
    action: Optional[str]        # "melt" or None
    id_vars: list[str]           # columns to keep as-is
    value_vars: list[str]        # columns to unpivot (for wide data)
```

### Extended MappingPlan

```python
class EnrichedMappingPlan(MappingPlan):
    """Extends MappingPlan with Phase A analysis + Phase B reasoning."""
    column_relationships: list[ColumnRelationship]
    statvar_blueprint: StatVarBlueprint
    value_dictionaries: list[ValueDictionary]
    place_resolution: Optional[PlaceResolution] = None
    time_resolution: Optional[TimeResolution] = None
    composite_key: list[str]
    transformation_strategy: Optional[TransformationStrategy] = None
```

Backward compatible — `MappingPlan` still works for existing pipelines. `EnrichedMappingPlan` extends it.

---

## Phase A: Programmatic Column Analyzer

**New file:** `src/pipeline/plan/column_analyzer.py`

Pure Python/pandas. Runs once, results cached. < 1 second on sampled data.

### Inputs
- `DatasetProfile` from existing `profiler.py`
- Sampled CSV (30-row stratified sample or first 1000 rows of full data)

### Algorithms

| Function | What it computes | Heuristic | Threshold |
|---|---|---|---|
| `_detect_co_referents(df, colA, colB)` | Bijection check | `groupby(A)[B].nunique().max() == 1` both ways | Purity >= 0.99 |
| `_detect_cross_products(df, colA, colB)` | Dimension intersection | `actual_combos / (unique_A * unique_B)` | Density >= 0.80 |
| `_detect_qualifiers(df, val_col, qual_col)` | Unit/currency modifying value | Numeric + low-cardinality categorical + keyword | Cardinality <= 5 |
| `_detect_hierarchical(df, child, parent)` | Many-to-one dependency | `child->parent == 1, parent->child.mean() > 1.1` | Strict FD |
| `_detect_value_error_bounds(df, est, moe)` | Estimate + MOE pair | Both numeric, MOE < abs(est) for 95%+ rows | 0.95 ratio |
| `_detect_temporal_composition(df)` | Year + Month -> date | Bounded ranges + `pd.to_datetime` validation | 99% parse |
| `_detect_composite_key(df)` | Minimal unique column set | Iterative `groupby(cols).size().max() == 1` | Exact |
| `_detect_place_format(series)` | Geo format detection | Regex: `^\d{2}$` -> FIPS state, `^[A-Z]{2}$` -> ISO-2 | 90%+ match |
| `_detect_total_indicators(series)` | Aggregate value detection | Match against: T, Total, All, Both, -, *, 00, 999 | Exact match |

### Data source for Phase A
- Uses the 30-row stratified sample for initial analysis (fast, already available in state)
- For composite key detection and cross-product density, reads first 1000 rows from the full input CSV (30 rows may not have enough unique combinations)
- Falls back to 30-row sample if full CSV read fails

### Edge cases
- Fuzzy matching for co-referent detection when names have typos ("St. Louis" vs "Saint Louis")
- Skip high-cardinality columns (> 100 unique values) for cross-product checks
- Handle datasets with no clear composite key (all rows unique by all columns — common in flat files)

---

## Phase B: Enhanced MappingPlanAgent

**Modified file:** `src/agents/mapping_plan_agent.py`
**New prompt:** `src/resources/prompts/mapping_plan_prompt_v2.txt`

### What the LLM now does

The LLM receives Phase A structural analysis as **trusted facts** and focuses on domain reasoning:

1. **StatVar Blueprint** — define `populationType`, `measuredProperty`, `statType` using composite key + column roles
2. **Value Dictionaries** — map each raw value to a DC DCID (domain knowledge: `M -> dcs:Male`, `15-24 -> dcs:Years15To24`)
3. **Top-K Candidates** — rank pre-retrieved candidates using Phase A evidence
4. **Transformation Strategy** — if wide data detected, specify melt instructions
5. **Archetype Classification** — deterministic with Phase A evidence

### Prompt structure

```
You are a Data Commons expert. Create a complete mapping specification 
using the pre-computed structural analysis below.

## Structural Analysis (TRUST THESE FACTS — computed programmatically)
{column_analysis_json}

## Pre-Retrieved Candidates
{candidate_pool_json}

## Schema Vocabulary
{schema_vocab_content}

## Small Data Sample (value verification only)
{sampled_data_5_rows}

## Engineer Feedback
{engineer_feedback}

## Tasks
1. Define StatVar blueprint using composite key and column roles
2. Map ALL raw dimension values to DC DCIDs (include DROP_CONSTRAINT for totals)
3. Rank candidates using structural evidence
4. If wide archetype, specify transformation strategy
5. Flag ambiguities for user review

## Output
Return JSON matching EnrichedMappingPlan schema.
```

### Model configuration
- Same as current: `gemini-3.1-pro-preview`, temperature 0.2, structured output
- Response schema: `EnrichedMappingPlan.model_json_schema()`
- Max tokens: 16384 (increased from 8192 — richer plan needs more space)

---

## Mitigations Layer

**New file:** `src/pipeline/plan/plan_mitigations.py`

Runs between PlanGate and Generator. All programmatic except dictionary expansion.

### Mitigation 1: Total/All Override
```python
TOTAL_INDICATORS = {"T", "Total", "All", "Both", "Both Sexes", "All Races", 
                    "All Ages", "Overall", "TOT", "-", "*", "~", "00", "000", "999", ""}

def strip_total_indicators(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """For each value dictionary, ensure total indicators have action=DROP_CONSTRAINT."""
    for vd in plan.value_dictionaries:
        for mapping in vd.mappings:
            if mapping.raw_value.strip() in TOTAL_INDICATORS:
                mapping.action = "DROP_CONSTRAINT"
                mapping.dcid = None
                mapping.reason = "Total/aggregate indicator — drop constraint"
    return plan
```

### Mitigation 2: Dynamic Dictionary Expansion
```python
async def expand_dictionary(plan: EnrichedMappingPlan, full_data_path: Path) -> EnrichedMappingPlan:
    """Detect unseen values in full data and map them via isolated LLM call."""
    full_values = extract_unique_values(full_data_path, plan.value_dictionaries)
    for vd in plan.value_dictionaries:
        known = {m.raw_value for m in vd.mappings}
        unseen = full_values[vd.column_name] - known
        if unseen:
            new_mappings = await gemini_map_values(
                unseen_values=list(unseen),
                existing_dict=vd.mappings,  # few-shot examples
                dc_property=vd.dc_property
            )
            vd.mappings.extend(new_mappings)
    return plan
```

### Mitigation 3: Pre-flight Skeleton Check
```python
def check_column_alignment(plan: EnrichedMappingPlan, full_data_path: Path) -> list[str]:
    """Verify all plan columns exist in full data. Detect new/missing columns."""
    full_columns = set(pd.read_csv(full_data_path, nrows=0).columns)
    plan_columns = {cm.column_name for cm in plan.active_columns + plan.ignored_columns}
    
    missing = plan_columns - full_columns  # plan references columns not in data
    new = full_columns - plan_columns      # data has columns plan doesn't know about
    
    issues = []
    if missing: issues.append(f"Plan references missing columns: {missing}")
    if new: issues.append(f"Data has unmapped columns: {new}")
    return issues  # empty = all good
```

### Mitigation 4: Format Normalization
```python
def normalize_place_formats(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """Apply zero-padding rules from PlaceResolution."""
    if plan.place_resolution and plan.place_resolution.pad_zeros:
        # Update the value expression in the selected candidate
        # e.g., "geoId/{Data}" -> "geoId/{Data:>05}" with zero-pad instruction
        ...
    return plan

def normalize_time_formats(plan: EnrichedMappingPlan) -> EnrichedMappingPlan:
    """Ensure time normalization rule is applied in skeleton."""
    ...
    return plan
```

---

## Generator: Plan Executor

**Modified:** `src/agents/pvmap_retry_loop.py` (StatePreparationAgent, PromptPreparationAgent)
**New prompt:** `src/resources/prompts/pvmap_executor_prompt.txt`

### Prompt budget

| Section | Budget | Content |
|---|---|---|
| Plan specification | 60% | Column roles, StatVar blueprint, value dictionaries, relationships |
| PVMAP skeleton | 20% | Pre-filled CSV from `plan_to_skeleton_csv()` |
| Sampled data | 10% | 5-10 rows, reference only |
| Syntax reference | 10% | PVMAP CSV format rules |

### Executor prompt structure

```
You are a PVMAP syntax generator. Translate the approved mapping plan 
into PVMAP CSV format. Do NOT alter any semantic decisions in the plan.

## PVMAP Syntax Rules
[key matching, carry-forward, {Data}/{Number}, dcs: prefix — compact reference]

## Approved Mapping Plan (USER APPROVED — DO NOT OVERRIDE)

### Column Roles
[table: column -> role -> selected property -> value expression]

### StatVar Blueprint  
[base_properties + constraint_columns + measure_columns]

### Value Dictionaries
[per-dimension: raw value -> DCID, with DROP_CONSTRAINT for totals]

### Place Resolution
[column -> prefix rule -> pad zeros]

### Time Resolution
[column(s) -> format -> normalization]

### Column Relationships (context)
[significant pairs: co-referent, hierarchical, qualifier]

## PVMAP Skeleton (pre-filled baseline)
```csv
{skeleton}
```

## Sampled Data (reference for exact string matching)
{5_rows}

## Rules
- Follow the plan EXACTLY
- If structurally impossible: output {"status": "PLAN_ERROR", "reason": "..."}
- Copy column names exactly from the plan
- Use dcs: prefix for DC properties and enum values
- Every skeleton row is mandatory — never remove rows
```

### PLAN_ERROR escalation

If the generator outputs `{"status": "PLAN_ERROR", ...}`, the retry loop:
1. Skips validation entirely
2. Routes the error reason to the Plan Agent (Phase B re-run)
3. Re-runs mitigations + generation after plan revision

---

## Two-Tiered Retry Loop

### Error classification

| Error Signal | Classification | Route To |
|---|---|---|
| CSV parse failure | Tier 1 (syntax) | Generator retry |
| Key doesn't match column | Tier 1 (syntax) | Generator retry |
| Missing `{Number}` on value | Tier 1 (syntax) | Generator retry |
| Wrong dcs: prefix usage | Tier 1 (syntax) | Generator retry |
| Duplicate observations (same place+time+statvar) | Tier 2 (semantic) | Plan Agent |
| Wrong column role (place unmapped) | Tier 2 (semantic) | Plan Agent |
| PLAN_ERROR from generator | Tier 2 (semantic) | Plan Agent |
| Zero data rows after validation | Tier 2 (semantic) | Plan Agent |

### Implementation

Modify `TieredCorrectionAgent` in `pvmap_retry_loop.py`:
- Tier 1: Same as current (programmatic fix + LLM patch + regen)
- Tier 2 (NEW): Set `state["plan_revision_needed"] = True` with error context. The outer loop detects this and re-runs Phase B with the error as `engineer_feedback`.

---

## UI: Plan Text Editor + Feedback

**Modified:** `frontend/src/pages/ReviewPlanPage.tsx`

### Layout
1. **Text editor** (top 70%) — full `EnrichedMappingPlan` as formatted JSON. User can edit any field: column roles, selected candidates (`selected_index`), value mappings, StatVar blueprint.
2. **Feedback box** (bottom 30%) — textarea for natural language instructions. Submit triggers `POST /api/runs/{run_id}/plan/regenerate` with feedback text.

### What's visible to users
- All top-K candidates per column (not just the winner)
- Column relationships (the attention matrix)
- Value dictionaries with DCID mappings
- StatVar blueprint
- Confidence scores with evidence

### API changes
- `GET /api/runs/{run_id}/plan` — returns `EnrichedMappingPlan` (backward compatible, new fields optional)
- `PUT /api/runs/{run_id}/plan` — accepts full plan edit (user modified the JSON)
- Existing endpoints (`regenerate`, `approve`, `notes`) work unchanged

---

## Key Files to Create/Modify

### New files
| File | Purpose |
|---|---|
| `src/pipeline/plan/column_analyzer.py` | Phase A: programmatic column relationship analysis |
| `src/pipeline/plan/plan_mitigations.py` | Mitigations layer: Total override, dict expansion, pre-flight, format normalization |
| `src/resources/prompts/mapping_plan_prompt_v2.txt` | Phase B prompt: structural analysis + reasoning |
| `src/resources/prompts/pvmap_executor_prompt.txt` | Generator prompt: plan executor (compact) |

### Modified files
| File | Changes |
|---|---|
| `src/api/models/plan.py` | Add new models: `ColumnRelationship`, `ValueDictionary`, `StatVarBlueprint`, `EnrichedMappingPlan` |
| `src/agents/mapping_plan_agent.py` | Use v2 prompt, accept `column_analysis` input, output `EnrichedMappingPlan` |
| `src/agents/pvmap_retry_loop.py` | New `MitigationsAgent`, restructured `PromptPreparationAgent`, two-tiered error routing |
| `src/pipeline/plan/skeleton_converter.py` | Handle `EnrichedMappingPlan` fields (value dicts, StatVar blueprint) |
| `src/pipeline/plan/candidate_retriever.py` | Accept Phase A analysis to improve candidate scoring |
| `src/run_pipeline.py` | Wire `ColumnRelationshipAnalyzer` into the pipeline sequence |
| `frontend/src/pages/ReviewPlanPage.tsx` | Text editor + feedback box UI |
| `frontend/src/types/index.ts` | TypeScript types for `EnrichedMappingPlan` |

---

## Testing Strategy

1. **Phase A unit tests** — test each heuristic against known datasets (BIS, Census, CRDC)
2. **Phase B integration tests** — verify LLM produces valid `EnrichedMappingPlan` schema
3. **Mitigations tests** — test Total stripping, dict expansion, pre-flight check, format normalization
4. **End-to-end A/B comparison** — run existing datasets through old vs new pipeline, compare:
   - Validation pass rate
   - Heuristic quality score
   - Ground truth PV accuracy
   - Number of retry iterations needed
5. **Regression** — all existing 982+ tests must still pass

---

## Success Criteria

1. Plan contains all 3 new sections (column relationships, value dictionaries, StatVar blueprint)
2. Generator follows the plan with < 5% deviation (measured by comparing plan column roles vs PVMAP output)
3. Top-K candidates visible in plan text for user review
4. Validation pass rate improves (fewer retries needed)
5. No regression in existing test suite
