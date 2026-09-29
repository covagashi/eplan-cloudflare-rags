import sys
import unittest
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).resolve().parent))
from geometry_probe import signature


def relay(color):
    image = Image.new("RGB", (140, 95), "white")
    draw = ImageDraw.Draw(image)
    draw.rectangle((20, 20, 120, 70), outline=color, width=2)
    draw.line((55, 20, 55, 70), fill=color, width=2)
    draw.line((29, 55, 38, 55, 38, 45, 47, 45), fill=color, width=2)
    return image


class GeometryProbeTests(unittest.TestCase):
    def test_gray_and_blue_relay_have_same_signature(self):
        blue = signature(relay((0, 0, 255)), "relay")
        gray = signature(relay((30, 30, 30)), "relay")
        self.assertTrue(np.array_equal(blue, gray))

    def test_two_relays_require_separate_crops(self):
        one = relay((0, 0, 255))
        pair = Image.new("RGB", (one.width * 2, one.height), "white")
        pair.paste(one, (0, 0))
        pair.paste(one, (one.width, 0))
        with self.assertRaisesRegex(ValueError, "multiple"):
            signature(pair, "relay")

    def test_simple_signature_keeps_small_disconnected_terminal(self):
        image = Image.new("RGB", (80, 80), "white")
        draw = ImageDraw.Draw(image)
        draw.line((20, 40, 45, 40, 45, 60), fill="blue", width=2)
        base = signature(image, "simple")
        draw.line((45, 20, 45, 26), fill="blue", width=2)
        with_terminal = signature(image, "simple")
        self.assertFalse(np.array_equal(base, with_terminal))

    def test_simple_rejects_two_major_glyphs(self):
        image = Image.new("RGB", (100, 70), "white")
        draw = ImageDraw.Draw(image)
        draw.line((15, 20, 25, 20, 25, 50), fill="blue", width=2)
        draw.line((65, 20, 75, 20, 75, 50), fill="blue", width=2)
        with self.assertRaisesRegex(ValueError, "multiple"):
            signature(image, "simple")

    def test_two_large_plug_components_require_separate_crops(self):
        image = Image.new("RGB", (130, 90), "white")
        draw = ImageDraw.Draw(image)
        draw.rectangle((20, 20, 34, 60), fill="blue")
        draw.rectangle((80, 20, 94, 60), fill="blue")
        with self.assertRaisesRegex(ValueError, "multiple"):
            signature(image, "plug")


if __name__ == "__main__":
    unittest.main()
