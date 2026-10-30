# Atlas Repair — three-agent code debugger

Primary product workflow:

1. Manager submits an error and a repository the **API process can read**.
2. Investigator retrieves real files and produces a diagnosis (no invented paths).
3. Repair engineer proposes a unified diff. The target project is not modified.
4. Pre-approval checks validate patch paths only.
5. Manager approves or rejects the **current patch revision**.
6. Approval applies the patch to an isolated candidate and runs tests.
7. Failed tests may produce a revised patch; the previous approval is invalid.
8. Integration is a separate authorization. This platform does not push to production.

## Start

```powershell
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000 --reload
cd frontend
npm run dev
```

Open `http://localhost:5173`. Use **New debug session**. A demo path is `data/sample_project`.

The document RAG debugger remains under **Document debugger**.

## What “complete” means here

Implemented in this repo:

- Three agents + persisted state machine
- Local authorized folders (`ALLOWED_REPO_ROOTS`; open in development)
- GitHub clone by URL + optional branch + `GITHUB_TOKEN` (not GitHub OAuth)
- Approval / reject / request revision bound to patch hash
- Isolated candidate tests after approval
- Checkpoints and restore
- Light/dark theme
- Evidence file upload

Not available without external products/credentials:

- GitHub App OAuth UI
- Live OpenAI/Ollama unless you set keys
- Browser access to arbitrary disks
- Linux cgroup hard isolation on Windows
- Automatic production git push
