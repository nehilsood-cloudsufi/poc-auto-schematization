# 02 - How Is the System Structured?

This document gives you a map of the codebase. It covers the directory layout, the pipeline phases, the layered architecture, the ADK framework concepts you need to know, and the key entry points and state variables. After reading this you should be able to open any file and know roughly where it fits.

---

## Directory Tree

### `src/` -- All application code lives here

```
src/
├── agents/                    # ADK agents -- one per pipeline phase + helpers
├── config/                    # CLI argument parsing
├── state/                     # State management (DatasetInfo, DatasetRegistry)
├── infrastructure/            # Core platform services
│   ├── io/                   # File I/O, GCS integration, downloads
│   ├── logging/              # Logging configuration and utilities
│   ├── config/               # Configuration (config_map, config_flags)
│   ├── metrics/              # Counters, timers
│   └── utils/                # Aggregation utilities
├── data_commons/              # Data Commons domain modules
│   ├── api/                  # Gemini client, DC API wrapper, MCP server
│   ├── mcf/                  # MCF/TMCF parsing and generation
│   ├── schema/               # Schema generation, resolution, Schema.org vocab
│   ├── statvar/              # StatVar DCID generation
│   ├── place/                # Place resolution (name -> DCID)
│   ├── geo/                  # Geographic code lookups (alpha2, county)
│   └── codes/                # Industry/occupation codes (NAICS, SOC)
├── pipeline/                  # Pipeline-specific tools
│   ├── sampling/             # Data sampling (profiler, stratified sampler)
│   ├── schema_selection/     # Schema category selection
│   ├── validation/           # PVMAP validation + repair
│   ├── evaluation/           # Ground truth comparison
│   └── logging/              # Pipeline logging tools
├── processing/                # Data processing utilities
│   ├── mapping/              # Property-value mapping
│   ├── filtering/            # Data outlier filtering
│   ├── transformation/       # Format conversion (JSON -> CSV)
│   ├── evaluation/           # Evaluation functions
│   └── matching/             # Matching utilities
├── ui/                        # Streamlit web interface
├── tools/                     # ADK tool functions (called by LlmAgents)
└── resources/                 # Static resources
    ├── schema_examples/      # Schema examples by category (7 categories)
    ├── prompts/              # Prompt templates
    └── test_data/            # Shared test fixtures
```

### Supporting directories (project root)

```
input/                         # Dataset inputs (one folder per dataset)
output/                        # Pipeline outputs (generated PVMAPs, logs)
ground_truth/                  # Ground truth PVMAPs for evaluation (81 datasets)
tests/                         # Test suite (mirrors src/ structure)
tools/                         # Legacy tool scripts (stat_var_processor.py lives here)
docs/                          # Documentation
```

A few things worth calling out:

- `tools/` at the project root is the **legacy** tools directory. The most important file there is `stat_var_processor.py`, which is called as a **subprocess** (not imported) during validation. Do not confuse it with `src/tools/`, which contains ADK tool functions that LlmAgents can invoke.
- `input/` has a strict folder structure per dataset: `test_data/` for CSV data, `input_metadata/` for optional metadata, and `schema/` for auto-populated schema files.
- `ground_truth/` mirrors the dataset names from `input/`. Each dataset folder contains `pvmap/` and optionally `metadata/`.

---

## 5-Phase Pipeline

```
Phase 1        Phase 2         Phase 2.5            Phase 3                       Phase 5
Discovery  ->  Sampling    ->  Schema Selection ->  PVMAP Generation          ->  Evaluation
                                                    (retry loop: up to 3
                                                     attempts with feedback)
```

Each phase is implemented as an ADK agent. They run in strict sequence inside a `SequentialAgent` called the **PipelineCoordinator**.

Here is what each phase does:

1. **Discovery** -- Scans the `input/` directory. Finds the CSV data files, metadata, schema files, and ground truth for the requested dataset. Populates a `DatasetInfo` object in session state.

2. **Sampling** -- Takes the full CSV (which can be thousands or millions of rows) and produces a representative sample of 60-100 rows. This is a programmatic agent that runs a 6-step DAG: profile the data, classify columns with an LLM, build a skeleton summary, run stratified sampling, ground place names via API, and assemble a structured context document. The sample and skeleton summary are what the PVMAP generator actually sees.

3. **Schema Selection** (Phase 2.5) -- Uses an LLM to classify the dataset into one of 7 predefined schema categories (Demographics, Economy, Education, Employment, Energy, Health, School). Copies the corresponding schema example files into the dataset's `schema/` folder so the generator can reference them.

4. **PVMAP Generation** (Phase 3) -- This is the core of the system. It is a `LoopAgent` containing 10 sub-agents that run in sequence on each iteration:

   ```
   StatePreparationAgent       -- Assembles the prompt, increments attempt counter
   [StatVarDiscoveryAgent]     -- (MCP only) Pre-discovers relevant StatVars
   PVMAPGeneratorAgent         -- LLM generates the PVMAP CSV
   MetadataGenerationAgent     -- Auto-generates validation config
   [MCPSpotCheckAgent]         -- (MCP only) Quick pre-validation
   ValidationAgent             -- Runs stat_var_processor subprocess on full data
   [MCPErrorResolverAgent]     -- (MCP only) Resolves errors using DC knowledge
   QualityEvaluationAgent      -- Scores quality, escalates if acceptable/stagnant
   ConditionalFeedbackAgent    -- Builds error feedback for next attempt
   MaxRetriesCheckAgent        -- Escalates if max retries (default 2) exceeded
   ```

   The loop exits when any agent escalates: quality is acceptable, quality has stagnated across attempts, or max retries are exceeded. Agents in brackets are only present when MCP is enabled.

5. **Evaluation** (Phase 5) -- Compares the generated PVMAP against ground truth (if available). Produces diff metrics (node accuracy, PV accuracy). Skipped if no ground truth exists or `--skip-evaluation` is set.

---

## 3-Layer Architecture

The codebase is organized into three layers. Each layer only depends on layers below it, never above.

### Layer 1: Infrastructure (`src/infrastructure/`)

Platform services that have no domain knowledge. File I/O (local and GCS), logging setup, configuration parsing, counters and timers. You could copy this layer into a completely different project and it would still work.

If you need to read a file, write to GCS, or set up a logger, look here.

### Layer 2: Domain (`src/data_commons/`, `src/processing/`)

Data Commons-specific logic. This layer knows about DC vocabulary, schema types, MCF format, StatVar DCIDs, place resolution, and geographic codes. It does **not** know about the pipeline -- it provides building blocks that the pipeline calls.

Key examples:
- `src/data_commons/schema/` knows how to resolve a property name to a valid DC schema term.
- `src/data_commons/place/` knows how to turn "Argentina" into `dcid:country/ARG`.
- `src/data_commons/mcf/` knows how to parse and generate MCF files.
- `src/processing/mapping/` knows how to apply a PVMAP to transform data rows.

### Layer 3: Pipeline (`src/agents/`, `src/pipeline/`)

Orchestration logic. This layer knows about the pipeline flow: which agent runs when, how retries work, how to sample data, how to validate output, how to evaluate against ground truth. It calls into the domain and infrastructure layers to get work done.

The `src/agents/` directory contains ADK agent definitions. The `src/pipeline/` directory contains the non-agent pipeline logic (sampling algorithms, validation subprocess management, evaluation scripts).

The mental model: **Infrastructure provides the plumbing. Domain provides the DC knowledge. Pipeline wires them together into a workflow.**

---

## ADK Primer

The pipeline is built on Google's Agent Development Kit (ADK). Here are the concepts you need to know.

### SequentialAgent

Runs its sub-agents one after another, in order. When agent A finishes, agent B starts. The pipeline coordinator is a SequentialAgent:

```
DiscoveryAgent -> SamplingAgent -> SchemaSelectionAgent -> PVMAPRetryLoop -> EvaluationAgent
```

### LoopAgent

Runs its sub-agents repeatedly in a cycle. Each iteration runs all sub-agents in order. The loop continues until one of the sub-agents **escalates** (see below) or `max_iterations` is hit. The PVMAP retry loop is a LoopAgent.

### BaseAgent

A custom agent where you write your own logic. You subclass `BaseAgent` and implement `async def _run_async_impl(self, ctx)`. Most agents in this codebase are BaseAgents -- DiscoveryAgent, SamplingAgent, ValidationAgent, EvaluationAgent, etc.

### LlmAgent

An agent backed by an LLM call. You give it an instruction string (which can contain `{state_variable}` placeholders that get resolved from session state) and optionally a list of tool functions it can call. The PVMAPGeneratorAgent is an LlmAgent -- it receives the assembled prompt and generates the PVMAP CSV.

### Session state

A shared Python dictionary at `ctx.session.state` that all agents can read from and write to. This is the primary mechanism for passing data between agents. For example, the SamplingAgent writes `skeleton_summary` to state, and the StatePreparationAgent reads it when building the prompt.

State persists across loop iterations, which is how error feedback accumulates: the FeedbackAgent writes `error_feedback` at the end of iteration N, and the StatePreparationAgent reads it at the start of iteration N+1.

### EventActions.escalate

An agent can yield an event with `EventActions(escalate=True)` to break out of the enclosing LoopAgent. This is how the retry loop exits. Three agents can escalate:

- **QualityEvaluationAgent** -- escalates when quality is acceptable or when quality has stagnated (no improvement across attempts).
- **MaxRetriesCheckAgent** -- escalates when the attempt counter exceeds `max_retries`.

When an escalate happens, the LoopAgent stops immediately and control returns to the parent SequentialAgent, which moves on to the next phase (Evaluation).

---

## Entry Points

### `src/run_pipeline.py`

The CLI entry point. This is what you run from the command line. It:
1. Loads `.env` (must happen before any other imports)
2. Parses CLI arguments
3. Calls `create_pipeline_coordinator()` to build the agent tree
4. Creates an ADK `Runner` and `Session` with initial state from CLI args
5. Runs the pipeline and collects results

### `src/agents/coordinator.py`

Creates the SequentialAgent that is the top-level pipeline. The agent sequence is:

```
DiscoveryAgent -> ProgrammaticSamplingAgent -> SchemaSelectionAgent
  -> [DCQueryAgent if MCP] -> PVMAPRetryLoop -> EvaluationAgent
```

The coordinator is a pure wiring function -- it instantiates each agent and hands them to SequentialAgent. No business logic lives here.

---

## Key State Variables

These are the ~25 most important keys in the session state dictionary. When you are reading agent code and see `ctx.session.state["some_key"]`, this table tells you where it comes from and where it goes.

| Key | Set By | Used By | Type | Description |
|-----|--------|---------|------|-------------|
| `input_dir` | CLI / run_pipeline | DiscoveryAgent | str | Path to input directory |
| `output_dir` | CLI / run_pipeline | All agents | str | Path to output directory |
| `current_dataset` | DiscoveryAgent | All agents | DatasetInfo | Current dataset being processed (file paths, name, etc.) |
| `skip_sampling` | CLI | SamplingAgent | bool | Skip the sampling phase |
| `skip_schema_selection` | CLI | SchemaSelectionAgent | bool | Skip schema selection |
| `skip_evaluation` | CLI | EvaluationAgent | bool | Skip evaluation phase |
| `force_resample` | CLI | SamplingAgent | bool | Force re-run sampling even if cached |
| `skeleton_summary` | SamplingAgent | StatePrep, Generator | str | Markdown description of dataset structure (columns, types, samples) |
| `data_context` | SamplingAgent | StatePrep | dict | Structural analysis of the dataset |
| `schema_category` | SchemaSelectionAgent | StatePrep | str | Selected schema category (e.g., "Economy") |
| `schema_vocab_content` | SchemaSelectionAgent | StatePrep, Generator | str | Compressed schema vocabulary JSON |
| `property_vocabulary` | StatePrep | ValidationAgent | dict | Enum values for schema property validation |
| `populated_pvmap_prompt` | StatePrep | Generator | str | Final prompt with all placeholders filled in |
| `pvmap_output` | Generator | Validation, Eval | str | The generated PVMAP as CSV text |
| `validation_passed` | ValidationAgent | QualityEval, Feedback | bool | Whether the PVMAP passed validation |
| `validation_data_rows` | ValidationAgent | QualityEval, MaxRetries | int | Number of output data rows from validation |
| `error_feedback` | FeedbackAgent | StatePrep (next iteration) | str | Error feedback injected into next retry attempt |
| `key_match_report` | ValidationAgent | FeedbackAgent | str | Diagnostic showing which PVMAP keys matched/missed data columns |
| `pvmap_repair_changes` | ValidationAgent | FeedbackAgent | list | List of programmatic repairs made to the PVMAP before validation |
| `generation_attempt` | StatePrep | All loop agents | int | Current attempt number (0-based; 0, 1, 2 for 3 attempts) |
| `quality_score` | QualityEval | FeedbackAgent | float | Heuristic quality score for the current PVMAP |
| `best_data_rows` | MaxRetriesCheck | MaxRetriesCheck | int | Highest validation_data_rows seen across all attempts |
| `best_pvmap_csv` | MaxRetriesCheck | MaxRetriesCheck | str | PVMAP text from the best attempt (restored if final attempt is worse) |
| `use_metadata` | CLI | Generator, Validation | bool | Whether to include metadata files in prompts and validation |
| `model` | CLI | LlmAgents | str | Gemini model name (default: gemini-3.1-pro-preview) |
| `mcp_enabled` | CLI / coordinator | MCP agents | bool | Whether MCP integration is active |

The flow of state through the retry loop on a single iteration looks like this:

```
StatePrep reads: skeleton_summary, error_feedback, schema_vocab_content, generation_attempt
StatePrep writes: populated_pvmap_prompt, generation_attempt (incremented)
    |
Generator reads: populated_pvmap_prompt
Generator writes: pvmap_output
    |
ValidationAgent reads: pvmap_output, current_dataset, property_vocabulary
ValidationAgent writes: validation_passed, validation_data_rows, key_match_report, pvmap_repair_changes
    |
QualityEval reads: validation_passed, validation_data_rows
QualityEval writes: quality_score (may escalate)
    |
FeedbackAgent reads: validation_passed, key_match_report, pvmap_repair_changes
FeedbackAgent writes: error_feedback
    |
MaxRetriesCheck reads: generation_attempt, validation_data_rows, best_data_rows
MaxRetriesCheck writes: best_data_rows, best_pvmap_csv (may escalate)
```

---

## What to Read Next

- **Doc 03** -- Deep dive into the retry loop (the 10 sub-agents, how feedback works, how validation runs as a subprocess)
- **Doc 04** -- The sampling pipeline (how raw CSV becomes a 60-100 row sample with a skeleton summary)
- **Doc 05** -- The PVMAP format and prompt engineering (what a PVMAP is, how the prompt template works)
