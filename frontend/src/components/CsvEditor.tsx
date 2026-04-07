/**
 * Editable CSV table using shadcn Table components.
 */
import { useState } from "react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { Input } from "@/components/ui/input";

interface CsvEditorProps {
  columns: string[];
  rows: Record<string, unknown>[];
  editable?: boolean;
  onChange?: (rows: Record<string, unknown>[]) => void;
}

export function CsvEditor({ columns, rows, editable = false, onChange }: CsvEditorProps) {
  const [editingCell, setEditingCell] = useState<{ row: number; col: string } | null>(null);

  const handleCellChange = (rowIdx: number, col: string, value: string) => {
    if (!onChange) return;
    const newRows = [...rows];
    newRows[rowIdx] = { ...newRows[rowIdx], [col]: value };
    onChange(newRows);
  };

  return (
    <div className="rounded-md border overflow-auto max-h-[500px]">
      <Table>
        <TableHeader>
          <TableRow>
            {columns.map((col) => (
              <TableHead key={col} className="text-xs whitespace-nowrap">{col}</TableHead>
            ))}
          </TableRow>
        </TableHeader>
        <TableBody>
          {rows.map((row, i) => (
            <TableRow key={i}>
              {columns.map((col) => (
                <TableCell key={col} className="py-0.5 px-1">
                  {editable && editingCell?.row === i && editingCell?.col === col ? (
                    <Input
                      className="h-7 text-xs"
                      value={String(row[col] ?? "")}
                      onChange={(e) => handleCellChange(i, col, e.target.value)}
                      onBlur={() => setEditingCell(null)}
                      autoFocus
                    />
                  ) : (
                    <span
                      className="text-xs cursor-default block px-1"
                      onDoubleClick={() => editable && setEditingCell({ row: i, col })}
                    >
                      {String(row[col] ?? "")}
                    </span>
                  )}
                </TableCell>
              ))}
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
