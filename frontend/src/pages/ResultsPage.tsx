/**
 * Wizard Step 5: View results, edit PVMAP, provide feedback.
 *
 * Two-panel layout:
 *   1. Input Files panel (PVMAP + Metadata tabs with SpreadsheetEditor)
 *   2. Output Files panel (read-only OutputViewer)
 * Plus: editable run name/notes, status banner, save & revalidate, delete.
 */
import { useEffect, useState, useCallback, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { WizardStepper } from "@/components/WizardStepper";
import { OutputViewer, ResultBanner } from "@/components/OutputViewer";
import { FeedbackForm } from "@/components/FeedbackForm";
import { DownloadButton } from "@/components/DownloadButton";
import { SpreadsheetEditor } from "@/components/SpreadsheetEditor";
import { ConfirmDeleteModal } from "@/components/ConfirmDeleteModal";
import { DevFeedbackForm } from "@/components/DevFeedbackForm";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { getRun, resumeRun, getFile, updateFile, revalidate, updateRun, deleteRun } from "@/lib/api";
import { toast } from "sonner";
import { Play, Pause, Loader2, Pencil, Trash2, AlertTriangle } from "lucide-react";
import type { PipelineResult, CsvFileResponse } from "@/types";

interface ResultsPageProps {
  datasetName: string;
  result?: PipelineResult;
  onRerunStarted: (newRunId: string) => void;
}

export function ResultsPage({ datasetName: propDatasetName, result: propResult, onRerunStarted }: ResultsPageProps) {
  const { runId } = useParams<{ runId: string }>();
  const navigate = useNavigate();
  const [datasetName, setDatasetName] = useState(propDatasetName);
  const [result, setResult] = useState<PipelineResult | undefined>(propResult);
  const [loading, setLoading] = useState(false);
  const [runStatus, setRunStatus] = useState<string>("");
  const [resuming, setResuming] = useState(false);

  // Run metadata editing
  const [displayName, setDisplayName] = useState("");
  const [notes, setNotes] = useState("");
  const [editingName, setEditingName] = useState(false);

  // Delete modal
  const [showDeleteModal, setShowDeleteModal] = useState(false);

  // Input files (PVMAP + Metadata)
  const [activeInputTab, setActiveInputTab] = useState<"pvmap" | "metadata">("pvmap");
  const [pvmapData, setPvmapData] = useState<{ columns: string[]; rows: Record<string, string>[] } | null>(null);
  const [metadataData, setMetadataData] = useState<{ columns: string[]; rows: Record<string, string>[] } | null>(null);
  const [inputDirty, setInputDirty] = useState(false);
  const [revalidating, setRevalidating] = useState(false);
  const [stale, setStale] = useState(false);

  // Edited state refs
  const editedPvmap = useRef<{ rows: Record<string, string>[]; columns: string[] } | null>(null);
  const editedMetadata = useRef<{ rows: Record<string, string>[]; columns: string[] } | null>(null);

  // Sync from props when they change (e.g., after a fresh pipeline run)
  useEffect(() => {
    if (propDatasetName) setDatasetName(propDatasetName);
    if (propResult) setResult(propResult);
  }, [propDatasetName, propResult]);

  // Fetch run data + input files when runId changes
  useEffect(() => {
    if (!runId) return;
    // Reset state so stale data from previous run doesn't linger
    setResult(undefined);
    setDatasetName("");
    setRunStatus("");
    setPvmapData(null);
    setMetadataData(null);
    setInputDirty(false);
    setStale(false);
    editedPvmap.current = null;
    editedMetadata.current = null;
    setLoading(true);

    getRun(runId)
      .then((run) => {
        setRunStatus(run.status);
        setDatasetName(run.dataset_name ?? "");
        setDisplayName(run.display_name || run.dataset_name || "");
        setNotes(run.notes || "");
        if (run.result && Object.keys(run.result).length > 0) {
          setResult(run.result as PipelineResult);
        }
      })
      .catch(() => {})
      .finally(() => setLoading(false));

    // Load input files
    getFile(runId, "generated_pvmap.csv")
      .then((resp) => {
        if (resp.type === "csv") {
          const csvResp = resp as CsvFileResponse;
          setPvmapData({ columns: csvResp.columns, rows: csvResp.rows as Record<string, string>[] });
        }
      })
      .catch(() => {});

    getFile(runId, "output_metadata.csv")
      .then((resp) => {
        if (resp.type === "csv") {
          const csvResp = resp as CsvFileResponse;
          setMetadataData({ columns: csvResp.columns, rows: csvResp.rows as Record<string, string>[] });
        }
      })
      .catch(() => {});
  }, [runId]);

  const handleResume = async () => {
    if (!runId || resuming) return;
    setResuming(true);
    try {
      await resumeRun(runId);
      toast.info("Resuming pipeline...");
      onRerunStarted(runId);
    } catch (err) {
      toast.error(err instanceof Error ? err.message : "Failed to resume");
      setResuming(false);
    }
  };

  const handleNameBlur = useCallback(async () => {
    setEditingName(false);
    if (runId) {
      try {
        await updateRun(runId, { display_name: displayName });
      } catch {
        /* ignore */
      }
    }
  }, [runId, displayName]);

  const handleNotesBlur = useCallback(async () => {
    if (runId) {
      try {
        await updateRun(runId, { notes });
      } catch {
        /* ignore */
      }
    }
  }, [runId, notes]);

  const handleDelete = useCallback(async () => {
    if (!runId) return;
    try {
      await deleteRun(runId);
      toast.success("Run deleted");
      navigate("/history");
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Delete failed");
    }
  }, [runId, navigate]);

  const handleSaveAndRevalidate = useCallback(async () => {
    if (!runId) return;
    setRevalidating(true);
    try {
      const saves: Promise<unknown>[] = [];
      if (editedPvmap.current) {
        saves.push(updateFile(runId, "generated_pvmap.csv", { rows: editedPvmap.current.rows }));
      }
      if (editedMetadata.current) {
        saves.push(updateFile(runId, "output_metadata.csv", { rows: editedMetadata.current.rows }));
      }
      await Promise.all(saves);

      const res = await revalidate(runId);
      if (res.success) {
        toast.success(`Validation passed: ${res.data_rows} data rows`);
      } else {
        toast.error(`Validation failed: ${res.error}`);
      }
      setStale(false);
      setInputDirty(false);

      // Reload run data to get updated result
      const updatedRun = await getRun(runId);
      if (updatedRun.result && Object.keys(updatedRun.result).length > 0) {
        setResult(updatedRun.result as PipelineResult);
      }

      // Reload input files for fresh baseline
      const pvResp = await getFile(runId, "generated_pvmap.csv");
      if (pvResp.type === "csv") {
        const csv = pvResp as CsvFileResponse;
        setPvmapData({ columns: csv.columns, rows: csv.rows as Record<string, string>[] });
      }
      const mdResp = await getFile(runId, "output_metadata.csv").catch(() => null);
      if (mdResp?.type === "csv") {
        const csv = mdResp as CsvFileResponse;
        setMetadataData({ columns: csv.columns, rows: csv.rows as Record<string, string>[] });
      }
      editedPvmap.current = null;
      editedMetadata.current = null;
    } catch (err: unknown) {
      toast.error(err instanceof Error ? err.message : "Revalidation failed");
    } finally {
      setRevalidating(false);
    }
  }, [runId]);

  if (!runId) return null;

  return (
    <div className="min-h-screen bg-muted/20 p-8">
      <div className="max-w-6xl mx-auto">
        <WizardStepper
          currentStep={4}
          onStepClick={(step) => {
            if (!runId) return;
            if (step === 2) navigate(`/runs/${runId}/plan`);
            // Steps 0,1,3 don't have useful pages for completed runs
          }}
        />

        {/* HEADER with editable name, notes, download, delete */}
        <div className="flex items-start justify-between mt-6 mb-5">
          <div className="flex-1">
            {loading ? (
              <div className="flex items-center gap-2">
                <Loader2 className="w-5 h-5 animate-spin text-muted-foreground" />
                <span className="text-lg text-muted-foreground">Loading results...</span>
              </div>
            ) : (
              <>
                {/* Editable display name */}
                <div className="flex items-center gap-2 mb-1">
                  {editingName ? (
                    <Input
                      value={displayName}
                      onChange={(e) => setDisplayName(e.target.value)}
                      onBlur={handleNameBlur}
                      onKeyDown={(e) => { if (e.key === "Enter") handleNameBlur(); }}
                      autoFocus
                      className="text-2xl font-bold h-auto py-0.5 max-w-md"
                    />
                  ) : (
                    <h1
                      className="text-2xl font-bold cursor-pointer hover:text-muted-foreground transition-colors group flex items-center gap-2"
                      onClick={() => setEditingName(true)}
                    >
                      {displayName || datasetName || "Untitled Run"}
                      <Pencil className="h-4 w-4 opacity-0 group-hover:opacity-50 transition-opacity" />
                    </h1>
                  )}
                </div>

                {/* Notes */}
                <Textarea
                  placeholder="Add notes..."
                  value={notes}
                  onChange={(e) => setNotes(e.target.value)}
                  onBlur={handleNotesBlur}
                  className="text-sm resize-none mt-1 max-w-lg"
                  rows={2}
                />

                {/* Run ID */}
                <p className="text-sm text-muted-foreground mt-1">
                  Run ID: <span className="font-mono">{runId.slice(0, 12)}</span>
                </p>
              </>
            )}
          </div>
          <div className="flex items-center gap-2 ml-4">
            <DownloadButton runId={runId} datasetName={datasetName} />
            <Button variant="destructive" size="sm" onClick={() => setShowDeleteModal(true)}>
              <Trash2 className="h-4 w-4 mr-1" /> Delete
            </Button>
          </div>
        </div>

        {/* Stopped card */}
        {runStatus === "stopped" && (
          <Card className="shadow-sm mb-6 border-amber-200 dark:border-amber-800">
            <CardContent className="pt-6 flex items-center justify-between">
              <div className="flex items-center gap-3">
                <Pause className="w-5 h-5 text-amber-500" />
                <div>
                  <p className="font-medium">Run was stopped</p>
                  <p className="text-sm text-muted-foreground">
                    Partial results shown below. Resume to continue from the last checkpoint.
                  </p>
                </div>
              </div>
              <Button onClick={handleResume} disabled={resuming} className="gap-2">
                {resuming ? (
                  <><Loader2 className="w-4 h-4 animate-spin" /> Resuming...</>
                ) : (
                  <><Play className="w-4 h-4" /> Resume Run</>
                )}
              </Button>
            </CardContent>
          </Card>
        )}

        {/* Status banner */}
        {result && <ResultBanner result={result} />}

        {/* INPUT FILES PANEL */}
        <Card className="shadow-sm mb-4">
          <CardContent className="pt-6">
            <h2 className="text-lg font-semibold mb-3">Input Files</h2>
            <div className="flex gap-2 mb-3">
              <Button
                variant={activeInputTab === "pvmap" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveInputTab("pvmap")}
              >
                PVMAP
              </Button>
              <Button
                variant={activeInputTab === "metadata" ? "default" : "outline"}
                size="sm"
                onClick={() => setActiveInputTab("metadata")}
                disabled={!metadataData}
              >
                Metadata
              </Button>
            </div>
            {activeInputTab === "pvmap" && pvmapData && (
              <SpreadsheetEditor
                columns={pvmapData.columns}
                rows={pvmapData.rows}
                onChange={(rows, columns) => {
                  editedPvmap.current = { rows, columns };
                  setStale(true);
                }}
                onDirty={setInputDirty}
              />
            )}
            {activeInputTab === "metadata" && metadataData && (
              <SpreadsheetEditor
                columns={metadataData.columns}
                rows={metadataData.rows}
                onChange={(rows, columns) => {
                  editedMetadata.current = { rows, columns };
                  setStale(true);
                }}
                onDirty={(dirty) => setInputDirty(dirty)}
              />
            )}
            {activeInputTab === "pvmap" && !pvmapData && !loading && (
              <p className="text-gray-500 text-sm py-8">No PVMAP file available yet.</p>
            )}
          </CardContent>
        </Card>

        {/* ACTION BAR */}
        <div className="flex items-center gap-3 mb-4">
          <Button onClick={handleSaveAndRevalidate} disabled={!inputDirty || revalidating}>
            {revalidating ? (
              <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Running stat_var_processor...</>
            ) : (
              "Save & Revalidate"
            )}
          </Button>
          {stale && !revalidating && (
            <div className="flex items-center gap-2 text-amber-600 text-sm">
              <AlertTriangle className="h-4 w-4" /> Output files may be outdated. Save & Revalidate to refresh.
            </div>
          )}
        </div>

        {/* OUTPUT FILES PANEL */}
        <Card className="shadow-sm mb-6">
          <CardContent className="pt-6">
            <h2 className="text-lg font-semibold mb-3">Output Files</h2>
            <OutputViewer runId={runId} key={revalidating ? "revalidating" : "ready"} />
          </CardContent>
        </Card>

        <Separator className="my-6" />

        {/* FEEDBACK */}
        <Card className="shadow-sm">
          <CardContent className="pt-6">
            <FeedbackForm runId={runId} onRerunStarted={onRerunStarted} />
          </CardContent>
        </Card>

        {/* DEVELOPER FEEDBACK */}
        <Card className="shadow-sm mt-4">
          <CardContent className="pt-6">
            <DevFeedbackForm runId={runId} />
          </CardContent>
        </Card>

        {/* DELETE MODAL */}
        {showDeleteModal && (
          <ConfirmDeleteModal
            datasetName={displayName || datasetName}
            onConfirm={handleDelete}
            onCancel={() => setShowDeleteModal(false)}
          />
        )}
      </div>
    </div>
  );
}
