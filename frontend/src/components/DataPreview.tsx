/**
 * Read-only table preview of uploaded CSV data.
 */
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";

interface DataPreviewProps {
  columns: string[];
  rows: Record<string, unknown>[];
  totalRows: number;
  totalColumns: number;
}

export function DataPreview({ columns, rows, totalRows, totalColumns }: DataPreviewProps) {
  return (
    <div className="rounded-md border">
      <div className="px-3 py-2 bg-muted/50 text-xs text-muted-foreground border-b flex items-center justify-between">
        <span>{totalRows.toLocaleString()} rows x {totalColumns} columns</span>
        <span>Showing first {rows.length}</span>
      </div>
      <div className="overflow-auto max-h-64">
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
                {columns.map((col) => (
                  <TableCell key={col} className="text-sm py-1.5 whitespace-nowrap tabular-nums">
                    {String(row[col] ?? "")}
                  </TableCell>
                ))}
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>
    </div>
  );
}
