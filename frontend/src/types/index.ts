/**
 * Shared TypeScript types for the PVMAP Pipeline UI.
 *
 * These mirror the Python Pydantic models / API response shapes.
 */

/** Response from POST /api/upload */
export interface UploadResponse {
  run_id: string;
  dataset_name: string;
  run_dir: string;
  input_path: string;
  metadata_path: string | null;
  rows: number;
  columns: number;
  column_names: string[];
  preview: Record<string, unknown>[];
}

/** Request body for POST /api/runs */
export interface StartRunRequest {
  run_id: string;
  dataset_name: string;
  model?: string;
  max_retries?: number;
  enable_mcp?: boolean;
  use_schema_examples?: boolean;
  skip_sampling?: boolean;
  use_metadata?: boolean;
  human_feedback?: string | null;
  thinking_level?: string;
}

/** A pipeline run (from GET /api/runs or GET /api/runs/{id}) */
export interface Run {
  run_id: string;
  dataset_name: string;
  status: "pending" | "running" | "complete" | "error" | "stopped" | "plan_ready";
  timestamp?: string;
  validation_passed?: boolean;
  result?: PipelineResult;
  error?: string | null;
  config?: Record<string, unknown>;
  display_name?: string;
  notes?: string;
  archived?: boolean;
}

export interface UpdateRunRequest {
  display_name?: string;
  notes?: string;
}

/** Pipeline result embedded in a Run */
export interface PipelineResult {
  validation_passed?: boolean;
  exit_reason?: string;
  retry_count?: number;
  phase?: string;
  quality_metrics?: {
    heuristic_score?: number;
  };
}

/** WebSocket progress message from the server */
export interface ProgressEvent {
  type: "progress" | "complete" | "error";
  agent: string;
  message: string;
  timestamp?: number;
  attempt?: number;
  result?: PipelineResult;
  traceback?: string;
}

/** Response from GET /api/runs/{id}/files/{name} for CSV files */
export interface CsvFileResponse {
  type: "csv";
  filename: string;
  rows: Record<string, unknown>[];
  columns: string[];
  row_count: number;
}

/** Response from GET /api/runs/{id}/files/{name} for text files */
export interface TextFileResponse {
  type: "text";
  filename: string;
  content: string;
}

export type FileResponse = CsvFileResponse | TextFileResponse;

/** Feedback submission */
export interface FeedbackRequest {
  text: string;
  category: string;
  severity: number;
}

/** Pipeline configuration (stored in React state across wizard steps) */
export interface PipelineConfig {
  dataset_name: string;
  model: string;
  max_retries: number;
  enable_mcp: boolean;
  use_schema_examples: boolean;
  human_feedback: string | null;
}

/** Pipeline phases for progress display */
/** Response from GET /api/runs/{id}/preview */
export interface PreviewResponse {
  total_rows: number;
  columns: number;
  column_names: string[];
  showing: number;
  data: Record<string, unknown>[];
}

// ── Structured Plan Types ─────────────────────────────────

export type CandidateSource = "from Schema.org" | "from MCP" | "from schema_vocab" | "LLM suggestion" | "user override";
export type ColumnRole = "observationAbout" | "observationDate" | "measure" | "dimension" | "metadata" | "ignored";

export interface CandidateValidation {
  property_exists: boolean;
  place_resolution_rate: number | null;
  existing_statvar: string | null;
  notes: string;
}

export interface PropertyValueCandidate {
  property: string;
  value_expression: string;
  confidence: number;
  source: CandidateSource;
  reason: string;
  validation: CandidateValidation | null;
}

export interface ColumnMapping {
  column_name: string;
  role: ColumnRole;
  candidates: PropertyValueCandidate[];
  selected_index: number;
  evidence: string;
  dc_match: string | null;
  is_ambiguous: boolean;
}

export interface StaticProperty {
  property_name: string;
  candidates: PropertyValueCandidate[];
  selected_index: number;
}

export interface DatasetUnderstanding {
  archetype: string;
  observation_grain: string;
  key_insight: string;
}

export interface MappingPlan {
  dataset_name: string;
  understanding: DatasetUnderstanding;
  active_columns: ColumnMapping[];
  ignored_columns: ColumnMapping[];
  static_properties: StaticProperty[];
  global_notes: string[];
}

export const PIPELINE_PHASES = [
  "StatePrep",
  "Sampling",
  "SchemaSelectionAgent",
  "SchemaOrgEnrichment",
  "MappingPlan",
  "PlanGate",
  "Generator",
  "MetadataGenerator",
  "Validator",
  "QualityEvaluator",
  "UnifiedFeedback",
  "MaxRetriesCheck",
] as const;

/** Phase 1 only (plan generation) */
export const PLAN_PHASES = [
  "StatePrep",
  "Sampling",
  "SchemaSelectionAgent",
  "SchemaOrgEnrichment",
  "CandidateRetriever",
  "MappingPlan",
  "PlanValidator",
] as const;

/** Phase 2 only (PVMAP generation) */
export const GENERATE_PHASES = [
  "Generator",
  "MetadataGenerator",
  "Validator",
  "QualityEvaluator",
  "UnifiedFeedback",
  "MaxRetriesCheck",
] as const;

export const PHASE_LABELS: Record<string, string> = {
  StatePrep: "Preparing state",
  Sampling: "Sampling data",
  SchemaSelectionAgent: "Selecting schema",
  SchemaOrgEnrichment: "Enriching with Schema.org",
  CandidateRetriever: "Retrieving grounding candidates",
  MappingPlan: "Generating mapping plan",
  PlanValidator: "Validating against DC API",
  PlanGate: "Plan approval",
  StatVarDiscovery: "Discovering StatVars (MCP)",
  Generator: "Generating PVMAP",
  MetadataGenerator: "Generating metadata config",
  Validator: "Validating PVMAP",
  MCPSpotCheck: "Spot-checking mappings (MCP)",
  MCPErrorResolver: "Resolving errors (MCP)",
  QualityEvaluator: "Evaluating quality",
  UnifiedFeedback: "Generating feedback",
  MaxRetriesCheck: "Checking retry status",
  Evaluation: "Running evaluation",
};
