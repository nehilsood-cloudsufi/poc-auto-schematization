import { useState, useEffect, useCallback, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns, archiveRun, deleteRun } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { Run } from "@/types";
import { Archive, ArchiveRestore, Trash2 } from "lucide-react";
import { toast } from "sonner";

export function HistoryPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const [showArchived, setShowArchived] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const deleteTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const navigate = useNavigate();

  // Clean up delete confirmation timer on unmount
  useEffect(() => () => {
    if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
  }, []);

  const fetchRuns = useCallback(async () => {
    try {
      const data = await listRuns(showArchived);
      setRuns(data);
    } catch {
      setRuns([]);
    }
  }, [showArchived]);

  useEffect(() => { fetchRuns(); }, [fetchRuns]);

  const handleArchive = useCallback(async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    try {
      const result = await archiveRun(runId);
      toast.success(result.archived ? "Run archived" : "Run unarchived");
      fetchRuns();
    } catch {
      toast.error("Failed to archive run");
    }
  }, [fetchRuns]);

  const handleDelete = useCallback(async (e: React.MouseEvent, runId: string) => {
    e.stopPropagation();
    if (deletingId === runId) {
      // Second click — confirmed
      try {
        await deleteRun(runId);
        toast.success("Run deleted permanently");
        setDeletingId(null);
        fetchRuns();
      } catch {
        toast.error("Failed to delete run");
        setDeletingId(null);
      }
    } else {
      // First click — ask for confirmation
      setDeletingId(runId);
      toast.info("Click delete again to confirm permanent deletion", { duration: 3000 });
      // Auto-reset after 3s if not confirmed
      if (deleteTimerRef.current) clearTimeout(deleteTimerRef.current);
      deleteTimerRef.current = setTimeout(() => setDeletingId((prev) => (prev === runId ? null : prev)), 3000);
    }
  }, [deletingId, fetchRuns]);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">Run History</h1>
        <Button variant="outline" size="sm" onClick={() => setShowArchived(!showArchived)}>
          {showArchived ? "Hide archived" : "Show archived"}
        </Button>
      </div>
      {runs.length === 0 ? (
        <p className="text-muted-foreground">No runs yet.</p>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <div
              key={run.run_id}
              onClick={() => {
                if (run.status === "plan_ready") {
                  navigate(`/runs/${run.run_id}/plan`);
                } else {
                  navigate(`/runs/${run.run_id}/results`);
                }
              }}
              className={`w-full text-left p-3 border rounded-md hover:bg-accent flex items-center justify-between cursor-pointer ${
                run.archived ? "opacity-50" : ""
              }`}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{run.display_name || run.dataset_name}</span>
                  {run.archived && <Badge variant="outline" className="text-xs">Archived</Badge>}
                </div>
                <span className="text-xs text-muted-foreground font-mono">{run.run_id.slice(0, 12)}</span>
                {run.notes && (
                  <p className="text-xs text-muted-foreground mt-1 truncate">{run.notes}</p>
                )}
              </div>
              <div className="flex items-center gap-2 ml-2">
                <Badge variant={
                  run.status === "plan_ready" ? "outline" :
                  run.status === "stopped" ? "secondary" :
                  run.status === "running" || run.status === "pending" ? "secondary" :
                  run.status === "error" ? "destructive" :
                  run.validation_passed ? "default" : "destructive"
                }>
                  {run.status === "plan_ready" ? "Plan Ready" :
                   run.status === "stopped" ? "Stopped" :
                   run.status === "running" ? "Running" :
                   run.status === "pending" ? "Pending" :
                   run.status === "error" ? "Error" :
                   run.validation_passed ? "Passed" : "Failed"}
                </Badge>
                <Button variant="ghost" size="sm"
                  onClick={(e) => handleArchive(e, run.run_id)}
                  title={run.archived ? "Unarchive" : "Archive"}>
                  {run.archived ? <ArchiveRestore className="h-4 w-4" /> : <Archive className="h-4 w-4" />}
                </Button>
                <Button variant="ghost" size="sm"
                  onClick={(e) => handleDelete(e, run.run_id)}
                  title={deletingId === run.run_id ? "Click again to confirm" : "Delete permanently"}
                  className={deletingId === run.run_id ? "text-destructive hover:text-destructive" : "hover:text-destructive"}>
                  <Trash2 className="h-4 w-4" />
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
