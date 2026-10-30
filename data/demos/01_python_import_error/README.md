# Demo 1 — Python import error

Intentional `ModuleNotFoundError` for Atlas Repair to diagnose.

## Prerequisites

Python 3.11+ (the parent project venv is enough).

## Setup

No extra packages.

## Run

```powershell
cd data/demos/01_python_import_error
python app.py
```

Expected after fix: `Hello, Ada`.

## Test

```powershell
python -m pytest tests -q
```

Tests encode the correct behavior, so they fail until the import is repaired.
