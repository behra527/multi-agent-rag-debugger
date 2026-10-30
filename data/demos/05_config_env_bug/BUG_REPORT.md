# Bug: APP_TOKEN from .env is ignored

Startup raises `RuntimeError: APP_TOKEN is not set` even when `.env` contains `APP_TOKEN=demo-local-token`.

## Expected

`require_app_token()` returns `demo-local-token`.

## Actual

Code reads `API_TOKEN` instead of `APP_TOKEN`.

## Repro

```powershell
cd data/demos/05_config_env_bug
python -m pytest tests -q
```

## Root cause

Wrong environment variable name.

## Acceptance

Read `APP_TOKEN`. No real secrets in this demo.
