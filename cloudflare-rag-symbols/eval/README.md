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

## Offline geometry probe

`geometry_probe.py` compares three narrow families with local templates: the
first chamber of rectangular relay symbols (KS/KT2), the largest connected
component of plug symbols (X2_ST/DCP2M), and the complete foreground glyph
for a simple symbol such as SSV. It accepts blue or dark strokes,
removes text outside the selected geometry, and rejects images containing
multiple substantial shapes. It needs `numpy`, `scipy`, and `pillow`.

Keep private files outside Git. The templates JSON maps family and identity
to local paths, for example `{"relay":{"KS":"C:/local/ks.png","KT2":"C:/local/kt2.png"}}`.
The cases JSONL has `tag`, `image_path`, `kind`, `expected`, and optional
`crop: [left, top, right, bottom]`. Run:

```powershell
python cloudflare-rag-symbols/eval/geometry_probe.py templates.json cases.jsonl --output probe.json
python cloudflare-rag-symbols/eval/geometry_stress.py templates.json cases.jsonl --tags ks-highres kt2-highres x2-user dcp2m-placed --output stress.json
```

The [exploratory probe](geometry-probe-2026-09-29.json) selected the intended symbol or abstained correctly in 12/12 local cases
(10 positives and two KR2 negatives); some are related crops of the same
screenshot, and
the source templates and queries share identities. The [stress report](geometry-stress-2026-09-29.json)
selected 18/24 transformed examples correctly: original 4/4, JPEG 4/4,
grayscale 4/4, half size 3/4, mirror 2/4, and 90-degree rotation 1/4.
The low-resolution DCP2M example was misclassified. Rotation and reflection
are orientation changes and must be handled as explicit variants. These
scores are **not** calibrated confidence and do not meet the held-out release
gate. No geometry code is wired into the public Worker or automatic placement.

## SSV follow-up

The [SSV local audit](ssv-local-2026-09-29.json) and
[unlabeled geometry result](ssv-geometry-2026-09-29.json) record the user-provided
`IEC_symbol / 3 / SSV` image without storing it. The source has A-D, eight
identical rows per variant, while the live EPLAN catalog exposes variant
numbers 0-7 and 16. Geometry favors the source A image (F1 0.6891); CLIP
slightly favors C (0.8570 versus A 0.8541). The EPLAN variant is therefore
not ground truth yet. The public RAG query was blocked by automatic approval
review for this new image embedding and has not been retried through REST.
