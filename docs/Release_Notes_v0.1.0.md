# Release Notes — Auto-Schematization Pipeline v0.1.0

| | |
|---|---|
| **Release Date** | 2026-02-18 |
| **Release Version** | v0.1.0 (Initial / GA Release) |
| **Environment** | Staging |
| **Prepared By** | Nehil Sood |

---

# Release Overview

This is the first production release of the **Automated PVMAP Generation Pipeline** deployed to the staging environment. The system transforms raw CSV datasets into Data Commons-compatible schema mappings (PVMAPs) using AI-powered generation with self-correcting validation.

Key highlights:

- **End-to-end automation:** CSV upload → AI-powered schema mapping → validated Data Commons output (StatVarObservations, MCF, TMCF)
- **Built on Google ADK + Gemini:** 5-phase agentic pipeline with intelligent retry and repair
- **Streamlit Web UI:** Upload data, configure runs, view real-time progress, edit PVMAPs, and provide feedback
- **Cloud Run deployment:** One-command deploy with GCS persistence and session affinity

---

# Core Capabilities

| Feature | Description |
|---------|-------------|
| Automated PVMAP Generation | 5-phase pipeline: Discovery → Sampling → Schema Selection → Generation/Validation → Evaluation |
| LLM-Driven Smart Sampling | Generates representative 60–100 row samples with column classification (place, time, dimension, value) and skeleton summary |
| Intelligent Schema Selection | AI selects from 7 categories (Demographics, Economy, Education, Employment, Energy, Health, School) with compressed vocabulary (~0.4–5.6 KB per category) |
| Self-Correcting Retry Loop | Up to 3 attempts with programmatic repair, pre-validation, quality-based early exit, stagnation detection, and best-attempt restoration |
| PVMAP Repair Pipeline | Automatic key repair (case normalization, whitespace, fuzzy match at 0.80–0.85 cutoff), placeholder normalization, hallucinated-key cleaning |
| Full-Dataset Validation | `stat_var_processor` validates on complete data (not samples), producing StatVarObservations, MCF, and TMCF output |
| Ground Truth Evaluation | Diff-based metrics (Node Accuracy, PV Accuracy) with 3-tier ground truth discovery across 81 datasets |
| Streamlit Web UI | Upload CSV, configure pipeline parameters, view real-time progress, inspect and edit PVMAP output, provide text feedback |
| Human-in-the-Loop Feedback | Edit PVMAP and metadata in UI, text feedback injected into retry context, output versioning with `v1/`, `v2/` snapshots |
| MCP Integration | Live StatVar discovery via Data Commons MCP server for enhanced schema matching |
| Cloud Run Deployment | One-command deploy via Cloud Build with GCS FUSE for output persistence, session affinity, and auto-scaling |

---

# AI / Model Baseline

| | |
|---|---|
| **Model** | `gemini-3.1-pro-preview` (configurable via `--model` CLI flag) |
| **Thinking levels** | Configurable (low / medium / high / minimal / none) |
| **Prompt versions** | v1 and v2 with decision-tree guidance, archetype classification, and worked examples |
| **Structured output** | Deterministic CSV format (default: enabled via `--structured-output`) |
| **Validation** | Full-dataset subprocess validation + programmatic key repair |
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
| Core Pipeline + UI | poc-auto-schematization | `release/nehil/agentB_v0` | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization) |

## Commit & Versioning Details

| | |
|---|---|
| **Release tag** | v0.1.0 |
| **Commit hash (primary)** | `bc4cf7535ae57b5d46bad36ad3267278a81d080d` |
| **Branch strategy** | `release/nehil/agentB_v0` |
| **CI pipeline** | Cloud Build (`Dockerfile` + `deploy/`) |

## API & Schema References

| Reference | Location |
|-----------|----------|
| Schema examples | `src/resources/schema_examples/` (7 categories: Demographics, Economy, Education, Employment, Energy, Health, School) |
| Prompt templates | `src/resources/prompts/` (`improved_pvmap_prompt.txt`, `improved_pvmap_prompt_v2.txt`) |

---

# What to Test

- CSV file upload and data preview in Streamlit UI
- End-to-end pipeline execution (Sampling → Schema Selection → PVMAP Generation → Validation)
- Real-time progress tracking during pipeline run
- PVMAP output viewing and in-browser editing
- Human feedback submission and re-run with feedback injected
- Output versioning (`v1/`, `v2/` snapshot directories with `run_manifest.json`)
- CLI execution with flags: `--dataset`, `--skip-sampling`, `--skip-schema-selection`, `--skip-evaluation`, `--structured-output`
- MCP toggle: enable/disable Data Commons discovery (`--enable-mcp`)
- Cloud Run deployment and GCS output persistence

---

# Known Issues

| ID | Description | Impact/Severity | Status |
|----|-------------|-----------------|--------|
| 1 | No authentication on Cloud Run UI (public endpoint by default) | High — unauthorized access to staging data | Planned for v0.2.0 |
| 2 | Schema categories limited to 7 predefined types; custom categories not yet supported | Medium — out-of-domain datasets use best-fit category | Extensible in future |
| 3 | MCP integration requires separate Data Commons API key configuration | Low — optional feature; pipeline fully functional without it | Documented |
| 4 | File upload size limited by Streamlit default (~200 MB) | Low — covers most datasets; adjustable via config | Configurable |
| 5 | `--skip-schema-selection` causes `schema_category` state to never be set | Low — fallback logic prevents errors | Handled gracefully |
| 6 | Multi-Batch processing leads to either resource deadlocks or Gemini API errors | High — blocks concurrent dataset runs | Planned for v0.2.0 |

---

# Documentation & Onboarding

| Document | Description | Link |
|----------|-------------|------|
| `README.md` | Project overview, quick start, and key metrics | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/agentB_v0/README.md) |
| `docs/SETUP.md` | Installation and environment setup guide | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/agentB_v0/docs/SETUP.md) |
| `docs/INPUT_GUIDE.md` | Input file structure and naming conventions | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/agentB_v0/docs/INPUT_GUIDE.md) |
| `docs/USAGE.md` | Pipeline usage, CLI flags, and common tasks | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/agentB_v0/docs/USAGE.md) |
| `docs/DEPLOYMENT.md` | Cloud Run deployment guide | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/agentB_v0/docs/DEPLOYMENT.md) |
| `docs/APPENDIX.md` | Troubleshooting, architecture details, and FAQ | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/agentB_v0/docs/APPENDIX.md) |
| `docs/mcp_integration.md` | MCP server setup and usage | [GitHub](https://github.com/nehilsood-cloudsufi/poc-auto-schematization/blob/release/nehil/agentB_v0/docs/mcp_integration.md) |

---

# Feedback / Test Results

| | |
|---|---|
| **Test suite** | 982 tests (982 pass, 5 skip) |
| **Skipped tests** | MCP integration tests and fixture-dependent tests |
| **Test command** | `PYTHONPATH="$(pwd):$(pwd)/src" pytest tests/ -x -q` |
| **Staging environment** | [Link to staging environment](https://agent-b-zc2xldqgha-uc.a.run.app/) |

---

# What's Next

- **Authentication & RBAC** — Add identity-aware proxy or OAuth for Cloud Run UI
- **Expanded schema categories** — Support custom and user-defined categories beyond the 7 built-in types
- **Batch processing in UI** — Queue and process multiple datasets in a single session
- **Performance optimizations** — Caching, parallel dataset processing, and reduced LLM round-trips
- **Enhanced evaluation metrics** — Richer diff reporting, per-column accuracy breakdown, and trend tracking across versions
- **Improved MCP integration** — Tighter StatVar discovery feedback loop and auto-suggestion in PVMAP generation
