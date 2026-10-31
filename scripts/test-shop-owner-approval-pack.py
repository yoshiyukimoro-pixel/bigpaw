"""Offline audit: draft seller terms and customer notices do not authorize live sales."""
from pathlib import Path
import json
import unittest

ROOT = Path(__file__).resolve().parents[1]


class ApprovalPackTests(unittest.TestCase):
    def test_draft_documents_cover_remaining_legal_and_notice_decisions(self):
        pack = (ROOT / "SHOP_SELLER_APPROVAL_PACK_20261031.md").read_text(encoding="utf-8")
        notices = (ROOT / "SHOP_CUSTOMER_NOTICES_FOR_APPROVAL_20261031.md").read_text(encoding="utf-8")
        owner = (ROOT / "SHOP_OWNER_DECISIONS.md").read_text(encoding="utf-8")
        for item in ("販売業者", "所在地", "電話番号", "事業者", "返品", "キャンセル",
                     "送料", "欠品", "返金", "注文", "Square", "4〜7日"):
            self.assertIn(item, pack, item)
        for item in ("ご注文", "欠品", "配送遅延", "発送完了", "返金完了",
                     "info@bigpaw.site", "4〜7日", "送料", "未承認", "未送信"):
            self.assertIn(item, notices, item)
        self.assertIn("SHOP_SELLER_APPROVAL_PACK_20261031.md", owner)
        self.assertIn("SHOP_CUSTOMER_NOTICES_FOR_APPROVAL_20261031.md", owner)
        self.assertIn("未承認", pack)
        self.assertIn("未承認", notices)

    def test_draft_docs_do_not_mutate_approval_or_go_live(self):
        status = json.loads(
            (ROOT / "shop_payments/retail_launch_status.json").read_text(encoding="utf-8")
        )
        returns = json.loads(
            (ROOT / "shop_payments/returns_policy_review.json").read_text(encoding="utf-8")
        )
        self.assertTrue(status["sandbox_only"])
        self.assertFalse(status["public_live_checkout_enabled"])
        self.assertEqual(set(status["launch_checks"].values()), {False})
        self.assertFalse(returns["accepted_by_proprietor"])
        self.assertEqual(returns["status"], "draft_not_approved")
        for policy in returns["policies"].values():
            self.assertIs(policy["approved"], False)
        from shop_payments.retail_launch_guard import check
        ready, missing = check(status)
        self.assertFalse(ready)
        self.assertIn("return_policy", missing)
        self.assertIn("checkout_disclosure", missing)
        self.assertIn("proprietor_approval", missing)


if __name__ == "__main__":
    unittest.main()
