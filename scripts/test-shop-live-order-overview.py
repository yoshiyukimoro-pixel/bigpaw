"""Offline, no network and no user data: private live order read-model tests."""
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from shop_payments.live_order_ledger import LiveOrderLedger, LiveOrderBlocked
from shop_payments.live_order_overview import read_order_management_snapshot
from shop_payments.staging_live_overview_page import render_order_overview_preview
from shop_payments.retail_catalog import load_sale_catalog

PENDING = "FOOD" + "a" * 32
PAID = "FOOD" + "b" * 32
LOC = "FAKESQUARELOCATION1234"
PAYMENT = "FAKESQUAREPAYMENT123456"


class LiveOrderManagementOverviewTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "private-live-orders.sqlite3"
        self.ledger = LiveOrderLedger(self.path)
        self.sku, item = next(iter(load_sale_catalog().items()))
        self.price = item.sale_price_yen

    def read(self, **kwargs):
        return read_order_management_snapshot(ledger=self.ledger, **kwargs)

    def setup_orders(self):
        self.ledger.register_checkout(
            order_id=PENDING, square_order_id="FAKESQUAREORDERPENDING1234",
            location_id=LOC, cart={self.sku: 2}
        )
        self.ledger.register_checkout(
            order_id=PAID, square_order_id="FAKESQUAREORDERPAID12345",
            location_id=LOC, cart={self.sku: 1}
        )

    def mark_paid_offline(self):
        self.ledger.reconcile_payment(
            order_id=PAID, payment_id=PAYMENT, api_key="SYNTHETIC",
            verifier=lambda **kwargs: {
                "live_square_verified": True,
                "payment_id": PAYMENT,
                "square_order_id": kwargs["square_order_id"],
                "location_id": LOC,
                "amount_yen": self.price,
            },
        )

    def test_missing_db_does_not_create_any_file(self):
        self.assertEqual(self.read(),
                         {"orders": [], "count": 0, "read_only": True})
        self.assertFalse(self.path.exists())

    def test_operator_read_model_returns_two_historical_state_labels(self):
        self.setup_orders()
        self.mark_paid_offline()
        self.ledger.record_signed_payment_event(
            event_id="FAKE_SIGNED_EVENT_123456",
            fingerprint="0" * 64,
            order_id=PAID, payment_id=PAYMENT,
        )
        before = self.path.read_bytes()
        snapshot = self.read()
        self.assertEqual(snapshot["count"], 2)
        self.assertTrue(snapshot["read_only"])
        by_id = {entry["order_id"]: entry for entry in snapshot["orders"]}
        self.assertEqual(by_id[PAID]["amount_yen"], self.price)
        self.assertTrue(by_id[PAID]["payment_recorded_historically"])
        self.assertEqual(by_id[PAID]["current_payment_status"], "not_checked")
        self.assertTrue(by_id[PAID]["manual_square_check_required"])
        self.assertEqual(by_id[PAID]["verified_signed_event_count"], 1)
        self.assertEqual(by_id[PAID]["items"][0]["sku"], self.sku)
        self.assertEqual(by_id[PENDING]["amount_yen"], 2 * self.price)
        self.assertFalse(by_id[PENDING]["payment_recorded_historically"])
        self.assertEqual(by_id[PENDING]["verified_signed_event_count"], 0)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn("email", str(snapshot).lower())
        self.assertNotIn("recipient", str(snapshot).lower())
        self.assertNotIn("payment_id", str(snapshot).lower())
        self.assertNotIn("square_order_id", str(snapshot).lower())

    def test_preview_html_displays_history_without_promising_current_payment(self):
        self.setup_orders()
        self.mark_paid_offline()
        html = render_order_overview_preview(self.ledger)
        self.assertIn("BIG PAW｜注文管理の表示確認", html)
        self.assertIn("過去のSquare入金確認記録あり", html)
        self.assertIn("現在の入金・返金状況は未確認", html)
        self.assertIn("仕入れ・発送やお客様への入金済み通知は行わない", html)
        self.assertIn("最大100件", html)
        self.assertNotIn("action=", html)
        self.assertNotIn("<form", html)
        for forbidden in ("recipient_email", "payment_id", "square_order_id",
                          "Authorization", "Bearer "):
            self.assertNotIn(forbidden, html)
        self.assertIn(f"{self.price:,}円", html)
        with sqlite3.connect(self.path) as db:
            import json
            row = db.execute(
                "SELECT cart_snapshot FROM food_live_order_ledger "
                "WHERE order_id=?", (PENDING,),
            ).fetchone()
            lines = json.loads(row[0])
            lines[0]["name"] = '<img src=x onerror="alert(1)">'
            db.execute(
                "UPDATE food_live_order_ledger SET cart_snapshot=? "
                "WHERE order_id=?",
                (json.dumps(lines), PENDING),
            )
        html = render_order_overview_preview(self.ledger)
        self.assertNotIn('<img src=x onerror="alert(1)">', html)
        self.assertIn("&lt;img src=x onerror=&quot;alert(1)&quot;&gt;", html)

    def test_limit_and_invalid_private_entry_are_blocked(self):
        self.setup_orders()
        self.assertEqual(self.read(limit=1)["count"], 1)
        for limit in (False, 0, 101, "2", None):
            with self.subTest(limit=limit), self.assertRaises(LiveOrderBlocked):
                self.read(limit=limit)
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE food_live_order_ledger SET amount_yen=1 WHERE order_id=?",
                (PENDING,),
            )
        with self.assertRaises(LiveOrderBlocked):
            self.read()


if __name__ == "__main__":
    unittest.main()
