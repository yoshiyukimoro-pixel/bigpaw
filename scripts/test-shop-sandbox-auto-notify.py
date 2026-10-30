"""Offline regression for opt-in order-paid -> operator notification bridge.

No Square API, Resend API, Railway, customer mail or supplier mail is called.
"""
import base64
import hashlib
import hmac
import json
import tempfile
import unittest
from pathlib import Path

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.sandbox_notifications import SandboxNotificationDrafts
from shop_payments.sandbox_operator_email import SandboxOperatorEmail
from shop_payments.sandbox_auto_notify import maybe_notify_verified_payment

ORDER = "FOOD" + "a" * 32
SQUARE_ORDER = "ORDER_SANDBOX_AUTO_12345"
PAYMENT = "PAYMENT_SANDBOX_AUTO_12345"
LOCATION = "LOCATION_SANDBOX_12345"
SECRET = "sandbox-local-test-hmac"
URL = "https://sandbox.example.invalid/api/shop/sandbox/webhook"
ENABLED = {
    "BIGPAW_ENV": "sandbox",
    "BIGPAW_SHOP_STAGING_ISOLATED": "1",
    "BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED": "1",
    "BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED": "1",
    "RESEND_API_KEY": "re_NOT_REAL_12345678901234567890",
}


class OperatorAutoNotificationTests(unittest.TestCase):
    def setUp(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.store = SandboxOrderStore(Path(folder.name) / "test.sqlite3")
        self.store.add_pending_order(
            order_id=ORDER, cart={"A02": 1},
            verified_prices=load_sale_catalog(), shipping_yen=0,
            location_id=LOCATION,
        )
        self.store.save_link(ORDER, {
            "url": "https://sandbox.square.link/u/fake",
            "square_order_id": SQUARE_ORDER,
            "square_link_id": "LINK_SANDBOX_AUTO_12345",
        })
        self.sent = []

    def sender(self, *, api_key, to, subject, body, idempotency_key):
        self.assertEqual(to, "info@bigpaw.site")
        self.assertEqual(api_key, ENABLED["RESEND_API_KEY"])
        self.assertIn("[Square Sandboxテスト", subject)
        self.assertIn("実際のお客様からの注文・入金ではありません", body)
        self.assertIn("発注しないでください", body)
        self.assertIn("21,450円", body)
        self.assertEqual(idempotency_key,
                         "bigpaw-shop-sandbox-operator-new-order/" + ORDER)
        self.sent.append(idempotency_key)
        return "mock_sandbox_resend_mail_1234"

    def event(self, *, event_id="signed-auto-notify-event-1",
              payment_status="COMPLETED", payment_id=PAYMENT):
        payment = {
            "id": payment_id,
            "order_id": SQUARE_ORDER,
            "location_id": LOCATION,
            "status": payment_status,
            "amount_money": {"amount": 21450, "currency": "JPY"},
        }
        obj = {
            "event_id": event_id,
            "type": "payment.updated",
            "data": {"object": {"payment": payment}},
        }
        raw = json.dumps(obj).encode()
        signature = base64.b64encode(hmac.new(
            SECRET.encode(), URL.encode() + raw, hashlib.sha256,
        ).digest()).decode()
        return raw, signature, payment

    def verified_webhook(self, *, payment_status="COMPLETED",
                         fresh_status=None, event_id="signed-auto-notify-event-1"):
        raw, signature, payment = self.event(
            event_id=event_id, payment_status=payment_status,
        )
        fresh = dict(payment)
        fresh["status"] = fresh_status or payment_status
        result = self.store.accept_webhook(
            raw_body=raw,
            signature_header=signature,
            signature_key=SECRET,
            notification_url=URL,
            payment_lookup=lambda _: fresh,
        )
        return result, raw

    def call(self, result, raw, *, env=None, sender=None):
        return maybe_notify_verified_payment(
            self.store, webhook_status=result, raw_body=raw,
            env=ENABLED if env is None else env,
            sender=self.sender if sender is None else sender,
        )

    def test_paid_verification_queues_drafts_then_one_operator_alert(self):
        status, raw = self.verified_webhook()
        self.assertEqual(status, "paid")
        self.assertEqual(len(SandboxNotificationDrafts(self.store).pending()), 3)
        self.assertEqual(self.call(status, raw), "accepted")
        self.assertEqual(len(self.sent), 1)
        history = SandboxOperatorEmail(self.store).history()
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0]["status"], "accepted")
        self.assertEqual(history[0]["recipient"], "info@bigpaw.site")
        # Same event and a new verified event must not duplicate mail.
        repeat, _ = self.verified_webhook()
        self.assertEqual(repeat, "duplicate")
        self.assertEqual(self.call(repeat, raw), "not_newly_paid")
        self.assertEqual(self.call("paid", raw), "already_handled")
        self.assertEqual(len(self.sent), 1)

    def test_pending_or_unverified_payments_never_notify(self):
        status, raw = self.verified_webhook(fresh_status="PENDING")
        self.assertEqual(status, "unverified")
        self.assertEqual(self.call(status, raw), "not_newly_paid")
        self.assertEqual(self.sent, [])
        self.assertEqual(SandboxOperatorEmail(self.store).history(), [])
        self.assertEqual(SandboxNotificationDrafts(self.store).pending(), [])

    def test_opt_in_and_sandbox_environment_required(self):
        status, raw = self.verified_webhook()
        self.assertEqual(status, "paid")
        variants = [
            {**ENABLED, "BIGPAW_ENV": "production"},
            {**ENABLED, "BIGPAW_ENV": "development"},
            {**ENABLED, "BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED": "0"},
            {**ENABLED, "BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED": "0"},
            {**ENABLED, "RAILWAY_ENVIRONMENT_ID": "production-service"},
            {**ENABLED, "RAILWAY_SERVICE_ID": "production-service"},
            {},
        ]
        for config in variants:
            self.assertEqual(self.call(status, raw, env=config), "disabled")
        self.assertEqual(SandboxOperatorEmail(self.store).history(), [])
        self.assertEqual(self.sent, [])
        for invalid in ("", "BADKEY", "re_has space", "re_SHORT"):
            self.assertEqual(self.call(status, raw, env={**ENABLED, "RESEND_API_KEY": invalid}),
                             "missing_send_key")
        self.assertEqual(self.sent, [])

    def test_existing_railway_test_service_only_is_allowed(self):
        status, raw = self.verified_webhook()
        self.assertEqual(status, "paid")
        target = {**ENABLED,
            "RAILWAY_PROJECT_ID": "d70f7165-f5eb-41e8-95a0-62f85ff90478",
            "RAILWAY_ENVIRONMENT_ID": "ecc9fcbf-496f-4b51-a651-65a46a971588",
            "RAILWAY_SERVICE_ID": "1a1a32bd-e885-4848-a6b5-fde5ef9ac902",
            "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID":
                "d70f7165-f5eb-41e8-95a0-62f85ff90478",
        }
        for service in (
            "32e31163-1049-41d3-84f8-dd61a0a7019e",  # bigpaw-site
            "1ad6d952-c284-4886-9237-a30c364132fd",  # bigpaw-web
            "fake-service",
        ):
            self.assertEqual(
                self.call(status, raw, env={**target, "RAILWAY_SERVICE_ID": service}),
                "disabled",
            )
        self.assertEqual(self.sent, [])
        self.assertEqual(self.call(status, raw, env=target), "accepted")
        self.assertEqual(len(self.sent), 1)

    def test_event_payment_id_must_match_committed_paid_order(self):
        status, raw = self.verified_webhook()
        self.assertEqual(status, "paid")
        other, _, _ = self.event(payment_id="PAYMENT_DIFFERENT_12345678")
        self.assertEqual(self.call(status, other), "unmatched")
        self.assertEqual(self.call(status, b"not-json"), "unavailable")
        self.assertEqual(self.sent, [])
        self.assertEqual(self.call(status, raw), "accepted")
        self.assertEqual(len(self.sent), 1)

    def test_ambiguous_failure_never_retries_even_for_new_event(self):
        status, raw = self.verified_webhook()
        attempts = []
        def timeout(**kwargs):
            attempts.append(kwargs["idempotency_key"])
            raise TimeoutError("offline simulated timeout")
        self.assertEqual(self.call(status, raw, sender=timeout), "unknown")
        self.assertEqual(self.call(status, raw), "already_handled")
        self.assertEqual(len(attempts), 1)
        self.assertEqual(len(self.sent), 0)
        self.assertEqual(SandboxOperatorEmail(self.store).history()[0]["status"], "unknown")


if __name__ == "__main__":
    unittest.main()
