/**
 * Wizard Step 3: Real-time pipeline progress.
 */
import { useNavigate, useParams } from "react-router-dom";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { useWebSocket } from "@/hooks/useWebSocket";
import type { ProgressEvent } from "@/types";

interface ProgressPageProps {
  startTime: number;
  onComplete: (result: ProgressEvent) => void;
  onError: (event: ProgressEvent) => void;
}

export function ProgressPage({ startTime, onComplete, onError }: ProgressPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const { events } = useWebSocket({
    runId: runId ?? null,
    onComplete: (event) => {
      onComplete(event);
      navigate(`/runs/${runId}/results`);
    },
    onError,
  });

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <WizardStepper currentStep={2} />
      <ProgressTracker events={events} startTime={startTime} />
    </div>
  );
}
