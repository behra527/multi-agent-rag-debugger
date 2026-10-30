# Bug: GET /users/1 returns HTTP 500

Requesting a known user does not return JSON. The server raises a response validation error.

## Expected

`GET /users/1` returns HTTP 200 with `id`, `name`, and `email`.

## Actual

HTTP 500 because the handler omits `email` while `response_model=User` requires it.

## Repro

```powershell
cd data/demos/02_fastapi_backend_failure
python -m uvicorn main:app --host 127.0.0.1 --port 8010
# other terminal:
curl http://127.0.0.1:8010/users/1
python -m pytest tests -q
```

## Root cause

Incomplete response dict vs Pydantic `User` model.

## Acceptance

Handler returns the stored email. Tests pass with status 200.
