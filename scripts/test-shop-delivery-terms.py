"""Static safety tests for agreed buy-to-order lead time and no premature live sales."""
from pathlib import Path
import re
import unittest

SHOP=Path("app/shop.html").read_text(encoding="utf-8")
REVIEW=Path("app/shop-order-review.js").read_text(encoding="utf-8")
COMMERCE=Path("app/shop-commerce.html").read_text(encoding="utf-8")


class DeliveryTermsTests(unittest.TestCase):
    def test_shop_catalog_product_detail_cart_are_informed(self):
        self.assertEqual(SHOP.count("4〜7日程度"),4,
                         "catalog listing, detail specification and notice, and cart")
        self.assertIn("九州の仕入先",SHOP)
        self.assertIn("当店（埼玉）",SHOP)
        self.assertIn("当店へ入荷後、検品",SHOP)
        self.assertIn("仕入先の欠品時",SHOP)
        self.assertIn("全額返金",SHOP)
        self.assertIn("全国送料無料",SHOP)
        self.assertIn('id="previewCheckout" disabled',SHOP)
        self.assertIn('disabled>販売開始までお待ちください',SHOP)
        self.assertNotIn('shop-sandbox-review.js',SHOP)

    def test_checkout_order_review_includes_4_to_7_day_approval(self):
        self.assertIn('id="orderDeliveryTitle"',REVIEW)
        self.assertIn("通常4〜7日程度",REVIEW)
        self.assertIn("注文・決済完了からの目安",REVIEW)
        self.assertIn("九州の仕入先",REVIEW)
        self.assertIn("埼玉の当店",REVIEW)
        self.assertIn("入荷・検品後",REVIEW)
        self.assertIn("全額返金",REVIEW)
        self.assertIn("お取り寄せによる通常4〜7日程度",REVIEW)
        self.assertIn("注文や決済は行われません",REVIEW)
        self.assertIn("checkout.disabled",REVIEW)
        self.assertNotIn("fetch(",REVIEW)

    def test_shop_has_separate_sale_conditions_but_blocks_live_checkout(self):
        # Existing breeder-marketplace legal notice does not cover food retail.
        self.assertIn('href="shop-commerce.html"', SHOP)
        self.assertIn('href="shop-commerce.html"', REVIEW)
        self.assertIn("返品・キャンセル・販売事業者のご案内", REVIEW)
        self.assertIn("条件が未確定", REVIEW)
        self.assertIn('id="previewCheckout" disabled', SHOP)
        self.assertIn("checkout.disabled", REVIEW)
        self.assertNotIn("fetch(", REVIEW, "public preview must not send orders")
        self.assertIn("現在、商品の注文・決済は受け付けていません", COMMERCE)
        self.assertIn("正式な特定商取引法に基づく表記", COMMERCE)
        self.assertIn("返品・キャンセル", COMMERCE)
        self.assertIn("販売業者・所在地・電話番号", COMMERCE)
        self.assertIn("事業者が正式に確認するまで未確定", COMMERCE)
        self.assertIn("通常4〜7日程度", COMMERCE)
        self.assertIn("追加送料0円", COMMERCE)
        self.assertIn("info@bigpaw.site", COMMERCE)
        self.assertIn("お客様に発送", COMMERCE)
        self.assertNotIn("お客様都合の返品は一切不可", COMMERCE,
                         "merchant has not approved a specific return exclusion")
        self.assertIn('name="robots" content="noindex,nofollow"', COMMERCE)

    def test_applies_to_all_35_products_without_catalog_edits(self):
        self.assertIn("document.getElementById('detail').innerHTML",SHOP)
        self.assertIn("detail-delivery",SHOP)
        self.assertIn("const chosen=",SHOP)
        rows=[line for line in SHOP.splitlines() if re.match(r"^'[AOZC][0-9]{2}\|",line)]
        # Shop has exactly 35 static product record strings.
        self.assertEqual(len(rows),35)
        self.assertIn("referenceMsrpExTax",SHOP)


if __name__=="__main__":
    unittest.main()
