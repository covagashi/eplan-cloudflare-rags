#!/usr/bin/env python3
"""Audit and index unique EPLAN symbol images into a staged Vectorize index.

The source parquet lacks a library column. Never infer a library from a
short_name, and never insert into the current live index from this script.
"""
import argparse
import hashlib
import io
import json
import os
import time
from collections import Counter
from pathlib import Path

DATASET_ID = "covaga/electrical-symbols-dataset"
DATASET_REVISION = "5fcf89e9cbbf7256fc07890a21a25ae92c5f0dfc"
MODEL_ID = "sentence-transformers/clip-ViT-B-32"
MODEL_REVISION = "327ab6726d33c0e22f920c83f2ff9e4bd38ca37f"
PARQUET_FILE = "data/train-00000-of-00001.parquet"
HARD_CASES = (("KS", "402", "A"), ("KT2", "190", "A"),
              ("X2_ST", "1363", "A"), ("DCP2M", "393", "A"),
              ("SSV", "3", "A"), ("SSV", "3", "B"),
              ("SSV", "3", "C"), ("SSV", "3", "D"))
BATCH = 500


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, "rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_source(parquet_path):
    import pyarrow.parquet as pq
    table = pq.read_table(parquet_path)
    required = {"file_name", "short_name", "number", "variant_id"}
    missing = required - set(table.column_names)
    if missing:
        raise ValueError(f"missing source columns: {sorted(missing)}")
    return table.to_pylist(), set(table.column_names)


def audit(rows, columns, source_hash):
    identities = {}
    multiplicity = Counter()
    for position, row in enumerate(rows):
        key = tuple(str(row.get(field) or "").strip()
                    for field in ("short_name", "number", "variant_id"))
        if not all(key):
            raise ValueError(f"incomplete identity at source row {position}: {key}")
        image = row.get("file_name") or {}
        image_bytes = image.get("bytes")
        if not image_bytes:
            raise ValueError(f"missing image bytes at source row {position}")
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        previous = identities.get(key)
        if previous and previous["image_sha256"] != image_hash:
            raise ValueError(f"one identity has different images: {key}")
        multiplicity[key] += 1
        if not previous:
            identities[key] = {
                "row": position,
                "image_sha256": image_hash,
                "record": row,
            }
    manifest = {
        "dataset_id": DATASET_ID,
        "dataset_revision": DATASET_REVISION,
        "parquet_sha256": source_hash,
        "model_id": MODEL_ID,
        "model_revision": MODEL_REVISION,
        "preprocessing": "PIL RGB; SentenceTransformer normalized image embedding",
        "source_rows": len(rows),
        "unique_identities": len(identities),
        "exact_duplicate_rows": len(rows) - len(identities),
        "library_column_present": "library" in columns,
        "hard_cases": {
            "/".join(key): {
                "present": key in identities,
                "source_rows": multiplicity[key],
                "image_sha256": identities[key]["image_sha256"] if key in identities else None,
            }
            for key in HARD_CASES
        },
    }
    return identities, manifest


def insert(index, vectors, account, token):
    import requests
    endpoint = (f"https://api.cloudflare.com/client/v4/accounts/{account}"
                f"/vectorize/v2/indexes/{index}/insert")
    body = "\n".join(json.dumps(v, separators=(",", ":")) for v in vectors)
    for attempt in range(4):
        response = requests.post(
            endpoint,
            headers={"Authorization": f"Bearer {token}",
                     "Content-Type": "application/x-ndjson"},
            data=body.encode("utf-8"), timeout=120,
        )
        if response.ok and response.json().get("success"):
            return
        if response.status_code in (429, 500, 502, 503) and attempt < 3:
            time.sleep(2 ** attempt)
            continue
        raise RuntimeError(
            f"insert failed {response.status_code}: {response.text[:300]}")


def write_manifest(path, manifest):
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parquet", help="local source parquet, for offline audit")
    parser.add_argument("--audit-only", action="store_true")
    parser.add_argument("--manifest", help="write audit/index manifest JSON")
    args = parser.parse_args()

    if args.parquet:
        parquet_path = args.parquet
    else:
        from huggingface_hub import hf_hub_download
        parquet_path = hf_hub_download(DATASET_ID, PARQUET_FILE,
                                       repo_type="dataset", revision=DATASET_REVISION)
    rows, columns = load_source(parquet_path)
    identities, manifest = audit(rows, columns, sha256_file(parquet_path))
    write_manifest(args.manifest, manifest)
    print(json.dumps(manifest, indent=2, sort_keys=True), flush=True)
    if args.audit_only:
        return

    index = os.environ.get("VECTORIZE_INDEX", "")
    if not index or index == "eplan-symbols":
        raise ValueError(
            "VECTORIZE_INDEX must name an existing empty candidate index; "
            "the live eplan-symbols index is protected")
    account, token = os.environ.get("CF_ACCOUNT_ID"), os.environ.get("CF_API_TOKEN")
    if not account or not token:
        raise ValueError("CF_ACCOUNT_ID and CF_API_TOKEN are required to index")
    limit = int(os.environ.get("LIMIT", "0"))
    if limit < 0:
        raise ValueError("LIMIT must be >= 0")
    selected = list(identities.items())[:limit or None]
    from PIL import Image
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(MODEL_ID, revision=MODEL_REVISION)
    manifest.update(index_name=index, expected_vectors=len(selected),
                    inserted_vectors=0, status="running")
    write_manifest(args.manifest, manifest)
    pending = []
    try:
        for start in range(0, len(selected), 32):
            batch = selected[start:start + 32]
            images = [Image.open(io.BytesIO(item["record"]["file_name"]["bytes"]))
                      .convert("RGB") for _, item in batch]
            embeddings = model.encode(images, batch_size=32,
                                      normalize_embeddings=True,
                                      show_progress_bar=False)
            for (key, item), embedding in zip(batch, embeddings):
                row = item["record"]
                vector_id = "sym_" + hashlib.sha256(
                    "\0".join(key).encode("utf-8")).hexdigest()[:24]
                pending.append({
                    "id": vector_id,
                    "values": [float(value) for value in embedding],
                    "metadata": {
                        "library": str(row.get("library") or ""),
                        "short_name": key[0],
                        "number": key[1],
                        "variant_id": key[2],
                        "description": str(row.get("description") or "")[:200],
                        "row": item["row"],
                        "image_sha256": item["image_sha256"],
                    },
                })
            if len(pending) >= BATCH:
                insert(index, pending, account, token)
                manifest["inserted_vectors"] += len(pending)
                pending.clear()
                write_manifest(args.manifest, manifest)
                print(f"{manifest['inserted_vectors']}/{len(selected)}", flush=True)
        if pending:
            insert(index, pending, account, token)
            manifest["inserted_vectors"] += len(pending)
        manifest["status"] = "completed"
    except Exception:
        manifest["status"] = "interrupted"
        raise
    finally:
        write_manifest(args.manifest, manifest)
    print(f"OK: {manifest['inserted_vectors']} unique vectors in {index}")


if __name__ == "__main__":
    main()
