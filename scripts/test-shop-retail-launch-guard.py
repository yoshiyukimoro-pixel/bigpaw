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
        self.assertIn("BIG PAWは屋号であり、法定の販売業者氏名を兼ねるものではありません", PAGE)
        self.assertIn("<strong>茂呂義之</strong>", PAGE)
        self.assertIn("住所および確実に連絡が取れる電話番号", PAGE)
        self.assertIn("ご請求があれば電子メール等により遅滞なく提供", PAGE)
        import re
        self.assertIsNone(re.search(r"\b0[789]0[- ]?\d{4}[- ]?\d{4}\b", PAGE))
        self.assertIsNone(re.search(r"\b\d{3}-\d{4}\b", PAGE))
        self.assertIn("フードショップ販売者情報の開示請求フォーム", PAGE)
        self.assertIn("info@bigpaw.site", PAGE)
        self.assertIn("受付・個別回答をテスト", PAGE)
        self.assertIn("事業者の所在地・電話番号", PAGE)
        self.assertIn("実際の請求対応体制の確認を終えるまで", PAGE)
        self.assertIn("販売開始前に、実際の請求受付・個別回答をテスト", PAGE)
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
