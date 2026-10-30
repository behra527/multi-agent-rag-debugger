# Can this go live?

## Honest answer

**Not as a public internet SaaS yet.** It **is** ready for a private demo, internal team, or localhost launch.

| Check | Status |
| :--- | :--- |
| Core workflow (report → diagnose → approve → test) | Yes |
| UI usable as a product | Yes, after this polish |
| Open to the public internet | No — auth is optional by default |
| Multi-tenant SaaS billing/GitHub App | No |
| Server can read customer laptops | No — only paths the API host can see |

## Private live (internal)

1. Set `AUTH_MODE=required`
2. Set `APP_ENV=production` and `DEBUG=false`
3. Use Postgres (`docker compose`) not a shared SQLite file
4. Set a real `LLM_PROVIDER` + API key (otherwise mock answers)
5. Set `ALLOWED_REPO_ROOTS` to the folders the server may read
6. Put HTTPS in front (nginx / cloud load balancer)
7. Do **not** expose port 5432 publicly

```powershell
.\.venv\Scripts\python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000
cd frontend
npm run dev
```

Or `docker compose up --build`.

Public customers still cannot select `D:\...` on their PC. They must connect a repo the **server** can clone (`GITHUB_TOKEN` + HTTPS URL) or that is mounted on the server.
