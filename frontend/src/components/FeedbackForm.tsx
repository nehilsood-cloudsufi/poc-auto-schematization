/**
 * Feedback submission form with category and severity.
 */
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { Slider } from "@/components/ui/slider";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { Send } from "lucide-react";
import { toast } from "sonner";
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
      toast.success("Feedback submitted — starting new run");
      onRerunStarted(resp.new_run_id);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Feedback submission failed");
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
      <div className="flex items-center gap-4 flex-wrap">
        <Select value={category} onValueChange={(v) => v && setCategory(v)}>
          <SelectTrigger className="w-48">
            <SelectValue />
          </SelectTrigger>
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
        <Button onClick={handleSubmit} disabled={!text.trim() || submitting} className="gap-2">
          {submitting ? (
            "Submitting..."
          ) : (
            <><Send className="w-4 h-4" /> Re-run with Feedback</>
          )}
        </Button>
      </div>
    </div>
  );
}
