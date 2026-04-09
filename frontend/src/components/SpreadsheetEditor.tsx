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
