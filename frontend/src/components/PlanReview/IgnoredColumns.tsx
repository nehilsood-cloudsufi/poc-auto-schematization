/**
 * Collapsed list of columns the plan chose to ignore.
 *
 * Collapsed by default; click header to expand.
 */
import { useState } from "react";
import type { ColumnMapping } from "@/types";

interface IgnoredColumnsProps {
  columns: ColumnMapping[];
}

export function IgnoredColumns({ columns }: IgnoredColumnsProps) {
  const [expanded, setExpanded] = useState(false);

  if (columns.length === 0) return null;

  return (
    <div className="rounded-md border">
      <button
        type="button"
        className="w-full flex items-center gap-2 px-3 py-2 text-sm font-medium text-muted-foreground hover:bg-muted/30 transition-colors"
        onClick={() => setExpanded((prev) => !prev)}
      >
        <span className="text-xs">{expanded ? "\u25BC" : "\u25B6"}</span>
        Ignored columns ({columns.length})
      </button>

      {expanded && (
        <div className="border-t px-3 py-2 space-y-1">
          {columns.map((col) => (
            <div key={col.column_name} className="text-sm">
              <span className="font-medium">{col.column_name}</span>
              {col.evidence && (
                <span className="text-muted-foreground"> — {col.evidence}</span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
