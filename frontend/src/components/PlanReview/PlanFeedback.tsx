/**
 * Feedback panel for plan review: notes list, textarea input, and
 * regenerate-with-feedback split button (Quick / Deep).
 */
import { useState, useEffect, useRef } from "react";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { RefreshCw, Plus, ChevronDown } from "lucide-react";

interface PlanFeedbackProps {
  notes: string[];
  onAddNote: (note: string) => void;
  onRegenerate: (feedback: string, deep: boolean) => void;
  regenerating: boolean;
}

export function PlanFeedback({ notes, onAddNote, onRegenerate, regenerating }: PlanFeedbackProps) {
  const [text, setText] = useState("");
  const [showDeepMenu, setShowDeepMenu] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Close dropdown on click outside
  useEffect(() => {
    if (!showDeepMenu) return;
    const handleClick = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setShowDeepMenu(false);
      }
    };
    document.addEventListener("mousedown", handleClick);
    return () => document.removeEventListener("mousedown", handleClick);
  }, [showDeepMenu]);

  const handleAddNote = () => {
    if (!text.trim()) return;
    onAddNote(text.trim());
    setText("");
  };

  const handleRegenerate = (deep: boolean) => {
    if (!text.trim()) return;
    onRegenerate(text.trim(), deep);
    setText("");
    setShowDeepMenu(false);
  };

  return (
    <div className="space-y-3">
      {/* Existing notes */}
      {notes.length > 0 && (
        <div className="border rounded-lg p-3 bg-muted/20">
          <div className="text-sm font-medium mb-1.5">Your Notes</div>
          <ul className="space-y-1">
            {notes.map((note, i) => (
              <li key={i} className="text-sm text-muted-foreground flex gap-2">
                <span className="text-muted-foreground/50">-</span>
                <span>{note}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Input area */}
      <Textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        placeholder="Feedback to regenerate the plan, or a note for the PVMAP generator..."
        rows={3}
        disabled={regenerating}
        className="text-sm"
      />

      {/* Action buttons */}
      <div className="flex gap-2">
        <Button
          variant="outline"
          size="sm"
          onClick={handleAddNote}
          disabled={!text.trim() || regenerating}
          className="gap-1.5"
        >
          <Plus className="w-3.5 h-3.5" />
          Add Note
        </Button>

        <div className="relative" ref={dropdownRef}>
          <div className="flex">
            <Button
              variant="outline"
              size="sm"
              onClick={() => handleRegenerate(false)}
              disabled={!text.trim() || regenerating}
              className="gap-1.5 rounded-r-none"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${regenerating ? "animate-spin" : ""}`} />
              {regenerating ? "Regenerating..." : "Regenerate Plan"}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={() => setShowDeepMenu(!showDeepMenu)}
              disabled={!text.trim() || regenerating}
              className="rounded-l-none border-l-0 px-1.5"
            >
              <ChevronDown className="w-3.5 h-3.5" />
            </Button>
          </div>
          {showDeepMenu && (
            <div className="absolute top-full mt-1 right-0 bg-background border rounded-md shadow-md z-10 py-1 min-w-[200px]">
              <button
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                onClick={() => handleRegenerate(false)}
              >
                Quick (re-rank only)
              </button>
              <button
                className="w-full text-left px-3 py-1.5 text-sm hover:bg-muted"
                onClick={() => handleRegenerate(true)}
              >
                Deep (re-retrieve candidates)
              </button>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
