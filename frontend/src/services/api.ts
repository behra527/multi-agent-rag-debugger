import {
  ApprovalRecord,
  DebugReport,
  DebugSessionSummary,
  DebuggingRunDetail,
  DebuggingRunSummary,
  EvaluationDataset,
  Evidence,
  Experiment,
  KnowledgeBase,
  KnowledgeDocument,
  OperationalMetrics,
  ProductOverview,
  SystemSettings,
} from "../types";

function resolveApiBase(): string {
  const explicit = String(import.meta.env.VITE_API_URL || "")
    .trim()
    .replace(/\/$/, "");
  if (explicit) return explicit;
  // Same-origin: Vite proxies /api → 127.0.0.1:8000 in development;
  // nginx does the same in Docker. Avoid http://localhost:8000 — on Windows
  // localhost often resolves to ::1 while uvicorn listens on 127.0.0.1.
  return "";
}

export const API_BASE = resolveApiBase();

function formatApiDetail(detail: unknown): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (!item || typeof item !== "object") return String(item);
        const loc = Array.isArray((item as { loc?: unknown }).loc)
          ? ((item as { loc: unknown[] }).loc.filter((part) => part !== "body" && part !== "query") as Array<string | number>)
          : [];
        const field = String(loc[0] || "field");
        const msg = String((item as { msg?: string }).msg || "invalid");
        if (field === "email") return "Enter a valid email (at least 3 characters).";
        if (field === "password") return "Password must be at least 8 characters.";
        return `${field}: ${msg}`;
      })
      .join(" ");
  }
  try {
    return JSON.stringify(detail);
  } catch {
    return "Request failed";
  }
}
const WORKSPACE_KEY = "rag-debugger-workspace";

export function getWorkspaceId(): string {
  return localStorage.getItem(WORKSPACE_KEY) || "default";
}

export function setWorkspaceId(value: string) {
  localStorage.setItem(WORKSPACE_KEY, value);
}

export function getAuthToken(): string | null {
  return localStorage.getItem("rag-debugger-token");
}

export function setAuthToken(token: string | null) {
  if (token) localStorage.setItem("rag-debugger-token", token);
  else localStorage.removeItem("rag-debugger-token");
}

export function clearAuth() {
  setAuthToken(null);
  localStorage.removeItem(WORKSPACE_KEY);
}

function workspaceHeaders(extra?: HeadersInit): HeadersInit {
  const headers: Record<string, string> = {
    "X-Workspace-Id": getWorkspaceId(),
  };
  const token = localStorage.getItem("rag-debugger-token");
  if (token) headers.Authorization = `Bearer ${token}`;
  return { ...headers, ...(extra || {}) };
}

async function request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const url = `${API_BASE}${endpoint}`;
  const headers: Record<string, string> = {
    ...((options.headers as Record<string, string>) || {}),
  };
  if (!(options.body instanceof FormData) && !headers["Content-Type"]) {
    headers["Content-Type"] = "application/json";
  }
  Object.assign(headers, workspaceHeaders());
  let response: Response;
  try {
    response = await fetch(url, {
      ...options,
      headers,
    });
  } catch (err) {
    const reason = err instanceof Error ? err.message : String(err);
    const target = API_BASE || window.location.origin;
    throw new Error(
      `Cannot reach the Atlas API at ${target}. Start the backend with ` +
        `python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 ` +
        `and open the UI at http://localhost:5173 so /api is proxied. ` +
        `Underlying error: ${reason}`
    );
  }

  if (!response.ok) {
    let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
    try {
      const errorJson = await response.json();
      if (errorJson.detail) errorMessage = formatApiDetail(errorJson.detail);
      else if (typeof errorJson.message === "string" && errorJson.message) errorMessage = errorJson.message;
    } catch {
      // ignore json parse errors
    }
    throw new Error(errorMessage);
  }

  return response.json();
}

export const api = {
  getHealth: () => request<{ status: string; service: string; version: string; llm_provider: string; database: string }>("/api/v1/health"),

  getMetrics: () => request<OperationalMetrics>("/api/v1/metrics"),

  scanRepository: (repositoryPath: string) =>
    request<{ path: string; exists: boolean; is_directory: boolean; total_files: number; files: string[] }>("/api/v1/repositories/scan", {
      method: "POST",
      body: JSON.stringify({ repository_path: repositoryPath }),
    }),

  startDebuggingRun: (payload: {
    title: string;
    description: string;
    repository_path: string;
    top_k?: number;
    use_langgraph?: boolean;
    provider?: string;
    validation_command?: string[];
  }) =>
    request<any>("/api/v1/debugging-runs", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listRuns: (params?: { skip?: number; limit?: number; status?: string; search?: string }) => {
    const query = new URLSearchParams();
    if (params?.skip !== undefined) query.set("skip", String(params.skip));
    if (params?.limit !== undefined) query.set("limit", String(params.limit));
    if (params?.status) query.set("status", params.status);
    if (params?.search) query.set("search", params.search);
    const qs = query.toString() ? `?${query.toString()}` : "";
    return request<DebuggingRunSummary[]>(`/api/v1/debugging-runs${qs}`);
  },

  getRunDetails: (runId: string) => request<DebuggingRunDetail>(`/api/v1/debugging-runs/${runId}`),

  getRunEvidence: (runId: string) => request<Evidence[]>(`/api/v1/debugging-runs/${runId}/evidence`),

  getRunPatch: (runId: string) => request<{ run_id: string; summary: string; affected_files: string[]; patch: string; reasoning: string }>(`/api/v1/debugging-runs/${runId}/patch`),

  submitApproval: (runId: string, payload: { status: "approved" | "rejected" | "revision_requested"; reviewer?: string; comment?: string }) =>
    request<ApprovalRecord>(`/api/v1/debugging-runs/${runId}/approval`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getSettings: () => request<SystemSettings>("/api/v1/settings"),

  updateSettings: (payload: Partial<SystemSettings>) =>
    request<SystemSettings>("/api/v1/settings", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getGitStatus: (repositoryPath: string) =>
    request<import("../types").GitRepositoryInfo>(
      `/api/v1/git/status?repository_path=${encodeURIComponent(repositoryPath)}`
    ),

  listGitCommits: (repositoryPath: string, limit: number = 10) =>
    request<import("../types").GitCommit[]>(
      `/api/v1/git/commits?repository_path=${encodeURIComponent(repositoryPath)}&limit=${limit}`
    ),

  createGitBranch: (payload: { repository_path: string; branch_name: string; base_branch?: string }) =>
    request<{ branch: string; created: boolean; head_sha: string }>("/api/v1/git/branch", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  commitApprovedPatch: (payload: {
    repository_path: string;
    run_id: string;
    branch_name?: string;
    commit_message?: string;
    author_name?: string;
    author_email?: string;
  }) =>
    request<{ commit_sha: string; message: string; author: string; modified_files: string[]; branch: string }>(
      "/api/v1/git/commit",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),

  cloneRepository: (payload: { remote_url: string; target_directory: string; branch?: string }) =>
    request<{ path: string; cloned: boolean; url: string }>("/api/v1/git/clone", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getOverview: () => request<ProductOverview>("/api/v1/overview"),

  listKnowledgeBases: () => request<KnowledgeBase[]>("/api/v1/knowledge-bases"),

  createKnowledgeBase: (payload: {
    name: string;
    description?: string;
    chunk_size?: number;
    chunk_overlap?: number;
    embedding_provider?: string;
  }) =>
    request<KnowledgeBase>("/api/v1/knowledge-bases", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getKnowledgeBase: (id: string) => request<KnowledgeBase>(`/api/v1/knowledge-bases/${id}`),

  deleteKnowledgeBase: (id: string) =>
    request<{ status: string }>(`/api/v1/knowledge-bases/${id}`, { method: "DELETE" }),

  uploadDocument: async (kbId: string, file: File) => {
    const body = new FormData();
    body.append("file", file);
    return request<KnowledgeDocument>(`/api/v1/knowledge-bases/${kbId}/documents`, {
      method: "POST",
      body,
    });
  },

  queryRag: (payload: {
    knowledge_base_id: string;
    query: string;
    config?: Record<string, unknown>;
  }) =>
    request<any>("/api/v1/rag/query", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  createDebugSession: (payload: {
    knowledge_base_id: string;
    query: string;
    config?: Record<string, unknown>;
  }) =>
    request<{ id: string; status: string; report: DebugReport; query: string; duration_ms?: number }>(
      "/api/v1/debug/sessions",
      {
        method: "POST",
        body: JSON.stringify(payload),
      }
    ),

  listDebugSessions: () => request<DebugSessionSummary[]>("/api/v1/debug/sessions"),

  getDebugSession: (id: string) =>
    request<{ id: string; status: string; report: DebugReport; query: string; error_message?: string }>(
      `/api/v1/debug/sessions/${id}`
    ),

  listDatasets: () => request<EvaluationDataset[]>("/api/v1/datasets"),

  createDataset: (payload: { name: string; description?: string }) =>
    request<EvaluationDataset>("/api/v1/datasets", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  getDataset: (id: string) => request<EvaluationDataset>(`/api/v1/datasets/${id}`),

  addDatasetItem: (
    datasetId: string,
    payload: { query: string; expected_answer?: string; relevant_document_ids?: string[] }
  ) =>
    request<any>(`/api/v1/datasets/${datasetId}/items`, {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  createExperiment: (payload: {
    name: string;
    knowledge_base_id: string;
    dataset_id: string;
    config?: Record<string, unknown>;
  }) =>
    request<Experiment>("/api/v1/experiments", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  listExperiments: () => request<Experiment[]>("/api/v1/experiments"),

  compareExperiments: (ids: string[]) =>
    request<{ experiments: Experiment[] }>(`/api/v1/experiments/compare?ids=${ids.join(",")}`),

  deleteDocument: (documentId: string) =>
    request<{ status: string }>(`/api/v1/documents/${documentId}`, { method: "DELETE" }),

  reindexKnowledgeBase: (kbId: string) =>
    request<{ chunk_count: number; document_count: number }>(`/api/v1/knowledge-bases/${kbId}/reindex`, {
      method: "POST",
    }),

  importDataset: (payload: Record<string, unknown>) =>
    request<EvaluationDataset>("/api/v1/datasets/import", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  exportDataset: (datasetId: string) =>
    request<Record<string, unknown>>(`/api/v1/datasets/${datasetId}/export`),

  exportExperiment: (experimentId: string) =>
    request<Record<string, unknown>>(`/api/v1/experiments/${experimentId}/export`),

  loadSample: () =>
    request<{
      sample: boolean;
      knowledge_base_id: string;
      dataset_id: string;
      document_id?: string | null;
      name: string;
      note: string;
    }>("/api/v1/onboarding/sample", { method: "POST" }),

  reproduceExperiment: (experimentId: string) =>
    request<Experiment>(`/api/v1/experiments/${experimentId}/reproduce`, { method: "POST" }),

  deleteDataset: (datasetId: string) =>
    request<{ status: string }>(`/api/v1/datasets/${datasetId}`, { method: "DELETE" }),

  register: (email: string, password: string) =>
    request<{ email: string; workspace_id: string; token: string; user_id: string }>("/api/v1/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  login: (email: string, password: string) =>
    request<{ email: string; workspace_id: string; token: string; user_id: string }>("/api/v1/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    }),

  me: () =>
    request<{ workspace_id: string; email?: string | null; auth_type: string; auth_mode: string }>("/api/v1/auth/me"),

  logout: () => request<{ status: string }>("/api/v1/auth/logout", { method: "POST" }),

  providersStatus: () => request<Record<string, unknown>>("/api/v1/providers/status"),

  listAudit: () => request<Array<Record<string, unknown>>>("/api/v1/audit"),

  createRepairSession: (payload: Record<string, unknown>) =>
    request<any>("/api/v1/repair/sessions", { method: "POST", body: JSON.stringify(payload) }),

  listRepairSessions: () => request<any[]>("/api/v1/repair/sessions"),

  getRepairSession: (id: string) => request<any>(`/api/v1/repair/sessions/${id}`),

  decideRepairSession: (id: string, payload: { decision: string; patch_revision: string; comment?: string }) =>
    request<any>(`/api/v1/repair/sessions/${id}/decision`, { method: "POST", body: JSON.stringify(payload) }),

  integrateRepairSession: (id: string) =>
    request<any>(`/api/v1/repair/sessions/${id}/integrate`, { method: "POST" }),

  cancelRepairSession: (id: string) =>
    request<any>(`/api/v1/repair/sessions/${id}/cancel`, { method: "POST" }),

  listAuthorizedRepos: () =>
    request<{ items: Array<{ name: string; path: string; kind: string }>; github_token_configured: boolean }>(
      "/api/v1/repair/repositories"
    ),

  restoreRepairCheckpoint: (id: string, checkpointId: string) =>
    request<any>(`/api/v1/repair/sessions/${id}/restore/${checkpointId}`, { method: "POST" }),
}
