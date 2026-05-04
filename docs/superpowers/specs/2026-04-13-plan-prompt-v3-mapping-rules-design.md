# Plan Prompt v3: Mapping Rules + Indicator Columns

**Date:** 2026-04-13
**Status:** Draft
**Scope:** Plan prompt refinement + model additions (no architectural changes)

## Problem

The current plan prompt (v2) produces shallow plans that read like column-role lookup tables. Gemini (the same model used in agents) identified 3 specific gaps when asked to review our plan quality:

1. **No Indicator Column concept** — columns like `Variable` (Output/Employees/Value added) fundamentally change the StatVar definition per-value, but the plan treats them as simple dimensions with passthrough `[DATA]`
2. **No multi-measure handling** — datasets with `Value` + `ValueUSD` need separate mapping rules per measure column, but the plan ignores one as "co-referent"
3. **No concrete PVMAP rows** — the plan says "column X → role Y" but never shows the actual PVMAP CSV rows the generator should produce

## Solution

Add 3 new concepts to the plan model and prompt:

### 1. Indicator Column vs Constraint Column

**Constraint Column** (e.g., Gender, Age): adds a property-value constraint to the StatVar. All values use the same `populationType` and `measuredProperty`.

**Indicator Column** (e.g., Variable, Indicator, Series): each value defines a DIFFERENT StatVar with different `populationType` and/or `measuredProperty`.

Example for UNIDO `Variable` column:
- `Output` → `populationType: dcs:EconomicActivity, measuredProperty: dcs:amount`
- `Employees` → `populationType: dcs:Person, measuredProperty: dcs:count`
- `Value added` → `populationType: dcs:EconomicActivity, measuredProperty: dcs:valueAdded`

The plan must produce an `IndicatorMapping` per-value that specifies the full StatVar properties.

### 2. Mapping Rules

Replace the single `statvar_blueprint` with a list of `mapping_rules`. Each rule specifies:
- **measure_column**: which value column this rule applies to (e.g., "Value", "ValueUSD")
- **statvar_template**: the StatVar construction recipe
  - base properties (populationType, measuredProperty, statType)
  - indicator_column: which column provides dynamic StatVar properties (or null)
  - constraint_columns: which columns add constraint properties
- **observation_template**: how place, time, value wire up
  - observationAbout column + expression
  - observationDate column + expression
  - value column + expression
  - unit (static value or mapped from a column)
- **pvmap_rows**: the actual PVMAP CSV rows this rule generates

For a single-measure dataset, there's 1 mapping rule. For multi-measure (Value + ValueUSD), there are 2 rules — one per measure column, potentially with different units.

### 3. Target PVMAP Rows in the Plan

Each mapping rule includes the concrete PVMAP CSV rows it generates. The PVMAP generator's job becomes: concatenate all `pvmap_rows` from all mapping rules + add the skeleton header.

## Data Model Changes

### New models in `src/api/models/plan.py`

```python
class IndicatorValueMapping(BaseModel):
    """How one value of an indicator column changes the StatVar."""
    raw_value: str
    population_type: str      # e.g., "dcs:Person"
    measured_property: str    # e.g., "dcs:count"
    stat_type: str            # e.g., "dcs:measuredValue"
    extra_properties: list[StatVarProperty] = Field(default_factory=list)
    reason: str

class IndicatorColumn(BaseModel):
    """A dimension column that changes the core StatVar per-value."""
    column_name: str
    value_mappings: list[IndicatorValueMapping]

class ObservationTemplate(BaseModel):
    """How a single observation is constructed."""
    about_column: str           # column for observationAbout
    about_expression: str       # e.g., "country/[DATA]"
    date_column: str            # column for observationDate
    date_expression: str        # e.g., "[NUMBER]"
    value_column: str           # column for value
    value_expression: str       # e.g., "[NUMBER]"
    unit: Optional[str] = None  # static unit, e.g., "dcs:USDollar"
    unit_column: Optional[str] = None  # column providing unit dynamically

class MappingRule(BaseModel):
    """A concrete rule for generating PVMAP rows from one measure column."""
    rule_id: str                          # e.g., "value_local_currency"
    measure_column: str                   # which value column
    description: str                      # human-readable explanation
    observation: ObservationTemplate
    indicator_column: Optional[str] = None  # column that changes StatVar per-value
    constraint_columns: list[str] = Field(default_factory=list)
    static_properties: list[StatVarProperty] = Field(default_factory=list)
    pvmap_rows: list[str] = Field(default_factory=list)  # actual PVMAP CSV rows
```

### Updated `EnrichedMappingPlan`

Add new fields (keep existing ones for backward compat):

```python
class EnrichedMappingPlan(MappingPlan):
    # ... existing fields ...
    
    # NEW v3 fields
    indicator_columns: list[IndicatorColumn] = Field(default_factory=list)
    mapping_rules: list[MappingRule] = Field(default_factory=list)
```

The existing `statvar_blueprint` stays for backward compatibility but `mapping_rules` takes precedence when present.

## Prompt Changes

### New prompt sections in `mapping_plan_prompt_v2.txt`

**After Step 2 (Column Role Assignment), add:**

#### Step 2b: Identify Indicator Columns

```
For each dimension column, determine if it is:

- A CONSTRAINT column: values add a property-value pair to the StatVar
  (e.g., Gender: M→gender=dcs:Male, F→gender=dcs:Female)
  
- An INDICATOR column: values CHANGE the core StatVar definition
  (e.g., Variable: "Output"→measuredProperty=dcs:amount, "Employees"→measuredProperty=dcs:count)

Detection heuristic: If a dimension column's values describe WHAT is being measured
(rather than WHO or WHERE or WHEN), it's likely an indicator column.

For each indicator column, create an IndicatorColumn with per-value mappings:
- raw_value: exact string
- population_type: what entity is being measured
- measured_property: what about that entity
- stat_type: how it's measured (usually dcs:measuredValue)
```

**Replace Step 3 (StatVar Blueprint) with:**

#### Step 3: Mapping Rules

```
For EACH measure column in the dataset, create a MappingRule:

1. Identify the measure column (e.g., "Value", "ValueUSD")
2. Define how observations are constructed:
   - observationAbout: which column + prefix expression
   - observationDate: which column + format expression
   - value: which measure column
   - unit: static (e.g., "dcs:USDollar") or from a column (e.g., UnitType)
3. Identify which indicator column (if any) changes the StatVar per-value
4. List constraint columns that add properties
5. List static properties (statType, etc.)
6. Generate the ACTUAL PVMAP CSV rows this rule produces

If UnitType or Currency column exists, it may mean:
- Two measure columns need different units → separate mapping rules
- One measure column needs unit from another column → unit_column reference

PVMAP ROW GENERATION RULES:
- For the measure column: key=column_name, include value,[NUMBER] + all static properties
- For each indicator value: key=INDICATOR_COL:VALUE, include the StatVar properties for that value
- For each constraint column with <=50 values: key=COL:VALUE rows mapping each value to its DCID
- For qualifier columns (unit/scaling): key=COL:VALUE rows mapping each value
```

## How This Flows to the PVMAP Generator

The executor prompt already consumes `{{PVMAP_SKELETON}}`. The skeleton converter (`plan_to_skeleton_csv`) will be enhanced to:

1. Read `mapping_rules` from the plan
2. For each rule, output its `pvmap_rows` directly
3. Add the static properties row

The generator's job becomes even more mechanical — the plan already contains the PVMAP rows.

## Files to Change

| File | Change |
|---|---|
| `src/api/models/plan.py` | Add `IndicatorValueMapping`, `IndicatorColumn`, `ObservationTemplate`, `MappingRule`. Add `indicator_columns` and `mapping_rules` to `EnrichedMappingPlan`. |
| `src/resources/prompts/mapping_plan_prompt_v2.txt` | Add indicator column detection (Step 2b), replace StatVar Blueprint with Mapping Rules (Step 3), add PVMAP row generation instructions |
| `src/agents/mapping_plan_agent.py` | Update `_plan_to_markdown()` to render indicator columns and mapping rules with PVMAP rows |
| `src/pipeline/plan/skeleton_converter.py` | When `mapping_rules` present, use their `pvmap_rows` instead of generating from column candidates |
| `tests/api/models/test_plan_models.py` | Tests for new models |
| `tests/pipeline/plan/test_plan_markdown.py` | Tests for new markdown sections |
| `tests/pipeline/plan/test_skeleton_converter.py` | Tests for mapping-rule-based skeleton generation |

## What Stays the Same

- Phase A column analyzer — untouched
- Plan mitigations layer — untouched
- PVMAP executor prompt — untouched (consumes skeleton)
- UI markdown view — untouched (renders new sections automatically)
- Retry loop — untouched
- Existing `statvar_blueprint`, `value_dictionaries`, `column_relationships` — kept for backward compat

## Success Criteria

1. Plan for UNIDO dataset includes indicator column detection (Variable → different StatVar per value)
2. Plan for multi-measure datasets (Value + ValueUSD) produces separate mapping rules
3. Plan includes actual PVMAP CSV rows that the generator can use directly
4. Existing plans (without mapping_rules) still work — backward compatible
5. All existing tests pass
