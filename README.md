# Multi-Agent RAG Debugger

Atlas Repair is the primary workspace: report an error, connect a repository the API can read, review an evidence-backed diagnosis and patch, approve application to an isolated candidate, then run tests. The document RAG debugger remains available in the UI.

A modular monolith also investigates **real RAG pipelines**: ingest your documents, index them, query with hybrid retrieval, generate grounded answers, and run multi-agent diagnostics that distinguish measured statistics from model-based judgments.

A legacy **code-debugging lab** (issue → patch → sandbox) remains available under `/api/v1/debugging-runs` and the frontend **Code Lab** tab.

---

## What this application actually does

- Create workspace-scoped knowledge bases.
- Upload TXT, Markdown, PDF, DOCX, or JSON documents.
- Extract, chunk, embed, and persist a FAISS index with chunk provenance.
- Query with lexical, semantic, or hybrid retrieval and optional reranking.
- Generate answers only from retrieved context (or skip generation).
- Run retrieval, chunking, embedding, generation, faithfulness, and root-cause analysts.
- Persist debug reports, evaluation datasets, and experiment metrics.
- Report precision/recall/MRR/nDCG **only** when relevant document IDs are labeled.

It does **not** invent retrieval scores, token usage, or dashboard metrics. Mock LLM and hash embeddings are explicit offline modes, not silent fallbacks for failed providers.

---

## Architecture

```
User documents
    → ingestion (extract / chunk / embed)
    → FAISS + BM25 hybrid retrieval
    → optional LLM generation + citations
    → diagnostic agents (bounded, sequential)
    → persisted report / experiment
```

Application layers live under `app/`:

| Package | Responsibility |
| :--- | :--- |
| `app/domain` | Schemas and enums |
| `app/rag` | Ingestion, chunking, embeddings, index, retrieval, metrics |
| `app/agents` | Diagnostic analysts and orchestrator |
| `app/application` | Knowledge, debug, and evaluation services |
| `app/api` | FastAPI routes, auth dependency, error handlers |
| `app/db` | SQLAlchemy models and sessions |
| `app/llm` | OpenAI, OpenRouter, Ollama, mock adapters |
| `frontend` | React workspace for the product |

See [docs/REPOSITORY_ASSESSMENT.md](docs/REPOSITORY_ASSESSMENT.md) and [docs/RAG_DEBUGGER.md](docs/RAG_DEBUGGER.md).

---

## Quickstart

Prerequisites: Python 3.13+, Node.js 20+, Git.

```powershell
cd "D:\AI TASK\multi-agent-rag-debugger"
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

- UI: `http://localhost:5173` (proxies `/api` to `127.0.0.1:8000`)
- OpenAPI: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/v1/health`

If the UI shows **Failed to fetch** / **API offline**, the backend is not listening on IPv4 port 8000. Bind with `--host 127.0.0.1` (not `localhost`, which can be IPv6 on Windows). Leave `VITE_API_URL` empty so the browser uses the Vite proxy. Demo repos: [data/README.md](data/README.md).

For shared deployments set `AUTH_MODE=required` and register a user in Settings. Session tokens are stored hashed.

Default `.env.example` uses `LLM_PROVIDER=mock` and `EMBEDDING_PROVIDER=hash` so the product runs offline. For semantic retrieval set `EMBEDDING_PROVIDER=local` (downloads sentence-transformers weights) or `openai` with `OPENAI_API_KEY`. For live generation set `LLM_PROVIDER` to `openai`, `openrouter`, or `ollama` and supply the matching credentials/URL.

---

## Database migrations

SQLite still initializes with `create_all` on API startup. To apply the Alembic baseline (required for a fresh PostgreSQL volume if you prefer migrations over implicit create):

```powershell
.\.venv\Scripts\python -m alembic upgrade head
```

## Tests

```powershell
.\.venv\Scripts\python -m pytest tests -q
```

Demo fixtures (expected to fail until repaired): see [data/README.md](data/README.md).

New product tests live in `tests/test_rag_product_api.py`, `tests/test_rag_metrics.py`, and `tests/test_security_controls.py`. They use hash embeddings and the mock LLM. They do not prove that OpenAI or a local sentence-transformer deployment is reachable.

---

## Docker

```bash
docker compose up --build
```

Compose defaults to mock/hash unless you pass `LLM_PROVIDER` / `EMBEDDING_PROVIDER` and API keys. PostgreSQL is used for application metadata; vector search still uses on-disk FAISS indexes mounted at `./data`.

---

## Security notes

- Set `API_AUTH_TOKEN` in any shared environment. When empty, the API is open for local development.
- Workspace isolation uses `X-Workspace-Id` at the service layer. Combine it with a bearer token in production.
- Uploads are limited by type and size. Retrieved document text is treated as untrusted in generation prompts.
- Do not commit `.env` or `data/*.db`.

---

## Known limitations

- Ingestion runs inline in the API process (`JOB_EXECUTION_MODE=inline`). Large corpora can exceed request time; use smaller files or split uploads.
- Hash embeddings are not semantic. Hybrid lexical search still works.
- Faithfulness “unsupported claims” from lexical overlap or an LLM judge are evaluations, not guarantees.
- Runtime `POST /api/v1/settings` mutates process memory only; it is not a durable settings store.
- Multi-user identity is workspace-header based, not a full account system.
