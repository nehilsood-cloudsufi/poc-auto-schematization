/**
 * CSV table viewer with explicit edit mode toggle.
 */
import { useState, useCallback } from "react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Pencil, X } from "lucide-react";

interface CsvEditorProps {
  columns: string[];
  rows: Record<string, unknown>[];
  editable?: boolean;
  onChange?: (rows: Record<string, unknown>[]) => void;
}

export function CsvEditor({ columns, rows, editable = false, onChange }: CsvEditorProps) {
  const [editing, setEditing] = useState(false);
  const [editingCell, setEditingCell] = useState<{ row: number; col: string } | null>(null);
  const [changedCells, setChangedCells] = useState<Set<string>>(new Set());
  const [originalRows, setOriginalRows] = useState(() => rows.map((r) => ({ ...r })));

  // Reset original rows when the source data changes (e.g., different file loaded)
  const [prevRowCount, setPrevRowCount] = useState(rows.length);
  if (rows.length !== prevRowCount && !editing) {
    setOriginalRows(rows.map((r) => ({ ...r })));
    setChangedCells(new Set());
    setPrevRowCount(rows.length);
  }

  const handleCellChange = useCallback((rowIdx: number, col: string, value: string) => {
    if (!onChange) return;
    const newRows = [...rows];
    newRows[rowIdx] = { ...newRows[rowIdx], [col]: value };
    onChange(newRows);

    const cellKey = `${rowIdx}:${col}`;
    const originalValue = String(originalRows[rowIdx]?.[col] ?? "");
    setChangedCells((prev) => {
      const next = new Set(prev);
      if (value !== originalValue) {
        next.add(cellKey);
      } else {
        next.delete(cellKey);
      }
      return next;
    });
  }, [onChange, rows, originalRows]);

  const handleDiscard = () => {
    if (onChange && originalRows.length > 0) {
      onChange(originalRows.map((r) => ({ ...r })));
    }
    setEditing(false);
    setEditingCell(null);
    setChangedCells(new Set());
  };

  return (
    <div>
      {editable && (
        <div className="flex items-center justify-between mb-2">
          {editing ? (
            <div className="flex items-center gap-2">
              <span className="text-sm text-amber-600 dark:text-amber-400 font-medium">
                Editing — {changedCells.size} cell{changedCells.size !== 1 ? "s" : ""} changed
              </span>
              <Button variant="ghost" size="sm" onClick={handleDiscard} className="gap-1 text-xs">
                <X className="w-3.5 h-3.5" /> Discard
              </Button>
            </div>
          ) : (
            <div />
          )}
          {!editing && (
            <Button variant="outline" size="sm" onClick={() => setEditing(true)} className="gap-1.5">
              <Pencil className="w-3.5 h-3.5" /> Edit PVMAP
            </Button>
          )}
        </div>
      )}

      <div className="rounded-md border overflow-auto max-h-[500px]">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="text-sm font-medium whitespace-nowrap bg-muted/30 sticky top-0">
                  {col}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={i} className="even:bg-muted/20">
                {columns.map((col) => {
                  const cellKey = `${i}:${col}`;
                  const isChanged = changedCells.has(cellKey);
                  const isEditing = editing && editingCell?.row === i && editingCell?.col === col;

                  return (
                    <TableCell
                      key={col}
                      className={`py-1 px-2 ${isChanged ? "bg-amber-50 dark:bg-amber-950/30" : ""}`}
                    >
                      {isEditing ? (
                        <Input
                          className="h-7 text-sm"
                          value={String(row[col] ?? "")}
                          onChange={(e) => handleCellChange(i, col, e.target.value)}
                          onBlur={() => setEditingCell(null)}
                          onKeyDown={(e) => {
                            if (e.key === "Enter") setEditingCell(null);
                            if (e.key === "Escape") setEditingCell(null);
                          }}
                          autoFocus
                        />
                      ) : (
                        <span
                          className={`text-sm block px-1 tabular-nums ${
                            editing ? "cursor-text hover:bg-primary/5 rounded" : "cursor-default"
                          }`}
                          onClick={() => editing && editable && setEditingCell({ row: i, col })}
                        >
                          {String(row[col] ?? "")}
                        </span>
                      )}
                    </TableCell>
                  );
                })}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
