# PVMAP Generation Pipeline — Comprehensive Architecture Guide

> Companion document for the Mermaid workflow diagrams in [`pipeline_workflow.md`](pipeline_workflow.md).

---

## Table of Contents

1. [Pipeline Overview](#1-pipeline-overview)
2. [Entry Point & CLI](#2-entry-point--cli)
3. [Phase 1: Discovery](#3-phase-1-discovery)
4. [Phase 2: Data Sampling](#4-phase-2-data-sampling)
5. [Phase 2.5: Schema Selection](#5-phase-25-schema-selection)
6. [Phase 3: PVMAP Retry Loop](#6-phase-3-pvmap-retry-loop)
   - [Step 1: StatePreparationAgent](#step-1-statepreparationagent)
   - [Step 2: StatVarDiscoveryAgent (MCP)](#step-2-statvardiscoveryagent-mcp-only)
   - [Step 3: PVMAPGeneratorAgent](#step-3-pvmapgeneratoragent)
   - [Step 4: MetadataGenerationAgent](#step-4-metadatagenerationagent)
   - [Step 5: MCPSpotCheckAgent (MCP)](#step-5-mcpspotcheckagent-mcp-only)
   - [Step 6: ValidationAgent](#step-6-validationagent)
   - [Step 7: MCPErrorResolverAgent (MCP)](#step-7-mcperrorresolveragent-mcp-only)
   - [Step 8: QualityEvaluationAgent](#step-8-qualityevaluationagent)
   - [Step 9: MaxRetriesCheckAgent](#step-9-maxretriescheckagent)
   - [Step 10: ConditionalFeedbackAgent](#step-10-conditionalfeedbackagent)
7. [Phase 5: Evaluation](#7-phase-5-evaluation)
8. [Loop Exit Conditions](#8-loop-exit-conditions)
9. [State Variable Reference](#9-state-variable-reference)
10. [Tool Reference](#10-tool-reference)
11. [MCP Integration](#11-mcp-integration)
12. [Token Budget & Compaction](#12-token-budget--compaction)
13. [Error Handling & Timeouts](#13-error-handling--timeouts)
14. [Agent Type Summary](#14-agent-type-summary)

---

## 1. Pipeline Overview

The PVMAP generation pipeline transforms raw CSV datasets into Data Commons-compatible Property-Value Maps (PVMAPs). It uses Google ADK (Agent Development Kit) to orchestrate a multi-agent system with LLM-powered generation, automated validation, and self-correcting feedback loops.

**High-level flow:**

```
CLI Entry → Discovery → Sampling → Schema Selection → [Retry Loop: Generate → Validate → Evaluate → Feedback] → Final Evaluation
```

**Key characteristics:**
- **5 phases** executed sequentially via ADK `SequentialAgent`
- **10-step retry loop** using ADK `LoopAgent` with quality-based exit
- **4 LLM-powered agents** (Gemini) for generation, sampling, schema selection, and feedback
- **10 BaseAgents** for deterministic orchestration, validation, and evaluation
- **21 tool functions** across Schema.org, sampling, validation, and MCP categories
- **Up to 3 attempts** (configurable) with accumulated error feedback

---

## 2. Entry Point & CLI

**File:** `src/run_pipeline.py`

### Input Modes

The pipeline supports three mutually exclusive input modes:

| Mode | Flag | Behavior |
|------|------|----------|
| Named dataset | `--dataset=NAME` | Process dataset from `input/NAME/` directory |
| Standalone file | `--input-file=PATH` | Process a single CSV file (no folder structure needed) |
| Auto-discovery | *(neither flag)* | Scan `input/` directory, process first found dataset |

### Key CLI Flags

| Flag | Default | Purpose |
|------|---------|---------|
| `--model` | `gemini-3-pro-preview` | Gemini model for PVMAP generation |
| `--thinking-level` | `high` | Extended thinking mode (`low`, `medium`, `high`, `none`) |
| `--max-retries` | `2` | Retry attempts after initial generation (3 total) |
| `--enable-mcp` | `False` | Enable Data Commons MCP integration |
| `--skip-sampling` | `False` | Skip agentic sampling (use existing files) |
| `--skip-schema-selection` | `False` | Skip AI schema category selection |
| `--skip-evaluation` | `False` | Skip ground truth comparison |
| `--force-resample` | `False` | Force re-run sampling even if cached |
| `--use-metadata` | `False` | Include metadata in prompt building |
| `--prompt-version` | `v2` | Prompt template version (`v1` or `v2`) |
| `--no-schema-examples` | `False` | Skip injecting schema examples into prompt |

### MCP Server Lifecycle

When `--enable-mcp` is set:
1. `MCPServerManager` starts a Data Commons MCP server on port 3000 (30s timeout)
2. The `mcp_url` is passed through to all MCP-aware agents
3. After pipeline completion (success or failure), `MCPServerManager.stop()` tears down the server

### Async Execution Model

The pipeline runs inside a dedicated asyncio event loop (not `asyncio.run()` to avoid shutdown deadlocks with MCP connections):

- **Pipeline timeout:** `(max_retries + 1) * 900s` — scales with retry count
- **Per-event stall detection:** 300s — breaks if no event received
- **Heartbeat:** Logs progress every 120s
- **Transient error retry:** Up to 2 retries with 60s backoff for 429/5xx errors

---

## 3. Phase 1: Discovery

**Agent:** `DiscoveryAgent` (BaseAgent, non-LLM)
**File:** `src/agents/discovery_agent.py`

### Purpose

Scans the filesystem to catalog all files belonging to a dataset, producing a `DatasetInfo` object that all downstream agents consume.

### Discovery Process

For a dataset named `example_dataset`, the agent scans:

```
input/example_dataset/
├── test_data/
│   ├── *_input.csv          → input_data_files
│   └── *_sampled_data.csv   → sampled_data_files (backward compat)
├── input_metadata/           → metadata_files (only if use_metadata=True)
│   └── *_metadata.csv
└── schema/                   → schema_files (auto-populated by SchemaSelectionAgent)
    ├── *.txt                 → schema_examples
    └── *.mcf                 → schema_mcf
```

Ground truth is discovered separately from `ground_truth/{dataset_name}/pvmap/`.

### DatasetInfo Fields

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | Dataset directory name |
| `path` | Path | Dataset directory path |
| `output_dir` | Path | `output/{dataset_name}/` |
| `input_data_files` | List[Path] | CSV/XLSX files from `test_data/` (excludes sampled) |
| `sampled_data_files` | List[Path] | Files matching `*_sampled_data.csv` |
| `metadata_files` | List[Path] | Metadata CSVs from `input_metadata/` |
| `schema_files` | List[Path] | Schema .txt and .mcf files |
| `use_metadata` | bool | Whether metadata is enabled |
| `standalone` | bool | True if from `--input-file` mode |

### State Outputs

| Key | Type | Description |
|-----|------|-------------|
| `current_dataset` | DatasetInfo | The dataset object used by all downstream agents |
| `datasets` | List[DatasetInfo] | All discovered datasets |
| `dataset_count` | int | Number of datasets found |

---

## 4. Phase 2: Data Sampling

**Agent:** `SamplingAgentWrapper` (BaseAgent wrapping an inner LlmAgent)
**File:** `src/agents/sampling_agent.py`

### Purpose

Uses an LLM to intelligently sample representative rows from the full dataset. Produces a `skeleton_summary` (enriched markdown) and `data_context` (structural analysis) that drive all downstream prompt construction.

### Skip/Cache Logic

```
if skip_sampling → skip entirely
elif data_context.json exists AND NOT force_resample → load from cache
else → run LLM sampling agent
```

### Inner LLM Agent

A fresh `LlmAgent` is created per invocation using `create_sampling_agent()`:

- **Model:** `SAMPLING_AGENT_MODEL` env var (default: `gemini-3-pro-preview`)
- **Tool calling mode:** `FunctionCallingConfigMode.ANY` (forces tool usage)
- **Max events:** 50 (prevents infinite loops)
- **Timeout:** `SAMPLING_AGENT_TIMEOUT` env var (default: 300s)

### Sampling Tools (5)

| Tool | Purpose |
|------|---------|
| `preview_data` | Quick file structure overview (columns, row count, dtypes) |
| `analyze_columns` | Statistical analysis — classify columns as place/time/dimension/value |
| `sample_rows` | Execute sampling strategy with intelligent row selection |
| `check_coverage` | Validate that sampled data covers key dimension combinations |
| `generate_context` | Create `DataContext` with structural analysis (MUST be called last) |

### State Outputs

| Key | Type | Description |
|-----|------|-------------|
| `skeleton_summary` | str | 9-section markdown injected as `{{DATA_CONTEXT}}` in PVMAP prompt |
| `data_context` | dict | Full structural analysis (column_roles, dimensions, coverage) |
| `sampling_success` | bool | Whether sampling completed successfully |
| `sampled_data_path` | str | Path to `agentic_sampled.csv` |

### skeleton_summary Sections

The skeleton_summary contains up to 9 sections:

1. **Dataset Overview** — Name, row/column counts, file path
2. **Column Classification** — Place, time, dimension, value columns
3. **Column Reference Table** (Section 1.5) — Exact column names with type/cardinality/samples
4. **Dimension Analysis** — Unique values per dimension column
5. **Value Columns** — Numeric ranges, units, aggregation flags
6. **StatVar Pattern** — Expected pattern like `Count_Person_Female`
7. **One-Shot Example** — Small PVMAP snippet
8. **Place/Time Analysis** — Geographic and temporal coverage
9. **Coverage Summary** — Expected combinations count

---

## 5. Phase 2.5: Schema Selection

**Agent:** `SchemaSelectionAgent` (LlmAgent, factory function)
**File:** `src/agents/schema_selection_agent.py`

### Purpose

AI-powered selection of the best schema category for the dataset from 7 predefined categories. Copies appropriate schema vocabulary files and stores compressed vocab in state for downstream PVMAP generation.

### Schema Categories

| Category | Coverage |
|----------|----------|
| Demographics | Population, age, gender, race, household |
| Economy | GDP, business establishments, revenue, trade |
| Education | Enrollment, degrees, attainment, literacy |
| Employment | Labor force, jobs, wages, unemployment |
| Energy | Power generation, consumption, renewable energy |
| Health | Disease prevalence, mortality, healthcare access |
| School | School metrics, performance, facilities |

### Schema Tools (5)

| Tool | Purpose |
|------|---------|
| `get_schema_categories()` | Returns dict of all 7 categories with descriptions |
| `copy_schema_files(category, schema_base_dir, input_dir)` | Copies .txt/.mcf files to `schema/` subfolder, returns formatted vocab |
| `read_schema_vocab(category, schema_base_dir)` | Reads compressed `schema_vocab.json` per category (0.4–5.6 KB) |
| `search_schemaorg_vocabulary(query, search_type)` | Search Schema.org types/properties by keyword |
| `lookup_schemaorg_type(type_name)` | Verify primary type exists in Schema.org hierarchy |

### State Outputs

| Key | Type | Description |
|-----|------|-------------|
| `schema_category` | str | Selected category name (e.g., "Health") |
| `schema_vocab_content` | str | Formatted compressed vocab for prompt injection |
| `property_vocabulary` | dict | Enum values for downstream validation |

### Vocab Fallback Chain

When loading schema vocabulary:
1. State variable `schema_vocab_content` (set by `copy_schema_files`)
2. Resource directory: `schema_base_dir/{category}/schema_vocab.json`
3. Full `.txt` file on disk (fallback)

---

## 6. Phase 3: PVMAP Retry Loop

**Agent:** `LoopAgent` (ADK built-in)
**File:** `src/agents/pvmap_retry_loop.py`
**Factory:** `create_pvmap_retry_loop(model, max_retries, enable_mcp, mcp_url, min_attempts, thinking_level)`

### Loop Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_iterations` | `max_retries + 1` | Total loop iterations (3 by default) |
| `max_retries` | `2` | Retry attempts after initial generation |
| `min_attempts` | `None` | Minimum attempts before allowing quality exit |

### Sub-agents Execution Order

The LoopAgent executes these sub-agents sequentially on each iteration:

```
1. StatePreparationAgent      (always)
2. StatVarDiscoveryAgent       (MCP only)
3. GeneratorWrapperAgent       (always)
4. MetadataGenerationAgent     (always)
5. MCPSpotCheckAgent           (MCP only)
6. ValidationAgent             (always)
7. MCPErrorResolverAgent       (MCP only)
8. QualityEvaluationAgent      (always)
9. MaxRetriesCheckAgent        (always)
10. ConditionalFeedbackAgent   (always)
```

Without MCP: 7 agents. With MCP: 10 agents.

---

### Step 1: StatePreparationAgent

**Type:** BaseAgent (non-LLM)

**Purpose:** Prepare session state before each generation attempt. This is the "glue" agent that reads files, populates the prompt template, and manages iteration tracking.

**Per-iteration actions:**

1. **Increment** `attempt_number` (0-indexed)
2. **On attempt 0:**
   - Initialize `quality_metrics_history = []`
   - Initialize best-attempt tracking (`best_data_rows`, `best_pvmap_csv`, etc.)
   - Discover and cache ground truth PVMAP path (`gt_pvmap_path_cached`)
   - Cache `property_vocabulary` from schema vocab JSON
3. **Read files into state:**
   - `sampled_data` — from sampled CSV file
   - `schema_examples` — from schema .txt file
   - `metadata` — from metadata CSV (if `use_metadata=True`)
4. **Populate prompt template:**
   - Load `improved_pvmap_prompt.txt` (or `_v2.txt` based on `prompt_version`)
   - Replace placeholders:
     - `{{SAMPLED_DATA}}` → sampled CSV content
     - `{{METADATA_CONFIG}}` → metadata content
     - `{{SCHEMA_EXAMPLES}}` → schema vocab content
     - `{{DATA_CONTEXT}}` → skeleton_summary
     - `{{ERROR_FEEDBACK}}` → feedback from previous attempt (empty on attempt 0)
   - Store as `populated_pvmap_prompt` in state
5. **Preserve human feedback** on attempt 0 if `human_feedback_provided=True`
6. **Compact** skeleton/vocab if token budget is tight

**Placeholder escaping:** PVMAP placeholders like `{Data}` and `{Number}` are escaped to `[DATA]` and `[NUMBER]` in state values to prevent ADK's template engine from interpreting them as state variable references.

---

### Step 2: StatVarDiscoveryAgent (MCP only)

**Type:** BaseAgent
**File:** `src/agents/statvar_discovery_agent.py`
**Skipped if:** `mcp_enabled = False`

**Purpose:** Discover relevant Data Commons Statistical Variables using MCP tools to enrich the generation prompt.

**Discovery modes:**
- **Attempt 0 (Broad):** Uses `data_context` P+M+C formula (Population + Measured Property + Constraints) to discover broad candidate StatVars
- **Attempt 1+ (Refinement):** Uses `validation_error` and `error_feedback` to drive refined queries targeting specific issues

**State outputs:**

| Key | Type | Description |
|-----|------|-------------|
| `discovered_statvars` | List[dict] | StatVar objects from MCP |
| `statvar_summary` | str | Formatted summary for prompt injection |
| `discovery_success` | bool | Whether discovery completed |
| `mcp_enrichment_context` | dict | Structured results |

---

### Step 3: PVMAPGeneratorAgent

**Type:** BaseAgent wrapper (`GeneratorWrapperAgent`) around an inner LlmAgent
**File:** `src/agents/pvmap_generator_agent.py`

**Purpose:** Generate a structured PVMAP using Gemini with output schema enforcement.

**Inner LlmAgent configuration:**
- **Model:** `PVMAP_GENERATOR_MODEL` env var (default: `gemini-3-pro-preview`)
- **Instruction:** `{populated_pvmap_prompt}` — resolved from session state at runtime
- **Output schema:** `PVMAPOutput` (Pydantic model) — guarantees valid JSON structure
- **Output key:** `pvmap_output` — stored automatically in session state
- **Include contents:** `none` — prevents conversation history accumulation across loop iterations

#### PVMAPOutput Schema

```
PVMAPOutput
├── format_detected: "pre-formatted" | "raw"
├── pvmap_rows: List[PVMAPRow]
│   └── PVMAPRow
│       ├── key: str          (column header or "Column:Value")
│       └── mappings: List[PropertyValuePair]
│           └── PropertyValuePair
│               ├── property: str  (e.g., "observationAbout", "measuredProperty")
│               └── value: str     ({Data}, {Number}, or literal identifier)
├── validation_notes: str
└── confidence: "high" | "medium" | "low"
```

#### Generator Tools

**Schema.org tools (always available, 5):**

| Tool | Purpose |
|------|---------|
| `lookup_schemaorg_type(type_name)` | Verify populationType exists in Schema.org |
| `lookup_schemaorg_property(property_name)` | Verify property names are valid |
| `search_schemaorg_vocabulary(query, search_type)` | Find properties by keyword |
| `validate_pvmap_property(property_name, population_type)` | Check property/type compatibility |
| `get_schemaorg_type_hierarchy(type_name)` | Get ancestor chain (e.g., Person → Thing) |

**Data Commons tools (MCP enabled, 3):**

| Tool | Purpose |
|------|---------|
| `resolve_place_names(place_names)` | Resolve place names to DCIDs |
| `validate_statvar_observation(variable_dcid, place_dcid)` | Check if StatVar has data for a place |
| `get_entity_type(dcid)` | Get entity type for a DCID |

**DC MCP Toolset (MCP enabled, remote):**

| Tool | Purpose |
|------|---------|
| `search_indicators` | Search for Statistical Variables |
| `get_observations` | Get observation data for a StatVar |

**State outputs:**

| Key | Type | Description |
|-----|------|-------------|
| `pvmap_output` | dict | Structured JSON matching PVMAPOutput schema |
| `pvmap_llm_result` | dict | Raw LLM call metadata for logging |

---

### Step 4: MetadataGenerationAgent

**Type:** BaseAgent with optional inner LlmAgent
**File:** `src/agents/metadata_generation_agent.py`

**Purpose:** Auto-generate a `stat_var_processor` configuration file (`output_metadata.csv`) that the validation subprocess needs.

**Two-phase approach:**

| Phase | Type | When | Action |
|-------|------|------|--------|
| Phase A | Deterministic | Always | Extract output_columns, header_rows from PVMAP + data_context |
| Phase B | LLM-assisted | Attempt 0 only | Suggest `schemaless`, `description`, `drop_statvars_without_svobs` |

**Metadata priority (3-tier):**
1. Ground truth metadata (highest — used for benchmarking)
2. User-provided metadata (if `--use-metadata`)
3. Auto-generated config (fallback)

**State outputs:**

| Key | Type | Description |
|-----|------|-------------|
| `generated_config_path` | str | Path to `output_metadata.csv` |
| `generated_config_params` | dict | Parameters written to CSV |

---

### Step 5: MCPSpotCheckAgent (MCP only)

**Type:** BaseAgent
**File:** `src/agents/mcp_spot_check_agent.py`
**Skipped if:** `mcp_enabled = False`

**Purpose:** Quick pre-validation of 1–2 discovered StatVars against live Data Commons data before the expensive subprocess validation.

**Process:**
1. Extract sample place values from `data_context`
2. Resolve first place to DCID via `resolve_place_names()`
3. Check top 2 HIGH-confidence StatVars with `validate_statvar_observation()`
4. Append warnings to state (informational only, does not block pipeline)

**Fallback:** Uses California (`geoId/06`) as default place DCID.

---

### Step 6: ValidationAgent

**Type:** BaseAgent (non-LLM, subprocess-based)
**File:** `src/agents/validation_agent.py`

**Purpose:** Convert the structured JSON output to CSV, repair common LLM key errors, and validate the PVMAP against the full dataset using the `stat_var_processor` subprocess.

#### Validation Pipeline (7 steps)

**Step 6.1 — JSON to CSV Conversion:**
- Parse `pvmap_output` dict into `PVMAPOutput` Pydantic model
- Validate structure (warnings only)
- Convert deterministically to flat CSV format
- Save to `output/{dataset}/generated_pvmap.csv`

**Step 6.2 — PVMAP Key Repair (`pvmap_repair.py`):**

Programmatic repair pipeline with cascading match levels:

| Level | Match Type | Example |
|-------|-----------|---------|
| 1 | Exact match | `State FIPS Code` → `State FIPS Code` |
| 2 | Case-insensitive + stripped | `state fips code` → `State FIPS Code` |
| 3 | Alphanumeric-only | `statefipscode` → `State FIPS Code` |
| 4 | Fuzzy match (difflib) | `State FIP Code` → `State FIPS Code` |

Fuzzy thresholds:
- Keys ≤ 15 chars: **0.85** cutoff
- Keys > 15 chars: **0.80** cutoff

Additional repairs:
- **Placeholder normalization:** `[DATA]` → `{Data}`, `[NUMBER]` → `{Number}`
- **dcid/dcs prefix stripping:** Remove double-prefixing artifacts
- **Hallucinated key cleanup:** Duplicate segments, appended values, index suffixes
- **#ignore conflict resolution:** Remove #ignore rows that conflict with COLUMN:VALUE mappings

**Step 6.3 — Pre-validation (fast fail):**
- Check if PVMAP keys match input headers (≤ **30%** match → FAIL)
- Check placeholder syntax
- Validate enum values against `property_vocabulary` (warnings)
- If pre-validation fails → skip expensive subprocess, return error immediately

**Step 6.4 — stat_var_processor subprocess:**

```bash
python tools/stat_var_processor.py \
  --input_data={FULL_input_file}     # Full dataset, NOT sampled
  --pv_map={generated_pvmap.csv}     # Generated PVMAP
  --config_file={metadata_file}      # Optional metadata
  --generate_statvar_name=True
  --output_path={output_dir}/processed
```

- **Timeout:** 300 seconds (5 minutes)
- **PYTHONPATH:** Must include project root and `src/`
- **Success criteria:** `returncode == 0` AND `processed.csv` has data rows (more than just header)

**Step 6.5 — Key match report generation:**
- Compare PVMAP keys against input file headers
- Report: matched, auto-fixed, unmatched, unmapped headers
- Calculate match rate (unique columns)
- Stored as `key_match_report` for feedback agent

**Step 6.6 — Best attempt tracking:**
- Track best attempt by: validation success → data_rows count
- Update `best_data_rows`, `best_pvmap_csv`, `best_attempt_number` if current is better

**Step 6.7 — Artifact saving:**
- Save attempt response JSON to `generated_response/attempt_N.md`
- Append to LLM call log (`llm_calls.jsonl`)
- Update `generation_notes.md` with attempt status

#### State Outputs

| Key | Type | Description |
|-----|------|-------------|
| `validation_success` | bool | Whether validation passed |
| `validation_passed` | bool | Flag for QualityEvaluationAgent |
| `validation_error` | str | Error message if failed |
| `validation_data_rows` | int | Number of output data rows |
| `validation_counter_summary` | str | Processing metrics from subprocess |
| `pvmap_csv` | str | Final CSV content (after repair) |
| `pvmap_path` | str | Path to saved PVMAP file |
| `key_match_report` | str | Column matching analysis |
| `pvmap_repair_changes` | List[str] | Description of auto-repairs applied |
| `best_data_rows` | int | Highest data row count across attempts |
| `best_pvmap_csv` | str | PVMAP CSV from best attempt |
| `best_attempt_number` | int | Attempt number that produced best result |

---

### Step 7: MCPErrorResolverAgent (MCP only)

**Type:** BaseAgent
**File:** `src/agents/pvmap_retry_loop.py`
**Skipped if:** `mcp_enabled = False` OR `validation_passed = True`

**Purpose:** Use MCP tools to resolve specific validation errors by querying Data Commons for correct StatVar DCIDs, property names, or place identifiers.

---

### Step 8: QualityEvaluationAgent

**Type:** BaseAgent with `_min_attempts` PrivateAttr
**File:** `src/agents/quality_evaluation_agent.py`

**Purpose:** Evaluate the quality of a validated PVMAP using heuristics and (optionally) ground truth comparison. Decides whether to exit the loop or continue with feedback.

**Precondition:** Only runs if `validation_passed = True`. If validation failed, skips directly to feedback.

#### Quality Scoring

**Heuristic score (0–100, always computed):**

| Component | Weight | Measures |
|-----------|--------|----------|
| Row coverage | ~25% | % of sampled data rows successfully mapped |
| Property coverage | ~25% | % of expected properties present in PVMAP rows |
| Column coverage | ~25% | % of input columns referenced in PVMAP keys |
| Format score | ~25% | CSV structure quality (headers, delimiters, syntax) |

**Ground truth PV accuracy (0–100%, computed if GT available):**
- Compare generated PVMAP against cached ground truth
- Extract ONLY numeric scores (`gt_node_accuracy`, `gt_pv_accuracy`)
- Ground truth content is NEVER leaked into state (prevents content contamination)

#### Quality Decision Logic

```
IF heuristic_score >= 70 OR gt_pv_accuracy >= 30%:
    quality_acceptable = True → ESCALATE (exit loop)
    exit_reason = "quality_met"

ELIF improvement_from_previous < 10% of previous score:
    quality_stagnant = True → ESCALATE (exit loop)
    exit_reason = "stagnant"

ELSE:
    Continue to MaxRetriesCheck → Feedback
```

#### Stagnation Detection

- **Threshold:** < 10% improvement from previous attempt (minimum absolute delta: 0.5)
- **Metric used for comparison:**
  - If rejected by PV accuracy → check PV accuracy delta
  - If rejected by heuristic → check heuristic score delta
- **Purpose:** Prevents infinite loops when feedback isn't driving improvement

#### Min Attempts Enforcement

When `min_attempts` is configured:
- If `attempt < min_attempts - 1`: force `quality_acceptable = False` and `quality_stagnant = False`
- Forces the loop to continue even if quality thresholds are met early
- Used by Streamlit UI for "run at least N attempts" workflows

#### State Outputs

| Key | Type | Description |
|-----|------|-------------|
| `quality_metrics` | dict | Heuristic + GT scores for current attempt |
| `quality_acceptable` | bool | Whether quality thresholds are met |
| `quality_stagnant` | bool | Whether improvement has stalled |
| `quality_diff_summary` | str | Summary of quality issues for feedback |
| `quality_metrics_history` | List[dict] | Accumulated metrics across all attempts |
| `exit_reason` | str | `"quality_met"`, `"stagnant"`, or `None` |
| `generation_success` | bool | Set to True on escalation if quality acceptable |

---

### Step 9: MaxRetriesCheckAgent

**Type:** BaseAgent
**File:** `src/agents/pvmap_retry_loop.py`

**Purpose:** Check if the maximum retry count has been reached. If so, restore the best attempt from history and escalate to exit the loop.

#### Best Attempt Selection Criteria

When max retries are exceeded, the agent selects the best historical attempt using this priority:

| Priority | Criterion | Rationale |
|----------|-----------|-----------|
| 1 | Valid > Invalid | Prefer an attempt that passed validation |
| 2 | Higher PV accuracy | Ground truth accuracy (if available) |
| 3 | Higher heuristic score | Quality score as secondary signal |
| 4 | More data rows | Tiebreaker — more output rows = more coverage |

#### Restoration Process

1. Identify best attempt from tracking state
2. Restore `pvmap_csv` and `pvmap_path` from best attempt
3. Re-run validation to regenerate `processed.csv` (so output files are consistent)
4. Mark `generation_success = True` if best attempt was valid
5. Update `generation_notes.md` with final status
6. Set `exit_reason = "max_retries"` or `"best_attempt_restored"`
7. **ESCALATE** → exit the LoopAgent

If the current attempt IS the best → no restoration needed, just escalate.

---

### Step 10: ConditionalFeedbackAgent

**Type:** BaseAgent wrapping an inner `FeedbackAgent` LlmAgent
**File:** `src/agents/pvmap_retry_loop.py` (wrapper) + `src/agents/feedback_agent.py` (inner LLM)

**Purpose:** Generate targeted feedback for the next generation attempt. Routes between error feedback and quality feedback based on current state.

#### Feedback Paths

| Path | Condition | Input Context |
|------|-----------|---------------|
| **Path A: Error** | `validation_passed = False` | `validation_error`, `key_match_report`, `validation_counter_summary` |
| **Path B: Quality** | `validation_passed = True` AND `quality_acceptable = False` | `quality_diff_summary`, `quality_metrics`, `validation_counter_summary` |
| **Skip** | `quality_acceptable = True` OR `quality_stagnant = True` | No feedback generated |

#### Inner FeedbackAgent (LlmAgent)

- **Model:** `FEEDBACK_AGENT_MODEL` env var (default: `gemini-2.5-flash`)
- **Output key:** `error_feedback` (stored in state for next iteration)
- **Max output tokens:** 1500
- **Include contents:** `none` (no history accumulation)

#### Context Processing Pipeline

Before passing context to the feedback LLM:

1. **Save originals** — Preserve full `skeleton_summary`, `schema_vocab_content`, `sampled_data`
2. **Compact for token budget** — Apply aggressive compaction (50–75% reduction):
   - Drop skeleton sections 6 (StatVar pattern), 7 (one-shot), 9 (coverage)
   - Compact section 1.5 (samples 5→2) and 4 (values 15→5)
   - Drop vocab representative examples, compact enum values (first 3 + count)
3. **Escape placeholders** — Convert `{Data}` → `[DATA]`, `{Number}` → `[NUMBER]` to prevent ADK template collisions
4. **Cap per-variable sizes** — Truncate oversized state values
5. **Run feedback LLM** — Generate actionable guidance
6. **Restore originals** — Put full context back for next generation iteration

#### Feedback Guardrails

The feedback agent is instructed to NEVER suggest:
- Removing `observationAbout`, `observationDate`, or `value` mappings
- Hardcoding dates or places as literals
- Replacing decomposed properties with `variableMeasured` DCID shortcuts

#### State Output

| Key | Type | Description |
|-----|------|-------------|
| `error_feedback` | str | Actionable guidance injected into next attempt's prompt |
| `feedback_mode` | str | `"error"` or `"quality"` — context for logging |

---

## 7. Phase 5: Evaluation

**Agent:** `EvaluationAgent` (BaseAgent, non-LLM)
**File:** `src/agents/evaluation_agent.py`

### Purpose

Compare the final generated PVMAP against ground truth files to calculate accuracy metrics. This is a post-loop assessment — it does NOT influence the retry loop.

### Ground Truth Discovery (3-tier precedence)

| Tier | Source | Flag |
|------|--------|------|
| 1 (highest) | Explicit PVMAP file | `--ground-truth-pvmap=PATH` |
| 2 | Directory search | `--ground-truth-dir=DIR` |
| 3 (default) | Repository | `ground_truth/{dataset_name}/pvmap/` |

### Comparison Process

1. Find all matching ground truth PVMAP files
2. Run `pvmap_diff` against each
3. Select best match by node accuracy
4. Calculate node accuracy and PV accuracy
5. Generate detailed diff report

### Output Files

```
output/{dataset_name}/eval_results/
├── diff_results.json    # Structured metrics (node_accuracy, pv_accuracy, counters)
└── diff.txt             # Human-readable diff report
```

### State Outputs

| Key | Type | Description |
|-----|------|-------------|
| `eval_metrics` | dict | `{node_accuracy, pv_accuracy, nodes_matched, nodes_ground_truth, ...}` |
| `best_ground_truth_pvmap` | str | Filename of best-matching GT PVMAP |
| `evaluation_passed` | bool | Whether evaluation completed successfully |

---

## 8. Loop Exit Conditions

The LoopAgent (`PVMAPRetryLoop`) exits when any of these conditions trigger:

| Condition | Agent | `exit_reason` | `generation_success` |
|-----------|-------|---------------|---------------------|
| Quality thresholds met | QualityEvaluationAgent | `"quality_met"` | `True` |
| Quality stagnant | QualityEvaluationAgent | `"stagnant"` | `True` (if valid) |
| Max retries exceeded | MaxRetriesCheckAgent | `"max_retries"` | Depends on best attempt |
| Best attempt restored | MaxRetriesCheckAgent | `"best_attempt_restored"` | `True` (if best was valid) |
| Loop counter exhausted | LoopAgent (fallback) | N/A | Depends on last attempt |

**Escalation mechanism:** Agents set `EventActions(escalate=True)` in their yielded events to break out of the LoopAgent.

---

## 9. State Variable Reference

### Dataset & Config

| Key | Set By | Used By | Description |
|-----|--------|---------|-------------|
| `current_dataset` | Discovery | All agents | DatasetInfo object |
| `model` | CLI | Generator | Gemini model name |
| `prompt_version` | CLI | StatePrep | `"v1"` or `"v2"` |
| `use_metadata` | CLI | Discovery, Validation | Metadata flag |

### Sampling & Schema

| Key | Set By | Used By | Description |
|-----|--------|---------|-------------|
| `skeleton_summary` | Sampling | StatePrep, Generator, Feedback | 9-section markdown |
| `data_context` | Sampling | SchemaSelection, Quality, Eval | Structural analysis dict |
| `schema_category` | SchemaSelection | StatePrep | e.g., "Health" |
| `schema_vocab_content` | SchemaSelection | StatePrep, Generator | Compressed vocab |
| `property_vocabulary` | StatePrep (cached) | Validation | Enum values for validation |

### Generation

| Key | Set By | Used By | Description |
|-----|--------|---------|-------------|
| `populated_pvmap_prompt` | StatePrep | Generator | Full prompt text |
| `pvmap_output` | Generator | Validation, MetadataGen | JSON dict (PVMAPOutput) |
| `pvmap_csv` | Validation | Quality, Feedback, Eval | CSV string |
| `pvmap_path` | Validation | Eval, post-pipeline | File path |
| `attempt_number` | StatePrep | All loop agents | 0-indexed counter |

### Validation & Quality

| Key | Set By | Used By | Description |
|-----|--------|---------|-------------|
| `validation_passed` | Validation | Quality, Feedback | Pass/fail flag |
| `validation_error` | Validation | Feedback | Error message |
| `validation_data_rows` | Validation | Quality, MaxRetries | Output row count |
| `validation_counter_summary` | Validation | Feedback | Processing metrics |
| `key_match_report` | Validation | Feedback | Column match analysis |
| `quality_metrics` | Quality | Feedback | Heuristic + GT scores |
| `quality_acceptable` | Quality | Feedback, MaxRetries | Threshold met flag |
| `quality_stagnant` | Quality | Feedback, MaxRetries | Stagnation flag |
| `quality_metrics_history` | Quality | Quality (next iter) | Accumulated metrics |

### Feedback Loop

| Key | Set By | Used By | Description |
|-----|--------|---------|-------------|
| `error_feedback` | Feedback | StatePrep (next iter) | Guidance for next attempt |
| `feedback_mode` | Feedback | Logging | `"error"` or `"quality"` |

### Best Attempt Tracking

| Key | Set By | Used By | Description |
|-----|--------|---------|-------------|
| `best_data_rows` | Validation | MaxRetries | Highest row count |
| `best_pvmap_csv` | Validation | MaxRetries | Best PVMAP content |
| `best_attempt_number` | Validation | MaxRetries | Best attempt index |
| `best_validation_passed` | Validation | MaxRetries | Best attempt validity |
| `best_heuristic_score` | Quality | MaxRetries | Best heuristic score |
| `best_pv_accuracy` | Quality | MaxRetries | Best GT accuracy |

### Exit & Results

| Key | Set By | Used By | Description |
|-----|--------|---------|-------------|
| `exit_reason` | Quality/MaxRetries | Post-pipeline | Why loop exited |
| `generation_success` | Quality/MaxRetries | Post-pipeline | Final success flag |
| `eval_metrics` | Evaluation | Post-pipeline | Final diff metrics |

### MCP (Optional)

| Key | Set By | Used By | Description |
|-----|--------|---------|-------------|
| `mcp_enabled` | CLI | All MCP agents | MCP flag |
| `mcp_url` | CLI | Generator, StatVarDiscovery | MCP server URL |
| `discovered_statvars` | StatVarDiscovery | MCPSpotCheck | Discovered StatVars |
| `statvar_summary` | StatVarDiscovery | Generator | Formatted for prompt |

---

## 10. Tool Reference

### Sampling Tools (5)

| Tool | File | Returns |
|------|------|---------|
| `preview_data(file_path)` | `src/tools/sampling_tools.py` | File structure overview |
| `analyze_columns(file_path)` | `src/tools/sampling_tools.py` | Column statistics + classification |
| `sample_rows(file_path, strategy_json)` | `src/tools/sampling_tools.py` | Sampled CSV rows |
| `check_coverage(file_path)` | `src/tools/sampling_tools.py` | Coverage validation report |
| `generate_context(file_path, output_dir)` | `src/tools/sampling_tools.py` | DataContext JSON + skeleton_summary |

### Schema Selection Tools (3)

| Tool | File | Returns |
|------|------|---------|
| `get_schema_categories()` | `src/tools/schema_tools.py` | Dict of 7 categories + descriptions |
| `copy_schema_files(category, base_dir, input_dir)` | `src/tools/schema_tools.py` | `{success, files_copied, schema_vocab_content}` |
| `read_schema_vocab(category, base_dir)` | `src/tools/schema_tools.py` | `{success, vocab, formatted}` |

### Schema.org Tools (5)

| Tool | File | Returns |
|------|------|---------|
| `lookup_schemaorg_type(type_name)` | `src/tools/schemaorg_tools.py` | `{success, data: {parent, description, properties}}` |
| `lookup_schemaorg_property(property_name)` | `src/tools/schemaorg_tools.py` | `{success, data: {domain, range, description}}` |
| `search_schemaorg_vocabulary(query, search_type)` | `src/tools/schemaorg_tools.py` | `{success, data: {types, properties}}` |
| `validate_pvmap_property(property_name, population_type)` | `src/tools/schemaorg_tools.py` | `{success, data: {compatible, notes}}` |
| `get_schemaorg_type_hierarchy(type_name)` | `src/tools/schemaorg_tools.py` | `{success, data: {type, hierarchy}}` |

### Data Commons Tools (3, MCP enabled)

| Tool | File | Returns |
|------|------|---------|
| `resolve_place_names(place_names)` | `src/tools/dc_tools.py` | Place name → DCID mapping |
| `validate_statvar_observation(variable_dcid, place_dcid)` | `src/tools/dc_tools.py` | Observation existence check |
| `get_entity_type(dcid)` | `src/tools/dc_tools.py` | Entity type string |

### Validation Tools (3, internal)

| Tool | File | Purpose |
|------|------|---------|
| `repair_pvmap(pvmap_csv, input_path)` | `src/pipeline/validation/pvmap_repair.py` | Cascading key repair |
| `pre_validate_pvmap(pvmap_csv, input_path, vocab)` | `src/pipeline/validation/pvmap_repair.py` | Fast structural checks |
| `stat_var_processor` (subprocess) | `tools/stat_var_processor.py` | Full dataset validation |

### DC MCP Remote Tools (2, MCP server)

| Tool | Source | Purpose |
|------|--------|---------|
| `search_indicators` | DC MCP Server | Search for Statistical Variables |
| `get_observations` | DC MCP Server | Get observation data for a StatVar |

---

## 11. MCP Integration

### Architecture

MCP (Model Context Protocol) provides live Data Commons API access for StatVar discovery and validation. When enabled, three additional agents are inserted into the retry loop.

### MCP Agents

| Agent | Position in Loop | Purpose |
|-------|-----------------|---------|
| `StatVarDiscoveryAgent` | After StatePrep | Discover candidate StatVars |
| `MCPSpotCheckAgent` | After MetadataGen | Quick pre-validation spot-check |
| `MCPErrorResolverAgent` | After Validation | Resolve validation errors |

### MCP Tools on Generator

When MCP is enabled, the PVMAPGeneratorAgent gets additional tools:
- 3 local DC tools (`resolve_place_names`, `validate_statvar_observation`, `get_entity_type`)
- 1 remote MCP toolset (with `search_indicators`, `get_observations`)

### Loop Counts

| MCP Status | Agents per Iteration | Total Tools Available |
|------------|---------------------|----------------------|
| Disabled | 7 | 16 (5 schema.org + 5 sampling + 3 schema + 3 validation) |
| Enabled | 10 | 21 (+ 3 DC local + 2 DC remote) |

---

## 12. Token Budget & Compaction

### Why Compaction?

The feedback agent's prompt includes the full PVMAP context (skeleton_summary, schema_vocab, sampled_data, error details). Without compaction, this can exceed Gemini's token limits.

### Compaction Strategies

**Skeleton compaction for feedback (aggressive, 60–70% reduction):**

| Action | Sections Affected |
|--------|-------------------|
| DROP entirely | 6 (StatVar pattern), 7 (one-shot example), 9 (coverage) |
| COMPACT | 1.5 (samples 5→2), 4 (dimension values 15→5) |
| KEEP | All other sections (dataset overview, column classification, etc.) |

**Skeleton compaction for generator (moderate, 30–40% reduction):**
- Only triggered when skeleton > 40 KB
- Section 1.5: samples 5→3
- Section 4: values 15→8

**Vocab compaction for feedback (aggressive, 50–75% reduction):**

| Action | Content |
|--------|---------|
| DROP | Representative examples (generation-only) |
| COMPACT | Enum values (keep first 3 + count) |
| KEEP | StatVar skeletons, Schema.org context |

**Vocab compaction for generator (moderate):**
- Only triggered when vocab > 15 KB
- Enum values: 30→10

---

## 13. Error Handling & Timeouts

### Timeout Hierarchy

| Level | Timeout | Purpose |
|-------|---------|---------|
| Pipeline-level | `(max_retries + 1) × 900s` | Total pipeline safety net |
| Per-event stall | 300s | Detect hung agent |
| stat_var_processor subprocess | 300s | Validation subprocess |
| Runner close | 30s | MCP connection teardown |
| Generator close | 15s | Async generator cleanup |
| Sampling agent | `SAMPLING_AGENT_TIMEOUT` (300s) | Sampling LLM timeout |
| MCP server start | 30s | Server startup |
| Heartbeat | 120s interval | Progress logging |

### Transient Error Handling

API errors (429, 500, 502, 503, 504) trigger:
- Up to 2 retries at the pipeline level
- 60-second backoff between retries
- Events cleared on retry

### Placeholder Escaping

**Critical ADK behavior:** Any `{...}` pattern in LlmAgent instruction strings is interpreted as a state variable reference. PVMAP placeholders like `{Data}` and `{Number}` must be escaped:

| In state values | In instruction text | In feedback text |
|-----------------|--------------------|--------------------|
| `{Data}` → escaped | `[DATA]` always | `[DATA]` always |
| `{Number}` → escaped | `[NUMBER]` always | `[NUMBER]` always |

---

## 14. Agent Type Summary

### BaseAgents (10) — Non-LLM, Deterministic

| Agent | File | Key Responsibility |
|-------|------|--------------------|
| DiscoveryAgent | `discovery_agent.py` | Filesystem scanning |
| SamplingAgentWrapper | `sampling_agent.py` | Cache/skip logic, inner LLM orchestration |
| StatePreparationAgent | `pvmap_retry_loop.py` | Prompt population, state management |
| GeneratorWrapperAgent | `pvmap_retry_loop.py` | Generator lifecycle management |
| MetadataGenerationAgent | `metadata_generation_agent.py` | Config file generation |
| ValidationAgent | `validation_agent.py` | CSV conversion, repair, subprocess |
| QualityEvaluationAgent | `quality_evaluation_agent.py` | Scoring, stagnation, escalation |
| MaxRetriesCheckAgent | `pvmap_retry_loop.py` | Retry limits, best attempt restoration |
| ConditionalFeedbackAgent | `pvmap_retry_loop.py` | Feedback routing, context compaction |
| EvaluationAgent | `evaluation_agent.py` | Ground truth comparison |

### LlmAgents (4) — Gemini-Powered

| Agent | File | Model | Output Key |
|-------|------|-------|------------|
| SamplingAgent (inner) | `sampling_agent.py` | `SAMPLING_AGENT_MODEL` | N/A (via tools) |
| SchemaSelectionAgent | `schema_selection_agent.py` | `SCHEMA_SELECTION_MODEL` | `schema_category` |
| PVMAPGenerator | `pvmap_generator_agent.py` | `PVMAP_GENERATOR_MODEL` | `pvmap_output` |
| FeedbackAgent (inner) | `feedback_agent.py` | `FEEDBACK_AGENT_MODEL` | `error_feedback` |

### MCP Agents (3) — Optional

| Agent | File | Condition |
|-------|------|-----------|
| StatVarDiscoveryAgent | `statvar_discovery_agent.py` | `mcp_enabled=True` |
| MCPSpotCheckAgent | `mcp_spot_check_agent.py` | `mcp_enabled=True` |
| MCPErrorResolverAgent | `pvmap_retry_loop.py` | `mcp_enabled=True` AND `validation_passed=False` |
