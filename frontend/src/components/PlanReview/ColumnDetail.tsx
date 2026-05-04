/**
 * Expandable detail panel for a single column mapping.
 *
 * Shows evidence, DC match, radio-selectable candidates, and a custom override input.
 */
import { useState } from "react";
import { Input } from "@/components/ui/input";
import type { ColumnMapping } from "@/types";

interface ColumnDetailProps {
  column: ColumnMapping;
  onSelectionChange: (selectedIndex: number) => void;
  onCustomOverride: (property: string, valueExpression: string) => void;
}

export function ColumnDetail({ column, onSelectionChange, onCustomOverride }: ColumnDetailProps) {
  const [customInput, setCustomInput] = useState("");

  const handleCustomSubmit = () => {
    const trimmed = customInput.trim();
    if (!trimmed) return;
    const arrowIdx = trimmed.indexOf("->");
    if (arrowIdx === -1) return;
    const property = trimmed.slice(0, arrowIdx).trim();
    const valueExpression = trimmed.slice(arrowIdx + 2).trim();
    if (property && valueExpression) {
      onCustomOverride(property, valueExpression);
      setCustomInput("");
    }
  };

  return (
    <div className="px-4 py-3 bg-muted/20 border-t space-y-3">
      {/* Evidence */}
      <p className="text-xs text-muted-foreground">{column.evidence}</p>

      {/* DC match */}
      {column.dc_match && (
        <p className="text-xs">
          <span className="text-muted-foreground">DC match:</span>{" "}
          <code className="bg-muted px-1 py-0.5 rounded text-xs">{column.dc_match}</code>
        </p>
      )}

      {/* Candidate options */}
      <div className="space-y-2">
        {column.candidates.map((candidate, idx) => {
          const radioId = `${column.column_name}-candidate-${idx}`;
          const isSelected = column.selected_index === idx;
          return (
            <label
              key={idx}
              htmlFor={radioId}
              className={`flex items-start gap-2 p-2 rounded border cursor-pointer transition-colors ${
                isSelected
                  ? "border-primary/50 bg-primary/5"
                  : "border-transparent hover:bg-muted/30"
              }`}
            >
              <input
                type="radio"
                id={radioId}
                name={`${column.column_name}-candidates`}
                checked={isSelected}
                onChange={() => onSelectionChange(idx)}
                className="mt-1 accent-primary"
              />
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 flex-wrap">
                  <span className="text-sm font-medium">
                    {candidate.property} &rarr; {candidate.value_expression}
                  </span>
                  <span className="text-xs text-muted-foreground">
                    {Math.round(candidate.confidence * 100)}%
                  </span>
                  <span className="text-xs text-muted-foreground italic">
                    {candidate.source}
                  </span>
                  {candidate.validation && (
                    <span
                      className={`text-xs px-1.5 py-0.5 rounded ${
                        candidate.validation.property_exists
                          ? "bg-green-100 text-green-700 dark:bg-green-900/30 dark:text-green-400"
                          : "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400"
                      }`}
                    >
                      {candidate.validation.property_exists ? "valid" : "unverified"}
                    </span>
                  )}
                </div>
                {candidate.reason && (
                  <p className="text-xs text-muted-foreground mt-0.5">{candidate.reason}</p>
                )}
              </div>
            </label>
          );
        })}
      </div>

      {/* Custom override input */}
      <div className="flex items-center gap-2">
        <Input
          className="h-7 text-sm flex-1"
          placeholder="Custom: property -> value_expression"
          value={customInput}
          onChange={(e) => setCustomInput(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") handleCustomSubmit();
          }}
        />
        <span className="text-xs text-muted-foreground whitespace-nowrap">Enter to add</span>
      </div>
    </div>
  );
}
