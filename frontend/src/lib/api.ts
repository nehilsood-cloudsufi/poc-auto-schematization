/**
 * Typed API client for the FastAPI backend.
 *
 * This is a thin wrapper around `fetch()` that:
 * - Prepends `/api` to all paths
 * - Handles JSON serialization/deserialization
 * - Throws on non-2xx responses with the error detail
 */

import type {
  UploadResponse,
  StartRunRequest,
  Run,
  UpdateRunRequest,
  FileResponse,
  FeedbackRequest,
  PreviewResponse,
} from "@/types";

const BASE = "/api";

/** Generic fetch wrapper with error handling. */
async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { headers: extraHeaders, ...rest } = options;
  const response = await fetch(`${BASE}${path}`, {
    ...rest,
    headers: {
      "Content-Type": "application/json",
      ...(extraHeaders as Record<string, string>),
    },
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error((error as { detail?: string }).detail || `Request failed: ${response.status}`);
  }

  return response.json() as Promise<T>;
}

// ── Upload ─────────────────────────────────────────────

export async function uploadFiles(
  inputCsv: File,
  metadataCsv?: File,
  datasetName?: string
): Promise<UploadResponse> {
  const formData = new FormData();
  formData.append("input_csv", inputCsv);
  if (metadataCsv) formData.append("metadata_csv", metadataCsv);
  if (datasetName) formData.append("dataset_name", datasetName);

  const response = await fetch(`${BASE}/upload`, {
    method: "POST",
    body: formData,
    // Don't set Content-Type — browser sets it with boundary for multipart
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error((error as { detail?: string }).detail || "Upload failed");
  }

  return response.json() as Promise<UploadResponse>;
}

// ── Runs ───────────────────────────────────────────────

export async function startRun(req: StartRunRequest): Promise<{ run_id: string; status: string }> {
  return request("/runs", { method: "POST", body: JSON.stringify(req) });
}

export async function listRuns(includeArchived = false): Promise<Run[]> {
  const params = includeArchived ? "?include_archived=true" : "";
  return request(`/runs${params}`);
}

export async function getRun(runId: string): Promise<Run> {
  return request(`/runs/${runId}`);
}

// ── Files ──────────────────────────────────────────────

export async function listFiles(runId: string): Promise<{ files: string[] }> {
  return request(`/runs/${runId}/files`);
}

export async function getFile(runId: string, filename: string): Promise<FileResponse> {
  return request(`/runs/${runId}/files/${filename}`);
}

export async function updateFile(
  runId: string,
  filename: string,
  body: { rows?: Record<string, unknown>[] } | { content?: string }
): Promise<{ saved: boolean }> {
  return request(`/runs/${runId}/files/${filename}`, {
    method: "PUT",
    body: JSON.stringify(body),
  });
}

export async function downloadZip(runId: string): Promise<Blob> {
  const response = await fetch(`${BASE}/runs/${runId}/download`);
  if (!response.ok) throw new Error("Download failed");
  return response.blob();
}

// ── Feedback ───────────────────────────────────────────

export async function submitFeedback(
  runId: string,
  feedback: FeedbackRequest
): Promise<{ new_run_id: string }> {
  return request(`/runs/${runId}/feedback`, {
    method: "POST",
    body: JSON.stringify(feedback),
  });
}

export async function submitDevFeedback(
  runId: string,
  text: string,
  category: string
): Promise<{ saved: boolean }> {
  return request(`/runs/${runId}/dev-feedback`, {
    method: "POST",
    body: JSON.stringify({ text, category }),
  });
}

// ── Revalidation ───────────────────────────────────────

export async function revalidate(
  runId: string
): Promise<{ success: boolean; data_rows?: number; error?: string }> {
  return request(`/runs/${runId}/revalidate`, { method: "POST" });
}

// ── Plan & Control ────────────────────────────────────

export async function generatePvmap(
  runId: string,
  plan?: string
): Promise<{ status: string }> {
  return request(`/runs/${runId}/generate`, {
    method: "POST",
    body: JSON.stringify({ plan: plan ?? null }),
  });
}

export async function stopRun(runId: string): Promise<{ status: string }> {
  return request(`/runs/${runId}/stop`, { method: "POST" });
}

export async function resumeRun(
  runId: string
): Promise<{ status: string; resumed_from: string }> {
  return request(`/runs/${runId}/resume`, { method: "POST" });
}

// ── Data Preview ──────────────────────────────────────

export async function getPreview(
  runId: string,
  rows: number = 100
): Promise<PreviewResponse> {
  return request(`/runs/${runId}/preview?rows=${rows}`);
}

export async function updateRun(
  runId: string,
  data: UpdateRunRequest,
): Promise<Run> {
  return request<Run>(`/runs/${runId}`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function archiveRun(
  runId: string,
): Promise<{ archived: boolean }> {
  return request<{ archived: boolean }>(`/runs/${runId}/archive`, {
    method: "POST",
  });
}

export async function deleteRun(runId: string): Promise<void> {
  const resp = await fetch(`/api/runs/${runId}`, {
    method: "DELETE",
    headers: { "X-Confirm-Delete": "true" },
  });
  if (!resp.ok) {
    const detail = await resp.json().catch(() => ({}));
    throw new Error((detail as { detail?: string }).detail || `Delete failed: ${resp.status}`);
  }
}
