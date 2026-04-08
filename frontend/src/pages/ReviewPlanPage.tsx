/**
 * Wizard Step 3: Review and edit the mapping plan.
 */
import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent } from "@/components/ui/card";
import { WizardStepper } from "@/components/WizardStepper";
import { ProgressTracker } from "@/components/ProgressTracker";
import { useWebSocket } from "@/hooks/useWebSocket";
import { getFile, generatePvmap, stopRun } from "@/lib/api";
import { toast } from "sonner";
import { PLAN_PHASES } from "@/types";
import {
  ChevronLeft,
  Play,
  Square,
  Pencil,
  Eye,
  CheckCircle2,
} from "lucide-react";
import DOMPurify from "dompurify";

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

  const [plan, setPlan] = useState("");
  const [planReady, setPlanReady] = useState(false);
  const [loadingPlan, setLoadingPlan] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [stopping, setStopping] = useState(false);
  const [isEditing, setIsEditing] = useState(false);

  const { events } = useWebSocket({
    runId: runId ?? null,
    enabled: !planReady,
    onComplete: (event) => {
      if (event.result?.phase === "plan") {
        setPlanReady(true);
        toast.info("Plan ready for review");
      } else {
        navigate(`/runs/${runId}/results`);
      }
    },
    onError,
  });

  useEffect(() => {
    if (!planReady || !runId) return;
    setLoadingPlan(true);
    getFile(runId, "mapping_plan.md")
      .then((file) => {
        if (file.type === "text") setPlan(file.content);
      })
      .catch(() => toast.error("Failed to load plan"))
      .finally(() => setLoadingPlan(false));
  }, [planReady, runId]);

  useEffect(() => {
    if (!runId) return;
    getFile(runId, "mapping_plan.md")
      .then((file) => {
        if (file.type === "text" && file.content) {
          setPlan(file.content);
          setPlanReady(true);
        }
      })
      .catch(() => {});
  }, [runId]);

  const handleApprove = async () => {
    if (!runId) return;
    setSubmitting(true);
    try {
      await generatePvmap(runId, plan);
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

  const renderMarkdown = (text: string): string => {
    let html = text
      .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
      .replace(/^### (.+)$/gm, "<h3>$1</h3>")
      .replace(/^## (.+)$/gm, "<h2>$1</h2>")
      .replace(/^# (.+)$/gm, "<h1>$1</h1>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/`(.+?)`/g, "<code>$1</code>")
      .replace(/^- (.+)$/gm, "<li>$1</li>")
      .replace(/\n\n/g, "</p><p>")
      .replace(/\n/g, "<br>");
    html = `<p>${html}</p>`;
    return DOMPurify.sanitize(html);
  };

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
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${50 + Math.random() * 50}%` }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (loadingPlan) {
    return (
      <div className="p-8 max-w-4xl mx-auto">
        <WizardStepper currentStep={2} />
        <Card className="shadow-sm mt-6">
          <CardContent className="pt-6">
            <div className="space-y-3">
              {Array.from({ length: 12 }).map((_, i) => (
                <div key={i} className="h-3.5 bg-muted animate-pulse rounded" style={{ width: `${40 + Math.random() * 60}%` }} />
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="p-8 max-w-4xl mx-auto">
      <WizardStepper currentStep={2} />

      <div className="flex items-center justify-between mb-1">
        <h1 className="text-2xl font-bold">Review Mapping Plan</h1>
        <div className="flex items-center gap-2">
          <CheckCircle2 className="w-4 h-4 text-green-500" />
          <span className="text-sm text-green-600 dark:text-green-400 font-medium">Plan Ready</span>
        </div>
      </div>
      <p className="text-muted-foreground mb-4">
        Dataset: <span className="font-mono font-medium">{datasetName}</span>
      </p>

      <Card className="shadow-sm">
        <div className="px-4 py-2 border-b flex items-center justify-between bg-muted/30">
          <span className="text-sm font-medium">Mapping Plan</span>
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setIsEditing(!isEditing)}
            className="gap-1.5 text-xs"
          >
            {isEditing ? (
              <><Eye className="w-3.5 h-3.5" /> Preview</>
            ) : (
              <><Pencil className="w-3.5 h-3.5" /> Edit</>
            )}
          </Button>
        </div>
        <CardContent className="pt-4">
          {isEditing ? (
            <Textarea
              value={plan}
              onChange={(e) => setPlan(e.target.value)}
              className="font-mono text-sm min-h-[500px]"
              rows={30}
            />
          ) : (
            <div
              className="prose dark:prose-invert max-w-none text-sm min-h-[200px]"
              dangerouslySetInnerHTML={{ __html: renderMarkdown(plan) }}
            />
          )}
        </CardContent>
      </Card>

      <div className="flex justify-between mt-6">
        <Button variant="ghost" onClick={() => navigate("/configure")} className="gap-1.5">
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>
        <Button onClick={handleApprove} disabled={submitting || !plan} size="lg" className="gap-2">
          {submitting ? "Starting..." : "Approve & Generate PVMAP"}
          {!submitting && <Play className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
