#!/usr/bin/env python3
"""Offline geometry probe for local symbol renders and screenshots.

This evaluates three narrow shape families; it does not identify arbitrary
symbols or authorize automatic placement. Image paths stay local.
"""
import argparse
import json
from pathlib import Path

import numpy as np
from PIL import Image
from scipy.ndimage import label


def stroke_mask(image):
    rgb = np.asarray(image.convert("RGB")).astype(np.int16)
    blue = ((rgb[:, :, 2] > 120)
            & (rgb[:, :, 2] - rgb[:, :, 0] > 80)
            & (rgb[:, :, 2] - rgb[:, :, 1] > 80))
    dark = rgb.max(axis=2) < 150
    return blue | dark


def normalized(mask, size):
    if not mask.any():
        raise ValueError("no symbol strokes found")
    image = Image.fromarray((mask * 255).astype("uint8"))
    return np.asarray(image.resize(size, Image.Resampling.NEAREST)) > 0


def relay_interior(mask):
    rows = mask.sum(axis=1)
    if rows.max() < 10:
        raise ValueError("no long rectangular frame")
    horizontal = np.flatnonzero(rows >= 0.8 * rows.max())
    top, bottom = int(horizontal.min()), int(horizontal.max())
    if bottom - top < 8:
        raise ValueError("rectangular frame is too short")
    columns = mask[top:bottom + 1].sum(axis=0)
    vertical = np.flatnonzero(columns >= 0.7 * (bottom - top + 1))
    groups = []
    for x in vertical:
        if not groups or x > groups[-1][-1] + 1:
            groups.append([int(x)])
        else:
            groups[-1].append(int(x))
    if len(groups) < 3:
        raise ValueError("rectangle and first divider not found")
    if len(groups) != 3:
        raise ValueError("multiple or unsupported rectangular frames")
    left, divider = groups[:2]
    width = divider[0] - left[-1]
    if width < 8:
        raise ValueError("first chamber is too narrow")
    xpad = max(1, round(width * 0.06))
    ypad = max(1, round((bottom - top) * 0.06))
    interior = mask[top + ypad:bottom - ypad + 1,
                    left[-1] + xpad:divider[0] - xpad]
    if not interior.any():
        raise ValueError("no mark inside first chamber")
    return normalized(interior, (64, 64))


def largest_component(mask):
    components, count = label(mask, structure=np.ones((3, 3), dtype=int))
    if not count:
        raise ValueError("no symbol component found")
    sizes = np.bincount(components.ravel())
    sizes[0] = 0
    largest = int(sizes.argmax())
    second = int(np.partition(sizes, -2)[-2]) if len(sizes) > 2 else 0
    if second >= 0.5 * sizes[largest]:
        raise ValueError("multiple substantial components")
    ys, xs = np.where(components == largest)
    component = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return normalized(component, (64, 128))


def whole_glyph(mask):
    components, count = label(mask, structure=np.ones((3, 3), dtype=int))
    if not count:
        raise ValueError("no symbol strokes found")
    sizes = np.bincount(components.ravel())
    sizes[0] = 0
    if len(sizes) > 2 and np.partition(sizes, -2)[-2] >= 0.5 * sizes.max():
        raise ValueError("multiple substantial components")
    ys, xs = np.where(mask)
    crop = mask[ys.min():ys.max() + 1, xs.min():xs.max() + 1]
    return normalized(crop, (64, 96))


def signature(image, kind):
    mask = stroke_mask(image)
    if kind == "relay":
        return relay_interior(mask)
    if kind == "plug":
        return largest_component(mask)
    if kind == "simple":
        return whole_glyph(mask)
    raise ValueError(f"unsupported shape family: {kind}")


def f1(a, b):
    intersection = np.count_nonzero(a & b)
    denominator = np.count_nonzero(a) + np.count_nonzero(b)
    return 2 * intersection / denominator if denominator else 0.0


def read_cases(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("templates", type=Path,
                        help='JSON: {"relay":{"KS":"local/path.png",...},"plug":{...}}')
    parser.add_argument("cases", type=Path,
                        help="JSONL with tag, image_path, kind, expected, optional crop")
    parser.add_argument("--output", type=Path,
                        help="sanitized JSON report with no image paths")
    args = parser.parse_args()

    template_paths = json.loads(args.templates.read_text(encoding="utf-8-sig"))
    templates = {
        kind: {name: signature(Image.open(path), kind)
               for name, path in entries.items()}
        for kind, entries in template_paths.items()
    }
    results = []
    for case in read_cases(args.cases):
        image = Image.open(case["image_path"])
        if case.get("crop"):
            image = image.crop(tuple(case["crop"]))
        kind = case["kind"]
        expected = case.get("expected")
        result = {"tag": case["tag"], "kind": kind,
                  "expected": expected}
        try:
            query = signature(image, kind)
            scores = {name: round(f1(query, template), 4)
                      for name, template in sorted(templates[kind].items())}
            winner = max(scores, key=scores.get)
            result.update(winner=winner,
                          correct=(winner == expected if expected is not None else None),
                          scores=scores)
        except ValueError as error:
            result.update(winner="ABSTAIN",
                          correct=(expected == "ABSTAIN" if expected is not None else None),
                          reason=str(error))
        results.append(result)
    if not results:
        raise ValueError("no cases")
    report = {
        "method": "foreground strokes; relay interior, plug component, or simple whole-glyph F1",
        "status": "exploratory; templates and queries share symbol identities",
        "cases": results,
        "correct": sum(row["correct"] is True for row in results),
        "total": sum(row["correct"] is not None for row in results),
        "unlabeled": sum(row["correct"] is None for row in results),
    }
    output = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.write_text(output, encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
