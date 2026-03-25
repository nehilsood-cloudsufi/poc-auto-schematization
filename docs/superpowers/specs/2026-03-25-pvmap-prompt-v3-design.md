# PVMAP Prompt v3 — Clean Rewrite Design Spec

**Date:** 2026-03-25
**Author:** Nehil + Claude
**Status:** Draft
**Approach:** Clean rewrite with sandwich architecture

## Problem Statement

The current `improved_pvmap_prompt_v2.txt` (467 lines) was written when upstream context was much thinner. Since then, the programmatic sampling agent, schema selection, PVMAP skeleton generator, and MCP enrichment have been added — all providing rich, dataset-specific context that the prompt's static sections now duplicate. This wastes ~190 lines of token budget on redundant content and places critical instructions in suboptimal attention positions.

## Goals

1. **Reduce prompt size by ~50%** (467 → ~200-250 lines) — reclaim token budget for dynamic context
2. **Sandwich architecture** — place rules and output format at attention-optimal positions (top/bottom)
3. **Add processor mental model** — teach the LLM how `stat_var_processor` consumes its output
4. **Remove redundancy** — strip content already provided by upstream agents
5. **Simplify output schema** — remove unused fields (`format_detected`, `validation_notes`, `confidence`)
6. **Maintain placeholder contract** — same `{{...}}` placeholders so `_populate_prompt_template()` needs no changes

## Non-Goals

- Changing the `_populate_prompt_template()` logic or compaction strategy
- Modifying upstream agents (sampling, schema selection, skeleton generator)
- Changing the retry loop logic or feedback agent behavior (only adding prompt version selection)
- Switching from JSON to CSV output format

## Decisions (from brainstorming)

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Archetype guide | Minimal reference table (names + 1-line signatures) | skeleton_summary Section 2 already classifies columns for the specific dataset |
| Schema.org tool instructions | Remove entirely | ADK wires tools automatically; LLM sees them without explicit instructions |
| Worked examples | Keep 1 compact example (Wide format) | skeleton_summary Section 7 provides dataset-specific example; 1 golden reference suffices |
| Skeleton framing | Hybrid: lock place/time/value rows, flexible on dimensions | Mixed compliance results — tighter framing on verified rows, freedom where LLM judgment needed |
| Processor understanding | Enhanced ~25-line mental model | LLM needs causal understanding of how its output gets consumed to avoid silent row drops |
| Syntax reference | Core operators detailed, advanced as one-liners | Most datasets need only {Data}, {Number}, COLUMN:VALUE, #Format, #ignore |
| Output schema | Strip to `pvmap_rows` only | `format_detected`, `validation_notes`, `confidence` are written to state but never read downstream |
| MCP sections | Keep as separate sections | MCP is used regularly; StatVar summary and tool instructions serve different purposes |
| Prompt structure | Sandwich (rules top, context middle, syntax+output bottom) | Optimal for LLM attention — rules at top, reference data in middle, generation instructions at bottom |
| Output format | Keep JSON (Pydantic structured output) | Downstream parsing is solid; type safety and deterministic CSV conversion |

## Prompt Architecture

```
TOP LAYER (high attention — primacy)
├── 1. Role & Task (~3 lines)
├── 2. Processor Mental Model (~25 lines)
├── 3. Critical Rules (~30 lines)
└── 4. Skeleton Usage Instructions (~10 lines)

MIDDLE LAYER (reference data — looked up as needed)
├──  5. {{DATA_CONTEXT}} — skeleton_summary from sampling agent
├──  6. {{PVMAP_SKELETON}} — pre-filled baseline from column discovery
├──  7. {{DIMENSION_VALUE_REFERENCE}} — MCP enrichment hints
├──  8. {{SCHEMA_EXAMPLES}} — domain vocabulary from schema selection
├──  9. {{SAMPLED_DATA}} — stratified CSV sample
├── 10. {{METADATA_CONFIG}} — optional processor config
├── 11. {{ERROR_FEEDBACK}} — retry-specific corrections
├── 12. {{STATVAR_SUMMARY}} — discovered StatVars from DC
└── 13. {{MCP_TOOLS_INSTRUCTION}} — MCP tool usage

BOTTOM LAYER (high attention — recency)
├── 14. Syntax Reference (~25 lines)
├── 15. Archetype Reference Table (~10 lines)
├── 16. Compact Example (~20 lines)
├── 17. Guardrails (~8 lines)
├── 18. Output Format (~10 lines)
└── 19. "Generate the PVMAP now."
```

**Estimated total static content: ~140 lines** (vs 317 static lines in v2)

## Section Details

### 1. Role & Task (TOP — ~3 lines)

```
You are a Data Commons engineer. Your job: generate a Property-Value Map (PVMAP)
that transforms input CSV rows into StatVarObservations. A PVMAP is a LOOKUP TABLE —
every key must match an actual column header or cell value. You are writing translation
rules, not generating data.
```

**Removed:** 5-point column classification guide (redundant with skeleton_summary Section 2).

### 2. Processor Mental Model (TOP — ~25 lines, NEW)

Explains the 6-step processing pipeline that `stat_var_processor` applies to the PVMAP:

1. **Key matching** — case-insensitive with substring fallback; exact matches preferred
2. **Placeholder resolution** — {Data} → string, {Number} → numeric, named variables for composition
3. **Carry-forward** — left-to-right across columns; non-value rows accumulate context for value rows
4. **StatVar construction** — variableMeasured auto-built from populationType + measuredProperty + statType + constraints
5. **Output requirements** — each StatVarObservation needs: observationAbout + observationDate + value + variableMeasured
6. **Common drop reasons** — unresolvable places, unparseable dates, {Number} on non-numeric cells, key matching no column

Includes a concrete carry-forward trace example:
```
Row [USA, 2020, 330000000]:
  "USA" → observationAbout=USA (no value → carry forward)
  "2020" → observationDate=2020 (no value → carry forward)
  "330000000" → value=330M + carried {observationAbout, observationDate} → Emit 1 SVObs
```

### 3. Critical Rules (TOP — ~30 lines)

Four rules, condensed from ~50 lines to ~30:

| Rule | Key Change from v2 |
|------|---------------------|
| Rule 1: BARE IDENTIFIERS | Reduced from 6-row table to 1 inline example |
| Rule 2: KEY FIDELITY | Reworded: "Matching is case-insensitive but ambiguous keys cause wrong mappings — copy names exactly from the COLUMN REFERENCE TABLE" (aligned with processor reality while encouraging precision) |
| Rule 3: COMPLETENESS | References skeleton as completeness checklist |
| Rule 4: UNIT & SCALING | Reduced from 5-row table to 2 inline examples |

### 4. Skeleton Usage Instructions (TOP — ~10 lines)

Hybrid framing:
- **LOCKED rows** (place, time, value): Pre-verified, do NOT modify
- **OPEN rows** (dimensions, COLUMN:VALUE): Fill in DC property names, adjust values per schema
- **May ADD rows** (missing dimension values, file-level properties) but NEVER remove

### 5-13. Dynamic Context Sections (MIDDLE)

Same 9 `{{...}}` placeholders as v2. Changes:
- Reordered for logical flow: data context → skeleton → dimension ref → schema → sample → config → feedback → statvars → MCP
- Metadata section condensed from 3 instructions to 2 lines
- Error feedback section condensed from 3 instructions to 1 line
- Removed "Schema Vocabulary Compliance" sub-section (6 lines) — schema examples header is sufficient
- Removed "Schema.org Tool Usage (MANDATORY)" sub-section (24 lines) — tools are wired via ADK

### 14. Syntax Reference (BOTTOM — ~25 lines)

Core placeholders table (6 entries: {Data}, {Number}, COLUMN:VALUE, #Format, #ignore, named variables).
Place prefixes table (4 entries: geoId, country, wikidataId, nuts).
Advanced operators as one-liners (5 entries: #Regex, #Eval, #Filter, #Aggregate, #Multiply).

**Removed:** Placeholder decision tree (IF/ELIF/ELSE), #Eval restrictions paragraph, "required properties" sub-section (covered in processor mental model).

**Added:** Minimal schema.org tool hint (2-3 lines): "If schema.org vocabulary tools are available, call `lookup_schemaorg_type` for your chosen populationType and `validate_pvmap_property` for key dimension properties before generating output." This preserves proactive tool usage without the 24-line mandatory checklist.

### 15. Archetype Reference Table (BOTTOM — ~10 lines)

Minimal 5-row table: archetype name + signature + key pattern.
Includes note: "Your data's archetype is identified in the Data Context above."

**Removed:** Full archetype decision tree (IF/ELIF/ELSE), Census/Coded prefix table, Passthrough detection example, First Principles Fallback — all provided by skeleton_summary.

### 16. Compact Example (BOTTOM — ~20 lines)

Single worked example: Wide format (Country + Year + GDP + Unemployment Rate).
Shows JSON output format with carry-forward pattern, unit extraction, and StatVar property decomposition.

**Removed:** Example 2 (World Bank commodity + date composition) and Example 3 (CDC SVI census/coded with #Format).

### 17. Guardrails (BOTTOM — ~8 lines)

Same 7 NEVER rules as v2. No changes needed — these are concise and critical.

### 18. Output Format (BOTTOM — ~10 lines)

Simplified schema — only `pvmap_rows`:
```json
{
  "pvmap_rows": [
    {"key": "ColumnName", "mappings": [{"property": "propName", "value": "propValue"}, ...]}
  ]
}
```

**Removed:** `format_detected`, `validation_notes`, `confidence` fields (unused downstream).
**Removed:** "Final Verification" checklist (5 items) — covered by guardrails and processor model.

## Token Budget Impact

| Component | v2 (lines) | v3 (lines) | Savings |
|-----------|-----------|-----------|---------|
| Role & task | 12 | 3 | -9 |
| Processor model | 20 | 25 | +5 (enhanced) |
| Rules | 50 | 30 | -20 |
| Skeleton usage | 15 | 10 | -5 |
| Dynamic sections (headers/instructions) | 50 | 30 | -20 |
| Syntax reference | 58 | 25 | -33 |
| Archetype guide | 70 | 10 | -60 |
| StatVar decision tree | 20 | 0 | -20 (in skeleton_summary) |
| Examples | 65 | 20 | -45 |
| Schema.org tool instructions | 24 | 3 | -21 (minimal hint kept) |
| Schema vocab compliance | 10 | 0 | -10 |
| Guardrails | 8 | 8 | 0 |
| Output format | 65 | 10 | -55 |
| **Total static** | **~317** | **~144** | **~173 lines (-55%)** |
| **Total with placeholders** | **467** | **~233** | **~234 lines (-50%)** |

**Net token savings:** ~50% reduction in static prompt content, freeing ~10-15KB for richer dynamic context (larger skeleton_summary, more sampled data rows, fuller schema examples).

## Downstream Code Changes

**Phased approach:** Schema simplification is deferred until AFTER A/B testing validates v3. During A/B, both prompts use the existing `PVMAPOutput` schema (v3 prompt simply won't mention the extra fields, but the Pydantic schema still requires them — the LLM will produce them anyway due to `output_schema` enforcement).

### Phase A: Prompt Rewrite + A/B Testing (this spec)

#### A1. `src/resources/prompts/improved_pvmap_prompt_v3.txt`
NEW — clean rewrite prompt. The v3 output format section still shows all `PVMAPOutput` fields to match the existing schema.

#### A2. `src/agents/pvmap_retry_loop.py`
Add prompt version selection:
- Environment variable: `PVMAP_PROMPT_VERSION=v3`
- Or CLI flag: `--prompt-version v3` (if we add to cli_parser.py)
- Default: v2 (safe rollout)
- **Important:** The v3 skeleton section heading MUST be `## PVMAP Skeleton (pre-filled baseline)` to match the regex in `_populate_prompt_template()` (lines 950-957) that handles empty skeleton removal.

#### A3. `src/config/cli_parser.py`
Add `--prompt-version` flag (choices: v2, v3; default: v2).

### Phase B: Schema Cleanup (AFTER v3 is validated)

Only proceed with Phase B after A/B testing confirms v3 is at least as good as v2.

#### B1. `src/agents/pvmap_generation/schemas.py`
Remove `format_detected`, `validation_notes`, `confidence` from both `PVMAPOutput` (Pydantic model) AND `PVMAP_OUTPUT_SCHEMA` (raw JSON schema dict). Keep only `pvmap_rows`.

#### B2. `src/agents/validation_agent.py`
- Remove lines 233-235 (dead state writes for `pvmap_format_detected`, `pvmap_confidence`, `pvmap_validation_notes`)
- Update `_parse_pvmap_output()` to not expect removed fields

#### B3. `src/agents/metadata_generation_agent.py`
Same cleanup in its `_parse_pvmap_output()`.

#### B4. `src/agents/pvmap_generation/helpers.py`
Update `parse_pvmap_from_dict()` to handle the leaner schema.

#### B5. Update tests
Any tests that construct `PVMAPOutput` instances with `format_detected`/`confidence`/`validation_notes` will need updating. Run `grep -r "format_detected\|validation_notes\|confidence" tests/` to identify affected files.

## A/B Testing Plan

### Datasets (10, covering all archetypes)

| # | Dataset | Archetype | Flags |
|---|---------|-----------|-------|
| 1 | `brfss_nchs_asthma_prevalence` | Dimension/Row | default |
| 2 | `bis_bis_central_bank_policy_rate` | Tidy/Long (SDMX) | `--enable-mcp` |
| 3 | `us_urban_school_teachers` | Wide/Flat | default |
| 4 | `census_v2_sahie` | Census/Coded | `--use-metadata` |
| 5 | `world_bank_commodity_market` | Wide + date composition | default |
| 6 | `cdc_social_vulnerability_index` | Census/Coded + #Format | `--enable-mcp` |
| 7 | `india_nfhs` | Large/Wide | `--no-schema-examples` |
| 8 | `oecd_regional_education` | Tidy/Long | `--use-metadata --enable-mcp` |
| 9 | `opendataforafrica_kenya_census` | Dimension/Row | default |
| 10 | `fao_currency_and_exchange_rate` | Wide/Multi-value | `--no-schema-examples` |

### Metrics

| Metric | Description | Primary? |
|--------|-------------|----------|
| `validation_data_rows` | Number of valid StatVarObservations generated | Yes |
| `validation_success` | Pass/fail | Yes |
| Retry attempts | How many iterations needed | Secondary |
| Prompt token count | Size of populated prompt | Secondary |
| Wall-clock time | Total pipeline runtime | Secondary |

### Process

1. Run each dataset with v2 prompt (baseline): `python src/run_pipeline.py --dataset=X [flags]`
2. Run each dataset with v3 prompt (new): same command with prompt version override
3. Compare `validation_data_rows` and `validation_success` side by side
4. v3 wins if: >=8/10 datasets match or exceed v2 on `validation_data_rows` AND no single dataset regresses by more than 20%
5. Investigate any regressions before committing to v3
6. **Rollback:** If A/B shows regressions, default remains v2. v3 is iterable — fix regressions and re-test

### Output Location

- v2 results: `output/ab_test_v2/{dataset}/`
- v3 results: `output/ab_test_v3/{dataset}/`

## Risks & Mitigations

| Risk | Likelihood | Mitigation |
|------|-----------|------------|
| v3 prompt regresses on some archetypes | Medium | A/B test on 10 diverse datasets; no single dataset >20% regression allowed |
| Simplified output schema breaks downstream | Low | Phased: schema changes deferred to Phase B after v3 validated |
| Processor mental model confuses LLM | Low | Tested carry-forward explanation pattern; concrete example included |
| Removed archetype guide hurts edge cases | Low | skeleton_summary provides dataset-specific guidance; minimal table kept as fallback |
| Token savings enable context overflow in other direction | Very Low | Budget caps unchanged in `_populate_prompt_template()` |
| Schema.org tools used less proactively without instructions | Low | Minimal 2-3 line tool hint retained in syntax reference section |
| v3 skeleton heading doesn't match regex in _populate_prompt_template | Low | Heading MUST be `## PVMAP Skeleton (pre-filled baseline)` — documented in Phase A2 |

## File Changes Summary

### Phase A (Prompt Rewrite + A/B Testing)

| File | Change |
|------|--------|
| `src/resources/prompts/improved_pvmap_prompt_v3.txt` | NEW — clean rewrite prompt |
| `src/resources/prompts/improved_pvmap_prompt_v2.txt` | KEEP — retained for A/B testing and rollback |
| `src/agents/pvmap_retry_loop.py` | MODIFY — add prompt version selection |
| `src/config/cli_parser.py` | MODIFY — add --prompt-version flag |

### Phase B (Schema Cleanup — after v3 validated)

| File | Change |
|------|--------|
| `src/agents/pvmap_generation/schemas.py` | MODIFY — simplify PVMAPOutput + PVMAP_OUTPUT_SCHEMA |
| `src/agents/validation_agent.py` | MODIFY — remove dead state writes |
| `src/agents/metadata_generation_agent.py` | MODIFY — cleanup _parse_pvmap_output |
| `src/agents/pvmap_generation/helpers.py` | MODIFY — update parse_pvmap_from_dict |
| `tests/` (multiple files) | MODIFY — update PVMAPOutput test fixtures |
