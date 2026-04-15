/**
 * Wizard Step 2: Configure pipeline settings before running.
 */
import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "@/components/ui/select";
import { WizardStepper } from "@/components/WizardStepper";
import { DataExplorer } from "@/components/DataExplorer";
import { startRun } from "@/lib/api";
import { toast } from "sonner";
import { ChevronLeft, Play, ChevronDown, ChevronUp, Settings, Cpu, MessageSquare } from "lucide-react";
import type { PipelineConfig } from "@/types";

const GEMINI_MODELS = [
  { value: "gemini-3.1-pro-preview", label: "Gemini 3.1 Pro" },
  { value: "gemini-3.0-flash", label: "Gemini 3.0 Flash" },
  { value: "gemini-2.5-pro", label: "Gemini 2.5 Pro" },
  { value: "gemini-2.5-flash", label: "Gemini 2.5 Flash" },
  { value: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
  { value: "gemini-2.0-flash-lite", label: "Gemini 2.0 Flash Lite" },
] as const;

interface ConfigurePageProps {
  runId: string;
  datasetName: string;
  config: PipelineConfig;
  onConfigChange: (config: PipelineConfig) => void;
  onRunStarted: () => void;
}

export function ConfigurePage({
  runId, datasetName, config, onConfigChange, onRunStarted,
}: ConfigurePageProps) {
  const navigate = useNavigate();
  const [showFeedback, setShowFeedback] = useState(false);
  const [starting, setStarting] = useState(false);

  const handleStart = async () => {
    setStarting(true);
    try {
      await startRun({
        run_id: runId,
        dataset_name: datasetName,
        model: config.model,
        max_retries: config.max_retries,
        enable_mcp: config.enable_mcp,
        use_schema_examples: config.use_schema_examples,
        human_feedback: config.human_feedback,
      });
      onRunStarted();
      navigate(`/runs/${runId}/plan`);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to start run");
    } finally {
      setStarting(false);
    }
  };

  return (
    <div className="p-8 max-w-3xl mx-auto">
      <WizardStepper currentStep={1} />

      <h1 className="text-2xl font-bold mb-1">Configure Pipeline</h1>
      <p className="text-muted-foreground mb-6">
        Dataset: <span className="font-mono font-medium">{datasetName}</span>
      </p>

      <div className="space-y-4">
        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Cpu className="w-4 h-4 text-muted-foreground" /> Model & Retries
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div>
              <Label className="mb-2 block text-sm">Model</Label>
              <Select
                value={config.model}
                onValueChange={(v) => onConfigChange({ ...config, model: v as string })}
              >
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {GEMINI_MODELS.map((m) => (
                    <SelectItem key={m.value} value={m.value}>{m.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div>
              <Label className="mb-2 block text-sm">Max Retries: {config.max_retries}</Label>
              <Slider
                value={[config.max_retries]}
                onValueChange={(v) => {
                  const arr = v as number[];
                  if (arr.length > 0) onConfigChange({ ...config, max_retries: arr[0] });
                }}
                min={0}
                max={10}
                step={1}
              />
              <p className="text-xs text-muted-foreground mt-1">
                How many StatVar Processing-feedback-retry cycles to run
              </p>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <CardHeader className="pb-3">
            <CardTitle className="text-base flex items-center gap-2">
              <Settings className="w-4 h-4 text-muted-foreground" /> Options
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm">MCP Discovery</Label>
                  <p className="text-xs text-muted-foreground">Use Model Context Protocol for enhanced mapping</p>
                </div>
                <Switch
                  checked={config.enable_mcp}
                  onCheckedChange={(v) => onConfigChange({ ...config, enable_mcp: v })}
                />
              </div>
              <div className="flex items-center justify-between">
                <div>
                  <Label className="text-sm">Schema Examples</Label>
                  <p className="text-xs text-muted-foreground">Include schema vocabulary in the generation prompt</p>
                </div>
                <Switch
                  checked={config.use_schema_examples}
                  onCheckedChange={(v) => onConfigChange({ ...config, use_schema_examples: v })}
                />
              </div>
            </div>
          </CardContent>
        </Card>

        <Card className="shadow-sm">
          <button
            type="button"
            onClick={() => setShowFeedback(!showFeedback)}
            className="w-full px-6 py-4 flex items-center justify-between cursor-pointer hover:bg-muted/30 transition-colors rounded-lg"
          >
            <div className="flex items-center gap-2">
              <MessageSquare className="w-4 h-4 text-muted-foreground" />
              <span className="text-sm font-medium">Initial Feedback</span>
              <span className="text-xs text-muted-foreground">(optional)</span>
            </div>
            {showFeedback ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
          </button>
          {showFeedback && (
            <CardContent className="pt-0 pb-4">
              <Textarea
                value={config.human_feedback || ""}
                onChange={(e) =>
                  onConfigChange({ ...config, human_feedback: e.target.value || null })
                }
                placeholder="e.g., 'The date column uses YYYY-MM format' or 'Ignore the footnote rows at the bottom'"
                rows={3}
              />
              <p className="text-xs text-muted-foreground mt-1.5">
                Give the pipeline hints about your data to improve initial results
              </p>
            </CardContent>
          )}
        </Card>
      </div>

      <div className="mt-4">
        <DataExplorer runId={runId} />
      </div>

      <div className="mt-6 p-3 rounded-md bg-muted/50 text-xs text-muted-foreground flex items-center justify-between">
        <span className="font-mono">
          {datasetName} · {config.model.replace("gemini-", "").replace("-preview", "")} · {config.max_retries} retries
        </span>
      </div>
      <div className="flex justify-between mt-4">
        <Button variant="ghost" onClick={() => navigate("/")} className="gap-1.5">
          <ChevronLeft className="w-4 h-4" /> Back
        </Button>
        <Button onClick={handleStart} size="lg" disabled={starting} className="gap-2">
          {starting ? "Starting..." : "Generate Plan"}
          {!starting && <Play className="w-4 h-4" />}
        </Button>
      </div>
    </div>
  );
}
