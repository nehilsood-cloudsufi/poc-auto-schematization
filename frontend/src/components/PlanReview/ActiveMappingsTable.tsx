/**
 * Table of active column mappings with expandable detail rows.
 *
 * Clicking a row expands/collapses the ColumnDetail panel.
 * The first ambiguous column is auto-expanded on mount.
 */
import { useState } from "react";
import {
  Table, TableBody, TableCell, TableHead, TableHeader, TableRow,
} from "@/components/ui/table";
import { ColumnDetail } from "./ColumnDetail";
import type { ColumnMapping, PropertyValueCandidate } from "@/types";

interface ActiveMappingsTableProps {
  columns: ColumnMapping[];
  onUpdate: (columnName: string, updates: Partial<ColumnMapping>) => void;
}

export function ActiveMappingsTable({ columns, onUpdate }: ActiveMappingsTableProps) {
  // Auto-expand first ambiguous column
  const firstAmbiguous = columns.find((c) => c.is_ambiguous);
  const [expandedColumn, setExpandedColumn] = useState<string | null>(
    firstAmbiguous?.column_name ?? null
  );

  const toggleExpand = (columnName: string) => {
    setExpandedColumn((prev) => (prev === columnName ? null : columnName));
  };

  const handleSelectionChange = (columnName: string, selectedIndex: number) => {
    onUpdate(columnName, { selected_index: selectedIndex });
  };

  const handleCustomOverride = (columnName: string, property: string, valueExpression: string) => {
    const col = columns.find((c) => c.column_name === columnName);
    if (!col) return;

    const newCandidate: PropertyValueCandidate = {
      property,
      value_expression: valueExpression,
      confidence: 1.0,
      source: "user override",
      reason: "User-provided custom mapping",
      validation: null,
    };

    const newCandidates = [...col.candidates, newCandidate];
    const newIndex = newCandidates.length - 1;

    onUpdate(columnName, {
      candidates: newCandidates,
      selected_index: newIndex,
    });
  };

  return (
    <div className="rounded-md border">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead className="text-sm font-medium bg-muted/30">Column Name</TableHead>
            <TableHead className="text-sm font-medium bg-muted/30">Role</TableHead>
            <TableHead className="text-sm font-medium bg-muted/30">Mapping</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {columns.map((col) => {
            const isExpanded = expandedColumn === col.column_name;
            const selected = col.candidates[col.selected_index];

            return (
              <TableRow key={col.column_name} className="group">
                <TableCell colSpan={3} className="p-0">
                  {/* Clickable summary row */}
                  <div
                    className="flex items-center cursor-pointer hover:bg-muted/30 transition-colors px-2 py-2"
                    onClick={() => toggleExpand(col.column_name)}
                  >
                    <div className="flex-1 min-w-0 basis-1/3">
                      <div className="flex items-center gap-1.5">
                        <span className="text-xs text-muted-foreground">
                          {isExpanded ? "\u25BC" : "\u25B6"}
                        </span>
                        <span className="text-sm font-medium truncate">{col.column_name}</span>
                        {col.is_ambiguous && (
                          <span className="text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                            ambiguous
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="basis-1/6">
                      <span className="text-xs text-muted-foreground">{col.role}</span>
                    </div>
                    <div className="flex-1 min-w-0">
                      {selected ? (
                        <span className="text-sm truncate">
                          {selected.property} &rarr; {selected.value_expression}
                        </span>
                      ) : (
                        <span className="text-sm text-muted-foreground italic">no mapping</span>
                      )}
                    </div>
                  </div>

                  {/* Expanded detail */}
                  {isExpanded && (
                    <ColumnDetail
                      column={col}
                      onSelectionChange={(idx) => handleSelectionChange(col.column_name, idx)}
                      onCustomOverride={(prop, val) => handleCustomOverride(col.column_name, prop, val)}
                    />
                  )}
                </TableCell>
              </TableRow>
            );
          })}
        </TableBody>
      </Table>
    </div>
  );
}
