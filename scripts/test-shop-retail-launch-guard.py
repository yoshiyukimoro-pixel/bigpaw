"""Offline safety checks for the independently sold BIG PAW food shop.

Do not let an owner confirmation of 'personal business' imply that a legal
merchant name, phone, street address, returns or live checkout were approved.
"""
import copy
from pathlib import Path
import unittest

from shop_payments.retail_launch_guard import REQUIRED, check, load_and_check

ROOT = Path(__file__).resolve().parents[1]
PAGE = (ROOT / "app/shop-commerce.html").read_text(encoding="utf-8")
REVIEW = (ROOT / "app/shop-order-review.js").read_text(encoding="utf-8")
SHOP = (ROOT / "app/shop.html").read_text(encoding="utf-8")


class RetailLaunchGuardTests(unittest.TestCase):
    def test_current_shop_is_explicitly_not_live(self):
        ready, missing = load_and_check()
        self.assertFalse(ready)
        self.assertGreaterEqual(len(missing), 9)
        self.assertIn("seller_identity", missing)
        self.assertIn("statutory_contact", missing)
        self.assertIn("return_policy", missing)
        self.assertIn("customer_email_delivery", missing)
        self.assertIn("square_live_readiness", missing)
        self.assertIn("proprietor_approval", missing)

    def test_all_requirements_are_independent_and_fail_closed(self):
        approved = {
            "business_structure": "individual_proprietor",
            "sandbox_only": True,
            "public_live_checkout_enabled": False,
            "launch_checks": {key: True for key in REQUIRED},
        }
        self.assertEqual(check(approved), (True, []))
        for item in REQUIRED:
            changed = copy.deepcopy(approved)
            changed["launch_checks"][item] = False
            self.assertFalse(check(changed)[0], item)
            self.assertIn(item, check(changed)[1])
        for key, value in (
            ("business_structure", "unknown"),
            ("sandbox_only", False),
            ("public_live_checkout_enabled", True),
        ):
            changed = copy.deepcopy(approved)
            changed[key] = value
            self.assertFalse(check(changed)[0], key)
        self.assertFalse(check(None)[0])
        self.assertFalse(check({"launch_checks": None})[0])

    def test_individual_proprietor_not_falsely_claimed_as_fully_disclosed(self):
        self.assertIn("個人事業", PAGE)
        self.assertIn("屋号だけでは代用できません", PAGE)
        self.assertIn("個人事業者の正式な氏名は未入力", PAGE)
        self.assertIn("事業者の所在地・電話番号", PAGE)
        self.assertIn("省略が認められる状態とは扱いません", PAGE)
        self.assertIn("返品・キャンセル", PAGE)
        self.assertIn('name="robots" content="noindex,nofollow"', PAGE)
        self.assertIn("受け付けていません", PAGE)
        self.assertIn("条件が未確定", REVIEW)
        self.assertIn("checkout.disabled", REVIEW)
        self.assertIn('id="previewCheckout" disabled', SHOP)
        self.assertNotIn("fetch(", REVIEW,
                         "Public review page must never issue a payment request")


if __name__ == "__main__":
    unittest.main()
