/**
 * Read-only table preview of uploaded CSV data.
 */
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
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
      <div className="p-2 bg-muted/50 text-xs text-muted-foreground">
        {totalRows} rows x {totalColumns} columns (showing first {rows.length})
      </div>
      <div className="overflow-auto max-h-64">
        <Table>
          <TableHeader>
            <TableRow>
              {columns.map((col) => (
                <TableHead key={col} className="text-xs whitespace-nowrap">
                  {col}
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((row, i) => (
              <TableRow key={i}>
                {columns.map((col) => (
                  <TableCell key={col} className="text-xs py-1">
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
