"""Install the approved 98-photo pack into a staging checkout, never production.

Usage:
    python3 scripts/install-shop-98-assets.py /path/to/bigpaw_shop_98_images_staging_ready_fixed.zip
    python3 scripts/install-shop-98-assets.py /path/to/pack.zip --install

Validates 35 front photos, 63 detail photos, 35 image assignments, all 98
SHA-256 checksums and WebP headers BEFORE making any local file changes.
No checkout, Square, deployments, GitHub tokens or branch operations involved.
"""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import zipfile

ROOT=Path(__file__).resolve().parents[1]
SCRIPT_DIR=Path(__file__).resolve().parent


def load_helper(name, filename):
    spec=importlib.util.spec_from_file_location(name, SCRIPT_DIR / filename)
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify(pack: Path) -> dict[str, bytes]:
    front=load_helper("food_front_import", "import-shop-images.py")
    detail=load_helper("food_detail_import", "import-shop-detail-assets.py")
    front_images=front.inspect_archive(pack)
    detail_images=detail.read_archives([pack])
    result={}
    for slug, data in front_images.items():
        result["app/assets/shop-products/"+slug+".webp"]=data
    for path, data in detail_images.items():
        result["app/"+path]=data
    if len(result)!=98:
        raise ValueError("Expected exactly 35+63 manufacturer WebP images")
    with zipfile.ZipFile(pack) as z:
        sums=json.loads(z.read("IMAGE_SHA256.json"))
    if not isinstance(sums,dict) or set(sums)!=set(result):
        raise ValueError("Hash manifest has missing or extra image names")
    for name, data in result.items():
        if not re.fullmatch(
            r"app/assets/shop-(?:products|details)/[A-Za-z0-9/_-]+\.webp",name
        ):
            raise ValueError("Unexpected image destination")
        if hashlib.sha256(data).hexdigest()!=sums[name]:
            raise ValueError("SHA-256 mismatch: "+name)
    return result


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("zip", type=Path)
    parser.add_argument("--install",action="store_true")
    opts=parser.parse_args()
    results=verify(opts.zip)
    print("VALIDATED 35 SKU front photos + 63 details = 98 authentic WebP files")
    if opts.install:
        for name, raw in results.items():
            destination=ROOT / name
            destination.parent.mkdir(parents=True,exist_ok=True)
            destination.write_bytes(raw)
        print("INSTALLED 98 images under app/assets/ in this local checkout only.")
        print("No GitHub push/production deploy/payment activation was performed.")


if __name__=="__main__":
    main()
