/**
 * Pick-from-options for global (non-column) properties like populationType, unit, etc.
 */
import type { StaticProperty } from "@/types";

interface StaticPropertiesProps {
  properties: StaticProperty[];
  onUpdate: (propName: string, selectedIndex: number) => void;
}

export function StaticProperties({ properties, onUpdate }: StaticPropertiesProps) {
  if (properties.length === 0) return null;

  return (
    <div className="space-y-4">
      {properties.map((prop) => (
        <div key={prop.property_name} className="space-y-1.5">
          <h4 className="text-sm font-medium">{prop.property_name}</h4>
          <div className="space-y-1">
            {prop.candidates.map((candidate, idx) => {
              const radioId = `static-${prop.property_name}-${idx}`;
              const isSelected = prop.selected_index === idx;
              return (
                <label
                  key={idx}
                  htmlFor={radioId}
                  className={`flex items-center gap-2 p-1.5 rounded cursor-pointer transition-colors ${
                    isSelected
                      ? "bg-primary/5"
                      : "hover:bg-muted/30"
                  }`}
                >
                  <input
                    type="radio"
                    id={radioId}
                    name={`static-${prop.property_name}`}
                    checked={isSelected}
                    onChange={() => onUpdate(prop.property_name, idx)}
                    className="accent-primary"
                  />
                  <span className="text-sm">{candidate.value_expression}</span>
                  <span className="text-xs text-muted-foreground">
                    {Math.round(candidate.confidence * 100)}%
                  </span>
                  <span className="text-xs text-muted-foreground italic">
                    {candidate.source}
                  </span>
                </label>
              );
            })}
          </div>
        </div>
      ))}
    </div>
  );
}
