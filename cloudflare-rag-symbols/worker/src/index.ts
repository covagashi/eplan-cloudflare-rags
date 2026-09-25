// Public visual-RAG endpoint for EPLAN electrical symbols.
//
// POST /query  { "vector": number[512], "topK"?: number }
//   -> [{ id, score, metadata: { short_name, number, description, variant_id } }]
//
// GET /health -> { ok: true }
//
// The caller embeds the symbol image with CLIP ViT-B/32 (L2-normalized,
// cosine metric) and posts the vector; we return the nearest EPLAN symbols.

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
      return json({ ok: true, index: "eplan-symbols" });
    }

    if (request.method === "POST" && url.pathname === "/query") {
      let body: { vector?: number[]; topK?: number };
      try {
        body = await request.json();
      } catch {
        return json({ error: "invalid JSON body" }, 400);
      }
      if (!Array.isArray(body.vector) || body.vector.length !== 512) {
        return json({ error: "vector must be a number[512] CLIP embedding" }, 400);
      }
      const topK = Math.min(Math.max(body.topK ?? 5, 1), 20);
      const res = await env.SYMBOLS.query(body.vector, {
        topK,
        returnMetadata: "all",
      });
      return json({
        matches: res.matches.map((m) => ({
          score: m.score,
          short_name: m.metadata?.short_name,
          number: m.metadata?.number,
          description: m.metadata?.description,
          variant_id: m.metadata?.variant_id,
        })),
      });
    }

    return json(
      { error: "not found", usage: "POST /query {vector: number[512], topK?: n}" },
      404,
    );
  },
} satisfies ExportedHandler<Env>;
