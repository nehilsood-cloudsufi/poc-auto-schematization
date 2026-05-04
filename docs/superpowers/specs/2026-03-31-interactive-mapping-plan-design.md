# Interactive Mapping Plan: Plan → Approve → Generate

**Date:** 2026-03-31  
**Status:** Draft  
**Phase:** 1 (CLI), Phase 2 (Streamlit UI — future)

## Problem

The current pipeline runs end-to-end without user input between upload and final output. Users see results only after generation completes. This means:
- No visibility into *why* the system chose specific mappings
- No ability to course-correct before expensive generation+validation cycles
- Feedback is only corrective (post-hoc), never proactive (pre-generation)

## Solution

Insert a **MappingPlanAgent** and **Approval Gate** between schema selection and PVMAP generation. The plan provides rich per-column reasoning. The user reviews, optionally edits, and approves before generation proceeds.

## Updated Pipeline Flow

```
[0] ProgrammaticSamplingAgent
[1] SchemaSelectionAgent
[NEW-1] StatVarDiscoveryAgent     ← MCP broad discovery (per-column DC lookup)
[NEW-2] MappingPlanAgent          ← generates plan with reasoning + DC findings
[NEW-3] Approval Gate             ← user reviews/edits, approves
[2] PVMAPRetryLoop                ← receives approved plan as constraint
    [2.0] StatePreparationAgent (reads approved_mapping_plan)
    [2.1] PVMAPGeneratorAgent
    [2.2] MetadataGenerationAgent
    [2.3] ValidationAgent
    [2.4] QualityEvaluationAgent
    [2.5] ConditionalFeedbackAgent (respects approved plan)
    [2.6] MaxRetriesCheckAgent
[3] EvaluationAgent
[4] LLMJudgeAgent
```

**Note:** The existing `StatVarDiscoveryAgent` inside the retry loop (attempt 1+ refinement) is **removed**. All MCP discovery now happens once, pre-plan. The retry loop still has access to `statvar_summary` from state for generation, but no longer re-queries MCP per attempt.

## Component 0: Pre-Plan StatVar Discovery

**File:** Reuses existing `src/agents/statvar_discovery_agent.py`  
**Type:** ADK `BaseAgent`

The existing `StatVarDiscoveryAgent` is **moved out of the retry loop** and placed before the MappingPlanAgent. It runs once in broad discovery mode (attempt=0) to find existing Data Commons StatVars relevant to the dataset.

### Per-Column DC Queries

The discovery agent is enhanced to run **per-column queries** in addition to the existing broad dataset query:

1. **Broad query** (existing): Search terms from dataset name, population type, dimension domains
2. **Per-column queries** (new): For each column identified as a measure or dimension by the profiler, query DC for matching StatVars or properties. Uses column name + sample values as search terms.

Example: For a column named `ASTHMA_PREVALENCE` with values like `12.5, 8.3, 15.1`:
- Query: "Search for statistical variables related to: asthma prevalence, percent"
- Result: `Percent_Person_WithAsthma`, `Count_Person_Asthma`

### Enhanced State Output

| State Key | Content |
|-----------|---------|
| `statvar_summary` | Existing: text summary of all discovered StatVars |
| `discovered_statvars` | Existing: list of StatVar dicts |
| `per_column_dc_matches` | **New**: dict mapping column names → list of DC matches with relevance scores |
| `mcp_enrichment_context` | Existing: structured discovery metadata |

The `per_column_dc_matches` structure:
```python
{
    "ASTHMA_PREV": [
        {"dcid": "Percent_Person_WithAsthma", "name": "Asthma Prevalence", "relevance": "high",
         "properties": ["measuredProperty: prevalence", "populationType: Person", "healthCondition: Asthma"]},
    ],
    "REF_AREA": [
        {"dcid": "country/USA", "name": "United States", "relevance": "high",
         "note": "Place identifier — use geoId or countryAlpha2Code"}
    ],
    "OBS_VALUE": []  # No DC match needed — this is a raw measure column
}
```

### MCP-Disabled Behavior

When `--enable-mcp` is not set, the discovery agent sets all outputs to empty. The plan agent still runs — it just omits the "DC Match" fields from the plan. No failure, just less information.

## Component 1: MappingPlanAgent

**File:** `src/agents/mapping_plan_agent.py`  
**Type:** ADK `LlmAgent`

### Inputs (from state)

| State Key | Source |
|-----------|--------|
| `skeleton_summary` | ProgrammaticSamplingAgent — column profiles with types, cardinality, samples, semantic types |
| `schema_category` | SchemaSelectionAgent — selected category (Health, Economy, etc.) |
| `schema_vocab_content` | SchemaSelectionAgent — compressed vocab JSON for the category |
| `sampled_data` | ProgrammaticSamplingAgent — representative sample rows |
| `statvar_summary` | StatVarDiscoveryAgent — broad DC discovery summary |
| `per_column_dc_matches` | StatVarDiscoveryAgent — per-column DC StatVar/property matches |
| `discovered_statvars` | StatVarDiscoveryAgent — full list of discovered StatVar dicts |

### Output

- **State key:** `mapping_plan` — the full markdown plan string
- **Disk:** Saved to `output/{dataset}/mapping_plan.md`

### Plan Structure (Markdown)

```markdown
# Mapping Plan: {dataset_name}

## Dataset Understanding
- **Format:** Wide/Flat/Dimension-row (archetype classification)
- **Observation grain:** One row = one observation per [entity] per [time period]
- **Key insight:** [1-2 sentences about what this data represents]

## Data Commons Findings
- **Existing StatVars found:** [list of relevant DCIDs with names]
- **Reuse recommendation:** [which existing StatVar patterns to follow]
- **Novel mappings needed:** [columns with no existing DC match — new StatVars required]

## Column Mappings

### Column: `{column_name}`
- **Role:** observationAbout | observationDate | measure | dimension | metadata | ignored
- **Mapping:** `{property} → {expression}`
- **Reason:** [Why this role was chosen]
- **Evidence:** [Data statistics: unique count, type, sample values, range]
- **Alternatives rejected:** [Other roles considered and why they don't fit]
- **Schema.org:** [Relevant schema.org type/property if applicable]
- **DC Match:** [Closest existing StatVar or "None — novel mapping needed"]
- **DC Properties:** [If match found: property decomposition from existing StatVar to reuse]

[Repeated for each column]

## Properties to Generate
- [Static properties like measurementMethod, unit, etc.]
- [Properties inferred from DC matches]

## Global Notes
- [Dataset-wide observations, warnings, special handling notes]
```

### Prompt Design

The agent instruction template lives at `src/resources/prompts/mapping_plan_prompt.txt`. It tells the LLM to:
1. Classify the dataset archetype (wide, flat, dimension-row)
2. Analyze each column systematically using profiler data
3. Incorporate DC discovery findings — reuse existing StatVar property patterns where matches are found
4. Explain reasoning with evidence from the data
5. Flag ambiguous columns where user input is especially valuable
6. Use `[DATA]`, `[NUMBER]` placeholder syntax (not `[Data]`, `[Number]` — ADK resolves `{...}` as state variables)

## Component 2: Approval Gate (CLI)

**File:** `src/pipeline/approval_gate.py`  
**Type:** Plain Python function (not an ADK agent — agents can't do interactive stdin)

### Interactive Mode (default)

When the pipeline reaches the approval gate:

1. Prints the plan to stdout with formatting
2. Saves it to `output/{dataset}/mapping_plan.md`
3. Prompts:
   ```
   Mapping plan saved to output/{dataset}/mapping_plan.md
   
   [A]pprove  |  [E]dit (opens in $EDITOR)  |  [R]eject (abort pipeline)
   > 
   ```
4. **Approve** — pipeline continues, plan stored in state as `approved_mapping_plan`
5. **Edit** — opens `mapping_plan.md` in `$EDITOR` (falls back to `vi`), waits for save/close, reads back the modified file, continues
6. **Reject** — pipeline exits cleanly with a message

### Non-Interactive Mode (`--plan-only` / `--from-plan`)

```bash
# Step 1: Generate plan only, exit
python src/run_pipeline.py --dataset=bis_central_bank_policy_rate --plan-only

# User reviews/edits output/bis_central_bank_policy_rate/mapping_plan.md at their leisure

# Step 2: Run generation from approved plan
python src/run_pipeline.py --dataset=bis_central_bank_policy_rate \
  --from-plan=output/bis_central_bank_policy_rate/mapping_plan.md
```

### CLI Flags

| Flag | Behavior |
|------|----------|
| (default) | Interactive: generate plan → prompt user → continue on approve |
| `--plan-only` | Generate plan, save to disk, exit |
| `--from-plan=PATH` | Skip sampling + schema + planning, load plan from file, go straight to generation |
| `--auto-approve` | Generate plan, save to disk, continue without prompting |

### `--from-plan` Behavior

When user provides a pre-edited plan:
1. Sampling **still runs** (needed for validation on full data)
2. Schema selection **still runs** (needed for vocab)
3. Planning agent is **skipped** — file loaded directly into `approved_mapping_plan` state
4. Approval gate is **skipped**
5. Retry loop runs normally with the plan as context

## Component 3: Plan → Generator Integration

### State Flow

The `StatePreparationAgent` ([2.0] in retry loop) already assembles the full prompt from state variables. It is extended to include the approved plan.

**New state key:** `approved_mapping_plan` — the markdown string (original or user-edited)

### Prompt Injection

The `populated_pvmap_prompt` template gets a new section inserted **before** schema vocab and sampled data (highest priority):

```
## APPROVED MAPPING PLAN
The user has reviewed and approved the following mapping plan.
You MUST follow these decisions. Only deviate if a mapping is
structurally impossible (and explain why in a comment).

{approved_mapping_plan}
```

### Escaping

The `{approved_mapping_plan}` reference in the prompt template is a legitimate ADK state variable. However, the plan content itself may contain `{...}` patterns (e.g., column names like `{Year}`). The plan content must be escaped before storing in state — replace `{` with `{{` and `}` with `}}` — consistent with how `pvmap_retry_loop.py` already escapes `key_match_report`.

### Feedback Agent Update

The `ConditionalFeedbackAgent` instruction is updated to:
- See the `approved_mapping_plan` in its context
- Prefer corrections that align with the approved plan
- Only suggest deviating from the plan if the approved mapping is provably incorrect

## File Layout

### New Files

```
src/agents/mapping_plan_agent.py              — LlmAgent that generates the plan
src/pipeline/approval_gate.py                 — Interactive CLI approval (stdin, $EDITOR)
src/resources/prompts/mapping_plan_prompt.txt  — Plan agent instruction template
tests/agents/test_mapping_plan_agent.py
tests/pipeline/test_approval_gate.py
```

### Modified Files

```
src/run_pipeline.py                            — new flags, orchestrate plan→approve→generate, move discovery pre-loop
src/agents/statvar_discovery_agent.py           — add per-column DC queries, new per_column_dc_matches output
src/agents/pvmap_retry_loop.py                 — StatePreparationAgent reads approved_mapping_plan; remove in-loop discovery
src/agents/feedback_agent.py                   — instruction updated to respect approved plan
src/resources/prompts/improved_pvmap_prompt.txt — new APPROVED MAPPING PLAN section
```

## Testing Strategy

- **Unit: plan agent** — Mock LLM response, verify markdown has all required sections (Dataset Understanding, Column Mappings with all 6 fields per column, Properties, Global Notes)
- **Unit: approval gate** — Test approve/reject/edit paths with mocked stdin and `$EDITOR` subprocess
- **Integration: plan generation** — Run plan agent on a real dataset (e.g., BIS), verify the plan mentions all columns from skeleton_summary
- **End-to-end: two-stage** — `--plan-only` produces a file, `--from-plan` consumes it and generates a PVMAP. Verify the PVMAP respects the plan's mapping decisions.
- **Regression** — Existing tests unchanged. `--auto-approve` is the default in test harness so no existing flow breaks.

## Phasing

- **Phase 1 (this PR):** MappingPlanAgent + approval gate + CLI flags + plan→generator integration + tests
- **Phase 2 (future PR):** Streamlit UI with inline plan editing and approval step

## Design Decisions

1. **Dedicated agent over two-pass generator** — Clean separation lets us tune plan quality independently of generation quality.
2. **Markdown over JSON/YAML** — The PVMAP generator is an LLM; it consumes markdown naturally. Markdown is also the friendliest format for human editing in `$EDITOR`.
3. **Approval gate outside ADK** — ADK agents can't do interactive stdin. A plain Python function between the agent graph sections is the simplest approach.
4. **Plan as highest-priority context** — Placed before schema vocab in the prompt so the LLM treats user-approved decisions as constraints, not suggestions.
5. **Full edit flexibility** — The plan file is the user's to reshape however they want. The LLM consumes whatever markdown it receives.
6. **MCP discovery moved pre-loop** — Discovery runs once before planning instead of per-attempt inside the retry loop. This gives the plan agent DC context and avoids redundant MCP queries during retries. The retry loop still has `statvar_summary` in state for generation.
7. **Per-column DC queries** — Instead of only a broad dataset-level query, we query DC for each column individually. This gives specific, actionable matches (e.g., "this column matches `Percent_Person_WithAsthma`") rather than generic discovery results.
