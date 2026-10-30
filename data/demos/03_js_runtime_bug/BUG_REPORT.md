# Bug: orderTotal throws TypeError

Calling `orderTotal()` throws `TypeError: Cannot read properties of undefined (reading 'reduce')` because `loadOrder()` returns a Promise that is not awaited.

## Expected

`orderTotal()` resolves to `15`.

## Actual

Synchronous access of `order.items` on a Promise.

## Repro

```powershell
cd data/demos/03_js_runtime_bug
node --test test/orders.test.js
```

## Root cause

Missing `async`/`await` on `orderTotal`.

## Acceptance

`orderTotal` is async, awaits `loadOrder()`, and the Node test passes.
