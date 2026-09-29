import assert from "node:assert/strict";
import test from "node:test";
import { distinctSymbols } from "../src/rank.ts";

const row = (id, score, short_name, number, variant_id, sourceRow) => ({
  id, score, metadata: { short_name, number, variant_id, row: sourceRow },
});

test("topK counts distinct identities, preserving the highest score", () => {
  const ranked = distinctSymbols([
    row("a", 0.9, "KR2", "100", "C", 1),
    row("b", 0.89, "KR2", "100", "C", 2),
    row("c", 0.88, "KR2", "100", "C", 3),
    row("d", 0.8, "KS", "402", "A", 4),
    row("e", 0.7, "KT2", "190", "A", 5),
  ], 3);
  assert.deepEqual(ranked.map((item) => item.short_name), ["KR2", "KS", "KT2"]);
  assert.equal(ranked[0].duplicate_count, 3);
  assert.deepEqual(ranked[0].source_rows, [1, 2, 3]);
});

test("variant and library are part of identity", () => {
  const ranked = distinctSymbols([
    { ...row("a", 0.9, "KS", "402", "A", 1), metadata: {
      ...row("a", 0.9, "KS", "402", "A", 1).metadata, library: "IEC_symbol" } },
    { ...row("b", 0.8, "KS", "402", "B", 2), metadata: {
      ...row("b", 0.8, "KS", "402", "B", 2).metadata, library: "IEC_symbol" } },
    { ...row("c", 0.7, "KS", "402", "A", 3), metadata: {
      ...row("c", 0.7, "KS", "402", "A", 3).metadata, library: "OTHER" } },
  ], 3);
  assert.equal(ranked.length, 3);
});
