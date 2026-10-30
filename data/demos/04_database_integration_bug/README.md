# Demo 4 — Database integration bug

SQLite query uses a column that does not exist.

## Prerequisites

Python 3.11+ (stdlib `sqlite3`).

## Test

```powershell
cd data/demos/04_database_integration_bug
python -m pytest tests -q
```

A local `demo.sqlite` file is created during tests and can be deleted.
