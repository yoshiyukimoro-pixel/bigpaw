"""Offline acceptance of a combined 35-front + 63-detail installer."""
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import subprocess
import tempfile
import unittest
import zipfile

ROOT=Path(__file__).resolve().parents[1]
WEBP=b"RIFF"+(120).to_bytes(4,"little")+b"WEBP"+b"\0"*116


def load_module():
    spec=importlib.util.spec_from_file_location(
        "combined_shop_installer", "scripts/install-shop-98-assets.py"
    )
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CombinedInstallerTest(unittest.TestCase):
    def make_pack(self, zip_path, corrupt=False):
        shop=(ROOT/"app/shop.html").read_text(encoding="utf8")
        products=[
            row.split("|")
            for row in re.findall(r"^'([AOZC]\d{2}\|[^']+)'[,]?$",shop,re.M)
        ]
        self.assertEqual(len(products),35)
        catalog=[
            {"brand":r[1],"slug":r[7],"name":r[2],
             "weight":r[3],"has_image":True} for r in products
        ]
        command=(
            "const fs=require('fs'),vm=require('vm');"
            "const c={window:{}};"
            "vm.runInNewContext(fs.readFileSync('app/shop-detail-images.js','utf8'),c);"
            "console.log(JSON.stringify(c.window.BIGPAW_SHOP_DETAIL_IMAGES));"
        )
        mapping=json.loads(subprocess.run(
            ["node","-e",command],capture_output=True,text=True,check=True
        ).stdout)
        records=[
            {"id":r[0],"brand":r[1],"images":mapping[r[0]]}
            for r in products
        ]
        images=set()
        for r in records:
            images.update("app/"+im["src"] for im in r["images"])
        for r in catalog:
            images.add("app/assets/shop-products/"+r["slug"]+".webp")
        self.assertEqual(len(images),98)
        sums={name:hashlib.sha256(WEBP).hexdigest() for name in images}
        if corrupt:
            sums[next(iter(sorted(sums)))]="0"*64
        with zipfile.ZipFile(zip_path,"w") as z:
            z.writestr("detail-images.json",json.dumps(records,ensure_ascii=False))
            z.writestr("PRODUCT_IMAGE_MAP.json",json.dumps(catalog,ensure_ascii=False))
            z.writestr("IMAGE_SHA256.json",json.dumps(sums))
            for name in images:
                z.writestr(name,WEBP)

    def test_98_images_and_reject_tampering(self):
        mod=load_module()
        with tempfile.TemporaryDirectory() as directory:
            good=Path(directory)/"good.zip"
            self.make_pack(good)
            files=mod.verify(good)
            self.assertEqual(len(files),98)
            self.assertEqual(sum(
                name.startswith("app/assets/shop-products/") for name in files
            ),35)
            bad=Path(directory)/"bad.zip"
            self.make_pack(bad,corrupt=True)
            with self.assertRaises(ValueError):
                mod.verify(bad)


if __name__=="__main__":
    unittest.main()
