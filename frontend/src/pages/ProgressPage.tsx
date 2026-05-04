/**
 * Wizard Step 4: Real-time pipeline progress with status header and activity log.
 */
import { useState, useRef, useEffect } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { useWebSocket } from "@/hooks/useWebSocket";
import { stopRun, getRun } from "@/lib/api";
import { toast } from "sonner";
import { GENERATE_PHASES } from "@/types";
import type { ProgressEvent } from "@/types";
import {
  Square,
  Loader2,
  Clock,
  ChevronDown,
  ChevronUp,
  AlertTriangle,
  Info,
  CheckCircle2,
} from "lucide-react";

interface ProgressPageProps {
  startTime: number;
  onComplete: (result: ProgressEvent) => void;
  onError: (event: ProgressEvent) => void;
}

function EventIcon({ type }: { type: string }) {
  if (type === "error") return <AlertTriangle className="w-3 h-3 text-destructive flex-shrink-0" />;
  if (type === "complete") return <CheckCircle2 className="w-3 h-3 text-green-500 flex-shrink-0" />;
  return <Info className="w-3 h-3 text-muted-foreground flex-shrink-0" />;
}

export function ProgressPage({ startTime, onComplete, onError }: ProgressPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [stopping, setStopping] = useState(false);
  const [showLog, setShowLog] = useState(false);
  const [elapsed, setElapsed] = useState(0);
  const logRef = useRef<HTMLDivElement>(null);
  const navTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // Redirect completed runs to results page immediately
  useEffect(() => {
    if (!runId) return;
    getRun(runId).then((run) => {
      if (run.status === "complete" || run.status === "error" || run.status === "stopped") {
        navigate(`/runs/${runId}/results`, { replace: true });
      }
    }).catch(() => {});
  }, [runId, navigate]);

  const { events, connected } = useWebSocket({
    runId: runId ?? null,
    onComplete: (event) => {
      onComplete(event);
      toast.success("Pipeline complete!");
      navTimerRef.current = setTimeout(() => navigate(`/runs/${runId}/results`), 1500);
    },
    onError: (event) => {
      onError(event);
      toast.error("Pipeline encountered an error");
    },
  });

  // Polling fallback: when WebSocket disconnects (Cloud Run restart),
  // poll the run status to detect completion
  useEffect(() => {
    if (!runId || connected) return;
    const poll = setInterval(async () => {
      try {
        const run = await getRun(runId);
        if (run.status === "complete" || run.status === "error" || run.status === "stopped" || run.status === "plan_ready") {
          clearInterval(poll);
          navigate(`/runs/${runId}/results`, { replace: true });
        }
      } catch { /* ignore — next poll will retry */ }
    }, 10_000);
    return () => clearInterval(poll);
  }, [runId, connected, navigate]);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  useEffect(() => {
    return () => {
      if (navTimerRef.current) clearTimeout(navTimerRef.current);
    };
  }, [runId]);

  useEffect(() => {
    if (logRef.current && showLog) {
      logRef.current.scrollTop = logRef.current.scrollHeight;
    }
  }, [events, showLog]);

  const currentAttempt = events.reduce((max, e) => Math.max(max, e.attempt ?? 0), 0);
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

  const handleStop = async () => {
    if (!runId || stopping) return;
    if (!window.confirm("Stop this run? You can resume later from the last checkpoint.")) return;
    setStopping(true);
    try {
      await stopRun(runId);
      navigate(`/runs/${runId}/results`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to stop run");
      setStopping(false);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <WizardStepper
        currentStep={3}
        onStepClick={(step) => {
          if (!runId) return;
          if (step === 2) navigate(`/runs/${runId}/plan`);
        }}
      />

      <Card className="shadow-sm mb-4">
        <CardContent className="py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <Loader2 className="w-5 h-5 text-primary animate-spin" />
              <div>
                <h1 className="text-lg font-semibold">Generating PVMAP</h1>
                <div className="flex items-center gap-2 mt-0.5">
                  {currentAttempt > 0 && (
                    <Badge variant="secondary" className="text-xs">
                      Attempt {currentAttempt + 1}
                    </Badge>
                  )}
                  <div className="flex items-center gap-1 text-xs text-muted-foreground">
                    <Clock className="w-3 h-3" />
                    <span className="tabular-nums">{elapsedStr}</span>
                  </div>
                </div>
              </div>
            </div>
            <Button
              variant="outline"
              size="sm"
              onClick={handleStop}
              disabled={stopping}
              className="text-destructive border-destructive/50 hover:bg-destructive/10 gap-1.5"
            >
              <Square className="w-3.5 h-3.5" />
              {stopping ? "Stopping..." : "Stop"}
            </Button>
          </div>
        </CardContent>
      </Card>

      <ProgressTracker events={events} startTime={startTime} phases={GENERATE_PHASES} />

      <div className="mt-4">
        <button
          type="button"
          onClick={() => setShowLog(!showLog)}
          className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors cursor-pointer mb-2"
        >
          {showLog ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          Activity Log ({events.length} events)
        </button>
        {showLog && (
          <Card className="shadow-sm">
            <div
              ref={logRef}
              className="max-h-64 overflow-auto p-3 space-y-1"
            >
              {events.length === 0 ? (
                <p className="text-xs text-muted-foreground text-center py-4">Waiting for events...</p>
              ) : (
                events.map((event, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs font-mono">
                    <EventIcon type={event.type} />
                    <span className="text-muted-foreground tabular-nums whitespace-nowrap">
                      {event.agent}
                    </span>
                    <span className={
                      event.type === "error" ? "text-destructive" :
                      event.type === "complete" ? "text-green-600 dark:text-green-400" :
                      "text-foreground"
                    }>
                      {event.message}
                    </span>
                  </div>
                ))
              )}
            </div>
          </Card>
        )}
      </div>
    </div>
  );
}
