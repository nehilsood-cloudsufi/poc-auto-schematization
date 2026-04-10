# Grounded Plan Agent Redesign

## Problem

The current MappingPlanAgent generates a freeform markdown plan where the LLM invents property-value pairs. This causes:

1. **Hallucination**: LLM creates properties not in Data Commons vocabulary (e.g., fabricated Schema.org mappings, non-existent DC properties)
2. **Ungrounded options**: MCP enrichment only runs in Phase 3 (PVMAP generation), not during plan generation. The plan has zero real-time DC validation.
3. **Poor UI**: The ReviewPlanPage renders raw markdown with regex-based parsing. No structure, no visual hierarchy, no way to quickly triage 17 columns.
4. **Non-binding plan**: The approved plan is passed as freeform text guidance. The PVMAP generator can ignore it entirely.
5. **Noise**: Every column gets the same verbose 8-field template whether it's a critical mapping decision or an obviously-ignored metadata column (14 of 17 columns in BIS are "ignored" with "N/A" everywhere).

## Solution

Restructure the plan agent into a **retrieve-then-rank** pipeline with structured output, an interactive frontend, and binding plan-to-PVMAP conversion.

## Architecture

```
CURRENT (ungrounded):
  Sampling -> SchemaSelection -> SchemaOrgEnrichment -> MappingPlanAgent (LLM invents)
  -> markdown plan -> engineer reads wall of text -> approves
  -> PVMAP Generator (ignores plan if it wants)

NEW (grounded, structured, binding):
  Sampling -> SchemaSelection -> SchemaOrgEnrichment -> CandidateRetriever (programmatic)
  -> MappingPlanAgent v2 (LLM ranks candidates, doesn't invent)
  -> structured JSON plan -> engineer picks from options in interactive UI
  -> PlanToSkeletonConverter -> partial PVMAP CSV (locked rows)
  -> PVMAP Generator (fills gaps only, cannot override engineer selections)
```

Three new components:
- **CandidateRetriever** -- programmatic, gathers grounding data per column from Schema.org, MCP, schema_vocab
- **MappingPlanAgent v2** -- LLM ranks candidates using Gemini structured output (Pydantic response schema)
- **PlanToSkeletonConverter** -- programmatic, converts approved selections to partial PVMAP CSV rows

## Implementation Phases

### Phase 1: Backend Restructure
- New Pydantic data models for structured plan
- CandidateRetriever: per-column grounding from Schema.org + MCP + schema_vocab
- MappingPlanAgent v2: Gemini structured output, LLM ranks not invents
- New API endpoints: `GET /plan` (JSON), `POST /plan/approve`
- Auto-generate markdown from JSON for logs/debugging
- Move MCP per-column queries before plan generation (currently only in Phase 3)

### Phase 2: Interactive Frontend
- Replace markdown dump with structured form
- Table overview (active mappings) + detail panel (expand row to see options)
- Radio buttons for option selection, text area for custom override
- Separate "Ignored Columns" section (simple list)
- Static properties section with same pick-from-options pattern

### Phase 3: Constrained PVMAP Generation
- PlanToSkeletonConverter: engineer selections become partial PVMAP CSV
- PVMAP generator receives skeleton as hard constraint
- LLM fills gaps only (formatting, unresolved columns)
- Validation failures trace back to specific decisions

## Data Models

### Backend (Pydantic)

```python
from enum import Enum
from pydantic import BaseModel, Field


class CandidateSource(str, Enum):
    SCHEMA_ORG = "from Schema.org"
    MCP = "from MCP"
    SCHEMA_VOCAB = "from schema_vocab"
    LLM = "LLM suggestion"
    USER_OVERRIDE = "user override"


class ColumnRole(str, Enum):
    OBSERVATION_ABOUT = "observationAbout"
    OBSERVATION_DATE = "observationDate"
    MEASURE = "measure"
    DIMENSION = "dimension"
    METADATA = "metadata"
    IGNORED = "ignored"


class PropertyValueCandidate(BaseModel):
    """One possible mapping for a column or static property."""
    property: str                       # DC property name, e.g. "observationAbout"
    value_expression: str               # e.g. "country/[DATA]", "[NUMBER]", "InterestRate"
    confidence: float = Field(ge=0, le=1)
    source: CandidateSource
    reason: str                         # 1-line explanation


class ColumnMapping(BaseModel):
    """Plan for a single column."""
    column_name: str                    # exact CSV column name
    role: ColumnRole
    candidates: list[PropertyValueCandidate]  # sorted by confidence desc
    selected_index: int = 0             # engineer's pick (default: top-1)
    evidence: str                       # type, cardinality, sample values (1-2 lines)
    dc_match: str | None = None         # closest existing StatVar DCID
    is_ambiguous: bool = False          # flag for human attention


class StaticProperty(BaseModel):
    """A global property like populationType, unit, etc."""
    property_name: str
    candidates: list[PropertyValueCandidate]
    selected_index: int = 0


class DatasetUnderstanding(BaseModel):
    """High-level dataset classification."""
    archetype: str                      # "Wide" | "Flat" | "Dimension-Row"
    observation_grain: str              # what one row represents
    key_insight: str                    # 1-2 sentences


class MappingPlan(BaseModel):
    """The complete structured plan."""
    dataset_name: str
    understanding: DatasetUnderstanding
    active_columns: list[ColumnMapping]
    ignored_columns: list[ColumnMapping]
    static_properties: list[StaticProperty]
    global_notes: list[str]             # warnings, edge cases
```

### Frontend (TypeScript, mirrors Pydantic)

```typescript
type CandidateSource = "from Schema.org" | "from MCP" | "from schema_vocab" | "LLM suggestion" | "user override";
type ColumnRole = "observationAbout" | "observationDate" | "measure" | "dimension" | "metadata" | "ignored";

interface PropertyValueCandidate {
  property: string;
  value_expression: string;
  confidence: number;
  source: CandidateSource;
  reason: string;
}

interface ColumnMapping {
  column_name: string;
  role: ColumnRole;
  candidates: PropertyValueCandidate[];
  selected_index: number;
  evidence: string;
  dc_match: string | null;
  is_ambiguous: boolean;
}

interface StaticProperty {
  property_name: string;
  candidates: PropertyValueCandidate[];
  selected_index: number;
}

interface DatasetUnderstanding {
  archetype: string;
  observation_grain: string;
  key_insight: string;
}

interface MappingPlan {
  dataset_name: string;
  understanding: DatasetUnderstanding;
  active_columns: ColumnMapping[];
  ignored_columns: ColumnMapping[];
  static_properties: StaticProperty[];
  global_notes: string[];
}
```

## CandidateRetriever (Grounding Engine)

### Location
`src/pipeline/plan/candidate_retriever.py`

### What it does
For each column, queries three sources and builds a merged candidate list:

1. **Schema.org** (local, instant): Looks up column name + semantic type in `SchemaOrgVocab` singleton. Maps semantic types to DC properties (place -> observationAbout, date -> observationDate, etc.)

2. **MCP / DC Discovery** (API, ~2-5s per column): Queries `search_indicators` for each column to find existing StatVar patterns that use similar properties. Extracts property decompositions from matches.

3. **Schema Vocab** (local, instant): Checks the selected category's compressed vocab JSON for valid property names and enum values.

### Merge logic
When multiple sources suggest the same property:
- Confidence = max across sources
- Source = comma-joined list of all sources
- Keep the most specific value expression (e.g., `country/[DATA]` over `[DATA]`)

### Role assignment heuristics
- Semantic type "place" -> observationAbout
- Semantic type "date" -> observationDate
- Numeric type + high cardinality -> measure
- 1 unique value -> ignored
- Empty column -> ignored
- Otherwise -> dimension (refined by MCP patterns)

### MCP timing
Move per-column `search_indicators` queries to run before plan generation (currently only in Phase 3 StatePrep). Results are cached in state key `per_column_candidates` so Phase 3 can reuse them without re-querying.

### Interface

```python
async def retrieve_candidates(
    columns: list[ColumnProfile],
    schema_category: str,
    schema_vocab: str,
    schemaorg_mappings: str,
    mcp_enabled: bool,
    mcp_client: MCPClient | None,
) -> dict[str, ColumnCandidates]:
    """
    Returns a dict mapping column_name -> ColumnCandidates.
    ColumnCandidates contains: role (proposed), candidates (list), evidence (str).
    """
```

## MappingPlanAgent v2 (LLM Ranker)

### Location
`src/agents/mapping_plan_agent.py` (replace existing)

### Prompt structure
The LLM receives:
- Column profiles (skeleton_summary)
- Sampled data
- Pre-retrieved candidate pools per column (structured JSON)
- Schema vocabulary (valid property names)

The LLM's job:
- RANK candidates per column by relevance (reorder if retrieval priorities are wrong)
- Assign confidence scores based on data evidence
- Assign roles considering cross-column context (e.g., only one column can be observationAbout)
- Propose ONE novel mapping per column if all candidates are poor (labeled "LLM suggestion")
- Classify dataset (archetype, grain, insight)
- Write global_notes warnings
- Propose static properties with top-k options

### Gemini structured output
```python
response = await client.aio.models.generate_content(
    model=self._model_name,
    contents=prompt,
    config=types.GenerateContentConfig(
        temperature=0.2,
        max_output_tokens=8192,
        response_mime_type="application/json",
        response_schema=MappingPlan,
    ),
)
plan = MappingPlan.model_validate_json(response.text)
```

### What the LLM CAN do
- Reorder candidates
- Adjust confidence scores with cross-column reasoning
- Assign roles
- Propose 1 novel mapping per column if needed
- Write understanding + global_notes

### What the LLM CANNOT do
- Invent property names not in candidates or schema vocab
- Skip columns
- Output unstructured text

### Saved artifacts
- `mapping_plan.json` -- structured plan (source of truth for UI and API)
- `mapping_plan.md` -- auto-generated markdown from JSON (for logs/debugging only)

## Frontend: Interactive Plan Review

### Layout
The ReviewPlanPage renders structured JSON as an interactive form:

**Sections (top to bottom):**
1. Dataset Understanding -- format, grain, insight (read-only text)
2. Active Mappings -- table with expandable rows
3. Static Properties -- pick-from-options for populationType, unit, etc.
4. Ignored Columns -- simple collapsed list with column name + reason
5. Warnings -- from global_notes
6. Approve button

### Active Mappings table
- Columns: Column Name | Role | Mapping
- Click a row to expand detail panel
- Detail panel shows: evidence, DC match, options (radio buttons), text input for custom override
- Ambiguous columns marked with a warning indicator, expanded by default

### Interaction model
- Radio buttons: select from top-k options (default: top-1 pre-selected)
- Text input: type custom `property -> value_expression` if none fit. Creates new candidate with source "user_override", sets selected_index to it.
- Ignored columns: simple list, each with column name + 1-line reason. No options needed.
- Approve: sends full MappingPlan JSON with updated selected_index values

### API endpoints
```
GET  /api/runs/{id}/plan          -- returns MappingPlan JSON
POST /api/runs/{id}/plan/approve  -- accepts MappingPlan JSON with engineer's selections
POST /api/runs/{id}/generate      -- starts Phase 2 (existing, now reads approved_plan.json)
```

## Plan to Constrained PVMAP (Phase 3)

### PlanToSkeletonConverter
Location: `src/pipeline/plan/skeleton_converter.py`

When the engineer approves, their selections are programmatically converted to a partial PVMAP CSV:

```
Engineer selections:
  REF_AREA -> observationAbout -> country/[DATA]
  TIME_PERIOD -> observationDate -> [DATA]
  OBS_VALUE -> measure -> value -> [NUMBER]
  FREQ -> dimension -> observationPeriod -> [DATA]
  Static: populationType=InterestRate, unit=Percent, statType=measuredValue

Generated skeleton CSV:
  key,property1,value1,property2,value2
  REF_AREA:Reference area,observationAbout,country/[DATA]
  TIME_PERIOD:Time period,observationDate,[DATA]
  OBS_VALUE:Observation Value,value,[NUMBER]
  FREQ:Frequency,observationPeriod,[DATA]
  ,populationType,InterestRate,measuredProperty,value,statType,measuredValue,unit,dcid:Percent
```

### How it constrains the PVMAP generator
- Skeleton rows from engineer selections are LOCKED -- LLM cannot change them
- LLM fills: value expression formatting (e.g., parsing "M: Monthly" to "P1M"), COLUMN:VALUE sub-mappings, any columns left as "let LLM decide"
- Validation failures trace back to specific engineer decisions vs. LLM gaps

### Files saved on approve
- `approved_plan.json` -- MappingPlan with engineer's selected_index values
- `pvmap_skeleton.csv` -- partial PVMAP derived from selections
- Both passed to Phase 2 via `extra_state["approved_plan_json"]` and `extra_state["pvmap_skeleton"]`

## Files Changed

### New files
- `src/pipeline/plan/candidate_retriever.py` -- grounding engine
- `src/pipeline/plan/skeleton_converter.py` -- plan to PVMAP conversion
- `src/pipeline/plan/__init__.py`
- `src/api/models/plan.py` -- Pydantic models (shared between agent and API)
- `frontend/src/components/PlanReview/ActiveMappingsTable.tsx`
- `frontend/src/components/PlanReview/ColumnDetail.tsx`
- `frontend/src/components/PlanReview/StaticProperties.tsx`
- `frontend/src/components/PlanReview/IgnoredColumns.tsx`
- `tests/pipeline/plan/test_candidate_retriever.py`
- `tests/pipeline/plan/test_skeleton_converter.py`
- `tests/api/test_plan_models.py`

### Modified files
- `src/agents/mapping_plan_agent.py` -- replace with v2 (structured output, ranker not inventor)
- `src/resources/prompts/mapping_plan_prompt.txt` -- new prompt (rank candidates, not invent)
- `src/api/routes/plan.py` -- new endpoints (GET /plan JSON, POST /plan/approve)
- `src/run_pipeline.py` -- wire CandidateRetriever before MappingPlanAgent, pass candidates in state
- `src/api/services/pipeline_runner.py` -- pass approved plan JSON + skeleton to Phase 2
- `frontend/src/pages/ReviewPlanPage.tsx` -- replace markdown dump with interactive form
- `frontend/src/types/index.ts` -- add MappingPlan types
- `frontend/src/lib/api.ts` -- add getPlan(), approvePlan() functions

### Removed
- `MappingPlanAgent._inject_schemaorg_into_plan()` -- no longer needed (Schema.org is in candidates)
- `ReviewPlanPage.renderMarkdown()` -- no longer needed (structured data rendered directly)

## Edge Cases

- **MCP disabled**: CandidateRetriever skips MCP queries, relies on Schema.org + schema_vocab only. Plan will have fewer candidates but still structured.
- **No schema category selected**: CandidateRetriever skips schema_vocab source. Schema.org and MCP still provide candidates.
- **Column with zero candidates**: LLM must propose at least one "LLM suggestion" candidate. If even that fails, column defaults to "ignored" with empty candidates list.
- **Gemini structured output failure**: If Gemini returns invalid JSON (rare with response_schema), fall back to unstructured generation + parse attempt. Log warning.
- **Engineer approves without changes**: selected_index stays at 0 for all columns. Skeleton generated from top-1 recommendations.
- **Wide datasets (50+ columns)**: CandidateRetriever processes columns in parallel (asyncio.gather for MCP queries). UI pagination not needed -- table handles 50 rows fine with collapse.

## Testing Strategy

### Phase 1 (backend)
- Unit tests for CandidateRetriever: mock Schema.org, MCP, schema_vocab responses, verify merged candidates
- Unit tests for CandidateRetriever merge logic: same property from multiple sources, confidence aggregation
- Unit tests for MappingPlanAgent v2: mock Gemini response, verify Pydantic validation
- Unit tests for PlanToSkeletonConverter: verify PVMAP CSV output matches selections
- Unit tests for PlanToSkeletonConverter: static properties row generation
- Integration test: run full Phase 1 on BIS dataset, verify plan JSON has grounded candidates
- Test MCP-disabled path: verify plan still generates with Schema.org + vocab only

### Phase 2 (frontend)
- Render test: MappingPlan JSON renders correct number of active/ignored rows
- Interaction test: selecting an option updates selected_index
- Interaction test: typing custom override appends candidate and updates selected_index
- Render test: ambiguous columns expanded by default

### Phase 3 (constrained PVMAP)
- Verify skeleton CSV rows appear unchanged in final PVMAP output
- Verify LLM only fills gaps, not overrides
- A/B comparison: constrained vs. unconstrained PVMAP quality on benchmark datasets
