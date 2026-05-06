/**
 * Collapsible viewer for extracted SDMX metadata JSON.
 * Shows a summary card with dataflow name, DSD id, and component counts.
 * Expands to show the full structured JSON grouped by dimensions/attributes/measures/codelists.
 */
import { useState } from "react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ChevronDown, ChevronUp, Database, Layers, Tag } from "lucide-react";
import type { SdmxMetadata, SdmxDataflow, SdmxComponent } from "@/types";

interface SdmxMetadataViewerProps {
  metadata: SdmxMetadata;
  defaultExpanded?: boolean;
}

function ComponentRow({ comp, kind }: { comp: SdmxComponent; kind: string }) {
  const rep = comp.representation;
  const codelistSize = rep?.codelist?.codes?.length ?? 0;
  return (
    <div className="flex items-start gap-2 py-1 border-b border-border/40 last:border-0">
      <code className="text-xs font-mono bg-muted px-1.5 py-0.5 rounded shrink-0">{comp.id}</code>
      {comp.name && <span className="text-xs text-muted-foreground">{comp.name}</span>}
      <div className="ml-auto flex items-center gap-1 shrink-0">
        <Badge variant="secondary" className="text-[10px] px-1.5 py-0">{kind}</Badge>
        {rep?.type === "enumerated" && codelistSize > 0 && (
          <Badge variant="outline" className="text-[10px] px-1.5 py-0">
            {codelistSize} codes
          </Badge>
        )}
      </div>
    </div>
  );
}

function DataflowSection({ df }: { df: SdmxDataflow }) {
  const dsd = df.data_structure_definition;
  const dims = dsd?.dimensions ?? [];
  const attrs = dsd?.attributes ?? [];
  const measures = dsd?.measures ?? [];
  const total = dims.length + attrs.length + measures.length;

  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2 flex-wrap">
        <span className="text-sm font-medium">{df.name || df.id}</span>
        {dsd?.id && (
          <code className="text-[11px] font-mono text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
            DSD: {dsd.id}
          </code>
        )}
        {total > 0 && (
          <span className="text-xs text-muted-foreground">{total} components</span>
        )}
      </div>

      {df.description && (
        <p className="text-xs text-muted-foreground">{df.description}</p>
      )}

      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        {dims.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
              <Layers className="w-3 h-3" /> Dimensions ({dims.length})
            </p>
            <div className="rounded-md border bg-muted/30 px-3 py-1">
              {dims.map((d) => <ComponentRow key={d.id} comp={d} kind="dim" />)}
            </div>
          </div>
        )}
        {measures.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
              <Database className="w-3 h-3" /> Measures ({measures.length})
            </p>
            <div className="rounded-md border bg-muted/30 px-3 py-1">
              {measures.map((m) => <ComponentRow key={m.id} comp={m} kind="measure" />)}
            </div>
          </div>
        )}
        {attrs.length > 0 && (
          <div>
            <p className="text-xs font-medium text-muted-foreground mb-1 flex items-center gap-1">
              <Tag className="w-3 h-3" /> Attributes ({attrs.length})
            </p>
            <div className="rounded-md border bg-muted/30 px-3 py-1">
              {attrs.map((a) => <ComponentRow key={a.id} comp={a} kind="attr" />)}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

export function SdmxMetadataViewer({ metadata, defaultExpanded = false }: SdmxMetadataViewerProps) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [showRaw, setShowRaw] = useState(false);

  const dataflows = metadata.dataflows ?? [];
  if (dataflows.length === 0) return null;

  const first = dataflows[0];
  const dsd = first.data_structure_definition;
  const dimCount = dsd?.dimensions?.length ?? 0;
  const attrCount = dsd?.attributes?.length ?? 0;
  const measureCount = dsd?.measures?.length ?? 0;

  return (
    <Card className="shadow-sm border-blue-200/60 dark:border-blue-800/40 bg-blue-50/30 dark:bg-blue-950/10">
      <CardHeader className="pb-2 pt-4 px-4">
        <button
          type="button"
          className="w-full flex items-center justify-between cursor-pointer"
          onClick={() => setExpanded((v) => !v)}
        >
          <CardTitle className="text-sm font-medium flex items-center gap-2">
            <Database className="w-4 h-4 text-blue-500" />
            SDMX Metadata Extracted
            <Badge className="text-[10px] bg-blue-100 text-blue-700 dark:bg-blue-900 dark:text-blue-300 border-blue-200">
              JSON
            </Badge>
          </CardTitle>
          <div className="flex items-center gap-3">
            <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <span>{dimCount}D</span>
              <span>·</span>
              <span>{measureCount}M</span>
              <span>·</span>
              <span>{attrCount}A</span>
            </div>
            {expanded ? (
              <ChevronUp className="w-4 h-4 text-muted-foreground" />
            ) : (
              <ChevronDown className="w-4 h-4 text-muted-foreground" />
            )}
          </div>
        </button>
      </CardHeader>

      {expanded && (
        <CardContent className="px-4 pb-4 pt-0 space-y-4">
          {dataflows.map((df) => (
            <DataflowSection key={df.id} df={df} />
          ))}

          <div className="flex justify-end">
            <Button
              variant="ghost"
              size="sm"
              className="text-xs h-7"
              onClick={() => setShowRaw((v) => !v)}
            >
              {showRaw ? "Hide raw JSON" : "View raw JSON"}
            </Button>
          </div>

          {showRaw && (
            <pre className="text-[10px] font-mono bg-muted rounded-md p-3 overflow-auto max-h-64 leading-relaxed">
              {JSON.stringify(metadata, null, 2)}
            </pre>
          )}
        </CardContent>
      )}
    </Card>
  );
}
