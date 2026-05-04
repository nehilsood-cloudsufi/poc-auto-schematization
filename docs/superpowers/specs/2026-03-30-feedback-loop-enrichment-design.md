# Feedback Loop Enrichment + Tiered Correction Pipeline

**Date:** 2026-03-30
**Branch:** `feature/nehil/feedback_integration`
**Status:** Design approved, pending implementation

---

## Problem

Two interrelated problems with the current retry loop:

### Problem 1: Feedback Quality
The LLM retry loop receives feedback from `log_filter.py` after each validation attempt, but it **loses critical diagnostic signals** the processor already emits:

1. **Specific failing values** — The processor emits debug counters like `error-unresolved-place_geoId/6`, but `log_filter.py` only reads the base counter (`error-unresolved-place: 42`). The LLM sees "42 place failures" but not that they're all caused by missing leading zeros.
2. **No error prioritization** — Errors are sorted by count, not by impact.
3. **No fix recipes** — `counter_feedback.py` has an `ERROR_PATTERNS` dict but it's deprecated and not in the active path.
4. **No systematic pattern detection** — When all 42 place failures share a root cause, the feedback doesn't say so.
5. **No iteration-aware guidance** — All attempts get identical feedback structure.

### Problem 2: Retry Architecture
The current retry loop is wasteful:

1. After validation fails, the **entire PVMAP is regenerated from scratch** by the PVMAPGenerationAgent (expensive 30-60s LLM call with 15K-token prompt).
2. Good mappings that already work are **thrown away** and must be regenerated.
3. Many errors are **mechanically fixable** (key case, leading zeros, missing prefixes) but still trigger a full LLM regeneration.
4. The feedback agent is a separate LLM call between iterations, adding more latency.
5. Multiple full regeneration retries (`max_retries=2` = 3 total attempts) waste time on patterns that don't need LLM intervention.

---

## Approach: Enriched Feedback + Tiered Correction Pipeline

Two changes, designed together:

1. **Enrich `log_filter.py`** with `counter_feedback.py`'s best features (debug extraction, priority ordering, fix recipes, pattern detection). This enriched data feeds both programmatic correction AND LLM correction.

2. **Replace the `LoopAgent` retry loop** with a tiered correction pipeline that escalates from programmatic fixes → lightweight LLM patch → full regeneration (last resort).

---

# Part 1: Feedback Enrichment

## Reference: stat_var_processor Processing Pipeline

```
Input CSV + PVMAP CSV + (optional) Metadata CSV
    │
    ▼
Phase 0: LOAD PV MAP
  - Parse PVMAP CSV into key→property map
  - 5-level fuzzy key matching: exact → case-insensitive → alphanumeric → n-gram → substring
    │
    ▼
Phase 1: PROCESS INPUT (per row)
  - Match row values to PVMAP keys
  - Resolve {Data}, {Number} placeholder templates
  - Generate StatVar DCID from properties
  - Resolve place values → DC DCIDs
  - Parse date formats
    │
    ▼
Phase 2: PREPARE OUTPUT
  - Deduplicate StatVars, aggregate observations, drop invalid rows
    │
    ▼
Phase 3-4: WRITE OUTPUT
  - processed.csv, processed_stat_vars.mcf, processed.tmcf, processed_counters.txt
```

## Reference: Counter Inventory

### High-Signal Counters (directly actionable)

| Counter Key | Suffixed Variant | What It Tells Us | Current Status |
|---|---|---|---|
| `error-pvmap-dropped-undefined-property` | `_<key_name>` | Exact PVMAP keys that don't match any column header | Base count only (suffixes lost) |
| `warning-missing-property-key` | `_<unmapped_value>` | Input values that failed all 5 match levels | Captured + pattern classified |
| `error-unresolved-place` | `_<place_value>` | Specific place values that couldn't resolve to DCID | Base count only (suffixes lost) |
| `dropped-svobs-unresolved-place` | `_<StatVar_name>` | Which StatVars lost observations due to place failures | Captured |
| `warning-svobs-missing-place` | `_<StatVar_name>` | StatVars with NO observationAbout mapping | Captured |
| `error-mismatched-svobs` | `_<StatVar_name>` | Duplicate observations for same StatVar+Place+Date | Base count only (suffixes lost) |
| `warning-unresolved-value-ref` | `_<ref_name>` | Failed `{Data}` or `{Number}` template resolution | Captured |
| `error-aggregate-invalid-values` | `_<column>` | Non-numeric values in `{Number}` positions | Not extracted |
| `error-duplicate-statvars` | `_<StatVar_name>` | StatVar DCID collisions | Not extracted |
| `dropped-svobs-unresolved-date` | `_<date_value>` | Date values that couldn't parse | Not extracted |

### Key Insight

The processor already emits suffixed debug counters with specific failing values. `counter_feedback.py` has `extract_debug_examples()` that mines these. But `log_filter.py` (the active code path) only reads base counter keys — this is the single biggest feedback gap.

## Design: 5 Enhancements to log_filter.py

### Enhancement A: Debug Example Extraction (highest impact)

New `FilteredLogs` field:

```python
# Maps error type → [(failing_value, count), ...] top 5 per error type
error_examples: Dict[str, List[Tuple[str, int]]] = field(default_factory=dict)
```

For each error counter key, scan `raw_counters` for `{error_key}_{suffix}` variants. Collect `(suffix, count)` tuples, sort by count descending, keep top 5.

### Enhancement B: Error Priority Ordering

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

### Enhancement C: Fix Recipe Injection

Port `ERROR_PATTERNS` dict from `counter_feedback.py` (trimmed to essentials). Each error type maps to `category`, `common_causes`, and `fix` string.

### Enhancement D: Systematic Pattern Detection

Port `detect_systematic_patterns()` and `_detect_format_pattern()`. Detect:
1. **Single-value pattern** — All errors share same value. Confidence: 1.0.
2. **Few-values pattern** — <20% unique values cause all errors. Confidence: 0.8.
3. **Format pattern** — Missing leading zeros, missing `dcid:` prefix. Confidence: 0.85-0.9.

### Enhancement E: Iteration-Aware Hints

New parameter: `filter_counters(counters_path, attempt_number=0)`

```python
ITERATION_ADVICE = {
    0: "ATTEMPT 1: Focus on structural fixes -- key matching, required properties, correct archetype.",
    1: "ATTEMPT 2: Structure should be sound. Focus on value-level fixes -- place resolution, placeholders, enums.",
    2: "ATTEMPT 3 (FINAL): Preserve all working rows. Only fix the highest-impact remaining error.",
}
```

### Enriched Output Example

Before:
```markdown
## Errors (must fix)
- error-pvmap-dropped-undefined-property: 5
- error-unresolved-place: 42
```

After:
```markdown
## Errors (must fix — ordered by impact)

### 1. error-pvmap-dropped-undefined-property: 5 [PVMAP Key Mismatch]
**Failing keys:** State FIPS (x300), Year Code (x150), Age Group (x50)
**Common causes:**
- Case mismatch (State FIPS vs state_fips)
- Typo or hallucinated key name
**Fix:** Match keys EXACTLY to column headers (case-sensitive)

### 2. error-unresolved-place: 42 [Place Resolution]
**Failing values:** geoId/6 (x15), geoId/1 (x12), geoId/9 (x8)
**Common causes:**
- FIPS codes missing leading zeros (6 → 06)
**Fix:** Use geoId/[val:0>2] for states, geoId/[val:0>5] for counties

## Systematic Patterns Detected
### PATTERN: Missing leading zeros (confidence: 0.9)
**Error:** error-unresolved-place (42 occurrences)
**Fix:** Change observationAbout format to geoId/[val:0>2]

## Iteration Guidance
ATTEMPT 1: Focus on structural fixes -- key matching, required properties, correct archetype.
```

---

# Part 2: Tiered Correction Pipeline

## Architecture

```
┌──────────────────────────────────────────────────────────┐
│ Attempt 0: Initial Generation                            │
│                                                          │
│ StatePrep → PVMAPGenerator → pvmap_repair → Validate     │
│                                            │             │
│                                     passes? ──→ EXIT     │
│                                            │             │
│                                         fails            │
│                                            ▼             │
├──────────────────────────────────────────────────────────┤
│ Attempt 1: Tiered Correction (no full regen)             │
│                                                          │
│ ┌─ Tier 1: Programmatic Fix ──────────────────────────┐  │
│ │ FilteredLogs.error_examples + patterns → rule engine │  │
│ │ Apply fixes directly to PVMAP CSV                    │  │
│ │ Re-validate                                          │  │
│ │                              passes? ──→ EXIT        │  │
│ └──────────────────────────────│────────────────────────┘  │
│                             fails                         │
│ ┌─ Tier 2: Lightweight LLM Patch ─────────────────────┐  │
│ │ Input: current PVMAP + enriched to_summary() ONLY    │  │
│ │ Instruction: "Fix ONLY the failing rows"             │  │
│ │ Re-validate                                          │  │
│ │                              passes? ──→ EXIT        │  │
│ └──────────────────────────────│────────────────────────┘  │
│                             fails                         │
│              compare with best-so-far, keep better        │
│                                │                          │
├────────────────────────────────▼─────────────────────────┤
│ Attempt 2: Full Regeneration (ONE time, last resort)     │
│                                                          │
│ StatePrep → PVMAPGenerator (with all feedback)           │
│          → pvmap_repair → Validate                       │
│                            │                             │
│                     passes? ──→ EXIT                     │
│                            │                             │
│                         fails → return best-so-far       │
└──────────────────────────────────────────────────────────┘
```

**Key constraints:**
- Max 3 validation subprocess runs total (down from 3 full regen loops)
- No `max_retries` config — the tier structure IS the retry strategy
- Best-so-far tracking at every tier transition
- Tier 3 runs exactly ONCE

## Tier 1: Counter-Driven Rule Engine

New module `src/pipeline/validation/pvmap_corrector.py`.

### Rule Structure

```python
@dataclass
class CorrectionRule:
    name: str                          # e.g., "fix_key_case_mismatch"
    error_type: str                    # Which error triggers this rule
    condition: Callable                # Should this rule fire?
    apply: Callable                    # Transform PVMAP CSV string
    priority: int                      # Lower = runs first
```

### Initial Rules (6)

| Rule | Trigger | Fix |
|---|---|---|
| `fix_key_mismatch` | `error-pvmap-dropped-undefined-property` + debug examples + key_match_report | Replace mismatched PVMAP keys with correct column headers |
| `fix_place_leading_zeros` | `error-unresolved-place` + `missing_leading_zeros` pattern | Rewrite `geoId/[Data]` → `geoId/[Data:0>2]` or `[Data:0>5]` |
| `fix_place_prefix` | `error-unresolved-place` + examples starting with bare FIPS | Add `geoId/` prefix to observationAbout mapping |
| `fix_duplicate_observations` | `error-mismatched-svobs` + debug examples | Add comment identifying unmapped dimension column (prep for Tier 2) |
| `fix_missing_required_props` | `error-svobs-missing-property` | Repair malformed observationAbout/Date/value rows |
| `fix_aggregate_invalid` | `error-aggregate-invalid-values` + examples | Change `[NUMBER]` → `[DATA]` for columns with non-numeric values |

### API

```python
def apply_correction_rules(
    pvmap_csv: str,
    filtered_logs: FilteredLogs,
    key_match_report: str,
) -> Tuple[str, List[str]]:
    """Apply all matching correction rules to PVMAP.

    Returns: (corrected_pvmap_csv, list_of_changes_made)
    """
```

Tier 1 consumes `FilteredLogs` fields directly (structured data) — no markdown parsing.

## Tier 2: Lightweight LLM Patch Agent

New file `src/agents/pvmap_patch_agent.py`.

| Aspect | Full Generator (Tier 3) | Patch Agent (Tier 2) |
|---|---|---|
| Prompt size | ~15K tokens | ~2K tokens |
| Input context | Full skeleton, schema, samples | PVMAP + enriched counter summary + key_match_report only |
| Instruction | "Generate complete PVMAP" | "Fix ONLY the failing rows" |
| LLM call cost | 30-60s | 5-15s |
| Tools | Schema.org lookup | None |

**Constraint instruction:**
```
You are a PVMAP repair specialist. You receive a PVMAP that partially works
and specific error diagnostics.

RULES:
1. Do NOT remove or modify any row that is currently producing output observations
2. ONLY fix rows identified in the error report
3. Keep the same CSV structure — same number of columns, same format
4. If you cannot fix an error, leave the row unchanged
5. Return the COMPLETE PVMAP (not just changed rows)
```

**State inputs:** `pvmap_csv`, `validation_counter_summary` (enriched), `key_match_report`
**State output:** `pvmap_csv` (overwritten with patched version)

**Safety:** Best-so-far comparison after Tier 2 validation. If Tier 2 produces fewer data_rows than Tier 1 (or the original), discard the patch.

## Retry Loop Rewrite

### Current agents — what changes:

| Current Agent | Fate |
|---|---|
| `StatePreparationAgent` | **Keep** — simplify, no loop iteration tracking |
| `PVMAPGenerationAgent` | **Keep** — runs on attempt 0 and Tier 3 only |
| `ValidationAgent` | **Keep** — runs at each re-validation step |
| `ConditionalFeedbackAgent` | **Remove** — replaced by Tier 1 + Tier 2 |
| `QualityEvaluationAgent` | **Keep** — runs after final validation |
| `MaxRetriesCheckAgent` | **Replace** — best-so-far tracking in `TieredCorrectionAgent` |
| `LoopAgent` (ADK) | **Remove** — replaced by `TieredCorrectionAgent(BaseAgent)` |

### New orchestrator: `TieredCorrectionAgent`

A `BaseAgent` subclass that runs sequentially:

```python
class TieredCorrectionAgent(BaseAgent):
    async def _run_async_impl(self, ctx):
        if ctx.session.state.get("validation_success"):
            return  # Attempt 0 passed

        best_pvmap = ctx.session.state["pvmap_csv"]
        best_rows = ctx.session.state.get("validation_data_rows", 0)

        # --- Tier 1: Programmatic fix ---
        filtered_logs = filter_counters(counters_path, attempt_number=1)
        corrected, changes = apply_correction_rules(best_pvmap, filtered_logs, key_match_report)
        if changes:
            result = run_validation(...)
            if result["success"]: return
            if result.get("data_rows", 0) > best_rows:
                best_pvmap, best_rows = corrected, result["data_rows"]

        # --- Tier 2: Lightweight LLM patch ---
        patched = await run_patch_agent(ctx, best_pvmap, filtered_logs.to_summary())
        if patched != best_pvmap:
            result = run_validation(...)
            if result["success"]: return
            if result.get("data_rows", 0) > best_rows:
                best_pvmap, best_rows = patched, result["data_rows"]

        # --- Tier 3: Full regeneration (ONE time) ---
        ctx.session.state["error_feedback"] = filtered_logs.to_summary()
        ctx.session.state["pvmap_csv"] = best_pvmap
        await run_full_generator(ctx)
```

---

## Files Changed — Complete Map

| File | Action | What Changes |
|---|---|---|
| **New Files** | | |
| `src/pipeline/validation/pvmap_corrector.py` | Create | Tier 1 rule engine: `CorrectionRule`, 6 rules, `apply_correction_rules()` |
| `src/agents/pvmap_patch_agent.py` | Create | Tier 2 LLM patch agent: `create_pvmap_patch_agent()` |
| `src/resources/prompts/pvmap_patch_agent.txt` | Create | Tier 2 prompt template (~40 lines) |
| `tests/pipeline/validation/test_pvmap_corrector.py` | Create | Tests for all 6 correction rules + rule engine |
| `tests/agents/test_pvmap_patch_agent.py` | Create | Tests for patch agent creation |
| **Modified Files** | | |
| `src/pipeline/validation/log_filter.py` | Modify | ERROR_PRIORITY, ERROR_PATTERNS, error_examples field, debug extraction, detect_systematic_patterns(), priority ordering, iteration hints |
| `src/tools/validation_tool.py` | Modify | Pass `attempt_number` to `filter_counters()` |
| `src/agents/pvmap_retry_loop.py` | Modify | Replace LoopAgent+ConditionalFeedbackAgent with TieredCorrectionAgent. Remove max_retries. |
| `src/resources/prompts/feedback_agent_v2.txt` | Modify | Update for enriched counter summary sections |
| `src/agents/coordinator.py` | Modify | Wire TieredCorrectionAgent into pipeline sequence |
| `src/config/cli_parser.py` | Modify | Remove `--max-retries` flag (or deprecation warning) |
| `src/pipeline/validation/counter_feedback.py` | Modify | Add deprecation notice |
| `tests/pipeline/validation/test_log_filter.py` | Modify | ~30 new tests for enrichment |
| **Untouched** | | |
| `src/pipeline/validation/stat_var_processor.py` | No change | |
| `src/agents/validation_agent.py` | No change | Already passes attempt_number |
| `src/pipeline/validation/pvmap_repair.py` | No change | Pre-validation repair unchanged |
| `src/agents/pvmap_generation_agent.py` | No change | Just called less often |

---

## Testing Strategy

1. **log_filter enrichment** (~30 tests): debug extraction, priority ordering, fix recipes, pattern detection
2. **pvmap_corrector rules** (~20 tests): each rule with mock counter data and PVMAP CSV
3. **pvmap_patch_agent** (~5 tests): agent creation, prompt structure, constraint verification
4. **TieredCorrectionAgent** (~5 tests): tier escalation logic, best-so-far tracking
5. **Integration** (~5 tests): full pipeline run on test datasets
6. **Regression**: all existing tests must pass

Estimated: ~60-65 new tests.

---

## Success Criteria

1. Enriched `FilteredLogs` with specific failing values for all error types
2. Errors sorted by impact priority with fix recipes
3. Systematic patterns detected and surfaced
4. Tier 1 programmatic fixes resolve key-case and leading-zero errors without any LLM call
5. Tier 2 lightweight LLM patch fixes complex issues in 5-15s (not 30-60s)
6. Tier 3 full regeneration runs at most ONCE
7. Max 3 validation runs total per dataset
8. Best-so-far tracking prevents regression at each tier
9. All existing tests pass, no processor changes

---

## Full Pipeline Verification Matrix

After implementation, run the following test matrix to verify all argument combinations work correctly. Datasets are selected to cover different archetypes (wide, flat, dimension-rich, geo-heavy, international).

### Test Group 1: Core Pipeline (default flags)

Tests the basic tiered correction flow with default arguments.

```bash
# Simple dataset (flat, few columns) — should pass quickly
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# Dimension-rich dataset (multiple dimension columns, needs qualifiers)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence

# Wide dataset (many columns, complex mapping)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=census_v2_sahie

# International dataset (non-US places, ISO codes)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=oecd_regional_education
```

**Verify for each:**
- Pipeline completes without error
- Output files exist: `output/{dataset}/generated_pvmap.csv`, `output/{dataset}/processed/`
- Logs show tiered correction flow (Tier 1 → Tier 2 → Tier 3 if needed)
- No more than 3 validation subprocess runs in logs

### Test Group 2: Schema & Sampling Flags

Tests that skip/force flags still work with the new tiered architecture.

```bash
# Skip sampling (use cached data) — tiered correction should still work
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-sampling

# Force re-sample — verify fresh sampling feeds into tiered correction
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --force-resample

# Skip schema selection — no schema vocab, correction still works
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-schema-selection

# No schema examples in prompt — generator gets less context, correction compensates
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=census_v2_sahie --no-schema-examples

# Skip column discovery — no column completeness report
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --skip-column-discovery
```

### Test Group 3: Evaluation & Ground Truth

Tests that evaluation still works after the retry loop rewrite.

```bash
# With ground truth evaluation (GT dataset)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# Skip evaluation entirely
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --skip-evaluation

# Explicit ground truth file
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=census_v2_sahie --ground-truth-pvmap=ground_truth/census_v2_sahie/pvmap/census_v2_sahie_pvmap.csv

# LLM judge evaluation
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --use-llm-judge
```

### Test Group 4: Model & Prompt Variants

Tests that different model/prompt versions work with tiered correction.

```bash
# Prompt v2 (older prompt)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --prompt-version=v2

# Prompt v3 (default, sandwich architecture)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --prompt-version=v3

# Feedback prompt v1 (comprehensive) — still used by Tier 3 fallback
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --feedback-prompt-version=v1

# Feedback prompt v2 (concise, default)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --feedback-prompt-version=v2

# Structured output disabled
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --no-structured-output

# Verbose logging (verify enriched counter summary visible in logs)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate --verbose
```

### Test Group 5: MCP Integration

Tests MCP flags with tiered correction.

```bash
# DC MCP enabled (Tier 2 patch agent does NOT use MCP, only Tier 3 generator does)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=census_v2_sahie --enable-mcp

# Schema.org MCP enabled
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --enable-schemaorg-mcp

# Both MCPs enabled
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=oecd_regional_education --enable-mcp --enable-schemaorg-mcp
```

### Test Group 6: Metadata & Input Overrides

Tests metadata and input file flags.

```bash
# Use metadata
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=census_v2_sahie --use-metadata

# Explicit metadata file
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=census_v2_sahie --metadata-file-path=input/census_v2_sahie/input_metadata/census_v2_sahie_metadata.csv

# Explicit schema file
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --schema-file=input/brfss_nchs_asthma_prevalence/schema/schema_vocab.json
```

### Test Group 7: Edge Cases

Tests that the tiered correction handles edge cases gracefully.

```bash
# Dataset that typically passes on first attempt (no correction needed)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=zurich_bev_3240_wiki

# Large dimension-heavy dataset (India NFHS — stress test for Tier 1 rule engine)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=india_nfhs

# Dataset with complex geo (US county-level FIPS — exercises place resolution fixes)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=cdc_social_vulnerability_index

# Dataset with no ground truth (non-GT quality gate path)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=world_bank_commodity_market
```

### Verification Checklist (for EACH run)

After each pipeline run, verify:

- [ ] Pipeline exits cleanly (exit code 0 or graceful timeout)
- [ ] `output/{dataset}/generated_pvmap.csv` exists and is non-empty
- [ ] `output/{dataset}/processed/` directory contains output files
- [ ] Log file in `logs/{dataset}/` shows:
  - [ ] "Tier 1" or "programmatic fix" entries (if correction was needed)
  - [ ] "Tier 2" or "patch agent" entries (if Tier 1 didn't fully resolve)
  - [ ] "Tier 3" or "full regeneration" entries (if Tier 2 didn't resolve — should be rare)
  - [ ] At most 3 `stat_var_processor` subprocess invocations
  - [ ] Enriched counter summary with "ordered by impact" and "Failing values" (if errors existed)
- [ ] No Python tracebacks in log files
- [ ] `output/{dataset}/generation_notes.md` reflects the tiered correction flow

### Quick Smoke Test (minimum viable verification)

If time is limited, run these 4 commands — they cover the critical paths:

```bash
# 1. Default flow, simple dataset (tests basic tiered correction)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# 2. Dimension-rich with GT (tests Tier 1 rules + quality evaluation)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence

# 3. Skip flags combo (tests flag compatibility with new architecture)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=census_v2_sahie --skip-sampling --skip-schema-selection --skip-evaluation

# 4. Full flags combo (tests everything together)
PYTHONPATH="$(pwd):$(pwd)/src" python src/run_pipeline.py --dataset=oecd_regional_education --verbose --use-llm-judge --prompt-version=v3 --feedback-prompt-version=v2
```
