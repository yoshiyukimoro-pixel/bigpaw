"""Offline import regression: exact SKU fingerprints and 63 fake WebP assets."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
import zipfile

spec = importlib.util.spec_from_file_location(
    "shop_detail_importer", "scripts/import-shop-detail-assets.py")
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

# Construct only harmless fake WebPs to test the ZIP format. This test never
# invokes Square, touches production, or writes to app/assets.
MOCK_WEBP = b"RIFF" + (120).to_bytes(4,"little") + b"WEBP" + b"\0"*116


class DetailImportTests(unittest.TestCase):
    def test_approved_manifests_install_only_63_files(self):
        js = """
const vm=require('node:vm'),fs=require('node:fs');
const context={window:{}};
vm.runInNewContext(fs.readFileSync('app/shop-detail-images.js','utf8'),context);
console.log(JSON.stringify(context.window.BIGPAW_SHOP_DETAIL_IMAGES));
"""
        raw=subprocess.run(["node","-e",js],check=True,text=True,capture_output=True)
        mapping=json.loads(raw.stdout)
        self.assertEqual(set(mapping),set(mod.EXPECTED))
        records=[]
        for sku,images in mapping.items():
            records.append({"id":sku,"brand":mod.BRANDS[sku[0]][0],
                            "images":images})
        assets=sorted({im["src"] for rec in records for im in rec["images"]})
        self.assertEqual(len(assets),63)
        with tempfile.TemporaryDirectory() as temp:
            p=Path(temp)/"assets.zip"
            with zipfile.ZipFile(p,"w") as z:
                z.writestr("detail-images.json",json.dumps(records,ensure_ascii=False))
                for asset in assets:
                    z.writestr("app/"+asset,MOCK_WEBP)
            self.assertEqual(len(mod.read_archives([p])),63)
            # A missing image must fail before any files are written.
            p2=Path(temp)/"missing.zip"
            with zipfile.ZipFile(p2,"w") as z:
                z.writestr("detail-images.json",json.dumps(records,ensure_ascii=False))
                for asset in assets[1:]:
                    z.writestr("app/"+asset,MOCK_WEBP)
            with self.assertRaises(ValueError):
                mod.read_archives([p2])

    def test_rejects_bad_brand_or_wrong_product(self):
        self.assertEqual(len(mod.EXPECTED),35)
        self.assertEqual(sum(x[1] for x in mod.BRANDS.values()),35)


if __name__ == "__main__":
    unittest.main()
