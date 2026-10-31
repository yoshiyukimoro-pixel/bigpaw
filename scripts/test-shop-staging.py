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
assert "referenceMsrpExTax" in shop, "35 manufacturer MSRP entries required"
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
assert "販売準備中" in shop and "販売価格（税込・送料込み）" in shop and "全商品送料込み" in shop
assert 'disabled>販売開始までお待ちください' in shop
assert "localStorage" not in shop and "fetch(" not in shop, "No checkout/data mutation permitted"
cart = Path("app/shop-cart-preview.js").read_text(encoding="utf-8")
assert "shop-cart-preview.js" in shop, "Shop must load the preview cart"
assert 'id="previewCartDialog"' in shop and 'id="previewCheckout" disabled' in shop
assert "checkout" not in cart.lower() or "checkout disabled" in cart.lower(), "No real checkout permitted"
assert "fetch(" not in cart and "XMLHttpRequest" not in cart and "sendBeacon" not in cart, "Cart must not contact a backend"
assert "localStorage" not in cart and "window.open" not in cart, "No persistent or redirected checkout"
assert 'sessionStorage' in cart, "Cart preview must only store session-level cart state"
assert 'referenceMsrpExTax' in cart, "Cart uses manufacturer MSRP as approved sale price"
assert '仕入' not in cart and '卸値' not in cart and 'wholesalePrice' not in cart
with tempfile.TemporaryDirectory() as tmp:
    node_path = Path(tmp) / "cart.js"
    node_path.write_text(cart, encoding="utf-8")
    subprocess.run(["node", "--check", str(node_path)], check=True)

assert "app/backend" not in shop, "Shop must remain independent from backend"
assert "ziwi-venison" in shop and "ziwi-tripe-lamb" in shop
assert 'id="brandCards"' in shop and 'id="catalogStart"' in shop
assert 'brand-section' in shop and 'seriesOrder' in shop
assert '"brand-card"' in shop and 'id="clearFilters"' in shop
assert 'ACANA:[\'アカナドッグ\',\'ハイエストプロテイン\',\'シングル\']' in shop
assert 'ZIWI:[\'エアドライ\',\'スチームドライ\']' in shop

assert shop.count("<script>") == 1 and shop.count("</script>") == 6, "Catalog script plus cart, image, quote verifier and order review scripts"
assert 'shop-review-quote-check.js' in shop, "Read-only quote module must be present for future approved checkout"
quote_script = Path("app/shop-review-quote-check.js").read_text(encoding="utf-8")
assert "'/api/shop/checkout/config'" in quote_script and "'/api/shop/checkout/quote'" in quote_script
assert "Square" in quote_script and "payment_link_created !== false" in quote_script
assert "window.open" not in quote_script and "localStorage" not in quote_script
assert "BigPawShopQuote.verify" not in Path("app/shop-order-review.js").read_text(encoding="utf-8"), "Actual preview must not call backend quote"
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "quote.js"
    path.write_text(quote_script, encoding="utf-8")
    subprocess.run(["node", "--check", str(path)], check=True)
assert 'shop-detail-images.js' in shop and 'shop-detail-gallery.js' in shop and 'shop-detail-gallery.css' in shop
assert 'shop-order-review.js' in shop and 'shop-order-review.css' in shop
assert 'id="orderReview" hidden' in shop and 'shop.html?order=review' in shop
assert 'id="previewCheckout" disabled' in shop
order_script = Path("app/shop-order-review.js").read_text(encoding="utf-8")
assert 'sessionStorage.getItem' in order_script and 'Math.round(p.referenceMsrpExTax * 1.1)' in order_script
assert 'shop-payments' not in order_script and 'fetch(' not in order_script and 'XMLHttpRequest' not in order_script
assert 'localStorage' not in order_script and 'sessionStorage.setItem' not in order_script
with tempfile.TemporaryDirectory() as tmp:
    path = Path(tmp) / "order.js"
    path.write_text(order_script, encoding="utf-8")
    subprocess.run(["node", "--check", str(path)], check=True)

script = shop.split("<script>", 1)[1].split("</script>", 1)[0]
with tempfile.TemporaryDirectory() as tmp:
    p = Path(tmp) / "shop.js"
    p.write_text(script, encoding="utf-8")
    subprocess.run(["node", "--check", str(p)], check=True)
print("SHOP_CATALOG_STATIC_OK|products=35|ACANA=14|ORIJEN=8|ZIWI=9|CHARM=4|checkout=disabled")

assert '参考・希望小売価格（税込）' not in shop
assert '※BIG PAWの販売価格ではありません' not in shop
assert '販売価格（税込・送料込み）' in cart
assert '送料・割引・在庫・注文条件は未確定' not in shop
