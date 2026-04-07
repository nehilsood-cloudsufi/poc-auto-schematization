/**
 * Real-time pipeline progress display.
 *
 * Shows a phase checklist with status icons, progress bar, and elapsed time.
 */
import { useEffect, useState } from "react";
import { Progress } from "@/components/ui/progress";
import { Card, CardContent } from "@/components/ui/card";
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
    <Card className="shadow-sm">
      <CardContent className="pt-6">
        {/* Header */}
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold">
            {currentAttempt > 0 ? `Attempt ${currentAttempt + 1}` : "Pipeline running..."}
          </h2>
          <span className="text-sm text-muted-foreground tabular-nums">⏱ {elapsedStr}</span>
        </div>

        {/* Progress bar */}
        <Progress value={progressPct} className="mb-1" />
        <p className="text-xs text-muted-foreground mb-5">
          {completedCount}/{allPhases.length} phases complete
        </p>

        {/* Phase checklist */}
        <ul className="space-y-2">
          {allPhases.map((phase) => {
            const label = PHASE_LABELS[phase] || phase;
            const isCompleted = completedAgents.has(phase);
            const isNext =
              !isCompleted &&
              completedCount > 0 &&
              allPhases.indexOf(phase) ===
                allPhases.findIndex((p) => !completedAgents.has(p));

            return (
              <li key={phase} className="flex items-center gap-3">
                <span className={`
                  w-5 h-5 rounded-full flex items-center justify-center text-xs flex-shrink-0
                  ${isCompleted
                    ? "bg-green-100 dark:bg-green-900 text-green-600 dark:text-green-300"
                    : isNext
                      ? "bg-blue-100 dark:bg-blue-900 text-blue-500 animate-pulse"
                      : "bg-muted text-muted-foreground"
                  }
                `}>
                  {isCompleted ? "✓" : isNext ? "⟳" : "○"}
                </span>
                <span
                  className={`text-sm ${
                    isCompleted
                      ? "text-foreground"
                      : isNext
                        ? "text-blue-600 dark:text-blue-400 font-medium"
                        : "text-muted-foreground"
                  }`}
                >
                  {label}
                </span>
              </li>
            );
          })}
        </ul>
      </CardContent>
    </Card>
  );
}
