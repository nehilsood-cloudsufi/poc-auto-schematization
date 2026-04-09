# Metadata Agent Improvements Design

**Date:** 2026-04-09
**Status:** Draft
**Scope:** Improve accuracy of auto-generated `output_metadata.csv` (P1 flags only)

## Problem Statement

The `MetadataGenerationAgent` produces `output_metadata.csv` with incorrect semantics for key flags. Feedback from 3 reviewers identified:

1. **`mapped_rows` / `mapped_columns` inaccuracy** — agent counts PVMAP structure instead of input data structure
2. **Unnecessary/unused flags** — `generate_statvar_name` (0% in GT), `drop_statvars_without_svobs`, `multi_value_properties` add noise
3. **`output_columns` not standardized** — required columns can be dropped if PVMAP is malformed

### Root Cause

The agent computes PVMAP-centric metrics and writes them as input-data-centric config parameters:

| Flag | What agent generates | What processor expects |
|---|---|---|
| `mapped_rows` | Count of PVMAP rows (e.g., 41) | Number of input rows for PV lookups (e.g., 1) |
| `mapped_columns` | Max PV pairs per PVMAP row (e.g., 8) | Number of leading input dimension columns (e.g., 9) |

This causes silent data truncation or incorrect PV lookup behavior in `stat_var_processor.py`.

## Approach: Hybrid (Deterministic Core + LLM Refinement)

Three flags are fixed deterministically. `mapped_columns` uses deterministic analysis with LLM fallback for ambiguous cases.

## P1 Flags — Detailed Design

### 1. `output_columns` — Deterministic Fix

**File:** `src/tools/metadata_tools.py` (`extract_output_columns()`)

**Current:** Scans PVMAP for `VALID_SVOBS_PROPERTIES`, returns only those found.

**New logic:**
```
REQUIRED_COLUMNS = ["observationAbout", "observationDate", "variableMeasured", "value"]
OPTIONAL_COLUMNS = ["unit", "scalingFactor", "measurementMethod", "observationPeriod"]

output = REQUIRED_COLUMNS (always)
      + [col for col in OPTIONAL_COLUMNS if col found in PVMAP properties]
```

**Rationale:** Ground truth analysis shows the 4 required columns appear in 100% of 51 GT metadata files. Optional columns vary: unit (76%), scalingFactor (51%), measurementMethod (35%), observationPeriod (39%).

### 2. `header_rows` — Strengthened Detection

**File:** `src/tools/metadata_tools.py` (`detect_header_rows()`)

**Current:** Checks `data_context`, then scans input for leading text-only rows.

**New logic (adds PVMAP cross-reference):**
```
1. If data_context has header_rows → use it (trusted source)
2. Else:
   a. text_scan: Count leading text-only rows in input (existing logic)
   b. pvmap_cross_ref: Check which input rows have values matching PVMAP keys
      - If row 1 column names match PVMAP keys → confirms 1 header row
      - If row 2 values also match PVMAP keys → suggests 2-row header
   c. result = max(text_scan, pvmap_cross_ref)
3. Minimum: 1
```

**New signature:** `detect_header_rows(input_file, data_context, pvmap_csv_content)` — adds optional pvmap parameter.

### 3. `mapped_rows` — Semantic Fix

**File:** `src/tools/metadata_tools.py` (`count_mapped_rows()` replaced)

**Current:** Counts non-header rows in PVMAP CSV. Wrong semantics.

**New logic:**
```python
def compute_mapped_rows(header_rows: int) -> int:
    return header_rows
```

**Rationale:** In `stat_var_processor.py:2045-2048`, `mapped_rows` controls which input rows get row-based PV lookups. Ground truth confirms `mapped_rows` equals `header_rows` wherever both are set. The processor's fallback (line 2065) handles the "not set" case correctly.

### 4. `mapped_columns` — Hybrid (Deterministic + LLM)

**File:** `src/tools/metadata_tools.py` (new `compute_mapped_columns()`)

**Current:** Counts max PV pairs per PVMAP row. Wrong semantics.

**New deterministic logic:**
```
Input: pvmap_csv_content, input_headers (list of column names)

Step 1 — Parse PVMAP keys into two sets:
  - direct_keys: plain string keys (e.g., "year", "NIPR")
  - column_value_columns: column names extracted from COLUMN:VALUE keys 
    (e.g., "agecat" from "agecat:0", "agecat:1")

Step 2 — Classify each input column:
  - "dimension": column name appears in column_value_columns
    (cell values are PVMAP keys — needs PV lookup on data rows)
  - "value": column name appears ONLY in direct_keys
    (header is the PVMAP key — processor handles via header-match at line 2062)
  - "unmapped": not referenced in PVMAP

Step 3 — Find rightmost dimension column position (1-based index)
  → that's the candidate mapped_columns value

Step 4 — Confidence scoring:
  - HIGH confidence when:
    - All dimension columns are contiguous from column 1
    - Clear separation from value/unmapped columns
    - At least 1 column_value_key found
  - LOW confidence when:
    - Dimension columns are scattered (non-contiguous)
    - A column appears in BOTH direct_keys AND column_value_columns
    - No column_value_keys found at all (all keys are direct)
    - Zero dimension columns detected

Return: (mapped_columns: int, confidence: str)
```

**LLM refinement (only when confidence is LOW):**

Rewrite `metadata_enrichment.txt` prompt to focus on column classification:

```
Given input CSV columns: {input_headers}
And PVMAP key patterns (grouped by type):
  Direct keys: {direct_keys_list}
  Column:Value keys: {column_value_keys_list}
First 3 input data rows: {sample_rows}

Classify each column as:
- DIMENSION: cell values appear as PVMAP keys (e.g., "agecat" with keys "agecat:0", "agecat:1")
- VALUE: column header itself is a PVMAP key (e.g., "NIPR" maps to observationAbout)
- UNMAPPED: not referenced in PVMAP

Return JSON: {"mapped_columns": N, "reasoning": "..."}
where N = position (1-based) of the rightmost dimension column.
```

**Fallback:** If LLM also fails → use `0` (processor falls back to "allow all lookups" per line 2065).

**Integration in `MetadataGenerationAgent`:**
- LLM enrichment scope changes from "schemaless/description/drop_statvars" to "mapped_columns refinement"
- Still only runs on first attempt (attempt_number == 0)
- Only triggered when deterministic confidence is LOW

## Flags Removed from Auto-Generation

| Flag | Reason |
|---|---|
| `generate_statvar_name` | 0% in ground truth, unnecessary noise |
| `drop_statvars_without_svobs` | Only 19% in GT, processor has sensible default |
| `multi_value_properties` | Only 8% in GT, not P1 |

These are still respected if present in user-provided or GT metadata (merge priority unchanged).

## Output Format

Still 2-column CSV. Example output:
```csv
output_columns,"observationAbout,observationDate,variableMeasured,value,unit,scalingFactor"
header_rows,1
mapped_rows,1
mapped_columns,9
```

## What Does NOT Change

- **Pipeline position:** MetadataGenerationAgent runs after PVMAP generation, before validation
- **3-tier merge priority:** GT metadata > user metadata > auto-generated
- **Agent type:** BaseAgent wrapping optional LlmAgent
- **Non-fatal failures:** Validation proceeds without config if generation fails
- **Output file path:** `{output_dir}/output_metadata.csv`
- **Retry loop integration:** Config regenerated each attempt (PVMAP changes)

## Testing Strategy

### Unit Tests (`tests/tools/test_metadata_tools.py`)

**output_columns:**
- Required 4 always present even with empty/broken PVMAP
- Optional columns added only when found in PVMAP
- Ordering matches canonical order

**header_rows:**
- PVMAP cross-reference confirms single-row header
- PVMAP cross-reference detects multi-row header
- Falls back to text-scan when no PVMAP provided

**mapped_rows:**
- Always equals header_rows input

**mapped_columns:**
- SAHIE: detects 9 dimension columns (agecat, racecat, etc. from COLUMN:VALUE keys)
- BRFSS: detects 2 dimension columns (State, Income)
- BIS: detects correct value from direct key patterns
- India NFHS: handles complex multi-dimension dataset
- Confidence HIGH for contiguous dimensions, LOW for scattered/ambiguous

### Integration Validation

Compare new auto-generated metadata against all 52 ground truth datasets:
- Run `generate_processor_config()` with GT PVMAP + input data
- Compare each flag value against GT metadata
- Report match rate per flag (target: >80% match)

### Regression

- Existing `tests/agents/test_metadata_generation_agent.py` tests updated for new output shape
- Full test suite must pass
