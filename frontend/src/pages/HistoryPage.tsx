import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { listRuns } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import type { Run } from "@/types";

export function HistoryPage() {
  const [runs, setRuns] = useState<Run[]>([]);
  const navigate = useNavigate();

  useEffect(() => {
    listRuns().then(setRuns).catch(() => setRuns([]));
  }, []);

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <h1 className="text-2xl font-bold mb-6">Run History</h1>
      {runs.length === 0 ? (
        <p className="text-muted-foreground">No runs yet.</p>
      ) : (
        <div className="space-y-2">
          {runs.map((run) => (
            <button
              key={run.run_id}
              onClick={() => navigate(`/runs/${run.run_id}/results`)}
              className="w-full text-left p-3 border rounded-md hover:bg-accent flex items-center justify-between"
            >
              <div>
                <span className="font-medium">{run.dataset_name}</span>
                <span className="text-xs text-muted-foreground ml-2 font-mono">
                  {run.run_id.slice(0, 12)}
                </span>
              </div>
              <Badge variant={run.validation_passed ? "default" : "destructive"}>
                {run.validation_passed ? "Passed" : "Failed"}
              </Badge>
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
