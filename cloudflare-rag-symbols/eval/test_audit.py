import hashlib
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from index_symbols import audit


def row(name, image):
    return {
        "short_name": name,
        "number": "402",
        "variant_id": "A",
        "file_name": {"bytes": image, "path": name + ".png"},
    }


class AuditTests(unittest.TestCase):
    def test_identical_rows_collapse_with_stable_first_row(self):
        identities, manifest = audit(
            [row("KS", b"image"), row("KS", b"image"), row("KT2", b"other")],
            {"short_name", "number", "variant_id", "file_name"},
            "source_hash",
        )
        self.assertEqual(len(identities), 2)
        self.assertEqual(manifest["exact_duplicate_rows"], 1)
        self.assertEqual(identities[("KS", "402", "A")]["row"], 0)
        self.assertEqual(identities[("KS", "402", "A")]["image_sha256"],
                         hashlib.sha256(b"image").hexdigest())

    def test_conflicting_image_for_identity_stops_indexing(self):
        with self.assertRaisesRegex(ValueError, "different images"):
            audit([row("KS", b"one"), row("KS", b"two")],
                  {"short_name", "number", "variant_id", "file_name"},
                  "source_hash")


if __name__ == "__main__":
    unittest.main()
