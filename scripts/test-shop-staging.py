#!/usr/bin/env python3
"""Non-production static safety gate for the independent BIG PAW food catalog."""
from collections import Counter
from pathlib import Path
import re
import subprocess
import tempfile

shop = Path("app/shop.html").read_text(encoding="utf-8")
rows = re.findall(r"^'([A-Z]\d{2})\|([A-Z]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|]+)\|([^|']+)'[,]?$", shop, re.M)
assert len(rows) == 35, f"Expected 35 products, got {len(rows)}"
assert Counter(r[1] for r in rows) == {"ACANA": 14, "ORIJEN": 8, "ZIWI": 9, "CHARM": 4}
assert len(set(r[0] for r in rows)) == 35, "Duplicate product IDs"
assert len(set(r[7] for r in rows)) == 35, "Duplicate image slugs"
assert all(r[3] in ("11.4kg", "10kg", "4kg", "3.2kg", "2.5kg") for r in rows)
assert {r[0]:r[3] for r in rows}["Z01"] == "2.5kg", "Venison is only stocked as 2.5kg"
assert {r[0]:r[3] for r in rows}["Z04"] == "2.5kg", "Tripe & Lamb is only stocked as 2.5kg"
assert "referenceMsrpExTax" in shop, "35 public reference MSRP entries required"
prices = re.search(r"const referenceMsrpExTax=(\{[^;]+\});",shop)
assert prices, "Reference MSRP catalog missing"
import json
retail = json.loads(prices.group(1))
assert len(retail) == 35, "All 35 products must have a retailer MSRP"
assert set(retail) == {r[0] for r in rows}
assert retail["Z01"] == 39000 and retail["Z04"] == 21800, "ZIWI 2.5kg MSRP mismatch"
assert retail["A02"] == 19500 and retail["O03"] == 23800
assert "小売店卸価格" not in shop, "Wholesale data must not appear in public frontend"
assert "noindex,nofollow" in shop
assert "販売準備中" in shop and "価格準備中" in shop
assert 'disabled>販売開始までお待ちください' in shop
assert "localStorage" not in shop and "fetch(" not in shop, "No checkout/data mutation permitted"
assert "app/backend" not in shop, "Shop must remain independent from backend"
assert "ziwi-venison" in shop and "ziwi-tripe-lamb" in shop
assert 'id="brandCards"' in shop and 'id="catalogStart"' in shop
assert 'brand-section' in shop and 'seriesOrder' in shop
assert '"brand-card"' in shop and 'id="clearFilters"' in shop
assert 'ACANA:[\'アカナドッグ\',\'ハイエストプロテイン\',\'シングル\']' in shop
assert 'ZIWI:[\'エアドライ\',\'スチームドライ\']' in shop

assert shop.count("<script>") == 1 and shop.count("</script>") == 1
script = shop.split("<script>", 1)[1].split("</script>", 1)[0]
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "shop.js"
    p.write_text(script, encoding="utf-8")
    subprocess.run(["node", "--check", str(p)], check=True)
print("SHOP_CATALOG_STATIC_OK|products=35|ACANA=14|ORIJEN=8|ZIWI=9|CHARM=4|checkout=disabled")
