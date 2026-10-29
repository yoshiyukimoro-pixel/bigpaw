"""Safely import the supplied 4 manufacturer detail ZIPs into the staging clone.

Usage (no production effects):
  python3 scripts/import-shop-detail-assets.py path/to/ACANA.zip path/to/ORIJEN.zip path/to/ZIWI.zip path/to/CHARM.zip
  python3 scripts/import-shop-detail-assets.py path/to/*.zip --install

Default validates only. --install writes the 63 WebP files under
app/assets/shop-details/. It never commits, pushes, deploys or edits prices.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
BRANDS = {"A": ("ACANA", 14), "O": ("ORIJEN", 8),
          "Z": ("ZIWI", 9), "C": ("CHARM", 4)}
# Per-SKU fingerprints from the four manufacturer manifests (ordered image
# path, caption and specific/shared scope). Protects from accidental mixing.
EXPECTED = {
 "A01":"905d699642cdbbe3","A02":"1b4b33b1eb9b0d0e",
 "A03":"cb031344a43d9e53","A04":"b89a315831cd03dc",
 "A05":"e969c3fd576d86a3","A06":"9bb0e5f647d84845",
 "A07":"0ebc2cac326b36c7","A08":"626b0264d9f43eea",
 "A09":"b5af4751ecc2cc40","A10":"8ab039adc0f9ea2e",
 "A11":"816d83cab42f4546","A12":"fbe5c7890a542b90",
 "A13":"4fda0ecdacba6a6d","A14":"a5cd32728e078e84",
 "O01":"fa1ef0b1e5cd8fb1","O02":"0f6c16f111fcf75b",
 "O03":"ffa3ad17ff7b750c","O04":"f36730f3ab04738c",
 "O05":"f47e029a5b6e3030","O06":"3efc1d2037ce2ac7",
 "O07":"fb81e9c8f518d778","O08":"6fe7f93019071a80",
 "Z01":"44142bbbc57fea36","Z02":"45557fc6217f7c12",
 "Z03":"9a8c1abd5212cb4a","Z04":"eb7c4c93231b6249",
 "Z05":"cc9ee76a06960a3c","Z06":"ed1f480969677999",
 "Z07":"4f7f0e68e6c43e3b","Z08":"ec65bad87e6097f4",
 "Z09":"ec65bad87e6097f4",
 "C01":"9a169565f61b9e88","C02":"8ed5fa8101ad2a4f",
 "C03":"731a742b66312cd7","C04":"4b6b76957339be04"
}


def read_archives(paths: list[Path]) -> dict[str, bytes]:
    if not 1 <= len(paths) <= 4:
        raise ValueError("Expected 1 verified combined archive or the 4 source ZIPs")
    records: dict[str, dict] = {}
    assets: dict[str, bytes] = {}
    for source in paths:
        with zipfile.ZipFile(source) as z:
            manifest = json.loads(z.read("detail-images.json"))
            if not isinstance(manifest, list):
                raise ValueError("Invalid detail image manifest")
            for product in manifest:
                if not isinstance(product, dict) or product.get("id") in records:
                    raise ValueError("Duplicate/invalid product")
                records[product["id"]] = product
            for info in z.infolist():
                if not info.filename.endswith(".webp"):
                    continue
                key = info.filename.removeprefix("app/")
                # A verified 98-image combined pack may include the 35 front
                # photos. Their completeness is checked separately.
                if re.fullmatch(r"assets/shop-products/[a-z0-9-]+\.webp", key):
                    continue
                if (not key.startswith("assets/shop-details/")
                        or not re.fullmatch(
                            r"assets/shop-details/(products/[AOZC]\d{2}|shared/(acana|orijen|ziwi|charm))/[a-z0-9-]+\.webp",
                            key,
                        ) or key in assets or info.file_size > 1_500_000):
                    raise ValueError("Unsafe or duplicate asset path")
                data = z.read(info)
                if (len(data) < 128 or data[:4] != b"RIFF" or data[8:12] != b"WEBP"
                        or int.from_bytes(data[4:8], "little")+8 != len(data)):
                    raise ValueError("Invalid WebP format/length")
                assets[key] = data
    if set(records) != set(EXPECTED):
        raise ValueError("Not the approved 35 SKU set")
    paths_in_manifest = set()
    for pid, item in records.items():
        brand = BRANDS[pid[0]][0]
        if item.get("brand") != brand or not isinstance(item.get("images"), list):
            raise ValueError("SKU/brand mismatch")
        lines = []
        for im in item["images"]:
            src, cap, scope = (im.get(key) for key in ("src", "caption", "scope"))
            if not isinstance(src, str) or src not in assets or not isinstance(cap, str):
                raise ValueError("Manufacturer image missing")
            if scope == "specific":
                if not src.startswith("assets/shop-details/products/"+pid+"/"):
                    raise ValueError("Product-specific image assigned to another SKU")
            elif scope == "brand":
                if not src.startswith("assets/shop-details/shared/"+brand.lower()+"/"):
                    raise ValueError("Cross-brand shared artwork")
            else:
                raise ValueError("Image scope missing")
            paths_in_manifest.add(src)
            lines.append("|".join((scope,src,cap)))
        digest = hashlib.sha256("\n".join(lines).encode()).hexdigest()[:16]
        if digest != EXPECTED[pid]:
            raise ValueError("Product image order/caption/association mismatch: "+pid)
    if paths_in_manifest != set(assets) or len(assets) != 63:
        raise ValueError("Expected exactly 63 referenced WebP images")
    return assets


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("archives", type=Path, nargs="+")
    parser.add_argument("--install", action="store_true")
    args = parser.parse_args()
    files = read_archives(args.archives)
    print("Verified: 35 SKUs, 63 unique WebP assets, exact approved image associations.")
    if args.install:
        for rel, body in files.items():
            dest = ROOT / "app" / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(body)
        print("Installed under app/assets/shop-details/ in the current workspace only.")
        print("Git commit / push and any publication remain separate prohibited steps.")


if __name__ == "__main__":
    main()
