# UI: Run Management & Editor Redesign

**Date:** 2026-04-09
**Status:** Approved
**Scope:** 2 features (plan visualization deferred)

## Overview

Two changes to the existing React + FastAPI UI:

1. **Run management** — archive/unarchive on History page, permanent delete + rename/notes on Results page
2. **Two-panel Results page** — PVMAP and Metadata promoted to editable input panel (AG Grid), separated from read-only output files, with Save & Revalidate flow

## Feature 1: Run Management

### Backend

**Extended `run_info.json` per run:**

```json
{
  "run_id": "abc-123",
  "dataset_name": "bis_central_bank",
  "display_name": "BIS Central Bank - Experiment 1",
  "notes": "Trying with schema examples disabled",
  "archived": false,
  "created_at": "2026-04-09T10:30:00Z"
}
```

New fields: `display_name` (string, defaults to `dataset_name`), `notes` (string, defaults to empty), `archived` (bool, defaults to false).

**New/modified endpoints:**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| `PATCH` | `/api/runs/{id}` | Update `display_name` and/or `notes` |
| `POST` | `/api/runs/{id}/archive` | Toggle `archived` status |
| `DELETE` | `/api/runs/{id}` | Permanently delete run directory from disk |
| `GET` | `/api/runs` (modified) | Add `?include_archived=true` query param (default: false) |

**PATCH /api/runs/{id}:**
- Request: `{ display_name?: string, notes?: string }`
- Reads `run_info.json`, merges fields, writes back
- Returns updated run object
- 404 if run not found

**POST /api/runs/{id}/archive:**
- Reads `run_info.json`, flips `archived` boolean, writes back
- Returns `{ archived: true/false }`
- 404 if run not found

**DELETE /api/runs/{id}:**
- Requires header `X-Confirm-Delete: true` (frontend sends after modal confirmation)
- Removes entire `ui_output/{run_id}/` directory via `shutil.rmtree`
- Removes from in-memory run state if present
- Returns 204 No Content
- 400 if confirmation header missing, 404 if run not found

**GET /api/runs (modified):**
- Adds `display_name`, `notes`, `archived` to each run in response
- Query param `include_archived` (default false) — when false, filters out runs where `archived=true`
- Historical runs loaded from disk inherit defaults for missing fields

### Frontend — History Page

- Each row gets an **archive icon button** (right side of row)
- Click archive: calls `POST /api/runs/{id}/archive` → row fades out
- **"Show archived" toggle** at top of page — when enabled, fetches with `?include_archived=true`
- Archived runs display with muted/greyed styling + **unarchive button**
- No confirmation modal for archive (reversible action)

### Frontend — Results Page

- **Header area**: editable `display_name` (inline click-to-edit with pencil icon) and `notes` (expandable textarea)
- Changes auto-save on blur via `PATCH /api/runs/{id}` with debounce
- **Delete button** (red, trash icon) in header area
- Click delete: confirmation modal ("Permanently delete this run and all its files? This cannot be undone.") → on confirm, sends `DELETE /api/runs/{id}` with `X-Confirm-Delete: true` → navigates to `/history`

### TypeScript Changes

```typescript
// types/index.ts — extend Run interface
interface Run {
  // ...existing fields
  display_name?: string;
  notes?: string;
  archived?: boolean;
}

// api.ts — new functions
updateRun(runId: string, data: { display_name?: string; notes?: string }): Promise<Run>
archiveRun(runId: string): Promise<{ archived: boolean }>
deleteRun(runId: string): Promise<void>
```

## Feature 2: Two-Panel Results Layout

### Page Structure

```
+--------------------------------------------------+
|  HEADER                                          |
|  display_name (editable) | notes                 |
|  Status badge | Delete button | Download ZIP     |
+--------------------------------------------------+
|  INPUT FILES (editable)                          |
|  [PVMAP tab] [Metadata tab]                      |
|  +--------------------------------------------+  |
|  |  AG Grid spreadsheet editor                |  |
|  |  Toolbar: +Row -Row +Col -Col | Undo Redo  |  |
|  |  ~500px max height, scrollable             |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
|  [ Save & Revalidate ]  (disabled until edits)   |
|  Stale indicator / loading spinner               |
+--------------------------------------------------+
|  OUTPUT FILES (read-only)                        |
|  [MCF] [TMCF] [Processed] [StatVars] [Notes] [Logs]
|  +--------------------------------------------+  |
|  |  Existing read-only viewer                 |  |
|  +--------------------------------------------+  |
+--------------------------------------------------+
|  FEEDBACK SECTION (existing, unchanged)          |
+--------------------------------------------------+
```

### What Moves Where

- **PVMAP tab**: removed from OutputViewer, promoted to Input panel with AG Grid
- **Metadata tab**: removed from OutputViewer, promoted to Input panel with AG Grid
- **Remaining 6 file types** stay in OutputViewer: Processed CSV, MCF, TMCF, StatVars, Notes, Metrics/Logs

### SpreadsheetEditor Component

**New file: `frontend/src/components/SpreadsheetEditor.tsx`**

Replaces `CsvEditor.tsx` for the input files panel only. CsvEditor remains for read-only table displays.

**Props:**

```typescript
interface SpreadsheetEditorProps {
  columns: string[];
  rows: Record<string, string>[];
  onChange: (rows: Record<string, string>[], columns: string[]) => void;
  onDirty: (isDirty: boolean) => void;
}
```

**Features on AG Grid Community (MIT, free):**

| Feature | Implementation |
|---------|---------------|
| Cell editing | `editable: true` on all column defs |
| Column resize & reorder | `resizable: true`, `suppressMovableColumns: false` |
| Sort by column | `sortable: true` |
| Filter/search | `filter: 'agTextColumnFilter'` per column |
| Clipboard paste | `processDataFromClipboard` handler |
| Add row | Toolbar button → append empty row to rowData |
| Delete row | Toolbar button → remove selected rows |
| Add column | Toolbar button → prompt for name → add to colDefs + rowData |
| Delete column | Toolbar button → remove from colDefs + rowData |
| Undo/Redo | Snapshot-based: push `{ rows, columns }` on each change, 50-entry ring buffer |
| Cell validation | `cellClassRules` — red highlight for empty required cells (observationAbout, observationDate, value) |
| Change tracking | Compare to original, yellow highlight on changed cells, count in toolbar |

**Toolbar layout:**
```
[+ Row] [- Row] [+ Column] [- Column]  |  [Undo] [Redo]  |  "3 changes"  |  [Discard]
```

**Keyboard shortcuts:**
- Ctrl+Z / Cmd+Z: Undo
- Ctrl+Y / Cmd+Shift+Z: Redo

**Dependency:** `ag-grid-community` + `ag-grid-react` (MIT license, ~50KB gzipped)

### Save & Revalidate Flow

**Sequence:**

1. User edits PVMAP and/or Metadata in AG Grid
2. "Save & Revalidate" button enables (change count > 0)
3. On click:
   - Save edited files: `PUT /api/runs/{id}/files/generated_pvmap.csv` and/or `PUT /api/runs/{id}/files/output_metadata.csv` (parallel)
   - Trigger revalidation: `POST /api/runs/{id}/revalidate`
   - Backend runs `stat_var_processor` via subprocess (~10-30s)
   - Returns validation result
4. Frontend refreshes output file tabs, updates validation banner, clears stale indicator, resets undo stack

**Error handling:**

| Scenario | Behavior |
|----------|----------|
| File save fails | Error toast, no revalidation triggered, edits preserved in grid |
| Revalidation timeout (>60s) | Timeout error, output panel stays stale, retry available |
| Revalidation error | Error shown in output panel, PVMAP/Metadata remain as saved |
| Only one file edited | Only that file saved, full revalidation still runs |

**Backend revalidation endpoint (modified `POST /api/runs/{id}/revalidate`):**

1. Locate input CSV (same discovery logic as pipeline runner)
2. Locate saved PVMAP + optional metadata from run output directory
3. Run `stat_var_processor` via subprocess (same as `validation_agent.py`)
4. Return: `{ passed: bool, data_rows: int, errors: string[], output_files: string[] }` where `output_files` is the list of filenames that were regenerated (e.g., `["processed.csv", "processed.mcf", "processed.tmcf", "processed_stat_vars.mcf", "processed_counters.txt"]`)
5. These output files are written to the run's output directory, overwriting previous versions

**Stale indicator:**
- Yellow banner between input and output panels: "Output files may be outdated. Save & Revalidate to refresh."
- Shows when: any edit made after last successful revalidation
- Hides when: revalidation completes successfully

## Files to Create

| File | Purpose |
|------|---------|
| `frontend/src/components/SpreadsheetEditor.tsx` | AG Grid-based rich editor |
| `frontend/src/components/ConfirmDeleteModal.tsx` | Delete confirmation dialog |

## Files to Modify

| File | Changes |
|------|---------|
| `frontend/src/types/index.ts` | Add `display_name`, `notes`, `archived` to `Run` |
| `frontend/src/lib/api.ts` | Add `updateRun`, `archiveRun`, `deleteRun` functions |
| `frontend/src/pages/ResultsPage.tsx` | Two-panel layout, header with rename/delete, Save & Revalidate flow |
| `frontend/src/pages/HistoryPage.tsx` | Archive button per row, show archived toggle, muted styling |
| `frontend/src/components/OutputViewer.tsx` | Remove PVMAP and Metadata tabs, keep remaining 6 |
| `src/api/routes/runs.py` | Add PATCH, DELETE endpoints; modify GET to include new fields + archive filter |
| `src/api/services/run_state.py` | Helper to read/write `run_info.json` fields |
| `src/api/services/file_manager.py` | Add `delete_run_directory()` function |
| `src/api/routes/revalidate.py` | Update to run full stat_var_processor and write output files |
| `frontend/package.json` | Add `ag-grid-community`, `ag-grid-react` |

## Deferred

- Clone/duplicate runs (future)
- Plan visualization improvements (requires core + UI changes)

## Testing Strategy

**Backend:**
- Unit tests for new endpoints (PATCH, DELETE, archive)
- Test archive filter on GET /runs
- Test delete with and without confirmation header
- Test revalidation with modified PVMAP

**Frontend:**
- Manual testing: archive/unarchive flow, delete with modal, rename inline edit
- Manual testing: AG Grid editing, add/delete rows+cols, undo/redo, clipboard paste
- Manual testing: Save & Revalidate end-to-end, stale indicator
