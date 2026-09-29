#!/usr/bin/env python3
"""Measure visual retrieval with private, local EPLAN fixtures.

Input JSONL: {"image_path":"...","short_name":"KS","number":"402",
              "variant_id":"A","library":"IEC_symbol"}
Paths are never sent to the server; only CLIP vectors are sent.
"""
import argparse
import json
from pathlib import Path

import requests


def identity(match):
    return (str(match.get("short_name") or ""),
            str(match.get("number") or ""),
            str(match.get("variant_id") or ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fixtures", type=Path)
    parser.add_argument("--endpoint", default="https://symbols.covaga.xyz")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    from PIL import Image
    from sentence_transformers import SentenceTransformer
    model = SentenceTransformer(
        "sentence-transformers/clip-ViT-B-32",
        revision="327ab6726d33c0e22f920c83f2ff9e4bd38ca37f",
    )
    session = requests.Session()
    try:
        import ssl
        import truststore
        from requests.adapters import HTTPAdapter

        class SystemTrustAdapter(HTTPAdapter):
            def init_poolmanager(self, *adapter_args, **adapter_kwargs):
                adapter_kwargs["ssl_context"] = truststore.SSLContext(
                    ssl.PROTOCOL_TLS_CLIENT)
                return super().init_poolmanager(*adapter_args, **adapter_kwargs)

        session.mount("https://", SystemTrustAdapter())
    except ImportError:
        pass

    cases = []
    for line in args.fixtures.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        fixture = json.loads(line)
        image = Image.open(fixture["image_path"]).convert("RGB")
        vector = model.encode(image, normalize_embeddings=True).tolist()
        response = session.post(
            args.endpoint.rstrip("/") + "/query",
            json={"vector": vector, "topK": 20},
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()
        raw = data.get("matches") or []
        distinct = []
        seen = set()
        for match in raw:
            key = identity(match)
            if key not in seen:
                distinct.append(key)
                seen.add(key)
        expected = (str(fixture["short_name"]), str(fixture["number"]),
                    str(fixture["variant_id"]))
        cases.append({
            "image_path": fixture["image_path"],
            "expected": expected,
            "top1_exact": bool(distinct and distinct[0] == expected),
            "recall_at_5_distinct": expected in distinct[:5],
            "raw_neighbors": len(raw),
            "distinct_neighbors": len(distinct),
            "review_required": data.get("review_required"),
        })
    if not cases:
        raise ValueError("fixture file is empty")
    result = {
        "endpoint": args.endpoint,
        "cases": cases,
        "top1_exact_accuracy": sum(c["top1_exact"] for c in cases) / len(cases),
        "recall_at_5_distinct": sum(c["recall_at_5_distinct"] for c in cases) / len(cases),
        "mean_duplicate_rate": sum(
            1 - c["distinct_neighbors"] / max(c["raw_neighbors"], 1)
            for c in cases) / len(cases),
        "review_required_rate": sum(
            c["review_required"] is True for c in cases) / len(cases),
    }
    output = json.dumps(result, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
