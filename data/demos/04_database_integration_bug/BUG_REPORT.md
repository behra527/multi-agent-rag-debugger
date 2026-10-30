# Bug: looking up a user raises sqlite3.OperationalError

`get_user_name(1)` fails with `no such column: user_id`. The table defines `id`.

## Expected

`get_user_name(1)` returns `"Ada"`.

## Actual

Query uses `WHERE user_id = ?` against column `id`.

## Repro

```powershell
cd data/demos/04_database_integration_bug
python -m pytest tests -q
```

## Root cause

Wrong column name in the SELECT.

## Acceptance

Query uses `id`. Tests pass. `demo.sqlite` is a local fixture, not production data.
