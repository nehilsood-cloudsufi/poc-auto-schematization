# ADK Retry Loop - Improvements

This document tracks the improvements made to the ADK retry loop for PVMAP generation.

## Completed Improvements

### 1. Unified Feedback Agent (2026-02-09)

**Problem:** Two separate feedback paths (error feedback + quality feedback) ran independently, leading to inconsistent guidance and redundant agents in the loop.

**Solution:** Merged into single `ConditionalFeedbackAgent` in `src/agents/pvmap_retry_loop.py`:
- **Path A (Validation Failed):** Provides structural error feedback from validation subprocess output
- **Path B (Quality Low):** Provides quality-focused feedback using heuristic scores + ground truth metrics
- Single output key: `error_feedback` (removed `quality_feedback` from active paths)
- Loop sequence reduced: without MCP 7→6 agents, with MCP 9→8

**Files changed:** `pvmap_retry_loop.py`, `feedback_agent.py`, `__init__.py`

---

### 2. StatVar Analysis & Schema Context in Feedback (2026-02-10)

**Problem:** The feedback agent was "flying blind" — it lacked the schema vocabulary, skeleton summary, and schema category that the generator had, and it never analyzed the rich StatVar MCF output from validation.

| What Generator Gets | What Feedback Agent Got (Before) |
|---|---|
| Schema vocab (valid properties, DCIDs, enum values) | Nothing |
| Skeleton summary (column roles, dimension domains) | Nothing |
| Schema category (Health, Economy, etc.) | Nothing |
| — | Heuristic score breakdown (structural, not semantic) |
| — | Raw counter summary (high-level only) |

**Solution:** Four-file change to give the feedback agent domain context and semantic analysis:

#### 2a. StatVar MCF Analysis (`src/tools/validation_tool.py`)

Added `_extract_statvar_summary(output_path, max_lines=40)` function that:
- Parses `{output_path}_stat_vars.mcf` after successful validation
- Extracts per-StatVar property→value distributions
- Flags potential issues: raw strings without `dcid:` prefix, special characters ($, /, –), single-value dimensions
- Returns compact markdown summary capped at 40 lines

**Output format:**
```
## Generated StatVar Analysis (N unique StatVars)

Properties used:
- populationType: Person (count)
- measuredProperty: count (count)
- income: [12 unique values] ⚠ RAW STRING values (may need DCID mapping)

Potential Issues:
- income: 12 values contain raw strings — likely need DCID enum mappings
- income: Values contain special characters ($, –, <) — possible CSV parsing corruption
```

#### 2b. State Propagation (`src/agents/validation_agent.py`)

Added `validation_statvar_analysis` to session state after validation completes:
```python
ctx.session.state["validation_statvar_analysis"] = result.get("statvar_analysis", "")
```

#### 2c. PV-Aware Feedback Modes (`src/agents/pvmap_retry_loop.py`)

Three changes:
1. **Feedback mode detection:** Checks `quality_reject_reason` to set appropriate mode:
   - `"PV ACCURACY LOW"` — semantic focus using schema vocab + StatVar analysis
   - `"QUALITY LOW"` — structural focus on coverage, mappings, format
2. **Schema context injection:** Passes `schema_vocab_content`, `schema_category`, `skeleton_summary`, and `validation_statvar_analysis` to feedback state with placeholder escaping
3. **PV-aware ground truth section:** Different guidance based on whether PV accuracy or general quality triggered the retry

#### 2d. Feedback Agent Instruction (`src/agents/feedback_agent.py`)

Added four new sections to `FEEDBACK_AGENT_INSTRUCTION`:
- **Schema Domain Context** — category + valid properties/values vocabulary
- **Data Structure Context** — skeleton summary with column classifications
- **Generated StatVar Analysis** — MCF-parsed property distributions + issue flags
- **PV Accuracy Analysis Guidance** — cross-reference steps for schema vocab vs generated StatVars
- **Anti-regression output format** — "Rows to PRESERVE" section in feedback output

**State inputs added:** `schema_category`, `schema_vocab_content`, `skeleton_summary`, `validation_statvar_analysis`

---

### 3. Placeholder Syntax (Resolved)

**Problem:** `{Data}` and `{Number}` placeholders conflicted with ADK instruction templating.

**Solution:** `escape_pvmap_placeholders()` converts `{Data}`→`[DATA]`, `{Number}`→`[NUMBER]` before ADK processes instructions. Applied in `_prepare_feedback_state()` to all text fields injected into feedback instruction.

---

### 4. Error Feedback Propagation (Resolved)

**Problem:** Error feedback may not propagate between LoopAgent iterations.

**Solution:** `StatePreparationAgent` explicitly logs and verifies `error_feedback` presence in session state. Feedback accumulates across attempts via the ADK session state mechanism.

---

### 5. Sampling Agent Iteration Limit (Resolved)

**Problem:** Forced tool calling mode with no iteration limit could cause infinite API calls.

**Solution:** `SamplingAgentWrapper` uses `max_llm_calls` limit and timeout in the inner Runner.

---

## Failure Patterns Addressed

| Pattern | Previous Blind Spot | How Improvements Help |
|---------|--------------------|-----------------------|
| **Dimension values as raw strings** | Feedback didn't know which properties need DCIDs vs passthrough | StatVar analysis shows raw strings; schema vocab provides valid DCID vocabulary |
| **Wrong populationType / measuredProperty** | Feedback only saw heuristic scores, not which properties were wrong | Schema vocab lists valid skeletons; StatVar analysis shows what was actually generated |
| **Corrupted CSV parsing in values** | MCF output showed corruption but nobody read it | StatVar analysis parses MCF and flags values with special characters |
| **Generator regression on retry** | No guidance to preserve working rows | Anti-regression output format ("Rows to PRESERVE") |
| **Missing column role context** | Feedback didn't know which columns are place/time/dimension | Skeleton summary provides column classification from sampling analysis |

---

## Architecture: Retry Loop Agents

```
LoopAgent (max_iterations=6)
├── StatePreparationAgent    — Prepares state, logs feedback presence
├── PVMAPGenerationAgent     — Generates PVMAP with error feedback
├── ValidationAgent          — Runs stat_var_processor, extracts StatVar analysis
├── QualityEvaluationAgent   — Computes heuristic + GT metrics, sets reject reason
├── ConditionalFeedbackAgent — Unified feedback (validation-failed OR quality-low)
│   ├── Path A: Validation failed → structural error feedback
│   └── Path B: Quality low → PV-aware or structural feedback with schema context
└── MaxRetriesCheckAgent     — Escalates after max attempts
```

**Key state keys:**
- `error_feedback` — accumulated feedback for generator
- `feedback_mode` — "VALIDATION FAILED", "PV ACCURACY LOW", or "QUALITY LOW"
- `validation_counter_summary` — high-level validation metrics
- `validation_statvar_analysis` — MCF-parsed StatVar property distributions
- `quality_metrics` — heuristic scores + GT accuracy + reject reason
- `schema_vocab_content` — compressed schema vocabulary JSON
- `schema_category` — selected schema category name
- `skeleton_summary` — column classification from sampling

---

## Verification

```bash
# Unit tests (all 499+ pass)
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q

# Test StatVar extraction standalone
python -c "
from src.tools.validation_tool import _extract_statvar_summary
summary = _extract_statvar_summary('output/brfss_nchs_asthma_prevalence/processed')
print(summary)
"

# Pipeline run with feedback improvements
python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --structured-output
```
