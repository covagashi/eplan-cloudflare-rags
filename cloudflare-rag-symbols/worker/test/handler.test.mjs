import assert from "node:assert/strict";
import test from "node:test";
import worker from "../src/index.ts";

const vector = Array(512).fill(0);
const request = (body) => new Request("https://example.invalid/query", {
  method: "POST",
  headers: { "Content-Type": "application/json" },
  body: JSON.stringify(body),
});

test("query returns distinct candidates and review status", async () => {
  let requestedRawTopK = 0;
  const env = {
    SYMBOLS: {
      query: async (_vector, options) => {
        requestedRawTopK = options.topK;
        return { matches: [
          { id: "a", score: 0.9, metadata: { short_name: "KR2", number: "100", variant_id: "C", row: 1 } },
          { id: "b", score: 0.89, metadata: { short_name: "KR2", number: "100", variant_id: "C", row: 2 } },
          { id: "c", score: 0.8, metadata: { short_name: "KS", number: "402", variant_id: "A", row: 3 } },
          { id: "d", score: 0.7, metadata: { short_name: "KT2", number: "190", variant_id: "A", row: 4 } },
        ] };
      },
    },
  };
  const response = await worker.fetch(request({ vector, topK: 3 }), env);
  const result = await response.json();
  assert.equal(response.status, 200);
  assert.equal(requestedRawTopK, 50);
  assert.deepEqual(result.matches.map((m) => m.short_name), ["KR2", "KS", "KT2"]);
  assert.equal(result.matches[0].duplicate_count, 2);
  assert.equal(result.review_required, true);
  assert.equal(result.pool_exhausted, false);
});

test("invalid vectors and topK are rejected before querying", async () => {
  const env = { SYMBOLS: { query: () => { throw new Error("should not query"); } } };
  for (const body of [
    { vector: [...Array(511).fill(0), "0"] },
    { vector: [...Array(511).fill(0), Infinity] },
    { vector, topK: 0 },
    { vector, topK: 1.5 },
    { vector, topK: 51 },
  ]) {
    const response = await worker.fetch(request(body), env);
    assert.equal(response.status, 400);
  }
});
