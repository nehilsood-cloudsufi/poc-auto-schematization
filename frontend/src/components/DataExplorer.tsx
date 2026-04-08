/**
 * Configurable data preview with adjustable row count.
 */
import { useEffect, useState, useRef } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Card, CardContent } from "@/components/ui/card";
import { getPreview } from "@/lib/api";
import type { PreviewResponse } from "@/types";

interface DataExplorerProps {
  runId: string;
}

export function DataExplorer({ runId }: DataExplorerProps) {
  const [rowCount, setRowCount] = useState(100);
  const [data, setData] = useState<PreviewResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout>>(undefined);

  useEffect(() => {
    if (!runId) return;

    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(async () => {
      setLoading(true);
      try {
        setData(await getPreview(runId, rowCount));
      } catch {
        // Ignore — preview is best-effort
      } finally {
        setLoading(false);
      }
    }, 500);

    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, [runId, rowCount]);

  return (
    <Card className="shadow-sm">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <div>
            <h3 className="text-base font-semibold">Data Preview</h3>
            {data && (
              <p className="text-sm text-muted-foreground">
                {data.total_rows} rows x {data.columns} columns
                {data.showing < data.total_rows && ` (showing ${data.showing})`}
              </p>
            )}
          </div>
          <div className="flex items-center gap-2">
            <Label htmlFor="row-count" className="text-sm whitespace-nowrap">
              Rows:
            </Label>
            <Input
              id="row-count"
              type="number"
              value={rowCount}
              onChange={(e) => {
                const v = parseInt(e.target.value, 10);
                if (v > 0 && v <= 1000) setRowCount(v);
              }}
              min={1}
              max={1000}
              className="w-20"
            />
          </div>
        </div>

        {loading && !data && (
          <div className="border rounded-md overflow-hidden">
            <div className="bg-muted/30 px-3 py-2 border-b">
              <div className="h-4 w-24 bg-muted animate-pulse rounded" />
            </div>
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4 px-3 py-2.5 border-b border-border/50">
                {Array.from({ length: 4 }).map((_, j) => (
                  <div key={j} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${60 + Math.random() * 80}px` }} />
                ))}
              </div>
            ))}
          </div>
        )}

        {data && (
          <div className="overflow-auto max-h-[500px] border rounded-md">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-muted">
                <tr>
                  {data.column_names.map((col) => (
                    <th
                      key={col}
                      className="px-3 py-2 text-sm text-left font-medium whitespace-nowrap border-b"
                    >
                      {col}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.data.map((row, i) => (
                  <tr key={i} className="even:bg-muted/50">
                    {data.column_names.map((col) => (
                      <td
                        key={col}
                        className="px-3 py-1.5 text-sm whitespace-nowrap tabular-nums border-b border-border/50"
                      >
                        {String(row[col] ?? "")}
                      </td>
                    ))}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
