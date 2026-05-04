# Plan Feedback & Input — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add feedback and notes input to the plan review page so engineers can regenerate the plan with corrections or append context notes that flow to PVMAP generation.

**Architecture:** Two new API endpoints (regenerate + notes), feedback injection into the MappingPlanAgent prompt, a new PlanFeedback frontend component, and an `engineer_notes` field on the MappingPlan model.

**Tech Stack:** Python/FastAPI (backend), Pydantic (models), React/TypeScript (frontend), Gemini (plan regeneration)

**Spec:** `docs/superpowers/specs/2026-04-10-plan-feedback-input-design.md`

---

## File Map

### New Files
| File | Responsibility |
|------|---------------|
| `frontend/src/components/PlanReview/PlanFeedback.tsx` | Textarea + action buttons for feedback and notes |

### Modified Files
| File | Change |
|------|--------|
| `src/api/models/plan.py:70-77` | Add `engineer_notes` field to MappingPlan |
| `src/api/routes/plan.py` | Add POST /plan/regenerate and POST /plan/notes endpoints |
| `src/agents/mapping_plan_agent.py:144-148` | Inject feedback into prompt template |
| `src/resources/prompts/mapping_plan_prompt.txt` | Add `{engineer_feedback}` placeholder |
| `frontend/src/types/index.ts` | Add `engineer_notes` to MappingPlan interface |
| `frontend/src/lib/api.ts` | Add `regeneratePlan()` and `addPlanNote()` functions |
| `frontend/src/pages/ReviewPlanPage.tsx` | Integrate PlanFeedback, regenerate/notes handlers |

---

### Task 1: Add engineer_notes to MappingPlan model

**Files:**
- Modify: `src/api/models/plan.py:70-77`
- Modify: `frontend/src/types/index.ts`
- Test: `tests/api/test_plan_models.py`

- [ ] **Step 1: Write failing test**

Add to `tests/api/test_plan_models.py`:

```python
class TestEngineerNotes:
    def test_default_empty(self):
        plan = MappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(
                archetype="Flat", observation_grain="n/a", key_insight="n/a"
            ),
            active_columns=[],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
        )
        assert plan.engineer_notes == []

    def test_notes_persist_roundtrip(self):
        plan = MappingPlan(
            dataset_name="test",
            understanding=DatasetUnderstanding(
                archetype="Flat", observation_grain="n/a", key_insight="n/a"
            ),
            active_columns=[],
            ignored_columns=[],
            static_properties=[],
            global_notes=[],
            engineer_notes=["Date format is YYYY-MM", "Use wikidataId for places"],
        )
        restored = MappingPlan.model_validate_json(plan.model_dump_json())
        assert restored.engineer_notes == ["Date format is YYYY-MM", "Use wikidataId for places"]

    def test_backward_compat_no_notes_field(self):
        """Old JSON without engineer_notes should still parse (defaults to [])."""
        old_json = '{"dataset_name":"test","understanding":{"archetype":"Flat","observation_grain":"n/a","key_insight":"n/a"},"active_columns":[],"ignored_columns":[],"static_properties":[],"global_notes":[]}'
        plan = MappingPlan.model_validate_json(old_json)
        assert plan.engineer_notes == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_plan_models.py::TestEngineerNotes -x -q`
Expected: FAIL with `unexpected keyword argument 'engineer_notes'`

- [ ] **Step 3: Add field to Pydantic model**

In `src/api/models/plan.py`, modify the `MappingPlan` class (line 70-77):

```python
class MappingPlan(BaseModel):
    """The complete structured plan."""
    dataset_name: str
    understanding: DatasetUnderstanding
    active_columns: list[ColumnMapping]
    ignored_columns: list[ColumnMapping]
    static_properties: list[StaticProperty]
    global_notes: list[str]
    engineer_notes: list[str] = Field(default_factory=list)
```

- [ ] **Step 4: Add field to TypeScript type**

In `frontend/src/types/index.ts`, add to the `MappingPlan` interface:

```typescript
export interface MappingPlan {
  dataset_name: string;
  understanding: DatasetUnderstanding;
  active_columns: ColumnMapping[];
  ignored_columns: ColumnMapping[];
  static_properties: StaticProperty[];
  global_notes: string[];
  engineer_notes: string[];
}
```

- [ ] **Step 5: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_plan_models.py -x -q`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add src/api/models/plan.py frontend/src/types/index.ts tests/api/test_plan_models.py
git commit -m "feat(plan): add engineer_notes field to MappingPlan model"
```

---

### Task 2: Add feedback placeholder to prompt + agent

**Files:**
- Modify: `src/resources/prompts/mapping_plan_prompt.txt`
- Modify: `src/agents/mapping_plan_agent.py:131-148`

- [ ] **Step 1: Add feedback section to prompt template**

In `src/resources/prompts/mapping_plan_prompt.txt`, add before the `## Output` section (after `## Data Commons Discovery Results`):

```
## Engineer Feedback

{engineer_feedback}

If engineer feedback is provided above, consider it carefully when ranking candidates and assigning roles. The engineer has domain knowledge that may override statistical heuristics.
```

- [ ] **Step 2: Handle feedback in agent prompt population**

In `src/agents/mapping_plan_agent.py`, after line 148 (`populated = populated.replace("{candidate_pool_json}", candidate_pool_json)`), add:

```python
        # Inject engineer feedback if provided (for plan regeneration)
        engineer_feedback = ctx.session.state.get("engineer_feedback", "")
        if not engineer_feedback:
            engineer_feedback = "(No feedback provided — this is the initial plan generation.)"
        populated = populated.replace("{engineer_feedback}", engineer_feedback)
```

- [ ] **Step 3: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -5`
Expected: All PASS (prompt template change is backward compatible — placeholder just gets empty string)

- [ ] **Step 4: Commit**

```bash
git add src/resources/prompts/mapping_plan_prompt.txt src/agents/mapping_plan_agent.py
git commit -m "feat(plan): add engineer feedback injection to plan prompt"
```

---

### Task 3: API endpoints — regenerate + notes

**Files:**
- Modify: `src/api/routes/plan.py`

- [ ] **Step 1: Add regenerate endpoint**

Add to `src/api/routes/plan.py` after the `approve_plan` endpoint:

```python
class RegeneratePlanRequest(BaseModel):
    feedback: str
    deep: bool = False


@router.post("/runs/{run_id}/plan/regenerate")
async def regenerate_plan(run_id: str, body: RegeneratePlanRequest):
    """Regenerate the mapping plan with engineer feedback."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    if run.status == "running":
        raise HTTPException(status_code=409, detail="Pipeline is already running")

    run_dir = Path(run.run_dir)

    # Read phase1 state
    phase1_path = run_dir / "phase1_state.json"
    if not phase1_path.exists():
        raise HTTPException(status_code=400, detail="Phase 1 not completed")

    phase1 = json.loads(phase1_path.read_text())
    dataset_name = phase1.get("dataset_name", run.dataset_name)

    # Preserve existing engineer_notes
    output_dir = run_dir / "output" / dataset_name
    existing_notes = []
    plan_json_path = output_dir / "mapping_plan.json"
    if plan_json_path.exists():
        try:
            existing_plan = MappingPlan.model_validate_json(plan_json_path.read_text())
            existing_notes = existing_plan.engineer_notes
        except Exception:
            pass

    # Reset run state
    run.cancel_event = threading.Event()
    run.progress_queue = queue.Queue(maxsize=200)
    run.status = "running"
    run.error = None

    from src.api.services.pipeline_runner import PipelineConfig, launch_pipeline

    config = PipelineConfig(
        run_id=run_id,
        dataset_name=dataset_name,
        input_dir=str(run_dir / "input"),
        output_dir=str(run_dir / "output"),
        input_file=run.config.get("input_file"),
        model=run.config.get("model", "gemini-3.1-pro-preview"),
        skip_sampling=True,
        skip_schema_selection=True,
        plan_only=True,
    )

    # Build extra_state for regeneration
    extra_state = {
        "skeleton_summary": phase1.get("skeleton_summary", ""),
        "schema_category": phase1.get("schema_category", ""),
        "schema_vocab_content": phase1.get("schema_vocab_content", ""),
        "sampled_data_path": phase1.get("sampled_data_path", ""),
        "data_context": phase1.get("data_context", {}),
        "schemaorg_column_mappings": phase1.get("schemaorg_column_mappings", ""),
        "engineer_feedback": body.feedback,
        "engineer_notes_carry": json.dumps(existing_notes),
    }

    if not body.deep:
        # Quick regenerate: reuse existing candidate pool
        extra_state["candidate_pool"] = phase1.get("candidate_pool", "")
        # Skip candidate retrieval — go straight to plan agent
        config.extra_state = extra_state
    else:
        # Deep regenerate: re-retrieve candidates
        config.extra_state = extra_state

    thread = launch_pipeline(config, run.progress_queue, run_state=run)
    run.thread = thread

    return {"status": "regenerating"}
```

- [ ] **Step 2: Add notes endpoint**

Add after the regenerate endpoint:

```python
class AddNoteRequest(BaseModel):
    note: str


@router.post("/runs/{run_id}/plan/notes")
async def add_plan_note(run_id: str, body: AddNoteRequest):
    """Append a note to the plan's engineer_notes."""
    run = get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_dir = Path(run.run_dir)
    dataset_name = run.dataset_name
    output_dir = run_dir / "output" / dataset_name

    # Load current plan
    plan_json_path = output_dir / "mapping_plan.json"
    if not plan_json_path.exists():
        raise HTTPException(status_code=400, detail="No plan found")

    plan = MappingPlan.model_validate_json(plan_json_path.read_text())
    plan.engineer_notes.append(body.note)

    # Save updated plan
    plan_json_path.write_text(plan.model_dump_json(indent=2))

    # Also update phase1_state
    phase1_path = run_dir / "phase1_state.json"
    if phase1_path.exists():
        phase1 = json.loads(phase1_path.read_text())
        phase1["mapping_plan_json"] = plan.model_dump_json()
        phase1_path.write_text(json.dumps(phase1, indent=2))

    return {"notes": plan.engineer_notes}
```

- [ ] **Step 3: Run tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/ -x -q`
Expected: All PASS

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/plan.py
git commit -m "feat(api): add POST /plan/regenerate and POST /plan/notes endpoints"
```

---

### Task 4: Frontend API functions

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add regeneratePlan and addPlanNote functions**

Add to `frontend/src/lib/api.ts` after the existing `approvePlan` function:

```typescript
export async function regeneratePlan(
  runId: string,
  feedback: string,
  deep: boolean = false
): Promise<{ status: string }> {
  return request(`/runs/${runId}/plan/regenerate`, {
    method: "POST",
    body: JSON.stringify({ feedback, deep }),
  });
}

export async function addPlanNote(
  runId: string,
  note: string
): Promise<{ notes: string[] }> {
  return request(`/runs/${runId}/plan/notes`, {
    method: "POST",
    body: JSON.stringify({ note }),
  });
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(ui): add regeneratePlan and addPlanNote API functions"
```

---

### Task 5: PlanFeedback component

**Files:**
- Create: `frontend/src/components/PlanReview/PlanFeedback.tsx`

- [ ] **Step 1: Create the component**

Create `frontend/src/components/PlanReview/PlanFeedback.tsx`:

```tsx
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { RefreshCw, Plus, ChevronDown } from "lucide-react";

interface PlanFeedbackProps {
  notes: string[];
  onAddNote: (note: string) => void;
  onRegenerate: (feedback: string, deep: boolean) => void;
  regenerating: boolean;
}

export function PlanFeedback({ notes, onAddNote, onRegenerate, regenerating }: PlanFeedbackProps) {
  const [text, setText] = useState("");
  const [showDeepMenu, setShowDeepMenu] = useState(false);

  const handleAddNote = () => {
    if (!text.trim()) return;
    onAddNote(text.trim());
    setText("");
  };

  const handleRegenerate = (deep: boolean) => {
    if (!text.trim()) return;
    onRegenerate(text.trim(), deep);
    setText("");
    setShowDeepMenu(false);
  };

  return (
    <div className="space-y-3">
      {/* Existing notes */}
      {notes.length > 0 && (
        <div className="border rounded-lg p-3 bg-muted/20">
          <div className="text-sm font-medium mb-1.5">Your Notes</div>
          <ul className="space-y-1">
            {notes.map((note, i) => (
              <li key={i} className="text-sm text-muted-foreground flex gap-2">
                <span className="text-muted-foreground/50">-</span>
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Input area */}
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Feedback to regenerate the plan, or a note for the PVMAP generator..."
        rows={3}
        disabled={regenerating}
        className="text-sm"
      />

      {/* Action buttons */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handleAddNote}
          disabled={!text.trim() || regenerating}
          className="gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Note
        </Button>

        <div className="relative">
          <div className="flex">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleRegenerate(false)}
              disabled={!text.trim() || regenerating}
              className="gap-1.5 rounded-r-none"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${regenerating ? "animate-spin" : ""}`} />
              {regenerating ? "Regenerating..." : "Regenerate Plan"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDeepMenu(!showDeepMenu)}
              disabled={!text.trim() || regenerating}
              className="rounded-l-none border-l-0 px-1.5"
            >
              <ChevronDown className="w-3.5 h-3.5" />
            </Button>
          </div>
          {showDeepMenu && (
            <div className="absolute top-full mt-1 right-0 bg-background border rounded-md shadow-md z-10 py-1 min-w-[200px]">
              <button
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                onClick={() => handleRegenerate(false)}
              >
                Quick (re-rank only)
              </button>
              <button
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                onClick={() => handleRegenerate(true)}
              >
                Deep (re-retrieve candidates)
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
git add frontend/src/components/PlanReview/PlanFeedback.tsx
git commit -m "feat(ui): add PlanFeedback component with notes and regenerate actions"
```

---

### Task 6: Integrate PlanFeedback into ReviewPlanPage

**Files:**
- Modify: `frontend/src/pages/ReviewPlanPage.tsx`

- [ ] **Step 1: Add imports**

Add to the imports at the top of `ReviewPlanPage.tsx`:

```typescript
import { PlanFeedback } from "@/components/PlanReview/PlanFeedback";
import { regeneratePlan, addPlanNote } from "@/lib/api";
```

- [ ] **Step 2: Add state**

After the existing `stopping` state (around line 52), add:

```typescript
  const [regenerating, setRegenerating] = useState(false);
```

- [ ] **Step 3: Add handlers**

After the `handleStop` handler, add:

```typescript
  const handleAddNote = async (note: string) => {
    if (!runId) return;
    try {
      const result = await addPlanNote(runId, note);
      setPlan(prev => prev ? { ...prev, engineer_notes: result.notes } : prev);
      toast.success("Note added");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add note");
    }
  };

  const handleRegenerate = async (feedback: string, deep: boolean) => {
    if (!runId) return;
    setRegenerating(true);
    setPlanReady(false);
    try {
      await regeneratePlan(runId, feedback, deep);
      // WebSocket will notify when new plan is ready
      // planReady=false triggers the progress view
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to regenerate");
      setRegenerating(false);
      setPlanReady(true);
    }
  };
```

- [ ] **Step 4: Update WebSocket onComplete to handle regeneration**

Modify the `onComplete` callback in the `useWebSocket` call. Replace the existing onComplete:

```typescript
    onComplete: (event) => {
      if (event.result?.phase === "plan") {
        setPlanReady(true);
        setRegenerating(false);
        toast.info("Plan ready for review");
      } else {
        navigate(`/runs/${runId}/results`);
      }
    },
```

- [ ] **Step 5: Add PlanFeedback to the rendered page**

In the interactive plan review section, add the PlanFeedback component between the Global Notes section and the navigation buttons. Find the `{/* Navigation buttons */}` comment and add before it:

```tsx
      {/* Feedback & Notes Input */}
      <Card className="shadow-sm mb-4">
        <CardContent className="pt-5 pb-4">
          <h2 className="text-sm font-semibold mb-3">Feedback & Notes</h2>
          <PlanFeedback
            notes={plan.engineer_notes ?? []}
            onAddNote={handleAddNote}
            onRegenerate={handleRegenerate}
            regenerating={regenerating}
          />
        </CardContent>
      </Card>
```

- [ ] **Step 6: Verify build**

Run: `cd frontend && npm run build`
Expected: Build succeeds

- [ ] **Step 7: Run full backend test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q 2>&1 | tail -5`
Expected: All PASS

- [ ] **Step 8: Commit**

```bash
git add frontend/src/pages/ReviewPlanPage.tsx
git commit -m "feat(ui): integrate PlanFeedback into ReviewPlanPage with regenerate and notes"
```

---

## Summary

| Task | What it delivers | Files |
|------|-----------------|-------|
| 1 | `engineer_notes` field on MappingPlan (both Python + TS) | 3 files |
| 2 | Feedback injection into plan prompt | 2 files |
| 3 | API endpoints: POST /plan/regenerate + POST /plan/notes | 1 file |
| 4 | Frontend API functions | 1 file |
| 5 | PlanFeedback component | 1 file (new) |
| 6 | Integration into ReviewPlanPage | 1 file |

Total: 6 tasks, each independently testable and committable.
