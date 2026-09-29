// POST /query {vector: number[512], topK?: 1..20, diagnostics?: boolean}
// topK counts distinct catalog identities, not source rows.
// Similarity is uncalibrated: all matches require visual/catalog review.

import { distinctSymbols, type SymbolMatch } from "./rank.ts";

export interface Env {
  SYMBOLS: VectorizeIndex;
}

const CORS = {
  "Access-Control-Allow-Origin": "*",
  "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
  "Access-Control-Allow-Headers": "Content-Type",
};

function json(data: unknown, status = 200): Response {
  return new Response(JSON.stringify(data), {
    status,
    headers: { "Content-Type": "application/json", ...CORS },
  });
}

export default {
  async fetch(request: Request, env: Env): Promise<Response> {
    const url = new URL(request.url);
    if (request.method === "OPTIONS") {
      return new Response(null, { status: 204, headers: CORS });
    }
    if (request.method === "GET" && url.pathname === "/health") {
      return json({ ok: true, index: "eplan-symbols", result_contract: "distinct-v1" });
    }
    if (request.method === "POST" && url.pathname === "/query") {
      let body: unknown;
      try {
        body = await request.json();
      } catch {
        return json({ error: "invalid JSON body" }, 400);
      }
      if (!body || typeof body !== "object" || Array.isArray(body)) {
        return json({ error: "body must be an object" }, 400);
      }
      const query = body as Record<string, unknown>;
      const vector = query.vector;
      if (!Array.isArray(vector) || vector.length !== 512 ||
          !vector.every((value) => typeof value === "number" && Number.isFinite(value))) {
        return json({ error: "vector must be 512 finite numbers" }, 400);
      }
      const topK = query.topK === undefined ? 5 : query.topK;
      if (typeof topK !== "number" || !Number.isInteger(topK) || topK < 1 || topK > 20) {
        return json({ error: "topK must be an integer from 1 to 20" }, 400);
      }
      if (query.diagnostics !== undefined && typeof query.diagnostics !== "boolean") {
        return json({ error: "diagnostics must be a boolean" }, 400);
      }
      try {
        // 50 is the Vectorize V2 maximum when all metadata is returned.
        // The current raw index contains many exact copies of the same image.
        const result = await env.SYMBOLS.query(vector, {
          topK: 50,
          returnMetadata: "all",
        });
        const raw = result.matches as SymbolMatch[];
        const matches = distinctSymbols(raw, topK);
        return json({
          matches,
          review_required: true,
          review_reason: matches.length ? "similarity_not_calibrated" : "no_matches",
          requested_distinct: topK,
          returned_distinct: matches.length,
          raw_neighbors_examined: raw.length,
          pool_exhausted: matches.length < topK,
          ...(query.diagnostics ? {
            raw_matches: raw.map((match) => ({
              id: match.id,
              score: match.score,
              metadata: match.metadata,
            })),
          } : {}),
        });
      } catch {
        return json({ error: "symbol index query failed" }, 503);
      }
    }
    return json(
      { error: "not found", usage: "POST /query {vector: number[512], topK?: 1..20}" },
      404,
    );
  },
} satisfies ExportedHandler<Env>;
