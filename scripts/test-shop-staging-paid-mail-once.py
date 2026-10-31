"""Offline tests: one operator Sandbox mail for already-paid order, no retry."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import unittest

from shop_payments.staging_paid_mail_once import maybe_send_verified_test_order
from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_runtime_guard import (
    LEGACY_BIGPAW_PROJECT, EXISTING_TEST_ENVIRONMENT, EXISTING_TEST_SERVICE,
)

ORDER = "FOOD" + "f" * 32
SQUARE_ORDER = "SANDBOX_MAIL_ONCE_ORDER_123"
PAYMENT = "SANDBOX_MAIL_ONCE_PAYMENT_123"
LOCATION = "SANDBOX_MAIL_ONCE_LOCATION_123"
KEY = "test-signature"
URL = "https://bigpaw-test-production.up.railway.app/api/shop/sandbox/webhook"
ENV = {
    "BIGPAW_ENV": "sandbox",
    "BIGPAW_SHOP_STAGING_ISOLATED": "1",
    "RAILWAY_PROJECT_ID": LEGACY_BIGPAW_PROJECT,
    "RAILWAY_ENVIRONMENT_ID": EXISTING_TEST_ENVIRONMENT,
    "RAILWAY_SERVICE_ID": EXISTING_TEST_SERVICE,
    "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID": LEGACY_BIGPAW_PROJECT,
    "BIGPAW_SHOP_SANDBOX_PAID_MAIL_ONCE_ENABLED": "1",
    "BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED": "1",
    "RESEND_API_KEY": "re_FAKE_SANDBOX_TESTING_1234567890",
    "BIGPAW_SHOP_SANDBOX_SEED_ORDER_ID": ORDER,
}


class TestOnceAfterPaid(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db = str(Path(temp.name) / "test.sqlite3")
        self.env = {**ENV, "BIGPAW_SHOP_SANDBOX_DB": self.db}
        self.store = SandboxOrderStore(self.db)
        self.store.add_pending_order(
            order_id=ORDER, cart={"A02": 1},
            verified_prices=load_sale_catalog(), shipping_yen=0,
            location_id=LOCATION,
        )
        self.store.save_link(ORDER, {
            "url": "https://sandbox.square.link/u/not-real",
            "square_order_id": SQUARE_ORDER,
            "square_link_id": "SANDBOX_MAIL_ONCE_LINK_123",
        })
        self.sends = []
        self.events = []

    def sender(self, *, api_key, to, subject, body, idempotency_key):
        self.assertEqual(api_key, ENV["RESEND_API_KEY"])
        self.assertEqual(to, "info@bigpaw.site")
        self.assertIn("Square Sandboxテスト", subject)
        self.assertIn("発注しないでください", body)
        self.assertIn("21,450円", body)
        self.assertEqual(idempotency_key,
                         "bigpaw-shop-sandbox-operator-new-order/" + ORDER)
        self.sends.append(idempotency_key)
        return "mock_resend_accept_id_123456789"

    def run_once(self, env=None, sender=None):
        return maybe_send_verified_test_order(
            self.env if env is None else env,
            sender=self.sender if sender is None else sender,
            output=self.events.append,
        )

    def set_paid_from_verified_square_event(self):
        payment = {
            "id": PAYMENT,
            "order_id": SQUARE_ORDER,
            "location_id": LOCATION,
            "status": "COMPLETED",
            "amount_money": {"amount": 21450, "currency": "JPY"},
        }
        raw = json.dumps({
            "event_id": "paid-mail-once-fixture-id-123456",
            "type": "payment.updated",
            "data": {"object": {"payment": payment}},
        }).encode()
        signature = base64.b64encode(hmac.new(
            KEY.encode(), URL.encode() + raw, hashlib.sha256,
        ).digest()).decode()
        self.assertEqual(self.store.accept_webhook(
            raw_body=raw, signature_header=signature,
            signature_key=KEY, notification_url=URL,
            payment_lookup=lambda _: dict(payment),
        ), "paid")

    def test_paid_required_and_only_one_sandbox_operator_message(self):
        self.assertEqual(self.run_once(), "not_paid")
        self.assertEqual(self.sends, [])
        self.set_paid_from_verified_square_event()
        self.assertEqual(self.run_once(), "accepted")
        self.assertEqual(self.run_once(), "already_handled")
        self.assertEqual(len(self.sends), 1)
        self.assertIn("SHOP_SANDBOX_PAID_MAIL=ACCEPTED_DELIVERY_UNVERIFIED", self.events)
        self.assertEqual(self.events[-1], "SHOP_SANDBOX_PAID_MAIL=ALREADY_HANDLED")

    def test_never_send_on_production_or_wrong_test_identity(self):
        self.set_paid_from_verified_square_event()
        for bad in (
            {**self.env, "BIGPAW_SHOP_SANDBOX_PAID_MAIL_ONCE_ENABLED": "0"},
            {**self.env, "BIGPAW_ENV": "production"},
            {**self.env, "RAILWAY_PROJECT_ID": "afb79723-1a2d-4c43-b498-f166e501760c"},
            {**self.env, "RAILWAY_SERVICE_ID": "32e31163-1049-41d3-84f8-dd61a0a7019e"},
            {**self.env, "RAILWAY_SERVICE_ID": "1ad6d952-c284-4886-9237-a30c364132fd"},
            {**self.env, "BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED": "0"},
            {**self.env, "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID": ""},
            {**self.env, "RESEND_API_KEY": ""},
        ):
            self.assertNotEqual(self.run_once(bad), "accepted")
        self.assertEqual(self.sends, [])

    def test_timeout_does_not_retry(self):
        self.set_paid_from_verified_square_event()
        attempts = []
        def timeout(**kw):
            attempts.append(1)
            raise TimeoutError("mock timeout")
        self.assertEqual(self.run_once(sender=timeout), "unknown")
        self.assertEqual(self.run_once(), "already_handled")
        self.assertEqual(attempts, [1])
        self.assertEqual(self.sends, [])
        self.assertEqual(self.events[-1], "SHOP_SANDBOX_PAID_MAIL=ALREADY_HANDLED")


if __name__ == "__main__":
    unittest.main()
