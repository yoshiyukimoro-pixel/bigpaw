"""Offline-only tests for order-email review; NO production network or mail."""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from shop_payments.live_customer_notice_preview import preview_paid_order_confirmation
from shop_payments.live_notice_approval import LiveNoticeApproval, APPROVAL_SECONDS
from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from shop_payments.retail_catalog import load_sale_catalog

ORDER = "FOOD" + "c" * 32
SQUARE_ORDER = "REVIEWFAKEORDER12345"
LOCATION = "REVIEWFAKELOCATION12345"
PAYMENT = "REVIEWFAKEPAYMENT12345"
API_KEY = "offline-test-only-not-real-square-key"
REVIEW_KEY = "offline-test-review-secret-only-12345"
EMAIL = "test-customer@example.invalid"


class OwnerReviewTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "private-test-order.sqlite"
        self.ledger = LiveOrderLedger(self.path)
        self.review = LiveNoticeApproval(self.ledger)
        self.sku, product = next(iter(load_sale_catalog().items()))
        self.price = product.sale_price_yen
        self.email = EMAIL
        self.total_offset = 0
        self.valid = True
        self.calls = []
        self.ledger.register_checkout(
            order_id=ORDER, square_order_id=SQUARE_ORDER,
            location_id=LOCATION, cart={self.sku: 1},
        )
        self.ledger.reconcile_payment(
            order_id=ORDER, payment_id=PAYMENT, api_key=API_KEY,
            verifier=self.mock_square,
        )
        self.calls.clear()

    def mock_square(self, **kwargs):
        self.calls.append(kwargs)
        self.assertEqual(kwargs["payment_id"], PAYMENT)
        self.assertEqual(kwargs["square_order_id"], SQUARE_ORDER)
        self.assertEqual(kwargs["location_id"], LOCATION)
        self.assertEqual(kwargs["amount_yen"], self.price)
        self.assertEqual(kwargs["api_key"], API_KEY)
        return {
            "live_square_verified": self.valid,
            "payment_id": PAYMENT, "square_order_id": SQUARE_ORDER,
            "location_id": LOCATION,
            "amount_yen": self.price + self.total_offset,
            "recipient_email": self.email,
        }

    def preview(self):
        return preview_paid_order_confirmation(
            ledger=self.ledger, order_id=ORDER,
            api_key=API_KEY, review_secret=REVIEW_KEY,
            verifier=self.mock_square,
        )

    def approve(self, **override):
        params = dict(
            order_id=ORDER,
            reviewed_fingerprint=self.preview()["review_fingerprint"],
            authorized=True, confirmed=True,
            api_key=API_KEY, review_secret=REVIEW_KEY,
            verifier=self.mock_square, now=1000,
        )
        params.update(override)
        return self.review.approve(**params)

    def check(self, **override):
        params = dict(order_id=ORDER, api_key=API_KEY,
                      review_secret=REVIEW_KEY, verifier=self.mock_square,
                      now=1100)
        params.update(override)
        return self.review.check(**params)

    def test_explicit_review_is_persisted_and_never_sendable(self):
        preview = self.preview()
        self.calls.clear()
        with self.assertRaises(LiveOrderBlocked):
            self.check()
        self.assertEqual(self.calls, [])
        result = self.review.approve(
            order_id=ORDER,
            reviewed_fingerprint=preview["review_fingerprint"],
            authorized=True, confirmed=True, api_key=API_KEY,
            review_secret=REVIEW_KEY, verifier=self.mock_square, now=1000,
        )
        self.assertEqual(result["expires_at"], 1000 + APPROVAL_SECONDS)
        self.assertFalse(result["send_enabled"])
        self.assertFalse(result["sent"])
        check = self.check()
        self.assertTrue(check["approved"])
        self.assertEqual(check["masked_recipient"], "t***@e***")
        self.assertFalse(check["send_enabled"])
        self.assertFalse(check["sent"])
        self.assertNotIn("to", check)
        self.assertNotIn("body", check)
        self.assertNotIn("prepared_only", check)
        # In the same SQLite DB, only a non-PII HMAC and timestamps persisted.
        raw = self.path.read_bytes()
        for secret in (EMAIL, API_KEY, REVIEW_KEY, "FAKE BUYER"):
            self.assertNotIn(secret.encode(), raw)
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT kind,state,fingerprint FROM food_live_notice_review"
            ).fetchone()
        self.assertEqual(row[0], "customer_order_confirmed")
        self.assertEqual(row[1], "approved")
        self.assertEqual(len(row[2]), 64)
        # Simulate process restart. The approval persists only in private DB.
        self.assertTrue(LiveNoticeApproval(LiveOrderLedger(self.path)).check(
            order_id=ORDER, api_key=API_KEY, review_secret=REVIEW_KEY,
            verifier=self.mock_square, now=1100,
        )["approved"])

    def test_missing_operator_confirmation_blocks_before_lookup_or_write(self):
        finger = self.preview()["review_fingerprint"]
        self.calls.clear()
        for values in (
            {"authorized": False, "confirmed": True},
            {"authorized": True, "confirmed": False},
            {"authorized": 1, "confirmed": True},
            {"authorized": True, "confirmed": 1},
        ):
            with self.subTest(values=values):
                with self.assertRaises(LiveOrderBlocked):
                    self.review.approve(
                        order_id=ORDER, reviewed_fingerprint=finger,
                        api_key=API_KEY, review_secret=REVIEW_KEY,
                        verifier=self.mock_square, now=1000, **values,
                    )
        self.assertEqual(self.calls, [])
        with sqlite3.connect(self.path) as db:
            self.assertIsNone(db.execute(
                "SELECT name FROM sqlite_master "
                "WHERE name='food_live_notice_review'"
            ).fetchone())

    def test_changed_customer_contact_or_amount_invalidates_old_approval(self):
        finger = self.preview()["review_fingerprint"]
        self.email = "changed@example.invalid"
        with self.assertRaises(LiveOrderBlocked):
            self.review.approve(
                order_id=ORDER, reviewed_fingerprint=finger, authorized=True,
                confirmed=True, api_key=API_KEY, review_secret=REVIEW_KEY,
                verifier=self.mock_square, now=1000,
            )
        self.email = EMAIL
        self.approve()
        self.email = "new-email@example.invalid"
        with self.assertRaises(LiveOrderBlocked):
            self.check()
        self.email = EMAIL
        self.total_offset = 5
        with self.assertRaises(LiveOrderBlocked):
            self.check()
        self.total_offset = 0
        self.valid = False
        with self.assertRaises(LiveOrderBlocked):
            self.check()

    def test_approval_expires_and_requires_fresh_review(self):
        self.approve()
        self.assertTrue(self.check(now=1000 + APPROVAL_SECONDS - 1)["approved"])
        self.calls.clear()
        with self.assertRaises(LiveOrderBlocked):
            self.check(now=1000 + APPROVAL_SECONDS)
        self.assertEqual(self.calls, [])  # Fails before any Square read.
        self.approve(now=2000)  # Explicit new approval, not an auto-renewal.
        self.assertTrue(self.check(now=2001)["approved"])

    def test_revoke_fails_closed_and_cannot_be_automatically_reenabled(self):
        self.approve()
        with self.assertRaises(LiveOrderBlocked):
            self.review.revoke(order_id=ORDER, authorized=False, confirmed=True)
        self.assertTrue(self.check()["approved"])
        result = self.review.revoke(
            order_id=ORDER, authorized=True, confirmed=True
        )
        self.assertEqual(result, {"revoked": True, "sent": False})
        self.calls.clear()
        with self.assertRaises(LiveOrderBlocked):
            self.check()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.review.revoke(
            order_id=ORDER, authorized=True, confirmed=True
        ), {"revoked": False, "sent": False})

    def test_tampering_or_wrong_review_secret_fails_closed(self):
        self.approve()
        self.calls.clear()
        with self.assertRaises(LiveOrderBlocked):
            self.check(review_secret="WRONG-key-secret-value-at-least-24")
        with sqlite3.connect(self.path) as db:
            db.execute("UPDATE food_live_notice_review SET fingerprint=?",
                       ("0" * 64,))
        with self.assertRaises(LiveOrderBlocked):
            self.check()
        self.assertFalse(any("recipient" in str(x) for x in self.calls))

    def test_invalid_inputs_do_not_authorize(self):
        finger = self.preview()["review_fingerprint"]
        for order, value in (("wrong", finger), (ORDER, "malformed")):
            with self.subTest(order=order):
                with self.assertRaises(LiveOrderBlocked):
                    self.review.approve(
                        order_id=order, reviewed_fingerprint=value,
                        authorized=True, confirmed=True, api_key=API_KEY,
                        review_secret=REVIEW_KEY, verifier=self.mock_square,
                        now=1000,
                    )


if __name__ == "__main__":
    unittest.main()
