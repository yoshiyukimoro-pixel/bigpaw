"""Validate/install 35 authorized product photos from the prepared manufacturer ZIP.

Staging branch only. Does not commit, deploy, or publish anything.
Usage:
  python3 scripts/import-shop-images.py /path/to/bigpaw_dogfood_staging_assets_updated.zip
  python3 scripts/import-shop-images.py /path/to/pack.zip --install
  python3 scripts/import-shop-images.py --check-installed
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PRODUCT_DIR = ROOT / "app" / "assets" / "shop-products"
PREFIX = "app/assets/shop-products/"


def catalog_slugs() -> set[str]:
    html = (ROOT / "app" / "shop.html").read_text(encoding="utf-8")
    rows = re.findall(r"^'([AOZC]\d{2}\|[^']*)',?$", html, flags=re.MULTILINE)
    ids, slugs = set(), set()
    for row in rows:
        fields = row.split("|")
        if len(fields) != 9:
            raise ValueError("Unexpected storefront catalog format")
        pid, slug = fields[0], fields[7]
        if pid in ids or slug in slugs or not re.fullmatch(r"[a-z0-9-]+", slug):
            raise ValueError("Duplicate or invalid product ID/slug")
        ids.add(pid)
        slugs.add(slug)
    if len(slugs) != 35:
        raise ValueError("Expected 35 unique product slugs")
    return slugs


def validate_webp(blob: bytes) -> None:
    if (not 128 <= len(blob) <= 2_000_000 or
            blob[:4] != b"RIFF" or blob[8:12] != b"WEBP" or
            int.from_bytes(blob[4:8], "little") + 8 != len(blob)):
        raise ValueError("Invalid or unexpectedly sized WebP file")


def inspect_archive(source: Path) -> dict[str, bytes]:
    slugs = catalog_slugs()
    with zipfile.ZipFile(source) as z:
        data = json.loads(z.read("PRODUCT_IMAGE_MAP.json"))
        if (not isinstance(data, list) or len(data) != 35 or
                {row.get("slug") for row in data if isinstance(row, dict)} != slugs or
                not all(isinstance(row, dict) and row.get("has_image") is True
                        for row in data)):
            raise ValueError("Product ZIP manifest does not match the storefront catalog")
        expected = {PREFIX + slug + ".webp" for slug in slugs}
        actual = {entry.filename for entry in z.infolist()
                  if entry.filename.startswith(PREFIX) and entry.filename.endswith(".webp")}
        if actual != expected or len(actual) != 35:
            raise ValueError("Product ZIP must contain exactly 35 matching WebP photos")
        result = {}
        for slug in sorted(slugs):
            filename = PREFIX + slug + ".webp"
            info = z.getinfo(filename)
            if info.file_size > 2_000_000:
                raise ValueError("Oversize product photo")
            blob = z.read(filename)
            validate_webp(blob)
            result[slug] = blob
        return result


def check_installed() -> bool:
    slugs = catalog_slugs()
    missing = []
    for slug in sorted(slugs):
        path = PRODUCT_DIR / (slug + ".webp")
        if not path.is_file():
            missing.append(slug)
        else:
            validate_webp(path.read_bytes())
    if missing:
        print("Missing GitHub-ready photos:", len(missing), "of 35")
        return False
    print("All 35 product photos are installed and have valid WebP headers.")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", nargs="?", type=Path)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--check-installed", action="store_true")
    args = parser.parse_args()
    if args.check_installed:
        return 0 if check_installed() else 1
    if not args.archive:
        parser.error("Provide the prepared product photo ZIP")
    photos = inspect_archive(args.archive)
    print("Verified photo pack: 35/35 correct product slugs and WebP files.")
    if args.install:
        PRODUCT_DIR.mkdir(parents=True, exist_ok=True)
        for slug, data in photos.items():
            (PRODUCT_DIR / (slug + ".webp")).write_bytes(data)
        if not check_installed():
            return 1
        print("Images copied into staging workspace only; NOT committed or deployed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
