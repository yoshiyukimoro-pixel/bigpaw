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
        self.assertIn("店主から5種類の通知文面の編集・最終決定を委任済み", notices)
        self.assertIn("未開封の場合も含めてお受けしておりません", notices)
        self.assertIn("店主自身", notices)
        self.assertIn("送信は禁止したまま", notices)

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
        self.assertIs(returns["policies"]["customer_change_of_mind"]["approved"], True)
        for key, policy in returns["policies"].items():
            if key != "customer_change_of_mind":
                self.assertIs(policy["approved"], False)
        self.assertIn("未開封・未使用", returns["policies"]["customer_change_of_mind"]["policy_ja"])
        self.assertFalse(returns["partial_owner_approvals"]["seller_identity_contact"]["confidential_values_committed"])
        disclosure = returns["partial_owner_approvals"]["seller_identity_contact"]
        self.assertTrue(disclosure["method_owner_approved"])
        self.assertEqual(disclosure["statutory_publication_method"],
                         "public_legal_name_address_phone_on_request")
        self.assertTrue(disclosure["legal_name_publication_owner_approved"])
        self.assertTrue(disclosure["legal_name_in_draft_public_page"])
        self.assertFalse(disclosure["private_postal_address_phone_committed"])
        self.assertEqual(disclosure["request_contact"], "info@bigpaw.site")
        self.assertFalse(disclosure["request_response_operational_tested"])
        self.assertFalse(disclosure["legal_disclosure_final_approved"])
        self.assertFalse(status["launch_checks"]["statutory_contact"])
        self.assertFalse(status["launch_checks"]["seller_identity"])
        self.assertIn("請求に応じて遅滞なく提供", owner)
        self.assertIn("住所と確実につながる電話番号は請求に応じ遅滞なく個別開示", pack)
        self.assertIn("正式氏名は公開", owner)
        from shop_payments.retail_launch_guard import check
        ready, missing = check(status)
        self.assertFalse(ready)
        self.assertIn("return_policy", missing)
        self.assertIn("checkout_disclosure", missing)
        self.assertIn("proprietor_approval", missing)


if __name__ == "__main__":
    unittest.main()
