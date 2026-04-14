/**
 * Persistent sidebar with navigation, history, and status.
 */
import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Separator } from "@/components/ui/separator";
import { listRuns } from "@/lib/api";
import type { Run } from "@/types";
import {
  Plus,
  Circle,
  CheckCircle2,
  XCircle,
  Loader2,
  Pause,
  FileText,
  Database,
  History,
} from "lucide-react";

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
    const now = new Date();
    const diffMs = now.getTime() - d.getTime();
    const diffMins = Math.floor(diffMs / 60000);
    if (diffMins < 1) return "Just now";
    if (diffMins < 60) return `${diffMins}m ago`;
    const diffHours = Math.floor(diffMins / 60);
    if (diffHours < 24) return `${diffHours}h ago`;
    return d.toLocaleDateString(undefined, { month: "short", day: "numeric" });
  } catch {
    return "";
  }
}

function StatusIcon({ run }: { run: Run }) {
  // Only trust validation_passed for terminal states (complete/error)
  const isTerminal = run.status === "complete" || run.status === "error";

  if (run.status === "running") return <Loader2 className="w-4 h-4 text-blue-500 animate-spin" />;
  if (run.status === "plan_ready") return <FileText className="w-4 h-4 text-blue-500" />;
  if (run.status === "stopped") return <Pause className="w-4 h-4 text-amber-500" />;
  if (isTerminal && run.validation_passed) return <CheckCircle2 className="w-4 h-4 text-green-500" />;
  if (isTerminal && !run.validation_passed) return <XCircle className="w-4 h-4 text-red-400" />;
  // Non-terminal, non-special status (e.g., "pending")
  return <Circle className="w-4 h-4 text-muted-foreground" />;
}

function statusLabel(run: Run): string {
  const isTerminal = run.status === "complete" || run.status === "error";
  if (run.status === "running") return "Running";
  if (run.status === "plan_ready") return "Plan Ready";
  if (run.status === "stopped") return "Stopped";
  if (isTerminal && run.validation_passed) return "Passed";
  if (isTerminal && !run.validation_passed) return "Failed";
  return run.status;
}

export function Sidebar({ currentRunId, status, onNewRun }: SidebarProps) {
  const navigate = useNavigate();
  const [history, setHistory] = useState<Run[]>([]);

  useEffect(() => {
    listRuns()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [status]);

  return (
    <aside className="w-64 border-r flex flex-col h-screen bg-card overflow-hidden">
      {/* Header */}
      <div className="px-4 py-4 border-b">
        <div className="flex items-center gap-2.5">
          <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
            <Database className="w-4 h-4 text-primary-foreground" />
          </div>
          <div>
            <h2 className="text-sm font-semibold leading-tight">Agent B</h2>
            <p className="text-xs text-muted-foreground leading-tight">Auto Schematization</p>
          </div>
        </div>
      </div>

      {/* New Run button */}
      <div className="px-3 py-3">
        <Button onClick={onNewRun} className="w-full gap-2" size="sm">
          <Plus className="w-4 h-4" />
          New Run
        </Button>
      </div>

      <Separator />

      {/* History */}
      <div className="flex-1 min-h-0 flex flex-col px-3 py-3">
        <div className="flex items-center justify-between mb-2 px-1">
          <h3 className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">
            History
          </h3>
          <button
            onClick={() => navigate("/history")}
            title="View all history"
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <History className="w-3.5 h-3.5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto">
          {history.length === 0 ? (
            <div className="text-center py-8 px-2">
              <Database className="w-8 h-8 mx-auto text-muted-foreground/40 mb-2" />
              <p className="text-xs text-muted-foreground">No runs yet</p>
              <p className="text-xs text-muted-foreground mt-0.5">Upload a CSV to get started</p>
            </div>
          ) : (
            <div className="space-y-0.5">
              {history.slice(0, 10).map((run) => {
                const isSelected = run.run_id === currentRunId;
                const ts = formatTimestamp(run.timestamp ?? "");
                return (
                  <button
                    key={run.run_id}
                    onClick={() => {
                      if (run.status === "plan_ready") {
                        navigate(`/runs/${run.run_id}/plan`);
                      } else {
                        navigate(`/runs/${run.run_id}/results`);
                      }
                    }}
                    title={run.dataset_name}
                    className={`
                      w-full text-left px-2.5 py-2 rounded-md transition-colors cursor-pointer
                      ${isSelected
                        ? "bg-secondary text-secondary-foreground"
                        : "hover:bg-muted/50 text-foreground"
                      }
                    `}
                  >
                    <div className="flex items-start gap-2.5">
                      <div className="mt-0.5 flex-shrink-0">
                        <StatusIcon run={run} />
                      </div>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium truncate leading-tight">
                          {run.dataset_name}
                        </p>
                        <div className="flex items-center gap-2 mt-0.5">
                          <span className="text-xs text-muted-foreground">{statusLabel(run)}</span>
                          {ts && (
                            <>
                              <span className="text-xs text-muted-foreground/50">·</span>
                              <span className="text-xs text-muted-foreground">{ts}</span>
                            </>
                          )}
                        </div>
                      </div>
                    </div>
                  </button>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </aside>
  );
}
