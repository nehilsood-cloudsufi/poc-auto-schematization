# Phase 2: Data Sampling — Deep Dive

> Part of the [Pipeline Architecture Guide](pipeline_architecture.md). See [Workflow Diagrams](pipeline_workflow.md) for visual reference.

---

## Table of Contents

1. [Overview](#1-overview)
2. [Why Sampling Matters](#2-why-sampling-matters)
3. [Architecture](#3-architecture)
4. [ProgrammaticSamplingAgent](#4-programmaticsamplingagent)
5. [The 5 Sampling Tools](#5-the-5-sampling-tools)
6. [DataContext & DataContextGenerator](#6-datacontext--datacontextgenerator)
7. [The skeleton_summary — 9-Section Markdown](#7-the-skeleton_summary--9-section-markdown)
8. [Sampling Strategies](#8-sampling-strategies)
9. [Column Classification](#9-column-classification)
10. [Cache & Skip Logic](#10-cache--skip-logic)
11. [Edge Cases](#11-edge-cases)
12. [State Contract](#12-state-contract)
13. [Configuration](#13-configuration)
14. [File Outputs](#14-file-outputs)
15. [How Downstream Agents Use Sampling Output](#15-how-downstream-agents-use-sampling-output)

---

## 1. Overview

Phase 2 uses a **code-orchestrated programmatic agent** (`ProgrammaticSamplingAgent`) to intelligently sample a representative subset of the full dataset and produce a rich structural analysis. The agent follows a deterministic 6-step DAG with only 2 LLM calls (semantic analysis + skeleton mapping), making it 2-5x faster than the previous LLM-orchestrated approach while producing richer skeletons.

**Key principle:** Pandas provides statistical **evidence**. The LLM makes semantic **decisions** (only where needed).

**Key files:**

| File | Purpose |
|------|---------|
| `src/agents/sampling_agent_v2.py` | `ProgrammaticSamplingAgent` (BaseAgent) — 6-step DAG |
| `src/tools/sampling_tools.py` | 5 tool functions (preview, analyze, sample, coverage, context) — shared infrastructure |
| `src/pipeline/sampling/profiler.py` | Dataset profiling (pandas-based) |
| `src/pipeline/sampling/stratified_sampler.py` | Stratified sampling with dimension coverage guarantee |
| `src/pipeline/sampling/context_assembler.py` | Skeleton summary assembly from analysis results |
| `src/pipeline/sampling/data_context.py` | `DataContext` dataclass + `DataContextGenerator` |
| `src/pipeline/sampling/sampling_interface.py` | Standalone `sample_dataset()` API (non-ADK usage) |
| `src/agents/sampling/schemas.py` | Pydantic schemas for LLM structured output |
| `src/agents/sampling/semantic_analyzer.py` | LLM-based semantic column analysis |
| `src/agents/sampling/skeleton_mapper.py` | LLM-based skeleton mapping |

---

## 2. Why Sampling Matters

The full input datasets can have thousands or millions of rows, far too large to pass into an LLM prompt. The sampling phase solves two problems:

1. **Row reduction** — Produce a representative 60–100 row sample (`agentic_sampled.csv`) that fits in the LLM context window
2. **Structural understanding** — Produce a `skeleton_summary` (markdown) and `data_context` (dict) that tell the PVMAP generator:
   - Which columns are places, times, dimensions, and values
   - What unique dimension values exist
   - How dimensions combine to form unique Statistical Variables
   - What the StatVar naming pattern looks like
   - Whether the data is pre-formatted DC data (passthrough mapping)

### The Data Commons Uniqueness Rule

```
StatVarObservation = Place + Time + StatVar
StatVar = MeasurementType + PopulationType + Dimensions (constraints)
```

If two rows share the same Place + Time but have different values, there **must** be a dimension column differentiating them (gender, age, race, etc.). The sampling agent's primary job is to identify these dimensions.

---

## 3. Architecture

The `ProgrammaticSamplingAgent` follows a deterministic 6-step DAG:

```
┌─────────────────────────────────────────────────────────────────┐
│              ProgrammaticSamplingAgent (BaseAgent)               │
│                                                                 │
│  Step 1: Profile (pandas)                                       │
│     └─ DatasetProfile with column stats, metadata rows          │
│                                                                 │
│  Step 2: Semantic Analysis (LLM call #1)                        │
│     └─ Column roles, dimension identification                   │
│                                                                 │
│  Step 3: Skeleton Mapping (LLM call #2)                         │
│     └─ StatVar pattern, population type, measurement type       │
│                                                                 │
│  Step 4: Stratified Sampling (pandas)                           │
│     └─ Dimension coverage guarantee, 60-100 rows                │
│                                                                 │
│  Step 5: StatVar Grounding (API, optional)                      │
│     └─ Validate StatVar DCIDs against Data Commons              │
│                                                                 │
│  Step 6: Context Assembly (template)                            │
│     └─ skeleton_summary markdown + data_context.json            │
└─────────────────────────────────────────────────────────────────┘
```

**Key advantages over the previous LLM-orchestrated approach:**
- Only 2 LLM calls (vs. 5+ tool-calling rounds)
- 2-5x faster (avg 3.6x across 7 test datasets)
- Deterministic profiling and sampling steps
- Richer skeletons with confidence scores, semantic types, functional dependencies

---

## 4. ProgrammaticSamplingAgent

**File:** `src/agents/sampling_agent_v2.py`, class `ProgrammaticSamplingAgent(BaseAgent)`

The agent's `_run_async_impl` follows the 6-step DAG described above. Each step is a separate method call, with results passed forward through the pipeline.

### Cache & Skip Logic

```
skip_sampling=True?
  ├─ YES → Set sampling_success=True, skeleton_summary="" → return
  └─ NO → Check cache
              │
              data_context.json exists AND !force_resample?
              ├─ YES → Load from cache → populate state → return
              └─ NO → Run 6-step DAG
```

---

## 5. The 5 Sampling Tools

**File:** `src/tools/sampling_tools.py`

These tools are **shared infrastructure** used by both the programmatic pipeline modules (`profiler.py`, `stratified_sampler.py`, `sampling_interface.py`) and the standalone `sample_dataset()` API. Each returns a dict with `success: bool`, result data, and `error: str | None`.

| Tool | Purpose |
|------|---------|
| `preview_data` | Quick overview of file structure (headers, row count, sample rows) |
| `analyze_columns` | Statistical evidence per column (cardinality, dtype, place/date detection) |
| `sample_rows` | Execute sampling strategy (head, random, stratified, fixed_pivot) |
| `check_coverage` | Validate dimension hypothesis by testing uniqueness |
| `generate_context` | Generate DataContext and skeleton_summary |

---

## 6. DataContext & DataContextGenerator

**File:** `src/pipeline/sampling/data_context.py`

See full documentation in the DataContext section of the architecture guide.

---

## 7. The skeleton_summary — 9-Section Markdown

The `skeleton_summary` is the **primary output** of Phase 2 — a structured markdown document injected into the PVMAP generation prompt as `{{DATA_CONTEXT}}`. It contains 9 sections:

1. **TOPOLOGY & STRUCTURE** — Dataset format, row/column counts, exact column headers
2. **COLUMN REFERENCE TABLE** — Exact column names with type/cardinality/samples for copy-paste
3. **COLUMN CLASSIFICATIONS** — Role assignments (place, time, dimension, value, metadata)
4. **ANCHOR ANALYSIS** — Geography and time column details with DCID resolution hints
5. **DIMENSION DEEP DIVE** — All unique values per dimension with aggregate warnings
6. **MEASUREMENT & UNITS** — Value columns, stat type, unit, population type
7. **STATVAR PATTERN** — P+M+C formula
8. **ONE-SHOT PVMAP EXAMPLE** — Template-generated starting point
9. **PRE-FORMATTED DC DETECTION** — Passthrough mapping detection

---

## 8. Sampling Strategies

| Strategy | When | Algorithm |
|----------|------|-----------|
| `head` | Wide data, no clear dimensions | First N rows |
| `random` | Large dataset, no clear strata | Random sample with seed=42 |
| `stratified` | Clear dimension columns | Two-pass: coverage guarantee + stratified fill |
| `fixed_pivot` | Tall data with dimensions | Fix anchor (place+time), vary dimensions |

**Dimension Coverage Guarantee** (stratified mode):
- Pass 1: Select one row per unique value per dimension column
- Pass 2: Fill remaining budget with stratified group sampling
- Ensures all dimension values are represented in the sample

---

## 9. Column Classification

The LLM classifies every column into one of 5 roles:

| Role | Meaning | Maps to in PVMAP |
|------|---------|-----------------|
| `place` | Geographic identifier | `observationAbout` |
| `time` | Temporal identifier | `observationDate` |
| `dimension` | Categorical constraint defining StatVar uniqueness | StatVar properties |
| `value` | Numeric measurement | `value` |
| `metadata` | Descriptive context (source, unit, notes) | Ignored |

---

## 10. Cache & Skip Logic

### Cache Location

```
output/{dataset_name}/
├── agentic_sampled.csv     # Sampled CSV (60-100 rows)
└── data_context.json       # Full context + skeleton_summary
```

### CLI Flags

| Flag | Description |
|------|-------------|
| `--skip-sampling` | Skip Phase 2 entirely (use existing files) |
| `--force-resample` | Force re-run even if cached context exists |

---

## 11. Edge Cases

### Metadata Row Detection

Rows where >50% of mostly-numeric columns have non-numeric values (unit descriptors, footnotes) are detected and excluded from sampling. Their content is surfaced in Section 11 DATA WARNINGS of the skeleton_summary.

### Pre-formatted Data Commons Data

If columns include `observationAbout`, `observationDate`, `variableMeasured`, `value`, the data is flagged as pre-formatted and passthrough mapping is suggested.

### Very Large Files

Profiling samples at most 500 rows for analysis, making it efficient even on million-row files.

---

## 12. State Contract

### Inputs (Read from Session State)

| Key | Type | Required | Description |
|-----|------|----------|-------------|
| `current_dataset` | DatasetInfo | Yes | Dataset with `input_data_files`, `output_dir` |
| `skip_sampling` | bool | No | If True, skip entirely (default: False) |
| `force_resample` | bool | No | If True, bypass cache (default: False) |

### Outputs (Written to Session State)

| Key | Type | Always Set | Description |
|-----|------|-----------|-------------|
| `skeleton_summary` | str | Yes | 9-section markdown (empty if skipped) |
| `data_context` | dict | Yes | Full structural analysis (empty dict if skipped) |
| `sampling_success` | bool | Yes | Whether sampling completed |
| `sampled_data_path` | str | On success | Path to `agentic_sampled.csv` |
| `context_file_path` | str | On success | Path to `data_context.json` |
| `error` | str | On failure | Error message |

---

## 13. Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `SAMPLING_AGENT_MODEL` | `gemini-3.1-pro-preview` | LLM model for sampling |

---

## 14. File Outputs

Phase 2 produces two files in the dataset's output directory:

### agentic_sampled.csv

A representative sample of the full dataset (60–100 rows).

### data_context.json

Complete structural analysis (serves as both output and cache).

---

## 15. How Downstream Agents Use Sampling Output

| Agent | Uses | How |
|-------|------|-----|
| **SchemaSelectionAgent** | `skeleton_summary` | Analyzes dataset description to select schema category |
| **StatePreparationAgent** | `skeleton_summary`, `sampled_data_path` | Reads sampled CSV into state; injects skeleton into prompt |
| **PVMAPGeneratorAgent** | `populated_pvmap_prompt` | Uses skeleton's classifications, dimension values, and example |
| **ValidationAgent** | `data_context` | Column stats inform `key_match_report` accuracy |
| **QualityEvaluationAgent** | `data_context` | Uses `total_combinations` and `coverage_percent` for scoring |
| **EvaluationAgent** | `data_context` | Extracts dimensions, combinations, StatVar pattern |
| **ConditionalFeedbackAgent** | `skeleton_summary` | Includes compacted skeleton in feedback context |
| **StatVarDiscoveryAgent** (MCP) | `data_context` | Uses P+M+C formula for MCP StatVar queries |
