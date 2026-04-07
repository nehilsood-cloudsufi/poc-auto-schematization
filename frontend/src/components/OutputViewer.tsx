/**
 * Tabbed output file viewer. Renders CSVs in CsvEditor, text in CodeViewer.
 * Auto-loads the first tab's content on mount.
 */
import { useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { CsvEditor } from "./CsvEditor";
import { CodeViewer } from "./CodeViewer";
import { listFiles, getFile, updateFile, revalidate } from "@/lib/api";
import type { FileResponse, CsvFileResponse, TextFileResponse, PipelineResult } from "@/types";

const TAB_ORDER = [
  { key: "generated_pvmap.csv", label: "PVMAP" },
  { key: "output_metadata.csv", label: "Metadata Config" },
  { key: "processed.csv", label: "Processed Data" },
  { key: "processed.mcf", label: "MCF" },
  { key: "processed.tmcf", label: "TMCF" },
  { key: "processed_stat_vars.mcf", label: "StatVars" },
  { key: "generation_notes.md", label: "Notes" },
  { key: "processed_counters.txt", label: "Metrics" },
];

interface OutputViewerProps {
  runId: string;
  result?: PipelineResult;
}

function isCsvResponse(f: FileResponse): f is CsvFileResponse {
  return f.type === "csv";
}

function isTextResponse(f: FileResponse): f is TextFileResponse {
  return f.type === "text";
}

function tabLabel(tab: { key: string; label: string }, fileData: Record<string, FileResponse>): string {
  const fd = fileData[tab.key];
  if (!fd) return tab.label;
  if (isCsvResponse(fd)) {
    return `${tab.label} (${fd.row_count}r × ${fd.columns.length}c)`;
  }
  return tab.label;
}

export function OutputViewer({ runId, result }: OutputViewerProps) {
  const [availableFiles, setAvailableFiles] = useState<string[]>([]);
  const [fileData, setFileData] = useState<Record<string, FileResponse>>({});
  const [editedRows, setEditedRows] = useState<Record<string, unknown>[] | null>(null);
  const [revalidating, setRevalidating] = useState(false);
  const [activeTab, setActiveTab] = useState<string>("");

  useEffect(() => {
    listFiles(runId).then((resp) => {
      setAvailableFiles(resp.files);
    });
  }, [runId]);

  // Auto-load first available tab when file list arrives
  useEffect(() => {
    const tabs = TAB_ORDER.filter((t) => availableFiles.includes(t.key));
    if (tabs.length === 0) return;
    const firstKey = tabs[0].key;
    if (!fileData[firstKey]) {
      void loadFile(firstKey);
    }
    if (!activeTab) {
      setActiveTab(firstKey);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [availableFiles]);

  const loadFile = async (filename: string) => {
    if (fileData[filename]) return;
    const data = await getFile(runId, filename);
    setFileData((prev) => ({ ...prev, [filename]: data }));
  };

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    void loadFile(value);
  };

  const tabs = TAB_ORDER.filter((t) => availableFiles.includes(t.key));

  const handleSaveAndRevalidate = async () => {
    if (editedRows) {
      await updateFile(runId, "generated_pvmap.csv", { rows: editedRows });
    }
    setRevalidating(true);
    try {
      const res = await revalidate(runId);
      if (res.success) {
        alert(`Validation passed: ${res.data_rows} data rows`);
      } else {
        alert(`Validation failed: ${res.error}`);
      }
    } finally {
      setRevalidating(false);
    }
  };

  return (
    <div>
      {/* Result banner */}
      {result && (
        <div className={`mb-4 p-3 rounded-md text-sm border ${
          result.validation_passed
            ? "bg-green-50 text-green-800 border-green-200 dark:bg-green-950 dark:text-green-200 dark:border-green-800"
            : "bg-red-50 text-red-800 border-red-200 dark:bg-red-950 dark:text-red-200 dark:border-red-800"
        }`}>
          <strong>{(result.retry_count ?? 0) + 1} attempt(s)</strong> — {result.exit_reason}
          {result.quality_metrics?.heuristic_score != null && (
            <Badge variant="outline" className="ml-2">
              Score: {result.quality_metrics.heuristic_score.toFixed(1)}/100
            </Badge>
          )}
        </div>
      )}

      {tabs.length === 0 ? (
        <p className="text-sm text-muted-foreground py-4 text-center">No output files found.</p>
      ) : (
        <Tabs value={activeTab || tabs[0]?.key} onValueChange={handleTabChange}>
          <TabsList className="flex-wrap h-auto gap-1">
            {tabs.map((tab) => (
              <TabsTrigger key={tab.key} value={tab.key} className="text-xs">
                {tabLabel(tab, fileData)}
              </TabsTrigger>
            ))}
          </TabsList>

          {tabs.map((tab) => {
            const fd = fileData[tab.key];
            return (
              <TabsContent key={tab.key} value={tab.key}>
                {fd ? (
                  isCsvResponse(fd) ? (
                    <CsvEditor
                      columns={fd.columns}
                      rows={editedRows && tab.key === "generated_pvmap.csv" ? editedRows : fd.rows}
                      editable={tab.key === "generated_pvmap.csv"}
                      onChange={tab.key === "generated_pvmap.csv" ? setEditedRows : undefined}
                    />
                  ) : tab.key.endsWith(".md") && isTextResponse(fd) ? (
                    <div
                      className="prose dark:prose-invert max-w-none p-4"
                      dangerouslySetInnerHTML={{ __html: fd.content }}
                    />
                  ) : isTextResponse(fd) ? (
                    <CodeViewer content={fd.content} />
                  ) : null
                ) : (
                  <div className="flex items-center justify-center py-12 text-muted-foreground">
                    <span className="animate-pulse text-sm">Loading file...</span>
                  </div>
                )}
              </TabsContent>
            );
          })}
        </Tabs>
      )}

      {/* Actions */}
      {availableFiles.includes("generated_pvmap.csv") && (
        <div className="flex justify-center mt-4">
          <Button onClick={handleSaveAndRevalidate} disabled={revalidating}>
            {revalidating ? "Validating..." : "Save & Revalidate"}
          </Button>
        </div>
      )}
    </div>
  );
}
