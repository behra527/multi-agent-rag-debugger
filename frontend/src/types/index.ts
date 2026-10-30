export type IssueType = "bug" | "error" | "performance" | "security" | "test_failure" | "unknown";
export type IssuePriority = "low" | "medium" | "high" | "critical";

export interface IssueRequest {
  title: string;
  description: string;
  repository_path: string;
}

export interface IssueAnalysis {
  issue_type: IssueType;
  priority: IssuePriority;
  summary: string;
  affected_components: string[];
  search_queries: string[];
}

export interface Evidence {
  source: string;
  content: string;
  score: number;
  start_line: number;
  end_line: number;
  language: string;
  symbols?: string[];
}

export interface RootCauseAnalysis {
  root_cause: string;
  explanation: string;
  affected_files: string[];
  evidence: string[];
  confidence: number;
}

export interface ProposedFix {
  summary: string;
  affected_files: string[];
  patch: string;
  reasoning: string;
}

export interface ValidationResult {
  passed: boolean;
  tests_run: number;
  tests_passed: number;
  tests_failed: number;
  output: string;
  errors: string[];
  attempts?: number;
}

export interface StageTrace {
  stage: string;
  status: "running" | "completed" | "failed";
  started_at: string;
  finished_at?: string;
  duration_ms?: number;
  error_type?: string;
  error_message?: string;
}

export interface ApprovalRecord {
  status: "approved" | "rejected" | "revision_requested";
  reviewer: string;
  comment?: string;
  reviewed_at: string;
}

export interface DebuggingRunSummary {
  run_id: string;
  created_at: string;
  status: string;
  title: string;
  description: string;
  repository_path: string;
  duration_ms?: number;
  message?: string;
  approval_status: string;
  has_fix: boolean;
  validation_passed?: boolean;
}

export interface DebuggingRunDetail extends DebuggingRunSummary {
  analysis?: IssueAnalysis;
  root_cause?: RootCauseAnalysis;
  proposed_fix?: ProposedFix;
  validation?: ValidationResult;
  evidence_count: number;
  stage_traces: StageTrace[];
  approval_history: ApprovalRecord[];
}

export interface OperationalMetrics {
  total_runs: number;
  completed_runs: number;
  failed_runs: number;
  approved_fixes: number;
  success_rate: number;
  avg_duration_ms: number;
}

export interface ProductOverview {
  knowledge_bases: number;
  documents: number;
  debug_sessions: number;
  failed_ingestions: number;
  experiments: number;
  source: string;
  llm_provider?: string;
  embedding_provider?: string;
  auth_required?: boolean;
}

export interface KnowledgeBase {
  id: string;
  name: string;
  description: string;
  chunk_size: number;
  chunk_overlap: number;
  embedding_provider: string;
  embedding_model: string;
  embedding_dimension: number;
  document_count: number;
  chunk_count: number;
  created_at: string | null;
  documents?: KnowledgeDocument[];
}

export interface KnowledgeDocument {
  id: string;
  knowledge_base_id: string;
  filename: string;
  status: string;
  checksum: string;
  char_count: number;
  chunk_count: number;
  error_message?: string | null;
  created_at: string | null;
  job_id?: string | null;
}

export interface DebugSessionSummary {
  id: string;
  status: string;
  knowledge_base_id: string;
  query: string;
  duration_ms?: number | null;
  created_at: string | null;
}

export interface DebugReport {
  session_id: string;
  knowledge_base_id: string;
  query: string;
  executive_summary: string;
  methodology: string;
  measured_metrics: Record<string, unknown>;
  findings: Array<{
    agent: string;
    title: string;
    description: string;
    severity: string;
    confidence: number;
    kind: string;
    stage: string;
    evidence: string[];
    recommendation?: string | null;
    validation_procedure?: string | null;
    metrics?: Record<string, unknown>;
  }>;
  root_causes: Array<{
    description: string;
    supporting_evidence: string[];
    confidence: number;
    severity: string;
    affected_stage: string;
    recommended_action: string;
    validation_procedure: string;
    causation: string;
  }>;
  recommendations: string[];
  remaining_uncertainties: string[];
  usage: Record<string, unknown>;
  agent_traces: Array<{ agent: string; status: string; duration_ms?: number; error?: string }>;
  query_result?: {
    query: string;
    answer?: string | null;
    citations: Array<{ chunk_id: string; source: string; document_id: string; quote: string; score: number }>;
    retrieved: Array<{
      score: number;
      lexical_score?: number | null;
      semantic_score?: number | null;
      chunk: { chunk_id: string; source: string; content: string; document_id: string };
    }>;
    context_truncated: boolean;
    latencies_ms: Record<string, number>;
  };
}

export interface EvaluationDataset {
  id: string;
  name: string;
  description: string;
  item_count?: number;
  created_at: string | null;
  items?: Array<{
    id: string;
    query: string;
    expected_answer?: string | null;
    relevant_document_ids: string[];
  }>;
}

export interface Experiment {
  id: string;
  name: string;
  status: string;
  knowledge_base_id?: string;
  dataset_id?: string;
  metrics: Record<string, unknown>;
  results?: Array<Record<string, unknown>>;
  config?: Record<string, unknown>;
  created_at: string | null;
}

export interface SystemSettings {
  app_name: string;
  app_env: string;
  llm_provider: string;
  llm_model: string;
  openai_model: string;
  ollama_base_url: string;
  ollama_model: string;
  llm_temperature: number;
  llm_max_tokens: number;
  database_url: string;
  sandbox_timeout_seconds: number;
}

export interface GitCommit {
  sha: string;
  author: string;
  date: string;
  message: string;
}

export interface GitRepositoryInfo {
  is_git: boolean;
  current_branch?: string;
  commit_sha?: string;
  commit_author?: string;
  commit_message?: string;
  branches: string[];
  is_clean: boolean;
  modified_files: string[];
  untracked_files: string[];
  detected_framework?: string;
  default_test_command?: string[];
}
