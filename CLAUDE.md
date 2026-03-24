# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Build & Test

```bash
# Install dependencies (--all-extras includes dev deps like pytest)
uv sync --all-extras

# Activate virtual environment
source .venv/bin/activate

# PYTHONPATH is required for ALL commands (imports, tests, pipeline)
export PYTHONPATH="$(pwd):$(pwd)/src"

# Run all tests
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q

# Run single test file
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/validation/test_pvmap_repair.py -x -q

# Run tests matching keyword
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -k "test_name" -x -q

# Run the pipeline
python src/run_pipeline.py --dataset=bis_bis_central_bank_policy_rate

# Launch Streamlit UI
PYTHONPATH="$(pwd):$(pwd)/src" streamlit run src/ui/app.py

# Manually validate a PVMAP
PYTHONPATH="$(pwd):$(pwd)/src" python3 tools/stat_var_processor.py \
  --input_data="input/{dataset}/test_data/*_input.csv" \
  --pv_map="output/{dataset}/generated_pvmap.csv" \
  --generate_statvar_name=True \
  --output_path="output/{dataset}/processed"
# Optional: add --config_file="input/{dataset}/input_metadata/*_metadata.csv" if metadata exists

# Query Gemini for Data Commons expert guidance
python -m src.tools.gemini_query_tool --topic pvmap "How should I map this column?"
# Topics: statvar, dimension, sampling, pvmap, mcp
```

**IMPORTANT:** `pytest-timeout` is NOT installed. Do not use `--timeout` flag.

## What This Project Does

Automated PVMAP (Property-Value Map) generation pipeline: transforms CSV datasets into Data Commons StatVarObservations using Gemini LLM with validation and self-correction.

Entry point: `src/run_pipeline.py` — run `--help` for all CLI flags.

Pipeline phases: Discovery → Sampling → Schema Selection → PVMAP Generation (with retry loop) → Validation → Evaluation

## Architecture (Non-Obvious Parts Only)

**Agent orchestration:** Google ADK agents in `src/agents/`, coordinated by `src/agents/coordinator.py`. The retry loop in `src/agents/pvmap_retry_loop.py` is the critical path.

**stat_var_processor is a subprocess, NOT a module import.** Called via `subprocess.run()` with 300-second timeout. PYTHONPATH must be set. See `.claude/rules/pipeline-validation.md` for details.

**Programmatic sampling** (`src/agents/sampling_agent_v2.py`) is the default. Legacy LLM-orchestrated sampling available via `--sampling-mode legacy`.

**Schema vocab:** Compressed JSON in `src/resources/schema_examples/{Category}/schema_vocab.json`. Built by `tools/build_schema_vocab.py` from `.txt` source files.

## Gotchas & Anti-Patterns

NEVER run validation on sampled data. Must use FULL original dataset (`test_data/*_input.csv`).

NEVER use `{Data}`, `{Number}`, or any `{...}` in ADK LlmAgent instruction text. ADK resolves these as state variables. Use `[DATA]`, `[NUMBER]` instead. This caused a production outage.

NEVER pass full error logs (10KB+) to LLM feedback. Sample to ~300 lines max (last 50 lines + 10 random 5-line samples).

NEVER modify original input files. Always write to `output/` or temp locations.

IMPORTANT: `.env` file MUST be loaded BEFORE any imports in `src/run_pipeline.py`. API keys from `.env` take priority over environment variables.

IMPORTANT: Execution order is strict — sampling → schema selection → PVMAP generation. Skipping or reordering breaks the pipeline.

IMPORTANT: When modifying `src/agents/feedback_agent.py`, ensure the feedback agent NEVER suggests removing observationAbout/observationDate/value mappings, hardcoding dates/places, or replacing decomposed properties with variableMeasured DCIDs.

Do not trust LLM category parsing — always use fuzzy matching with validation.

Do not assume schema files exist — check first (e.g., School category may be missing).

## Environment

```bash
# Required
export PYTHONPATH="$(pwd):$(pwd)/src"
# In .env file (loaded automatically)
GEMINI_API_KEY=your-key-here
```

`ANTHROPIC_API_KEY` needed only if not using Claude Code subscription.

## Logging & Debugging

- Pipeline log: `logs/pipeline_{timestamp}.log`
- Per-dataset log: `logs/{dataset_name}/generation_{timestamp}.log`
- Human-readable notes: `output/{dataset_name}/generation_notes.md`
- LLM responses per attempt: `output/{dataset_name}/generated_response/attempt_N.md`

## Workflow & Conventions

**Commits:** Use conventional commits — `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`. Keep messages concise (1-2 sentences). NEVER include Claude as co-author or contributor in commits — no `Co-Authored-By` lines.

**Branches:** Use `feature/nehil/`, `release/nehil/`, or `nehil/` prefix for all branches.

**Phase-based development:** Large features are built in numbered phases (Phase 1, 2, 3...). Each phase should be independently testable. Run A/B comparisons on significant changes before committing to an approach.

**Test verification:** After every code change, run the full test suite and report the pass/skip/fail count. Track test count growth — regressions in test count should be flagged.

**Documentation:** Always update `docs/` when implementing major changes (features, architecture, refactoring). Create dedicated docs for complex migrations (e.g., `docs/metadata_refactoring.md`).

**Dependencies:** `pyproject.toml` is the source of truth. `requirements.txt` is generated via `uv pip freeze`. Dev deps go in `[project.optional-dependencies] dev`.

**Google ADK:** This project uses Google ADK for agent orchestration. Use the `/google-adk` skill when working with ADK agents. Key ADK gotchas are in `.claude/rules/adk-agents.md`.

Reference: README.md, docs/SETUP.md, docs/INPUT_GUIDE.md, docs/USAGE.md, docs/APPENDIX.md
