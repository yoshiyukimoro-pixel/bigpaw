"""Static safety tests for agreed buy-to-order lead time and no premature live sales."""
from pathlib import Path
import re
import unittest

SHOP=Path("app/shop.html").read_text(encoding="utf-8")
REVIEW=Path("app/shop-order-review.js").read_text(encoding="utf-8")


class DeliveryTermsTests(unittest.TestCase):
    def test_shop_catalog_product_detail_cart_are_informed(self):
        self.assertEqual(SHOP.count("4〜7日程度"),3,
                         "catalog listing, each product detail template and cart")
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

    def test_applies_to_all_35_products_without_catalog_edits(self):
        self.assertIn("document.getElementById('detail').innerHTML",SHOP)
        self.assertIn("detail-delivery",SHOP)
        self.assertIn("const chosen=",SHOP)
        rows=re.findall(r"^'[A-Z]\\d{2}\\|",SHOP,re.MULTILINE)
        # Shop has exactly 35 static product record strings.
        self.assertEqual(len(rows),35)
        self.assertIn("referenceMsrpExTax",SHOP)


if __name__=="__main__":
    unittest.main()
