/**
 * Wizard Step 4: View results, edit PVMAP, provide feedback.
 *
 * When navigating directly from the sidebar (historical run), fetches run
 * data from the API so datasetName and result are populated.
 */
import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { WizardStepper } from "@/components/WizardStepper";
import { OutputViewer } from "@/components/OutputViewer";
import { FeedbackForm } from "@/components/FeedbackForm";
import { DownloadButton } from "@/components/DownloadButton";
import { getRun } from "@/lib/api";
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

  // When navigating directly to a historical run, props are empty — fetch from API
  useEffect(() => {
    if (!runId) return;
    if (propDatasetName) {
      setDatasetName(propDatasetName);
      setResult(propResult);
      return;
    }
    // Historical navigation: load run metadata from backend
    setLoading(true);
    getRun(runId)
      .then((run) => {
        setDatasetName(run.dataset_name ?? "");
        if (run.result && Object.keys(run.result).length > 0) {
          setResult(run.result as PipelineResult);
        }
      })
      .catch(() => {
        // Run not found or API error — show empty state
        setDatasetName("");
      })
      .finally(() => setLoading(false));
  }, [runId, propDatasetName, propResult]);

  if (!runId) return null;

  return (
    <div className="min-h-screen bg-muted/20 p-8">
      <div className="max-w-6xl mx-auto">
        <WizardStepper currentStep={3} />

        {/* Page header */}
        <div className="flex items-center justify-between mt-6 mb-5">
          <div>
            <h1 className="text-2xl font-bold">
              {loading ? (
                <span className="text-muted-foreground">Loading...</span>
              ) : (
                <>
                  Results
                  {datasetName && (
                    <span className="text-muted-foreground font-mono ml-2 text-xl">
                      — {datasetName}
                    </span>
                  )}
                </>
              )}
            </h1>
            <p className="text-sm text-muted-foreground mt-1">
              Run ID: <span className="font-mono">{runId}</span>
            </p>
          </div>
          <DownloadButton runId={runId} datasetName={datasetName} />
        </div>

        {/* Output files section */}
        <Card className="shadow-sm mb-6">
          <CardContent className="pt-6">
            <OutputViewer runId={runId} result={result} />
          </CardContent>
        </Card>

        <Separator className="my-6" />

        {/* Feedback section */}
        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <h2 className="text-base font-semibold mb-4">Provide Feedback</h2>
            <FeedbackForm runId={runId} onRerunStarted={onRerunStarted} />
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
