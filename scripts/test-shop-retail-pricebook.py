"""Safe offline retail pricebook assertions; no web calls or payment tokens."""
import json
from pathlib import Path
import re
import unittest

from shop_payments.retail_catalog import load_sale_catalog, build_shipping_included_square_order


class TestApprovedRetailPricebook(unittest.TestCase):
    def test_35_products_tax_and_shipping_included(self):
        data = json.loads(Path("shop_payments/retail_pricebook.json").read_text(encoding="utf-8"))
        self.assertTrue(data["tax_included"])
        self.assertTrue(data["shipping_included"])
        self.assertEqual(data["shipping_yen"], 0)
        catalog = load_sale_catalog()
        self.assertEqual(len(catalog), 35)
        self.assertEqual(catalog["A02"].sale_price_yen, 21450)
        self.assertEqual(catalog["Z01"].sale_price_yen, 42900)
        self.assertEqual(catalog["Z04"].sale_price_yen, 23980)
        self.assertEqual(catalog["C04"].sale_price_yen, 27280)
        # Public price numbers must match server-approved pricebook.
        html = Path("app/shop.html").read_text(encoding="utf-8")
        values = json.loads(re.search(r"const referenceMsrpExTax=(\{[^;]+\});", html).group(1))
        for pid, product in catalog.items():
            self.assertIn(pid, values)
            self.assertEqual(product.sale_price_yen, round(values[pid] * 1.1))
        self.assertNotIn("小売店卸価格", html)
        self.assertNotIn("仕入価格", html)
        self.assertNotIn("卸価格", html)

    def test_no_delivery_line_or_extra_charge(self):
        payload, total = build_shipping_included_square_order(
            cart={"A02": 2, "Z01": 1},
            square_location_id="SQUARETEST1234",
            local_order_id="FOOD202610290001",
        )
        self.assertEqual(total, 85800)
        self.assertEqual(payload["order"]["taxes"][0]["type"], "INCLUSIVE")
        self.assertEqual(payload["order"]["taxes"][0]["scope"], "ORDER")
        self.assertEqual(payload["order"]["taxes"][0]["percentage"], "10")
        self.assertEqual(len(payload["order"]["line_items"]), 2)
        self.assertNotIn("送料", [x["name"] for x in payload["order"]["line_items"]])
        self.assertTrue(all(x["base_price_money"]["currency"] == "JPY" for x in payload["order"]["line_items"]))

    def test_cannot_inject_sale_price(self):
        with self.assertRaises(TypeError):
            build_shipping_included_square_order(
                cart={"A02": 1}, square_location_id="SQUARETEST1234",
                local_order_id="FOOD202610290002", sale_price_yen=1,
            )
        with self.assertRaises(ValueError):
            build_shipping_included_square_order(
                cart={"UNLISTED": 1}, square_location_id="SQUARETEST1234",
                local_order_id="FOOD202610290003",
            )


if __name__ == "__main__":
    unittest.main()
