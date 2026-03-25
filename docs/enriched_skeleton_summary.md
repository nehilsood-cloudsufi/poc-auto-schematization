# Enriched Skeleton Summary for PVMAP Generation

**Date:** February 2026
**Branch:** `feature/nehil/restructuring-cleaning`
**Status:** Implemented and pipeline-tested

## Problem Statement

The `skeleton_summary` is the most critical state key for PVMAP generation — it's the structured dataset analysis injected directly into the LLM prompt. Three problems existed:

1. **Silently dropped**: The prompt template (`improved_pvmap_prompt.txt`) had no `{{DATA_CONTEXT}}` placeholder. The `helpers.py` replacement at line 79 was a no-op — the skeleton never reached the LLM.
2. **Too thin**: The old skeleton only showed topology, anchors (column + format), dimensions (truncated to 5 values), measurement, and StatVar pattern. Missing critical info that caused top validation errors.
3. **Broken data flow**: `SamplingAgentWrapper` wrote the sampled file to `output/{dataset}/agentic_sampled.csv` but `PVMAPGenerationAgent` only checked `current_dataset.combined_sampled_data` (set by DiscoveryAgent before sampling ran). The DatasetInfo object was never updated, so the prompt builder always failed with "No sampled data available."

## Solution Overview

### Enriched 9-Section Skeleton Format

The `DataContext.to_skeleton_summary()` method was rewritten to produce a 9-section markdown format designed to prevent the top PVMAP validation errors:

| Section | Content | Prevents |
|---------|---------|----------|
| 1. Topology & Structure | Format, row/col count, **ALL column headers** (exact, case-sensitive) | `error-pvmap-dropped-undefined-property` (key mismatch) |
| 2. Column Classifications | Table: column → role (place/time/dimension/value/metadata) + ignored columns list | Over-dimensioning (metadata forced into StatVar) |
| 3. Anchor Analysis | Geo: column, format, sample values → **suggested DCID** (e.g. `06 → geoId/06`). Time: column, format, samples | `error-unresolved-place` (#1 validation error) |
| 4. Dimension Deep Dive | Per dimension: **up to 15 values**, **aggregate flags** ("Total" → drop constraint) | Incomplete dimension enumeration, wrong "Total" handling |
| 5. Measurement & Units | Value columns with data type, stat type, unit | `error-aggregate-invalid-values`, missing units |
| 6. StatVar Pattern | P+M+C formula, populationType, measuredProperty, statType | `error-statvar-missing-property` |
| 7. One-Shot PVMAP Example | Mini 3-5 row PVMAP generated from classified columns | Syntax hallucination, missing `observationAbout` |
| 8. Pre-Formatted DC Detection | Boolean flag + passthrough hint if `variableMeasured` column exists | Missed passthrough opportunity |
| 9. Coverage | Total dimension combinations + generate-all reminder | Incomplete PVMAPs |

### Prompt Template Integration

The `{{DATA_CONTEXT}}` placeholder was added to `improved_pvmap_prompt.txt` between "COMMON MISTAKES TO AVOID" and "SCHEMA EXAMPLES":

```
# COMMON MISTAKES TO AVOID
...

---

# DATA UNDERSTANDING (from automated analysis)

{{DATA_CONTEXT}}

---

# SCHEMA EXAMPLES
...
```

**Placement rationale:** After rules/mistakes are absorbed, before schema examples. The one-shot example in DATA_CONTEXT is immediately followed by full schema examples = "specific hint → general reference" flow.

### Pipeline Data Flow Fixes

Three agents were updated to fix the broken sampled-data and metadata resolution paths:

1. **PVMAPGenerationAgent** — Sampled data resolved via fallback chain instead of single source
2. **PVMAPRetryLoop** — Same fallback chain applied
3. **SamplingAgentWrapper** — Now sets `sampled_data_path` in session state from output dir fallback

## Detailed Changes

### 1. DataContext Dataclass (`src/pipeline/sampling/data_context.py`)

**New fields added to `DataContext`:**

```python
# === ENRICHED FIELDS (for improved PVMAP generation) ===
all_columns: List[str]                          # Every column header (exact, case-sensitive)
ignored_columns: List[str]                      # Metadata/constant columns to NOT map
aggregate_values: Dict[str, List[str]]          # {dimension: [aggregate_values]} e.g. {"Gender": ["Total"]}
place_resolution_hints: List[Dict[str, str]]    # [{raw_value, suggested_dcid}]
is_preformatted_dc: bool                        # True if data has variableMeasured+observationAbout+value
one_shot_example: str                           # Mini PVMAP CSV for the LLM
```

**New helper methods on `DataContextGenerator`:**

| Method | Purpose |
|--------|---------|
| `_detect_aggregate_values(df, dimension_columns)` | Scans each dimension for values matching `total_keywords` (`Total`, `All`, `Overall`, etc.) |
| `_generate_place_resolution_hints(geo_info, df)` | Maps detected geo format to DCID prefix using `GEO_FORMAT_DCID_MAP` static lookup |
| `_generate_one_shot_example(context, df)` | Deterministic mini PVMAP from classified columns (place → DCID, time → observationDate, dimensions → enumerated values, value → StatVar line) |
| `_detect_preformatted_dc(df)` | Checks if columns include `variableMeasured` + `observationAbout` + `value` |

**Geo format → DCID mapping table:**

| Geo Format | DCID Pattern | Example |
|------------|-------------|---------|
| `FIPS_STATE` | `geoId/{val:02d}` | `06` → `geoId/06` |
| `FIPS_COUNTY` | `geoId/{val:05d}` | `06037` → `geoId/06037` |
| `ISO_2` / `ISO_3` | `country/{val}` | `US` → `country/US` |
| `DC_DCID` | `{val}` (passthrough) | `geoId/06` → `geoId/06` |
| `NAME` | `wikidataId/{val}` | `California` → `wikidataId/California` |
| `ZIP` | `zip/{val}` | `90210` → `zip/90210` |

### 2. Prompt Template (`src/resources/prompts/improved_pvmap_prompt.txt`)

Added `{{DATA_CONTEXT}}` placeholder at line 422-424. No changes needed in `helpers.py` — line 79 already did `template.replace("{{DATA_CONTEXT}}", data_context)`.

### 3. Manual Context Fallback (`src/tools/sampling_tools.py`)

Updated `_generate_context_manual()` to produce the enriched 9-section format with graceful degradation:
- Includes column headers listing (Section 1)
- Includes classification table (Section 2) from `column_roles`
- Includes ignored columns (Section 2)
- Skips one-shot example and aggregate detection
- Appends note: `_Simplified analysis. Full context generation not available._`

Also updated the LLM-override logic in `generate_context()` to rebuild `ignored_columns` and `aggregate_values` when LLM classifications override heuristic results.

### 4. State Key Consolidation (`src/agents/sampling_agent.py`)

Documented the 4 overlapping state keys with clear priority:

1. **`skeleton_summary`** (str) — PRIMARY output. Enriched 9-section markdown injected into PVMAP prompt via `{{DATA_CONTEXT}}`
2. **`data_context`** (dict) — SECONDARY output. Full structured dict for programmatic access (evaluation, MCP queries, debugging)
3. **`column_roles`** (dict) — DERIVED convenience key (backward compat)
4. **`dimension_columns`** (list) — DERIVED convenience key (backward compat)

### 5. Sampled Data Path Resolution (`src/agents/pvmap_generation_agent.py`)

**Before:** Single source — `current_dataset.combined_sampled_data` (set by DiscoveryAgent, never updated after sampling)

**After:** Three-tier fallback:

```python
# 1. current_dataset.combined_sampled_data (set by DiscoveryAgent)
# 2. session state sampled_data_path (set by SamplingAgentWrapper)
# 3. output_dir/agentic_sampled.csv (written by sampling agent)
```

Same fix applied in `src/agents/pvmap_retry_loop.py`.

### 6. Metadata Resolution for Validation (`src/agents/pvmap_generation_agent.py`)

**Before:** `str(current_dataset.combined_metadata)` — passed `"None"` string when metadata wasn't loaded, causing `stat_var_processor` to fail with "Metadata file not found: None"

**After:** Two-tier resolution matching `ValidationAgent`'s pattern:

```python
# 1. ground_truth/{dataset}/metadata/*.csv (from ground_truth_metadata dir)
# 2. current_dataset.combined_metadata (from input_metadata/)
# 3. None (omit --config_file, validation proceeds without metadata)
```

### 7. SamplingAgent State Update (`src/agents/sampling_agent.py`)

`_populate_state_from_context()` now always sets `sampled_data_path` in session state by falling back to `output_dir/agentic_sampled.csv` when the data_context dict doesn't contain a `sampled_file` key.

### 8. Downstream Consumers

- **`src/agents/schema_selection_agent.py`** — Added `{skeleton_summary}` reference in instruction with guidance to prefer it over raw `data_context` dict
- **`src/agents/evaluation_agent.py`** — Added `aggregate_values_detected` to eval metrics when aggregate values present in data_context

## Example Output

For the `brfss_nchs_asthma_prevalence` dataset, the enriched skeleton in the prompt looks like:

```markdown
## 1. TOPOLOGY & STRUCTURE

- **Dataset:** output
- **Format:** PIVOTED_WIDE
- **Rows:** 10  |  **Columns:** 11

**ALL column headers (exact, case-sensitive):** `State`, `Income`, `Sample Sizec`,
`Prevalence (Percent)`, `Standard Error`, `95% CId (Percent)`, `|| ||`,
`Weighted Numbere`, `95% CId (Weighted Number)`, `year`, `life_stage`

## 2. COLUMN CLASSIFICATIONS

| Column | Role |
|--------|------|
| `State` | place |
| `year` | time |
| `Income` | dimension |
| `life_stage` | dimension |
| `Prevalence (Percent)` | value |
| `Sample Sizec` | value |
| `Standard Error` | value |
| `Weighted Numbere` | value |
| `95% CId (Percent)` | metadata |
| `95% CId (Weighted Number)` | metadata |
| `|| ||` | metadata |

**Ignored columns** (metadata/constant — do NOT map): `95% CId (Percent)`,
`95% CId (Weighted Number)`, `|| ||`

## 3. ANCHOR ANALYSIS

**Geography:** Column `State` — Format: NAME
  Sample values: U.S. Totalf, AL
  **Place → DCID resolution hints:**
  - `U.S. Totalf` → `wikidataId/U.S. Totalf`
  - `AL` → `wikidataId/AL`

**Time:** Not detected

## 4. DIMENSION DEEP DIVE

- **`Income`** (5 values): [$15,000–<$25,000, $25,000–<$50,000, ...]
- **`life_stage`** (1 values): [adult]

## 5. MEASUREMENT & UNITS

- Value Column: `Sample Sizec` (StatType: measuredValue)
- Value Column: `Prevalence (Percent)` (StatType: Percent)
- ...

## 6. STATVAR PATTERN (P+M+C Formula)

`Count_Person_{Income}`

## 7. ONE-SHOT PVMAP EXAMPLE

​```csv
key,property,value
State,observationAbout,wikidataId/{Data}
Income:$15,000–<$25,000,income,$15,000–<$25,000
Income:$25,000–<$50,000,income,$25,000–<$50,000
...
Sample Sizec,value,{Number},populationType,Person,measuredProperty,count,statType,measuredValue
​```

## 8. PRE-FORMATTED DATA COMMONS DETECTION

Not pre-formatted. Generate PVMAP from scratch.

## 9. COVERAGE

- Total Dimension Combinations: 5

**IMPORTANT:** Generate PVMAP for ALL dimension combinations, not just those in sample.
```

## Tests Added

24 new tests across 3 files (438 total, all passing):

### `tests/pipeline/sampling/test_data_context.py` (20 tests)

| Test | Validates |
|------|-----------|
| `test_enriched_skeleton_has_all_columns` | Section 1 lists ALL column headers |
| `test_enriched_skeleton_has_ignored_columns` | Metadata columns listed under ignored |
| `test_enriched_skeleton_aggregate_detection` | "Total" flagged in dimension columns |
| `test_enriched_skeleton_place_resolution` | FIPS → `geoId/` hints generated |
| `test_enriched_skeleton_one_shot_example` | Mini PVMAP contains `observationDate`, `value` |
| `test_enriched_skeleton_preformatted_detection` | DC-formatted CSV sets `is_preformatted_dc=True` |
| `test_enriched_skeleton_not_preformatted` | Regular CSV returns `False` |
| `test_enriched_skeleton_dimension_values_expanded` | Up to 15 values shown |
| `test_enriched_skeleton_all_nine_sections` | All 9 section headers present |
| `test_enriched_skeleton_coverage_reminder` | Generate-all reminder present |
| `test_detect_aggregate_values_basic` | Finds "Total" keyword |
| `test_detect_aggregate_values_no_aggregates` | Returns empty when none |
| `test_detect_preformatted_dc_positive` | Detects DC format |
| `test_detect_preformatted_dc_negative` | Returns False for regular data |
| `test_generate_place_resolution_hints_fips` | FIPS → geoId mapping |
| `test_generate_place_resolution_hints_empty_geo` | Empty for no geo |
| `test_generate_one_shot_example` | Valid mini PVMAP produced |
| `test_generate_one_shot_example_with_dimensions` | Dimension values enumerated |
| `test_metadata_dict_includes_new_fields` | `to_metadata_dict()` includes enriched fields |
| `test_generate_data_context_convenience` | Convenience function returns enriched context |

### `tests/agents/test_pvmap_helpers.py` (2 tests)

| Test | Validates |
|------|-----------|
| `test_build_prompt_data_context_placeholder` | `{{DATA_CONTEXT}}` replaced in template |
| `test_build_prompt_data_context_default` | Default fallback when data_context is None |

### `tests/tools/test_sampling_tools.py` (3 tests)

| Test | Validates |
|------|-----------|
| `test_generate_context_enriched_columns` | Enriched context has all columns |
| `test_generate_context_enriched_preformatted` | Detects DC format |
| `test_generate_context_enriched_ignored_columns` | Metadata as ignored |

## Pipeline Verification

Tested on `brfss_nchs_asthma_prevalence`:

| Metric | Before | After |
|--------|--------|-------|
| Generation | Failed after 3 attempts ("No sampled data available") | Succeeded on attempt 1 |
| Validation | Failed ("Metadata file not found: None") | Passed |
| Prompt contains skeleton | No (placeholder missing) | Yes (all 9 sections) |
| Evaluation | N/A | 21.1% node accuracy, 23.3% PV accuracy |

## Files Modified

| File | Change |
|------|--------|
| `src/pipeline/sampling/data_context.py` | 6 new fields, rewritten `to_skeleton_summary()`, 4 new helper methods, `GEO_FORMAT_DCID_MAP` |
| `src/resources/prompts/improved_pvmap_prompt.txt` | Added `{{DATA_CONTEXT}}` placeholder |
| `src/tools/sampling_tools.py` | Updated manual fallback + LLM-override for enriched fields |
| `src/agents/sampling_agent.py` | State key consolidation docs, `sampled_data_path` fallback |
| `src/agents/pvmap_generation_agent.py` | Sampled data 3-tier fallback, metadata resolution from ground_truth |
| `src/agents/pvmap_retry_loop.py` | Sampled data 3-tier fallback |
| `src/agents/schema_selection_agent.py` | Reference `{skeleton_summary}` in instruction |
| `src/agents/evaluation_agent.py` | `aggregate_values_detected` in eval metrics |
| `tests/pipeline/sampling/test_data_context.py` | 20 new tests |
| `tests/agents/test_pvmap_helpers.py` | 2 new tests |
| `tests/tools/test_sampling_tools.py` | 3 new tests |
