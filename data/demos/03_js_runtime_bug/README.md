# Demo 3 — JavaScript runtime bug

Missing `await` on an async data load.

## Prerequisites

Node.js 20+.

## Run / test

```powershell
cd data/demos/03_js_runtime_bug
node --test test/orders.test.js
```

The test fails until `orderTotal` awaits `loadOrder()`.
