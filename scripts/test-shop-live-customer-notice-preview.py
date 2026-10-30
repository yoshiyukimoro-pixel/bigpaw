"""Offline-only pre-send preview tests; synthetic Square responses, no send.

A preview cannot make a live checkout, refund, shipment or email request.
No actual customer/merchant data, API credentials, network, or production SQL.
"""
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from shop_payments.live_customer_notice_preview import preview_paid_order_confirmation
from shop_payments.customer_email_transport import (
    CustomerEmailJournal, CustomerMailBlocked,
)
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.square_live_readonly import LiveSquareNotVerified, ENDPOINT

ORDER = "FOOD" + "a" * 32
SQUARE_ORDER = "NOTICETESTSQUAREORDER1234"
LOCATION = "NOTICETESTLOCATION1234"
PAYMENT = "NOTICETESTPAYMENT1234"
KEY = "fake-square-key-NOT-LIVE"
SIGN = "fake-review-key-31-chars-NOT-LIVE"
EMAIL = "synthetic-recipient@example.invalid"


class FakeResponse:
    status = 200
    def __init__(self, obj):
        self.raw = json.dumps(obj).encode()
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, limit):
        return self.raw[:limit]


class PaidNoticePreviewTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "private-live-preview.sqlite"
        self.journal = LiveOrderLedger(self.path)
        self.sku, self.product = next(iter(load_sale_catalog().items()))
        self.total = self.product.sale_price_yen
        self.cart = {self.sku: 1}
        self.calls = []
        self.pay_data = {
            "id": PAYMENT,
            "order_id": SQUARE_ORDER,
            "location_id": LOCATION,
            "status": "COMPLETED",
            "amount_money": {"amount": self.total, "currency": "JPY"},
            "refunded_money": {"amount": 0, "currency": "JPY"},
        }
        self.order_data = {
            "id": SQUARE_ORDER,
            "location_id": LOCATION,
            "state": "OPEN",
            "total_money": {"amount": self.total, "currency": "JPY"},
            "fulfillments": [{
                "type": "SHIPMENT",
                "shipment_details": {"recipient": {
                    "display_name": "FAKE RECIPIENT",
                    "email_address": EMAIL,
                    "address": {"country": "JP", "address_line_1": "TEST STREET",
                                "postal_code": "000-0000"},
                }},
            }],
        }

    def fake_square(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url))
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 10)
        self.assertEqual(request.headers["Authorization"], "Bearer " + KEY)
        if request.full_url == ENDPOINT + "/payments/" + PAYMENT:
            return FakeResponse({"payment": self.pay_data})
        if request.full_url == ENDPOINT + "/orders/" + SQUARE_ORDER:
            return FakeResponse({"order": self.order_data})
        self.fail("Unexpected call or unsupported Square endpoint")

    def register(self):
        return self.journal.register_checkout(
            order_id=ORDER, square_order_id=SQUARE_ORDER,
            location_id=LOCATION, cart=self.cart,
        )

    def paid(self):
        self.register()
        result = self.journal.reconcile_payment(
            order_id=ORDER, payment_id=PAYMENT, api_key=KEY,
            opener=self.fake_square,
        )
        self.assertTrue(result["new_transition"])
        self.calls.clear()

    def preview(self, **kwargs):
        values = {"ledger": self.journal, "order_id": ORDER,
                  "api_key": KEY, "review_secret": SIGN,
                  "opener": self.fake_square}
        return preview_paid_order_confirmation(**{**values, **kwargs})

    def test_paid_preview_uses_only_private_order_snapshot_and_fresh_get(self):
        self.paid()
        before = self.path.read_bytes()
        result = self.preview()
        self.assertEqual(self.calls, [
            ("GET", ENDPOINT + "/payments/" + PAYMENT),
            ("GET", ENDPOINT + "/orders/" + SQUARE_ORDER),
        ])
        self.assertEqual(result["masked_recipient"], "s***@e***")
        self.assertEqual(result["kind"], "customer_order_confirmed")
        self.assertIn(self.sku, result["body"])
        self.assertIn(self.product.name, result["body"])
        self.assertIn(self.product.size, result["body"])
        self.assertIn(f"{self.total:,}円", result["body"])
        self.assertIn("4〜7日程度", result["body"])
        self.assertIn("送信されていません", result["body"])
        self.assertTrue(result["review_only"])
        self.assertFalse(result["send_enabled"])
        self.assertFalse(result["sent"])
        self.assertTrue(result["requires_owner_approval"])
        self.assertEqual(len(result["review_fingerprint"]), 64)
        self.assertNotIn("to", result)
        self.assertNotIn("prepared_only", result)
        self.assertNotIn("live_square_verified", result)
        raw = json.dumps(result, ensure_ascii=False)
        for secret in (EMAIL, "TEST STREET", "FAKE RECIPIENT", KEY, SIGN):
            self.assertNotIn(secret, raw)
        self.assertEqual(before, self.path.read_bytes())
        self.assertEqual(result, self.preview())

    def test_unpaid_or_unknown_blocks_before_any_square_read(self):
        with self.assertRaises(LiveOrderBlocked):
            self.preview()
        self.assertEqual(self.calls, [])
        self.register()
        with self.assertRaises(LiveOrderBlocked):
            self.preview()
        self.assertEqual(self.calls, [])

    def test_refund_payment_or_shipping_changes_reject_fresh_notice(self):
        self.paid()
        original_pay = deepcopy(self.pay_data)
        original_order = deepcopy(self.order_data)
        cases = [
            ("part-refund", {"refunded_money": {"amount": 1, "currency": "JPY"}}, {}),
            ("unpaid", {"status": "PENDING"}, {}),
            ("currency", {"amount_money": {"amount": self.total, "currency": "USD"}}, {}),
            ("total", {}, {"total_money": {"amount": self.total + 100, "currency": "JPY"}}),
            ("address", {}, {"fulfillments": []}),
            ("order", {"order_id": "BADOTHERORDER123"}, {}),
        ]
        for name, payment_updates, order_updates in cases:
            with self.subTest(name=name):
                self.pay_data = {**original_pay, **payment_updates}
                self.order_data = {**original_order, **order_updates}
                with self.assertRaises(LiveSquareNotVerified):
                    self.preview()
        self.pay_data = original_pay
        self.order_data = original_order
        self.assertTrue(self.preview()["review_only"])

    def test_contact_changes_invalidate_review_fingerprint(self):
        self.paid()
        first = self.preview()
        self.order_data["fulfillments"][0]["shipment_details"]["recipient"]["email_address"] = (
            "changed-person@another.invalid"
        )
        second = self.preview()
        self.assertNotEqual(first["review_fingerprint"], second["review_fingerprint"])
        self.assertNotIn("changed-person", str(second))
        self.assertFalse(second["send_enabled"])

    def test_forged_verifier_and_invalid_signing_key_fail_closed(self):
        self.paid()
        self.calls.clear()
        with self.assertRaises(LiveOrderBlocked):
            self.preview(review_secret="")
        self.assertEqual(self.calls, [])
        def bad_verifier(**kwargs):
            return {"live_square_verified": True,
                    "payment_id": PAYMENT, "square_order_id": SQUARE_ORDER,
                    "location_id": LOCATION, "amount_yen": self.total + 1,
                    "recipient_email": EMAIL}
        with self.assertRaises(LiveOrderBlocked):
            self.preview(verifier=bad_verifier)
        self.assertEqual(self.calls, [])
        def no_recipient(**kwargs):
            return {"live_square_verified": True,
                    "payment_id": PAYMENT, "square_order_id": SQUARE_ORDER,
                    "location_id": LOCATION, "amount_yen": self.total}
        with self.assertRaises(LiveOrderBlocked):
            self.preview(verifier=no_recipient)

    def test_tampered_saved_snapshot_is_never_rendered(self):
        self.paid()
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE food_live_order_ledger SET cart_snapshot=? WHERE order_id=?",
                       ('[{"sku":"DANGER","qty":1,"unit_yen":-5}]', ORDER))
        self.calls.clear()
        with self.assertRaises(LiveOrderBlocked):
            self.preview()
        self.assertEqual(self.calls, [])

    def test_review_preview_cannot_enter_real_email_sender(self):
        self.paid()
        result = self.preview()
        mail_db = Path(self.tmp.name) / "mail-never-create.sqlite"
        sender = CustomerEmailJournal(mail_db)
        fake_live_flags = {
            "BIGPAW_ENV": "live",
            "BIGPAW_SHOP_CUSTOMER_EMAIL_ENABLED": "1",
            "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "1",
            "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "1",
        }
        calls = []
        def no_send(**kwargs):
            calls.append(kwargs)
            return "NOT-SENT"
        with self.assertRaises(CustomerMailBlocked):
            sender.send_once(result, env=fake_live_flags, confirmed=True,
                             api_key="fake-resend-key-not-valid-12345",
                             sender=no_send)
        self.assertEqual(calls, [])
        self.assertFalse(mail_db.exists())


if __name__ == "__main__":
    unittest.main()
