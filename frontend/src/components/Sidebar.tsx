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

export function Sidebar({ currentRunId, status, onNewRun }: SidebarProps) {
  const navigate = useNavigate();
  const [history, setHistory] = useState<Run[]>([]);

  // Fetch run history on mount
  useEffect(() => {
    listRuns()
      .then(setHistory)
      .catch(() => setHistory([]));
  }, [status]); // Re-fetch when status changes (new run completed)

  const statusVariant = (
    status === "error" ? "destructive" :
    status === "running" ? "default" :
    status === "complete" ? "default" :
    "secondary"
  ) as "secondary" | "default" | "destructive";

  return (
    <aside className="w-64 border-r bg-muted/30 flex flex-col h-screen">
      {/* Header */}
      <div className="p-4">
        <h2 className="text-lg font-bold">Agent B</h2>
        <p className="text-xs text-muted-foreground">Auto Schematization</p>
        {status !== "pending" && (
          <Badge variant={statusVariant} className="mt-2">
            {status}
          </Badge>
        )}
        {currentRunId && (
          <p className="text-xs text-muted-foreground mt-1 font-mono">
            {currentRunId.slice(0, 12)}
          </p>
        )}
      </div>

      <Separator />

      {/* Actions */}
      <div className="p-4">
        {(status === "complete" || status === "error") && (
          <Button onClick={onNewRun} variant="outline" className="w-full">
            New Run
          </Button>
        )}
      </div>

      <Separator />

      {/* History */}
      <div className="p-4 flex-1 min-h-0">
        <h3 className="text-sm font-medium mb-2">History</h3>
        <ScrollArea className="h-full">
          {history.length === 0 ? (
            <p className="text-xs text-muted-foreground">No previous runs.</p>
          ) : (
            <div className="space-y-1">
              {history.slice(0, 15).map((run) => (
                <button
                  key={run.run_id}
                  onClick={() => navigate(`/runs/${run.run_id}/results`)}
                  className={`
                    w-full text-left px-2 py-1.5 rounded text-xs hover:bg-accent
                    ${run.run_id === currentRunId ? "bg-accent" : ""}
                  `}
                >
                  <span className="mr-1">
                    {run.validation_passed ? "✓" : "✗"}
                  </span>
                  {run.dataset_name}
                </button>
              ))}
            </div>
          )}
        </ScrollArea>
      </div>
    </aside>
  );
}
