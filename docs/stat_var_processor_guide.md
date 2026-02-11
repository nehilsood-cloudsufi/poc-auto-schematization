# stat_var_processor.py — Comprehensive Guide

> **Source:** `src/pipeline/validation/stat_var_processor.py` (~3,100 lines)
> **Wrapper:** `src/tools/validation_tool.py` (~550 lines)

## 1. Big Picture Overview

`stat_var_processor.py` is the core engine that transforms raw CSV data into Data Commons StatVarObservations using a Property-Value Map (PVMAP). It is the **validation backbone** of the pipeline — if it produces output rows, the PVMAP is valid.

```
┌─────────────────┐    ┌──────────────┐    ┌────────────────┐
│  Input CSV       │    │  PVMAP CSV    │    │ Metadata CSV   │
│  (full dataset)  │    │  (generated)  │    │  (optional)    │
└────────┬────────┘    └──────┬───────┘    └───────┬────────┘
         │                    │                     │
         └────────────┬───────┘─────────────────────┘
                      │
                      ▼
         ┌────────────────────────┐
         │  StatVarDataProcessor  │
         │  ─────────────────     │
         │  1. Load PVMAP         │
         │  2. Read CSV rows      │
         │  3. Lookup PVs/cell    │
         │  4. Merge PV layers    │
         │  5. Resolve place/date │
         │  6. Generate StatVars  │
         │  7. Collect SVObs      │
         │  8. Validate & filter  │
         └────────────┬──────────┘
                      │
         ┌────────────┼────────────┐
         ▼            ▼            ▼
   ┌──────────┐ ┌──────────┐ ┌──────────┐
   │ .mcf     │ │ .csv     │ │ .tmcf    │
   │ StatVar  │ │ SVObs    │ │ Template │
   │ defs     │ │ data     │ │ MCF      │
   └──────────┘ └──────────┘ └──────────┘
```

**In the automated pipeline**, `stat_var_processor.py` is **never imported as a Python module**. It is invoked via `subprocess.run()` by `validation_tool.py`, which acts as the ADK agent's interface to validation.

---

## 2. The Three Inputs

### 2.1 Input CSV (required)

The raw data CSV. This is the **full dataset** (not the sampled version). Each row represents one or more potential StatVarObservations.

```csv
State,Year,Population,Unemployment Rate
California,2020,39538223,7.9
Texas,2020,29145505,7.6
```

### 2.2 PVMAP CSV (required)

The Property-Value Map tells the processor how to interpret each column header or cell value. Format: `key, property1, value1, property2, value2, ...`

```csv
State,observationAbout,{Data}
Year,observationDate,{Data}
Population,populationType,Person,measuredProperty,count,value,{Number}
Unemployment Rate,populationType,Person,measuredProperty,unemploymentRate,value,{Number}
California,observationAbout,geoId/06
Texas,observationAbout,geoId/48
```

**Key patterns in values:**
| Pattern | Meaning |
|---------|---------|
| `{Data}` | Pass-through: use the raw cell string value |
| `{Number}` | Use the numeric value parsed from the cell |
| `{Key}` | The original lookup key |
| `@PropertyName` | Reference another property's resolved value |
| `{PropertyName}` | Same as `@PropertyName` |
| `#Internal` | Internal/processing property (not emitted) |

### 2.3 Metadata CSV (optional)

A 2-column config file (parameter, value) that overrides processing settings:

```csv
datasetname,Central Bank Policy Rate
source,Bank for International Settlements
unit,Percent Per Annum
observation_date_format,%Y
```

Any row whose key matches a known config key (e.g., `header_rows`, `skip_rows`, `observation_date_format`) is treated as configuration rather than a PVMAP entry. This is parsed by `PropertyValueMapper._process_csv_row()` at line 180.

---

## 3. Two Core Classes

### 3.1 StatVarsMap (lines 204–1468)

**Purpose:** In-memory store for StatVars and StatVarObservations with validation, deduplication, and output generation.

**Key data members:**

| Member | Type | Purpose |
|--------|------|---------|
| `_statvars_map` | `dict` | Maps DCID → `{property: value}` for each StatVar |
| `_statvar_obs_map` | `dict` | Maps fingerprint key → `{property: value}` for each SVObs |
| `_statvar_obs_props` | `dict` | Tracks unique values per SVObs property (for tMCF) |
| `_dc_api_ids_cache` | `dict` | Cache for DC API "is defined DCID" lookups |
| `_statvar_dcid_remap` | `dict` | Old DCID → new DCID substitution map |
| `_statvar_resolver` | `SchemaResolver` | Resolves existing StatVars from MCF files |

### 3.2 StatVarDataProcessor (lines 1470–2934)

**Purpose:** Main orchestrator — reads CSV files, performs PVMAP lookups, generates StatVar/SVObs, writes outputs.

**Key data members:**

| Member | Type | Purpose |
|--------|------|---------|
| `_pv_mapper` | `PropertyValueMapper` | PVMAP lookup handler |
| `_statvars_map` | `StatVarsMap` | StatVar/SVObs storage |
| `_place_resolver` | `PlaceResolver` | Geographic name resolution |
| `_column_pvs` | `dict` | PVs per column indexed by column number |
| `_row_pvs` | `list` | Accumulated PVs for the current row |
| `_file_pvs` | `dict` | PVs applicable to the entire file |
| `_reference_pattern` | `regex` | Pattern matching `@Variable` and `{Variable}` |

---

## 4. Step-by-Step Processing Flow

```
main() → process() → StatVarDataProcessor:
  ├── __init__(): load PVMAP via PropertyValueMapper
  ├── setup_config(): parse metadata, configure column refs
  ├── process_data_files():
  │   ├── For each CSV file:
  │   │   ├── Skip header/ignore rows per config
  │   │   ├── For each data row:
  │   │   │   └── process_row()
  │   │   └── filter_svobs() (remove outliers)
  │   └── Record processing rate counters
  └── write_outputs():
      ├── drop_invalid_statvars()
      ├── write_statvars_mcf()   → .mcf file
      ├── write_statvar_obs_csv() → .csv file
      └── write_statvar_obs_tmcf() → .tmcf file
```

### The `process()` function (line 3003)

This is the top-level entry point. It:
1. Initializes config from command-line flags and metadata file
2. Expands input file wildcards
3. Creates a `StatVarDataProcessor` instance
4. Calls `process_data_files()` then `write_outputs()`
5. Checks for error counters and returns `True`/`False`

### The `main()` function (line 3067)

Called by `app.run(main)` (absl). Configures cloud logging, optionally starts HTTP server, then calls `process()`.

---

## 5. Deep Dive: PVMAP Lookup Logic

PVMAP lookup is the process of finding the right set of property:value pairs for each cell in the CSV. This is handled by the `PropertyValueMapper` class (`src/processing/mapping/property_value_mapper.py`).

### 5.1 PVMAP Storage Structure

The PVMAP is stored as a two-level dictionary:

```python
_pv_map = {
    'GLOBAL': {           # Default namespace
        'State': {'observationAbout': '{Data}'},
        'California': {'observationAbout': 'geoId/06'},
        ...
    },
    'ColumnHeader': {     # Column-specific namespace
        'Male': {'gender': 'Male'},
        ...
    },
}
```

The first-level keys are **namespaces** — typically column headers or `'GLOBAL'`. When looking up a cell value, the column header namespace is tried first, then `GLOBAL`.

### 5.2 Cell Lookup Priority Chain

`get_pvs_for_cell()` (line 2109) looks up PVs for each cell in this priority order:

```
1. Cell value        → e.g., "California"
2. Cell:row:col      → e.g., "Cell:5:3"
3. Column:col        → e.g., "Column:3"
4. Row:row           → e.g., "Row:5"
```

The first match wins. For each key, `get_all_pvs_for_value()` tries:

1. **Exact match** in column namespace → `_pv_map[column_header][key]`
2. **Exact match** with namespace prefix → `_pv_map['GLOBAL'][column_header:key]`
3. **Case-insensitive** → `_pv_map[namespace][key.lower()]`
4. **Filtered key** → strip non-alphanumeric characters, retry
5. **Substring match** → any PVMAP key that is a substring of the value
6. **Multi-word splitting** → split by word delimiter, try subsets

### 5.3 The 5-Layer PV Merge

For each cell, PVs are collected from 5 sources and merged (line 2292):

```python
col_pvs_list = [
    self.get_file_header_pvs(),              # Layer 1: File-level PVs
    self.get_column_header_pvs(col_index),   # Layer 2: Column header PVs
    self.get_section_header_pvs(col_index),  # Layer 3: Section header PVs
    row_col_pvs.get(col_index, {}),          # Layer 4: Cell's own PVs
    {'Data': col_value},                     # Layer 5: Raw cell value
]
```

These are merged via `resolve_value_references()`, which:
1. Flattens the list into a single dict (later layers override earlier)
2. Resolves `@Variable` and `{Variable}` references between properties
3. Processes special properties (`#Regex`, `#Format`, `#Eval`)

### 5.4 Reference Resolution

References like `{Data}`, `@observationAbout`, or `{Number}` are replaced with the resolved value of the referenced property:

```
PVMAP entry:  Year, observationDate, {Data}
Cell value:   "2020"
After merge:  Data = "2020", so observationDate = "2020"
```

The `resolve_value_references()` method (line ~1850) performs iterative resolution, handling chains of references. Unresolved references trigger a second pass.

### 5.5 Special Processing Properties

| Property | Purpose | Example |
|----------|---------|---------|
| `#Regex` | Apply regex with named groups | `#Regex: (?P<age>\d+) to (?P<age_end>\d+)` |
| `#Format` | Python format string | `#Format: observationDate={year}-{month}` |
| `#Eval` | Evaluate Python expression | `#Eval: value=float(Data)*1000` |
| `#Header` | Mark a row as column header | `#Header: gender` |
| `#IgnoreRow` | Skip this row entirely | `#IgnoreRow: True` |
| `#Aggregate` | Aggregation type for duplicates | `#Aggregate: sum` |
| `#Multiply` | Multiply numeric value | `#Multiply: 1000` |
| `#DateFormat` | Input date format | `#DateFormat: %m/%d/%Y` |

### 5.6 Carry-Forward Pattern

If a column's PVs do **not** contain `value` or `measurementResult`, those PVs are "carried forward" to subsequent columns as row-level context (line 2318–2342). This allows left-side columns (like place, date, category) to contribute their properties to right-side value columns.

---

## 6. Deep Dive: StatVar DCID Generation

The DCID (Data Commons Identifier) uniquely identifies each statistical variable. Generation happens in `StatVarsMap.generate_statvar_dcid()` (line 450).

### 6.1 DCID Generation Flow

```
generate_statvar_dcid(pvs):
  1. Check pvs for existing 'dcid' or 'Node' → return if present
  2. Check _statvar_resolver for existing StatVar → return if found
  3. Try standard generator (get_statvar_dcid from statvar_dcid_generator.py)
     - Works for defined DC schema properties only
     - Sanitizes: replace non-alphanumeric with '_'
  4. If schemaless or standard fails → build DCID manually:
     a. For each property in default_statvar_pvs order:
        - Get DCID term via _get_dcid_term_for_pv()
     b. Handle measurementDenominator suffix ("AsAFractionOf")
     c. Sort remaining properties alphabetically
     d. Join all terms with '_'
  5. Check _statvar_dcid_remap for substitution
  6. Add namespace prefix (dcid:)
  7. Store as pvs['Node']
```

### 6.2 Standard Generator (`statvar_dcid_generator.py`)

Located at `src/data_commons/statvar/statvar_dcid_generator.py`, the standard generator:

- Uses the Data Commons naming convention
- Handles quantity notations: `[2 Person]`, `[USDollar 10000 14999]`
- Applies prepend/append rules per property (e.g., `householderRace` → `HouseholderRace{Value}`)
- Resolves NAICS codes to industry names
- Resolves SOC codes to occupation names
- Ignores properties like `unit`, `Node`, `memberOf`, `typeOf`, `name`, `description`, etc.

**Default ignored properties** (line 57):
```python
_DEFAULT_IGNORE_PROPS = (
    'unit', 'Node', 'memberOf', 'typeOf', 'constraintProperties',
    'name', 'description', 'descriptionUrl', 'label', 'url',
    'alternateName', 'scalingFactor',
)
```

### 6.3 Schemaless Path

When `schemaless=True` (or standard generation fails), the DCID is built from raw PVs:

```python
# For property 'age' with value 'Years5To17':
_get_dcid_term_for_pv('age', 'Years5To17')
# → 'Age_Years5To17'  (schemaless: property prefix added)
# → 'Years5To17'      (standard: value only)
```

Schemaless StatVars can have their `measuredProperty` set to the DCID itself via `convert_to_schemaless_statvar()` (line 644).

### 6.4 DCID Remapping

After generation, the DCID is checked against `_statvar_dcid_remap` (loaded from a CSV file) for substitution. This allows manual corrections without changing the PVMAP.

---

## 7. Deep Dive: Validation Error Handling

### 7.1 Subprocess Execution

`validation_tool.py` wraps `stat_var_processor.py` as a subprocess:

```python
result = subprocess.run(
    cmd,
    capture_output=True,
    text=True,
    timeout=300,           # 5 minutes
    cwd=str(PROJECT_ROOT),
    env=env                # PYTHONPATH includes PROJECT_ROOT + src/
)
```

**Command constructed by `build_validation_command()`** (line 227):
```bash
.venv/bin/python3 src/pipeline/validation/stat_var_processor.py \
  --input_data=input/dataset/test_data/input_data.csv \
  --pv_map=output/dataset/generated_pvmap.csv \
  --config_file=input/dataset/input_metadata/metadata.csv \
  --generate_statvar_name=True \
  --output_path=output/dataset/processed \
  --debug=True
```

### 7.2 Five Possible Outcomes

`run_validation()` (line 316) returns a dict with one of five outcomes:

| # | Condition | `success` | When It Happens |
|---|-----------|-----------|-----------------|
| 1 | returncode=0, data_rows > 0 | `True` | PVMAP correctly transforms data |
| 2 | returncode=0, data_rows=0 | `False` | Process ran but produced no output (bad column mappings) |
| 3 | returncode ≠ 0 | `False` | Process crashed (syntax error, import failure, etc.) |
| 4 | Input file not found | `False` | File path validation failed before subprocess |
| 5 | Timeout (300s) | `False` | Processing took too long |

### 7.3 Error Feedback Generation

Two feedback mechanisms, with smart filtering preferred:

**Smart log filtering** (primary):
1. `stat_var_processor.py` writes a `processed_counters.txt` file when `--debug=True`
2. `filter_counters()` parses this file into structured counter data
3. `generate_concise_feedback()` produces ~50–80 lines of actionable feedback
4. Identifies specific failing value patterns and column issues

**Fallback random sampling** (when no counters file):
```python
extract_log_samples(
    log_output,
    tail_lines=50,      # Last 50 lines
    sample_count=10,     # 10 random middle samples
    sample_size=5        # 5 consecutive lines each
)
# Total: ~300 lines max (prevents token budget overrun)
```

### 7.4 StatVar Analysis Summary

On success, `_extract_statvar_summary()` (line 87) parses the generated MCF file and produces:
- Property → value distribution analysis
- Flags for raw strings needing DCID mappings
- Flags for special characters suggesting broken CSV parsing
- Flags for single-value dimensions suggesting missing breakdowns
- Output capped at 40 lines

### 7.5 Return Dictionary Structure

All outcomes return the same shape:
```python
{
    "success": bool,
    "error": str | None,           # Human-readable error message
    "error_logs": str | None,      # Sampled logs (fallback only)
    "structured_feedback": str | None,  # Smart counter-based feedback
    "counters": dict,              # Parsed counter dict (backward compat)
    "output_file": str | None,     # Path to processed.csv
    "data_rows": int,              # Number of output data rows
    "stdout": str,                 # Process stdout
    "stderr": str,                 # Process stderr
    "returncode": int,             # Process exit code (-1 on timeout)
    "counter_summary": str,        # Formatted summary of counters
    "statvar_analysis": str,       # MCF analysis (success only)
}
```

---

## 8. Deep Dive: Place Resolution

Place resolution converts human-readable geographic names into Data Commons place DCIDs. Handled by `resolve_svobs_place()` (line 2761).

### 8.1 Three-Strategy Chain

```
resolve_svobs_place(pvs):
  ┌─────────────────────────┐
  │ 1. Already a DCID?      │
  │    is_place_dcid(place)  │──Yes──▶ Return True
  └────────┬────────────────┘
           │ No
  ┌────────▼────────────────┐
  │ 2. PVMAP lookup         │
  │    get_all_pvs_for_value │
  │    (place,               │
  │     'observationAbout')  │──Found DCID──▶ Return True
  └────────┬────────────────┘
           │ Not found
  ┌────────▼────────────────┐
  │ 3. PlaceResolver        │
  │    (Maps API / geocode)  │
  │    resolve_places=True   │──Resolved──▶ Return True
  │    required in config    │
  └────────┬────────────────┘
           │ Failed
           ▼
    Counter: error-unresolved-place
    Return False
```

### 8.2 What Counts as a Place DCID

The `is_place_dcid()` utility checks if a value:
- Starts with `dcid:`, `dcs:`, or `geoId/`
- Matches known place patterns (country codes, FIPS codes, ISO codes)
- Contains a known DC namespace prefix

### 8.3 PlaceResolver

When `resolve_places=True` is configured, the `PlaceResolver` class (`src/data_commons/place/place_resolver.py`) is used. It receives:
- `place_name`: the raw string
- `country`: optional country restriction (from `#country` PV or config)
- `administrative_area`: optional admin area restriction

It returns a DCID like `geoId/06` for "California".

---

## 9. Deep Dive: Date Resolution

Date resolution normalizes raw date strings into the `YYYY-MM-DD` (or `YYYY`) format expected by Data Commons. Handled by `resolve_svobs_date()` (line 2822).

### 9.1 Resolution Flow

```
resolve_svobs_date(pvs):
  1. Get observationDate value
  2. Normalize: replace non-alphanumeric chars with '-'
     "2020/01/15" → "2020-01-15"
  3. Determine output format:
     - From config observation_date_format, OR
     - Auto-detect via get_observation_date_format()
       "2020"       → "%Y"
       "2020-01"    → "%Y-%m"
       "2020-01-15" → "%Y-%m-%d"
  4. Try parsing with output format (already formatted?)
  5. If fails: try input format from #DateFormat PV or config
  6. If fails: try eval_functions.format_date() (flexible parser)
  7. If resolved:
     - Set pvs['observationDate'] = resolved_date
     - Infer observationPeriod if empty:
       "%Y"       → "P1Y" (yearly)
       "%Y-%m"    → "P1M" (monthly)
       "%Y-%m-%d" → "P1D" (daily)
  8. Return True/False
```

### 9.2 Period Inference

`get_observation_period_for_date()` automatically sets the observation period based on the date granularity, but only if `observationPeriod` is empty string (explicitly set to empty by default PVs, meaning "please infer").

---

## 10. Deep Dive: Duplicate Handling

The processor handles three types of duplicates at different levels.

### 10.1 Duplicate StatVars

When two rows generate the same StatVar DCID but with **different** property values:

```python
add_dict_to_map(dcid, pvs, _statvars_map, duplicate_prop='#ErrorDuplicateStatVar')
```

- If PVs are identical → allowed (no error)
- If PVs differ → the second entry is stored under `#ErrorDuplicateStatVar`
- Counter: `error-duplicate-statvars`

### 10.2 Duplicate StatVarObservations

When two rows produce SVObs for the same place + date + variable but **different values**:

**Fingerprint key** (`get_svobs_key()`, line 754):
```python
# Key = all SVObs properties EXCEPT 'value' and 'measurementResult'
key = fingerprint_node(pvs, ignore=_IGNORE_SVOBS_KEY_PVS)
```

**Resolution depends on config:**

| Config Setting | Behavior |
|---------------|----------|
| `aggregate_duplicate_svobs = 'sum'` | Sum the values |
| `aggregate_duplicate_svobs = 'mean'` | Average the values |
| `aggregate_duplicate_svobs = 'min'` | Keep minimum |
| `aggregate_duplicate_svobs = 'max'` | Keep maximum |
| `aggregate_duplicate_svobs = 'first'` | Keep first encountered |
| `aggregate_duplicate_svobs = 'last'` | Keep last encountered |
| `aggregate_duplicate_svobs = None` (default) | Mark as error |

The `aggregate_value()` method (line 771) performs the aggregation. Merged SVObs are tracked via the `#MergedSVObs` property.

### 10.3 Duplicate SVObs with Different Key Properties

`set_statvar_dup_svobs()` (line 856) detects SVObs that have the same place + date + variable but differ in a **key property** (like a dimension that should create separate StatVars). These are marked with `#ErrorDuplicateSVObs`.

If `drop_statvars_with_dup_svobs=True` (default), the entire StatVar and all its observations are dropped.

### 10.4 Cascade Cleanup

`drop_invalid_statvars()` (line 1095) performs cascade cleanup:
1. Remove StatVars with error markers
2. Remove all SVObs referencing dropped StatVars
3. `drop_statvars_without_svobs()` removes StatVars that have no remaining observations

---

## 11. Complete Walkthrough Example

Given this input CSV:

```csv
State,Year,Population
California,2020,39538223
Texas,2020,29145505
```

And this PVMAP:

```csv
State,observationAbout,{Data}
Year,observationDate,{Data}
Population,populationType,Person,measuredProperty,count,value,{Number}
California,observationAbout,geoId/06
Texas,observationAbout,geoId/48
```

### Processing Row: `California, 2020, 39538223`

**Pass 1 — Collect per-column PVs:**

| Column | Value | PVMAP Match | PVs |
|--------|-------|-------------|-----|
| 0 | California | `California` → `{observationAbout: geoId/06}` | `{observationAbout: geoId/06, Data: California}` |
| 1 | 2020 | `Year` matched by column header | `{observationDate: {Data}, Data: 2020}` → resolved: `{observationDate: 2020}` |
| 2 | 39538223 | No exact match, but `Number: 39538223` | `{Number: 39538223}` |

Column headers are looked up in the PVMAP during header detection:
- "State" → `{observationAbout: {Data}}` (column header PV)
- "Year" → `{observationDate: {Data}}` (column header PV)
- "Population" → `{populationType: Person, measuredProperty: count, value: {Number}}` (column header PV)

**Pass 2 — Merge layers and identify SVObs:**

For column 2 ("39538223"):
```python
merged_pvs = {
    # From file PVs: (none)
    # From column header "Population":
    'populationType': 'Person',
    'measuredProperty': 'count',
    'value': '{Number}',
    # From row carry-forward (columns 0, 1):
    'observationAbout': 'geoId/06',
    'observationDate': '2020',
    # From cell:
    'Data': '39538223',
    'Number': 39538223,
}
# After reference resolution:
# value = {Number} → 39538223
```

**Pass 3 — Create StatVar and SVObs:**

Separate into StatVar PVs and SVObs PVs:
- **StatVar PVs:** `{populationType: Person, measuredProperty: count}`
- **SVObs PVs:** `{observationAbout: geoId/06, observationDate: 2020, value: 39538223, variableMeasured: ...}`

Generate DCID: `Count_Person` (via standard generator)

**Result:**

StatVar:
```
Node: dcid:Count_Person
typeOf: dcs:StatisticalVariable
populationType: dcs:Person
measuredProperty: dcs:count
statType: dcs:measuredValue
```

SVObs row in CSV:
```
geoId/06,2020,dcid:Count_Person,39538223
```

---

## 12. The Three Output Formats

### 12.1 MCF File (`processed_stat_vars.mcf`)

Generated by `write_statvars_mcf()` (line 1125). Contains StatVar definitions:

```
Node: dcid:Count_Person
typeOf: dcs:StatisticalVariable
populationType: dcs:Person
measuredProperty: dcs:count
statType: dcs:measuredValue
name: "Count_Person"
```

**Generation steps:**
1. Optionally drop existing MCF nodes (`drop_existing_mcf_nodes`)
2. Generate human-readable names (`generate_statvar_name`) if `generate_statvar_name=True`
3. Run `sanity_check_nodes()` for schema validation
4. Optionally generate new schema MCF (`generate_schema_mcf`)
5. Write with sorted nodes

### 12.2 CSV File (`processed.csv`)

Generated by `write_statvar_obs_csv()` (line 1334). Contains StatVarObservations:

```csv
observationAbout,observationDate,variableMeasured,value
geoId/06,2020,dcid:Count_Person,39538223
geoId/48,2020,dcid:Count_Person,29145505
```

**Column selection:** Determined by `get_statvar_obs_columns()` which collects all unique SVObs property names seen during processing. Numeric values are formatted to `precision_digits` decimal places.

### 12.3 tMCF File (`processed.tmcf`)

Generated by `write_statvar_obs_tmcf()` (line 1379). Template MCF mapping CSV columns to properties:

```
Node: E:Data->E0
typeOf: dcs:StatVarObservation
observationAbout: C:Data->observationAbout
observationDate: C:Data->observationDate
variableMeasured: C:Data->variableMeasured
value: C:Data->value
```

**Constant detection:** If a property has only 1 unique value across all SVObs, it's emitted as a constant in the tMCF rather than a column reference.

---

## 13. Key Counters

The processor tracks hundreds of counters via the `Counters` class. The most important ones:

### Input Counters
| Counter | Meaning |
|---------|---------|
| `input-files-processed` | Number of CSV files read |
| `input-rows-processed` | Total rows processed |
| `input-header-rows` | Rows identified as headers |
| `input-data-rows` | Rows containing data (at least 1 SVObs) |
| `input-rows-ignored` | Rows skipped (no PVs, too few columns, etc.) |

### Generation Counters
| Counter | Meaning |
|---------|---------|
| `generated-statvars` | Unique StatVars created |
| `generated-svobs` | Total SVObs created |
| `resolved-places` | Places resolved via PlaceResolver |

### Error Counters
| Counter | Meaning |
|---------|---------|
| `error-duplicate-statvars` | Same DCID, different PVs |
| `error-unresolved-place` | Place name not resolved to DCID |
| `error-svobs-missing-property` | SVObs missing required property |
| `dropped-svobs-unresolved-place` | SVObs dropped due to unresolved place |
| `dropped-svobs-unresolved-date` | SVObs dropped due to unparseable date |
| `dropped-invalid-statvars` | StatVars removed during cleanup |
| `dropped-statvars-without-svobs` | StatVars with no observations |
| `warning-missing-property-key` | PVMAP key not found for cell value |

---

## 14. Key File Paths

| File | Purpose |
|------|---------|
| `src/pipeline/validation/stat_var_processor.py` | Core processor (this guide) |
| `src/tools/validation_tool.py` | ADK agent subprocess wrapper |
| `src/processing/mapping/property_value_mapper.py` | PVMAP loading and lookup |
| `src/data_commons/statvar/statvar_dcid_generator.py` | Standard DCID generation |
| `src/data_commons/place/place_resolver.py` | Geographic name resolution |
| `src/data_commons/schema/schema_resolver.py` | Existing StatVar resolution |
| `src/data_commons/schema/schema_generator.py` | StatVar name generation |
| `src/data_commons/schema/schema_checker.py` | MCF sanity checks |
| `src/data_commons/mcf/mcf_file_util.py` | MCF file I/O utilities |
| `src/data_commons/mcf/mcf_diff.py` | MCF node diffing and fingerprinting |
| `src/infrastructure/config/config_map.py` | Configuration management |
| `src/infrastructure/config/config_flags.py` | CLI flag definitions |
| `src/infrastructure/metrics/counters.py` | Counter tracking |
| `src/processing/evaluation/eval_functions.py` | Date formatting, evaluation |
| `src/processing/filtering/filter_data_outliers.py` | SVObs outlier filtering |
| `src/pipeline/validation/log_filter.py` | Smart log filtering for feedback |
