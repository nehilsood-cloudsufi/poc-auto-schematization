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
import { Input } from "./ui/input";
import {
  Plus,
  Minus,
  Undo2,
  Redo2,
  RotateCcw,
  Columns3,
  Rows3,
  Search,
  X,
  Eraser,
  Copy,
  ClipboardPaste,
  ChevronUp,
  ChevronDown,
  CopyPlus,
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

interface CellMatch {
  row: number;
  col: string;
}

const MAX_UNDO = 50;

// Required PVMAP columns that should be highlighted if empty
const REQUIRED_CELLS = new Set([
  "observationAbout",
  "observationDate",
  "value",
]);

function escapeRegex(s: string): string {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

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
  const [undoDepth, setUndoDepth] = useState(0);
  const [redoDepth, setRedoDepth] = useState(0);

  // Find & Replace
  const [showFind, setShowFind] = useState(false);
  const [showReplace, setShowReplace] = useState(false);
  const [searchTerm, setSearchTerm] = useState("");
  const [replaceTerm, setReplaceTerm] = useState("");
  const [matchIndex, setMatchIndex] = useState(0);
  const findInputRef = useRef<HTMLInputElement>(null);

  // Search highlight ref — avoids re-creating colDefs on every search keystroke
  const searchHighlightRef = useRef<{
    matchKeys: Set<string>;
    activeKey: string;
  }>({ matchKeys: new Set(), activeKey: "" });

  // ── Core helpers ──────────────────────────────────────────────

  const pushSnapshot = useCallback(() => {
    undoStack.current.push({
      rows: currentRows.map((r) => ({ ...r })),
      columns: [...currentColumns],
    });
    if (undoStack.current.length > MAX_UNDO) {
      undoStack.current.shift();
    }
    redoStack.current = [];
    setUndoDepth(undoStack.current.length);
    setRedoDepth(0);
  }, [currentRows, currentColumns]);

  const computeChangeCount = useCallback(
    (rows: Record<string, string>[], columns: string[]) => {
      const orig = originalSnapshot.current;
      let count = 0;
      if (
        columns.length !== orig.columns.length ||
        columns.some((c, i) => c !== orig.columns[i])
      ) {
        count += Math.abs(columns.length - orig.columns.length) || 1;
      }
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

  // ── Find & Replace ────────────────────────────────────────────

  const matches = useMemo<CellMatch[]>(() => {
    if (!searchTerm) return [];
    const found: CellMatch[] = [];
    const lower = searchTerm.toLowerCase();
    currentRows.forEach((row, rowIdx) => {
      currentColumns.forEach((col) => {
        if ((row[col] ?? "").toLowerCase().includes(lower)) {
          found.push({ row: rowIdx, col });
        }
      });
    });
    return found;
  }, [searchTerm, currentRows, currentColumns]);

  // Keep matchIndex in bounds
  useEffect(() => {
    if (matches.length === 0) {
      setMatchIndex(0);
    } else if (matchIndex >= matches.length) {
      setMatchIndex(0);
    }
  }, [matches.length, matchIndex]);

  // Sync search highlight ref → refresh grid cells
  useEffect(() => {
    const matchKeys = new Set(matches.map((m) => `${m.row}:${m.col}`));
    const active = matches[matchIndex];
    const activeKey = active ? `${active.row}:${active.col}` : "";
    searchHighlightRef.current = { matchKeys, activeKey };
    gridApiRef.current?.refreshCells({ force: true });
    if (active) {
      gridApiRef.current?.ensureIndexVisible(active.row);
      gridApiRef.current?.setFocusedCell(active.row, active.col);
    }
  }, [matches, matchIndex]);

  const nextMatch = useCallback(() => {
    if (matches.length === 0) return;
    setMatchIndex((i) => (i + 1) % matches.length);
  }, [matches.length]);

  const prevMatch = useCallback(() => {
    if (matches.length === 0) return;
    setMatchIndex((i) => (i - 1 + matches.length) % matches.length);
  }, [matches.length]);

  const handleReplace = useCallback(() => {
    if (matches.length === 0 || matchIndex >= matches.length) return;
    pushSnapshot();
    const match = matches[matchIndex];
    const updatedRows = currentRows.map((r, i) => {
      if (i !== match.row) return r;
      const oldVal = r[match.col] ?? "";
      const newVal = oldVal.replace(
        new RegExp(escapeRegex(searchTerm), "i"),
        replaceTerm,
      );
      return { ...r, [match.col]: newVal };
    });
    applyState(updatedRows, currentColumns);
  }, [
    matches,
    matchIndex,
    searchTerm,
    replaceTerm,
    currentRows,
    currentColumns,
    pushSnapshot,
    applyState,
  ]);

  const handleReplaceAll = useCallback(() => {
    if (matches.length === 0) return;
    pushSnapshot();
    const regex = new RegExp(escapeRegex(searchTerm), "gi");
    const updatedRows = currentRows.map((row) => {
      const newRow = { ...row };
      currentColumns.forEach((col) => {
        if (newRow[col]) {
          newRow[col] = newRow[col].replace(regex, replaceTerm);
        }
      });
      return newRow;
    });
    applyState(updatedRows, currentColumns);
  }, [
    matches.length,
    searchTerm,
    replaceTerm,
    currentRows,
    currentColumns,
    pushSnapshot,
    applyState,
  ]);

  const closeFind = useCallback(() => {
    setShowFind(false);
    setShowReplace(false);
    setSearchTerm("");
    setReplaceTerm("");
  }, []);

  // ── Clipboard ─────────────────────────────────────────────────

  const handleCopy = useCallback(async () => {
    const api = gridApiRef.current;
    if (!api) return;
    const selected = api.getSelectedRows();
    if (selected.length > 0) {
      const header = currentColumns.join("\t");
      const rows = selected.map((r) =>
        currentColumns.map((c) => r[c] ?? "").join("\t"),
      );
      await navigator.clipboard.writeText([header, ...rows].join("\n"));
    } else {
      const focused = api.getFocusedCell();
      if (focused) {
        const colId = focused.column.getColId();
        const value = currentRows[focused.rowIndex]?.[colId] ?? "";
        await navigator.clipboard.writeText(value);
      }
    }
  }, [currentRows, currentColumns]);

  const handlePaste = useCallback(async () => {
    const api = gridApiRef.current;
    if (!api) return;
    // Don't intercept paste when a cell is being edited
    if (api.getEditingCells().length > 0) return;

    let text: string;
    try {
      text = await navigator.clipboard.readText();
    } catch {
      return; // Permission denied or not available
    }
    if (!text) return;

    pushSnapshot();
    const lines = text.split("\n").filter((l) => l.length > 0);
    const focused = api.getFocusedCell();
    const startRow = focused?.rowIndex ?? currentRows.length;
    const startColIdx = focused
      ? currentColumns.indexOf(focused.column.getColId())
      : 0;

    const updatedRows = currentRows.map((r) => ({ ...r }));

    lines.forEach((line, lineIdx) => {
      const cells = line.split("\t");
      const rowIdx = startRow + lineIdx;

      // Expand grid if pasting beyond current rows
      while (rowIdx >= updatedRows.length) {
        const emptyRow: Record<string, string> = {};
        currentColumns.forEach((c) => (emptyRow[c] = ""));
        updatedRows.push(emptyRow);
      }

      cells.forEach((cell, cellIdx) => {
        const colIdx = startColIdx + cellIdx;
        if (colIdx >= 0 && colIdx < currentColumns.length) {
          updatedRows[rowIdx] = {
            ...updatedRows[rowIdx],
            [currentColumns[colIdx]]: cell,
          };
        }
      });
    });

    applyState(updatedRows, currentColumns);
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  // ── Row / Column operations ───────────────────────────────────

  const addRow = useCallback(() => {
    pushSnapshot();
    const emptyRow: Record<string, string> = {};
    currentColumns.forEach((c) => (emptyRow[c] = ""));
    applyState([...currentRows, emptyRow], currentColumns);
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  const deleteRow = useCallback(() => {
    const api = gridApiRef.current;
    if (!api) return;
    const indices = api.getSelectedNodes()
      .map((n) => n.rowIndex)
      .filter((i): i is number => i != null);
    if (indices.length === 0) return;
    pushSnapshot();
    const selectedIndices = new Set(indices);
    const filtered = currentRows.filter((_, i) => !selectedIndices.has(i));
    applyState(filtered, currentColumns);
    api.deselectAll();
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  const duplicateRows = useCallback(() => {
    const api = gridApiRef.current;
    if (!api) return;
    const indices = api.getSelectedNodes()
      .map((n) => n.rowIndex)
      .filter((i): i is number => i != null);
    if (indices.length === 0) return;
    pushSnapshot();
    // Insert duplicates right after the last selected row
    const selectedIndices = new Set(indices);
    const lastIdx = Math.max(...indices);
    const dupes = indices.map((i) => ({ ...currentRows[i] }));
    const updatedRows = [...currentRows];
    updatedRows.splice(lastIdx + 1, 0, ...dupes);
    applyState(updatedRows, currentColumns);
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  const clearSelected = useCallback(() => {
    const api = gridApiRef.current;
    if (!api) return;
    const indices = api.getSelectedNodes()
      .map((n) => n.rowIndex)
      .filter((i): i is number => i != null);
    if (indices.length === 0) return;
    pushSnapshot();
    const selectedIndices = new Set(indices);
    const updatedRows = currentRows.map((r, i) => {
      if (selectedIndices.has(i)) {
        const cleared: Record<string, string> = {};
        currentColumns.forEach((c) => (cleared[c] = ""));
        return cleared;
      }
      return r;
    });
    applyState(updatedRows, currentColumns);
    api.deselectAll();
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
    if (!colId || !currentColumns.includes(colId)) return;
    pushSnapshot();
    const newCols = currentColumns.filter((c) => c !== colId);
    const newRows = currentRows.map((r) => {
      const { [colId]: _, ...rest } = r;
      return rest;
    });
    applyState(newRows, newCols);
  }, [currentRows, currentColumns, pushSnapshot, applyState]);

  // ── Undo / Redo / Discard ─────────────────────────────────────

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
    setUndoDepth(undoStack.current.length);
    setRedoDepth(redoStack.current.length);
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
    setUndoDepth(undoStack.current.length);
    setRedoDepth(redoStack.current.length);
  }, [currentRows, currentColumns, applyState]);

  const discard = useCallback(() => {
    undoStack.current = [];
    redoStack.current = [];
    setUndoDepth(0);
    setRedoDepth(0);
    applyState(
      originalSnapshot.current.rows.map((r) => ({ ...r })),
      [...originalSnapshot.current.columns],
    );
  }, [applyState]);

  // Selection tracking (reactive)
  const [selectedCount, setSelectedCount] = useState(0);
  const onSelectionChanged = useCallback(() => {
    const count = gridApiRef.current?.getSelectedRows().length ?? 0;
    setSelectedCount(count);
  }, []);

  // ── AG Grid config ────────────────────────────────────────────

  const colDefs = useMemo<ColDef[]>(() => {
    const checkboxCol: ColDef = {
      headerCheckboxSelection: true,
      checkboxSelection: true,
      width: 48,
      maxWidth: 48,
      sortable: false,
      filter: false,
      resizable: false,
      editable: false,
      pinned: "left",
      lockPosition: "left",
      headerName: "",
    };

    const dataCols: ColDef[] = currentColumns.map((col) => ({
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
        "bg-amber-50": (params: {
          data: Record<string, string>;
          rowIndex: number;
        }) => {
          const origRow = originalSnapshot.current.rows[params.rowIndex];
          if (!origRow) return true; // new row
          return (params.data[col] ?? "") !== (origRow[col] ?? "");
        },
        "bg-yellow-200": (params: { rowIndex: number }) =>
          searchHighlightRef.current.matchKeys.has(
            `${params.rowIndex}:${col}`,
          ),
        "ring-2 ring-blue-500 bg-blue-100": (params: {
          rowIndex: number;
        }) =>
          searchHighlightRef.current.activeKey ===
          `${params.rowIndex}:${col}`,
      },
    }));

    return [checkboxCol, ...dataCols];
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
      if (event.rowIndex == null) return;
      pushSnapshot();
      const updatedRows = [...currentRows];
      updatedRows[event.rowIndex] = { ...event.data };
      applyState(updatedRows, currentColumns);
    },
    [currentRows, currentColumns, pushSnapshot, applyState],
  );

  // ── Reset on prop change ──────────────────────────────────────

  useEffect(() => {
    originalSnapshot.current = {
      rows: initialRows.map((r) => ({ ...r })),
      columns: [...initialColumns],
    };
    setCurrentRows(initialRows.map((r) => ({ ...r })));
    setCurrentColumns([...initialColumns]);
    setChangeCount(0);
    onDirty?.(false);
    undoStack.current = [];
    redoStack.current = [];
    setUndoDepth(0);
    setRedoDepth(0);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [initialRows, initialColumns]);

  // ── Keyboard shortcuts ────────────────────────────────────────

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey;
      const active = document.activeElement;
      const inTextInput =
        active?.tagName === "INPUT" || active?.tagName === "TEXTAREA";

      // Undo
      if (meta && e.key === "z" && !e.shiftKey) {
        if (inTextInput && showFind) return; // Let find input handle its own undo
        e.preventDefault();
        undo();
        return;
      }
      // Redo
      if (meta && (e.key === "y" || (e.key === "z" && e.shiftKey))) {
        if (inTextInput && showFind) return;
        e.preventDefault();
        redo();
        return;
      }
      // Find
      if (meta && e.key === "f") {
        e.preventDefault();
        setShowFind(true);
        setShowReplace(false);
        setTimeout(() => findInputRef.current?.focus(), 0);
        return;
      }
      // Find & Replace
      if (meta && e.key === "h") {
        e.preventDefault();
        setShowFind(true);
        setShowReplace(true);
        setTimeout(() => findInputRef.current?.focus(), 0);
        return;
      }
      // Copy (only when not editing a cell or text input)
      if (meta && e.key === "c" && !inTextInput) {
        e.preventDefault();
        handleCopy();
        return;
      }
      // Paste (only when not editing a cell or text input)
      if (meta && e.key === "v" && !inTextInput) {
        e.preventDefault();
        handlePaste();
        return;
      }
      // Delete/Backspace → clear selected rows
      if (
        (e.key === "Delete" || e.key === "Backspace") &&
        !inTextInput
      ) {
        const api = gridApiRef.current;
        if (
          api &&
          api.getSelectedRows().length > 0 &&
          api.getEditingCells().length === 0
        ) {
          e.preventDefault();
          clearSelected();
        }
      }
      // Escape → close find bar
      if (e.key === "Escape" && showFind) {
        closeFind();
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, [
    undo,
    redo,
    handleCopy,
    handlePaste,
    clearSelected,
    closeFind,
    showFind,
  ]);

  // Focus find input when opened
  useEffect(() => {
    if (showFind) {
      setTimeout(() => findInputRef.current?.focus(), 0);
    }
  }, [showFind]);

  // ── Render ────────────────────────────────────────────────────

  return (
    <div className="flex flex-col gap-2">
      {/* Toolbar */}
      <div className="flex items-center gap-1 flex-wrap">
        {/* Row operations */}
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
            onClick={duplicateRows}
            title="Duplicate selected row(s)"
          >
            <CopyPlus className="h-3 w-3 mr-1" />
            <Rows3 className="h-3 w-3" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={clearSelected}
            title="Clear values in selected row(s)"
          >
            <Eraser className="h-3 w-3" />
          </Button>
        </div>

        {/* Column operations */}
        <div className="flex items-center gap-1 border-r pr-2 mr-1">
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
            title="Delete focused column (click a cell first)"
          >
            <Minus className="h-3 w-3 mr-1" />
            <Columns3 className="h-3 w-3" />
          </Button>
        </div>

        {/* Clipboard */}
        <div className="flex items-center gap-1 border-r pr-2 mr-1">
          <Button
            variant="outline"
            size="sm"
            onClick={handleCopy}
            title="Copy selected rows or focused cell (Ctrl+C)"
          >
            <Copy className="h-3 w-3" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={handlePaste}
            title="Paste from clipboard (Ctrl+V)"
          >
            <ClipboardPaste className="h-3 w-3" />
          </Button>
        </div>

        {/* Undo / Redo */}
        <div className="flex items-center gap-1 border-r pr-2 mr-1">
          <Button
            variant="outline"
            size="sm"
            onClick={undo}
            disabled={undoDepth === 0}
            title="Undo (Ctrl+Z)"
          >
            <Undo2 className="h-3 w-3" />
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={redo}
            disabled={redoDepth === 0}
            title="Redo (Ctrl+Y)"
          >
            <Redo2 className="h-3 w-3" />
          </Button>
        </div>

        {/* Find */}
        <div className="flex items-center gap-1 border-r pr-2 mr-1">
          <Button
            variant={showFind ? "default" : "outline"}
            size="sm"
            onClick={() => {
              if (showFind) {
                closeFind();
              } else {
                setShowFind(true);
              }
            }}
            title="Find & Replace (Ctrl+F)"
          >
            <Search className="h-3 w-3" />
          </Button>
        </div>

        {/* Change indicator */}
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

      {/* Find & Replace bar */}
      {showFind && (
        <div className="flex flex-col gap-1.5 p-2 bg-muted/60 rounded-md border">
          {/* Search row */}
          <div className="flex items-center gap-2">
            <Search className="h-3.5 w-3.5 text-muted-foreground shrink-0" />
            <Input
              ref={findInputRef}
              placeholder="Find..."
              value={searchTerm}
              onChange={(e) => setSearchTerm((e.target as HTMLInputElement).value)}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  if (e.shiftKey) {
                    prevMatch();
                  } else {
                    nextMatch();
                  }
                }
                if (e.key === "Escape") {
                  closeFind();
                }
              }}
              className="h-7 text-sm max-w-xs"
            />
            <span className="text-xs text-muted-foreground whitespace-nowrap min-w-[60px]">
              {searchTerm
                ? `${matches.length > 0 ? matchIndex + 1 : 0} of ${matches.length}`
                : ""}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={prevMatch}
              disabled={matches.length === 0}
              className="h-7 w-7 p-0"
              title="Previous match (Shift+Enter)"
            >
              <ChevronUp className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={nextMatch}
              disabled={matches.length === 0}
              className="h-7 w-7 p-0"
              title="Next match (Enter)"
            >
              <ChevronDown className="h-3.5 w-3.5" />
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setShowReplace((v) => !v)}
              className="h-7 text-xs px-2"
              title="Toggle replace"
            >
              {showReplace ? "Hide Replace" : "Replace"}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={closeFind}
              className="h-7 w-7 p-0"
              title="Close (Esc)"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </div>

          {/* Replace row */}
          {showReplace && (
            <div className="flex items-center gap-2 pl-5">
              <Input
                placeholder="Replace with..."
                value={replaceTerm}
                onChange={(e) => setReplaceTerm((e.target as HTMLInputElement).value)}
                onKeyDown={(e) => {
                  if (e.key === "Enter") {
                    e.preventDefault();
                    handleReplace();
                  }
                  if (e.key === "Escape") {
                    closeFind();
                  }
                }}
                className="h-7 text-sm max-w-xs"
              />
              <Button
                variant="outline"
                size="sm"
                onClick={handleReplace}
                disabled={matches.length === 0}
                className="h-7 text-xs"
              >
                Replace
              </Button>
              <Button
                variant="outline"
                size="sm"
                onClick={handleReplaceAll}
                disabled={matches.length === 0}
                className="h-7 text-xs"
              >
                Replace All
              </Button>
            </div>
          )}
        </div>
      )}

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
          onSelectionChanged={onSelectionChanged}
        />
      </div>

      {/* Status bar */}
      <div className="flex items-center gap-4 text-xs text-muted-foreground px-1">
        <span>
          {currentRows.length} row{currentRows.length !== 1 ? "s" : ""} &times;{" "}
          {currentColumns.length} column{currentColumns.length !== 1 ? "s" : ""}
        </span>
        {selectedCount > 0 && (
          <span className="text-blue-600 font-medium">
            {selectedCount} row{selectedCount !== 1 ? "s" : ""} selected
          </span>
        )}
      </div>
    </div>
  );
}
