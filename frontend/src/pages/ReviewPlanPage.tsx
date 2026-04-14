/**
 * Wizard Step 3: Review the mapping plan as rendered markdown.
 *
 * Two modes:
 * - View (default): Rendered markdown with headings, tables, code blocks
 * - Edit: Raw markdown textarea (monospace, full height)
 *
 * Feedback & Notes section always visible below.
 */
import { useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import ReactMarkdown from "react-markdown";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { PlanFeedback } from "@/components/PlanReview/PlanFeedback";
import { useWebSocket } from "@/hooks/useWebSocket";
import {
  getPlan,
  getPlanMarkdown,
  approvePlan,
  generatePvmap,
  stopRun,
  regeneratePlan,
  addPlanNote,
  getRun,
} from "@/lib/api";
import { toast } from "sonner";
import { PLAN_PHASES } from "@/types";
import type { MappingPlan } from "@/types";
import {
  ChevronLeft,
  Play,
  Square,
  CheckCircle2,
  AlertTriangle,
} from "lucide-react";

interface ReviewPlanPageProps {
  datasetName: string;
  startTime: number;
  onGenerateStarted: () => void;
  onError: (event: import("@/types").ProgressEvent) => void;
}

export function ReviewPlanPage({
  datasetName, startTime, onGenerateStarted, onError,
}: ReviewPlanPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();

  const [plan, setPlan] = useState<MappingPlan | null>(null);
  const [planReady, setPlanReady] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [regenerating, setRegenerating] = useState(false);
  const regenStartRef = useRef<number>(startTime);
  const [planError, setPlanError] = useState<string | null>(null);

  const [markdown, setMarkdown] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editText, setEditText] = useState("");
  const [readOnly, setReadOnly] = useState(false);

  // --- On mount: load run status + plan data in one coordinated flow ---
  useEffect(() => {
    if (!runId) return;
    let cancelled = false;

    async function loadPlan() {
      // Step 1: Check run status first
      try {
        const run = await getRun(runId!);
        if (cancelled) return;
        const isCompleted = run.status !== "plan_ready" && run.status !== "pending" && run.status !== "running";
        if (isCompleted) setReadOnly(true);
      } catch {
        // Can't determine status — assume active
      }

      // Step 2: Try loading plan data
      try {
        const [planData, md] = await Promise.all([
          getPlan(runId!).catch(() => null),
          getPlanMarkdown(runId!).catch(() => ""),
        ]);
        if (cancelled) return;

        if (planData && planData.active_columns) {
          setPlan(planData);
          setPlanReady(true);
          if (md) setMarkdown(md);
        } else {
          // No plan — check if run finished (plan generation failed) or still running
          const run = await getRun(runId!).catch(() => null);
          if (cancelled) return;
          if (run && (run.status === "plan_ready" || run.status === "stopped" || run.status === "error")) {
            setPlanReady(true);
            setPlanError("Plan generation failed. Try 'Regenerate' below.");
          }
          // If still running/pending, WebSocket will handle it
        }
      } catch {
        // Network error
      }
    }

    loadPlan();
    return () => { cancelled = true; };
  }, [runId]);

  // --- WebSocket: listen for plan generation progress (only when plan not ready) ---
  const { events } = useWebSocket({
    runId: runId ?? null,
    enabled: !planReady && !readOnly,  // Don't connect WebSocket for completed runs
    onComplete: (event) => {
      if (event.result?.phase === "plan") {
        setPlanReady(true);
        setRegenerating(false);
        toast.info("Plan ready for review");
        // Reload plan data
        if (runId) {
          getPlan(runId).then((data) => setPlan(data)).catch(() => {});
          getPlanMarkdown(runId).then((md) => setMarkdown(md)).catch(() => {});
        }
      } else {
        navigate(`/runs/${runId}/results`);
      }
    },
    onError,
  });

  // --- Handlers ---

  const handleApprove = async () => {
    if (!runId || !plan) return;
    setSubmitting(true);
    try {
      await approvePlan(runId, plan);
      await generatePvmap(runId);
      onGenerateStarted();
      navigate(`/runs/${runId}`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start generation");
    } finally {
      setSubmitting(false);
    }
  };

  const handleStop = async () => {
    if (!runId || stopping) return;
    if (!window.confirm("Stop this run?")) return;
    setStopping(true);
    try {
      await stopRun(runId);
      navigate(`/runs/${runId}/results`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to stop");
      setStopping(false);
    }
  };

  const handleAddNote = async (note: string) => {
    if (!runId) return;
    try {
      const result = await addPlanNote(runId, note);
      setPlan(prev => prev ? { ...prev, engineer_notes: result.notes } : prev);
      toast.success("Note added");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to add note");
    }
  };

  const handleRegenerate = async (feedback: string, deep: boolean) => {
    if (!runId) return;
    const previousPlan = plan;
    setRegenerating(true);
    setPlanReady(false);
    regenStartRef.current = Date.now();
    setPlan(null);
    try {
      await regeneratePlan(runId, feedback, deep);
      // WebSocket will notify when new plan is ready via onComplete
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to regenerate");
      setRegenerating(false);
      setPlanReady(true);
      setPlan(previousPlan);
    }
  };

  // --- Render: plan generation in progress ---
  if (!planReady) {
    return (
      <div className="p-8 max-w-2xl mx-auto">
        <WizardStepper currentStep={2} />
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-2xl font-bold">Preparing Your Plan</h1>
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
        <ProgressTracker events={events} startTime={regenStartRef.current} phases={PLAN_PHASES} />

        <Card className="shadow-sm mt-4">
          <CardContent className="pt-6">
            <div className="space-y-3">
              {Array.from({ length: 8 }, (_, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${50 + Math.random() * 50}%` }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // --- Render: loading plan data or error ---
  if (loadingPlan || !plan) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <WizardStepper currentStep={2} />
        {planError ? (
          <Card className="shadow-sm mt-6 border-destructive/50">
            <CardContent className="pt-6">
              <div className="flex items-start gap-3">
                <AlertTriangle className="w-5 h-5 text-destructive mt-0.5 shrink-0" />
                <div className="space-y-3">
                  <p className="text-sm font-medium text-destructive">{planError}</p>
                  <PlanFeedback
                    notes={[]}
                    onRegenerate={handleRegenerate}
                    onAddNote={handleAddNote}
                    regenerating={regenerating}
                  />
                </div>
              </div>
            </CardContent>
          </Card>
        ) : (
          <Card className="shadow-sm mt-6">
            <CardContent className="pt-6">
              <div className="space-y-3">
                {Array.from({ length: 12 }, (_, i) => (
                  <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${40 + Math.random() * 60}%` }} />
                ))}
              </div>
            </CardContent>
          </Card>
        )}
      </div>
    );
  }

  // --- Render: interactive plan review ---
  const stepClickHandler = readOnly
    ? (step: number) => {
        if (!runId) return;
        if (step === 0) navigate("/");
        else if (step === 1) navigate("/configure");
        else if (step === 4) navigate(`/runs/${runId}/results`);
        // Step 3 (Generate/Progress) has no useful state for completed runs — skip
      }
    : undefined;

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <WizardStepper currentStep={2} completedUpTo={readOnly ? 5 : undefined} onStepClick={stepClickHandler} />

      {/* Page header */}
      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold">Review Mapping Plan</h1>
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-500" />
          <span className="text-sm text-green-600 dark:text-green-400 font-medium">Plan Ready</span>
        </div>
      </div>
      <p className="text-muted-foreground mb-4">
        Dataset: <span className="font-mono font-medium">{plan?.dataset_name || datasetName}</span>
      </p>

      {/* Plan content */}
      <Card className="shadow-sm mb-4">
        <CardContent className="pt-5 pb-4">
          <div className="flex items-center justify-between mb-3">
            <h2 className="text-sm font-semibold">Mapping Plan</h2>
            {!readOnly && (
              <button
                onClick={() => {
                  if (!editMode) setEditText(markdown);
                  setEditMode(!editMode);
                }}
                className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
              >
                {editMode ? "View Rendered" : "Edit Markdown"}
              </button>
            )}
          </div>

          {editMode ? (
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full font-mono text-xs leading-relaxed p-3 rounded-md border bg-muted/30 resize-vertical focus:outline-none focus:ring-2 focus:ring-ring"
              rows={30}
              spellCheck={false}
            />
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-base prose-h1:text-lg prose-h2:text-base prose-h3:text-sm prose-table:text-xs prose-code:text-xs prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-td:py-1 prose-th:py-1 prose-pre:bg-muted prose-pre:text-foreground prose-pre:border prose-pre:border-border prose-pre:rounded-md prose-pre:overflow-x-auto">
              <ReactMarkdown>{markdown || "No plan content available. Click 'Regenerate' below to generate a plan."}</ReactMarkdown>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Feedback & Notes — hidden in read-only until unlocked */}
      {!readOnly && (
        <Card className="shadow-sm mb-4">
          <CardContent className="pt-5 pb-4">
            <h2 className="text-sm font-semibold mb-3">Feedback & Notes</h2>
            <PlanFeedback
              notes={plan?.engineer_notes ?? []}
              onAddNote={handleAddNote}
              onRegenerate={handleRegenerate}
              regenerating={regenerating}
            />
          </CardContent>
        </Card>
      )}

      {/* Navigation */}
      <div className="flex justify-between mt-6 pb-8">
        <Button variant="ghost" onClick={() => {
          if (readOnly && runId) {
            navigate(`/runs/${runId}/results`);
          } else {
            navigate("/configure");
          }
        }} className="gap-1.5">
          <ChevronLeft className="w-4 h-4" /> {readOnly ? "Back to Results" : "Back"}
        </Button>
        <div className="flex items-center gap-2">
          {readOnly ? (
            <Button
              variant="outline"
              onClick={() => setReadOnly(false)}
              className="gap-2"
            >
              Edit & Regenerate
            </Button>
          ) : (
            <Button onClick={handleApprove} disabled={submitting || editMode} size="lg" className="gap-2">
              {submitting ? "Starting..." : editMode ? "Exit edit mode to approve" : "Approve & Generate PVMAP"}
              {!submitting && !editMode && <Play className="w-4 h-4" />}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
