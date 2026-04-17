# Batch Benchmark: 49 Datasets with Per-Agent Telemetry

**Date:** 2026-04-17
**Status:** Design approved, implementation pending
**Owner:** nehil

---

## 1. Goal

Run the auto-schematization pipeline over **49 datasets** (derived from `analysis/Gemini_vs_Claude_Comparison.md`) using a fixed pipeline configuration, and produce a unified report that contains:

- **Accuracy metrics per dataset:** PV accuracy, Node accuracy, Node coverage (plus ground-truth raw counts).
- **Token utilization per dataset:** broken down per agent and per individual LLM call, split into prompt / thinking / response / total. Report USD cost using per-model pricing.
- **Wall-time per dataset:** broken down by pipeline phase (discovery / sampling / schema selection / PVMAP generation / validation / evaluation).
- **Dataset complexity signals:** raw row count (primary), cleaned row count, generated observation count, column count, file size MB, skeleton bytes.
- **Run metadata:** attempt count, schema category, sampling strategy, best-attempt fallback flag, output StatVar count, git SHA, timestamps.
- **Correlations:** scatter plots of `raw_rows vs total_tokens` and `raw_rows vs total_duration_s`.
- **Comparison:** delta vs. the Gemini 3 Pro column in the source comparison doc.

Failed datasets (process crash / timeout only) are captured in `failed.json` for selective rerun.

---

## 2. Dataset selection

49 datasets, selected from the PV Accuracy table in `analysis/Gemini_vs_Claude_Comparison.md`:

- **44 datasets** where PV accuracy > 0 in *any* of the three model columns (Gemini Base, Claude CLI, Gemini 3 Pro).
- **5 borderline-zero datasets** (all three columns = 0) taken in document order to fill to 49: `brazil_visdata_brazil_rural_development_program`, `child_birth`, `crdc_import_crdc_harassment_or_bullying`, `crdc_instructional_wifi_devices`, `fao_currency_and_exchange_rate`.

Final list stored at `config/batch_49.txt`, one dataset name per line.

All 49 datasets have both `input/{ds}/` and `ground_truth/{ds}/` directories. Verified via `scripts/check_datasets.py` (one-liner).

---

## 3. Pipeline configuration (fixed across all 49 runs)

| Area | Value |
|---|---|
| `--model` | `gemini-3.1-pro-preview` |
| `--thinking-level` | `high` |
| `--enable-mcp` | on (DC MCP only; Schema.org MCP server is deprecated, but Schema.org ADK function tools — `search_schemaorg_vocabulary`, `lookup_schemaorg_type`, `validate_pvmap_property` — remain wired into `SchemaSelectionAgent` and `PVMAPGenerator`, reading the local `src/resources/schema_org/` cache. `SchemaOrgEnrichmentAgent` also runs as a sub-agent on every pipeline run.) |
| `--prompt-version` | `v3` |
| `--feedback-prompt-version` | `v1` |
| `--use-metadata` | off |
| `--use-llm-judge` | off |
| Retry loop | default (`max_retries=2`, `min_attempts=1`, up to 3 attempts per dataset) |
| Sampling mode | programmatic (default) |
| Per-agent models | pipeline defaults (SchemaSelection → `gemini-2.5-pro`, StatVarDiscovery → `gemini-3-flash-preview`, others → `gemini-3.1-pro-preview`). Per-call log records which model each agent used. |
| First-pass caching | off (no `--skip-sampling`, no `--skip-schema-selection`) |
| Rerun-failed caching | on (orchestrator adds `--skip-sampling --skip-schema-selection` when `--resume-failed`) |
| Concurrency | 3 workers, each with its own MCP port (3000 / 3001 / 3002) |
| Per-dataset timeout | 45 min (2700 s) |

**Failure definition:** process crash (exit ≠ 0) or timeout. Validation failures, `max_retries_exceeded`, and low accuracy are *results*, not failures — they are recorded in the normal per-dataset record, not in `failed.json`.

---

## 4. Architecture

Three loosely-coupled components communicating via the filesystem.

```
┌────────────────────────────────────────────────────────────────────┐
│  1. Batch Orchestrator (scripts/batch_benchmark.py)                │
│     • Input: dataset list, pipeline args, concurrency, timeout     │
│     • Owns: subprocess pool, checkpoint, timeout, port allocation, │
│       failed-list capture                                          │
│     • Output: spawns pipeline subprocesses, writes checkpoint.jsonl│
└──────────────────────────────┬─────────────────────────────────────┘
                               │ one subprocess per dataset
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  2. Pipeline with telemetry (src/run_pipeline.py + new plugin)     │
│     • LLMTelemetryPlugin  → llm_calls.jsonl (every LLM call)       │
│     • phase_timer ctx-mgr → phase_timings.json                     │
│     • run_manifest writer → run_manifest.json                      │
│     • NO behavioral change: same prompts, agents, retry logic      │
└──────────────────────────────┬─────────────────────────────────────┘
                               │ writes artifacts under runs/{ds}/
                               ▼
┌────────────────────────────────────────────────────────────────────┐
│  3. Aggregator (scripts/batch_aggregate.py)                        │
│     • Reads: llm_calls.jsonl, phase_timings.json, run_manifest,    │
│       all_metrics.json, generated_pvmap.csv, dataset profile,      │
│       input CSV for raw row count and file size                    │
│     • Applies: pricing table → $USD, roll-up per agent             │
│     • Output: batch_results.json, batch_summary.csv, report.md,    │
│       scatter_tokens_vs_rows.png, scatter_duration_vs_rows.png,    │
│       failed.json                                                  │
└────────────────────────────────────────────────────────────────────┘
```

### Why three components

- **Orchestrator** knows nothing about metrics — just runs processes and catches failures.
- **Pipeline** knows nothing about batching — just emits richer artifacts.
- **Aggregator** knows nothing about running — just reads the filesystem and produces reports.

Each can be tested and re-run independently. If aggregation has a bug, we do not re-run the 49.

---

## 5. Component details

### 5.1 Batch Orchestrator (`scripts/batch_benchmark.py`)

**CLI:**
```bash
python scripts/batch_benchmark.py \
  --datasets-file config/batch_49.txt \
  --output-dir output/batch_runs/2026-04-17_comparison \
  --concurrency 3 \
  --timeout 2700 \
  --mcp-port-base 3000 \
  --pipeline-args "--model=gemini-3.1-pro-preview --thinking-level=high --enable-mcp --prompt-version=v3 --feedback-prompt-version=v1" \
  [--resume-failed path/to/prev/failed.json] \
  [--limit N]
```

**Responsibilities:**
- Read dataset list (or subset from `--limit` for dry runs; or `failed.json` for rerun).
- Maintain a worker pool of 3 via `concurrent.futures.ThreadPoolExecutor` (threads, not processes — actual isolation comes from each `subprocess.run` call).
- For each dataset, assign `MCP_PORT = mcp-port-base + (worker_id mod concurrency)`. Port-busy detection: bump by 10 and retry once.
- Run `python src/run_pipeline.py --dataset {ds} --output-dir {out}/runs/{ds} {pipeline_args}` with `env["MCP_PORT"]` set.
- Capture stdout+stderr to `runs/{ds}/pipeline.log`.
- On `subprocess.TimeoutExpired`, send SIGKILL and record status = `timeout`.
- On non-zero exit, record status = `exit_{code}`.
- Append each completed dataset's status row to `checkpoint.jsonl` under an `fcntl.flock` file lock.
- At end, write `failed.json` (datasets with status ≠ `ok`).

**What it does NOT do:** no metrics parsing, no LLM calls, no accuracy evaluation. Pure process runner.

**Resumability:** if the orchestrator is killed mid-run, the next invocation reads `checkpoint.jsonl` and skips already-completed datasets (matched by dataset name).

### 5.2 Pipeline telemetry extensions

Three narrow additions to the pipeline. **No prompt or retry-logic changes.**

#### 5.2.1 `LLMTelemetryPlugin` (extends / replaces `ArtifactLoggingPlugin`)

Modify `src/utils/artifact_plugin.py` in place: rename the class to `LLMTelemetryPlugin`, keep the old `ArtifactLoggingPlugin` name as an alias for backward compatibility, and extend its responsibilities as described below.

- Remove the `_GENERATOR_AGENT_NAMES` filter so the plugin fires for every agent's LLM call.
- Use `before_model_callback` / `after_model_callback` to capture start time, model, prompt tokens, thinking tokens, response tokens, total tokens, duration.
- Append one JSON line per call to `output/{dataset}/llm_calls.jsonl`:

```json
{
  "call_id": "uuid",
  "timestamp": "2026-04-17T12:34:56.789",
  "agent": "SchemaSelectionAgent",
  "model": "gemini-2.5-pro",
  "prompt_tokens": 12345,
  "thoughts_tokens": 890,
  "response_tokens": 2345,
  "total_tokens": 15580,
  "duration_ms": 8421,
  "temperature": null,
  "max_output_tokens": null,
  "prompt_bytes": 52340,
  "response_preview": "first 200 chars of response"
}
```

- **Preserve** the existing special-case behavior for the `Generator` / `PVMAPGenerator` agent: continue stashing `pvmap_llm_result` in session state so `ValidationAgent.save_attempt_response()` keeps working.
- Append-only JSONL chosen for: thread-safe appends, stream parsing, easy `wc -l`, easy `jq` filtering.

**Verification during implementation:** confirm that `ProgrammaticSamplingAgent`'s nested LlmAgents (`semantic_analyzer`, `skeleton_mapper`) trigger the before/after callbacks. If they do not, instrument those two agents directly.

#### 5.2.2 `phase_timer` context manager

Located at `src/utils/phase_timer.py`. Invoked around each pipeline phase in `src/run_pipeline.py`:

```python
with phase_timer("sampling"):
    await coordinator.run_sampling(...)
```

Writes `output/{dataset}/phase_timings.json`:
```json
{
  "discovery":        {"start": "...", "end": "...", "duration_s": 2.1},
  "sampling":         {"start": "...", "end": "...", "duration_s": 57.3},
  "schema_selection": {"start": "...", "end": "...", "duration_s": 14.8},
  "pvmap_generation": {"start": "...", "end": "...", "duration_s": 142.6},
  "validation":       {"start": "...", "end": "...", "duration_s": 301.2},
  "evaluation":       {"start": "...", "end": "...", "duration_s": 5.4},
  "total":            {"start": "...", "end": "...", "duration_s": 523.4}
}
```

Writes atomically on process exit via `atexit` so partial runs still produce what they got.

#### 5.2.3 Run manifest

At pipeline start, write `output/{dataset}/run_manifest.json`:
```json
{
  "dataset": "bis_bis_central_bank_policy_rate",
  "git_sha": "e2e010a...",
  "git_branch": "release/nehil/v0.2.0-deploy",
  "git_dirty": false,
  "started_at": "2026-04-17T12:34:56",
  "cli_args": {"...full parsed args..."},
  "pipeline_config": {
    "model": "gemini-3.1-pro-preview",
    "thinking_level": "high",
    "enable_mcp": true,
    "prompt_version": "v3",
    "feedback_prompt_version": "v1",
    "use_metadata": false
  },
  "worker_id": 0,
  "mcp_port": 3000
}
```

#### 5.2.4 MCP call counts (best-effort)

If DC MCP calls are already counted per-agent in the existing code, surface those counts in the aggregated output. If they are not, **skip** — the user confirmed this is not critical.

### 5.3 Aggregator (`scripts/batch_aggregate.py`)

**CLI:**
```bash
python scripts/batch_aggregate.py \
  --runs-dir output/batch_runs/2026-04-17_comparison/runs \
  --output-dir output/batch_runs/2026-04-17_comparison \
  --pricing-file config/gemini_pricing.json \
  --baseline-doc analysis/Gemini_vs_Claude_Comparison.md
```

**Inputs per dataset** (read from `runs/{dataset}/`):
- `llm_calls.jsonl` — every LLM call
- `phase_timings.json` — wall-time per phase
- `run_manifest.json` — config + git SHA + worker info
- `all_metrics.json` — existing evaluation output (PV accuracy, node accuracy, raw counts)
- `generated_pvmap.csv` — for output StatVar count
- `generation_notes.md` — for attempt count and best-attempt flag
- `dataset_profile.json` (or skeleton) — for cleaned row count, column count, sampling strategy, skeleton bytes, schema category
- Original `input/{ds}/test_data/*.csv` — for raw row count and file size MB

**Per-dataset record** (one entry per dataset in `batch_results.json`):

```json
{
  "dataset": "bis_bis_central_bank_policy_rate",
  "status": "passed",
  "complexity": {
    "raw_rows":           12453,
    "cleaned_rows":       12450,
    "observation_rows":   98211,
    "columns":            14,
    "file_size_mb":        1.87,
    "skeleton_bytes":     6421
  },
  "accuracy": {
    "pv_accuracy":    36.4,
    "node_accuracy":  14.3,
    "node_coverage": 114.3,
    "pvs_matched":   12, "pvs_modified":    18, "pvs_deleted":     3,
    "nodes_matched":  2, "nodes_gt":        14, "nodes_generated":16,
    "delta_pv_vs_doc_gemini3pro":   0.0,
    "delta_node_vs_doc_gemini3pro": 0.0
  },
  "tokens_total":   {"prompt": 345678, "thoughts": 54321, "response": 23456, "total": 423455},
  "tokens_by_agent": {
    "SamplingAgent":        {"model": "gemini-3.1-pro-preview", "calls": 2, "prompt": "...", "thoughts": "...", "response": "...", "total": "...", "duration_ms": 57000, "cost_usd": 0.42},
    "SchemaSelectionAgent": {"model": "gemini-2.5-pro",         "calls": 1, "..."},
    "PVMAPGenerator":       {"model": "gemini-3.1-pro-preview", "calls": 3, "..."},
    "FeedbackAgent":        {"model": "gemini-3.1-pro-preview", "calls": 2, "..."}
  },
  "cost_usd": {"total": 1.87, "by_agent": {"...":"..."}, "pricing_version": "gemini-2026-04", "is_estimate": true},
  "timing_seconds": {
    "discovery": 2.1, "sampling": 57.3, "schema_selection": 14.8,
    "pvmap_generation": 142.6, "validation": 301.2, "evaluation": 5.4, "total": 523.4
  },
  "run_meta": {
    "attempt_count": 3, "best_attempt_used": true,
    "schema_category": "Economy", "sampling_strategy": "stratified",
    "output_statvar_count": 16, "prompt_bytes_generator": 52340,
    "worker_id": 0, "mcp_port": 3000,
    "git_sha": "e2e010a", "started_at": "2026-04-17T12:34:56", "ended_at": "2026-04-17T12:43:39"
  },
  "pipeline_log":    "runs/bis_bis_central_bank_policy_rate/pipeline.log",
  "generated_pvmap": "runs/bis_bis_central_bank_policy_rate/generated_pvmap.csv"
}
```

**Outputs:**
1. `batch_results.json` — array of 49 records (source of truth).
2. `batch_summary.csv` — one row per dataset, flat columns, one column per agent for tokens and cost. Ready for pandas / Google Sheets.
3. `report.md` — Markdown report with:
   - Header: run date, git SHA, pipeline CLI args, pricing table (with estimate flag), grand totals.
   - Summary stats table (averages across 49, totals, Δ vs. doc).
   - Per-dataset table: `dataset | raw_rows | pv_acc | Δ_pv | node_acc | Δ_node | total_tokens | total_s | attempts | status`.
   - Per-agent aggregate table across all 49 (which agent consumed the most tokens and cost).
4. `scatter_tokens_vs_rows.png` — raw_rows (x, log) vs total_tokens (y, log).
5. `scatter_duration_vs_rows.png` — raw_rows (x, log) vs total duration_s (y, log).
6. `failed.json` — datasets with status ≠ `ok` (for `--resume-failed`).

### 5.4 Pricing table (`config/gemini_pricing.json`)

```json
{
  "_source": "https://ai.google.dev/pricing as of 2026-04-17",
  "_note": "Preview models may use closest stable-tier pricing as estimate; annotated per-record with is_estimate flag.",
  "gemini-3.1-pro-preview": {"input_per_mtok": 1.25, "output_per_mtok": 10.00, "thoughts_per_mtok": 10.00, "is_estimate": true},
  "gemini-2.5-pro":         {"input_per_mtok": 1.25, "output_per_mtok": 10.00, "thoughts_per_mtok": 10.00, "is_estimate": false},
  "gemini-3-flash-preview": {"input_per_mtok": 0.15, "output_per_mtok": 0.60,  "thoughts_per_mtok": 0.60,  "is_estimate": true}
}
```

Exact prices refined during Phase A implementation. Overridable via `--pricing-file`.

---

## 6. Directory layout

```
output/batch_runs/2026-04-17_comparison/
├─ checkpoint.jsonl                      # orchestrator checkpoint (resume state)
├─ failed.json                           # crashed/timed-out datasets
├─ batch_results.json                    # source of truth
├─ batch_summary.csv                     # spreadsheet-ready
├─ report.md                             # human report
├─ scatter_tokens_vs_rows.png
├─ scatter_duration_vs_rows.png
└─ runs/
   ├─ bis_bis_central_bank_policy_rate/
   │  ├─ pipeline.log
   │  ├─ run_manifest.json
   │  ├─ phase_timings.json
   │  ├─ llm_calls.jsonl                 # every LLM call, every agent
   │  ├─ generated_pvmap.csv
   │  ├─ all_metrics.json                # existing eval output
   │  ├─ generation_notes.md             # existing pipeline output
   │  └─ ... (all other existing pipeline outputs preserved)
   └─ ... (48 more)
```

---

## 7. Rollout plan

### Phase A — Plumbing (before any dataset runs)

1. Write `config/batch_49.txt` (49 dataset names).
2. Implement `LLMTelemetryPlugin` (extend `ArtifactLoggingPlugin`; preserve the Generator-specific `pvmap_llm_result` stash).
3. Implement `phase_timer` context manager + wire it into `src/run_pipeline.py` phases.
4. Implement `run_manifest.json` writer at pipeline start.
5. Implement `scripts/batch_benchmark.py` (orchestrator).
6. Implement `scripts/batch_aggregate.py` (aggregator).
7. Create `config/gemini_pricing.json` with best-available prices and explicit `is_estimate` flags.
8. Unit tests for: telemetry plugin (mock LlmResponse), phase timer, aggregator row-builder with synthetic fixtures, cost computation, timeout handling, checkpoint resume.

### Phase B — Dry-run ladder

Each step stops for human review of the `report.md` before proceeding.

1. **Dry 1 — 2 datasets:** one small (`zurich_bev_3240_wiki`), one medium (`oecd_wastewater_treatment`). End-to-end pipeline → aggregator sanity check.
2. **Dry 2 — +1 (cumulative 3):** add `us_crash_fars_crashdata` (larger). Verifies 3 concurrent workers on distinct MCP ports.
3. **Dry 3 — +2 (cumulative 5):** include a known-retry-prone dataset (e.g. `brfss_nchs_asthma_prevalence`). Exercises retry accounting and timeout/failed path.
4. **Go live — remaining 44 datasets.** Full 49-dataset report.

### Phase C — Rerun failed (if any)

```bash
python scripts/batch_benchmark.py \
  --resume-failed output/batch_runs/2026-04-17_comparison/failed.json \
  --output-dir output/batch_runs/2026-04-17_comparison_rerun \
  --pipeline-args "... --skip-sampling --skip-schema-selection"
```

The orchestrator automatically adds `--skip-sampling --skip-schema-selection` to take advantage of cached outputs from the original run.

---

## 8. Edge cases and failure handling

- **Port already in use** — orchestrator bumps the port by 10 and retries once before failing.
- **Pipeline crashes before `llm_calls.jsonl` is created** — aggregator treats missing file as `calls=0`, status = `crashed`, dataset still appears in the report with null metrics.
- **Pipeline crashes mid-retry** — JSONL append semantics preserve all LLM calls logged before the crash.
- **Evaluation phase fails but PVMAP exists** — `all_metrics.json` absent; record accuracy as `null`, status = `passed_with_warnings`. Not counted as a failure.
- **Preview-model pricing uncertain** — `is_estimate: true` flag in per-record cost output; report header explicitly notes estimate.
- **Concurrent writes to `checkpoint.jsonl`** — `fcntl.flock` on append.
- **Dataset missing from `input/`** — orchestrator skips and logs (verified all 49 exist, so this should not trigger).

---

## 9. Testing strategy

- **Unit tests:** telemetry plugin, phase timer, aggregator row-builder with synthetic fixtures, pricing math, scatter plot generation, failed-list composition.
- **Integration test:** the Phase B Dry 1 (2-dataset) run IS the integration test for the full harness. If its report is correct, the harness is correct. Each subsequent dry-run phase further exercises concurrency, retry accounting, and timeout paths.

---

## 10. Out of scope

- No new accuracy metrics beyond what the existing `evaluate_pvmap_diff.py` produces.
- No changes to prompts, agents, sampling strategies, retry thresholds, or MCP behavior.
- No Schema.org MCP server (deprecated, not wired as flag). Schema.org function tools and the local vocab cache remain active — pipeline behavior unchanged.
- No LLM-judge evaluation (`--use-llm-judge=off`).
- No multi-model comparison (single model per Q1/A choice).
- No MCP latency instrumentation beyond best-effort reuse of existing counts.

---

## 11. Decision log

| # | Question | Decision |
|---|---|---|
| 1 | Models compared | Single: `gemini-3.1-pro-preview` (pipeline defaults for other agents) |
| 2 | MCP | DC MCP only |
| 3 | Dataset count / selection | 49: 44 with PV>0 in any column + 5 borderline zeros in doc order |
| 4 | Parallelism | 3 concurrent workers, port-isolated (no worktrees) |
| 5 | Token granularity | Raw per-call JSONL + per-agent rollup + per-dataset total |
| 6 | Row definition | All three (raw / cleaned / observation) + cols + file MB |
| 7 | Retry behavior | Default (up to 3 attempts) |
| 8 | Prompt versions / metadata / judge / caching | v3 / v1 / off / off / no cache first pass, cache on rerun |
| 9 | Output format | JSON + CSV + Markdown + scatter PNG |
| 10 | Timeout / failure / Δ vs doc / plots / dry runs | 45 min / crash+timeout only / yes / yes / 2→3→5→remaining |
| 11 | Per-agent model behavior | Keep pipeline defaults (mixed); tag model in per-call log |
| 12 | Additional fields to track | All proposed (MCP calls best-effort, $USD, sampling strategy, schema category, attempt count, output StatVar count, phase timing, thinking vs output tokens separate, validation status enum, GT raw counts, prompt bytes, skeleton bytes, git SHA, best-attempt flag, pricing table in header) |
