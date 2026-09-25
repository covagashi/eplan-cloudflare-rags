#!/usr/bin/env python3
"""Index covaga/electrical-symbols-dataset into Cloudflare Vectorize.

Computes CLIP ViT-B/32 image embeddings (512-dim, L2-normalized -> cosine)
for every EPLAN symbol image and inserts vectors + metadata into the
`eplan-symbols` Vectorize index via the REST API.

Env:  CF_ACCOUNT_ID, CF_API_TOKEN, VECTORIZE_INDEX (default eplan-symbols)
      DATASET_ID (default covaga/electrical-symbols-dataset), LIMIT (0=all)
"""

import io
import os
import sys
import time

import requests
from datasets import load_dataset
from PIL import Image

ACCOUNT = os.environ["CF_ACCOUNT_ID"]
TOKEN = os.environ["CF_API_TOKEN"]
INDEX = os.environ.get("VECTORIZE_INDEX", "eplan-symbols")
DATASET_ID = os.environ.get("DATASET_ID", "covaga/electrical-symbols-dataset")
LIMIT = int(os.environ.get("LIMIT", "0"))

API = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT}/vectorize/v2/indexes/{INDEX}"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}
BATCH = 500  # vectors per insert call


def to_pil(x):
    if isinstance(x, Image.Image):
        return x.convert("RGB")
    if x.get("bytes"):
        return Image.open(io.BytesIO(x["bytes"])).convert("RGB")
    return Image.open(x["path"]).convert("RGB")


def insert(vectors):
    """vectors: list of dicts {id, values, metadata} -> NDJSON insert."""
    body = "\n".join(__import__("json").dumps(v) for v in vectors)
    for attempt in range(4):
        r = requests.post(f"{API}/insert", headers={
            **HEADERS, "Content-Type": "application/x-ndjson"},
            data=body.encode(), timeout=120)
        if r.ok and r.json().get("success"):
            return
        if r.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(f"insert failed {r.status_code}: {r.text[:300]}")


def main():
    from sentence_transformers import SentenceTransformer

    model = SentenceTransformer("clip-ViT-B-32")
    ds = load_dataset(DATASET_ID, split="train")
    if LIMIT:
        ds = ds.select(range(LIMIT))
    print(f"{len(ds)} simbolos a indexar en '{INDEX}'")

    pending, done = [], 0
    for i in range(0, len(ds), 32):  # encode in chunks of 32 images
        rows = ds[i:i + 32]
        imgs = [to_pil(im) for im in rows["file_name"]]
        embs = model.encode(imgs, batch_size=32, normalize_embeddings=True,
                            show_progress_bar=False)
        for j, emb in enumerate(embs):
            pending.append({
                "id": f"{rows['short_name'][j]}__{i + j}",
                "values": [float(x) for x in emb],
                "metadata": {
                    "short_name": str(rows["short_name"][j] or ""),
                    "number": str(rows["number"][j] or ""),
                    "description": str(rows["description"][j] or "")[:200],
                    "variant_id": str(rows["variant_id"][j] or ""),
                    "row": i + j,
                },
            })
        if len(pending) >= BATCH:
            insert(pending)
            done += len(pending)
            pending.clear()
            print(f"{done}/{len(ds)}", flush=True)
    if pending:
        insert(pending)
        done += len(pending)
    print(f"OK: {done} vectores insertados en {INDEX}")


if __name__ == "__main__":
    sys.exit(main())
