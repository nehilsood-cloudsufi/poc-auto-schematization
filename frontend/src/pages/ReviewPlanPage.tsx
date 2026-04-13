/**
 * Wizard Step 3: Review and edit the structured mapping plan.
 *
 * Replaces the old markdown-dump view with an interactive form:
 * - Dataset Understanding (read-only summary)
 * - ActiveMappingsTable (expandable rows with selectable candidates)
 * - StaticProperties (radio buttons for global props)
 * - IgnoredColumns (collapsed list)
 * - Global notes / warnings
 * - Approve button that sends the edited plan to the backend
 */
import { useEffect, useMemo, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { ActiveMappingsTable } from "@/components/PlanReview/ActiveMappingsTable";
import { StaticProperties } from "@/components/PlanReview/StaticProperties";
import { IgnoredColumns } from "@/components/PlanReview/IgnoredColumns";
import { PlanFeedback } from "@/components/PlanReview/PlanFeedback";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getPlan, approvePlan, generatePvmap, stopRun, regeneratePlan, addPlanNote, updatePlan } from "@/lib/api";
import { toast } from "sonner";
import { PLAN_PHASES } from "@/types";
import type { MappingPlan, ColumnMapping } from "@/types";
import {
  ChevronLeft,
  Play,
  Square,
  CheckCircle2,
  AlertTriangle,
  Info,
  Code2,
  Table2,
  Save,
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
  const [viewMode, setViewMode] = useState<"structured" | "json">("structured");
  const [jsonText, setJsonText] = useState("");
  const [jsonDirty, setJsonDirty] = useState(false);
  const [jsonError, setJsonError] = useState<string | null>(null);
  const [savingJson, setSavingJson] = useState(false);

  const skeletonWidths8 = useMemo(() => Array.from({ length: 8 }, () => `${50 + Math.random() * 50}%`), []);
  const skeletonWidths12 = useMemo(() => Array.from({ length: 12 }, () => `${40 + Math.random() * 60}%`), []);

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
    getPlan(runId)
      .then((data) => setPlan(data))
      .catch(() => toast.error("Failed to load plan"))
      .finally(() => setLoadingPlan(false));
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
      .catch(() => {});
  }, [runId]);

  // --- Sync JSON text when plan loads or changes from structured edits ---
  useEffect(() => {
    if (plan && !jsonDirty) {
      setJsonText(JSON.stringify(plan, null, 2));
      setJsonError(null);
    }
  }, [plan, jsonDirty]);

  // --- Handlers ---

  const handleJsonChange = (value: string) => {
    setJsonText(value);
    setJsonDirty(true);
    // Validate JSON on each change
    try {
      JSON.parse(value);
      setJsonError(null);
    } catch (e) {
      setJsonError(e instanceof Error ? e.message : "Invalid JSON");
    }
  };

  const handleSaveJson = async () => {
    if (!runId || jsonError) return;
    setSavingJson(true);
    try {
      const parsed = JSON.parse(jsonText);
      await updatePlan(runId, parsed);
      setPlan(parsed as MappingPlan);
      setJsonDirty(false);
      toast.success("Plan saved");
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to save plan");
    } finally {
      setSavingJson(false);
    }
  };

  const handleColumnUpdate = (columnName: string, updates: Partial<ColumnMapping>) => {
    setPlan(prev => prev ? {
      ...prev,
      active_columns: prev.active_columns.map(col =>
        col.column_name === columnName ? { ...col, ...updates } : col
      ),
    } : prev);
  };

  const handleStaticUpdate = (propName: string, selectedIndex: number) => {
    setPlan(prev => prev ? {
      ...prev,
      static_properties: prev.static_properties.map(sp =>
        sp.property_name === propName ? { ...sp, selected_index: selectedIndex } : sp
      ),
    } : prev);
  };

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
              {skeletonWidths8.map((w, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: w }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // --- Render: loading plan data ---
  if (loadingPlan || !plan) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <WizardStepper currentStep={2} />
        <Card className="shadow-sm mt-6">
          <CardContent className="pt-6">
            <div className="space-y-3">
              {skeletonWidths12.map((w, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: w }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // --- Count ambiguous columns for the header badge ---
  const ambiguousCount = plan.active_columns.filter(c => c.is_ambiguous).length;

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

      {/* View mode toggle */}
      <div className="flex items-center gap-1 mb-4 border rounded-md p-0.5 w-fit bg-muted/50">
        <button
          onClick={() => {
            if (viewMode === "json" && jsonDirty) {
              // Sync JSON edits back to structured view
              try {
                const parsed = JSON.parse(jsonText);
                setPlan(parsed as MappingPlan);
                setJsonDirty(false);
              } catch {
                toast.error("Fix JSON errors before switching to structured view");
                return;
              }
            }
            setViewMode("structured");
          }}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded transition-colors ${
            viewMode === "structured"
              ? "bg-background shadow-sm font-medium"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Table2 className="w-3.5 h-3.5" />
          Structured
        </button>
        <button
          onClick={() => {
            // Sync current plan state to JSON when switching
            if (plan) {
              setJsonText(JSON.stringify(plan, null, 2));
              setJsonDirty(false);
              setJsonError(null);
            }
            setViewMode("json");
          }}
          className={`flex items-center gap-1.5 px-3 py-1.5 text-sm rounded transition-colors ${
            viewMode === "json"
              ? "bg-background shadow-sm font-medium"
              : "text-muted-foreground hover:text-foreground"
          }`}
        >
          <Code2 className="w-3.5 h-3.5" />
          JSON Editor
        </button>
      </div>

      {viewMode === "json" ? (
        <>
          {/* JSON Editor View */}
          <Card className="shadow-sm mb-4">
            <CardContent className="pt-5 pb-4">
              <div className="flex items-center justify-between mb-2">
                <h2 className="text-sm font-semibold">Plan JSON</h2>
                <div className="flex items-center gap-2">
                  {jsonDirty && (
                    <span className="text-xs text-amber-600 dark:text-amber-400">Unsaved changes</span>
                  )}
                  {jsonError && (
                    <span className="text-xs text-destructive">{jsonError}</span>
                  )}
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={handleSaveJson}
                    disabled={savingJson || !!jsonError || !jsonDirty}
                    className="gap-1.5"
                  >
                    <Save className="w-3.5 h-3.5" />
                    {savingJson ? "Saving..." : "Save Edits"}
                  </Button>
                </div>
              </div>
              <textarea
                value={jsonText}
                onChange={(e) => handleJsonChange(e.target.value)}
                className={`w-full font-mono text-xs leading-relaxed p-3 rounded-md border bg-muted/30 resize-vertical focus:outline-none focus:ring-2 focus:ring-ring ${
                  jsonError ? "border-destructive focus:ring-destructive" : ""
                }`}
                style={{ minHeight: "400px", height: "60vh", maxHeight: "80vh" }}
                spellCheck={false}
              />
            </CardContent>
          </Card>
        </>
      ) : (
        <>
          {/* Structured View (existing sections) */}

          {/* Section 1: Dataset Understanding (read-only) */}
          <Card className="shadow-sm mb-4">
            <CardContent className="pt-5 pb-4">
              <h2 className="text-sm font-semibold mb-3">Dataset Understanding</h2>
              <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-2 text-sm">
                <dt className="text-muted-foreground">Archetype</dt>
                <dd className="font-medium">{plan.understanding.archetype}</dd>
                <dt className="text-muted-foreground">Observation Grain</dt>
                <dd>{plan.understanding.observation_grain}</dd>
                <dt className="text-muted-foreground">Key Insight</dt>
                <dd>{plan.understanding.key_insight}</dd>
              </dl>
            </CardContent>
          </Card>

          {/* Section 2: Active Column Mappings */}
          <div className="mb-4">
            <div className="flex items-center gap-2 mb-2">
              <h2 className="text-sm font-semibold">Column Mappings</h2>
              <span className="text-xs text-muted-foreground">
                {plan.active_columns.length} columns
              </span>
              {ambiguousCount > 0 && (
                <span className="flex items-center gap-1 text-xs px-1.5 py-0.5 rounded bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400">
                  <AlertTriangle className="w-3 h-3" />
                  {ambiguousCount} ambiguous
                </span>
              )}
            </div>
            <ActiveMappingsTable
              columns={plan.active_columns}
              onUpdate={handleColumnUpdate}
            />
          </div>

          {/* Section 3: Static Properties */}
          {plan.static_properties.length > 0 && (
            <Card className="shadow-sm mb-4">
              <CardContent className="pt-5 pb-4">
                <h2 className="text-sm font-semibold mb-3">Static Properties</h2>
                <StaticProperties
                  properties={plan.static_properties}
                  onUpdate={handleStaticUpdate}
                />
              </CardContent>
            </Card>
          )}

          {/* Section 4: Ignored Columns */}
          {plan.ignored_columns.length > 0 && (
            <div className="mb-4">
              <IgnoredColumns columns={plan.ignored_columns} />
            </div>
          )}

          {/* Section 5: Global Notes / Warnings */}
          {plan.global_notes.length > 0 && (
            <Card className="shadow-sm mb-4">
              <CardContent className="pt-5 pb-4">
                <h2 className="text-sm font-semibold mb-2">Notes</h2>
                <ul className="space-y-1.5">
                  {plan.global_notes.map((note, idx) => (
                    <li key={idx} className="flex items-start gap-2 text-sm text-muted-foreground">
                      <Info className="w-3.5 h-3.5 mt-0.5 flex-shrink-0" />
                      <span>{note}</span>
                    </li>
                  ))}
                </ul>
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* Feedback & Notes Input (visible in both views) */}
      <Card className="shadow-sm mb-4">
        <CardContent className="pt-5 pb-4">
          <h2 className="text-sm font-semibold mb-3">Feedback & Notes</h2>
          <PlanFeedback
            notes={plan.engineer_notes ?? []}
            onAddNote={handleAddNote}
            onRegenerate={handleRegenerate}
            regenerating={regenerating}
          />
        </CardContent>
      </Card>

      {/* Navigation buttons */}
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
