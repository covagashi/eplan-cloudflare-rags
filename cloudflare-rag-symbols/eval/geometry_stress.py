#!/usr/bin/env python3
"""Stress an offline geometry probe with local image transformations."""
import argparse
import io
import json
from pathlib import Path

from PIL import Image, ImageOps

from geometry_probe import f1, read_cases, signature


def jpeg35(image):
    data = io.BytesIO()
    image.convert("RGB").save(data, format="JPEG", quality=35)
    data.seek(0)
    return Image.open(data).convert("RGB")


TRANSFORMS = {
    "original": lambda image: image,
    "half_bilinear": lambda image: image.resize(
        (max(1, image.width // 2), max(1, image.height // 2)),
        Image.Resampling.BILINEAR,
    ),
    "jpeg35": jpeg35,
    "mirror": ImageOps.mirror,
    "rotate90": lambda image: image.rotate(90, expand=True),
    "grayscale": ImageOps.grayscale,
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("templates", type=Path)
    parser.add_argument("cases", type=Path)
    parser.add_argument("--tags", nargs="+", required=True,
                        help="selected case tags from private JSONL")
    parser.add_argument("--output", type=Path,
                        help="sanitized report without image paths")
    args = parser.parse_args()
    paths = json.loads(args.templates.read_text(encoding="utf-8-sig"))
    templates = {
        kind: {name: signature(Image.open(path), kind)
               for name, path in entries.items()}
        for kind, entries in paths.items()
    }
    selected = [case for case in read_cases(args.cases)
                if case["tag"] in set(args.tags)]
    if len(selected) != len(args.tags):
        raise ValueError("some selected tags are missing or duplicated")
    rows = []
    for case in selected:
        image = Image.open(case["image_path"]).convert("RGB")
        if case.get("crop"):
            image = image.crop(tuple(case["crop"]))
        kind = case["kind"]
        for transform_name, transform in TRANSFORMS.items():
            row = {"tag": case["tag"], "transform": transform_name}
            try:
                query = signature(transform(image), kind)
                scores = {name: round(f1(query, template), 4)
                          for name, template in templates[kind].items()}
                winner = max(scores, key=scores.get)
                row.update(winner=winner,
                           correct=winner == case["expected"], scores=scores)
            except ValueError as error:
                row.update(winner=None, correct=False, error=str(error))
            rows.append(row)
    report = {
        "status": "exploratory transformations of existing local examples",
        "cases": rows,
        "correct": sum(row["correct"] for row in rows),
        "total": len(rows),
    }
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
