# Demo fixtures (not production data)

These folders are **intentional, isolated defects** for Atlas Repair. They are not live customer data.

| Folder | Language | Bug | Setup / test |
| :--- | :--- | :--- | :--- |
| `demos/01_python_import_error` | Python | Wrong import (`greeter` vs `greeting.py`) | `python -m pytest data/demos/01_python_import_error/tests -q` |
| `demos/02_fastapi_backend_failure` | Python / FastAPI | Response missing `email` → HTTP 500 | `python -m pytest data/demos/02_fastapi_backend_failure/tests -q` |
| `demos/03_js_runtime_bug` | JavaScript | Missing `await` on Promise | `node --test data/demos/03_js_runtime_bug/test/orders.test.js` |
| `demos/04_database_integration_bug` | Python / SQLite | Query uses `user_id` but column is `id` | `python -m pytest data/demos/04_database_integration_bug/tests -q` |
| `demos/05_config_env_bug` | Python | Reads `API_TOKEN` instead of `APP_TOKEN` | `python -m pytest data/demos/05_config_env_bug/tests -q` |
| `demos/06_regression_test_failure` | Python | Discount ignores `percent` | `python -m pytest data/demos/06_regression_test_failure/tests -q` |
| `sample_project` | Python | Weak login (legacy sample) | Point Atlas at `data/sample_project` |

Tests **fail on purpose** until the defect is repaired. That is the point of the fixture.

## Load in Atlas

1. Start API: `python -m uvicorn app.api.main:app --host 127.0.0.1 --port 8000`
2. Start UI: `cd frontend; npm run dev`
3. New session → **Repository** dropdown lists these demos (`GET /api/v1/repair/repositories`).
4. Paste the title/description from each `BUG_REPORT.md`.
5. Review the proposed patch. Approve only if you want tests on an isolated candidate. Integration into the demo folder is a separate authorization.

Machine-readable index: `data/demos/manifest.json`.
