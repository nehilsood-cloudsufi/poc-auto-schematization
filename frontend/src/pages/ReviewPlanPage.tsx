/**
 * Wizard Step 3: Review the mapping plan as rendered markdown.
 *
 * Two modes:
 * - View (default): Rendered markdown with headings, tables, code blocks
 * - Edit: Raw markdown textarea (monospace, full height)
 *
 * Feedback & Notes section always visible below.
 */
import { useEffect, useState } from "react";
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
  const [planError, setPlanError] = useState<string | null>(null);

  const [markdown, setMarkdown] = useState("");
  const [editMode, setEditMode] = useState(false);
  const [editText, setEditText] = useState("");

  // --- WebSocket: listen for plan generation progress ---
  const { events } = useWebSocket({
    runId: runId ?? null,
    enabled: !planReady,
    onComplete: (event) => {
      if (event.result?.phase === "plan") {
        setPlanReady(true);
        setRegenerating(false);
        toast.info("Plan ready for review");
      } else {
        navigate(`/runs/${runId}/results`);
      }
    },
    onError,
  });

  // --- Load plan when ready (via WebSocket completion) ---
  useEffect(() => {
    if (!planReady || !runId || plan !== null) return;
    setLoadingPlan(true);
    Promise.all([
      getPlan(runId).then((data) => setPlan(data)).catch(() => {}),
      getPlanMarkdown(runId).then((md) => setMarkdown(md)).catch(() => {}),
    ]).finally(() => setLoadingPlan(false));
  }, [planReady, runId, plan]);

  // --- On mount: check if plan already exists (e.g. page refresh) ---
  useEffect(() => {
    if (!runId) return;
    getPlan(runId)
      .then((data) => {
        if (data && data.active_columns) {
          setPlan(data);
          setPlanReady(true);
        }
      })
      .catch(() => {
        // Plan not found -- check if the run already finished
        getRun(runId)
          .then((run) => {
            if (run.status === "plan_ready" || run.status === "stopped" || run.status === "error") {
              setPlanReady(true);
              setPlanError("Plan generation failed. Try 'Regenerate' below.");
            }
          })
          .catch(() => {});
      });
    // Also load markdown
    getPlanMarkdown(runId)
      .then((md) => setMarkdown(md))
      .catch(() => {});
  }, [runId]);

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
        <ProgressTracker events={events} startTime={startTime} phases={PLAN_PHASES} />

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
                    onAddNote={() => {}}
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
  return (
    <div className="p-8 max-w-4xl mx-auto">
      <WizardStepper currentStep={2} />

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
            <button
              onClick={() => {
                if (!editMode) setEditText(markdown);
                setEditMode(!editMode);
              }}
              className="text-xs text-muted-foreground hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-muted"
            >
              {editMode ? "View Rendered" : "Edit Markdown"}
            </button>
          </div>

          {editMode ? (
            <textarea
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
              className="w-full font-mono text-xs leading-relaxed p-3 rounded-md border bg-muted/30 resize-vertical focus:outline-none focus:ring-2 focus:ring-ring"
              style={{ minHeight: "400px", height: "60vh", maxHeight: "80vh" }}
              spellCheck={false}
            />
          ) : (
            <div className="prose prose-sm dark:prose-invert max-w-none prose-headings:text-base prose-h1:text-lg prose-h2:text-base prose-h3:text-sm prose-table:text-xs prose-code:text-xs prose-code:bg-muted prose-code:px-1 prose-code:py-0.5 prose-code:rounded prose-td:py-1 prose-th:py-1">
              <ReactMarkdown>{markdown || "No plan content available. Click 'Regenerate' below to generate a plan."}</ReactMarkdown>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Feedback & Notes */}
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

      {/* Navigation */}
      <div className="flex justify-between mt-6">
        <Button variant="ghost" onClick={() => navigate("/configure")} className="gap-1.5">
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>
        <Button onClick={handleApprove} disabled={submitting} size="lg" className="gap-2">
          {submitting ? "Starting..." : "Approve & Generate PVMAP"}
          {!submitting && <Play className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
