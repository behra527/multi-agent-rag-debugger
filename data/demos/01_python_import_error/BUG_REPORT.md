# Bug: ModuleNotFoundError for greeter

The CLI cannot start. Python raises `ModuleNotFoundError: No module named 'greeter'`.

## Expected

`python app.py` prints `Hello, Ada`. `pytest tests` passes.

## Actual

Import fails because `app.py` imports `greeter` while the implementation lives in `greeting.py`.

## Repro

```powershell
cd data/demos/01_python_import_error
python app.py
python -m pytest tests -q
```

## Root cause

Incorrect import name. There is no `greeter.py` package.

## Acceptance

`from greeting import greet` (or rename the file) and both the CLI and tests succeed.
