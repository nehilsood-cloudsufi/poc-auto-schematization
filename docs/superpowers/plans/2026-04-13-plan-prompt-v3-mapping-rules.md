# Plan Prompt v3: Mapping Rules + Indicator Columns

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add indicator column detection, mapping rules, and target PVMAP rows to the plan — making generated plans actionable specifications instead of shallow lookup tables.

**Architecture:** Add 4 new Pydantic models to `plan.py`, update the plan prompt with indicator/mapping-rule instructions, enhance `_plan_to_markdown()` for new sections, and update `skeleton_converter.py` to use mapping-rule PVMAP rows when available.

**Tech Stack:** Pydantic models, Gemini structured output, Python

**Spec:** `docs/superpowers/specs/2026-04-13-plan-prompt-v3-mapping-rules-design.md`

---

### Task 1: Add new data models

**Files:**
- Modify: `src/api/models/plan.py`
- Test: `tests/api/models/test_plan_models.py`

- [ ] **Step 1: Write tests for the new models**

Add to `tests/api/models/test_plan_models.py`:

```python
from src.api.models.plan import (
    IndicatorValueMapping, IndicatorColumn, ObservationTemplate, MappingRule,
)


class TestIndicatorValueMapping:
    def test_creation(self):
        ivm = IndicatorValueMapping(
            raw_value="Output",
            population_type="dcs:EconomicActivity",
            measured_property="dcs:amount",
            stat_type="dcs:measuredValue",
            reason="Industrial output measurement",
        )
        assert ivm.raw_value == "Output"
        assert ivm.population_type == "dcs:EconomicActivity"
        assert ivm.extra_properties == []


class TestIndicatorColumn:
    def test_creation(self):
        ic = IndicatorColumn(
            column_name="Variable",
            value_mappings=[
                IndicatorValueMapping(
                    raw_value="Output",
                    population_type="dcs:EconomicActivity",
                    measured_property="dcs:amount",
                    stat_type="dcs:measuredValue",
                    reason="Output",
                ),
                IndicatorValueMapping(
                    raw_value="Employees",
                    population_type="dcs:Person",
                    measured_property="dcs:count",
                    stat_type="dcs:measuredValue",
                    reason="Employee count",
                ),
            ],
        )
        assert ic.column_name == "Variable"
        assert len(ic.value_mappings) == 2
        assert ic.value_mappings[0].population_type == "dcs:EconomicActivity"
        assert ic.value_mappings[1].population_type == "dcs:Person"


class TestObservationTemplate:
    def test_creation(self):
        ot = ObservationTemplate(
            about_column="Country",
            about_expression="country/[DATA]",
            date_column="Year",
            date_expression="[NUMBER]",
            value_column="Value",
            value_expression="[NUMBER]",
            unit="dcs:USDollar",
        )
        assert ot.about_column == "Country"
        assert ot.unit == "dcs:USDollar"
        assert ot.unit_column is None

    def test_unit_from_column(self):
        ot = ObservationTemplate(
            about_column="Country",
            about_expression="country/[DATA]",
            date_column="Year",
            date_expression="[NUMBER]",
            value_column="Value",
            value_expression="[NUMBER]",
            unit_column="UnitType",
        )
        assert ot.unit is None
        assert ot.unit_column == "UnitType"


class TestMappingRule:
    def test_creation_with_pvmap_rows(self):
        rule = MappingRule(
            rule_id="value_local",
            measure_column="Value",
            description="Local currency values",
            observation=ObservationTemplate(
                about_column="Country",
                about_expression="country/[DATA]",
                date_column="Year",
                date_expression="[NUMBER]",
                value_column="Value",
                value_expression="[NUMBER]",
            ),
            indicator_column="Variable",
            constraint_columns=["ActivityCode"],
            static_properties=[StatVarProperty(name="statType", value="dcs:measuredValue")],
            pvmap_rows=[
                "Variable,Output,populationType,dcs:EconomicActivity,measuredProperty,dcs:amount",
                "Variable,Employees,populationType,dcs:Person,measuredProperty,dcs:count",
                "ActivityCode,05,economicActivity,dcs:ISICv4_05",
            ],
        )
        assert rule.rule_id == "value_local"
        assert len(rule.pvmap_rows) == 3
        assert rule.indicator_column == "Variable"


class TestEnrichedPlanWithMappingRules:
    def test_new_v3_fields_default_empty(self):
        """EnrichedMappingPlan v3 fields default to empty lists."""
        plan = EnrichedMappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
            active_columns=[],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
            statvar_blueprint=StatVarBlueprint(
                base_properties=[StatVarProperty(name="populationType", value="dcs:Person")],
                constraint_columns=[], measure_columns=["Value"],
            ),
            composite_key=["A"],
        )
        assert plan.indicator_columns == []
        assert plan.mapping_rules == []

    def test_v3_fields_roundtrip(self):
        """New fields survive JSON roundtrip."""
        plan = EnrichedMappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
            active_columns=[],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
            statvar_blueprint=StatVarBlueprint(
                base_properties=[StatVarProperty(name="populationType", value="dcs:Person")],
                constraint_columns=[], measure_columns=["Value"],
            ),
            composite_key=["A"],
            indicator_columns=[
                IndicatorColumn(column_name="Variable", value_mappings=[
                    IndicatorValueMapping(raw_value="X", population_type="dcs:P", measured_property="dcs:c", stat_type="dcs:m", reason="test"),
                ]),
            ],
            mapping_rules=[
                MappingRule(
                    rule_id="r1", measure_column="Value", description="test",
                    observation=ObservationTemplate(
                        about_column="A", about_expression="[DATA]",
                        date_column="B", date_expression="[NUMBER]",
                        value_column="Value", value_expression="[NUMBER]",
                    ),
                    pvmap_rows=["A,x,y,z"],
                ),
            ],
        )
        json_str = plan.model_dump_json()
        restored = EnrichedMappingPlan.model_validate_json(json_str)
        assert len(restored.indicator_columns) == 1
        assert len(restored.mapping_rules) == 1
        assert restored.mapping_rules[0].pvmap_rows == ["A,x,y,z"]
```

- [ ] **Step 2: Run tests — verify FAIL**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/models/test_plan_models.py -x -q`
Expected: ImportError — `IndicatorValueMapping` not found

- [ ] **Step 3: Add the 4 new models to `src/api/models/plan.py`**

Add BEFORE `EnrichedMappingPlan` (after `TransformationStrategy`):

```python
class IndicatorValueMapping(BaseModel):
    """How one value of an indicator column changes the StatVar."""
    raw_value: str
    population_type: str
    measured_property: str
    stat_type: str
    extra_properties: list[StatVarProperty] = Field(default_factory=list)
    reason: str


class IndicatorColumn(BaseModel):
    """A dimension column that changes the core StatVar per-value."""
    column_name: str
    value_mappings: list[IndicatorValueMapping]


class ObservationTemplate(BaseModel):
    """How a single observation is constructed."""
    about_column: str
    about_expression: str
    date_column: str
    date_expression: str
    value_column: str
    value_expression: str
    unit: Optional[str] = None
    unit_column: Optional[str] = None


class MappingRule(BaseModel):
    """A concrete rule for generating PVMAP rows from one measure column."""
    rule_id: str
    measure_column: str
    description: str
    observation: ObservationTemplate
    indicator_column: Optional[str] = None
    constraint_columns: list[str] = Field(default_factory=list)
    static_properties: list[StatVarProperty] = Field(default_factory=list)
    pvmap_rows: list[str] = Field(default_factory=list)
```

Then add 2 new fields to `EnrichedMappingPlan`:

```python
class EnrichedMappingPlan(MappingPlan):
    # ... existing fields ...
    transformation_strategy: Optional[TransformationStrategy] = None
    # NEW v3 fields
    indicator_columns: list[IndicatorColumn] = Field(default_factory=list)
    mapping_rules: list[MappingRule] = Field(default_factory=list)
```

- [ ] **Step 4: Run tests — verify PASS**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/models/test_plan_models.py -x -q`

- [ ] **Step 5: Run full suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/api/models/plan.py tests/api/models/test_plan_models.py
git commit -m "feat(plan): add IndicatorColumn, MappingRule, ObservationTemplate models"
```

---

### Task 2: Update `_plan_to_markdown()` for new sections

**Files:**
- Modify: `src/agents/mapping_plan_agent.py`
- Test: `tests/pipeline/plan/test_plan_markdown.py`

- [ ] **Step 1: Add tests for new markdown sections**

Add to `tests/pipeline/plan/test_plan_markdown.py`:

```python
from src.api.models.plan import (
    IndicatorValueMapping, IndicatorColumn, ObservationTemplate, MappingRule,
)


def test_enriched_plan_includes_indicator_columns():
    plan = EnrichedMappingPlan(
        **_base_plan(),
        statvar_blueprint=StatVarBlueprint(
            base_properties=[StatVarProperty(name="populationType", value="dcs:Person")],
            constraint_columns=[], measure_columns=["Value"],
        ),
        value_dictionaries=[],
        column_relationships=[],
        composite_key=["Year"],
        indicator_columns=[
            IndicatorColumn(column_name="Variable", value_mappings=[
                IndicatorValueMapping(raw_value="Output", population_type="dcs:EconomicActivity",
                    measured_property="dcs:amount", stat_type="dcs:measuredValue", reason="Output"),
                IndicatorValueMapping(raw_value="Employees", population_type="dcs:Person",
                    measured_property="dcs:count", stat_type="dcs:measuredValue", reason="Count"),
            ]),
        ],
    )
    md = _plan_to_markdown(plan)
    assert "## Indicator Columns" in md
    assert "Variable" in md
    assert "Output" in md
    assert "dcs:EconomicActivity" in md
    assert "dcs:Person" in md


def test_enriched_plan_includes_mapping_rules():
    plan = EnrichedMappingPlan(
        **_base_plan(),
        statvar_blueprint=StatVarBlueprint(
            base_properties=[StatVarProperty(name="populationType", value="dcs:Person")],
            constraint_columns=[], measure_columns=["Value"],
        ),
        value_dictionaries=[],
        column_relationships=[],
        composite_key=["Year"],
        mapping_rules=[
            MappingRule(
                rule_id="value_main", measure_column="Value",
                description="Primary measure",
                observation=ObservationTemplate(
                    about_column="Country", about_expression="country/[DATA]",
                    date_column="Year", date_expression="[NUMBER]",
                    value_column="Value", value_expression="[NUMBER]",
                ),
                pvmap_rows=[
                    "Country,observationAbout,country/[DATA]",
                    "Year,observationDate,[NUMBER]",
                    "Value,value,[NUMBER]",
                ],
            ),
        ],
    )
    md = _plan_to_markdown(plan)
    assert "## Mapping Rules" in md
    assert "value_main" in md
    assert "Primary measure" in md
    assert "```" in md  # PVMAP rows in code block
    assert "Country,observationAbout,country/[DATA]" in md
```

- [ ] **Step 2: Run tests — verify FAIL**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_markdown.py -x -q`
Expected: FAIL — "Indicator Columns" not in markdown

- [ ] **Step 3: Add sections to `_plan_to_markdown()` in `src/agents/mapping_plan_agent.py`**

After the existing enriched sections (Time Resolution), add:

```python
    # Indicator Columns
    if hasattr(plan, 'indicator_columns') and plan.indicator_columns:
        lines.append("## Indicator Columns")
        lines.append("")
        lines.append("These columns change the core StatVar definition per-value (not just add a constraint).")
        lines.append("")
        for ic in plan.indicator_columns:
            lines.append(f"### `{ic.column_name}`")
            lines.append("")
            lines.append("| Value | populationType | measuredProperty | statType | Reason |")
            lines.append("|-------|---------------|-----------------|----------|--------|")
            for ivm in ic.value_mappings:
                lines.append(f"| `{ivm.raw_value}` | `{ivm.population_type}` | `{ivm.measured_property}` | `{ivm.stat_type}` | {ivm.reason} |")
            lines.append("")

    # Mapping Rules
    if hasattr(plan, 'mapping_rules') and plan.mapping_rules:
        lines.append("## Mapping Rules")
        lines.append("")
        for rule in plan.mapping_rules:
            lines.append(f"### Rule: `{rule.rule_id}` — {rule.description}")
            lines.append(f"- **Measure column:** `{rule.measure_column}`")
            obs = rule.observation
            lines.append(f"- **observationAbout:** `{obs.about_column}` = `{obs.about_expression}`")
            lines.append(f"- **observationDate:** `{obs.date_column}` = `{obs.date_expression}`")
            lines.append(f"- **value:** `{obs.value_column}` = `{obs.value_expression}`")
            if obs.unit:
                lines.append(f"- **unit:** `{obs.unit}`")
            if obs.unit_column:
                lines.append(f"- **unit (from column):** `{obs.unit_column}`")
            if rule.indicator_column:
                lines.append(f"- **indicator column:** `{rule.indicator_column}`")
            if rule.constraint_columns:
                lines.append(f"- **constraints:** {', '.join(f'`{c}`' for c in rule.constraint_columns)}")
            if rule.pvmap_rows:
                lines.append("")
                lines.append("**Target PVMAP rows:**")
                lines.append("```csv")
                for row in rule.pvmap_rows:
                    lines.append(row)
                lines.append("```")
            lines.append("")
```

- [ ] **Step 4: Run tests — verify PASS**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_markdown.py -x -q`

- [ ] **Step 5: Run full suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/agents/mapping_plan_agent.py tests/pipeline/plan/test_plan_markdown.py
git commit -m "feat(plan): add Indicator Columns and Mapping Rules to plan markdown"
```

---

### Task 3: Update the plan prompt with indicator + mapping rule instructions

**Files:**
- Modify: `src/resources/prompts/mapping_plan_prompt_v2.txt`

- [ ] **Step 1: Add Step 2b after existing Step 2 (Column Role Assignment)**

After the Step 2 section (around line 87), insert:

```
### Step 2b: Identify Indicator Columns

For each dimension column, determine if it is a CONSTRAINT or an INDICATOR:

- **CONSTRAINT column** (most dimensions): values add a property-value pair to the StatVar.
  Example: Gender column — M adds gender=dcs:Male, F adds gender=dcs:Female.
  The populationType and measuredProperty stay the SAME regardless of the value.

- **INDICATOR column** (rare but critical): values CHANGE the core StatVar definition.
  Example: Variable column — "Output" means measuredProperty=dcs:amount with populationType=dcs:EconomicActivity,
  while "Employees" means measuredProperty=dcs:count with populationType=dcs:Person.
  
Detection: If a dimension column's values describe WHAT IS BEING MEASURED (not who/where/when/how), it is likely an indicator column. Common names: Variable, Indicator, Series, Metric, Measure_Type.

For each indicator column, create an IndicatorColumn entry with a value_mapping per unique value:
- raw_value: exact string from raw_value_profiles
- population_type: what entity is being measured for THIS value
- measured_property: what property of that entity
- stat_type: how it's measured (usually dcs:measuredValue)
- reason: brief explanation

If NO indicator column exists, leave indicator_columns empty — the StatVar blueprint's static properties apply uniformly.
```

- [ ] **Step 2: Replace Step 3 (StatVar Blueprint) with expanded version**

Replace the existing Step 3 with:

```
### Step 3: Mapping Rules

For EACH measure column in the dataset, create a MappingRule. This is the most critical section — it defines exactly how PVMAP rows should be generated.

**For each measure column:**

1. **rule_id**: short identifier (e.g., "value_local_currency", "value_usd")
2. **measure_column**: column name holding the numeric value
3. **description**: what this measure represents
4. **observation**: how place, time, and value wire up
   - about_column + about_expression (e.g., "Country", "country/[DATA]")  
   - date_column + date_expression (e.g., "Year", "[NUMBER]")
   - value_column + value_expression (e.g., "Value", "[NUMBER]")
   - unit: static unit if known (e.g., "dcs:USDollar"), or null
   - unit_column: column providing unit dynamically (e.g., "UnitType"), or null
5. **indicator_column**: name of indicator column (or null if none)
6. **constraint_columns**: dimension columns that add constraints
7. **static_properties**: properties that apply to ALL observations in this rule (e.g., statType)
8. **pvmap_rows**: the ACTUAL PVMAP CSV rows this rule generates

**PVMAP ROW GENERATION:**
Generate concrete PVMAP CSV rows following this pattern:

For the place column:
  column_name,observationAbout,{expression}

For the time column:
  column_name,observationDate,{expression}

For the measure column:
  column_name,value,[NUMBER],{static_prop1},{static_val1},{static_prop2},{static_val2},...

For each indicator column value:
  INDICATOR_COL:VALUE,populationType,{pop_type},measuredProperty,{measured_prop}

For each constraint column value (from value_dictionaries):
  CONSTRAINT_COL:VALUE,{dc_property},{dcid}

For qualifier columns (unit, scaling):
  QUALIFIER_COL:VALUE,{property},{value}

MULTI-MEASURE HANDLING:
If the dataset has multiple measure columns (e.g., Value + ValueUSD):
- Create SEPARATE mapping rules for each
- Each rule may have different units, StatVar properties, or transformations
- Value and ValueUSD are NOT co-referent — they represent different observations with different units

INDICATOR + CONSTRAINT INTERACTION:
When both indicator and constraint columns exist:
- Indicator values define the BASE StatVar (populationType + measuredProperty)
- Constraint values add ADDITIONAL properties on top
- Example: Variable="Employees" + Activity="Manufacturing" → Count_Person with economicActivity=Manufacturing
```

- [ ] **Step 3: Update the Output schema section**

In the JSON output example (near line 224), add the new fields:

```json
  "indicator_columns": [
    {
      "column_name": "Variable",
      "value_mappings": [
        {
          "raw_value": "Output",
          "population_type": "dcs:EconomicActivity",
          "measured_property": "dcs:amount",
          "stat_type": "dcs:measuredValue",
          "extra_properties": [],
          "reason": "Industrial output in monetary terms"
        }
      ]
    }
  ],
  "mapping_rules": [
    {
      "rule_id": "value_local",
      "measure_column": "Value",
      "description": "Observations in local currency",
      "observation": {
        "about_column": "CountryCode",
        "about_expression": "countryNumeric/[DATA]",
        "date_column": "Year",
        "date_expression": "[NUMBER]",
        "value_column": "Value",
        "value_expression": "[NUMBER]",
        "unit": null,
        "unit_column": null
      },
      "indicator_column": "Variable",
      "constraint_columns": ["ActivityCode"],
      "static_properties": [{"name": "statType", "value": "dcs:measuredValue"}],
      "pvmap_rows": [
        "CountryCode,observationAbout,countryNumeric/[DATA]",
        "Year,observationDate,[NUMBER]",
        "Variable:Output,populationType,dcs:EconomicActivity,measuredProperty,dcs:amount",
        "Variable:Employees,populationType,dcs:Person,measuredProperty,dcs:count",
        "ActivityCode,economicActivity,[DATA]",
        "Value,value,[NUMBER],statType,dcs:measuredValue"
      ]
    }
  ]
```

- [ ] **Step 4: Commit**

```bash
git add src/resources/prompts/mapping_plan_prompt_v2.txt
git commit -m "feat(plan): add indicator column and mapping rule instructions to prompt v2"
```

---

### Task 4: Update skeleton converter to use mapping rule PVMAP rows

**Files:**
- Modify: `src/pipeline/plan/skeleton_converter.py`
- Test: `tests/pipeline/plan/test_skeleton_converter.py`

- [ ] **Step 1: Write test for mapping-rule-based skeleton**

Add to `tests/pipeline/plan/test_skeleton_converter.py`:

```python
def test_skeleton_from_mapping_rules():
    """When mapping_rules have pvmap_rows, use them directly."""
    from src.api.models.plan import (
        EnrichedMappingPlan, DatasetUnderstanding, StatVarBlueprint,
        StatVarProperty, MappingRule, ObservationTemplate,
    )
    plan = EnrichedMappingPlan(
        dataset_name="test",
        understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
        active_columns=[],
        ignored_columns=[],
        static_properties=[],
        global_notes=[],
        statvar_blueprint=StatVarBlueprint(
            base_properties=[StatVarProperty(name="populationType", value="dcs:Person")],
            constraint_columns=[], measure_columns=["Value"],
        ),
        composite_key=["A"],
        mapping_rules=[
            MappingRule(
                rule_id="r1", measure_column="Value", description="test",
                observation=ObservationTemplate(
                    about_column="Country", about_expression="country/{Data}",
                    date_column="Year", date_expression="{Number}",
                    value_column="Value", value_expression="{Number}",
                ),
                pvmap_rows=[
                    "Country,observationAbout,country/{Data}",
                    "Year,observationDate,{Number}",
                    "Value,value,{Number},populationType,dcs:Person",
                ],
            ),
        ],
    )
    from src.pipeline.plan.skeleton_converter import plan_to_skeleton_csv
    csv = plan_to_skeleton_csv(plan)
    assert "Country,observationAbout,country/{Data}" in csv
    assert "Year,observationDate,{Number}" in csv
    assert "Value,value,{Number},populationType,dcs:Person" in csv
```

- [ ] **Step 2: Run test — verify FAIL**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_skeleton_converter.py::test_skeleton_from_mapping_rules -x -q`

- [ ] **Step 3: Update `plan_to_skeleton_csv()` in `src/pipeline/plan/skeleton_converter.py`**

At the top of `plan_to_skeleton_csv()`, add a check for mapping rules:

```python
def plan_to_skeleton_csv(plan: "MappingPlan") -> str:
    # If this is an EnrichedMappingPlan with mapping_rules that have pvmap_rows,
    # use them directly instead of generating from candidates
    if hasattr(plan, 'mapping_rules') and plan.mapping_rules:
        all_pvmap_rows = []
        for rule in plan.mapping_rules:
            if rule.pvmap_rows:
                all_pvmap_rows.extend(rule.pvmap_rows)
        if all_pvmap_rows:
            # Find max columns for header
            max_cols = max(len(row.split(",")) for row in all_pvmap_rows) if all_pvmap_rows else 1
            header = "key" + "," * (max_cols - 1)
            lines = [header] + all_pvmap_rows
            return "\n".join(lines) + "\n"

    # --- Existing logic (candidate-based skeleton) ---
    # ... rest of the function unchanged ...
```

- [ ] **Step 4: Run test — verify PASS**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_skeleton_converter.py -x -q`

- [ ] **Step 5: Run full suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/pipeline/plan/skeleton_converter.py tests/pipeline/plan/test_skeleton_converter.py
git commit -m "feat(plan): skeleton converter uses mapping rule pvmap_rows when available"
```

---

## Execution Order

```
Task 1 (models) — foundation, no deps
Task 2 (markdown) — depends on Task 1
Task 3 (prompt) — depends on Task 1 (uses model names in examples)
Task 4 (skeleton) — depends on Task 1

Tasks 2, 3, 4 are independent of each other, all depend on Task 1.
```
