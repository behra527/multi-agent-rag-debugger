# Deployment Guide: Multi-Agent RAG Debugger

This guide outlines both local bare-metal development setup and production containerized deployment.

---

## 1. Local Bare-Metal Setup (Windows / Linux / macOS)

### Step 1: Clone and Configure Environment
```bash
git clone https://github.com/behra527/multi-agent-rag-debugger.git
cd multi-agent-rag-debugger
```

Create virtual environment:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
pip install langgraph sqlalchemy
```

Configure `.env`:
```powershell
cp .env.example .env
```
Key settings in `.env`:
```ini
APP_NAME=Multi-Agent RAG Debugger
APP_ENV=development
LLM_PROVIDER=openrouter  # or openai, ollama, mock
OPENROUTER_API_KEY=your_key_here
OPENAI_API_KEY=your_key_here
DATABASE_URL=sqlite:///data/debugger.db
```

### Step 2: Start Backend Server
```powershell
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
```
API is available at `http://localhost:8000`. Database tables are automatically initialized upon startup.

### Step 3: Start React Frontend
In a separate terminal:
```powershell
cd frontend
npm install
npm run dev
```
Open `http://localhost:5173`. Requests to `/api/*` are automatically proxied to `http://localhost:8000`.

---

## 2. Production Docker Compose Deployment

The repository includes a multi-service `docker-compose.yml` comprising:
- **`backend`**: Multi-stage Python 3.13 image with unprivileged `appuser`.
- **`frontend`**: Vite React single-page app compiled to static assets and served via Nginx.
- **`db`**: PostgreSQL 16 image with the `pgvector` extension enabled for persistent vector storage.

### Launch Services:
```bash
docker compose up -d --build
```

### Service URLs:
- Frontend Web Dashboard: `http://localhost:5173`
- Backend API Docs: `http://localhost:8000/docs`
- Health Endpoint: `http://localhost:8000/api/v1/health`
- PostgreSQL: `localhost:5432` (database: `debugger_db`, user: `debugger`)

### Checking Container Health:
```bash
docker compose ps
docker compose logs -f backend
```

---

## 3. Environment Variables Reference

| Variable | Default | Purpose |
| :--- | :--- | :--- |
| `LLM_PROVIDER` | `openrouter` | Provider selector (`openrouter`, `openai`, `ollama`, `mock`) |
| `OPENROUTER_API_KEY` | `""` | API key for OpenRouter models |
| `OPENAI_API_KEY` | `""` | API key for OpenAI direct |
| `OLLAMA_BASE_URL` | `http://localhost:11434/v1` | Local Ollama endpoint |
| `DATABASE_URL` | `sqlite:///data/debugger.db` | Database connection string |
| `SANDBOX_TIMEOUT_SECONDS` | `120` | Maximum test runner execution time |
| `LLM_MAX_TOKENS` | `800` | Token limit per LLM response |
| `LLM_TEMPERATURE` | `0.2` | Generation temperature |
