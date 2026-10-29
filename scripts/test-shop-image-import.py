"""Offline contract tests for the guarded 35-photo ZIP importer."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location(
    "shop_image_import", "scripts/import-shop-images.py",
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


class TestImagePack(unittest.TestCase):
    def make_pack(self, path, *, omit=None, corrupt=None):
        slugs = module.catalog_slugs()
        manifest = [{"slug": slug, "has_image": True} for slug in sorted(slugs)]
        # This fixture tests archive structure/header validation, not photo quality.
        valid = b"RIFF" + (120).to_bytes(4, "little") + b"WEBP" + b"0" * 116
        with zipfile.ZipFile(path, "w") as z:
            z.writestr("PRODUCT_IMAGE_MAP.json", json.dumps(manifest))
            for slug in slugs:
                if slug != omit:
                    z.writestr(module.PREFIX + slug + ".webp",
                               b"not a WebP" if slug == corrupt else valid)

    def test_35_slugs_and_valid_pack(self):
        self.assertEqual(len(module.catalog_slugs()), 35)
        with tempfile.TemporaryDirectory() as t:
            p = Path(t) / "pack.zip"
            self.make_pack(p)
            self.assertEqual(len(module.inspect_archive(p)), 35)

    def test_refuses_missing_and_corrupt_photos(self):
        with tempfile.TemporaryDirectory() as t:
            for kind in ("missing", "corrupt"):
                p = Path(t) / (kind + ".zip")
                slugs = sorted(module.catalog_slugs())
                self.make_pack(p, omit=slugs[0] if kind == "missing" else None,
                               corrupt=slugs[0] if kind == "corrupt" else None)
                with self.subTest(kind=kind), self.assertRaises(ValueError):
                    module.inspect_archive(p)


if __name__ == "__main__":
    unittest.main()
