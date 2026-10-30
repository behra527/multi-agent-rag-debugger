# Repository Assessment (Phase One)

Date: 2026-10-29

## Existing architecture

The repository started as a Final Year Project **code-debugging** platform: issue intake, hybrid retrieval over a local repository, root-cause analysis, patch generation, and sandboxed test validation. That stack remains in `app/core`, `app/agents` (issue/fix/root-cause), `app/tools`, `app/api/v1/router.py`, and the original React dashboard.

A second product layer for **RAG pipeline debugging** was already sketched but not fully connected:

- Domain schemas and enums in `app/domain`
- Knowledge-base persistence in `app/db/models.py`
- Ingestion, chunking, FAISS indexes, hybrid retrieval, and generation in `app/rag`
- Diagnostic agents and orchestrator in `app/agents/rag_agents.py` and `app/agents/orchestrator.py`
- Application services in `app/application`
- Product API in `app/api/v1/rag_routes.py` (not mounted on the FastAPI app)

Default deployment is a **modular monolith**: FastAPI + SQLAlchemy + on-disk FAISS + React SPA.

## Existing functional capabilities

- Code-debug workflow with mock/OpenAI/OpenRouter/Ollama providers
- Hybrid BM25 + dense retrieval for source files
- SQLite persistence for code-debug runs
- React UI for code-debug sessions
- Tests covering the original code-debug path

## Incomplete or nonfunctional components (before this iteration)

- `rag_routes` was not included in `app.api.main`, so knowledge bases, uploads, RAG query, debug sessions, datasets, and experiments were unreachable
- Request-ID middleware and structured `AppError` handlers were unused
- Frontend still called only code-debug endpoints and showed hardcoded-adjacent code-lab UX
- `requirements.txt` omitted SQLAlchemy, python-multipart, pypdf, and python-docx despite the code depending on them
- `.env.example` did not document embedding, database, workspace, or execution-limit settings
- Ingestion counted documents incorrectly (duplicate recount logic) and did not reject empty extracts
- Experiment compare route would be captured by `GET /experiments/{id}`
- Orchestrator aborted the entire debug session if one analyst raised
- Mock LLM had no grounded RAG-answer path (it fell through to generic JSON)

## Architectural weaknesses

- Two products share one API surface without a clear primary UX
- Process-local settings mutation via `POST /settings`
- Indexes live on local disk, not in the relational database
- Jobs exist as rows but execution is inline unless background mode is implemented
- Default LLM provider is `mock`, which is valid for offline use only if labeled as such

## Reliability and security risks

- Optional bearer auth only when `API_AUTH_TOKEN` is set
- Workspace isolation depends on `X-Workspace-Id` (spoofable unless auth is enabled)
- Uploads needed extension/size checks (present in `app.core.security` but unused if routes were unmounted)
- Ollama URL SSRF checks exist; OpenAI/OpenRouter use vendor endpoints

## Missing product capabilities (relative to a RAG debugger)

Users could not, through the running app: upload documents, index a knowledge base, query with citations, run diagnostic agents, or compare retrieval experiments.

## Recommended architectural changes

Keep a modular monolith. Make the RAG debugger the primary product. Preserve the code-debug API as a legacy lab. Do not introduce microservices or Redis until job volume requires it.

## Implementation priorities

1. Mount product routes, errors, and request IDs
2. Make ingestion → index → query → debug → evaluate a real path
3. Connect the frontend to those APIs
4. Add tests for metrics, isolation, ingestion, and debugging reports
5. Document configuration, limits, and evaluation caveats
