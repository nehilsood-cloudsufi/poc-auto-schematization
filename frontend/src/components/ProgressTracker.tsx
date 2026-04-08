/**
 * Real-time pipeline progress display with Lucide icons and expandable errors.
 */
import { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
import { PIPELINE_PHASES, PHASE_LABELS } from "@/types";
import type { ProgressEvent } from "@/types";
import {
  CheckCircle2,
  Circle,
  Loader2,
  XCircle,
  Clock,
  ChevronDown,
  ChevronRight,
} from "lucide-react";

interface ProgressTrackerProps {
  events: ProgressEvent[];
  startTime: number;
  phases?: readonly string[];
}

export function ProgressTracker({ events, startTime, phases }: ProgressTrackerProps) {
  const [elapsed, setElapsed] = useState(0);
  const [expandedError, setExpandedError] = useState<string | null>(null);

  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  const completedAgents = new Set(events.map((e) => e.agent));
  const currentAttempt = Math.max(0, ...events.map((e) => e.attempt ?? 0));
  const errorEvents = new Map(
    events.filter((e) => e.type === "error").map((e) => [e.agent, e])
  );

  const allPhases = phases ? [...phases] : [...PIPELINE_PHASES];
  const completedCount = allPhases.filter((p) => completedAgents.has(p)).length;
  const progressPct = (completedCount / allPhases.length) * 100;

  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

  return (
    <Card className="shadow-sm">
      <CardContent className="pt-6">
        <div className="flex items-center justify-between mb-4">
          <div className="flex items-center gap-3">
            <Loader2 className="w-4 h-4 text-primary animate-spin" />
            <h2 className="text-base font-semibold">
              {currentAttempt > 0 ? `Attempt ${currentAttempt + 1}` : "Pipeline running..."}
            </h2>
          </div>
          <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Clock className="w-3.5 h-3.5" />
            <span className="tabular-nums">{elapsedStr}</span>
          </div>
        </div>

        <Progress value={progressPct} className="mb-1" />
        <p className="text-xs text-muted-foreground mb-5">
          {completedCount}/{allPhases.length} phases complete
        </p>

        <ul className="space-y-1.5">
          {allPhases.map((phase) => {
            const label = PHASE_LABELS[phase] || phase;
            const isCompleted = completedAgents.has(phase);
            const hasError = errorEvents.has(phase);
            const isNext =
              !isCompleted &&
              !hasError &&
              completedCount > 0 &&
              allPhases.indexOf(phase) ===
                allPhases.findIndex((p) => !completedAgents.has(p));
            const isExpanded = expandedError === phase;

            return (
              <li key={phase}>
                <div className="flex items-center gap-3">
                  {hasError ? (
                    <button
                      onClick={() => setExpandedError(isExpanded ? null : phase)}
                      className="flex items-center gap-0.5 cursor-pointer"
                    >
                      <XCircle className="w-4.5 h-4.5 text-destructive flex-shrink-0" />
                      {isExpanded ? (
                        <ChevronDown className="w-3 h-3 text-destructive" />
                      ) : (
                        <ChevronRight className="w-3 h-3 text-destructive" />
                      )}
                    </button>
                  ) : isCompleted ? (
                    <CheckCircle2 className="w-4.5 h-4.5 text-green-500 flex-shrink-0" />
                  ) : isNext ? (
                    <Loader2 className="w-4.5 h-4.5 text-primary animate-spin flex-shrink-0" />
                  ) : (
                    <Circle className="w-4.5 h-4.5 text-muted-foreground/40 flex-shrink-0" />
                  )}

                  <span
                    className={`text-sm ${
                      hasError
                        ? "text-destructive font-medium"
                        : isCompleted
                          ? "text-foreground"
                          : isNext
                            ? "text-primary font-medium"
                            : "text-muted-foreground"
                    }`}
                  >
                    {label}
                  </span>
                </div>

                {hasError && isExpanded && (
                  <div className="ml-8 mt-1 p-2 rounded bg-destructive/5 border border-destructive/20 text-xs font-mono text-destructive max-h-32 overflow-auto">
                    {errorEvents.get(phase)?.message || "Unknown error"}
                  </div>
                )}
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
