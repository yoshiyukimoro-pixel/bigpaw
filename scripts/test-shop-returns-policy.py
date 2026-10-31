"""No merchant return policy is approved until actual owner confirmation.

This static test guards the separate BIG PAW food-sale returns proposal
from being mistaken for binding purchase terms or authorizing live checkout.
"""
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
DATA = json.loads((ROOT / "shop_payments/returns_policy_review.json").read_text(encoding="utf-8"))
GATE = json.loads((ROOT / "shop_payments/retail_launch_status.json").read_text(encoding="utf-8"))
PAGE = (ROOT / "app/shop-returns.html").read_text(encoding="utf-8")
REVIEW = (ROOT / "app/shop-order-review.js").read_text(encoding="utf-8")


class ReturnsDraftTests(unittest.TestCase):
    def test_owner_has_not_approved_draft_as_refund_contract(self):
        self.assertEqual(DATA["status"], "draft_not_approved")
        self.assertFalse(DATA["accepted_by_proprietor"])
        self.assertEqual(DATA["policy_applies_to"], "dog_food_shop_only")
        self.assertFalse(GATE["launch_checks"]["return_policy"])
        self.assertFalse(GATE["public_live_checkout_enabled"])
        self.assertTrue(GATE["sandbox_only"])

    def test_all_policy_decisions_need_merchant_approval(self):
        self.assertEqual(
            set(DATA["policies"]), {
                "customer_change_of_mind", "before_shipping_cancel",
                "defect_damage_wrong_item", "supplier_out_of_stock_or_delay",
                "refund_and_contact",
            },
        )
        for case, value in DATA["policies"].items():
            with self.subTest(case=case):
                if case == "customer_change_of_mind":
                    self.assertIs(value["approved"], True)
                    self.assertIn("未開封・未使用", value["policy_ja"])
                    self.assertIn("不良", value["exceptions_ja"])
                    self.assertIn("誤配送", value["exceptions_ja"])
                    self.assertFalse(DATA["accepted_by_proprietor"])
                else:
                    self.assertIs(value["approved"], False)
                    self.assertTrue(value["proposed"].strip())
                    self.assertTrue(value["decision_needed"].strip())
        self.assertIn("https://www.no-trouble.caa.go.jp/what/mailorder/",
                      DATA["references"])

    def test_preview_explicitly_distinguishes_legal_fallback_and_draft(self):
        for text in ("返品・キャンセル対応案（未承認）",
                     "正式な返品特約ではありません",
                     "特定商取引法",
                     "未開封・未使用の場合も含めてお受けしておりません",
                     "クーリング・オフ制度はありません",
                     "法令上の購入者の権利"):
            self.assertIn(text, PAGE)
        self.assertIn('name="robots" content="noindex,nofollow"', PAGE)
        self.assertIn("条件が未確定", REVIEW)
        self.assertIn("shop-returns.html", REVIEW)
        self.assertIn("checkout.disabled", REVIEW)
        self.assertNotIn("send_real_email", PAGE)


if __name__ == "__main__":
    unittest.main()
