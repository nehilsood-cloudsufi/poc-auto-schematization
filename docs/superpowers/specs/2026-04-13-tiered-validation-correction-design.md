# Tiered Validation Correction Design

**Date**: 2026-04-13
**Status**: Draft
**Scope**: Redesign of the post-PVMAP-generation validation and correction flow

## Problem Statement

The current validation-feedback-regeneration loop has a **46.2% pass rate** across 60 datasets (104 attempts). 20 of 42 datasets that ran never pass at all. Only 4 achieve clean success.

**Root causes identified**:
1. **KEY_MISMATCH dominates** — 26/42 datasets (72% of failures). LLM generates PVMAP keys that don't match CSV column headers.
2. **Feedback not landing** — The LLM feedback agent produces text advice, but the generator ignores it 50%+ of the time (e.g., BRFSS fails 4x on the same `{Number}` template issue).
3. **No enforcement** — Deterministic errors (key mismatch, place format, placeholder syntax) are treated as semantic problems requiring LLM reasoning. They don't.
4. **Regeneration destroys progress** — The loop always re-generates the entire PVMAP, which can regress rows that were already correct.

**Gemini DC expert consultation** confirmed: "Stop asking the Generator LLM to fix its own mistakes via text prompts. Surgical editing should be done via programmatic patch application."

## Design: Tiered Correction Architecture

### New Loop Flow

**Current** (every iteration regenerates):
```
StatePrep → Generator → MetadataGen → Validate → QualityEval → FeedbackAgent(text) → [loop]
```

**New** (patch in place for Tier 1, regenerate only for Tier 2 semantic failures):
```
Iteration 0 (always generate fresh):
  StatePrep → Generator → MetadataGen → Validate → QualityEval

If validation failed or quality low:
  → TieredCorrectionAgent:
      Tier 1: Deterministic patches (no LLM)
        → Fast re-validate (pre_validate_pvmap, milliseconds)
        → If pre-validation passes → Full re-validate (subprocess)
        → If passes → QualityEval → done
      Tier 2: Semantic LLM patches (JSON structured output)
        → Apply patches programmatically
        → Full re-validate
        → If passes → QualityEval → done

If STILL failing after Tier 1 + Tier 2:
  → Regenerate (iteration 1): Generator with targeted reasoning
  → Same Tier 1 → Tier 2 cycle

Max 3 total generator calls. Tier 1/Tier 2 corrections are intra-iteration.
```

**Key architectural change**: Corrections happen WITHIN an iteration (patch + re-validate) rather than across iterations (feedback → regenerate). A typical key-mismatch failure should resolve in 1 generator call.

### TieredCorrectionAgent

**New file**: `src/agents/tiered_correction_agent.py`

A `BaseAgent` that replaces the current `FeedbackAgent` in the loop. It orchestrates:
1. Error classification (Tier 1 vs Tier 2)
2. Tier 1 deterministic patches
3. Fast re-validation
4. Tier 2 LLM JSON patches (if needed)
5. Full re-validation
6. State update for loop decision (continue/regenerate/exit)

### Feedback Signal Design

Validated against stat_var_processor source (3093 lines, every `add_counter` call verified) and Gemini DC expert review.

#### Tier 1 Signals (deterministic correction)

| # | Signal | Source Counter | Correction Action |
|---|--------|---------------|-------------------|
| 1 | Unmatched PVMAP keys | `error-pvmap-dropped-undefined-property_{KEY}` | Force key match via normalization cascade |
| 2 | Unresolved templates | `warning-unresolved-value-ref_{TEMPLATE}` | Fix placeholder syntax (`[DATA]`→`{Data}`) |
| 3 | Unresolved places | `error-unresolved-place_{VALUE}` | Fix geoId format, add prefix, zero-pad FIPS |
| 4 | Missing required props | `error-svobs-missing-property_{DETAIL}` | Inject mapping from column_manifest |
| 5 | Missing place mapping | `warning-svobs-missing-place` | Map place column identified by profiler |
| 6 | Unresolved dates | `dropped-svobs-unresolved-date` | Fix date format/column mapping |
| 7 | Invalid aggregation values | `error-aggregate-invalid-values` | Switch `{Number}` → `{Data}` for non-numeric columns |

#### Tier 2 Signals (LLM semantic patches)

| # | Signal | Source Counter | LLM Task |
|---|--------|---------------|----------|
| 8 | Duplicate observation tuples | `error-mismatched-svobs_{DETAIL}` | Identify which unmapped column resolves collision |
| 9 | Dropped StatVar names | `dropped-invalid-statvars_{DCID}` | Analyze why StatVar definition is invalid |
| 10 | Output property cardinality | `output-svobs-unique-{PROPERTY}` | Flag collapsed dimensions (compare to expected) |
| 11 | Dropped observation context | `dropped-invalid-svobs_{FULL_TUPLE}` | Analyze dropped observation tuples |
| 12 | Per-StatVar observation imbalance | `generated-svobs_{DCID}` counts | Identify inconsistent dimension mapping |
| 13 | MCF property distribution | Parsed from `.mcf` file | Raw strings needing DCID mapping |

#### Routing Signals

| Signal | Threshold | Route |
|--------|-----------|-------|
| Coverage % | <10% CRITICAL | Determines urgency |
| `error-pvmap-dropped-undefined-property` | >0 | Tier 1 |
| `error-mismatched-svobs` | >0 | Tier 2 |
| Wasted PVMAP rows (`dropped-statvars-without-svobs`) | >30% of statvars | Tier 2 |

#### Removed (redundant)
- Raw log sampling (`extract_log_samples()`) — replaced by structured counter extraction
- Iteration advice text — replaced by tiered correction logic
- Separate fragmentation ratio — derivable from counters
- Separate wide/long detection — handled by collision analysis + profiler already has this

### Tier 1 Correction Rules

Extends `pvmap_corrector.py` with a normalization-first key matching cascade and new rules.

#### Rule 0: force_key_match (UPGRADED)

The most impactful change. Replaces current fuzzy matching (0.80-0.85 threshold) with a strict normalization cascade:

1. **Exact match**: `key == header`
2. **Normalized exact**: Strip whitespace, lowercase, remove non-alphanumeric. `Count_Person_Female` matches `Count Person Female`
3. **Token set ratio**: Permutation-invariant. `Population Female` matches `Female Population`
4. **REJECT if only numeric-different match**: `Age 15-19` must NOT match `Age 15-29`. Any edit involving a digit change is rejected to prevent silent data corruption.

Applied to ALL unmatched PVMAP keys after generation. Uses exact failing keys from `error-pvmap-dropped-undefined-property_{KEY}` counter.

**Edge case guards** (from Gemini):
- Value-based keys (e.g., `Male` in a `COLUMN:VALUE` mapping) are NOT matched against column headers
- Literal MCF constants (`Person`, `count`) are NOT matched against headers
- Keys with `:` are split via `_split_column_value()` before matching the column part

#### Rule 1: fix_missing_required_props (NEW)

When `error-svobs-missing-property` fires and `column_manifest` identifies the required column:
- If no `observationAbout` → inject place column from manifest
- If no `observationDate` → inject date/year column from manifest
- If no `value` → inject first numeric column from manifest

#### Rule 2: fix_duplicate_observation (UPGRADED)

When `error-mismatched-svobs` fires, run collision resolution scoring:
1. Parse colliding tuples from `error-mismatched-svobs_{DETAIL}`
2. Identify mapped dimensions from current PVMAP
3. For each unmapped column in column_manifest with role=DIMENSION:
   - Check if its cardinality matches the collision multiplier
4. If exactly one column resolves: add it as constraintProperty (Tier 1 fix)
5. If ambiguous: delegate to Tier 2 (LLM decides which column and how to map values)

#### Existing rules (kept as-is)
- `fix_place_leading_zeros`, `fix_place_prefix`, `fix_csv_structure`, `fix_aggregate_invalid`

### Tier 2: Semantic LLM Patches

A new `SemanticPatchAgent` (LlmAgent with `output_schema`) that outputs JSON:

```json
{
  "patches": [
    {
      "action": "replace_row",
      "key": "Race",
      "new_row": "Race:White,race,dcid:WhiteAlone"
    },
    {
      "action": "add_row",
      "row": "Race:Black,race,dcid:BlackOrAfricanAmericanAlone"
    },
    {
      "action": "remove_row",
      "key": "bad_column"
    },
    {
      "action": "update_property",
      "key": "NIPR",
      "old_property": "statType",
      "old_value": "measuredValue",
      "new_property": "statType",
      "new_value": "Count"
    }
  ],
  "reasoning": "The Race column has categorical values that need DCID enum mappings from the schema vocabulary."
}
```

**Patch actions**:
- `replace_row`: Replace entire PVMAP row by key
- `add_row`: Add new PVMAP row
- `remove_row`: Remove PVMAP row by key
- `update_property`: Change a specific property-value pair within a row

Patches applied programmatically by TieredCorrectionAgent — NEVER fed as text to the generator.

### Counter Parsing Improvements

Upgrade `log_filter.py:filter_counters()` to extract signals currently missed:

1. **Parse `output-svobs-unique-{PROPERTY}`** counters into `property_cardinality` dict
2. **Parse `dropped-invalid-statvars_{DCID}`** into `dropped_statvar_names` list
3. **Parse `dropped-invalid-svobs_{TUPLE}`** into structured dicts: `{place, date, statvar, value, reason}`
4. **Parse `generated-svobs_{DCID}`** into per-StatVar observation counts for imbalance detection
5. **Parse `error-mismatched-svobs_{DETAIL}`** into collision tuple details
6. **Remove hardcoded 7-type limit** on debug example mining — mine ALL error types with `_{value}` suffixes
7. **Merge unmapped column roles + key match report** into unified "Unfulfilled Schema Requirements" signal

### Integration with Existing Loop

The TieredCorrectionAgent replaces the current `ConditionalFeedbackAgent` in the LoopAgent sequence:

```python
# Before (pvmap_retry_loop.py)
sub_agents = [
    StatePrep, Generator, MetadataGen, Validate, QualityEval,
    FeedbackAgent,  # Text feedback → next generator call
    MaxRetriesCheck,
]

# After
sub_agents = [
    StatePrep, Generator, MetadataGen, Validate, QualityEval,
    TieredCorrectionAgent,  # Deterministic + LLM patches → re-validate
    MaxRetriesCheck,
]
```

The TieredCorrectionAgent internally runs re-validation (calling `run_validation()` directly) and updates state accordingly.

**If Tier 1+2 patches resolve the issue**:
- Sets `validation_passed=True`, `validation_success=True` in state
- Sets `correction_resolved=True` flag
- Yields event with `escalate=True` to exit the LoopAgent immediately (no need for another generator call)
- QualityEval runs on the corrected PVMAP to set final quality metrics

**If patches improve but don't fully resolve**:
- Sets `validation_data_rows` to new row count (may be higher than before patches)
- Updates `best_pvmap_csv` if patched version is better
- Sets `regeneration_reasoning` in state — targeted guidance for the generator (much shorter than current feedback, focused only on what Tier 1+2 couldn't fix)
- Does NOT escalate — loop continues to MaxRetriesCheck → next iteration

**If patches make things worse**:
- Reverts to pre-patch PVMAP (stored before any patches applied)
- Sets `regeneration_reasoning` with "Tier 1+2 correction attempted but reverted"
- Does NOT escalate — loop continues

### Files Changed

| File | Change |
|------|--------|
| `src/agents/tiered_correction_agent.py` | NEW — TieredCorrectionAgent (BaseAgent) |
| `src/agents/semantic_patch_agent.py` | NEW — LLM agent with JSON output_schema for Tier 2 |
| `src/pipeline/validation/pvmap_corrector.py` | EXTEND — Add force_key_match, fix_missing_required, upgrade fix_duplicate_obs |
| `src/pipeline/validation/log_filter.py` | EXTEND — Parse new counter types (property cardinality, dropped details, collision tuples) |
| `src/agents/pvmap_retry_loop.py` | MODIFY — Replace FeedbackAgent with TieredCorrectionAgent in sub_agents list |
| `src/tools/validation_tool.py` | MODIFY — Return parsed FilteredLogs object (not just summary string) |
| `src/pipeline/validation/pvmap_repair.py` | EXTEND — Upgrade key matching cascade with numeric guards |
| `src/agents/feedback_agent.py` | DEPRECATE — Kept for backward compat but no longer in default loop |

### Testing Strategy

1. **Unit tests for each Tier 1 rule**: Given specific counter patterns, verify correct PVMAP patch
2. **Unit tests for JSON patch application**: Given a PVMAP + patch array, verify correct result
3. **Unit tests for counter parsing**: Given real counter files from actual runs, verify all signals extracted
4. **Integration test**: Run TieredCorrectionAgent on real failed PVMAPs from BIS, BRFSS, Census datasets
5. **A/B comparison**: Run 10 datasets with old feedback loop vs new tiered correction, compare pass rate

### Success Criteria

- Pass rate improvement from 46.2% to >70% across the 42-dataset portfolio
- KEY_MISMATCH resolved in Tier 1 (no generator retry needed) for >80% of cases
- Max 3 generator calls per dataset (unchanged)
- Tier 1 correction completes in <5 seconds (no subprocess for simple fixes)
- Zero silent data corruption from force key matching (numeric guard prevents Age 15-19 → Age 15-29 type errors)

### Risk Mitigation

1. **Force key matching corrupts numeric cohorts**: Mitigated by rejecting matches where edits involve digit changes
2. **Tier 2 LLM produces invalid JSON patches**: Validate patch schema before applying; fall back to regeneration if invalid
3. **Patching preserves broken rows**: Always re-validate after patches; if validation worsens, revert to pre-patch PVMAP
4. **Backward compatibility**: Keep FeedbackAgent available via config flag; TieredCorrectionAgent is opt-in initially
