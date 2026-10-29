"""No network, no real Square credentials, no production dependencies."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import unittest
from urllib.error import URLError

from shop_payments.square_checkout import SaleItem
from shop_payments.sandbox_connector import (
    SANDBOX_ENDPOINT, SandboxOrderStore, SquareSandboxError,
    create_square_sandbox_payment_link,
)


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = body

    def read(self, n):
        return self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return None


class TestSquareSandboxIntegration(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db = SandboxOrderStore(Path(self.temp_dir.name) / "staging.sqlite")
        self.order_id = "FOOD202610290001"
        self.location_id = "SQUARE_SANDBOX_TEST01"
        self.catalog = {
            "A02": SaleItem("A02", "ACANA パピーラージ", "11.4kg", 25000),
            "Z01": SaleItem("Z01", "ZIWI ベニソン", "2.5kg", 35000),
        }
        self.cart = {"A02": 2, "Z01": 1}

    def tearDown(self):
        self.temp_dir.cleanup()

    def prepare(self, order_id=None):
        return self.db.add_pending_order(
            order_id=order_id or self.order_id, cart=self.cart,
            verified_prices=self.catalog, shipping_yen=900,
            location_id=self.location_id,
        )

    def link(self):
        return {
            "url": "https://checkout.square.site/test-payment-page",
            "square_order_id": "sq-order-test001",
            "square_link_id": "sq-link-test001",
        }

    def sign(self, *, event_id="evt1", amount=85900, status="COMPLETED", currency="JPY",
             square_order_id="sq-order-test001", location=None, event_type="payment.updated"):
        event = {
            "event_id": event_id, "type": event_type,
            "data": {"object": {"payment": {
                "status": status,
                "order_id": square_order_id,
                "location_id": location or self.location_id,
                "amount_money": {"amount": amount, "currency": currency},
            }}},
        }
        body = json.dumps(event, ensure_ascii=False).encode()
        url, key = "https://staging.invalid/api/shop/square/webhook", "sandbox-fake-signature-key"
        signature = base64.b64encode(
            hmac.new(key.encode(), url.encode()+body, hashlib.sha256).digest()
        ).decode()
        return dict(raw_body=body, signature_header=signature, signature_key=key, notification_url=url)

    def test_sandbox_link_transport_never_uses_production(self):
        payload, amount = self.prepare()
        self.assertEqual(amount, 85900)
        calls = []

        def fake_open(req, timeout):
            calls.append((req, timeout))
            return FakeResponse(json.dumps({"payment_link": {
                "id": "sq-link-test001", "order_id": "sq-order-test001",
                "long_url": "https://checkout.square.site/test-payment-page",
            }}).encode())
        result = create_square_sandbox_payment_link(payload, token="FAKE_SANDBOX_TOKEN", opener=fake_open)
        self.assertEqual(result, self.link())
        request, timeout = calls[0]
        self.assertEqual(request.full_url, SANDBOX_ENDPOINT)
        self.assertIn("squareupsandbox.com", request.full_url)
        self.assertNotEqual(request.full_url, "https://connect.squareup.com/v2/online-checkout/payment-links")
        self.assertEqual(timeout, 12)
        self.assertEqual(request.get_method(), "POST")
        self.assertIn("Bearer FAKE_SANDBOX_TOKEN", request.get_header("Authorization"))
        body = json.loads(request.data)
        self.assertEqual(body["order"]["line_items"][-1]["name"], "送料")
        self.assertEqual(body["order"]["line_items"][-1]["base_price_money"]["amount"], 900)

    def test_no_token_no_request_and_no_url_injection(self):
        payload, _ = self.prepare()

        def never_call(*_args, **_kwargs):
            self.fail("network must not be called")

        with self.assertRaises(SquareSandboxError):
            create_square_sandbox_payment_link(payload, token="", opener=never_call)

        def malicious(_req, timeout):
            return FakeResponse(json.dumps({"payment_link": {
                "id": "evil", "order_id": "sq-order-test001", "url": "https://evil.example/steal"
            }}).encode())
        with self.assertRaises(SquareSandboxError):
            create_square_sandbox_payment_link(payload, token="fake", opener=malicious)

    def test_network_errors_cannot_mark_paid(self):
        payload, _ = self.prepare()

        def failure(_req, timeout):
            raise URLError("temporary fake error")

        with self.assertRaises(SquareSandboxError):
            create_square_sandbox_payment_link(payload, token="fake", opener=failure)
        self.assertEqual(self.db.status(self.order_id), "created")

    def test_saved_link_and_idempotent_webhook(self):
        self.prepare()
        self.assertEqual(self.db.status(self.order_id), "created")
        self.db.save_link(self.order_id, self.link())
        self.db.save_link(self.order_id, self.link())
        self.assertEqual(self.db.status(self.order_id), "payment_pending")
        self.assertEqual(self.db.accept_webhook(**self.sign()), "paid")
        self.assertEqual(self.db.status(self.order_id), "paid")
        self.assertEqual(self.db.accept_webhook(**self.sign()), "duplicate")
        with self.assertRaises(ValueError):
            self.db.save_link(self.order_id, self.link())

    def test_rejects_wrong_payment_without_settling(self):
        self.prepare()
        self.db.save_link(self.order_id, self.link())
        cases = [
            dict(event_id="wrong-amount", amount=85901),
            dict(event_id="wrong-currency", currency="USD"),
            dict(event_id="pending", status="PENDING"),
            dict(event_id="wrong-location", location="wrong-test-location"),
            dict(event_id="wrong-order", square_order_id="other-square-order"),
            dict(event_id="wrong-event", event_type="order.updated"),
        ]
        for item in cases:
            with self.subTest(item=item):
                status = self.db.accept_webhook(**self.sign(**item))
                self.assertIn(status, ("ignored", "unmatched"))
                self.assertEqual(self.db.status(self.order_id), "payment_pending")

    def test_invalid_signature_refused(self):
        self.prepare()
        self.db.save_link(self.order_id, self.link())
        args = self.sign()
        args["signature_header"] = "altered-signature"
        with self.assertRaises(ValueError):
            self.db.accept_webhook(**args)
        self.assertEqual(self.db.status(self.order_id), "payment_pending")

    def test_unknown_event_then_link_commit_recovers(self):
        self.prepare()
        signed = self.sign()
        self.assertEqual(self.db.accept_webhook(**signed), "unmatched")
        self.db.save_link(self.order_id, self.link())
        self.assertEqual(self.db.accept_webhook(**signed), "paid")

    def test_no_duplicate_orders_or_multiple_square_link_changes(self):
        self.prepare()
        with self.assertRaises(Exception):
            self.prepare()
        self.db.save_link(self.order_id, self.link())
        with self.assertRaises(ValueError):
            self.db.save_link(self.order_id, {
                **self.link(), "square_link_id": "another-link"
            })
        self.assertEqual(self.db.status(self.order_id), "payment_pending")


if __name__ == "__main__":
    unittest.main()
