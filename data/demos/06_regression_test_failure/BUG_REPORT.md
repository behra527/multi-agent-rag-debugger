# Bug: discount tests fail after a pricing change

`apply_discount` ignores the `percent` argument and always applies 20%. Existing tests still require 10% by default.

## Expected

`apply_discount(100, 10) == 90` and `apply_discount(200, 25) == 150`.

## Actual

Both calls return 20% off (80.0 and 160.0).

## Repro

```powershell
cd data/demos/06_regression_test_failure
python -m pytest tests -q
```

## Root cause

Hard-coded `20.0` instead of using `percent`.

## Acceptance

Use the `percent` parameter. Both tests pass.
