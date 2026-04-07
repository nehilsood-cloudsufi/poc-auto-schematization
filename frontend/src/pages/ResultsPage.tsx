/**
 * Wizard Step 4: View results, edit PVMAP, provide feedback.
 */
import { useParams } from "react-router-dom";
import { Separator } from "@/components/ui/separator";
import { WizardStepper } from "@/components/WizardStepper";
import { OutputViewer } from "@/components/OutputViewer";
import { FeedbackForm } from "@/components/FeedbackForm";
import { DownloadButton } from "@/components/DownloadButton";
import type { PipelineResult } from "@/types";

interface ResultsPageProps {
  datasetName: string;
  result?: PipelineResult;
  onRerunStarted: (newRunId: string) => void;
}

export function ResultsPage({ datasetName, result, onRerunStarted }: ResultsPageProps) {
  const { runId } = useParams<{ runId: string }>();

  if (!runId) return null;

  return (
    <div className="p-8 max-w-6xl mx-auto">
      <WizardStepper currentStep={3} />

      <div className="flex items-center justify-between mb-6">
        <h1 className="text-2xl font-bold">
          Results: <span className="font-mono">{datasetName}</span>
        </h1>
        <DownloadButton runId={runId} datasetName={datasetName} />
      </div>

      <OutputViewer runId={runId} result={result} />

      <Separator className="my-6" />

      <FeedbackForm runId={runId} onRerunStarted={onRerunStarted} />
    </div>
  );
}
