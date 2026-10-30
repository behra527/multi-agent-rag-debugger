# RAG Debugger operations

## Ingestion

`POST /api/v1/knowledge-bases` then `POST /api/v1/knowledge-bases/{id}/documents`.

States: `uploaded` → `extracting` → `chunking` → `embedding` → `indexed` or `failed`.

Duplicate content hashes return the existing document without re-indexing.

## Query

`POST /api/v1/rag/query` with `knowledge_base_id`, `query`, and optional `PipelineConfig`:

- `retrieval_mode`: `lexical` | `semantic` | `hybrid`
- `top_k`, `keyword_weight`, `vector_weight`, `rerank`, `generate_answer`

## Debug

`POST /api/v1/debug/sessions` runs retrieval then sequential analysts. Agent failures are recorded in `agent_traces` and do not fabricate findings. Workflows stop if `MAX_WORKFLOW_SECONDS` or `MAX_LLM_CALLS_PER_WORKFLOW` is exceeded.

Finding `kind` values:

- `measured` — computed from the live index or scores
- `heuristic` — useful but not labeled ground truth
- `model_based` — LLM judgment
- `hypothesis` — suggested, not demonstrated

## Evaluation

Create a dataset, add items with `relevant_document_ids`, then `POST /api/v1/experiments`. Ranking metrics are omitted when labels are missing.

Import/export:

- `POST /api/v1/datasets/import` with `{ "name", "description", "items": [{ "query", "expected_answer", "relevant_document_ids" }] }`
- `GET /api/v1/datasets/{id}/export`
- `GET /api/v1/experiments/{id}/export`

## Database migrations

Local development still calls `Base.metadata.create_all` on API startup so SQLite works with zero extra steps.

For an explicit schema upgrade (including PostgreSQL):

```powershell
.\.venv\Scripts\python -m alembic upgrade head
```

The baseline revision is `0001_baseline`.

## Optional sample data

`POST /api/v1/onboarding/sample` creates a knowledge base and dataset named with a `[Sample]` prefix. It is optional, labeled, and idempotent per workspace. The application does not require it to start.

## Reproduce an experiment

`POST /api/v1/experiments/{id}/reproduce` re-runs the saved pipeline configuration against the same dataset and knowledge base.

## Rate limits

Set `RATE_LIMIT_PER_MINUTE` to a positive integer to enable a per-IP window. `0` disables limiting. Health endpoints are excluded.

## Auth

- `AUTH_MODE=optional` (default): anonymous access with `X-Workspace-Id`.
- `AUTH_MODE=required`: register or login, then send `Authorization: Bearer <session token>`.
- A static `API_AUTH_TOKEN` still authenticates as a service account and may select a workspace header.

`POST /api/v1/auth/register` and `/api/v1/auth/login` return a session token. User tokens cannot read another user's workspace.

## Audit

`GET /api/v1/audit` lists workspace actions such as ingest, debug, and experiment runs.

## Provider status

`GET /api/v1/providers/status` reports whether LLM/embedding credentials are configured. It does not call the provider unless you run a query.
