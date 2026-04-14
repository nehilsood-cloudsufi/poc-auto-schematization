/**
 * Tabbed output file viewer with tab icons and sanitized markdown.
 */
import { useCallback, useEffect, useState } from "react";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Badge } from "@/components/ui/badge";
import { CsvEditor } from "./CsvEditor";
import { CodeViewer } from "./CodeViewer";
import { listFiles, getFile } from "@/lib/api";
import DOMPurify from "dompurify";
import { toast } from "sonner";
import {
  Table2,
  FileText,
  FileCode,
  BarChart3,
  StickyNote,
  Loader2,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import type { FileResponse, CsvFileResponse, TextFileResponse, PipelineResult } from "@/types";

const TAB_CONFIG = [
  { key: "processed.csv", label: "Processed", icon: Table2 },
  { key: "processed.mcf", label: "MCF", icon: FileCode },
  { key: "processed.tmcf", label: "TMCF", icon: FileCode },
  { key: "processed_stat_vars.mcf", label: "StatVars", icon: FileText },
  { key: "generation_notes.md", label: "Notes", icon: StickyNote },
  { key: "processed_counters.txt", label: "Metrics", icon: BarChart3 },
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

/** Simple markdown-to-HTML for rendering .md file content. */
function renderMarkdown(text: string): string {
  return text
    .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
    .replace(/^### (.+)$/gm, "<h3>$1</h3>")
    .replace(/^## (.+)$/gm, "<h2>$1</h2>")
    .replace(/^# (.+)$/gm, "<h1>$1</h1>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/`(.+?)`/g, "<code>$1</code>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/\n\n/g, "</p><p>")
    .replace(/\n/g, "<br>");
}

export function ResultBanner({ result }: { result: PipelineResult }) {
  const passed = result.validation_passed;
  const attempts = (result.retry_count ?? 0) + 1;
  const exitReason = result.exit_reason ?? "Unknown";
  const score = result.quality_metrics?.heuristic_score;

  return (
    <div className={`mb-4 p-4 rounded-lg border flex items-center justify-between ${
      passed
        ? "bg-green-50 border-green-200 dark:bg-green-950/30 dark:border-green-800"
        : "bg-red-50 border-red-200 dark:bg-red-950/30 dark:border-red-800"
    }`}>
      <div className="flex items-center gap-3">
        {passed ? (
          <CheckCircle2 className="w-5 h-5 text-green-600 dark:text-green-400 flex-shrink-0" />
        ) : (
          <XCircle className="w-5 h-5 text-red-500 flex-shrink-0" />
        )}
        <div>
          <p className={`text-sm font-medium ${passed ? "text-green-800 dark:text-green-200" : "text-red-800 dark:text-red-200"}`}>
            {passed ? "Validation Passed" : "Validation Failed"}
          </p>
          <p className="text-xs text-muted-foreground mt-0.5">
            {attempts} attempt{attempts !== 1 ? "s" : ""} — {exitReason}
          </p>
        </div>
      </div>
      {score != null && (
        <Badge variant="outline" className="text-sm tabular-nums">
          Score: {score.toFixed(1)}/100
        </Badge>
      )}
    </div>
  );
}

export function OutputViewer({ runId, result }: OutputViewerProps) {
  const [availableFiles, setAvailableFiles] = useState<string[]>([]);
  const [fileData, setFileData] = useState<Record<string, FileResponse>>({});
  const [activeTab, setActiveTab] = useState<string>("");

  // Reset all state when runId changes so stale data from previous run is cleared
  useEffect(() => {
    setAvailableFiles([]);
    setFileData({});
    setActiveTab("");
    listFiles(runId)
      .then((resp) => { setAvailableFiles(resp.files); })
      .catch(() => { toast.error("Failed to load output files"); });
  }, [runId]);

  const loadFile = useCallback(async (filename: string) => {
    if (fileData[filename]) return;
    try {
      const data = await getFile(runId, filename);
      setFileData((prev) => ({ ...prev, [filename]: data }));
    } catch {
      // Store a placeholder so the UI shows an error instead of infinite spinner
      setFileData((prev) => ({
        ...prev,
        [filename]: { type: "text", filename, content: "Failed to load file." } as TextFileResponse,
      }));
    }
  }, [runId, fileData]);

  useEffect(() => {
    const tabs = TAB_CONFIG.filter((t) => availableFiles.includes(t.key));
    if (tabs.length === 0) return;
    const firstKey = tabs[0].key;
    if (!fileData[firstKey]) {
      void loadFile(firstKey);
    }
    if (!activeTab) {
      setActiveTab(firstKey);
    }
  }, [availableFiles, fileData, loadFile, activeTab]);

  const handleTabChange = (value: string) => {
    setActiveTab(value);
    void loadFile(value);
  };

  const tabs = TAB_CONFIG.filter((t) => availableFiles.includes(t.key));

  return (
    <div>
      {result && <ResultBanner result={result} />}

      {tabs.length === 0 ? (
        <div className="text-center py-12">
          <FileText className="w-8 h-8 mx-auto text-muted-foreground/40 mb-2" />
          <p className="text-sm text-muted-foreground">No output files found.</p>
        </div>
      ) : (
        <Tabs value={activeTab || tabs[0]?.key} onValueChange={handleTabChange}>
          <TabsList className="flex-wrap h-auto gap-1">
            {tabs.map((tab) => {
              const Icon = tab.icon;
              const fd = fileData[tab.key];
              const sizeLabel = fd && isCsvResponse(fd) ? ` (${fd.row_count}r)` : "";
              return (
                <TabsTrigger key={tab.key} value={tab.key} className="text-xs gap-1.5">
                  <Icon className="w-3.5 h-3.5" />
                  {tab.label}{sizeLabel}
                </TabsTrigger>
              );
            })}
          </TabsList>

          {tabs.map((tab) => {
            const fd = fileData[tab.key];
            return (
              <TabsContent key={tab.key} value={tab.key}>
                {fd ? (
                  isCsvResponse(fd) ? (
                    <CsvEditor
                      columns={fd.columns}
                      rows={fd.rows}
                      editable={false}
                    />
                  ) : tab.key.endsWith(".md") && isTextResponse(fd) ? (
                    <div
                      className="prose dark:prose-invert max-w-none p-4"
                      dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(renderMarkdown(fd.content)) }}
                    />
                  ) : isTextResponse(fd) ? (
                    <CodeViewer content={fd.content} />
                  ) : null
                ) : (
                  <div className="flex items-center justify-center py-12 gap-2 text-muted-foreground">
                    <Loader2 className="w-4 h-4 animate-spin" />
                    <span className="text-sm">Loading file...</span>
                  </div>
                )}
              </TabsContent>
            );
          })}
        </Tabs>
      )}

    </div>
  );
}
