/**
 * Root application component with routing and shared state.
 *
 * App-level state lifted here:
 * - currentRunId — set on upload, used by all pages
 * - datasetName — set on upload
 * - config — PipelineConfig, modified by ConfigurePage
 * - status — tracks wizard progress
 * - result — pipeline result from WebSocket terminal event
 * - startTime — for elapsed time tracking
 */
import { useState, useCallback } from "react";
import { BrowserRouter, Routes, Route, useNavigate } from "react-router-dom";
import { Sidebar } from "@/components/Sidebar";
import { UploadPage } from "@/pages/UploadPage";
import { ConfigurePage } from "@/pages/ConfigurePage";
import { ProgressPage } from "@/pages/ProgressPage";
import { ResultsPage } from "@/pages/ResultsPage";
import { ReviewPlanPage } from "@/pages/ReviewPlanPage";
import { HistoryPage } from "@/pages/HistoryPage";
import type { UploadResponse, PipelineConfig, PipelineResult, ProgressEvent } from "@/types";
import { Toaster } from "sonner";

const DEFAULT_CONFIG: PipelineConfig = {
  dataset_name: "",
  model: "gemini-3.1-pro-preview",
  max_retries: 1,
  enable_mcp: false,
  use_schema_examples: true,
  human_feedback: null,
};

function AppLayout() {
  const navigate = useNavigate();
  const [currentRunId, setCurrentRunId] = useState<string | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [config, setConfig] = useState<PipelineConfig>(DEFAULT_CONFIG);
  const [status, setStatus] = useState("pending");
  const [result, setResult] = useState<PipelineResult | undefined>(undefined);
  const [startTime, setStartTime] = useState(Date.now());

  const handleUploadComplete = useCallback((response: UploadResponse) => {
    setCurrentRunId(response.run_id);
    setDatasetName(response.dataset_name);
    setConfig((prev) => ({ ...prev, dataset_name: response.dataset_name }));
    setStatus("uploaded");
  }, []);

  const handleRunStarted = useCallback(() => {
    setStatus("running");
    setStartTime(Date.now());
    setResult(undefined);
  }, []);

  const handleComplete = useCallback((event: ProgressEvent) => {
    if (event.result?.phase === "plan") {
      setStatus("plan_ready");
    } else {
      setStatus("complete");
    }
    if (event.result) setResult(event.result);
  }, []);

  const handleError = useCallback((event: ProgressEvent) => {
    setStatus("error");
    if (event.result) setResult(event.result);
  }, []);

  const handleNewRun = useCallback(() => {
    setCurrentRunId(null);
    setDatasetName("");
    setConfig(DEFAULT_CONFIG);
    setStatus("pending");
    setResult(undefined);
    navigate("/");
  }, [navigate]);

  const handleRerunStarted = useCallback((newRunId: string) => {
    setCurrentRunId(newRunId);
    setStatus("running");
    setStartTime(Date.now());
    setResult(undefined);
    navigate(`/runs/${newRunId}`);
  }, [navigate]);

  return (
    <div className="flex h-screen bg-background text-foreground">
      <Sidebar
        currentRunId={currentRunId}
        status={status}
        onNewRun={handleNewRun}
      />
      <main className="flex-1 overflow-auto">
        <Routes>
          <Route
            path="/"
            element={<UploadPage onUploadComplete={handleUploadComplete} />}
          />
          <Route
            path="/configure"
            element={
              <ConfigurePage
                runId={currentRunId ?? ""}
                datasetName={datasetName}
                config={config}
                onConfigChange={setConfig}
                onRunStarted={handleRunStarted}
              />
            }
          />
          <Route
            path="/runs/:runId/plan"
            element={
              <ReviewPlanPage
                datasetName={datasetName}
                startTime={startTime}
                onGenerateStarted={handleRunStarted}
                onError={handleError}
              />
            }
          />
          <Route
            path="/runs/:runId"
            element={
              <ProgressPage
                startTime={startTime}
                onComplete={handleComplete}
                onError={handleError}
              />
            }
          />
          <Route
            path="/runs/:runId/results"
            element={
              <ResultsPage
                datasetName={datasetName}
                result={result}
                onRerunStarted={handleRerunStarted}
              />
            }
          />
          <Route path="/history" element={<HistoryPage />} />
        </Routes>
      </main>
    </div>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <AppLayout />
      <Toaster position="bottom-right" richColors closeButton />
    </BrowserRouter>
  );
}
