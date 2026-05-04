# Release Notes — Auto-Schematization Pipeline v0.2.0

| | |
|---|---|
| **Release Date** | 2026-04-21 |
| **Release Version** | v0.2.0 (Feature Release) |
| **Previous Release** | [v0.1.0 — 2026-02-18](https://docs.google.com/document/d/1HuRLZysSDYJFPUxuI1xLdX9hhxwNWcir1hfy37CmXVU/edit?tab=t.0) |
| **Environment** | Dev (Internal) |
| **Prepared By** | CLOUDSUFI DC Team |

---

# Release Overview

This is the v0.2.0 release of the **Automated PVMAP Generation Pipeline** deployed to the staging environment, continuing from [v0.1.0 (GA, 2026-02-18)](https://docs.google.com/document/d/1HuRLZysSDYJFPUxuI1xLdX9hhxwNWcir1hfy37CmXVU/edit?tab=t.0). The system transforms raw CSV datasets into Data Commons-compatible schema mappings (PVMAPs) using AI-powered generation with self-correcting validation.

Key highlights:

- **End-to-end automation:** CSV upload → AI-powered schema mapping → validated Data Commons output (StatVarObservations, MCF, TMCF)
- **Built on Google ADK + Gemini:** 5-phase agentic pipeline with intelligent retry and repair, now with a plan → approve → generate workflow
- **React + FastAPI Web UI:** Upload data, configure runs, review and edit the mapping plan, view real-time progress, edit PVMAPs, and provide structured feedback
- **Cloud Run deployment with IAP:** One-command deploy with GCS persistence, session affinity, and domain-restricted authentication

---

# Core Capabilities

| Feature | Description |
|---------|-------------|
| Automated PVMAP Generation | 5-phase pipeline: Discovery → Sampling → Schema Selection → Generation/Validation → Evaluation |
| Grounded Mapping Plan | Pre-generation plan phase with column analysis, Schema.org enrichment, candidate ranking, and human approval |
| LLM-Driven Smart Sampling | Generates representative 60–100 row samples with column classification (place, time, dimension, value) and skeleton summary |
| Intelligent Schema Selection | AI selects from 7 categories (Demographics, Economy, Education, Employment, Energy, Health, School) with compressed vocabulary (~0.4–5.6 KB per category) |
| Tiered Self-Correction | 3-tier correction (counter rule engine → lightweight patch agent → full regen) with programmatic repair, pre-validation, quality-based early exit, and best-attempt restoration |
| PVMAP Repair Pipeline | Automatic key repair (case normalization, whitespace, fuzzy match at 0.80–0.85 cutoff), placeholder normalization, hallucinated-key cleaning |
| Full-Dataset Validation | `stat_var_processor` validates on complete data (not samples), producing StatVarObservations, MCF, and TMCF output |
| Ground Truth Evaluation | Diff-based metrics (Node Accuracy, PV Accuracy) with 3-tier ground truth discovery across 49+ datasets |
| React + FastAPI Web UI | Upload CSV, configure pipeline, review/edit plan, view real-time progress, inspect and edit PVMAP output, submit structured feedback |
| Human-in-the-Loop Feedback | Structured feedback ledger (Pin Row, Set Mapping, Notes) enforced during correction; output versioning with `v1/`, `v2/` snapshots |
| MCP Integration | Live StatVar discovery via Data Commons MCP server (enabled by default) for enhanced schema matching |
| Batch Benchmark System | 49-dataset orchestrator with resumable checkpoint, cost rollup, and automated comparison reports |
| Cloud Run Deployment | One-command deploy via Cloud Build with GCS FUSE, session affinity, IAP auth, and auto-scaling |

---

# AI / Model Baseline

| | |
|---|---|
| **Model** | `gemini-3.1-pro-preview` (configurable via `--model` CLI flag) |
| **Thinking levels** | Configurable (low / medium / high / minimal / none) |
| **Prompt versions** | v2 and v3 with decision-tree guidance, archetype classification, and worked examples (v3 default) |
| **Structured output** | Deterministic CSV format (default: enabled via `--structured-output`) |
| **Validation** | Full-dataset subprocess validation + programmatic key repair + tiered correction |
| **Test corpus** | 49 datasets across 6 domains; average processing time ~45 seconds per dataset |

**Baseline Performance Metrics**

| Metric | This Release | Gemini-Only Baseline | Improvement |
|--------|-------------|---------------------|-------------|
| PV Accuracy | 26.8% | 8.1% | +18.7% |
| Node Accuracy | 15.1% | 4.6% | +10.5% |

---

# Git Repositories & Technical References

## Source Code Repositories

| Component | Repository Name | Branch / Tag | Link |
|-----------|----------------|-------------|------|
| Core Pipeline + UI | poc-auto-schematization | `release/nehil/v0.2.0-deploy` | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization) |

## Commit & Versioning Details

| | |
|---|---|
| **Release tag** | v0.2.0 |
| **Commit hash (primary)** | `1f0f5bd8c26b` |
| **Branch strategy** | `release/nehil/v0.2.0-deploy` |
| **CI pipeline** | Cloud Build (`Dockerfile` + `deploy/`) |

## API & Schema References

| Reference | Location |
|-----------|----------|
| Schema examples | `src/resources/schema_examples/` (7 categories: Demographics, Economy, Education, Employment, Energy, Health, School) |
| Prompt templates | `src/resources/prompts/` (`improved_pvmap_prompt.txt`, `improved_pvmap_prompt_v2.txt`, `improved_pvmap_prompt_v3.txt`, `mapping_plan_v2.txt`, `feedback_v2.txt`) |

---

# What to Test

- CSV file upload and data preview in the Web UI
- End-to-end pipeline execution (Sampling → Schema Selection → Mapping Plan → PVMAP Generation → Validation)
- Mapping plan review, edit, and approval flow
- Real-time progress tracking during pipeline run
- PVMAP output viewing and in-browser editing (AG Grid spreadsheet editor)
- Structured human feedback submission (Pin Row / Set Mapping / Notes) and re-run with feedback injected
- Output versioning (`v1/`, `v2/` snapshot directories with `run_manifest.json`)
- CLI execution with flags: `--dataset`, `--skip-sampling`, `--skip-schema-selection`, `--skip-evaluation`, `--structured-output`, `--plan-only`, `--from-plan`, `--auto-approve`, `--prompt-version`
- MCP toggle: enable/disable Data Commons discovery (`--enable-mcp`, on by default)
- Cloud Run deployment with IAP authentication and GCS output persistence

---

# Known Issues

| ID | Description | Impact/Severity | Status |
|----|-------------|-----------------|--------|
| 1 | Schema categories limited to 7 predefined types; custom categories not yet supported | Medium — out-of-domain datasets use best-fit category | Extensible in future |
| 2 | MCP integration requires separate Data Commons API key configuration | Low — optional feature; pipeline fully functional without it | Documented |
| 3 | File upload size limited by FastAPI/browser default (~200 MB) | Low — covers most datasets; adjustable via config | Configurable |
| 4 | `--skip-schema-selection` causes `schema_category` state to never be set | Low — fallback logic prevents errors | Handled gracefully |
| 5 | Plan regeneration on very large datasets can approach 64 K output-token budget | Low — automatic fallback to v1 prompt on truncation | Mitigated |

**Resolved from v0.1.0:** authentication on Cloud Run UI (IAP domain-restricted to `@cloudsufi.com` and `@google.com`) and multi-batch resource deadlocks (new subprocess-pool batch orchestrator with checkpointing).

---

# Documentation & Onboarding

| Document | Description | Link |
|----------|-------------|------|
| `README.md` | Project overview, quick start, and key metrics | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/v0.2.0-deploy/README.md) |
| `docs/SETUP.md` | Installation and environment setup guide | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/v0.2.0-deploy/docs/SETUP.md) |
| `docs/INPUT_GUIDE.md` | Input file structure and naming conventions | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/v0.2.0-deploy/docs/INPUT_GUIDE.md) |
| `docs/USAGE.md` | Pipeline usage, CLI flags, and common tasks | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/v0.2.0-deploy/docs/USAGE.md) |
| `docs/DEPLOYMENT.md` | Cloud Run deployment guide (with IAP setup) | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/v0.2.0-deploy/docs/DEPLOYMENT.md) |
| `docs/APPENDIX.md` | Troubleshooting, architecture details, and FAQ | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/v0.2.0-deploy/docs/APPENDIX.md) |
| `docs/mcp_integration.md` | MCP server setup and usage | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/v0.2.0-deploy/docs/mcp_integration.md) |

---

# Feedback / Test Results

| | |
|---|---|
| **Test suite** | 2100 tests (up from 982 in v0.1.0) |
| **Skipped tests** | MCP integration tests and fixture-dependent tests |
| **Test command** | `PYTHONPATH="$(pwd):$(pwd)/src" pytest tests/ -x -q` |
| **Staging environment** | [Link to staging environment](https://auto-schematization-agent-90008518143.us-central1.run.app/) (IAP-protected) |

---

# What's Next

- **Expanded schema categories** — Support custom and user-defined categories beyond the 7 built-in types
- **Batch processing in UI** — Surface the CLI batch orchestrator as an in-UI queue for multiple datasets in a single session
- **Performance optimizations** — Caching, parallel dataset processing, and reduced LLM round-trips
- **Enhanced evaluation metrics** — Richer diff reporting, per-column accuracy breakdown, and trend tracking across versions
- **Improved MCP integration** — Tighter StatVar discovery feedback loop and auto-suggestion in PVMAP generation
- **Cost dashboards** — Surface `llm_calls.jsonl` + pricing rollup in the History page
- **RBAC beyond domain gating** — Per-role permissions (viewer / engineer / reviewer) on top of IAP
