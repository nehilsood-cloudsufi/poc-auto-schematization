# Plan Markdown View Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the overcomplicated Structured/JSON toggle in ReviewPlanPage with a single rendered-markdown view that shows the plan as readable text, is editable, and has a feedback box below.

**Architecture:** Backend generates markdown from plan JSON via an enhanced `_plan_to_markdown()`. A new API endpoint serves the markdown. Frontend replaces the two-tab view with: (1) a rendered markdown display with an "Edit" toggle to switch to a raw markdown textarea, (2) feedback box below. On save, the edited markdown is NOT parsed back to JSON — it's saved as-is for human reference, while the JSON remains the source of truth for the pipeline.

**Tech Stack:** Python (_plan_to_markdown), FastAPI (new endpoint), React + react-markdown (rendering), Tailwind (styling)

---

## File Structure

| File | Responsibility |
|------|---------------|
| `src/agents/mapping_plan_agent.py` | Enhance `_plan_to_markdown()` to include enriched fields |
| `src/api/routes/plan.py` | Add `GET /runs/{run_id}/plan/markdown` endpoint |
| `frontend/src/lib/api.ts` | Add `getPlanMarkdown()` API function |
| `frontend/src/pages/ReviewPlanPage.tsx` | Replace Structured/JSON with markdown view + edit mode |

---

### Task 1: Enhance `_plan_to_markdown()` for enriched fields

**Files:**
- Modify: `src/agents/mapping_plan_agent.py:43-113`
- Test: `tests/pipeline/plan/test_plan_markdown.py`

The current `_plan_to_markdown()` only handles base `MappingPlan` fields. It needs to also render `EnrichedMappingPlan` fields when present: composite_key, statvar_blueprint, value_dictionaries, column_relationships, place_resolution, time_resolution.

- [ ] **Step 1: Write test for enriched markdown output**

```python
# tests/pipeline/plan/test_plan_markdown.py
import pytest
from src.agents.mapping_plan_agent import _plan_to_markdown
from src.api.models.plan import (
    MappingPlan, EnrichedMappingPlan, DatasetUnderstanding,
    ColumnMapping, ColumnRole, PropertyValueCandidate, CandidateSource,
    StaticProperty, StatVarBlueprint, StatVarProperty,
    ValueDictionary, ValueMapping, ColumnRelationship, RelationshipType,
    PlaceResolution, TimeResolution,
)


def _base_plan():
    return dict(
        dataset_name="test",
        understanding=DatasetUnderstanding(archetype="Long", observation_grain="row", key_insight="test"),
        active_columns=[
            ColumnMapping(
                column_name="Year", role=ColumnRole.OBSERVATION_DATE,
                candidates=[PropertyValueCandidate(
                    property="observationDate", value_expression="[NUMBER]",
                    confidence=0.95, source=CandidateSource.SCHEMA_ORG, reason="YYYY format",
                )],
                evidence="Integer, YYYY", selected_index=0,
            ),
        ],
        ignored_columns=[],
        static_properties=[],
        global_notes=["A note"],
    )


def test_base_plan_markdown():
    plan = MappingPlan(**_base_plan())
    md = _plan_to_markdown(plan)
    assert "# Mapping Plan: test" in md
    assert "## Dataset Understanding" in md
    assert "## Active Column Mappings" in md
    assert "`Year`" in md
    assert "observationDate" in md
    assert "A note" in md


def test_enriched_plan_includes_blueprint():
    plan = EnrichedMappingPlan(
        **_base_plan(),
        statvar_blueprint=StatVarBlueprint(
            base_properties=[StatVarProperty(name="populationType", value="dcs:Person")],
            constraint_columns=["SEX"],
            measure_columns=["Value"],
        ),
        value_dictionaries=[
            ValueDictionary(column_name="SEX", dc_property="gender", mappings=[
                ValueMapping(raw_value="M", dcid="dcs:Male", action="MAP", reason="Male"),
                ValueMapping(raw_value="T", dcid=None, action="DROP_CONSTRAINT", reason="Total"),
            ], total_indicators=["T"]),
        ],
        column_relationships=[
            ColumnRelationship(column_a="A", column_b="B",
                relationship=RelationshipType.CO_REFERENT, strength=0.99,
                evidence="1:1", pvmap_implication="Use A, ignore B"),
        ],
        composite_key=["Year", "Country"],
    )
    md = _plan_to_markdown(plan)
    # Enriched sections present
    assert "## StatVar Blueprint" in md
    assert "populationType" in md and "dcs:Person" in md
    assert "## Value Dictionaries" in md
    assert "M" in md and "dcs:Male" in md
    assert "DROP" in md  # T -> DROP_CONSTRAINT
    assert "## Column Relationships" in md
    assert "co_referent" in md or "CO_REFERENT" in md or "co-referent" in md.lower()
    assert "## Composite Key" in md or "Composite Key" in md
    assert "Year" in md and "Country" in md


def test_base_plan_no_enriched_sections():
    """Base MappingPlan should NOT have enriched sections."""
    plan = MappingPlan(**_base_plan())
    md = _plan_to_markdown(plan)
    assert "StatVar Blueprint" not in md
    assert "Value Dictionaries" not in md
    assert "Column Relationships" not in md
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_markdown.py -x -q`
Expected: `test_enriched_plan_includes_blueprint` FAILS (enriched sections missing from markdown)

- [ ] **Step 3: Enhance `_plan_to_markdown()` in `src/agents/mapping_plan_agent.py`**

After the existing "Global Notes" section (line 111), add enriched-plan sections using `hasattr` checks:

```python
    # --- Enriched plan sections (only if EnrichedMappingPlan) ---

    # Composite Key
    if hasattr(plan, 'composite_key') and plan.composite_key:
        lines.append("## Composite Key")
        lines.append(f"Columns that uniquely identify each row: `{'`, `'.join(plan.composite_key)}`")
        lines.append("")

    # StatVar Blueprint
    if hasattr(plan, 'statvar_blueprint') and plan.statvar_blueprint:
        bp = plan.statvar_blueprint
        lines.append("## StatVar Blueprint")
        lines.append("")
        lines.append("**Base Properties:**")
        for p in bp.base_properties:
            lines.append(f"- `{p.name}`: `{p.value}`")
        lines.append("")
        if bp.constraint_columns:
            lines.append(f"**Constraint Columns:** {', '.join(f'`{c}`' for c in bp.constraint_columns)}")
        if bp.measure_columns:
            lines.append(f"**Measure Columns:** {', '.join(f'`{c}`' for c in bp.measure_columns)}")
        lines.append("")

    # Value Dictionaries
    if hasattr(plan, 'value_dictionaries') and plan.value_dictionaries:
        lines.append("## Value Dictionaries")
        lines.append("")
        for vd in plan.value_dictionaries:
            lines.append(f"### `{vd.column_name}` (property: `{vd.dc_property}`)")
            lines.append("")
            lines.append("| Raw Value | Action | DCID | Reason |")
            lines.append("|-----------|--------|------|--------|")
            for m in vd.mappings:
                dcid = m.dcid or "—"
                lines.append(f"| `{m.raw_value}` | {m.action} | `{dcid}` | {m.reason} |")
            lines.append("")

    # Column Relationships
    if hasattr(plan, 'column_relationships') and plan.column_relationships:
        significant = [r for r in plan.column_relationships if r.relationship.value != "independent"]
        if significant:
            lines.append("## Column Relationships")
            lines.append("")
            lines.append("| Column A | Relationship | Column B | Evidence |")
            lines.append("|----------|-------------|----------|----------|")
            for r in significant:
                rel_label = r.relationship.value.replace("_", " ")
                lines.append(f"| `{r.column_a}` | {rel_label} | `{r.column_b}` | {r.evidence} |")
            lines.append("")

    # Place Resolution
    if hasattr(plan, 'place_resolution') and plan.place_resolution:
        pr = plan.place_resolution
        lines.append("## Place Resolution")
        lines.append(f"- **Column:** `{pr.column_name}`")
        lines.append(f"- **Format:** {pr.format_detected}")
        lines.append(f"- **Prefix:** `{pr.prefix_rule}`")
        if pr.pad_zeros:
            lines.append(f"- **Zero-pad to:** {pr.pad_zeros} digits")
        lines.append("")

    # Time Resolution
    if hasattr(plan, 'time_resolution') and plan.time_resolution:
        tr = plan.time_resolution
        lines.append("## Time Resolution")
        lines.append(f"- **Columns:** {', '.join(f'`{c}`' for c in tr.columns)}")
        lines.append(f"- **Format:** {tr.format_detected}")
        lines.append(f"- **Rule:** {tr.normalization_rule}")
        lines.append("")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/pipeline/plan/test_plan_markdown.py -x -q`
Expected: All 3 PASS

- [ ] **Step 5: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`

- [ ] **Step 6: Commit**

```bash
git add src/agents/mapping_plan_agent.py tests/pipeline/plan/test_plan_markdown.py
git commit -m "feat(plan): enhance _plan_to_markdown with enriched plan sections"
```

---

### Task 2: Add markdown API endpoint

**Files:**
- Modify: `src/api/routes/plan.py`

Add an endpoint that serves the plan as rendered markdown text.

- [ ] **Step 1: Add the endpoint to `src/api/routes/plan.py`**

Add after the existing `get_plan` endpoint:

```python
@router.get("/runs/{run_id}/plan/markdown")
async def get_plan_markdown(run_id: str, request: Request):
    """Return the mapping plan as human-readable markdown text."""
    run = get_or_load_run(run_id, request.app.state.output_dir)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")

    run_dir = Path(run.run_dir)
    dataset_name = run.dataset_name

    # Try reading the markdown file from disk first
    md_path = run_dir / "output" / dataset_name / "mapping_plan.md"
    if md_path.exists():
        return {"markdown": md_path.read_text()}

    # Fallback: generate markdown from JSON plan
    json_path = run_dir / "output" / dataset_name / "mapping_plan.json"
    if json_path.exists():
        from src.agents.mapping_plan_agent import _plan_to_markdown
        raw = json_path.read_text()
        plan_data = json.loads(raw)
        if "statvar_blueprint" in plan_data:
            from src.api.models.plan import EnrichedMappingPlan
            plan = EnrichedMappingPlan.model_validate(plan_data)
        else:
            plan = MappingPlan.model_validate(plan_data)
        md = _plan_to_markdown(plan)
        # Cache to disk for next time
        md_path.write_text(md)
        return {"markdown": md}

    # Fallback: check phase1_state
    phase1_path = run_dir / "phase1_state.json"
    if phase1_path.exists():
        phase1 = json.loads(phase1_path.read_text())
        plan_json = phase1.get("mapping_plan_json", "")
        if plan_json:
            from src.agents.mapping_plan_agent import _plan_to_markdown
            plan_data = json.loads(plan_json)
            if "statvar_blueprint" in plan_data:
                from src.api.models.plan import EnrichedMappingPlan
                plan = EnrichedMappingPlan.model_validate(plan_data)
            else:
                plan = MappingPlan.model_validate(plan_data)
            return {"markdown": _plan_to_markdown(plan)}

    raise HTTPException(status_code=404, detail="No plan found for this run")
```

- [ ] **Step 2: Test the endpoint**

Run: `curl -s http://localhost:8000/api/runs/0731daf6a7c8/plan/markdown | python3 -c "import json,sys; d=json.load(sys.stdin); print(d['markdown'][:200])"`
Expected: Markdown text starting with `# Mapping Plan:`

- [ ] **Step 3: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/plan.py
git commit -m "feat(api): add GET /runs/{run_id}/plan/markdown endpoint"
```

---

### Task 3: Add `getPlanMarkdown()` to API client

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add the function**

Add after the existing `getPlan` function:

```typescript
export async function getPlanMarkdown(
  runId: string
): Promise<string> {
  const data = await request<{ markdown: string }>(`/runs/${runId}/plan/markdown`);
  return data.markdown;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat(ui): add getPlanMarkdown API client function"
```

---

### Task 4: Replace ReviewPlanPage with markdown view

**Files:**
- Modify: `frontend/src/pages/ReviewPlanPage.tsx`

Replace the Structured/JSON toggle with a single view:
1. **Read mode (default):** Rendered markdown with proper formatting (headings, tables, code blocks, bold)
2. **Edit mode:** Raw markdown textarea (monospace, full height)
3. **Feedback box:** Always visible below, with Regenerate + Add Note

- [ ] **Step 1: Install react-markdown**

```bash
cd frontend && npm install react-markdown
```

- [ ] **Step 2: Rewrite the main render section of ReviewPlanPage**

Replace everything from the `{/* View mode toggle */}` section through the `{/* end of structured/json views */}` closing `</>` with:

```tsx
// Add at top of file imports:
import ReactMarkdown from "react-markdown";

// New state (replace viewMode/jsonText/jsonDirty/jsonError/savingJson):
const [markdown, setMarkdown] = useState("");
const [editMode, setEditMode] = useState(false);
const [editText, setEditText] = useState("");
const [savingEdit, setSavingEdit] = useState(false);

// Load markdown instead of JSON in the mount effect:
// Replace the existing getPlan().then(...) mount effect with:
useEffect(() => {
  if (!runId) return;
  // Load both plan JSON (for approve/regenerate) and markdown (for display)
  getPlan(runId)
    .then((data) => {
      if (data && data.active_columns) {
        setPlan(data);
        setPlanReady(true);
      }
    })
    .catch(() => {
      getRun(runId).then((run) => {
        if (run.status === "plan_ready" || run.status === "stopped" || run.status === "error") {
          setPlanReady(true);
          setPlanError("Plan generation failed. Try 'Regenerate' below.");
        }
      }).catch(() => {});
    });

  getPlanMarkdown(runId)
    .then((md) => setMarkdown(md))
    .catch(() => {}); // Will fall back to plan JSON display
}, [runId]);
```

For the main render (after `planReady` and `plan` are set):

```tsx
{/* Markdown Plan View */}
<Card className="shadow-sm mb-4">
  <CardContent className="pt-5 pb-4">
    <div className="flex items-center justify-between mb-3">
      <h2 className="text-sm font-semibold">Mapping Plan</h2>
      <div className="flex items-center gap-2">
        {editMode && (
          <Button
            variant="outline"
            size="sm"
            onClick={async () => {
              setSavingEdit(true);
              // Save edited markdown to a note (feedback), not as plan JSON
              try {
                await addPlanNote(runId!, editText.slice(0, 500) + "\n[Full edit saved]");
                setMarkdown(editText);
                setEditMode(false);
                toast.success("Edit saved as note");
              } catch { toast.error("Failed to save"); }
              finally { setSavingEdit(false); }
            }}
            disabled={savingEdit}
            className="gap-1.5"
          >
            <Save className="w-3.5 h-3.5" />
            {savingEdit ? "Saving..." : "Save"}
          </Button>
        )}
        <Button
          variant="ghost"
          size="sm"
          onClick={() => {
            if (!editMode) setEditText(markdown);
            setEditMode(!editMode);
          }}
          className="gap-1.5"
        >
          {editMode ? (
            <><Table2 className="w-3.5 h-3.5" /> View</>
          ) : (
            <><Code2 className="w-3.5 h-3.5" /> Edit</>
          )}
        </Button>
      </div>
    </div>

    {editMode ? (
      <textarea
        value={editText}
        onChange={(e) => setEditText(e.target.value)}
        className="w-full font-mono text-xs leading-relaxed p-3 rounded-md border bg-muted/30 resize-vertical focus:outline-none focus:ring-2 focus:ring-ring"
        style={{ minHeight: "400px", height: "60vh", maxHeight: "80vh" }}
        spellCheck={false}
      />
    ) : (
      <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-base prose-h1:text-lg prose-h2:text-base prose-h3:text-sm prose-table:text-xs prose-code:text-xs prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded">
        <ReactMarkdown>{markdown || "No plan content available."}</ReactMarkdown>
      </div>
    )}
  </CardContent>
</Card>
```

Remove: `ActiveMappingsTable`, `StaticProperties`, `IgnoredColumns`, `ColumnDetail` imports and all the structured view JSX. Remove `viewMode`, `jsonText`, `jsonDirty`, `jsonError`, `savingJson` state. Remove `handleJsonChange`, `handleSaveJson`, `handleColumnUpdate`, `handleStaticUpdate` handlers. Remove `skeletonWidths8`, `skeletonWidths12`, `ambiguousCount`.

Keep: `PlanFeedback`, `handleRegenerate`, `handleAddNote`, `handleApprove`, `handleStop`.

- [ ] **Step 3: Build and verify**

```bash
cd frontend && npm run build
```
Expected: Build succeeds with no TS errors.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/pages/ReviewPlanPage.tsx frontend/package.json frontend/package-lock.json
git commit -m "feat(ui): replace structured/JSON views with rendered markdown plan view

Single view with View/Edit toggle. Markdown rendered via react-markdown
with Tailwind prose styling. Edit mode shows raw markdown textarea.
Removed ActiveMappingsTable, StaticProperties, IgnoredColumns from
this page (components kept for potential reuse elsewhere)."
```

---

## Execution Order

```
Task 1 (enhance _plan_to_markdown) — no deps
Task 2 (API endpoint) — depends on Task 1
Task 3 (API client) — no deps
Task 4 (frontend rewrite) — depends on Tasks 2 + 3
```

Tasks 1+3 can run in parallel. Task 2 depends on 1. Task 4 depends on 2+3.
