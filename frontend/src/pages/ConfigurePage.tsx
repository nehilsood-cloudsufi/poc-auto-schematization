/**
 * Wizard Step 2: Configure pipeline settings before running.
 */
import { useNavigate } from "react-router-dom";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Slider } from "@/components/ui/slider";
import { Switch } from "@/components/ui/switch";
import { Textarea } from "@/components/ui/textarea";
import { WizardStepper } from "@/components/WizardStepper";
import { startRun } from "@/lib/api";
import type { PipelineConfig } from "@/types";

interface ConfigurePageProps {
  runId: string;
  datasetName: string;
  config: PipelineConfig;
  onConfigChange: (config: PipelineConfig) => void;
  onRunStarted: () => void;
}

export function ConfigurePage({
  runId,
  datasetName,
  config,
  onConfigChange,
  onRunStarted,
}: ConfigurePageProps) {
  const navigate = useNavigate();

  const handleStart = async () => {
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
      navigate(`/runs/${runId}`);
    } catch (err) {
      console.error("Failed to start run:", err);
    }
  };

  return (
    <div className="p-8 max-w-2xl mx-auto">
      <WizardStepper currentStep={1} />

      <h1 className="text-2xl font-bold mb-6">Configure Pipeline</h1>
      <p className="text-muted-foreground mb-6">
        Dataset: <span className="font-mono font-medium">{datasetName}</span>
      </p>

      <div className="space-y-6">
        {/* Max Retries */}
        <div>
          <Label className="mb-2 block">Max Retries: {config.max_retries}</Label>
          <Slider
            value={[config.max_retries]}
            onValueChange={(v) => {
              const arr = v as number[];
              if (arr.length > 0) {
                onConfigChange({ ...config, max_retries: arr[0] });
              }
            }}
            min={0}
            max={10}
            step={1}
          />
        </div>

        {/* Toggles */}
        <div className="flex gap-8">
          <div className="flex items-center gap-2">
            <Switch
              checked={config.enable_mcp}
              onCheckedChange={(v) => onConfigChange({ ...config, enable_mcp: v })}
            />
            <Label>MCP Discovery</Label>
          </div>
          <div className="flex items-center gap-2">
            <Switch
              checked={config.use_schema_examples}
              onCheckedChange={(v) => onConfigChange({ ...config, use_schema_examples: v })}
            />
            <Label>Schema Examples</Label>
          </div>
        </div>

        {/* Model */}
        <div>
          <Label className="mb-2 block">Model</Label>
          <Input
            value={config.model}
            onChange={(e) => onConfigChange({ ...config, model: e.target.value })}
          />
        </div>

        {/* Human Feedback */}
        <div>
          <Label className="mb-2 block">Initial Feedback (optional)</Label>
          <Textarea
            value={config.human_feedback || ""}
            onChange={(e) =>
              onConfigChange({ ...config, human_feedback: e.target.value || null })
            }
            placeholder="Pre-seed the pipeline with guidance..."
            rows={3}
          />
        </div>
      </div>

      {/* Actions */}
      <div className="flex justify-between mt-8">
        <Button variant="outline" onClick={() => navigate("/")}>
          Back
        </Button>
        <Button onClick={handleStart} size="lg">
          Generate PVMAP
        </Button>
      </div>
    </div>
  );
}
