/**
 * Persistent sidebar with navigation, history, and status.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { listRuns } from "@/lib/api";
import type { Run } from "@/types";

interface SidebarProps {
  currentRunId: string | null;
  status: string;
  onNewRun: () => void;
}

function formatTimestamp(ts: string): string {
  if (!ts) return "";
  try {
    const d = new Date(ts);
    if (isNaN(d.getTime())) return "";
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  } catch {
    return "";
  }
}

export function Sidebar({ currentRunId, status, onNewRun }: SidebarProps) {
  const navigate = useNavigate();
  const [history, setHistory] = useState<Run[]>([]);

  // Fetch run history on mount and whenever status changes
  useEffect(() => {
    listRuns()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [status]);

  const statusVariant = (
    status === "error" ? "destructive" :
    status === "running" ? "default" :
    status === "complete" ? "default" :
    "secondary"
  ) as "secondary" | "default" | "destructive";

  const isActive = status !== "pending";

  return (
    <aside className="w-64 border-r flex flex-col h-screen bg-background">
      {/* Branded header */}
      <div className="bg-gradient-to-br from-slate-800 to-slate-900 px-4 py-5">
        <div className="flex items-center gap-2 mb-1">
          <span className="text-2xl">🤖</span>
          <h2 className="text-lg font-bold text-white tracking-tight">Agent B</h2>
        </div>
        <p className="text-xs text-slate-400">Auto Schematization</p>
        {isActive && (
          <div className="flex items-center gap-2 mt-3">
            <Badge variant={statusVariant} className="text-xs">
              {status}
            </Badge>
            {currentRunId && (
              <span className="text-xs text-slate-400 font-mono">
                {currentRunId.slice(0, 8)}
              </span>
            )}
          </div>
        )}
      </div>

      {/* New Run button — always visible */}
      <div className="px-4 py-3 border-b">
        <Button
          onClick={onNewRun}
          variant="outline"
          size="sm"
          className="w-full text-sm"
        >
          + New Run
        </Button>
      </div>

      {/* History */}
      <div className="flex-1 min-h-0 flex flex-col px-3 py-3">
        <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2 px-1">
          History
        </h3>
        <ScrollArea className="flex-1">
          {history.length === 0 ? (
            <p className="text-xs text-muted-foreground px-1 py-2">No previous runs.</p>
          ) : (
            <div className="space-y-0.5">
              {history.slice(0, 20).map((run) => {
                const isSelected = run.run_id === currentRunId;
                const passed = run.validation_passed;
                const ts = formatTimestamp(run.timestamp ?? "");
                return (
                  <button
                    key={run.run_id}
                    onClick={() => navigate(`/runs/${run.run_id}/results`)}
                    className={`
                      w-full text-left px-2 py-2 rounded-md transition-colors group
                      ${isSelected
                        ? "bg-accent text-accent-foreground"
                        : "hover:bg-muted text-foreground"
                      }
                    `}
                  >
                    <div className="flex items-start gap-2">
                      <span className={`text-sm mt-0.5 flex-shrink-0 ${passed ? "text-green-500" : "text-red-400"}`}>
                        {passed ? "✓" : "✗"}
                      </span>
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-medium truncate leading-tight">
                          {run.dataset_name}
                        </p>
                        {ts && (
                          <p className="text-xs text-muted-foreground mt-0.5 leading-tight">
                            {ts}
                          </p>
                        )}
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </ScrollArea>
      </div>
    </aside>
  );
}
