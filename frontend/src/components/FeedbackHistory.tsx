/**
 * Collapsible panel showing accumulated feedback entries across rounds.
 * Human entries can be retracted; auto entries are read-only.
 */
import { useState, useEffect } from "react";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronRight, Undo2 } from "lucide-react";
import { toast } from "sonner";
import { getFeedbackLedger, retractFeedbackEntry } from "@/lib/api";
import type { FeedbackEntry, FeedbackLedger } from "@/types";

interface FeedbackHistoryProps {
  runId: string;
}

export function FeedbackHistory({ runId }: FeedbackHistoryProps) {
  const [ledger, setLedger] = useState<FeedbackLedger | null>(null);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    getFeedbackLedger(runId)
      .then(setLedger)
      .catch(() => setLedger(null))
      .finally(() => setLoading(false));
  }, [runId, open]);

  const handleRetract = async (entryId: string) => {
    try {
      await retractFeedbackEntry(runId, entryId);
      toast.success("Entry retracted");
      const updated = await getFeedbackLedger(runId);
      setLedger(updated);
    } catch {
      toast.error("Failed to retract entry");
    }
  };

  const entries = ledger?.entries ?? [];
  const activeCount = entries.filter((e) => !e.retracted && !e.superseded).length;

  if (entries.length === 0 && !loading) return null;

  const byRound = new Map<number, FeedbackEntry[]>();
  for (const e of entries) {
    const list = byRound.get(e.round) ?? [];
    list.push(e);
    byRound.set(e.round, list);
  }

  return (
    <div className="border rounded-lg">
      <button
        className="flex items-center gap-2 w-full px-3 py-2 text-sm font-medium hover:bg-muted/50"
        onClick={() => setOpen(!open)}
      >
        {open ? <ChevronDown className="w-4 h-4" /> : <ChevronRight className="w-4 h-4" />}
        Feedback History ({activeCount} active)
      </button>

      {open && (
        <div className="px-3 pb-3 space-y-3">
          {loading && <p className="text-sm text-muted-foreground">Loading...</p>}
          {[...byRound.entries()].map(([round, roundEntries]) => (
            <div key={round} className="space-y-1">
              <div className="text-xs font-medium text-muted-foreground">
                Round {round} ({roundEntries[0]?.source})
              </div>
              {roundEntries.map((e) => (
                <div
                  key={e.id}
                  className={`flex items-center gap-2 text-sm px-2 py-1 rounded ${
                    e.retracted ? "line-through text-muted-foreground bg-muted/30" :
                    e.superseded ? "text-muted-foreground bg-muted/30 italic" :
                    e.source === "human" ? "bg-blue-50 dark:bg-blue-950/20" :
                    "bg-gray-50 dark:bg-gray-900/20"
                  }`}
                >
                  <span className="font-mono text-xs px-1 rounded bg-muted">{e.type}</span>
                  <span className="flex-1 truncate">{e.content}</span>
                  {e.target && <span className="text-xs text-muted-foreground">({e.target})</span>}
                  {e.superseded && <span className="text-xs italic">replaced</span>}
                  {e.source === "human" && !e.retracted && !e.superseded && (
                    <Button
                      variant="ghost" size="sm"
                      className="h-6 w-6 p-0"
                      onClick={() => handleRetract(e.id)}
                      title="Retract this entry"
                    >
                      <Undo2 className="w-3 h-3" />
                    </Button>
                  )}
                </div>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
