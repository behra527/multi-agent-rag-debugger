import assert from "node:assert/strict";
import test from "node:test";
import { orderTotal } from "../src/orders.js";

test("orderTotal sums item prices", async () => {
  const total = await orderTotal();
  assert.equal(total, 15);
});
