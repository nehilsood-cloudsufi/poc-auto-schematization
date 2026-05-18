# Consolidate Schema.org + DC Lookups into Plan Phase

**Date:** 2026-04-01
**Status:** Draft
**Depends on:** `2026-03-31-interactive-mapping-plan-design.md` (plan → approve → generate)

## Problem

The MappingPlanAgent generates plans with `Schema.org: N/A` and `DC Match: None` for every column because it has no access to Schema.org or DC MCP tools. Meanwhile, these same tools are called redundantly by multiple downstream agents:
- `SchemaSelectionAgent` — Schema.org search + lookup
- `PVMAPGeneratorAgent` — all 4 Schema.org tools + DC MCP tools
- `MetadataGenerationAgent` — Schema.org validate

This wastes tokens (LLM tool calls in the generator), adds latency (DC MCP queries per retry attempt), and produces plans that lack the very information users need to make approval decisions.

## Solution

Move **discovery** lookups (Schema.org + DC MCP) into the plan phase. Downstream agents keep only **validation** tools. The plan becomes the single source of truth for property mappings.

## Updated Pipeline Flow

```
[0] ProgrammaticSamplingAgent
[1] SchemaSelectionAgent         ← Schema.org: search + lookup (KEEP for category selection)
[2] SchemaOrgEnrichmentAgent     ← NEW: programmatic per-column Schema.org lookups
[3] StatVarDiscoveryAgent        ← ENHANCED: real per-column DC MCP queries
[4] MappingPlanAgent             ← reads enriched state, produces plan with REAL data
[5] PlanGateAgent
[6] PVMAPRetryLoop
    [6.0] StatePreparationAgent
    [6.1] PVMAPGeneratorAgent    ← Schema.org: validate_pvmap_property ONLY (discovery removed)
                                   DC MCP: REMOVED
    [6.2] MetadataGenerationAgent ← Schema.org: validate_pvmap_property (KEEP)
    [6.3] ValidationAgent
    [6.4] QualityEvaluationAgent
    [6.5] ConditionalFeedbackAgent
    [6.6] MaxRetriesCheckAgent
[7] EvaluationAgent
[8] LLMJudgeAgent
```

## Component 1: SchemaOrgEnrichmentAgent

**File:** `src/agents/schemaorg_enrichment_agent.py`
**Type:** ADK `BaseAgent` (programmatic, no LLM call)

### What It Does

1. Reads `skeleton_summary` from state to get column names + semantic types
2. For each column, calls `SchemaOrgVocab` (local cache singleton, instant) to find:
   - Matching schema.org property
   - Property type and expected value types
   - Valid enum values if applicable
3. Also reads `schema_category` to get category-specific type hierarchy
4. Stores formatted results in state as `schemaorg_column_mappings`

### State Input

| Key | Source |
|-----|--------|
| `skeleton_summary` | ProgrammaticSamplingAgent |
| `schema_category` | SchemaSelectionAgent |

### State Output

| Key | Content |
|-----|---------|
| `schemaorg_column_mappings` | Formatted markdown string — per-column Schema.org findings |

### Output Format

```markdown
### REF_AREA
- Schema.org property: addressCountry (from Place)
- Expected type: Country or Text
- DC equivalent: observationAbout with geoId resolution

### OBS_VALUE
- Schema.org property: value (from StatisticalVariable)
- Expected type: Number

### FREQ
- No direct Schema.org match
- Closest: frequency (from Dataset)
```

### Behavior

- Always runs (Schema.org is local cache, no MCP dependency)
- Instant (~ms, no network calls)
- If no matches found for a column, outputs "No direct Schema.org match"

## Component 2: Enhanced StatVarDiscovery (Per-Column)

**File:** `src/agents/statvar_discovery_agent.py` (modify existing)

### Changes

The existing `_build_per_column_queries()` builds query strings but returns empty match lists. Enhancement: actually execute the queries via `run_mcp_query()`.

### Query Execution

1. For each column with semantic type `measure` or `dimension`, build a query
2. Execute top 3 queries max (by column importance: measure > dimension > place) to control latency
3. Parse results via existing `parse_statvars()` + `build_structured_summary()`
4. Store in `per_column_dc_matches` with actual DCIDs

### Latency Control

- Max 3 per-column MCP queries (beyond the existing broad query)
- Each query has 30s timeout
- Total added latency: ~30-90s (vs current ~0s placeholder)
- When `--enable-mcp` is not set: skipped entirely, empty results

### State Output (enhanced)

```python
{
    "ASTHMA_PREV": [
        {"dcid": "Percent_Person_WithAsthma", "name": "Asthma Prevalence",
         "relevance": "high", "properties": ["measuredProperty: prevalence",
         "populationType: Person", "healthCondition: Asthma"]},
    ],
    "REF_AREA": [
        {"note": "Place identifier — use geoId or countryAlpha2Code"}
    ],
    "OBS_VALUE": []
}
```

## Component 3: MappingPlanAgent Updates

**File:** `src/agents/mapping_plan_agent.py` (modify existing)

### New State Inputs

| Key | Source |
|-----|--------|
| `schemaorg_column_mappings` | SchemaOrgEnrichmentAgent |
| `per_column_dc_matches` | StatVarDiscoveryAgent (already wired) |

### Prompt Template Update

Add `{schemaorg_column_mappings}` to `mapping_plan_prompt.txt`:

```text
## Schema.org Property Mappings (from automated lookup)

{schemaorg_column_mappings}

Use these Schema.org mappings in your plan. If a column has a Schema.org match,
include it in the Schema.org field. If not, write "N/A".
```

### Expected Impact

Plans will now contain real data like:
```markdown
### Column: `REF_AREA`
- **Schema.org:** addressCountry (from Place) — expected type: Country or Text
- **DC Match:** country/ARG (from StatVar discovery)
- **DC Properties:** observationAbout → geoId/{ISO_code}
```

Instead of the current:
```markdown
### Column: `REF_AREA`
- **Schema.org:** N/A
- **DC Match:** None — novel mapping
- **DC Properties:** N/A
```

## Component 4: Generator Tool Removal

**File:** `src/agents/pvmap_generator_agent.py` (modify existing)

### Remove

```python
# REMOVE these imports and tool registrations:
lookup_schemaorg_type      # discovery — now in plan
lookup_schemaorg_property  # discovery — now in plan
search_schemaorg_vocabulary # discovery — now in plan
# REMOVE DC MCP toolset creation
```

### Keep

```python
# KEEP — cheap validation, catches generation mistakes:
validate_pvmap_property
```

### No Changes To

- `schema_selection_agent.py` — keeps Schema.org tools (needed for category selection, runs before plan)
- `metadata_generation_agent.py` — keeps `validate_pvmap_property`

## File Layout

### New Files

```
src/agents/schemaorg_enrichment_agent.py     — programmatic Schema.org per-column lookups
tests/agents/test_schemaorg_enrichment.py
```

### Modified Files

```
src/agents/statvar_discovery_agent.py        — execute real per-column MCP queries
src/agents/pvmap_generator_agent.py          — remove discovery tools, keep validate only
src/agents/mapping_plan_agent.py             — read schemaorg_column_mappings from state
src/resources/prompts/mapping_plan_prompt.txt — add {schemaorg_column_mappings} section
src/run_pipeline.py                          — insert SchemaOrgEnrichment before MappingPlan
```

## Testing Strategy

- **Unit: SchemaOrgEnrichmentAgent** — mock SchemaOrgVocab, verify formatted output per column type
- **Unit: StatVarDiscovery per-column** — mock MCP queries, verify real results stored (not empty placeholders)
- **Unit: Generator tools** — verify only `validate_pvmap_property` remains
- **Integration: Plan content** — run with enrichment, verify plan contains real Schema.org + DC data
- **A/B test** — compare quality metrics before/after consolidation on 5 datasets (BIS, FAO, CRDC, BRFSS, Census SAHIE)
- **Regression** — existing tests pass with `--auto-approve`

## Design Decisions

1. **Programmatic Schema.org lookups over LLM tool calls** — SchemaOrgVocab is a local cache singleton. Calling it programmatically is instant and deterministic. LLM tool calls add latency and unpredictability.
2. **Max 3 per-column MCP queries** — balances DC coverage with latency. Most datasets have 1-3 important measure/dimension columns.
3. **Keep validate_pvmap_property in generator** — zero-cost safety net. Discovery moves to plan, validation stays at generation.
4. **Clean removal over flag-gating** — simpler code. A/B testing determines if removal is safe. Revert if quality drops.
5. **SchemaOrgEnrichment as separate agent, not merged into plan agent** — single responsibility. Enrichment is programmatic (no LLM), plan is LLM-driven. Different concerns, different testing strategies.
