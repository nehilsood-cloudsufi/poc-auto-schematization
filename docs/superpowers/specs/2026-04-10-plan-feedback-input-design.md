# Plan Feedback & Input Design

## Problem

The plan review page lets engineers select from pre-ranked options and override with custom mappings, but there's no way to:
1. Give freeform feedback to the plan agent to regenerate with corrections
2. Append notes/context that flow downstream to the PVMAP generator

## Solution

Add two capabilities to the plan page:
- **Regenerate Plan**: Engineer writes feedback, plan agent re-runs considering it
- **Append Notes**: Engineer adds freeform notes visible on the plan page and passed to PVMAP generation

## Regenerate Plan

### Quick Regenerate (default)
- Keeps existing `candidate_pool` from CandidateRetriever
- Injects engineer feedback into MappingPlanAgent prompt
- Re-runs MappingPlanAgent + PlanValidator only (~15-30s)
- Plan resets to new LLM output (all selections back to defaults)

### Deep Regenerate
- Re-runs full pipeline: CandidateRetriever → MappingPlanAgent → PlanValidator (~2-5min)
- Same feedback injection
- For when candidates themselves are wrong (e.g., Schema.org missed the right property)

### Feedback injection
The feedback is injected into the plan prompt as a new section:
```
## Engineer Feedback
{feedback}
Consider this feedback carefully when ranking candidates and assigning roles.
```

This section is placed after the candidate pool and before the output instructions so the LLM sees it as a high-priority constraint.

### Selection reset
After regeneration, all selections reset to defaults (top-ranked option per column). The engineer reviews from scratch. Rationale: the whole point of regenerating is that the LLM should reconsider — preserving old selections would mask changes.

## Append Notes

### Storage
Notes are stored as `engineer_notes: string[]` on the `MappingPlan` model. Each "Add Note" appends to this list.

### Visibility
Notes are displayed in a "Your Notes" section on the plan page, above the input area. Simple bullet list. Notes persist across regenerations — they are NOT cleared when the plan regenerates.

### Downstream usage
When the plan is approved and PVMAP generation starts:
- Notes are included in `approved_plan.json`
- Notes are passed via `extra_state["engineer_notes"]`
- The PVMAP generation prompt gets a section: `## Engineer Notes\n{notes}` injected as extra context

## API Endpoints

### POST /runs/{run_id}/plan/regenerate
```
Request:  { "feedback": "string", "deep": boolean }
Response: { "status": "regenerating" }
```

Launches plan regeneration in a background thread. The frontend listens for completion via the existing WebSocket, then reloads the plan via `GET /plan`.

Implementation:
- Reads `phase1_state.json` for existing state (skeleton_summary, schema_vocab, candidate_pool, etc.)
- If `deep=false`: passes existing `candidate_pool` + feedback to MappingPlanAgent + PlanValidator
- If `deep=true`: re-runs CandidateRetriever + MappingPlanAgent + PlanValidator
- Preserves `engineer_notes` from existing plan (not cleared on regenerate)
- Resets run status to "running" during regeneration, back to "plan_ready" on completion
- Uses existing `ProgressTrackingPlugin` for WebSocket events

### POST /runs/{run_id}/plan/notes
```
Request:  { "note": "string" }
Response: { "notes": ["note1", "note2", ...] }
```

Appends a note to the plan's `engineer_notes` list. Updates both `mapping_plan.json` on disk and `phase1_state.json`.

## Data Model Changes

### Pydantic (src/api/models/plan.py)
Add to `MappingPlan`:
```python
engineer_notes: list[str] = Field(default_factory=list)
```

### TypeScript (frontend/src/types/index.ts)
Add to `MappingPlan` interface:
```typescript
engineer_notes: string[];
```

## Frontend Component: PlanFeedback

### Location
`frontend/src/components/PlanReview/PlanFeedback.tsx`

### Props
```typescript
interface PlanFeedbackProps {
  notes: string[];
  onAddNote: (note: string) => void;
  onRegenerate: (feedback: string, deep: boolean) => void;
  regenerating: boolean;
}
```

### Layout
1. "Your Notes" section (visible only if notes exist) — bullet list of existing notes
2. Textarea (3 rows) for input
3. Action buttons: "Add Note" and "Regenerate Plan" (with dropdown for Quick/Deep)
4. While regenerating: textarea disabled, button shows spinner

### Position on page
Bottom of the plan page, between the Global Notes/Warnings section and the navigation buttons (Back / Approve).

## ReviewPlanPage Changes

### New state
```typescript
const [notes, setNotes] = useState<string[]>([]);
const [regenerating, setRegenerating] = useState(false);
```

### Load notes on mount
Notes come from `plan.engineer_notes` when the plan loads.

### Regenerate handler
1. POST `/plan/regenerate` with feedback + deep flag
2. Set `regenerating=true`, show progress
3. Listen for WebSocket completion (plan phase)
4. Reload plan via `getPlan()`
5. Restore notes (preserved on backend)
6. Reset `regenerating=false`

### Add note handler
1. POST `/plan/notes` with note text
2. Update local notes state
3. Clear textarea

### Approve flow (unchanged)
Notes already in MappingPlan model, passed through existing `approvePlan()`.

## Files Changed

### New files
- `frontend/src/components/PlanReview/PlanFeedback.tsx` — feedback/notes input component

### Modified files
- `src/api/models/plan.py` — add `engineer_notes` field to MappingPlan
- `src/api/routes/plan.py` — add POST /plan/regenerate and POST /plan/notes endpoints
- `src/agents/mapping_plan_agent.py` — handle feedback injection in prompt
- `src/api/services/pipeline_runner.py` — handle regeneration pipeline launch
- `frontend/src/types/index.ts` — add `engineer_notes` to MappingPlan interface
- `frontend/src/lib/api.ts` — add `regeneratePlan()` and `addPlanNote()` functions
- `frontend/src/pages/ReviewPlanPage.tsx` — integrate PlanFeedback component, regenerate/notes handlers

## Testing

- Unit test: feedback injection into prompt template (verify feedback text appears in populated prompt)
- Unit test: notes append and persist across plan regeneration
- Unit test: engineer_notes field survives JSON roundtrip
- Frontend: build check (npm run build)
- Integration: regenerate flow preserves notes but resets selections
