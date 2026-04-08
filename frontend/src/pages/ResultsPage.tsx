/**
 * Wizard Step 5: View results, edit PVMAP, provide feedback.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { WizardStepper } from "@/components/WizardStepper";
import { OutputViewer } from "@/components/OutputViewer";
import { FeedbackForm } from "@/components/FeedbackForm";
import { DownloadButton } from "@/components/DownloadButton";
import { Button } from "@/components/ui/button";
import { DataExplorer } from "@/components/DataExplorer";
import { getRun, resumeRun } from "@/lib/api";
import { toast } from "sonner";
import { Play, Pause, Loader2 } from "lucide-react";
import type { PipelineResult } from "@/types";

interface ResultsPageProps {
  datasetName: string;
  result?: PipelineResult;
  onRerunStarted: (newRunId: string) => void;
}

export function ResultsPage({ datasetName: propDatasetName, result: propResult, onRerunStarted }: ResultsPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const [datasetName, setDatasetName] = useState(propDatasetName);
  const [result, setResult] = useState<PipelineResult | undefined>(propResult);
  const [loading, setLoading] = useState(false);
  const [runStatus, setRunStatus] = useState<string>("");
  const [resuming, setResuming] = useState(false);

  useEffect(() => {
    if (propDatasetName) setDatasetName(propDatasetName);
    if (propResult) setResult(propResult);
  }, [propDatasetName, propResult]);

  useEffect(() => {
    if (!runId) return;
    setLoading(true);
    getRun(runId)
      .then((run) => {
        setRunStatus(run.status);
        if (!propDatasetName) setDatasetName(run.dataset_name ?? "");
        if (!propResult && run.result && Object.keys(run.result).length > 0) {
          setResult(run.result as PipelineResult);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [runId]);

  const handleResume = async () => {
    if (!runId || resuming) return;
    setResuming(true);
    try {
      await resumeRun(runId);
      toast.info("Resuming pipeline...");
      onRerunStarted(runId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to resume");
      setResuming(false);
    }
  };

  if (!runId) return null;

  return (
    <div className="min-h-screen bg-muted/20 p-8">
      <div className="max-w-6xl mx-auto">
        <WizardStepper currentStep={4} />

        <div className="flex items-center justify-between mt-6 mb-5">
          <div>
            {loading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                <span className="text-lg text-muted-foreground">Loading results...</span>
              </div>
            ) : (
              <>
                <h1 className="text-2xl font-bold">
                  Results
                  {datasetName && (
                    <span className="text-muted-foreground font-mono ml-2 text-xl">
                      — {datasetName}
                    </span>
                  )}
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                  Run ID: <span className="font-mono">{runId.slice(0, 12)}</span>
                </p>
              </>
            )}
          </div>
          <DownloadButton runId={runId} datasetName={datasetName} />
        </div>

        {runStatus === "stopped" && (
          <Card className="shadow-sm mb-6 border-amber-200 dark:border-amber-800">
            <CardContent className="pt-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Pause className="w-5 h-5 text-amber-500" />
                <div>
                  <p className="font-medium">Run was stopped</p>
                  <p className="text-sm text-muted-foreground">
                    Partial results shown below. Resume to continue from the last checkpoint.
                  </p>
                </div>
              </div>
              <Button onClick={handleResume} disabled={resuming} className="gap-2">
                {resuming ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Resuming...</>
                ) : (
                  <><Play className="w-4 h-4" /> Resume Run</>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        <div className="mb-6">
          <DataExplorer runId={runId} />
        </div>

        <Card className="shadow-sm mb-6">
          <CardContent className="pt-6">
            <OutputViewer runId={runId} result={result} />
          </CardContent>
        </Card>

        <Separator className="my-6" />

        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <FeedbackForm runId={runId} onRerunStarted={onRerunStarted} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
