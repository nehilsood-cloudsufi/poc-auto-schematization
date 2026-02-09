# MCP Integration: Live Agentic StatVar Discovery

## Overview

The MCP (Model Context Protocol) integration transforms Data Commons StatVar discovery from a one-shot pre-pipeline step into a live, error-responsive tool available throughout the PVMAP retry loop. When enabled (`--enable-mcp`), the pipeline starts a local DC MCP server and uses it for StatVar discovery, error resolution, and direct generator lookups.

## Architecture

### Before (One-Shot)

```
SequentialAgent([
  Sampling,
  Schema,
  StatVarDiscovery,        # Runs ONCE before the loop
  LoopAgent([
    StatePrep, Generator, Validator, QualityEval, QualityFeedback, ErrorFeedback, MaxRetry
  ])
])
```

- Discovery ran once, results stored as static `statvar_summary` text
- Same summary injected identically into every retry attempt
- Defensive language ("Reference Only", "IGNORE them") told the LLM to disregard results
- Only `search_indicators` was used; `get_observations` was never called
- Validation errors never triggered new MCP queries

### After (Live Agentic)

```
SequentialAgent([
  Sampling,
  Schema,
  LoopAgent([
    StatePrep,
    StatVarDiscovery,      # Inside loop, attempt-aware
    Generator,             # Has MCP toolset for direct lookups
    Validator,
    MCPErrorResolver,      # New: post-validation error resolution
    QualityEval,
    QualityFeedback,
    ErrorFeedback,
    MaxRetry
  ])
])
```

- 9 agents in loop (vs 7 without MCP)
- StatVarDiscovery runs every iteration with attempt-aware behavior
- Generator has direct MCP tool access for on-demand lookups
- MCPErrorResolver makes targeted queries after validation failures
- Confidence-weighted guidance replaces defensive language

## DC MCP Tools Available

| Tool | Key Parameters | Returns |
|------|---------------|---------|
| `search_indicators` | `query` (required), `places`, `parent_place`, `per_search_limit` | StatVar DCIDs with names, descriptions, match scores |
| `get_observations` | `variable_dcid` (required), `place_dcid` (required), `date` | Observation values: `{variable, entity, observations}` |

## Files Modified

| File | Role |
|------|------|
| `src/agents/dc_query_agent.py` | All MCP query logic centralized here |
| `src/agents/statvar_discovery_agent.py` | Loop-aware, delegates to dc_query_agent |
| `src/agents/pvmap_retry_loop.py` | Insert agents, pass MCP params, state defaults |
| `src/agents/pvmap_generator_agent.py` | MCP toolset + instruction updates |
| `src/agents/pvmap_generation/helpers.py` | Confidence-weighted StatVar injection |
| `src/agents/feedback_agent.py` | `{mcp_resolved_context}` in instruction |
| `src/run_pipeline.py` | Pipeline plumbing for MCP params |

## Key Components

### 1. dc_query_agent.py (Centralized MCP Logic)

All MCP query logic lives in a single file with these factory functions:

```python
create_enrichment_agent(mcp_url, model, data_context, attempt, error_feedback, validation_error)
```
- **Attempt 0:** Broad discovery using dataset's P+M+C formula (places, measures, categories)
- **Attempt 1+:** Error-driven refinement using validation errors

```python
create_error_resolver_agent(mcp_url, model, validation_error, pvmap_csv)
```
- Classifies validation errors and makes targeted MCP queries to resolve them
- Runs after validator, writes `mcp_resolved_context` to state

```python
async run_mcp_query(mcp_url, agent, query) -> str
```
- Shared helper to run an MCP agent and collect text results

```python
parse_statvars(text) -> list[dict]
```
- Parse StatVar DCIDs from discovery output

### 2. StatVarDiscoveryAgent (Loop-Aware)

Behavior changes based on attempt number:

| Attempt | Behavior | Query Strategy |
|---------|----------|---------------|
| 0 | Broad discovery | Uses skeleton_summary context to search for relevant StatVars |
| 1+ | Error-driven refinement | Uses validation errors to make targeted queries |

Writes to state:
- `statvar_summary` (str): Human-readable summary of discovered StatVars
- `mcp_enrichment_context` (dict): Structured discovery results

### 3. MCPErrorResolverAgent (New)

Minimal BaseAgent defined inline in `pvmap_retry_loop.py`:
- Skips if MCP disabled or validation passed
- Delegates to `dc_query_agent.create_error_resolver_agent()`
- Writes `mcp_resolved_context` to state for use by feedback agents

### 4. Generator MCP Toolset

When MCP is enabled, the PVMAP generator agent receives:
- `tools=[create_dc_mcp_toolset(mcp_url)]` for direct `search_indicators`/`get_observations` calls
- `{mcp_tools_instruction}` in its system instruction with usage guidance

### 5. Confidence-Weighted StatVar Injection

Replaced binary inject-or-nothing with graduated guidance:

```
# DISCOVERED DATA COMMONS VARIABLES
The following variables were found via live Data Commons search.

Usage guidance:
- HIGH confidence matches: Use these DCIDs directly in your PVMAP
- MEDIUM confidence: Reference for property naming conventions
- No good matches: Generate StatVar definition from schema examples
```

## State Keys

| Key | Type | Set By | Read By |
|-----|------|--------|---------|
| `mcp_enrichment_context` | dict | StatVarDiscoveryAgent | Generator, FeedbackAgents |
| `mcp_tools_instruction` | str | StatePrep | Generator (instruction template) |
| `mcp_resolved_context` | str | MCPErrorResolver | FeedbackAgent, QualityFeedback |
| `mcp_enabled` | bool | run_pipeline.py | StatePrep, retry loop |
| `mcp_url` | str | run_pipeline.py | All MCP agents |

## Usage

### Enable MCP

```bash
# With MCP enabled (starts local DC MCP server on port 3000)
python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --enable-mcp

# With structured output + MCP
python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence --structured-output --enable-mcp

# Full pipeline with all options
python src/run_pipeline.py --dataset=brfss_nchs_asthma_prevalence \
  --structured-output --enable-mcp --force-resample
```

### Graceful Degradation

The pipeline completes successfully even if:
- MCP server is down (connection errors are caught)
- MCP returns no results (falls back to schema examples)
- MCP session fails mid-retry (continues without MCP for that attempt)

## Test Coverage

| Test File | Tests | What It Covers |
|-----------|:-----:|----------------|
| `tests/agents/test_dc_query_agent_enrichment.py` | 23 | Enrichment/error resolver factories, parse_statvars, run_mcp_query, instruction templates |
| `tests/agents/test_retry_loop_with_mcp.py` | 13 | Loop agent count (9 vs 7), agent ordering, state defaults, MCPErrorResolver skip logic |
| `tests/agents/test_pvmap_generator_with_mcp.py` | 12 | Generator with/without MCP toolset, instruction content, confidence-weighted injection |
| `tests/mcp/test_statvar_discovery.py` | 1 | Integration test (gated behind `RUN_MCP_INTEGRATION_TESTS=true`) |

Run tests:
```bash
# Unit tests (no MCP server needed)
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest \
  tests/agents/test_dc_query_agent_enrichment.py \
  tests/agents/test_retry_loop_with_mcp.py \
  tests/agents/test_pvmap_generator_with_mcp.py -x -q

# Full regression (499 tests)
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q

# Integration test (requires running MCP server)
RUN_MCP_INTEGRATION_TESTS=true PYTHONPATH="$(pwd):$(pwd)/src" \
  .venv/bin/python -m pytest tests/mcp/test_statvar_discovery.py -x -q
```

## Benchmark Results

### PV Accuracy Comparison (9 Datasets)

| Dataset | Gemini Base | Claude CLI | Gemini 3 Pro | MCP OFF | MCP ON |
|---------|:-----------:|:----------:|:------------:|:-------:|:------:|
| cdc_social_vulnerability_index | 4.9 | 28.3 | 14.6 | **37.9** | **37.9** |
| world_bank_commodity_market | 3.7 | 35.5 | 32.7 | 23.0 | **32.7** |
| brfss_nchs_asthma_prevalence | 1.5 | 23.3 | 19.1 | — | **30.2** |
| bis_bis_central_bank_policy_rate | 0.0 | 18.2 | **36.4** | 18.2 | 18.2 |
| us_urban_school_teachers | 2.1 | 0.0 | 8.2 | **11.0** | 9.6 |
| fbi_fbigovcrime | 0.0 | **8.2** | 6.6 | 6.6 | 6.6 |
| india_nfhs | 14.2 | 5.3 | **21.6** | 4.4 | 4.4 |
| oecd_regional_education | **5.3** | 2.6 | 2.6 | 2.6 | 2.6 |
| us_bls_cpi_category | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |

### MCP Impact (ON vs OFF)

| Dataset | MCP OFF | MCP ON | Delta |
|---------|:-------:|:------:|:-----:|
| world_bank_commodity_market | 23.0% | 32.7% | **+9.7** |
| brfss_nchs_asthma_prevalence | — | 30.2% | new best |
| cdc_social_vulnerability_index | 37.9% | 37.9% | 0.0 |
| bis_bis_central_bank_policy_rate | 18.2% | 18.2% | 0.0 |
| fbi_fbigovcrime | 6.6% | 6.6% | 0.0 |
| india_nfhs | 4.4% | 4.4% | 0.0 |
| oecd_regional_education | 2.6% | 2.6% | 0.0 |
| us_bls_cpi_category | 0.0% | 0.0% | 0.0 |
| us_urban_school_teachers | 11.0% | 9.6% | -1.4 |

### Key Findings

1. **Current pipeline sets new bests on 3/9 datasets** vs all prior models (cdc 37.9%, brfss 30.2%, us_urban 11.0%)
2. **MCP's clearest win: world_bank +9.7pp** (23.0% to 32.7%), matching Gemini 3 Pro benchmark
3. **MCP is neutral on 6/9 datasets** and has one minor regression (-1.4pp on us_urban)
4. **Pipeline improvements** (structured output, quality agents, feedback loop) contribute more than MCP alone
5. **Graceful degradation confirmed** - pipeline completes successfully even with MCP connection errors

### Winner Distribution

| Model | Wins (Best PV%) | Datasets |
|-------|:----------------:|----------|
| Current pipeline (MCP OFF/ON) | 3 | cdc, brfss, us_urban |
| Claude CLI | 2 | world_bank, fbi |
| Gemini 3 Pro | 2 | bis, india_nfhs |
| Gemini Base | 1 | oecd |
| Tie | 1 | us_bls_cpi (all 0%) |

## Known Issues

1. **Port contention**: Running multiple MCP-enabled pipelines concurrently can cause connection failures since all share port 3000. Run MCP pipelines sequentially or use different ports.
2. **ADK `{Data}` templating bug**: ADK's `inject_session_state` interprets `{Data}` in PVMAP CSV content as a state variable, causing `KeyError: 'Context variable not found: Data'` in QualityFeedbackAgent. The pipeline still completes despite this error.
3. **StatVar discovery yield**: Some datasets return 0 StatVars from MCP (e.g., india_nfhs) — the pipeline falls back to schema examples in these cases.
