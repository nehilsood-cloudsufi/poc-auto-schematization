/**
 * Real-time pipeline progress display.
 *
 * Shows a phase checklist with status icons, progress bar, and elapsed time.
 */
import { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { PIPELINE_PHASES, PHASE_LABELS } from "@/types";
import type { ProgressEvent } from "@/types";

interface ProgressTrackerProps {
  events: ProgressEvent[];
  startTime: number;
}

export function ProgressTracker({ events, startTime }: ProgressTrackerProps) {
  const [elapsed, setElapsed] = useState(0);

  // Update elapsed time every second
  useEffect(() => {
    const interval = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startTime) / 1000));
    }, 1000);
    return () => clearInterval(interval);
  }, [startTime]);

  // Track completed agents and current attempt
  const completedAgents = new Set(events.map((e) => e.agent));
  const currentAttempt = Math.max(0, ...events.map((e) => e.attempt ?? 0));

  // Calculate progress
  const allPhases = [...PIPELINE_PHASES];
  const completedCount = allPhases.filter((p) => completedAgents.has(p)).length;
  const progressPct = (completedCount / allPhases.length) * 100;

  // Format elapsed time
  const minutes = Math.floor(elapsed / 60);
  const seconds = elapsed % 60;
  const elapsedStr = minutes > 0 ? `${minutes}m ${seconds}s` : `${seconds}s`;

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-medium">
          {currentAttempt > 0 ? `Attempt ${currentAttempt + 1}` : "Pipeline running..."}
        </h2>
        <span className="text-sm text-muted-foreground">Elapsed: {elapsedStr}</span>
      </div>

      {/* Progress bar */}
      <Progress value={progressPct} />
      <p className="text-xs text-muted-foreground">
        {completedCount}/{allPhases.length} phases
      </p>

      {/* Phase checklist */}
      <ul className="space-y-1">
        {allPhases.map((phase) => {
          const label = PHASE_LABELS[phase] || phase;
          const isCompleted = completedAgents.has(phase);
          const isNext =
            !isCompleted &&
            completedCount > 0 &&
            allPhases.indexOf(phase) ===
              allPhases.findIndex((p) => !completedAgents.has(p));

          return (
            <li key={phase} className="flex items-center gap-2 text-sm">
              {isCompleted ? (
                <span className="text-green-600">✓</span>
              ) : isNext ? (
                <span className="text-blue-500 animate-pulse">⟳</span>
              ) : (
                <span className="text-muted-foreground">○</span>
              )}
              <span
                className={
                  isCompleted
                    ? "text-foreground"
                    : isNext
                      ? "text-blue-600 font-medium"
                      : "text-muted-foreground"
                }
              >
                {label}
              </span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
