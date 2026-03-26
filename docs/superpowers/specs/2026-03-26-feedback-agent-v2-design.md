# Feedback Agent v2 — Prompt Rewrite + Quality Gate Refactor

**Date:** 2026-03-26
**Author:** Nehil + Claude
**Status:** Draft
**Approach:** Prompt rewrite + QualityEvaluationAgent refactor + GT separation

## Problem Statement

The current `feedback_agent.txt` (291 lines) was written when upstream context was thinner. Since then, `counter_feedback.py`, `log_filter.py`, and `pvmap_repair.py` have been added — all providing rich, pre-processed diagnostics that the prompt's static sections now duplicate (~90 lines teach the LLM to re-derive insights already in `{validation_counter_summary}` and `{key_match_report}`).

Additionally, the feedback system conflates two distinct use cases:
1. **Production (no GT):** Feedback should focus on "what prevents stat_var_processor from producing valid output?"
2. **Testing (with GT):** Feedback should additionally compare against ground truth PV accuracy.

The `QualityEvaluationAgent` mixes heuristic scoring with GT comparison, and the retry loop uses the same `max_retries=3` and quality gates for both modes.

## Goals

1. **Reduce feedback prompt by ~55%** (291 → ~130 lines) — strip redundant metrics interpretation
2. **Separate GT from non-GT paths** — GT analysis as conditional `{{GT_FEEDBACK_SECTION}}` placeholder
3. **Production-optimized retry logic** — non-GT: max_retries=2, column_coverage as sole quality gate
4. **Processor-focused feedback** — organize around stat_var_processor outcomes (0 rows / partial / full)
5. **Maintain placeholder contract** — same injection mechanism via `ConditionalFeedbackAgent`

## Non-Goals

- Changing `counter_feedback.py`, `log_filter.py`, or `pvmap_repair.py` (upstream producers)
- Changing the PVMAP generator prompt (`improved_pvmap_prompt_v3.txt`)
- Splitting `QualityEvaluationAgent` into separate classes (use conditional blocks instead)
- Changing the `ValidationAgent` (structural validation stays as-is)

## Decisions (from brainstorming)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| GT separation | Conditional `{{GT_FEEDBACK_SECTION}}` placeholder | Empty when no GT, populated with PV accuracy analysis when GT exists |
| QualityEvaluationAgent refactor | Conditional block within same class | Minimal refactor — no new classes |
| Non-GT primary gate | stat_var_processor success + data_rows > 0 | Production reality: "did it produce valid output?" |
| Non-GT secondary gate | Column coverage >= 80% only | Catches unmapped dimensions even when processor succeeds |
| Heuristics in non-GT | Computed for logging, only column_coverage triggers retries | Other heuristics (row/prop/format) are secondary signals |
| GT quality gate | pv_accuracy >= 30% OR heuristic >= 70 (preserves current) | GT mode can force additional retries |
| max_retries | 2 for non-GT, 3 for GT | Fewer retries saves API costs when there's no GT to chase |
| Schema.org tool instructions | Remove — 2-line hint only | ADK wires tools; same rationale as PVMAP v3 prompt |
| Metrics interpretation (Step 2) | Strip entirely | counter_feedback.py and key_match_report already do this |
| Root cause (Step 1) | Condense 86 → ~15 lines | Checklist, not tutorial |
| Output format + guardrails | Keep | Well-defined, actionable |
| Drop from context | `{sampled_data}`, `{structure_warnings}`, `{mcp_resolved_context}` | Redundant with skeleton or rarely populated |
| Prompt structure | Sandwich (same as PVMAP v3) | Rules at top/bottom, context in middle |

## Prompt Architecture

```
TOP LAYER (high attention — primacy)
├── 1. Role & Task (~3 lines)
├── 2. Feedback Mode ({feedback_mode})
└── 3. Processor-Focused Analysis Framework (~15 lines)
    ├── PATH A: 0 rows — key/structural failures checklist
    ├── PATH B: partial rows — column-specific drop diagnosis
    └── Root cause checklist (key mismatch, missing props, DCID, #Eval)

MIDDLE LAYER (injected context — reference data)
├──  4. {validation_error}
├──  5. {validation_counter_summary}
├──  6. {pvmap_csv}
├──  7. {key_match_report}
├──  8. {pvmap_repair_changes}
├──  9. {column_completeness_report}
├── 10. {quality_metrics}
├── 11. {skeleton_summary} (compacted)
├── 12. {schema_category} + {schema_vocab_content}
├── 13. {validation_statvar_analysis}
└── 14. {{GT_FEEDBACK_SECTION}} (empty when no GT)

BOTTOM LAYER (high attention — recency)
├── 15. Output Format (~15 lines)
├── 16. Guardrails (5 NEVER rules)
├── 17. Schema.org tool hint (2 lines)
└── 18. "Provide your analysis now."
```

**Estimated total: ~130 lines** (vs 291 in v1, ~55% reduction)

### Dropped Context Variables

| Variable | Reason |
|----------|--------|
| `{sampled_data}` | Redundant — skeleton_summary Section 1.5 has column names, types, cardinality, sample values |
| `{structure_warnings}` | Usually empty; info already in key_match_report pre-validation warnings |
| `{mcp_resolved_context}` | Rarely populated; only when MCP enabled AND errors occurred |

### GT Feedback Section Content (~20 lines, injected conditionally)

**Placeholder mechanism:** The GT section uses a normal state variable `{gt_feedback_section}` (single braces), NOT double-brace `{{...}}` syntax. `ConditionalFeedbackAgent._prepare_feedback_state()` sets this state variable before invoking the FeedbackAgent LlmAgent. ADK resolves `{gt_feedback_section}` from state at runtime, just like all other placeholders in the prompt.

When GT is available, `ConditionalFeedbackAgent` populates `gt_feedback_section` with:

```
## Ground Truth Comparison
[GT score section formatted by ConditionalFeedbackAgent._format_gt_section()]

### PV Accuracy Analysis
If PV accuracy is low, the PVMAP structure is OK but property-value pairs don't match:
- Cross-reference generated properties against schema_vocab property_vocabulary
- Check if dimension values use proper DCIDs from vocabulary
- Verify populationType matches stat_var_skeletons for this domain
- Check StatVar Analysis for corrupted/malformed values
- If raw strings appear where DCIDs expected, suggest Column:Value mappings with vocab DCIDs
```

When no GT: `gt_feedback_section` = empty string.

**Note:** `gt_score_section` formatting stays in `ConditionalFeedbackAgent._format_gt_section()` (pvmap_retry_loop.py line 1457), NOT in `QualityEvaluationAgent`. The quality agent only sets the raw metric values; the feedback agent formats them for the prompt.

## Quality Gate Refactor

### Current Behavior (QualityEvaluationAgent)

```python
# Always compute heuristic score (0-100)
# Always compare GT if available
# quality_acceptable = heuristic >= 70 OR pv_accuracy >= 30
# quality_stagnant = improvement < 10% of previous
```

### New Behavior

```python
gt_available = bool(state.get("gt_pvmap_path_cached"))

# Always compute heuristic (for logging/reporting)
heuristic = calculate_heuristic_score(...)

if gt_available:
    # GT mode: full evaluation
    gt_comparison = compare_pvmaps(...)
    quality_acceptable = (
        gt_comparison.pv_accuracy >= PV_ACCURACY_THRESHOLD  # 30%
        or heuristic.score >= QUALITY_THRESHOLD  # 70
    )
    quality_reject_reason = "pv_accuracy_low" if not quality_acceptable else None
    # NOTE: gt_score_section formatting stays in ConditionalFeedbackAgent._format_gt_section()
    # QualityEvaluationAgent only stores raw gt_node_accuracy, gt_pv_accuracy in quality_metrics
else:
    # Non-GT mode: column coverage is the only additional quality gate
    # NOTE: existing check_column_completeness() critical gate is preserved (runs first)
    column_coverage = heuristic.breakdown["column_coverage"]
    quality_acceptable = column_coverage >= COLUMN_COVERAGE_THRESHOLD  # 80
    quality_reject_reason = "column_coverage_low" if not quality_acceptable else None
```

### New Constants

```python
COLUMN_COVERAGE_THRESHOLD = 80.0  # Non-GT quality gate (% of input columns in PVMAP)
```

Existing constants unchanged:
- `QUALITY_THRESHOLD = 70.0` (heuristic, used in GT mode)
- `PV_ACCURACY_THRESHOLD = 30.0` (GT PV accuracy)

## Retry Loop Changes

### max_retries and Loop Ordering

**Loop agent order:** `QualityEvaluator → MaxRetriesCheck → UnifiedFeedback`

`MaxRetriesCheck` runs BEFORE `UnifiedFeedback`. When it escalates at `attempt >= max_retries`, the loop exits WITHOUT running feedback on the final iteration. This means:

- **Non-GT (max_retries=2):** attempt 0 (initial) → feedback → attempt 1 (retry) → feedback → attempt 2 (MaxRetriesCheck escalates, no feedback). **2 feedback-informed attempts.** This is acceptable — with the processor-focused feedback, 2 informed retries should be sufficient.
- **GT (max_retries=3):** attempt 0 → feedback → attempt 1 → feedback → attempt 2 → feedback → attempt 3 (escalates). **3 feedback-informed attempts.**

```python
def create_pvmap_retry_loop(...):
    gt_available = bool(gt_pvmap_path)  # determined at pipeline start
    max_retries = 2 if not gt_available else 3
```

Or dynamically in `MaxRetriesCheckAgent`:
```python
gt_available = bool(ctx.session.state.get("gt_pvmap_path_cached"))
effective_max = 2 if not gt_available else self._max_retries  # 3
```

### ConditionalFeedbackAgent Changes

1. **GT placeholder injection (uses single-brace `{gt_feedback_section}`, resolved by ADK from state):**
   ```python
   gt_available = bool(ctx.session.state.get("gt_pvmap_path_cached"))
   if gt_available:
       gt_section = GT_FEEDBACK_TEMPLATE.format(
           gt_score_section=self._format_gt_section(ctx)  # stays in ConditionalFeedbackAgent
       )
   else:
       gt_section = ""
   ctx.session.state["gt_feedback_section"] = gt_section
   ```
   **Note on ADK safety:** The variable name `gt_feedback_section` must not collide with any LLM-generated PVMAP content. This is safe because PVMAP placeholders use `{Data}`, `{Number}` patterns which are escaped to `[DATA]`, `[NUMBER]` before reaching the feedback agent.

2. **Drop unused variables from preparation — all 4 locations per variable:**
   - Remove `sampled_data` from `_FEEDBACK_CAPS`, `_FEEDBACK_STATE_KEYS`, escaping loops, and `_FEEDBACK_RESTORE_KEYS`
   - Remove `structure_warnings` from same 4 locations
   - Remove `mcp_resolved_context` from same 4 locations
   - **Important:** `sampled_data` MUST remain in session state for `QualityEvaluationAgent._evaluate_with_heuristics()` — only remove from the feedback preparation path, not from state itself.

3. **Feedback prompt version selection:**
   ```python
   feedback_version = ctx.session.state.get("feedback_prompt_version", "v1")
   template_name = f"feedback_agent{'_v2' if feedback_version == 'v2' else ''}.txt"
   ```

### Feedback Paths (Non-GT Production Mode)

| Scenario | data_rows | validation_passed | column_coverage | Action |
|----------|-----------|-------------------|-----------------|--------|
| Total failure | 0 | False | n/a | **PATH A**: feedback on key/structural fixes, retry |
| Partial success | >0 | True | <80% | **PATH B**: feedback on dropping columns, retry |
| Full success | >0 | True | >=80% | **EXIT**: done, log heuristics |

### Feedback Paths (GT Testing Mode)

Same as above, plus:

| Scenario | pv_accuracy | Action |
|----------|-------------|--------|
| Structure OK, PV low | <30% | **PATH GT**: feedback with GT section, retry (up to attempt 3) |
| PV acceptable | >=30% | **EXIT**: done |

## Token Budget Impact

| Component | v1 (lines) | v2 (lines) | Savings |
|-----------|-----------|-----------|---------|
| Role & task | 3 | 3 | 0 |
| Step 0: Schema.org tools | 23 | 2 | -21 |
| Step 1: Root cause | 86 | 15 | -71 |
| Step 2: Metrics interpretation | 68 | 0 | -68 (upstream does this) |
| Steps 3-4: Fixes + patterns | 16 | 12 | -4 |
| Output format | 19 | 15 | -4 |
| Guardrails | 7 | 7 | 0 |
| Context section headers | 55 | 40 | -15 (3 variables dropped) |
| GT section | (inline ~27) | 0 + conditional 20 | -7 (conditional) |
| **Total** | **291** | **~130** | **~161 lines (-55%)** |

## Downstream Code Changes

### Phase A: Prompt Rewrite + Quality Gate + A/B Testing

#### A1. `src/resources/prompts/feedback_agent_v2.txt`
NEW — rewritten prompt ~130 lines with sandwich architecture, processor-focused paths, GT as `{{GT_FEEDBACK_SECTION}}`.

#### A2. `src/agents/quality_evaluation_agent.py`
MODIFY — add `gt_available` conditional:
- Non-GT: `quality_acceptable = column_coverage >= 80`
- GT: preserve current behavior (`pv_accuracy >= 30 OR heuristic >= 70`)
- Add `COLUMN_COVERAGE_THRESHOLD = 80.0` constant
- Only run `compare_pvmaps()` when GT available

#### A3. `src/agents/pvmap_retry_loop.py`
MODIFY:
- `ConditionalFeedbackAgent`: inject `{{GT_FEEDBACK_SECTION}}`, drop 3 unused state vars from preparation
- `MaxRetriesCheckAgent`: `max_retries = 2` when no GT, `3` when GT
- `StatePreparationAgent`: support `feedback_prompt_version` from state, load correct template
- Add `--feedback-prompt-version` flag reading

#### A4. `src/agents/feedback_agent.py`
MODIFY — support feedback prompt version selection. Currently the prompt is loaded at module import time as a constant (`FEEDBACK_AGENT_INSTRUCTION = load_prompt("feedback_agent.txt")`). Change `create_feedback_agent()` to accept a `prompt_version` parameter and load the correct template at call time:
```python
def create_feedback_agent(model=..., prompt_version="v1", ...):
    template_name = f"feedback_agent{'_v2' if prompt_version == 'v2' else ''}.txt"
    instruction = load_prompt(template_name)
    return LlmAgent(instruction=instruction, ...)
```
The module-level `FEEDBACK_AGENT_INSTRUCTION` constant can remain as the v1 default for backward compatibility.

#### A5. `src/config/cli_parser.py`
MODIFY — add `--feedback-prompt-version` flag (choices: v1, v2; default: v1).

#### A6. `src/run_pipeline.py`
MODIFY — wire `feedback_prompt_version` through to pipeline state. Add to both argparsers (cli_parser.py and run_pipeline.py's own parser).

### Phase B: Set v2 as Default (after A/B)

Same pattern as PVMAP v3: flip defaults after A/B validation.

## A/B Testing Plan

### Datasets (10, same as PVMAP v3 A/B)

| # | Dataset | Has GT? | Flags |
|---|---------|---------|-------|
| 1 | `brfss_nchs_asthma_prevalence` | Yes | default |
| 2 | `bis_bis_central_bank_policy_rate` | Yes | `--enable-mcp` |
| 3 | `us_urban_school_teachers` | Yes | default |
| 4 | `census_v2_sahie` | Yes | `--use-metadata` |
| 5 | `world_bank_commodity_market` | Yes | default |
| 6 | `cdc_social_vulnerability_index` | No GT | `--enable-mcp` |
| 7 | `india_nfhs` | No GT | `--no-schema-examples` |
| 8 | `oecd_regional_education` | Yes | `--use-metadata --enable-mcp` |
| 9 | `opendataforafrica_kenya_census` | Yes | default |
| 10 | `fao_currency_and_exchange_rate` | Yes | `--no-schema-examples` |

### Metrics

| Metric | Description | Primary? |
|--------|-------------|----------|
| `validation_data_rows` | SVObs produced | Yes |
| `validation_success` | Pass/fail | Yes |
| Retry attempts | Iterations needed | Secondary |
| Wall-clock time | Total runtime | Secondary (expect improvement from fewer retries) |

### Acceptance Criteria

- v2 matches or exceeds v1 on >=8/10 datasets for `validation_data_rows`
- No single dataset regresses by >20%
- Non-GT datasets should use fewer retries (max 2 vs 3)
- Rollback: if regressions, default remains v1

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| Condensed root cause section misses edge cases | Medium | A/B test on 10 diverse datasets |
| Column coverage threshold (80%) too strict/lenient | Medium | Monitor and tune; can adjust without prompt change |
| Dropping `{sampled_data}` from feedback hurts analysis | Low | skeleton_summary has column info; data is in pvmap_csv |
| GT/non-GT path bug | Low | Separate tests for both paths |
| max_retries=2 insufficient for some non-GT datasets | Low | Can fall back to `--feedback-prompt-version v1` which keeps 3 retries |
| ADK template variable collision with `{gt_feedback_section}` | Very Low | PVMAP placeholders ({Data}, {Number}) are escaped to [DATA], [NUMBER] before reaching feedback agent; no collision possible |

## File Changes Summary

### Phase A (Prompt + Quality Gate + A/B)

| File | Change |
|------|--------|
| `src/resources/prompts/feedback_agent_v2.txt` | NEW — rewritten prompt ~130 lines |
| `src/resources/prompts/feedback_agent.txt` | KEEP — retained for A/B and rollback |
| `src/agents/quality_evaluation_agent.py` | MODIFY — conditional GT block, column_coverage gate |
| `src/agents/pvmap_retry_loop.py` | MODIFY — GT placeholder, max_retries logic, prompt version |
| `src/agents/feedback_agent.py` | MODIFY — prompt version selection |
| `src/config/cli_parser.py` | MODIFY — add `--feedback-prompt-version` flag |
| `src/run_pipeline.py` | MODIFY — wire flag through (both argparsers) |
| `tests/` | NEW — GT vs non-GT quality paths, prompt version selection |

### Phase B (Set v2 as Default — after A/B)

| File | Change |
|------|--------|
| `src/config/cli_parser.py` | MODIFY — change default v1 → v2 |
| `src/run_pipeline.py` | MODIFY — change defaults |
| `tests/` | MODIFY — update default expectations |
