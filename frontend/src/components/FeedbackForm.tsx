/**
 * Enhanced feedback form with three input modes:
 * 1. Quick Feedback — free-text (default, backward compatible)
 * 2. Precise Mapping — column -> property dropdowns for DC experts
 * 3. Pin Rows — show edited rows from CsvEditor with pin checkboxes
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Send, Plus, X } from "lucide-react";
import { toast } from "sonner";
import { submitFeedback } from "@/lib/api";
import type { FeedbackEntryInput, FeedbackType } from "@/types";

const CATEGORIES = [
  "Column mapping", "Property names", "Value formatting",
  "Missing mappings", "Incorrect mappings", "Structural issue", "Other",
];

interface FeedbackFormProps {
  runId: string;
  onRerunStarted: (newRunId: string) => void;
  columns?: string[];
  changedRows?: Array<{ rowIndex: number; before: Record<string, string>; after: Record<string, string> }>;
}

export function FeedbackForm({ runId, onRerunStarted, columns = [], changedRows = [] }: FeedbackFormProps) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [severity, setSeverity] = useState(3);
  const [mappings, setMappings] = useState<FeedbackEntryInput[]>([]);
  const [mapColumn, setMapColumn] = useState("");
  const [mapProperty, setMapProperty] = useState("");
  const [mapValue, setMapValue] = useState("");
  const [pinnedRowIndices, setPinnedRowIndices] = useState<Set<number>>(new Set());
  const [submitting, setSubmitting] = useState(false);

  const addMapping = () => {
    if (!mapColumn || !mapProperty) return;
    const content = mapValue ? `${mapProperty},${mapValue}` : mapProperty;
    setMappings([...mappings, { type: "set_mapping" as FeedbackType, content, target: mapColumn }]);
    setMapColumn("");
    setMapProperty("");
    setMapValue("");
  };

  const removeMapping = (idx: number) => {
    setMappings(mappings.filter((_, i) => i !== idx));
  };

  const togglePin = (rowIndex: number) => {
    setPinnedRowIndices((prev) => {
      const next = new Set(prev);
      if (next.has(rowIndex)) next.delete(rowIndex);
      else next.add(rowIndex);
      return next;
    });
  };

  const handleSubmit = async () => {
    const entries: FeedbackEntryInput[] = [];

    if (text.trim()) {
      entries.push({ type: "free_text" as FeedbackType, content: text });
    }

    entries.push(...mappings);

    for (const idx of pinnedRowIndices) {
      const row = changedRows.find((r) => r.rowIndex === idx);
      if (row) {
        const afterCsv = Object.values(row.after).join(",");
        const key = Object.values(row.after)[0] || `row_${idx}`;
        entries.push({ type: "pin_row" as FeedbackType, content: afterCsv, target: key });
      }
    }

    if (entries.length === 0) {
      toast.error("Please add at least one feedback item");
      return;
    }

    setSubmitting(true);
    try {
      const resp = await submitFeedback(runId, {
        text: text || undefined,
        category,
        severity,
        entries,
      });
      toast.success("Feedback submitted — starting new run");
      onRerunStarted(resp.new_run_id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Feedback submission failed");
    } finally {
      setSubmitting(false);
    }
  };

  const totalEntries = (text.trim() ? 1 : 0) + mappings.length + pinnedRowIndices.size;

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Feedback & Re-run</h3>

      <Tabs defaultValue="quick">
        <TabsList>
          <TabsTrigger value="quick">Quick Feedback</TabsTrigger>
          <TabsTrigger value="mapping">Precise Mapping</TabsTrigger>
          {changedRows.length > 0 && (
            <TabsTrigger value="pin">Pin Rows ({changedRows.length})</TabsTrigger>
          )}
        </TabsList>

        <TabsContent value="quick" className="space-y-3">
          <Textarea
            value={text}
            onChange={(e) => setText(e.target.value)}
            placeholder="Describe what needs to be fixed or improved..."
            rows={4}
          />
          <div className="flex items-center gap-4 flex-wrap">
            <Select value={category} onValueChange={(v) => v && setCategory(v)}>
              <SelectTrigger className="w-48"><SelectValue /></SelectTrigger>
              <SelectContent>
                {CATEGORIES.map((c) => (
                  <SelectItem key={c} value={c}>{c}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <div className="flex items-center gap-2 flex-1 min-w-[160px]">
              <Label className="text-sm whitespace-nowrap">Severity: {severity}</Label>
              <Slider
                value={[severity]}
                onValueChange={(v) => { const arr = v as number[]; if (arr.length > 0) setSeverity(arr[0]); }}
                min={1} max={5} step={1} className="w-32"
              />
            </div>
          </div>
        </TabsContent>

        <TabsContent value="mapping" className="space-y-3">
          <div className="flex items-end gap-2">
            <div className="flex-1">
              <Label className="text-xs">Column</Label>
              {columns.length > 0 ? (
                <Select value={mapColumn} onValueChange={(v) => v && setMapColumn(v)}>
                  <SelectTrigger><SelectValue placeholder="Select column" /></SelectTrigger>
                  <SelectContent>
                    {columns.map((c) => <SelectItem key={c} value={c}>{c}</SelectItem>)}
                  </SelectContent>
                </Select>
              ) : (
                <Input value={mapColumn} onChange={(e) => setMapColumn(e.target.value)} placeholder="Column name" />
              )}
            </div>
            <div className="flex-1">
              <Label className="text-xs">Property</Label>
              <Input value={mapProperty} onChange={(e) => setMapProperty(e.target.value)} placeholder="e.g. observationAbout" />
            </div>
            <div className="flex-1">
              <Label className="text-xs">Value (optional)</Label>
              <Input value={mapValue} onChange={(e) => setMapValue(e.target.value)} placeholder="e.g. {Data}" />
            </div>
            <Button variant="outline" size="sm" onClick={addMapping} disabled={!mapColumn || !mapProperty}>
              <Plus className="w-4 h-4" />
            </Button>
          </div>
          {mappings.length > 0 && (
            <div className="space-y-1">
              {mappings.map((m, i) => (
                <div key={i} className="flex items-center gap-2 text-sm bg-muted rounded px-2 py-1">
                  <span className="font-mono">{m.target}</span>
                  <span className="text-muted-foreground">-&gt;</span>
                  <span className="font-mono">{m.content}</span>
                  <Button variant="ghost" size="sm" className="ml-auto h-6 w-6 p-0" onClick={() => removeMapping(i)}>
                    <X className="w-3 h-3" />
                  </Button>
                </div>
              ))}
            </div>
          )}
        </TabsContent>

        {changedRows.length > 0 && (
          <TabsContent value="pin" className="space-y-2">
            <p className="text-sm text-muted-foreground">
              Select rows to pin as ground truth. Pinned rows will be preserved in future generations.
            </p>
            {changedRows.map((row) => (
              <label key={row.rowIndex} className="flex items-start gap-2 text-sm p-2 border rounded cursor-pointer hover:bg-muted/50">
                <input
                  type="checkbox"
                  checked={pinnedRowIndices.has(row.rowIndex)}
                  onChange={() => togglePin(row.rowIndex)}
                  className="mt-1"
                />
                <div className="flex-1 font-mono text-xs">
                  <div className="text-red-600 line-through">{Object.values(row.before).join(", ")}</div>
                  <div className="text-green-600">{Object.values(row.after).join(", ")}</div>
                </div>
              </label>
            ))}
          </TabsContent>
        )}
      </Tabs>

      <Button onClick={handleSubmit} disabled={totalEntries === 0 || submitting} className="gap-2">
        {submitting ? "Submitting..." : <><Send className="w-4 h-4" /> Re-run with Feedback ({totalEntries})</>}
      </Button>
    </div>
  );
}
