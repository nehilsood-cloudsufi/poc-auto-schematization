/**
 * Feedback submission form with category and severity.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import { submitFeedback } from "@/lib/api";

const CATEGORIES = [
  "Column mapping", "Property names", "Value formatting",
  "Missing mappings", "Incorrect mappings", "Structural issue", "Other",
];

interface FeedbackFormProps {
  runId: string;
  onRerunStarted: (newRunId: string) => void;
}

export function FeedbackForm({ runId, onRerunStarted }: FeedbackFormProps) {
  const [text, setText] = useState("");
  const [category, setCategory] = useState(CATEGORIES[0]);
  const [severity, setSeverity] = useState(3);
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async () => {
    if (!text.trim()) return;
    setSubmitting(true);
    try {
      const resp = await submitFeedback(runId, { text, category, severity });
      onRerunStarted(resp.new_run_id);
    } catch (err) {
      console.error("Feedback submission failed:", err);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="space-y-4">
      <h3 className="text-lg font-medium">Feedback & Re-run</h3>
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Describe what needs to be fixed or improved..."
        rows={4}
      />
      <div className="flex items-center gap-4">
        <select
          value={category}
          onChange={(e) => setCategory(e.target.value)}
          className="text-sm border rounded px-2 py-1"
        >
          {CATEGORIES.map((c) => <option key={c} value={c}>{c}</option>)}
        </select>
        <div className="flex items-center gap-2 flex-1">
          <Label className="text-sm">Severity: {severity}</Label>
          <Slider
            value={[severity]}
            onValueChange={(v) => {
              const arr = v as number[];
              if (arr.length > 0) setSeverity(arr[0]);
            }}
            min={1}
            max={5}
            step={1}
            className="w-32"
          />
        </div>
        <Button onClick={handleSubmit} disabled={!text.trim() || submitting}>
          {submitting ? "Submitting..." : "Re-run with Feedback"}
        </Button>
      </div>
    </div>
  );
}
