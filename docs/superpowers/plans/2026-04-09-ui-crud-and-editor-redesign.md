# UI Run Management & Editor Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add run CRUD (archive/delete/rename+notes) and restructure the Results page into a two-panel layout with AG Grid spreadsheet editing for PVMAP/Metadata, separated from read-only output files.

**Architecture:** Backend extends existing `run_info.json` with `display_name`, `notes`, `archived` fields. Three new endpoints (PATCH, DELETE, POST archive). Frontend replaces CsvEditor with AG Grid for input files, restructures ResultsPage into input panel + action bar + output panel. HistoryPage gets archive/unarchive with filtering.

**Tech Stack:** FastAPI (backend), React + TypeScript (frontend), AG Grid Community (MIT, spreadsheet), existing Tailwind + shadcn/ui component library.

**Spec:** `docs/superpowers/specs/2026-04-09-ui-crud-and-editor-redesign.md`

---

## File Map

### Files to Create

| File | Responsibility |
|------|---------------|
| `frontend/src/components/SpreadsheetEditor.tsx` | AG Grid wrapper with toolbar (add/delete row+col, undo/redo, change tracking) |
| `frontend/src/components/ConfirmDeleteModal.tsx` | Modal dialog for permanent run deletion |
| `tests/api/test_run_management.py` | Backend tests for PATCH, DELETE, archive endpoints |

### Files to Modify

| File | Changes |
|------|---------|
| `src/api/routes/runs.py` | Add PATCH, DELETE, archive endpoints; modify GET list to filter archived |
| `src/api/services/run_state.py` | Add `read_run_info()`, `write_run_info()` helpers |
| `src/api/services/file_manager.py` | Add `delete_run_directory()` function |
| `src/api/routes/revalidate.py` | Return `output_files` list; ensure stat_var_processor outputs are written |
| `frontend/package.json` | Add `ag-grid-community`, `ag-grid-react` |
| `frontend/src/types/index.ts` | Add `display_name`, `notes`, `archived` to `Run`; add `UpdateRunRequest` |
| `frontend/src/lib/api.ts` | Add `updateRun()`, `archiveRun()`, `deleteRun()` |
| `frontend/src/pages/ResultsPage.tsx` | Two-panel layout, header with rename/notes/delete, save & revalidate flow |
| `frontend/src/pages/HistoryPage.tsx` | Archive button per row, "Show archived" toggle, muted styling |
| `frontend/src/components/OutputViewer.tsx` | Remove PVMAP and Metadata tabs, keep remaining 6 output file types |

---

## Task 1: Backend — Run Info Helpers

**Files:**
- Modify: `src/api/services/run_state.py` (add helpers after line 156)
- Test: `tests/api/test_run_management.py` (create)

- [ ] **Step 1: Write the failing test for read_run_info**

Create `tests/api/test_run_management.py`:

```python
"""Tests for run management: metadata read/write, archive, delete."""
import json
import os
import shutil
import tempfile

import pytest


@pytest.fixture
def run_dir():
    """Create a temporary run directory with run_info.json."""
    d = tempfile.mkdtemp()
    run_id = "test-run-123"
    run_path = os.path.join(d, run_id)
    os.makedirs(os.path.join(run_path, "input"))
    os.makedirs(os.path.join(run_path, "output", "test_dataset"))
    info = {"run_id": run_id, "dataset_name": "test_dataset"}
    with open(os.path.join(run_path, "run_info.json"), "w") as f:
        json.dump(info, f)
    yield run_path
    shutil.rmtree(d, ignore_errors=True)


def test_read_run_info_returns_defaults_for_missing_fields(run_dir):
    from src.api.services.run_state import read_run_info

    info = read_run_info(run_dir)
    assert info["dataset_name"] == "test_dataset"
    assert info["display_name"] == "test_dataset"  # defaults to dataset_name
    assert info["notes"] == ""
    assert info["archived"] is False


def test_read_run_info_missing_file(run_dir):
    from src.api.services.run_state import read_run_info

    os.remove(os.path.join(run_dir, "run_info.json"))
    info = read_run_info(run_dir)
    assert info == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_management.py::test_read_run_info_returns_defaults_for_missing_fields -x -q`
Expected: FAIL with `ImportError` or `cannot import name 'read_run_info'`

- [ ] **Step 3: Implement read_run_info and write_run_info**

Add to `src/api/services/run_state.py` after the `delete_run()` function (after line 156):

```python
def read_run_info(run_dir: str) -> dict:
    """Read run_info.json from a run directory, with defaults for new fields."""
    info_path = os.path.join(run_dir, "run_info.json")
    if not os.path.exists(info_path):
        return {}
    with open(info_path) as f:
        info = json.load(f)
    # Apply defaults for new fields
    info.setdefault("display_name", info.get("dataset_name", ""))
    info.setdefault("notes", "")
    info.setdefault("archived", False)
    return info


def write_run_info(run_dir: str, updates: dict) -> dict:
    """Update run_info.json with the given fields. Returns updated info."""
    info = read_run_info(run_dir)
    if not info:
        return {}
    info.update(updates)
    info_path = os.path.join(run_dir, "run_info.json")
    with open(info_path, "w") as f:
        json.dump(info, f, indent=2)
    return info
```

Also add `import json` at the top of the file if not already present.

- [ ] **Step 4: Write test for write_run_info**

Add to `tests/api/test_run_management.py`:

```python
def test_write_run_info_updates_fields(run_dir):
    from src.api.services.run_state import read_run_info, write_run_info

    result = write_run_info(run_dir, {"display_name": "My Custom Name", "notes": "Test notes"})
    assert result["display_name"] == "My Custom Name"
    assert result["notes"] == "Test notes"

    # Verify persisted
    info = read_run_info(run_dir)
    assert info["display_name"] == "My Custom Name"
    assert info["notes"] == "Test notes"


def test_write_run_info_preserves_existing_fields(run_dir):
    from src.api.services.run_state import read_run_info, write_run_info

    write_run_info(run_dir, {"notes": "Some note"})
    info = read_run_info(run_dir)
    assert info["run_id"] == "test-run-123"
    assert info["dataset_name"] == "test_dataset"
    assert info["notes"] == "Some note"
```

- [ ] **Step 5: Run all tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_management.py -x -q`
Expected: 4 passed

- [ ] **Step 6: Commit**

```bash
git add tests/api/test_run_management.py src/api/services/run_state.py
git commit -m "feat(api): add read_run_info/write_run_info helpers for run metadata"
```

---

## Task 2: Backend — PATCH /runs/{id} Endpoint

**Files:**
- Modify: `src/api/routes/runs.py` (add endpoint after `start_run`)
- Test: `tests/api/test_run_management.py` (extend)

- [ ] **Step 1: Write the failing test**

Add to `tests/api/test_run_management.py`:

```python
import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def app_client(run_dir, monkeypatch):
    """Create a test client with UI_OUTPUT_DIR pointing to our temp dir."""
    parent_dir = os.path.dirname(run_dir)
    monkeypatch.setattr("src.api.config.UI_OUTPUT_DIR", parent_dir)

    from src.api.main import app
    return TestClient(app)


def test_patch_run_updates_display_name(app_client, run_dir):
    run_id = os.path.basename(run_dir)
    resp = app_client.patch(f"/api/runs/{run_id}", json={"display_name": "New Name"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["display_name"] == "New Name"


def test_patch_run_updates_notes(app_client, run_dir):
    run_id = os.path.basename(run_dir)
    resp = app_client.patch(f"/api/runs/{run_id}", json={"notes": "My notes here"})
    assert resp.status_code == 200
    assert resp.json()["notes"] == "My notes here"


def test_patch_run_404_for_unknown(app_client):
    resp = app_client.patch("/api/runs/nonexistent", json={"display_name": "X"})
    assert resp.status_code == 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_management.py::test_patch_run_updates_display_name -x -q`
Expected: FAIL with 404 or 405 (endpoint doesn't exist)

- [ ] **Step 3: Implement PATCH endpoint**

Add to `src/api/routes/runs.py` after the `start_run` function. First add the Pydantic model:

```python
from pydantic import BaseModel
from typing import Optional

class UpdateRunRequest(BaseModel):
    display_name: Optional[str] = None
    notes: Optional[str] = None
```

Then add the endpoint:

```python
@router.patch("/runs/{run_id}")
async def update_run(run_id: str, req: UpdateRunRequest):
    """Update run metadata (display name, notes)."""
    from src.api.services.run_state import read_run_info, write_run_info

    run_dir = os.path.join(UI_OUTPUT_DIR, run_id)
    info = read_run_info(run_dir)
    if not info:
        raise HTTPException(status_code=404, detail="Run not found")

    updates = {}
    if req.display_name is not None:
        updates["display_name"] = req.display_name
    if req.notes is not None:
        updates["notes"] = req.notes

    if not updates:
        return info

    updated = write_run_info(run_dir, updates)
    return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_management.py -x -q`
Expected: 7 passed

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/runs.py tests/api/test_run_management.py
git commit -m "feat(api): add PATCH /runs/{id} for updating display_name and notes"
```

---

## Task 3: Backend — Archive Endpoint

**Files:**
- Modify: `src/api/routes/runs.py` (add archive endpoint)
- Modify: `src/api/routes/runs.py` (modify `list_all_runs` to filter archived)
- Test: `tests/api/test_run_management.py` (extend)

- [ ] **Step 1: Write failing tests**

Add to `tests/api/test_run_management.py`:

```python
def test_archive_run_toggles_archived(app_client, run_dir):
    run_id = os.path.basename(run_dir)
    # Archive
    resp = app_client.post(f"/api/runs/{run_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived"] is True

    # Unarchive
    resp = app_client.post(f"/api/runs/{run_id}/archive")
    assert resp.status_code == 200
    assert resp.json()["archived"] is False


def test_list_runs_excludes_archived_by_default(app_client, run_dir):
    run_id = os.path.basename(run_dir)
    # Archive the run
    app_client.post(f"/api/runs/{run_id}/archive")

    # List without include_archived — should not include it
    resp = app_client.get("/api/runs")
    assert resp.status_code == 200
    run_ids = [r["run_id"] for r in resp.json()]
    assert run_id not in run_ids


def test_list_runs_includes_archived_when_requested(app_client, run_dir):
    run_id = os.path.basename(run_dir)
    app_client.post(f"/api/runs/{run_id}/archive")

    resp = app_client.get("/api/runs?include_archived=true")
    assert resp.status_code == 200
    run_ids = [r["run_id"] for r in resp.json()]
    assert run_id in run_ids
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_management.py::test_archive_run_toggles_archived -x -q`
Expected: FAIL with 404 or 405

- [ ] **Step 3: Implement archive endpoint and modify list**

Add archive endpoint to `src/api/routes/runs.py`:

```python
@router.post("/runs/{run_id}/archive")
async def archive_run(run_id: str):
    """Toggle archived status for a run."""
    from src.api.services.run_state import read_run_info, write_run_info

    run_dir = os.path.join(UI_OUTPUT_DIR, run_id)
    info = read_run_info(run_dir)
    if not info:
        raise HTTPException(status_code=404, detail="Run not found")

    new_archived = not info.get("archived", False)
    write_run_info(run_dir, {"archived": new_archived})
    return {"archived": new_archived}
```

Modify `list_all_runs()` to accept the query param and include new fields. Change the function signature and add filtering:

```python
@router.get("/runs")
async def list_all_runs(include_archived: bool = False):
    """List all runs, optionally including archived ones."""
    from src.api.services.run_state import read_run_info

    active = list_runs()
    active_ids = {r.run_id for r in active}

    result = []
    for r in active:
        run_dir = os.path.join(UI_OUTPUT_DIR, r.run_id)
        info = read_run_info(run_dir)
        archived = info.get("archived", False) if info else False
        if not include_archived and archived:
            continue
        result.append({
            "run_id": r.run_id,
            "dataset_name": r.dataset_name,
            "status": r.status,
            "display_name": info.get("display_name", r.dataset_name) if info else r.dataset_name,
            "notes": info.get("notes", "") if info else "",
            "archived": archived,
            "validation_passed": (r.result or {}).get("validation_passed"),
            "result": r.result,
        })

    historical = discover_historical_runs(UI_OUTPUT_DIR)
    for h in historical:
        if h["run_id"] in active_ids:
            continue
        run_dir = os.path.join(UI_OUTPUT_DIR, h["run_id"])
        info = read_run_info(run_dir)
        archived = info.get("archived", False) if info else False
        if not include_archived and archived:
            continue
        h["display_name"] = info.get("display_name", h.get("dataset_name", "")) if info else h.get("dataset_name", "")
        h["notes"] = info.get("notes", "") if info else ""
        h["archived"] = archived
        result.append(h)

    return result
```

- [ ] **Step 4: Run all tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_management.py -x -q`
Expected: 10 passed

- [ ] **Step 5: Commit**

```bash
git add src/api/routes/runs.py tests/api/test_run_management.py
git commit -m "feat(api): add archive/unarchive endpoint and filter archived from run list"
```

---

## Task 4: Backend — DELETE /runs/{id} Endpoint

**Files:**
- Modify: `src/api/routes/runs.py` (add DELETE endpoint)
- Modify: `src/api/services/file_manager.py` (add `delete_run_directory`)
- Test: `tests/api/test_run_management.py` (extend)

- [ ] **Step 1: Write failing tests**

Add to `tests/api/test_run_management.py`:

```python
def test_delete_run_removes_directory(app_client, run_dir):
    run_id = os.path.basename(run_dir)
    resp = app_client.delete(
        f"/api/runs/{run_id}",
        headers={"X-Confirm-Delete": "true"},
    )
    assert resp.status_code == 204
    assert not os.path.exists(run_dir)


def test_delete_run_requires_confirmation_header(app_client, run_dir):
    run_id = os.path.basename(run_dir)
    resp = app_client.delete(f"/api/runs/{run_id}")
    assert resp.status_code == 400
    assert os.path.exists(run_dir)  # Not deleted


def test_delete_run_404_for_unknown(app_client):
    resp = app_client.delete(
        "/api/runs/nonexistent",
        headers={"X-Confirm-Delete": "true"},
    )
    assert resp.status_code == 404
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_management.py::test_delete_run_removes_directory -x -q`
Expected: FAIL with 405 (method not allowed)

- [ ] **Step 3: Implement delete_run_directory helper**

Add to `src/api/services/file_manager.py` after `cleanup_old_runs()`:

```python
def delete_run_directory(run_dir: str) -> bool:
    """Permanently delete a run directory. Returns True if deleted."""
    if not os.path.isdir(run_dir):
        return False
    shutil.rmtree(run_dir)
    return True
```

Add `import shutil` at top if not already present.

- [ ] **Step 4: Implement DELETE endpoint**

Add to `src/api/routes/runs.py`:

```python
from fastapi import Header, Response

@router.delete("/runs/{run_id}")
async def delete_run_endpoint(
    run_id: str,
    response: Response,
    x_confirm_delete: Optional[str] = Header(None),
):
    """Permanently delete a run and all its files."""
    if x_confirm_delete != "true":
        raise HTTPException(status_code=400, detail="Missing X-Confirm-Delete: true header")

    run_dir = os.path.join(UI_OUTPUT_DIR, run_id)
    if not os.path.isdir(run_dir):
        raise HTTPException(status_code=404, detail="Run not found")

    from src.api.services.file_manager import delete_run_directory
    delete_run_directory(run_dir)

    # Also remove from in-memory tracking
    delete_run(run_id)

    response.status_code = 204
    return Response(status_code=204)
```

- [ ] **Step 5: Run all tests**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/api/test_run_management.py -x -q`
Expected: 13 passed

- [ ] **Step 6: Run full test suite to check for regressions**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All existing tests pass

- [ ] **Step 7: Commit**

```bash
git add src/api/routes/runs.py src/api/services/file_manager.py tests/api/test_run_management.py
git commit -m "feat(api): add DELETE /runs/{id} for permanent run removal"
```

---

## Task 5: Backend — Improve Revalidation Response

**Files:**
- Modify: `src/api/routes/revalidate.py`
- Test: `tests/api/test_run_management.py` (extend)

- [ ] **Step 1: Read the current revalidation service**

Read `src/api/services/revalidation.py` (or `revalidation_service.py`) to understand what `revalidate_pvmap()` returns and how `stat_var_processor` is invoked. Understand the current output file handling.

- [ ] **Step 2: Modify revalidation endpoint to return output_files**

Update `src/api/routes/revalidate.py` to include the list of regenerated output files in the response:

```python
@router.post("/runs/{run_id}/revalidate")
async def revalidate(run_id: str):
    """Revalidate the PVMAP for a run, regenerating output files."""
    run = get_or_load_run(run_id, UI_OUTPUT_DIR)
    if not run:
        raise HTTPException(status_code=404, detail="Run not found")

    input_csv = os.path.join(run.run_dir, "input", "input.csv")
    if not os.path.exists(input_csv):
        raise HTTPException(status_code=404, detail="Input CSV not found")

    dataset_name = run.dataset_name
    output_dir = os.path.join(run.run_dir, "output", dataset_name)
    pvmap_path = os.path.join(output_dir, "generated_pvmap.csv")
    if not os.path.exists(pvmap_path):
        raise HTTPException(status_code=404, detail="PVMAP not found")

    metadata_path = os.path.join(output_dir, "output_metadata.csv")
    if not os.path.exists(metadata_path):
        metadata_path = None

    result = revalidate_pvmap(input_csv, pvmap_path, metadata_path, output_dir)

    # Collect list of output files that were regenerated
    from src.api.services.file_manager import get_output_files
    output_files = list(get_output_files(output_dir).keys())

    if "error" in result:
        return {"success": False, "error": result["error"], "output_files": output_files}

    return {
        "success": True,
        "data_rows": result.get("data_rows", 0),
        "passed": result.get("passed", False),
        "output_files": output_files,
    }
```

- [ ] **Step 3: Run full test suite**

Run: `PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q`
Expected: All tests pass

- [ ] **Step 4: Commit**

```bash
git add src/api/routes/revalidate.py
git commit -m "fix(api): include output_files list in revalidation response"
```

---

## Task 6: Frontend — Install AG Grid + TypeScript Types + API Client

**Files:**
- Modify: `frontend/package.json` (add deps)
- Modify: `frontend/src/types/index.ts` (extend Run, add UpdateRunRequest)
- Modify: `frontend/src/lib/api.ts` (add 3 new functions)

- [ ] **Step 1: Install AG Grid**

```bash
cd frontend && npm install ag-grid-community ag-grid-react
```

- [ ] **Step 2: Update TypeScript types**

In `frontend/src/types/index.ts`, extend the `Run` interface (around line 34-44) to add 3 new optional fields:

```typescript
export interface Run {
  run_id: string;
  dataset_name: string;
  status: string;
  result?: PipelineResult;
  error?: string;
  config?: Record<string, unknown>;
  validation_passed?: boolean;
  display_name?: string;
  notes?: string;
  archived?: boolean;
}
```

Add `UpdateRunRequest` interface after the `Run` interface:

```typescript
export interface UpdateRunRequest {
  display_name?: string;
  notes?: string;
}
```

- [ ] **Step 3: Add API client functions**

In `frontend/src/lib/api.ts`, add these functions after the existing `getPreview()` function (after line 170):

Also update the existing `listRuns` function to accept the archive filter parameter:

```typescript
export async function listRuns(includeArchived = false): Promise<Run[]> {
  const params = includeArchived ? "?include_archived=true" : "";
  return request<Run[]>(`/api/runs${params}`);
}
```

Then add the new functions:

```typescript
export async function updateRun(
  runId: string,
  data: UpdateRunRequest,
): Promise<Run> {
  return request<Run>(`/api/runs/${runId}`, {
    method: "PATCH",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(data),
  });
}

export async function archiveRun(
  runId: string,
): Promise<{ archived: boolean }> {
  return request<{ archived: boolean }>(`/api/runs/${runId}/archive`, {
    method: "POST",
  });
}

export async function deleteRun(runId: string): Promise<void> {
  const resp = await fetch(`/api/runs/${runId}`, {
    method: "DELETE",
    headers: { "X-Confirm-Delete": "true" },
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error(detail.detail || `Delete failed: ${resp.status}`);
  }
}
```

Add the `UpdateRunRequest` import at the top:

```typescript
import type { Run, UpdateRunRequest } from "../types";
```

- [ ] **Step 4: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds with no type errors

- [ ] **Step 5: Commit**

```bash
cd frontend && git add package.json package-lock.json src/types/index.ts src/lib/api.ts
git commit -m "feat(ui): add AG Grid dependency, run management types, and API client functions"
```

---

## Task 7: Frontend — SpreadsheetEditor Component

**Files:**
- Create: `frontend/src/components/SpreadsheetEditor.tsx`

This is the largest component. It wraps AG Grid Community with a toolbar for add/delete rows+columns, undo/redo, change tracking, and cell validation.

- [ ] **Step 1: Create SpreadsheetEditor component**

Create `frontend/src/components/SpreadsheetEditor.tsx`:

```tsx
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { AgGridReact } from "ag-grid-react";
import {
  AllCommunityModule,
  type ColDef,
  type CellValueChangedEvent,
  type GridReadyEvent,
  type GridApi,
  ModuleRegistry,
} from "ag-grid-community";
import { Button } from "./ui/button";
import {
  Plus,
  Minus,
  Undo2,
  Redo2,
  RotateCcw,
  Columns3,
  Rows3,
} from "lucide-react";

ModuleRegistry.registerModules([AllCommunityModule]);

interface SpreadsheetEditorProps {
  columns: string[];
  rows: Record<string, string>[];
  onChange: (rows: Record<string, string>[], columns: string[]) => void;
  onDirty: (isDirty: boolean) => void;
}

interface Snapshot {
  rows: Record<string, string>[];
  columns: string[];
}

const MAX_UNDO = 50;

// Required PVMAP columns that should be highlighted if empty
const REQUIRED_CELLS = new Set([
  "observationAbout",
  "observationDate",
  "value",
]);

export function SpreadsheetEditor({
  columns: initialColumns,
  rows: initialRows,
  onChange,
  onDirty,
}: SpreadsheetEditorProps) {
  const gridRef = useRef<AgGridReact>(null);
  const gridApiRef = useRef<GridApi | null>(null);

  const [currentRows, setCurrentRows] = useState<Record<string, string>[]>(
    () => initialRows.map((r) => ({ ...r })),
  );
  const [currentColumns, setCurrentColumns] = useState<string[]>(
    () => [...initialColumns],
  );

  // Snapshot-based undo/redo
  const undoStack = useRef<Snapshot[]>([]);
  const redoStack = useRef<Snapshot[]>([]);
  const originalSnapshot = useRef<Snapshot>({
    rows: initialRows.map((r) => ({ ...r })),
    columns: [...initialColumns],
  });

  // Change tracking
  const [changeCount, setChangeCount] = useState(0);

  const pushSnapshot = useCallback(() => {
    undoStack.current.push({
      rows: currentRows.map((r) => ({ ...r })),
      columns: [...currentColumns],
    });
    if (undoStack.current.length > MAX_UNDO) {
      undoStack.current.shift();
    }
    redoStack.current = [];
  }, [currentRows, currentColumns]);

  const computeChangeCount = useCallback(
    (rows: Record<string, string>[], columns: string[]) => {
      const orig = originalSnapshot.current;
      let count = 0;
      // Column changes
      if (
        columns.length !== orig.columns.length ||
        columns.some((c, i) => c !== orig.columns[i])
      ) {
        count += Math.abs(columns.length - orig.columns.length) || 1;
      }
      // Cell changes
      const maxRows = Math.max(rows.length, orig.rows.length);
      for (let i = 0; i < maxRows; i++) {
        if (i >= orig.rows.length) {
          count++;
          continue;
        }
        if (i >= rows.length) {
          count++;
          continue;
        }
        for (const col of columns) {
          if ((rows[i][col] ?? "") !== (orig.rows[i]?.[col] ?? "")) {
            count++;
          }
        }
      }
      return count;
    },
    [],
  );

  const applyState = useCallback(
    (rows: Record<string, string>[], columns: string[]) => {
      setCurrentRows(rows);
      setCurrentColumns(columns);
      const count = computeChangeCount(rows, columns);
      setChangeCount(count);
      onDirty(count > 0);
      onChange(rows, columns);
    },
    [onChange, onDirty, computeChangeCount],
  );

  // AG Grid column definitions
  const colDefs = useMemo<ColDef[]>(() => {
    return currentColumns.map((col) => ({
      field: col,
      headerName: col,
      editable: true,
      sortable: true,
      filter: "agTextColumnFilter",
      resizable: true,
      minWidth: 100,
      cellClassRules: {
        "bg-red-50": (params: { value: unknown }) =>
          REQUIRED_CELLS.has(col) && !params.value,
        "bg-amber-50": (params: { data: Record<string, string>; rowIndex: number }) => {
          const origRow = originalSnapshot.current.rows[params.rowIndex];
          if (!origRow) return true; // new row
          return (params.data[col] ?? "") !== (origRow[col] ?? "");
        },
      },
    }));
  }, [currentColumns]);

  const defaultColDef = useMemo<ColDef>(
    () => ({
      flex: 1,
      minWidth: 120,
    }),
    [],
  );

  const onGridReady = useCallback((params: GridReadyEvent) => {
    gridApiRef.current = params.api;
  }, []);

  const onCellValueChanged = useCallback(
    (event: CellValueChangedEvent) => {
      pushSnapshot();
      const updatedRows = [...currentRows];
      updatedRows[event.rowIndex!] = { ...event.data };
      applyState(updatedRows, currentColumns);
    },
    [currentRows, currentColumns, pushSnapshot, applyState],
  );

  // Toolbar actions
  const addRow = useCallback(() => {
    pushSnapshot();
    const emptyRow: Record<string, string> = {};
    currentColumns.forEach((c) => (emptyRow[c] = ""));
    applyState([...currentRows, emptyRow], currentColumns);
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  const deleteRow = useCallback(() => {
    const api = gridApiRef.current;
    if (!api) return;
    const selected = api.getSelectedRows();
    if (selected.length === 0) return;
    pushSnapshot();
    const selectedSet = new Set(selected);
    const filtered = currentRows.filter((r) => !selectedSet.has(r));
    applyState(filtered, currentColumns);
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  const addColumn = useCallback(() => {
    const name = window.prompt("Column name:");
    if (!name || currentColumns.includes(name)) return;
    pushSnapshot();
    const newCols = [...currentColumns, name];
    const newRows = currentRows.map((r) => ({ ...r, [name]: "" }));
    applyState(newRows, newCols);
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  const deleteColumn = useCallback(() => {
    const api = gridApiRef.current;
    if (!api) return;
    const focusedCell = api.getFocusedCell();
    if (!focusedCell) return;
    const colId = focusedCell.column.getColId();
    if (!colId) return;
    pushSnapshot();
    const newCols = currentColumns.filter((c) => c !== colId);
    const newRows = currentRows.map((r) => {
      const { [colId]: _, ...rest } = r;
      return rest;
    });
    applyState(newRows, newCols);
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  const undo = useCallback(() => {
    if (undoStack.current.length === 0) return;
    const prev = undoStack.current.pop()!;
    redoStack.current.push({
      rows: currentRows.map((r) => ({ ...r })),
      columns: [...currentColumns],
    });
    applyState(
      prev.rows.map((r) => ({ ...r })),
      [...prev.columns],
    );
  }, [currentRows, currentColumns, applyState]);

  const redo = useCallback(() => {
    if (redoStack.current.length === 0) return;
    const next = redoStack.current.pop()!;
    undoStack.current.push({
      rows: currentRows.map((r) => ({ ...r })),
      columns: [...currentColumns],
    });
    applyState(
      next.rows.map((r) => ({ ...r })),
      [...next.columns],
    );
  }, [currentRows, currentColumns, applyState]);

  const discard = useCallback(() => {
    undoStack.current = [];
    redoStack.current = [];
    applyState(
      originalSnapshot.current.rows.map((r) => ({ ...r })),
      [...originalSnapshot.current.columns],
    );
  }, [applyState]);

  // Reset baseline when props change (e.g., after revalidation)
  useEffect(() => {
    originalSnapshot.current = {
      rows: initialRows.map((r) => ({ ...r })),
      columns: [...initialColumns],
    };
    setCurrentRows(initialRows.map((r) => ({ ...r })));
    setCurrentColumns([...initialColumns]);
    setChangeCount(0);
    undoStack.current = [];
    redoStack.current = [];
  }, [initialRows, initialColumns]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === "z" && !e.shiftKey) {
        e.preventDefault();
        undo();
      } else if (
        (e.metaKey || e.ctrlKey) &&
        (e.key === "y" || (e.key === "z" && e.shiftKey))
      ) {
        e.preventDefault();
        redo();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [undo, redo]);

  return (
    <div className="flex flex-col gap-2">
      {/* Toolbar */}
      <div className="flex items-center gap-1 flex-wrap">
        <div className="flex items-center gap-1 border-r pr-2 mr-1">
          <Button variant="outline" size="sm" onClick={addRow} title="Add row">
            <Plus className="h-3 w-3 mr-1" />
            <Rows3 className="h-3 w-3" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={deleteRow}
            title="Delete selected row(s)"
          >
            <Minus className="h-3 w-3 mr-1" />
            <Rows3 className="h-3 w-3" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={addColumn}
            title="Add column"
          >
            <Plus className="h-3 w-3 mr-1" />
            <Columns3 className="h-3 w-3" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={deleteColumn}
            title="Delete focused column"
          >
            <Minus className="h-3 w-3 mr-1" />
            <Columns3 className="h-3 w-3" />
          </Button>
        </div>
        <div className="flex items-center gap-1 border-r pr-2 mr-1">
          <Button
            variant="outline"
            size="sm"
            onClick={undo}
            disabled={undoStack.current.length === 0}
            title="Undo (Ctrl+Z)"
          >
            <Undo2 className="h-3 w-3" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={redo}
            disabled={redoStack.current.length === 0}
            title="Redo (Ctrl+Y)"
          >
            <Redo2 className="h-3 w-3" />
          </Button>
        </div>
        <div className="flex items-center gap-2">
          {changeCount > 0 && (
            <>
              <span className="text-sm text-amber-600 font-medium">
                {changeCount} change{changeCount !== 1 ? "s" : ""}
              </span>
              <Button
                variant="ghost"
                size="sm"
                onClick={discard}
                title="Discard all changes"
              >
                <RotateCcw className="h-3 w-3 mr-1" />
                Discard
              </Button>
            </>
          )}
        </div>
      </div>

      {/* AG Grid */}
      <div className="ag-theme-alpine w-full" style={{ height: 500 }}>
        <AgGridReact
          ref={gridRef}
          rowData={currentRows}
          columnDefs={colDefs}
          defaultColDef={defaultColDef}
          onGridReady={onGridReady}
          onCellValueChanged={onCellValueChanged}
          rowSelection="multiple"
          enableCellTextSelection={true}
          stopEditingWhenCellsLoseFocus={true}
          suppressRowClickSelection={true}
        />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/components/SpreadsheetEditor.tsx
git commit -m "feat(ui): add SpreadsheetEditor component with AG Grid, toolbar, undo/redo"
```

---

## Task 8: Frontend — ConfirmDeleteModal Component

**Files:**
- Create: `frontend/src/components/ConfirmDeleteModal.tsx`

- [ ] **Step 1: Create the modal component**

Create `frontend/src/components/ConfirmDeleteModal.tsx`:

```tsx
import { Button } from "./ui/button";
import { AlertTriangle } from "lucide-react";

interface ConfirmDeleteModalProps {
  datasetName: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDeleteModal({
  datasetName,
  onConfirm,
  onCancel,
}: ConfirmDeleteModalProps) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onCancel}
      />
      {/* Dialog */}
      <div className="relative bg-white rounded-lg shadow-xl p-6 max-w-md w-full mx-4">
        <div className="flex items-start gap-3">
          <div className="flex-shrink-0 p-2 bg-red-100 rounded-full">
            <AlertTriangle className="h-5 w-5 text-red-600" />
          </div>
          <div>
            <h3 className="text-lg font-semibold text-gray-900">
              Delete Run
            </h3>
            <p className="mt-2 text-sm text-gray-600">
              Permanently delete{" "}
              <span className="font-medium">{datasetName}</span> and all its
              files? This cannot be undone.
            </p>
          </div>
        </div>
        <div className="mt-6 flex justify-end gap-3">
          <Button variant="outline" onClick={onCancel}>
            Cancel
          </Button>
          <Button
            variant="destructive"
            onClick={onConfirm}
          >
            Delete
          </Button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 3: Commit**

```bash
cd frontend && git add src/components/ConfirmDeleteModal.tsx
git commit -m "feat(ui): add ConfirmDeleteModal component"
```

---

## Task 9: Frontend — OutputViewer: Remove PVMAP & Metadata Tabs

**Files:**
- Modify: `frontend/src/components/OutputViewer.tsx`

- [ ] **Step 1: Remove PVMAP and Metadata from TAB_CONFIG**

In `frontend/src/components/OutputViewer.tsx`, replace the `TAB_CONFIG` array (lines 26-35) to remove the first two entries:

Old (lines 26-35):
```typescript
const TAB_CONFIG = [
  { key: "generated_pvmap.csv", label: "PVMAP", icon: Table2 },
  { key: "output_metadata.csv", label: "Metadata", icon: Settings },
  { key: "processed.csv", label: "Processed", icon: Table2 },
  { key: "processed.mcf", label: "MCF", icon: FileCode },
  { key: "processed.tmcf", label: "TMCF", icon: FileCode },
  { key: "processed_stat_vars.mcf", label: "StatVars", icon: FileText },
  { key: "generation_notes.md", label: "Notes", icon: StickyNote },
  { key: "processed_counters.txt", label: "Metrics", icon: BarChart3 },
];
```

New:
```typescript
const TAB_CONFIG = [
  { key: "processed.csv", label: "Processed", icon: Table2 },
  { key: "processed.mcf", label: "MCF", icon: FileCode },
  { key: "processed.tmcf", label: "TMCF", icon: FileCode },
  { key: "processed_stat_vars.mcf", label: "StatVars", icon: FileText },
  { key: "generation_notes.md", label: "Notes", icon: StickyNote },
  { key: "processed_counters.txt", label: "Metrics", icon: BarChart3 },
];
```

- [ ] **Step 2: Remove the Save & Revalidate button from OutputViewer**

The Save & Revalidate flow moves to the ResultsPage. Remove the `handleSaveAndRevalidate` function (around lines 152-169) and the save button rendering (around lines 228-238). Also remove the `editedRows`/`editedPvmap` state that tracked PVMAP edits inside OutputViewer.

Remove the `editable` prop check that was specific to PVMAP in the CsvEditor rendering section. OutputViewer should now be purely read-only.

- [ ] **Step 3: Remove unused imports**

Remove `Settings` from lucide-react import (was used by Metadata tab icon). Remove any `CsvEditor`-related edit state that's no longer needed.

- [ ] **Step 4: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 5: Commit**

```bash
cd frontend && git add src/components/OutputViewer.tsx
git commit -m "refactor(ui): remove PVMAP and Metadata tabs from OutputViewer (moved to input panel)"
```

---

## Task 10: Frontend — Restructure ResultsPage

**Files:**
- Modify: `frontend/src/pages/ResultsPage.tsx`

This is the biggest frontend change. The page gets restructured into: header (rename/delete), input panel (PVMAP/Metadata with SpreadsheetEditor), action bar (Save & Revalidate), output panel (read-only OutputViewer), feedback section.

- [ ] **Step 1: Read the current ResultsPage fully**

Read `frontend/src/pages/ResultsPage.tsx` to understand the current structure, props, state, and rendering order. Note the existing imports and how OutputViewer/FeedbackForm/DataExplorer are used.

- [ ] **Step 2: Add imports and state for new features**

Add to the imports section of `ResultsPage.tsx`:

```tsx
import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { SpreadsheetEditor } from "../components/SpreadsheetEditor";
import { ConfirmDeleteModal } from "../components/ConfirmDeleteModal";
import {
  getFile,
  updateFile,
  revalidate,
  updateRun,
  deleteRun,
  getRun,
  listFiles,
} from "../lib/api";
import { Pencil, Trash2, Download, Loader2, AlertTriangle } from "lucide-react";
import { toast } from "sonner";
```

Add new state variables inside the component:

```tsx
// Run metadata editing
const [displayName, setDisplayName] = useState(run?.display_name || run?.dataset_name || "");
const [notes, setNotes] = useState(run?.notes || "");
const [editingName, setEditingName] = useState(false);
const nameInputRef = useRef<HTMLInputElement>(null);

// Delete modal
const [showDeleteModal, setShowDeleteModal] = useState(false);

// Input files (PVMAP + Metadata)
const [activeInputTab, setActiveInputTab] = useState<"pvmap" | "metadata">("pvmap");
const [pvmapData, setPvmapData] = useState<{ columns: string[]; rows: Record<string, string>[] } | null>(null);
const [metadataData, setMetadataData] = useState<{ columns: string[]; rows: Record<string, string>[] } | null>(null);
const [inputDirty, setInputDirty] = useState(false);
const [revalidating, setRevalidating] = useState(false);
const [stale, setStale] = useState(false);

// Edited state refs (latest values for save)
const editedPvmap = useRef<{ rows: Record<string, string>[]; columns: string[] } | null>(null);
const editedMetadata = useRef<{ rows: Record<string, string>[]; columns: string[] } | null>(null);
```

- [ ] **Step 3: Add data fetching for input files**

Add useEffect to load PVMAP and Metadata data when the component mounts:

```tsx
useEffect(() => {
  if (!runId) return;
  // Load PVMAP
  getFile(runId, "generated_pvmap.csv").then((resp) => {
    if (resp.type === "csv") {
      setPvmapData({ columns: resp.columns, rows: resp.rows });
    }
  }).catch(() => {});

  // Load Metadata
  getFile(runId, "output_metadata.csv").then((resp) => {
    if (resp.type === "csv") {
      setMetadataData({ columns: resp.columns, rows: resp.rows });
    }
  }).catch(() => {});
}, [runId]);
```

- [ ] **Step 4: Add handler functions**

```tsx
// Auto-save display name on blur
const handleNameBlur = useCallback(async () => {
  setEditingName(false);
  if (runId && displayName !== (run?.display_name || run?.dataset_name)) {
    try {
      await updateRun(runId, { display_name: displayName });
    } catch {
      toast.error("Failed to update name");
    }
  }
}, [runId, displayName, run]);

// Auto-save notes on blur
const handleNotesBlur = useCallback(async () => {
  if (runId && notes !== (run?.notes || "")) {
    try {
      await updateRun(runId, { notes });
    } catch {
      toast.error("Failed to update notes");
    }
  }
}, [runId, notes, run]);

// Delete
const handleDelete = useCallback(async () => {
  if (!runId) return;
  try {
    await deleteRun(runId);
    toast.success("Run deleted");
    navigate("/history");
  } catch (err: unknown) {
    toast.error(err instanceof Error ? err.message : "Delete failed");
  }
}, [runId, navigate]);

// Save & Revalidate
const handleSaveAndRevalidate = useCallback(async () => {
  if (!runId) return;
  setRevalidating(true);
  try {
    // Save edited files
    const saves: Promise<unknown>[] = [];
    if (editedPvmap.current) {
      saves.push(
        updateFile(runId, "generated_pvmap.csv", {
          rows: editedPvmap.current.rows,
        }),
      );
    }
    if (editedMetadata.current) {
      saves.push(
        updateFile(runId, "output_metadata.csv", {
          rows: editedMetadata.current.rows,
        }),
      );
    }
    await Promise.all(saves);

    // Trigger revalidation
    const result = await revalidate(runId);
    toast.success(
      result.passed ? "Validation passed!" : "Validation completed (check results)",
    );
    setStale(false);
    setInputDirty(false);

    // Reload input files to get fresh baseline
    const pvResp = await getFile(runId, "generated_pvmap.csv");
    if (pvResp.type === "csv") setPvmapData({ columns: pvResp.columns, rows: pvResp.rows });
    const mdResp = await getFile(runId, "output_metadata.csv").catch(() => null);
    if (mdResp?.type === "csv") setMetadataData({ columns: mdResp.columns, rows: mdResp.rows });

    editedPvmap.current = null;
    editedMetadata.current = null;
  } catch (err: unknown) {
    toast.error(err instanceof Error ? err.message : "Revalidation failed");
  } finally {
    setRevalidating(false);
  }
}, [runId]);
```

- [ ] **Step 5: Build the JSX layout**

Replace the return JSX of ResultsPage with the new two-panel layout:

```tsx
return (
  <div className="max-w-6xl mx-auto p-6 space-y-6">
    {/* HEADER */}
    <div className="flex items-start justify-between">
      <div className="flex-1">
        {editingName ? (
          <input
            ref={nameInputRef}
            className="text-2xl font-bold border-b-2 border-blue-500 outline-none bg-transparent w-full"
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            onBlur={handleNameBlur}
            onKeyDown={(e) => e.key === "Enter" && handleNameBlur()}
            autoFocus
          />
        ) : (
          <h1
            className="text-2xl font-bold cursor-pointer group flex items-center gap-2"
            onClick={() => setEditingName(true)}
          >
            {displayName || datasetName}
            <Pencil className="h-4 w-4 text-gray-400 opacity-0 group-hover:opacity-100" />
          </h1>
        )}
        <textarea
          className="mt-2 w-full text-sm text-gray-600 border rounded p-2 resize-none"
          placeholder="Add notes about this run..."
          rows={2}
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          onBlur={handleNotesBlur}
        />
      </div>
      <div className="flex items-center gap-2 ml-4">
        <DownloadButton runId={runId} datasetName={datasetName} />
        <Button
          variant="destructive"
          size="sm"
          onClick={() => setShowDeleteModal(true)}
        >
          <Trash2 className="h-4 w-4 mr-1" />
          Delete
        </Button>
      </div>
    </div>

    {/* Status banner */}
    {result && <ResultBanner result={result} />}

    {/* INPUT FILES PANEL */}
    <div className="border rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-3">Input Files</h2>
      <div className="flex gap-2 mb-3">
        <Button
          variant={activeInputTab === "pvmap" ? "default" : "outline"}
          size="sm"
          onClick={() => setActiveInputTab("pvmap")}
        >
          PVMAP
        </Button>
        <Button
          variant={activeInputTab === "metadata" ? "default" : "outline"}
          size="sm"
          onClick={() => setActiveInputTab("metadata")}
          disabled={!metadataData}
        >
          Metadata
        </Button>
      </div>
      {activeInputTab === "pvmap" && pvmapData && (
        <SpreadsheetEditor
          columns={pvmapData.columns}
          rows={pvmapData.rows}
          onChange={(rows, columns) => {
            editedPvmap.current = { rows, columns };
            setStale(true);
          }}
          onDirty={(dirty) => setInputDirty(dirty)}
        />
      )}
      {activeInputTab === "metadata" && metadataData && (
        <SpreadsheetEditor
          columns={metadataData.columns}
          rows={metadataData.rows}
          onChange={(rows, columns) => {
            editedMetadata.current = { rows, columns };
            setStale(true);
          }}
          onDirty={(dirty) => setInputDirty(dirty)}
        />
      )}
      {activeInputTab === "pvmap" && !pvmapData && (
        <p className="text-gray-500 text-sm">No PVMAP file available yet.</p>
      )}
    </div>

    {/* ACTION BAR */}
    <div className="flex items-center gap-3">
      <Button
        onClick={handleSaveAndRevalidate}
        disabled={!inputDirty || revalidating}
      >
        {revalidating ? (
          <>
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
            Running stat_var_processor...
          </>
        ) : (
          "Save & Revalidate"
        )}
      </Button>
      {stale && !revalidating && (
        <div className="flex items-center gap-2 text-amber-600 text-sm">
          <AlertTriangle className="h-4 w-4" />
          Output files may be outdated. Save & Revalidate to refresh.
        </div>
      )}
    </div>

    {/* OUTPUT FILES PANEL */}
    <div className="border rounded-lg p-4">
      <h2 className="text-lg font-semibold mb-3">Output Files</h2>
      <OutputViewer
        runId={runId}
        result={result}
        key={revalidating ? "revalidating" : "ready"}
      />
    </div>

    {/* FEEDBACK SECTION */}
    <FeedbackForm
      runId={runId}
      onFeedbackSubmitted={onFeedbackSubmitted}
    />

    {/* DELETE MODAL */}
    {showDeleteModal && (
      <ConfirmDeleteModal
        datasetName={displayName || datasetName}
        onConfirm={handleDelete}
        onCancel={() => setShowDeleteModal(false)}
      />
    )}
  </div>
);
```

Note: The exact JSX structure will need to be adapted to the current component's props and how it receives `runId`, `datasetName`, `result`, etc. The key point is the structural order: Header → Input Panel → Action Bar → Output Panel → Feedback → Delete Modal.

- [ ] **Step 6: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 7: Commit**

```bash
cd frontend && git add src/pages/ResultsPage.tsx
git commit -m "feat(ui): restructure ResultsPage into two-panel layout with input editing and run management"
```

---

## Task 11: Frontend — History Page Archive/Unarchive

**Files:**
- Modify: `frontend/src/pages/HistoryPage.tsx`

- [ ] **Step 1: Read current HistoryPage**

Read `frontend/src/pages/HistoryPage.tsx` to understand the current rendering and state.

- [ ] **Step 2: Add archive state and toggle**

Update `frontend/src/pages/HistoryPage.tsx` with archive functionality:

```tsx
import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns, archiveRun } from "../lib/api";
import type { Run } from "../types";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Archive, ArchiveRestore, ToggleLeft, ToggleRight } from "lucide-react";
import { toast } from "sonner";

export function HistoryPage() {
  const navigate = useNavigate();
  const [runs, setRuns] = useState<Run[]>([]);
  const [loading, setLoading] = useState(true);
  const [showArchived, setShowArchived] = useState(false);

  const fetchRuns = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listRuns(showArchived);
      setRuns(data);
    } catch {
      toast.error("Failed to load runs");
    } finally {
      setLoading(false);
    }
  }, [showArchived]);

  useEffect(() => {
    fetchRuns();
  }, [fetchRuns]);

  const handleArchive = useCallback(
    async (e: React.MouseEvent, runId: string) => {
      e.stopPropagation(); // Don't navigate to results
      try {
        const result = await archiveRun(runId);
        toast.success(result.archived ? "Run archived" : "Run unarchived");
        fetchRuns(); // Refresh list
      } catch {
        toast.error("Failed to archive run");
      }
    },
    [fetchRuns],
  );

  // ... status badge logic (keep existing) ...

  return (
    <div className="max-w-4xl mx-auto p-6">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Run History</h1>
        <Button
          variant="outline"
          size="sm"
          onClick={() => setShowArchived(!showArchived)}
        >
          {showArchived ? (
            <ToggleRight className="h-4 w-4 mr-2" />
          ) : (
            <ToggleLeft className="h-4 w-4 mr-2" />
          )}
          {showArchived ? "Showing archived" : "Show archived"}
        </Button>
      </div>

      {loading ? (
        <p className="text-gray-500">Loading...</p>
      ) : runs.length === 0 ? (
        <p className="text-gray-500">No runs found.</p>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <div
              key={run.run_id}
              className={`flex items-center justify-between p-4 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors ${
                run.archived ? "opacity-50" : ""
              }`}
              onClick={() => navigate(`/runs/${run.run_id}/results`)}
            >
              <div className="flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-medium">
                    {run.display_name || run.dataset_name}
                  </span>
                  {run.archived && (
                    <Badge variant="outline" className="text-xs">
                      Archived
                    </Badge>
                  )}
                </div>
                <span className="text-sm text-gray-500">
                  {run.run_id.slice(0, 8)}...
                </span>
                {run.notes && (
                  <p className="text-xs text-gray-400 mt-1 truncate max-w-md">
                    {run.notes}
                  </p>
                )}
              </div>
              <div className="flex items-center gap-2">
                {/* Status badge (keep existing logic) */}
                <Badge variant={getStatusVariant(run)}>
                  {getStatusLabel(run)}
                </Badge>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={(e) => handleArchive(e, run.run_id)}
                  title={run.archived ? "Unarchive" : "Archive"}
                >
                  {run.archived ? (
                    <ArchiveRestore className="h-4 w-4" />
                  ) : (
                    <Archive className="h-4 w-4" />
                  )}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
```

Note: The `listRuns` API function needs to accept an `includeArchived` parameter. Update `frontend/src/lib/api.ts`:

```typescript
export async function listRuns(includeArchived = false): Promise<Run[]> {
  const params = includeArchived ? "?include_archived=true" : "";
  return request<Run[]>(`/api/runs${params}`);
}
```

- [ ] **Step 3: Verify frontend builds**

```bash
cd frontend && npm run build
```
Expected: Build succeeds

- [ ] **Step 4: Commit**

```bash
cd frontend && git add src/pages/HistoryPage.tsx src/lib/api.ts
git commit -m "feat(ui): add archive/unarchive to History page with show archived toggle"
```

---

## Task 12: Integration — Manual End-to-End Testing

**Files:** None (testing only)

- [ ] **Step 1: Start backend**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" uvicorn src.api.main:app --reload --port 8000
```

- [ ] **Step 2: Start frontend dev server**

```bash
cd frontend && npm run dev
```

- [ ] **Step 3: Test run management on History page**

1. Open http://localhost:5173/history
2. Verify runs display with archive button
3. Click archive on a run — verify it disappears
4. Toggle "Show archived" — verify archived run reappears with muted styling
5. Click unarchive — verify it returns to normal

- [ ] **Step 4: Test run management on Results page**

1. Click into a run's results
2. Click the display name — verify inline edit activates
3. Change the name, click away — verify it saves (check run_info.json on disk)
4. Add notes — verify they save on blur
5. Click Delete — verify confirmation modal appears
6. Confirm delete — verify navigates to history and run is gone

- [ ] **Step 5: Test PVMAP/Metadata editing**

1. On Results page, verify the two-panel layout: Input Files on top, Output Files below
2. Click into a PVMAP cell — verify it's editable
3. Edit a cell — verify yellow highlight and change count
4. Add a row — verify it appears
5. Delete a row — select it, click delete row
6. Undo/Redo — verify Ctrl+Z and toolbar buttons work
7. Switch to Metadata tab — verify separate editor
8. Discard changes — verify revert

- [ ] **Step 6: Test Save & Revalidate flow**

1. Edit a PVMAP cell
2. Click "Save & Revalidate" — verify loading state
3. Wait for stat_var_processor to complete
4. Verify output panel refreshes with new files
5. Verify stale indicator clears
6. Edit again — verify stale indicator reappears

- [ ] **Step 7: Run full backend test suite**

```bash
PYTHONPATH="$(pwd):$(pwd)/src" .venv/bin/python -m pytest tests/ -x -q
```
Expected: All tests pass

- [ ] **Step 8: Final commit if any fixes were needed**

```bash
git add -A && git commit -m "fix(ui): integration fixes from end-to-end testing"
```
