# Repository Assessment (Phase 1)

Date: 2026-10-29

## Existing architecture

The repository is a **code-debugging** platform that uses RAG as a retrieval technique, not a debugger for RAG pipelines.

Entry points:

- FastAPI: `app.api.main:app` (`/debug` legacy + `/api/v1/*`)
- Streamlit prototype: `app/ui/streamlit_app.py`
- React SPA: `frontend/` (Vite + Tailwind)

Core flow: issue intake → issue analyzer LLM → repository scan/chunk/index → hybrid retrieval → root-cause LLM → patch LLM → sandbox pytest → human approval.

Persistence is SQLAlchemy (`create_all`) with SQLite by default. Vector search is in-process FAISS (`IndexFlatIP`) and is **not durable across process restarts**.

## Existing functional capabilities that are real

- Line-based code chunking with optional Python AST symbols
- Local SentenceTransformer embeddings
- In-memory FAISS similarity search
- Keyword overlap retrieval and reciprocal-rank hybrid fusion
- LLM provider adapters (OpenAI, OpenRouter, Ollama, mock)
- SQLite/Postgres-capable SQLAlchemy models for code-debug runs
- FastAPI routes for code-debug sessions, metrics, git helpers
- Docker Compose with pgvector (application code does not actually query pgvector)

## Incomplete, misleading, or non-product behavior

- Product docs claim a production RAG debugger; the implemented product debugs **source repositories**.
- `get_llm_client` silently falls back to `MockLLMClient` when OpenRouter has no key.
- Mock LLM fabricates issue analysis, root causes, and patches (including a hardcoded `calculate() -> 2` special case).
- Vector indexes live only in RAM; each request builds a new `ProjectManager`.
- No user document ingestion (PDF/DOCX/Markdown knowledge bases).
- No retrieval/generation evaluation framework, experiments, or claim-level faithfulness.
- No knowledge-base, dataset, or experiment APIs.
- Frontend is a code-debug dashboard (diffs, sandbox logs, repo explorer).
- `main.tsx` default-imports `App` while `App.tsx` only named-exports `App`.
- Auth is absent. Workspace isolation is absent. `POST /settings` mutates global process settings.
- `requirements.txt` omits SQLAlchemy/langgraph that Docker/CI install separately.
- `data/debugger.db` and generated artifacts are not fully ignored.
- LangGraph is an optional extra, not a required runtime for the default workflow.

## Architectural weaknesses

- Agents are prompt variants over one `generate()` call, not specialized analyzers.
- RAG primitives are coupled to repository files (`source`, `start_line`, `language`).
- Business logic sits in FastAPI route handlers and a per-request factory.
- No job queue; long workflows run inside the HTTP request.
- No request IDs, budget limits, or cost accounting on the hot path.
- Duplicate workflow implementations (`DebuggingWorkflow` vs `GraphDebuggingWorkflow`).

## Reliability and security risks

- Local `repository_path` lets the API read/scan arbitrary host directories.
- Git commit/branch endpoints can mutate local git repos.
- Sandbox reduces some patch risk but still executes tests on cloned workspaces.
- CORS is open to localhost origins; no authentication.
- Credentials can appear in logs if exceptions include request context.
- No upload size/type validation because uploads do not exist yet.
- Silent mock fallback hides misconfiguration.

## Missing product capabilities (RAG debugger)

Document knowledge bases, ingestion jobs, configurable chunk/embed/retrieve, query+citation generation, multi-agent RAG diagnostics, evaluation datasets, experiment comparison, evidence-backed reports, durable indexes, tenant isolation, and a UI for those workflows.

## Recommended changes (adopted)

Keep hybrid retrieval, FAISS, embedding interface, LLM adapters, and SQLAlchemy.

Rebuild the product around:

1. Persistent knowledge bases and document indexes
2. A real query/generation pipeline with provenance
3. Deterministic diagnostic agents plus optional LLM judgments labeled as such
4. Evaluation metrics only when labels exist
5. Versioned API + frontend for KB / debug / eval / reports
6. Workspace-scoped persistence, optional bearer auth, execution limits
7. Inline background jobs with durable status (no Redis required for the modular monolith)

Legacy code-debug modules remain available under existing `/api/v1/debugging-runs` routes so prior tests and demos keep working, but they are no longer the primary product.
