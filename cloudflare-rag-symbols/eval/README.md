# Symbol retrieval evaluation

The source audit is deterministic and runs before any Cloudflare indexing:

```powershell
python cloudflare-rag-symbols/index_symbols.py --audit-only --manifest cloudflare-rag-symbols/eval/source-manifest.json
```

The source revision and CLIP revision are pinned in the indexer. The audit
rejects one catalog identity with conflicting image bytes. It computes image
hashes, counts exact duplicate rows, and reports the mandatory hard cases.
The current source has no library column, so the audit cannot establish a
complete EPLAN identity or prove what is deployed in Vectorize.

The Worker test checks that a query returning three copies of one source
identity still returns distinct alternatives. Run it with Node 22 or later:

```powershell
cd cloudflare-rag-symbols/worker
npm.cmd test
```

The source audit is **not** the held-out visual benchmark. Before promotion,
add authorized screenshots and canonical EPLAN renders for KS/KT2 and
X2_ST/DCP2M, measure exact top-1 and distinct recall at five, and verify the
candidate index separately. The public response always requires review until
that benchmark calibrates a reliable exact-match decision.

Indexing requires an existing empty Vectorize V2 candidate index with 512
dimensions and cosine distance. Set VECTORIZE_INDEX to its name, plus
CF_ACCOUNT_ID and CF_API_TOKEN. The script rejects the live
`eplan-symbols` index. Reusing a nonempty candidate index can leave stale
vectors; use a fresh index name for each complete run.

A private fixture file can drive the benchmark:

```json
{"image_path":"C:/local/ks-render.png","short_name":"KS","number":"402","variant_id":"A","library":"IEC_symbol"}
```

Run `python cloudflare-rag-symbols/eval/benchmark.py fixtures.jsonl --endpoint https://symbols.covaga.xyz`. This sends a 512-number CLIP embedding derived from each local image to the endpoint; it never sends the image bytes or commits fixtures. Only run against an endpoint approved for those images. The user explicitly authorized sending the two KS/KT2 embeddings on 2026-09-29. The sanitized results are in `baseline-live-2026-09-29.json`: top-1 exact 0/2, distinct recall at five 0/2, and mean duplicate rate 82.5%. The public Worker did not report `review_required`.