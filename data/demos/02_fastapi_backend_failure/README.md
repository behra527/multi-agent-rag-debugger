# Demo 2 — FastAPI backend failure

Broken response model for Atlas Repair.

## Prerequisites

FastAPI and pytest from the parent venv (`pip install -r requirements.txt` at repo root).

## Run

```powershell
cd data/demos/02_fastapi_backend_failure
python -m uvicorn main:app --host 127.0.0.1 --port 8010
```

## Test

```powershell
python -m pytest tests -q
```

Tests fail until `/users/{id}` includes `email`.
