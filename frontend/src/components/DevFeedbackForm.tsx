import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { toast } from "sonner";
import { submitDevFeedback } from "@/lib/api";
import { ChevronDown, ChevronUp, MessageSquarePlus } from "lucide-react";

const CATEGORIES = [
  "Bug Report",
  "UI Improvement",
  "Pipeline Quality",
  "Feature Request",
  "Other",
];

interface DevFeedbackFormProps {
  runId: string;
}

export function DevFeedbackForm({ runId }: DevFeedbackFormProps) {
  const [open, setOpen] = useState(false);
  const [text, setText] = useState("");
  const [category, setCategory] = useState("Bug Report");
  const [submitting, setSubmitting] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit() {
    if (!text.trim()) {
      toast.error("Please enter feedback text");
      return;
    }
    setSubmitting(true);
    try {
      await submitDevFeedback(runId, text.trim(), category);
      toast.success("Feedback submitted — thank you!");
      setText("");
      setSubmitted(true);
    } catch (e) {
      toast.error(`Failed to submit feedback: ${e instanceof Error ? e.message : "Unknown error"}`);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div>
      <button
        onClick={() => setOpen(!open)}
        className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <MessageSquarePlus className="w-4 h-4" />
        Developer Feedback
        {open ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
      </button>

      {open && (
        <div className="mt-3 space-y-3">
          {submitted ? (
            <div className="flex items-center gap-2 text-sm text-green-600">
              <span>Feedback submitted successfully.</span>
              <button
                onClick={() => { setSubmitted(false); }}
                className="underline text-muted-foreground hover:text-foreground"
              >
                Submit another
              </button>
            </div>
          ) : (
            <>
              <Select value={category} onValueChange={(v) => setCategory(v ?? "Bug Report")}>
                <SelectTrigger className="w-48">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CATEGORIES.map((c) => (
                    <SelectItem key={c} value={c}>
                      {c}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Textarea
                placeholder="Describe the issue or suggestion..."
                value={text}
                onChange={(e) => setText(e.target.value)}
                rows={3}
              />

              <Button onClick={handleSubmit} disabled={submitting} size="sm">
                {submitting ? "Submitting..." : "Submit Feedback"}
              </Button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
