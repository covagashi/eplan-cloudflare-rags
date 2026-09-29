# Visual symbol RAG improvement roadmap

Status: implementation in progress, 2026-09-29. The live service has not been re-indexed or deployed.

## Verified source audit (2026-09-29)

The pinned source parquet contains 33,502 rows and **9,445 distinct `(short_name, number, variant_id)` identities**. All 24,057 excess rows are byte-identical copies within their identities; no identity has conflicting image bytes. KS/402/A, KT2/190/A, and X2_ST/1363/A each occur eight times with one image hash. DCP2M/393/A occurs once. The source has **no library column**, so source metadata cannot prove the full EPLAN library identity. The deployed Vectorize inventory remains unverified because account credentials are unavailable locally.

The authorized live baseline on two high-resolution EPLAN renders yielded top-1 exact 0/2 and distinct recall-at-five 0/2. The public endpoint returned 20 raw rows but only four distinct identities for KS and three for KT2 (82.5% mean duplication); it did not return a review-required field. See [baseline metrics](eval/baseline-live-2026-09-29.json). Deduplication alone cannot establish exact visual recognition: local CLIP cosine ranked the wrong source template above the correct one for KS (0.8802 versus 0.8672).

An offline geometry probe now isolates the KS/KT2 relay mark or the X2_ST/DCP2M plug component and rejects multi-symbol inputs. It chose the intended symbol or abstained correctly in 12/12 exploratory local cases, including two KR2 negatives, but only 18/24 transformed checks. Half-size DCP2M, mirrored relays, and 90-degree rotations expose unresolved failure modes. See [probe](eval/geometry-probe-2026-09-29.json) and [stress results](eval/geometry-stress-2026-09-29.json). These examples are related and do not constitute a held-out release benchmark.

Implemented: deterministic source audit and manifest, staged unique-identity indexer, Worker distinct-result grouping and review-required status, local benchmark harness, and MCP client TLS/system-trust plus cautious candidate text. Worker and audit tests pass. The visual hard-pair and held-out release gates remain open; no candidate index was created or promoted.
## Evidence and scope

The original deployed pipeline embedded each dataset row with CLIP ViT-B/32 and returned raw nearest rows. The new candidate indexer collapses identical source rows, and the updated Worker groups raw neighbors by catalog code. The MCP client still uses the same CLIP model and normalized embeddings, so the measured fine-geometry failure remains a separate issue.

| Observation | Verified ground truth | Result |
| --- | --- | --- |
| Two near-identical relay symbols | IEC_symbol / 402 / KS, variant A; IEC_symbol / 190 / KT2, variant A | Neither isolated, label-free crop returned its own code among the first 20 raw neighbors. |
| Original KS screenshot | IEC_symbol / 402 / KS | topK=3 returned KR2 variant C three times at similarity 0.657; a visually similar but incorrect KT2 was later placed. |
| Plug-related screenshot | IEC_symbol / 1363 / X2_ST | The visually similar SPECIAL / DCP2M was selected. |

The two isolated KS and KT2 screenshot crops have cosine similarity **0.9909 between their CLIP embeddings**. EPLAN exports at higher resolution still have similarity **0.9907**, with neither exact code in the first 20 raw neighbors. Text in the initial screenshot and image resolution can affect ranking, but they do not explain this failure alone. A nearest-neighbor score is not a calibrated probability of correctness.

The Python MCP client also hit a TLS certificate verification error against symbols.covaga.xyz, while a Windows REST client reached the service. This transport failure is separate from relevance quality.

**Unresolved:** the public query endpoint cannot prove whether KS, KT2, and X2_ST are present and correctly labeled in the deployed index. Audit index coverage before attributing every miss to the embedding model.

## Product goal and release gates

Return an exact identity only when the evidence supports its library, catalog number, short name, and variant. Otherwise return distinct candidates marked for review. A visually similar symbol must never be presented as an exact match or placed automatically from one raw similarity score.

Before replacing the production service:

1. KS and KT2 must be distinguished as top-1 exact codes on clean EPLAN renders and held-out screenshots. Add X2_ST versus DCP2M as a mandatory hard pair after recording the exact source variant.
2. topK=3 must mean three distinct symbol identities when the index contains at least three, not three rows with the same code and variant.
3. The held-out benchmark must improve top-1 exact accuracy without reducing recall at five distinct identities. Report metrics by library, variant, and image source.
4. Mandatory hard pairs must never produce a confident wrong answer. Ambiguous images must return a review-required result.
5. The MCP client must reach the public endpoint with TLS verification enabled.

## P0 — Ground truth, coverage, and a reproducible benchmark

- Build a versioned evaluation set under cloudflare-rag-symbols/eval. Record the EPLAN library, number, short name, variant, source image, crop coordinates, and orientation. Include clean renders, screenshots with and without labels, different scales, and images containing multiple symbols. Keep training and held-out examples separate by identity or hard pair. Do not commit user screenshots without permission.
- Start with KS/KT2 and X2_ST/DCP2M. Add further hard negatives whose tiny strokes change electrical meaning. Use the live EPLAN catalog and rendered glyph as ground truth rather than a text description alone.
- Audit the source dataset and deployed index separately. Verify the expected identities, inspect their actual source images, count duplicate identities, and check corrupted or truncated metadata. Publish an index manifest with source revision, image hashes, model revision, preprocessing revision, expected row count, completed batch count, and index name.
- Add a deterministic offline benchmark for the current pipeline: raw and distinct neighbors, exact top-1 accuracy, distinct-code recall at 3 and 5, hard-pair confusion, duplicate rate, and review-required rate. Save baseline results before changing retrieval.

**Exit gate:** the hard-pair source rows and deployed coverage are verified, and the baseline can be reproduced. If a symbol is missing or mislabeled, fix the data and re-index before model work.

## P1 — Make current retrieval usable and safe

- Add query-image segmentation and symbol-only crops in the MCP client. Preserve aspect ratio with padding and normalize foreground color. Keep device tags and pin text outside the visual crop. For a multi-symbol image, return separate regions or ask which region to search.
- In the Worker, fetch enough raw neighbors to produce the requested number of distinct identities, then group by library, number, short name, and variant. Include library in indexed metadata and expose raw vector IDs/rows in a diagnostic response. Keep the existing query contract compatible while documenting what topK counts.
- Replace the instruction to use the first short name unconditionally. Calibrate a review-required rule from the held-out benchmark using score, score gap, and agreement across alternative crops. Do not treat 0.657 as 65.7% confidence.
- Fix the MCP client's certificate chain with a trusted CA bundle or Windows trust-store integration. Keep certificate verification enabled and add an HTTPS smoke check.

**Exit gate:** topK=3 returns distinct identities; multiple symbols and labels no longer silently contaminate one query; weak matches are not asserted as exact; the MCP client passes TLS verification.

## P2 — Recover the small geometry CLIP loses

- Retain CLIP as a candidate generator only if the exact code reaches a useful candidate pool. Measure this explicitly; the 0.99 KS/KT2 query-embedding similarity is a concrete warning for this pair.
- Create a versioned gallery of canonical EPLAN renders for each library, number, and variant. Re-rank candidates with geometry-sensitive comparison after alignment: binarized strokes, contours, endpoints, junctions, and the interior mark. Test rotation and mirroring as explicit variants.
- If that re-ranker cannot pass the hard-pair gate, fine-tune a symbol-specific metric model with hard negatives such as KS versus KT2. Keep training examples out of the held-out test and version the model, preprocessing, and index together.
- Calibrate the final decision rule on held-out images. Return rendered previews with alternatives when an exact identity is not justified.

**Exit gate:** hard pairs pass on clean and screenshot fixtures, and held-out top-1 accuracy improves without a distinct-code recall-at-5 regression.

## P3 — Stage, monitor, and roll back

- Build a new Vectorize index rather than overwriting the live one. Run the benchmark against the candidate index, then shadow-query representative images without changing public answers.
- Include model, preprocessing, and index versions in responses. Monitor distinct-code recall, duplicate results, ambiguous responses, confident wrong matches, TLS errors, and latency. Do not retain user images unless authorized.
- Promote through the existing manual workflows only after all gates pass. Keep the previous Worker/index configuration and a documented rollback. Re-run the hard-pair fixtures immediately after deployment.

## Implementation map

| File or repository | Planned responsibility |
| --- | --- |
| [index_symbols.py](index_symbols.py) | Coverage audit, canonical identity with library, image hashes, index manifest, duplicate accounting. |
| [worker/src/index.ts](worker/src/index.ts) | Distinct-code results, diagnostic raw IDs, version fields, and review-required status. |
| [index-symbols workflow](../.github/workflows/index-symbols.yml) | Audit and benchmark gates, staged index build, controlled promotion. |
| [EPLAN MCP symbol-search extension](https://github.com/covagashi/eplan-rag-mcp/blob/main/eplan-p8-mcp-server/extensions/symbol_search.py) | Segmentation, TLS trust, distinct candidate display, and safe handling of uncertainty. This change belongs in the separate eplan-rag-mcp repository. |

Implement P0 before choosing a replacement model. The measured embedding collapse explains why a present row can be ranked badly; only the coverage audit can establish whether a source or indexing fault also exists.
