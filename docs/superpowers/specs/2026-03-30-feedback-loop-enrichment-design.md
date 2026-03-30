# Feedback Loop Enrichment: Merging log_filter + counter_feedback

**Date:** 2026-03-30
**Branch:** `feature/nehil/feedback_integration`
**Status:** Design approved, pending implementation

---

## Problem

The LLM retry loop receives feedback from `log_filter.py` after each validation attempt. While `log_filter.py` produces structured markdown with coverage metrics, error counts, and value pattern analysis, it **loses critical diagnostic signals** that the processor already emits:

1. **Specific failing values** — The processor emits debug counters like `error-unresolved-place_geoId/6`, but `log_filter.py` only reads the base counter (`error-unresolved-place: 42`). The LLM sees "42 place failures" but not that they're all caused by missing leading zeros.

2. **No error prioritization** — Errors are sorted by count, not by impact. A key mismatch error (which blocks ALL output) may appear below a spelling warning.

3. **No fix recipes** — The LLM must infer fixes from raw error names. `counter_feedback.py` has an `ERROR_PATTERNS` dict mapping each error type to common causes and fix patterns, but this code is deprecated and not in the active path.

4. **No systematic pattern detection** — When all 42 place failures share the same root cause (missing leading zero), the feedback should say so explicitly rather than listing individual values.

5. **No iteration-aware guidance** — Attempt 1 should focus on structural fixes; attempt 3 should preserve working rows. Currently all attempts get identical feedback structure.

Meanwhile, `counter_feedback.py` (970 lines) already solves problems 2-5 but was deprecated in favor of `log_filter.py`'s leaner approach. The solution is to merge the best of both.

---

## Approach: Merge Best of Both Worlds

Enrich `log_filter.py` with `counter_feedback.py`'s strongest features. Single code path, no new modules.

**Rejected alternatives:**
- **New feedback_synthesizer.py layer** — Premature abstraction. log_filter.py is the right place for this logic.
- **Processor-side JSON output** — Too risky to change the 3000-line subprocess. Debug counters already provide the signal we need.

---

## Reference: stat_var_processor Processing Pipeline

```
Input CSV + PVMAP CSV + (optional) Metadata CSV
    │
    ▼
Phase 0: LOAD PV MAP
  - Parse PVMAP CSV into key→property map
  - 5-level fuzzy key matching: exact → case-insensitive → alphanumeric → n-gram → substring
  - Counters: load_pv_map_*
    │
    ▼
Phase 1: PROCESS INPUT (per row)
  - Match row values to PVMAP keys
  - Resolve {Data}, {Number} placeholder templates
  - Generate StatVar DCID from properties
  - Resolve place values → DC DCIDs
  - Parse date formats
  - Counters: process_stat_vars_*, resolve_svobs_*
    │
    ▼
Phase 2: PREPARE OUTPUT
  - Deduplicate StatVars
  - Aggregate observations
  - Drop invalid/incomplete rows
  - Counters: prepare_output_*
    │
    ▼
Phase 3-4: WRITE OUTPUT
  - processed.csv (StatVarObservations)
  - processed_stat_vars.mcf (StatVar definitions)
  - processed.tmcf (Template MCF)
  - processed_counters.txt (diagnostic counters — CSV format)
```

**Feedback loop uses:** `processed_counters.txt` (parsed by log_filter.py) and `processed_stat_vars.mcf` (parsed by validation_tool.py's `_extract_statvar_summary`).

---

## Reference: Counter Inventory

### Tier 1: High-Signal Counters (directly actionable)

| Counter Key | Suffixed Variant | What It Tells the LLM | Current Status |
|---|---|---|---|
| `error-pvmap-dropped-undefined-property` | `_<key_name>` | Exact PVMAP keys that don't match any column header | Base count only (suffixes lost) |
| `warning-missing-property-key` | `_<unmapped_value>` | Input values that failed all 5 match levels | Captured + pattern classified |
| `error-unresolved-place` | `_<place_value>` | Specific place values that couldn't resolve to DCID | Base count only (suffixes lost) |
| `dropped-svobs-unresolved-place` | `_<StatVar_name>` | Which StatVars lost observations due to place failures | Captured |
| `warning-svobs-missing-place` | `_<StatVar_name>` | StatVars with NO observationAbout mapping | Captured |
| `error-mismatched-svobs` | `_<StatVar_name>` | Duplicate observations for same StatVar+Place+Date | Base count only (suffixes lost) |
| `warning-unresolved-value-ref` | `_<ref_name>` | Failed `{Data}` or `{Number}` template resolution | Captured |
| `error-aggregate-invalid-values` | `_<column>` | Non-numeric values in `{Number}` positions | Not extracted |
| `error-duplicate-statvars` | `_<StatVar_name>` | StatVar DCID collisions (different combos, same DCID) | Not extracted |
| `dropped-svobs-unresolved-date` | `_<date_value>` | Date values that couldn't parse | Not extracted |

### Tier 2: Diagnostic Counters (scope/shape)

| Counter Key | What It Tells the LLM | Current Status |
|---|---|---|
| `input-rows-processed` | Total input rows | Captured |
| `output-svobs-csv-rows` | Output observation rows | Captured |
| `generated-unique-statvars` | Unique StatVars created | Captured |
| `output-svobs-unique-<property>` | Cardinality per output property | Captured |
| `svobs-added_dcid:<StatVar>` | Per-StatVar observation count | Captured |
| `dropped-statvars-without-svobs_<SV>` | StatVars with 0 observations | Captured |
| Fragmentation ratio (computed) | unique_statvars / observations | Captured |

### Key Insight

The processor already emits suffixed debug counters with specific failing values. `counter_feedback.py` has `extract_debug_examples()` that mines these. But `log_filter.py` (the active code path) only reads base counter keys — this is the single biggest feedback gap.

---

## Design: 4 Enhancements to log_filter.py

### Enhancement A: Debug Example Extraction (highest impact)

**New FilteredLogs fields:**

```python
# Maps error type → [(failing_value, count), ...] top 5 per error type
error_examples: Dict[str, List[Tuple[str, int]]] = field(default_factory=dict)

# Specific PVMAP keys that didn't match any column
key_mismatch_examples: List[Tuple[str, int]] = field(default_factory=list)

# StatVars with duplicate observations
duplicate_statvar_examples: List[Tuple[str, int]] = field(default_factory=list)

# Date values that couldn't parse
unresolved_date_examples: List[Tuple[str, int]] = field(default_factory=list)
```

**Extraction logic (ported from counter_feedback.py `extract_debug_examples()`):**

For each Tier 1 error counter key, scan all counters for `{error_key}_{suffix}` variants. Collect `(suffix, count)` tuples, sort by count descending, keep top 5.

**Impact on to_summary():**

Before:
```markdown
## Errors (must fix)
- error-unresolved-place: 42
```

After:
```markdown
## Errors (must fix)

### error-unresolved-place: 42
**Failing values:** geoId/6 (x42), Alabama (x18), New York City (x5)
```

### Enhancement B: Error Priority Ordering

**Port from counter_feedback.py:**

```python
ERROR_PRIORITY = [
    'error-pvmap-dropped-undefined-property',   # 1. Structural — blocks everything
    'error-unresolved-place',                   # 2. Place resolution — unlocks many rows
    'error-statvar-missing-property',           # 3. StatVar completeness
    'error-svobs-missing-property',             # 4. Observation completeness
    'error-mismatched-svobs',                   # 5. Duplicates — need qualifiers
    'error-duplicate-statvars',                 # 6. DCID collisions
    'error-aggregate-invalid-values',           # 7. Value aggregation
    'error-invalid-multiply-factor',            # 8. Multiplication factors
]
```

`to_summary()` sorts errors by this priority order instead of raw count. Errors not in the list sort after all prioritized errors, by count descending.

### Enhancement C: Fix Recipe Injection

**Port `ERROR_PATTERNS` dict from counter_feedback.py** (trimmed to essentials):

```python
ERROR_PATTERNS = {
    'error-pvmap-dropped-undefined-property': {
        'category': 'PVMAP Key Mismatch',
        'common_causes': [
            'Case mismatch (State FIPS vs state_fips)',
            'Typo or hallucinated key name',
            'Column renamed or missing from input',
        ],
        'fix': 'Match keys EXACTLY to column headers (case-sensitive)',
    },
    'error-unresolved-place': {
        'category': 'Place Resolution',
        'common_causes': [
            'FIPS codes missing leading zeros (6 → 06)',
            'Missing geoId/ prefix in observationAbout',
            'Ambiguous place names without containedInPlace',
        ],
        'fix': 'Use geoId/{val:0>2} for states, geoId/{val:0>5} for counties',
    },
    'error-mismatched-svobs': {
        'category': 'Duplicate Observations',
        'common_causes': [
            'Missing dimension qualifier (gender, age, race)',
            'Multiple data columns mapped to same StatVar',
        ],
        'fix': 'Add qualifier properties to differentiate observations',
    },
    'error-aggregate-invalid-values': {
        'category': 'Invalid Aggregation',
        'common_causes': [
            'Non-numeric values in [NUMBER] column',
            'Text values like "N/A", "-", "suppressed"',
        ],
        'fix': 'Add #Filter to exclude non-numeric rows, or use [DATA] instead of [NUMBER]',
    },
    # ... additional patterns for remaining error types
}
```

**Impact on to_summary():**

```markdown
### error-unresolved-place: 42
**Category:** Place Resolution
**Failing values:** geoId/6 (x42), Alabama (x18)
**Common causes:**
- FIPS codes missing leading zeros (6 → 06)
- Missing geoId/ prefix in observationAbout
**Fix:** Use geoId/{val:0>2} for states, geoId/{val:0>5} for counties
```

### Enhancement D: Systematic Pattern Detection

**Port `detect_systematic_patterns()` from counter_feedback.py.**

After extracting debug examples, detect patterns across failing values:

1. **Single-value pattern** — All errors share the same value. Confidence: 1.0.
   Example: "All 42 place failures are on value 'geoId/6' — likely missing leading zero"

2. **Few-values pattern** — <20% unique values cause all errors. Confidence: 0.8.
   Example: "Only 3 unique place values cause all 60 failures"

3. **Format pattern** — Common formatting issues detected across values:
   - Missing leading zeros: >50% of values are single digits (for FIPS)
   - Missing `dcid:` prefix: >50% look like DCIDs without prefix
   - Missing `geoId/` prefix: >50% are bare FIPS numbers

**New section in to_summary():**

```markdown
## Systematic Patterns Detected

### PATTERN: Missing leading zeros in place values (confidence: 0.9)
**Error:** error-unresolved-place (42 occurrences)
**Evidence:** 38/42 failing values are single digits (6, 1, 9, 4, ...)
**Fix:** Change observationAbout format to geoId/{val:0>2} for zero-padding
```

### Enhancement E: Iteration-Aware Hints

**New parameter:** `filter_counters(counters_path, attempt_number=0)`

**Iteration advice appended to summary footer:**

```python
ITERATION_ADVICE = {
    0: "ATTEMPT 1: Focus on structural fixes — key matching, required properties (observationAbout, observationDate, value), correct archetype.",
    1: "ATTEMPT 2: Structure should be sound. Focus on value-level fixes — place resolution format, placeholder templates, enum values.",
    2: "ATTEMPT 3 (FINAL): Preserve all working rows. Only fix the highest-impact remaining error. Do not restructure.",
}
```

---

## Changes by File

| File | Change | Risk | Lines |
|---|---|---|---|
| `src/pipeline/validation/log_filter.py` | Add debug extraction, priority ordering, fix recipes, pattern detection, iteration hints | Medium | +300 |
| `src/tools/validation_tool.py` | Pass `attempt_number` to `filter_counters()` | Low | +5 |
| `src/resources/prompts/feedback_agent_v2.txt` | New sections: use "Failing values" for targeted fixes, follow error priority, check "Systematic Patterns", iteration-aware strategy | Low | +30 |
| `src/agents/pvmap_retry_loop.py` | Pass `attempt_number` through validation call chain | Low | +10 |
| `src/agents/validation_agent.py` | Accept and forward `attempt_number` | Low | +5 |
| `src/pipeline/validation/counter_feedback.py` | Add deprecation notice at module top | None | +3 |

**No changes to:**
- `stat_var_processor.py` (processor unchanged)
- `feedback_agent.py` (Python code unchanged)
- `pvmap_repair.py` (pre-validation unchanged)
- Pipeline architecture (same flow)

---

## Example: Before vs After Feedback

### Before (current log_filter.py output)

```markdown
## Validation Summary
- Input rows: 500
- Output rows: 0
- Coverage: 0.0%
- STATUS: CRITICAL FAILURE

## Errors (must fix)
- error-pvmap-dropped-undefined-property: 5
- error-unresolved-place: 42

## Top Unmatched Input Values
- 'AL': 15 occurrences (state_code pattern)
- 'CA': 12 occurrences (state_code pattern)
```

### After (enriched output)

```markdown
## Validation Summary
- Input rows: 500
- Output rows: 0
- Coverage: 0.0%
- STATUS: CRITICAL FAILURE

## Errors (must fix — ordered by impact)

### 1. error-pvmap-dropped-undefined-property: 5 [PVMAP Key Mismatch]
**Failing keys:** State FIPS (x300), Year Code (x150), Age Group (x50)
**Common causes:**
- Case mismatch (State FIPS vs state_fips)
- Typo or hallucinated key name
**Fix:** Match keys EXACTLY to column headers (case-sensitive)

### 2. error-unresolved-place: 42 [Place Resolution]
**Failing values:** geoId/6 (x15), geoId/1 (x12), geoId/9 (x8), geoId/4 (x7)
**Common causes:**
- FIPS codes missing leading zeros (6 → 06)
**Fix:** Use geoId/{val:0>2} for states, geoId/{val:0>5} for counties

## Systematic Patterns Detected

### PATTERN: Missing leading zeros in place values (confidence: 0.9)
**Error:** error-unresolved-place (42 occurrences)
**Evidence:** 38/42 failing values are single-digit FIPS codes
**Fix:** Change observationAbout format to geoId/{val:0>2}

## Iteration Guidance
ATTEMPT 1: Focus on structural fixes — key matching, required properties, correct archetype.

## Top Unmatched Input Values
- 'AL': 15 occurrences (state_code pattern)
- 'CA': 12 occurrences (state_code pattern)
```

---

## Testing Strategy

1. **Unit tests for new FilteredLogs fields** — Mock counters files with known debug suffixes, verify extraction
2. **Unit tests for pattern detection** — Test single-value, few-values, and format patterns
3. **Unit tests for priority ordering** — Verify errors sort by ERROR_PRIORITY
4. **Integration test** — Run on a real dataset counters file (e.g., BIS or BRFSS), verify enriched summary
5. **Regression** — Existing log_filter tests must still pass (base metrics unchanged)

Estimated: ~25-30 new tests.

---

## Success Criteria

1. Feedback agent receives specific failing values for all Tier 1 error types
2. Errors sorted by impact priority, not raw count
3. Fix recipes appear inline with each error type
4. Systematic patterns detected and surfaced when present
5. Iteration-specific guidance varies across retry attempts
6. All existing tests pass, no processor changes required
