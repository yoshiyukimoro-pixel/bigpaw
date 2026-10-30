"""Synthetic-only end-to-end HTTP tests for DORMANT signed Square live webhook.

Never calls real Square; fake Square GET verifies the existing private ledger.
Checked-in manifest never permits requests, and real production app is NOT
deployed or configured with these synthetic credentials.
"""
from copy import deepcopy
import base64
import hashlib
import hmac
import io
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "backend"))
import shop_live_webhook_bridge as bridge

from shop_payments.live_order_ledger import LiveOrderLedger
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.retail_launch_guard import REQUIRED
from shop_payments.square_live_readonly import ENDPOINT as SQUARE_ENDPOINT

SITE = "https://bigpaw.site"
PATH = "/api/shop/square-webhook"
URL = SITE + PATH
TOKEN = "SYNTHETIC_NO_REAL_SQUARE_TOKEN_123456789"
SECRET = "SYNTHETIC_NO_REAL_SIGNATURE_SECRET_123456789"
ORDER = "FOOD" + "a" * 32
SQUARE_ORDER = "SYNTHETICSQUAREORDER123456"
SQUARE_LOCATION = "SYNTHETICSQUARELOCATION1234"
PAYMENT_ID = "SYNTHETICSQUAREPAYMENT12345"
SKU, PRODUCT = next(iter(load_sale_catalog().items()))


class Response:
    status = 200
    def __init__(self, obj):
        self.raw = json.dumps(obj).encode()
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, n):
        return self.raw[:n]


class FakeHandler:
    def __init__(self, raw, signature):
        self.path = PATH
        self.headers = {
            "Host": "bigpaw.site",
            "Content-Type": "application/json",
            "Content-Length": str(len(raw)),
            "X-Square-Hmacsha256-Signature": signature,
        }
        self.rfile = io.BytesIO(raw)
        self.responses = []
    def send_json(self, data, status=200):
        self.responses.append((status, data))
    @property
    def code(self):
        return self.responses[-1][0]


class WebhookAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.private = Path(tmp.name)
        self.ledger_path = self.private / "bigpaw-shop-live-orders.sqlite3"
        self.env = {
            "BIGPAW_ENV": "production",
            "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "1",
            "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "1",
            "BIGPAW_SHOP_ORDER_HMAC_SECRET":
                "synthetic-shop-order-hmac-secret-123456789",
            "BIGPAW_SHOP_APPROVED_TERMS_SHA256": "a" * 64,
            "BIGPAW_SQUARE_LIVE_ACCESS_TOKEN": TOKEN,
            "BIGPAW_SQUARE_LIVE_LOCATION_ID": SQUARE_LOCATION,
            "BIGPAW_SHOP_SQUARE_LIVE_WEBHOOK_ENABLED": "1",
            "BIGPAW_SQUARE_LIVE_WEBHOOK_URL": URL,
            "BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY": SECRET,
        }
        self.approved = {
            "business_structure": "individual_proprietor",
            "sandbox_only": True,
            "public_live_checkout_enabled": False,
            "launch_checks": {key: True for key in REQUIRED},
        }
        self.event = {
            "event_id": "synthetic-webhook-event-123456",
            "type": "payment.updated",
            "data": {"object": {"payment": {
                "id": PAYMENT_ID, "order_id": SQUARE_ORDER,
                "location_id": SQUARE_LOCATION, "status": "COMPLETED",
                "amount_money": {
                    "currency": "JPY", "amount": PRODUCT.sale_price_yen},
            }}},
        }
        self.payment = {
            "id": PAYMENT_ID, "order_id": SQUARE_ORDER,
            "location_id": SQUARE_LOCATION, "status": "COMPLETED",
            "amount_money": {
                "currency": "JPY", "amount": PRODUCT.sale_price_yen},
            "refunded_money": {"amount": 0, "currency": "JPY"},
        }
        self.order = {
            "id": SQUARE_ORDER, "location_id": SQUARE_LOCATION,
            "state": "OPEN",
            "total_money": {"amount": PRODUCT.sale_price_yen,
                            "currency": "JPY"},
            "fulfillments": [{
                "type": "SHIPMENT",
                "shipment_details": {"recipient": {
                    "display_name": "SYNTHETIC NEVER REAL",
                    "email_address": "buyer@example.invalid",
                    "address": {"country": "JP", "postal_code": "000-0000",
                                "address_line_1": "NOT REAL"},
                }},
            }],
        }
        self.gets = []

    def fake_get(self, req, timeout):
        self.assertEqual(req.get_method(), "GET",
                         "No Square POST is allowed in this test")
        self.assertEqual(timeout, 10)
        self.assertEqual(req.headers["Authorization"], "Bearer " + TOKEN)
        self.gets.append(req.full_url)
        if req.full_url == SQUARE_ENDPOINT + "/payments/" + PAYMENT_ID:
            return Response({"payment": self.payment})
        if req.full_url == SQUARE_ENDPOINT + "/orders/" + SQUARE_ORDER:
            return Response({"order": self.order})
        self.fail("Unexpected Square GET endpoint")

    def sign(self, event=None, url=URL):
        raw = json.dumps(self.event if event is None else event,
                         separators=(",", ":"), ensure_ascii=False).encode()
        signature = base64.b64encode(
            hmac.new(SECRET.encode(), url.encode() + raw,
                     hashlib.sha256).digest()
        ).decode()
        return raw, signature

    def handler(self, event=None):
        return FakeHandler(*self.sign(event=event))

    def invoke(self, handler, **kwargs):
        arguments = {
            "env": self.env, "base_url": SITE, "data_dir": self.private,
            "launch_status": self.approved,
            "square_get_opener": self.fake_get,
        }
        arguments.update(kwargs)
        self.assertTrue(bridge.handle_post(handler, **arguments))
        return handler.code

    def seed(self):
        ledger = LiveOrderLedger(self.ledger_path)
        ledger.register_checkout(
            order_id=ORDER, square_order_id=SQUARE_ORDER,
            location_id=SQUARE_LOCATION, cart={SKU: 1},
        )
        return ledger

    def test_unconfigured_webhook_rejects_before_body_db_or_square(self):
        h = self.handler()
        self.assertEqual(self.invoke(h, launch_status=None, env={
            **self.env, "BIGPAW_SHOP_SQUARE_LIVE_WEBHOOK_ENABLED": "0"
        }), 404)
        self.assertEqual(h.rfile.tell(), 0)
        self.assertFalse(self.ledger_path.exists())
        self.assertEqual(self.gets, [])
        # A correctly signed webhook must NOT bootstrap a new private DB.
        h2 = self.handler()
        self.assertEqual(self.invoke(h2, launch_status=None), 503)
        self.assertEqual(h2.rfile.tell(), len(self.sign()[0]))
        self.assertFalse(self.ledger_path.exists())
        self.assertEqual(self.gets, [])

    def test_requires_owner_approval_secret_url_and_exact_domain(self):
        bad_cases = [
            {"BIGPAW_SHOP_SQUARE_LIVE_WEBHOOK_ENABLED": "0"},
            {"BIGPAW_SQUARE_LIVE_WEBHOOK_URL": SITE + "/wrong"},
            {"BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY": "short"},
            {"BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "0"},
            {"BIGPAW_SQUARE_LIVE_ACCESS_TOKEN": ""},
        ]
        for changes in bad_cases:
            with self.subTest(changes=changes):
                h = self.handler()
                self.assertEqual(self.invoke(
                    h, env={**self.env, **changes}), 404)
                self.assertEqual(h.rfile.tell(), 0)
                self.assertEqual(self.gets, [])
                self.assertFalse(self.ledger_path.exists())
        # Checkout terms/state are intentionally not required for signed
        # reconciliation: preexisting links may be paid after shop closure.
        not_approved = deepcopy(self.approved)
        not_approved["launch_checks"]["proprietor_approval"] = False
        h = self.handler()
        self.assertEqual(self.invoke(h, launch_status=not_approved), 503)
        self.assertEqual(h.rfile.tell(), len(self.sign()[0]))
        self.assertEqual(self.gets, [])
        self.assertFalse(self.ledger_path.exists())

    def test_signed_payment_stays_verifiable_after_checkout_is_suspended(self):
        """Kill new purchases; honor already-issued link via Square GET only."""
        import shop_live_checkout_bridge as checkout
        from shop_payments.retail_launch_guard import REQUIRED
        ledger = self.seed()
        env = {**self.env, "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "0"}
        # New checkout is blocked even if owner approval remains in place.
        gated_status = {
            **self.approved,
            "launch_checks": {
                **self.approved["launch_checks"],
                "square_live_readiness": False,
            },
        }
        self.assertFalse(checkout._gate(env, SITE, gated_status))
        # The webhook's independent signature + exact URL + existing order
        # + Square independent GET allow a pending payment to be accounted for.
        h = self.handler()
        self.assertEqual(self.invoke(h, env=env,
                                     launch_status=gated_status), 200)
        self.assertEqual(ledger.status(ORDER)["state"], "paid_verified")
        self.assertEqual(len(self.gets), 2)
        self.assertEqual(self.invoke(self.handler(), env=env,
                                     launch_status=gated_status), 200)
        self.assertEqual(len(self.gets), 4)
        self.assertEqual(ledger.status(ORDER)["state"], "paid_verified")

        # Signing-key loss is different: no reliable authentication,
        # so incoming notifications must be rejected without reading.
        bad = self.handler()
        self.assertEqual(self.invoke(
            bad, env={**env,"BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY":""},
            launch_status=gated_status
        ), 404)
        self.assertEqual(bad.rfile.tell(), 0)
        self.assertEqual(len(self.gets), 4)

    def test_refunded_payment_not_accepted_after_checkout_suspension(self):
        ledger = self.seed()
        self.payment["refunded_money"]["amount"] = 1
        env = {**self.env, "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "0"}
        h = self.handler()
        self.assertEqual(self.invoke(h, env=env, launch_status=None), 503)
        self.assertEqual(ledger.status(ORDER)["state"], "checkout_recorded")
        self.assertEqual(len(self.gets), 1)

    def test_invalid_signature_host_origin_and_length_cannot_reach_ledger(self):
        mutations = (
            ("signature", lambda h: h.headers.update({
                "X-Square-Hmacsha256-Signature": "A" * 43 + "="}), 401),
            ("missing signature", lambda h: h.headers.pop(
                "X-Square-Hmacsha256-Signature"), 401),
            ("wrong host", lambda h: h.headers.update({
                "Host": "attacker.invalid"}), 403),
            ("wrong forwarded host", lambda h: h.headers.update({
                "X-Forwarded-Host": "attacker.invalid"}), 403),
            ("browser origin", lambda h: h.headers.update({
                "Origin": SITE}), 403),
            ("browser cookie", lambda h: h.headers.update({
                "Cookie": "bigpaw_session=bogus"}), 403),
            ("query path", lambda h: setattr(
                h, "path", PATH + "?order_id=injected"), 403),
            ("transfer encoding", lambda h: h.headers.update({
                "Transfer-Encoding": "chunked"}), 403),
            ("oversized length", lambda h: h.headers.update({
                "Content-Length": "256001"}), 413),
            ("bad content type", lambda h: h.headers.update({
                "Content-Type": "text/plain"}), 415),
        )
        for label, change, expected in mutations:
            with self.subTest(label=label):
                h = self.handler()
                change(h)
                self.assertEqual(self.invoke(h), expected)
                self.assertFalse(self.ledger_path.exists())
                self.assertEqual(self.gets, [])

    def test_valid_signed_payment_rechecks_square_and_deduplicates(self):
        ledger = self.seed()
        h = self.handler()
        self.assertEqual(self.invoke(h), 200)
        self.assertEqual(h.responses[-1], (200, {"ok": True}))
        self.assertEqual(ledger.status(ORDER)["state"], "paid_verified")
        self.assertEqual(self.gets, [
            SQUARE_ENDPOINT + "/payments/" + PAYMENT_ID,
            SQUARE_ENDPOINT + "/orders/" + SQUARE_ORDER,
        ])
        self.assertEqual(self.invoke(self.handler()), 200)
        self.assertEqual(len(self.gets), 4)
        import sqlite3
        with sqlite3.connect(self.ledger_path) as db:
            self.assertEqual(db.execute(
                "SELECT COUNT(*) FROM food_live_signed_payment_events"
            ).fetchone()[0], 1)
        all_bytes = self.ledger_path.read_bytes()
        for private in ("SYNTHETIC NEVER REAL", "NOT REAL",
                        "buyer@example.invalid", SECRET, TOKEN):
            self.assertNotIn(private.encode(), all_bytes)

    def test_unknown_or_refunded_or_mismatched_never_mark_paid(self):
        self.seed()
        self.payment["refunded_money"]["amount"] = 1
        h = self.handler()
        self.assertEqual(self.invoke(h), 503)
        self.assertEqual(LiveOrderLedger(self.ledger_path).status(ORDER)[
            "state"], "checkout_recorded")
        self.payment["refunded_money"]["amount"] = 0
        self.order["total_money"]["amount"] += 1
        self.assertEqual(self.invoke(self.handler()), 503)
        self.order["total_money"]["amount"] -= 1
        unknown = deepcopy(self.event)
        unknown["data"]["object"]["payment"]["order_id"] = "UNRECOGNIZED12345678"
        self.assertEqual(self.invoke(self.handler(unknown)), 409)
        self.assertEqual(LiveOrderLedger(self.ledger_path).status(ORDER)[
            "state"], "checkout_recorded")

    def test_nonpayment_and_pending_signed_events_ack_without_mark_paid(self):
        self.seed()
        other = deepcopy(self.event)
        other["type"] = "refund.updated"
        self.assertEqual(self.invoke(self.handler(other)), 200)
        pending = deepcopy(self.event)
        pending["event_id"] = "synthetic-pending-event-123456"
        pending["data"]["object"]["payment"]["status"] = "PENDING"
        self.assertEqual(self.invoke(self.handler(pending)), 200)
        self.assertEqual(self.gets, [])
        self.assertEqual(LiveOrderLedger(self.ledger_path).status(ORDER)[
            "state"], "checkout_recorded")

    def test_main_server_route_and_docker_imports_are_dormant(self):
        root = Path(__file__).resolve().parents[1]
        server = (root / "app/backend/server.py").read_text()
        self.assertIn("import shop_live_webhook_bridge as bp_shop_webhook", server)
        self.assertIn("bp_shop_webhook.handle_post(", server)
        self.assertLess(server.index("m=re.fullmatch(r'/api/inquiries/([^/]+)/messages',path)"),
                        server.index("bp_shop_webhook.handle_post("))
        docker = (root / "Dockerfile").read_text()
        self.assertIn("COPY shop_payments/ /app/shop_payments/", docker)


if __name__ == "__main__":
    unittest.main()
