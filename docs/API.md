# REST API Specification: Multi-Agent RAG Debugger

The backend exposes a versioned REST API under `/api/v1` alongside legacy endpoints. All requests and responses use JSON.

Base URL: `http://localhost:8000/api/v1`

---

## Endpoints Summary

| Method | Endpoint | Description |
| :--- | :--- | :--- |
| `GET` | `/health` | System health, active provider, database state |
| `GET` | `/metrics` | Real operational telemetry and success metrics |
| `POST` | `/repositories/scan` | Scans directory and discovers valid source files |
| `POST` | `/debugging-runs` | Executes full multi-agent debugging workflow |
| `GET` | `/debugging-runs` | Lists historical debugging runs with search/filter |
| `GET` | `/debugging-runs/{run_id}` | Detailed report, root cause, diff, and stage traces |
| `GET` | `/debugging-runs/{run_id}/evidence` | Code evidence snippets with line numbers |
| `GET` | `/debugging-runs/{run_id}/patch` | Raw unified git diff patch |
| `POST` | `/debugging-runs/{run_id}/approval` | Submits human review (approve / reject / revise) |
| `GET` | `/settings` | Retrieve active LLM, inference, and sandbox configs |
| `POST` | `/settings` | Update runtime provider and parameters |

---

## Endpoint Details

### 1. `GET /api/v1/health`
Checks application availability, active provider, and database connectivity.

**Response `200 OK`**:
```json
{
  "status": "ok",
  "service": "multi-agent-rag-debugger",
  "version": "1.0.0",
  "llm_provider": "openrouter",
  "database": "connected"
}
```

---

### 2. `GET /api/v1/metrics`
Calculates genuine operational metrics from persisted run records.

**Response `200 OK`**:
```json
{
  "total_runs": 14,
  "completed_runs": 12,
  "failed_runs": 2,
  "approved_fixes": 11,
  "success_rate": 85.7,
  "avg_duration_ms": 14250.4
}
```

---

### 3. `POST /api/v1/repositories/scan`
Validates and scans a local directory, returning total file count and preview.

**Request Body**:
```json
{
  "repository_path": "D:\\AI TASK\\multi-agent-rag-debugger\\data\\sample_project"
}
```

**Response `200 OK`**:
```json
{
  "path": "D:\\AI TASK\\multi-agent-rag-debugger\\data\\sample_project",
  "exists": true,
  "is_directory": true,
  "total_files": 3,
  "files": [
    "README.md",
    "config.json",
    "login.py"
  ]
}
```

---

### 4. `POST /api/v1/debugging-runs`
Triggers the multi-agent debugging pipeline.

**Request Body**:
```json
{
  "title": "Login crash on empty password",
  "description": "User login raises TypeError when password is None",
  "repository_path": "D:\\AI TASK\\multi-agent-rag-debugger\\data\\sample_project",
  "top_k": 5,
  "use_langgraph": true,
  "provider": "openrouter"
}
```

**Response `200 OK`**:
```json
{
  "run_id": "8fa3c7b2-4d2b-4fa8-bcf6-71239854ef12",
  "created_at": "2026-10-19T12:00:00Z",
  "status": "validated",
  "message": "The proposed fix was applied in an isolated workspace and passed validation.",
  "issue": {
    "title": "Login crash on empty password",
    "description": "User login raises TypeError when password is None",
    "repository_path": "D:\\AI TASK\\multi-agent-rag-debugger\\data\\sample_project"
  },
  "analysis": {
    "issue_type": "bug",
    "priority": "high",
    "summary": "Login validation error",
    "affected_components": ["authentication"],
    "search_queries": ["def login", "authenticate user"]
  },
  "root_cause": {
    "root_cause": "Missing null guard before password hashing",
    "explanation": "login() passes None to hashing function without check",
    "affected_files": ["login.py"],
    "evidence": ["login.py: line 12"],
    "confidence": 0.95
  },
  "proposed_fix": {
    "summary": "Add null check to password input",
    "affected_files": ["login.py"],
    "patch": "diff --git a/login.py b/login.py\n...",
    "reasoning": "Prevents NoneType error"
  },
  "validation": {
    "passed": true,
    "tests_run": 2,
    "tests_passed": 2,
    "tests_failed": 0,
    "output": "2 passed in 0.12s",
    "errors": []
  },
  "validation_attempts": 1,
  "stage_traces": [
    {
      "stage": "analyze",
      "status": "completed",
      "duration_ms": 1250.4
    }
  ]
}
```

---

### 5. `POST /api/v1/debugging-runs/{run_id}/approval`
Submits a human review decision.

**Request Body**:
```json
{
  "status": "approved",
  "reviewer": "lead_developer",
  "comment": "Verified and passed isolated regression tests"
}
```

**Response `200 OK`**:
```json
{
  "run_id": "8fa3c7b2-4d2b-4fa8-bcf6-71239854ef12",
  "approval_status": "approved",
  "reviewer": "lead_developer",
  "reviewed_at": "2026-10-19T12:05:00Z",
  "comment": "Verified and passed isolated regression tests"
}
```
