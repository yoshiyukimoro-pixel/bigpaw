"""Complete synthetic checkout -> Square signed payment -> one private order ledger.

ALL external Square traffic is intercepted. Real production manifest stays
disabled; no real credentials, emails, refunds, shipments or deployments.
"""
import base64
import hashlib
import hmac
import io
import json
from pathlib import Path
import sqlite3
import sys
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "backend"))
import shop_live_checkout_bridge as checkout
import shop_live_webhook_bridge as webhook

from shop_payments.live_order_ledger import LiveOrderLedger
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.retail_launch_guard import REQUIRED
from shop_payments.square_live_checkout_adapter import ENDPOINT as LINK_POST
from shop_payments.square_live_readonly import ENDPOINT as SQUARE_GET

SITE = "https://bigpaw.site"
WEBHOOK_PATH = "/api/shop/square-webhook"
WEBHOOK_URL = SITE + WEBHOOK_PATH
SQUARE_ORDER = "SYNTHETICFULLPIPELINEORDER123456"
PAYMENT = "SYNTHETICFULLPIPELINEPAYMENT123456"
LINK_ID = "SYNTHETICFULLPIPELINELINK123456"
LINK_URL = "https://square.link/u/TEST_ONLY"
LOCATION = "SYNTHETICFULLPIPELINELOCATION1234"
BUYER_SESSION = "synthetic_checkout_buyer_session_1234567890"
BUYER = "fake_buyer_session_owner"
SECRET = "synthetic-bigpaw-order-secret-not-for-production-1234"
WEBHOOK_SECRET = "synthetic-square-signature-key-not-for-production-1234"
API_KEY = "synthetic-square-production-token-NOT-REAL-1234"
SKU, PRODUCT = next(iter(load_sale_catalog().items()))
TOTAL = PRODUCT.sale_price_yen
ATTEMPT = "12345678-1234-4234-8234-123456789abc"
TERMS_HASH = hashlib.sha256(b"SYNTHETIC APPROVAL").hexdigest()


class Response:
    def __init__(self, body, status=200):
        self.status = status
        self.data = json.dumps(body).encode()
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, size):
        return self.data[:size]


class BuyerHandler:
    path = "/api/shop/checkout"
    def __init__(self, raw):
        self.headers = {
            "Host": "bigpaw.site", "Origin": SITE,
            "Sec-Fetch-Site": "same-origin",
            "Content-Type": "application/json",
            "Content-Length": str(len(raw)),
            "Cookie": "bigpaw_session=" + BUYER_SESSION,
            "X-Shop-CSRF": checkout._csrf(SECRET, BUYER_SESSION, BUYER),
        }
        self.rfile = io.BytesIO(raw)
        self.responses = []
    def current_user(self):
        return {"id": BUYER, "role": "buyer"}
    def send_json(self, obj, code=200):
        self.responses.append((code, obj))
    @property
    def code(self):
        return self.responses[-1][0]


class WebhookHandler:
    path = WEBHOOK_PATH
    def __init__(self, raw, signature):
        self.headers = {
            "Host": "bigpaw.site",
            "Content-Type": "application/json",
            "Content-Length": str(len(raw)),
            "X-Square-Hmacsha256-Signature": signature,
        }
        self.rfile = io.BytesIO(raw)
        self.responses = []
    def send_json(self, obj, code=200):
        self.responses.append((code, obj))
    @property
    def code(self):
        return self.responses[-1][0]


class FullSyntheticOrderPipelineTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.private = Path(tmp.name)
        self.ledger = LiveOrderLedger(self.private / "bigpaw-shop-live-orders.sqlite3")
        self.status = {
            "business_structure": "individual_proprietor",
            "sandbox_only": True,
            "public_live_checkout_enabled": False,
            "launch_checks": {key: True for key in REQUIRED},
        }
        self.env = {
            "BIGPAW_ENV": "production",
            "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "1",
            "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "1",
            "BIGPAW_SHOP_ORDER_HMAC_SECRET": SECRET,
            "BIGPAW_SHOP_APPROVED_TERMS_SHA256": TERMS_HASH,
            "BIGPAW_SQUARE_LIVE_ACCESS_TOKEN": API_KEY,
            "BIGPAW_SQUARE_LIVE_LOCATION_ID": LOCATION,
            "BIGPAW_SHOP_SQUARE_LIVE_WEBHOOK_ENABLED": "1",
            "BIGPAW_SQUARE_LIVE_WEBHOOK_URL": WEBHOOK_URL,
            "BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY": WEBHOOK_SECRET,
        }
        self.posts = []
        self.gets = []
        self.payment = {
            "id": PAYMENT, "order_id": SQUARE_ORDER,
            "location_id": LOCATION, "status": "COMPLETED",
            "amount_money": {"amount": TOTAL, "currency": "JPY"},
            "refunded_money": {"amount": 0, "currency": "JPY"},
        }
        self.order = {
            "id": SQUARE_ORDER, "location_id": LOCATION,
            "state": "OPEN", "total_money": {"amount": TOTAL, "currency": "JPY"},
            "fulfillments": [{
                "type": "SHIPMENT",
                "shipment_details": {"recipient": {
                    "display_name": "FAKE BUYER NEVER SEND",
                    "email_address": "fake@example.invalid",
                    "address": {
                        "country": "JP", "postal_code": "000-0000",
                        "address_line_1": "SYNTHETIC SHIPPING ADDRESS",
                    },
                }},
            }],
        }

    def post(self, req, timeout):
        self.assertEqual((req.get_method(), req.full_url),
                         ("POST", LINK_POST))
        self.assertEqual(timeout, 12)
        self.posts.append(req.full_url)
        payload = json.loads(req.data)
        self.assertEqual(payload["order"]["location_id"], LOCATION)
        self.assertEqual(payload["order"]["line_items"][0][
            "base_price_money"]["amount"], TOTAL)
        return Response({"payment_link": {
            "id": LINK_ID, "order_id": SQUARE_ORDER, "url": LINK_URL,
        }}, status=201)

    def get(self, req, timeout):
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(timeout, 10)
        self.assertEqual(req.headers["Authorization"], "Bearer " + API_KEY)
        self.gets.append(req.full_url)
        if req.full_url == SQUARE_GET + "/orders/" + SQUARE_ORDER:
            return Response({"order": self.order})
        if req.full_url == SQUARE_GET + "/payments/" + PAYMENT:
            return Response({"payment": self.payment})
        self.fail("Unexpected Square API request")

    def new_buyer(self):
        raw = json.dumps({
            "attempt_id": ATTEMPT,
            "terms_sha256": TERMS_HASH,
            "cart": {SKU: 1},
        }).encode()
        return BuyerHandler(raw)

    def signed_notice(self, changes=None):
        event = {
            "event_id": "SYNTHETIC_NEW_PAID_EVENT_123456",
            "type": "payment.updated",
            "data": {"object": {"payment": {
                "id": PAYMENT, "order_id": SQUARE_ORDER,
                "location_id": LOCATION, "status": "COMPLETED",
                "amount_money": {"amount": TOTAL, "currency": "JPY"},
            }}},
        }
        if changes:
            event["data"]["object"]["payment"].update(changes)
        raw = json.dumps(event, separators=(",", ":")).encode()
        signature = base64.b64encode(
            hmac.new(WEBHOOK_SECRET.encode(), WEBHOOK_URL.encode() + raw,
                     hashlib.sha256).digest()
        ).decode()
        return WebhookHandler(raw, signature)

    def buy(self, env=None, status=None):
        handler = self.new_buyer()
        checkout.handle_post(
            handler, env=self.env if env is None else env,
            base_url=SITE, data_dir=self.private,
            launch_status=self.status if status is None else status,
            rate_limited=lambda *args: False,
            post_opener=self.post, get_opener=self.get,
        )
        return handler

    def signed_payment(self, env=None, status=None, handler=None):
        handler = self.signed_notice() if handler is None else handler
        webhook.handle_post(
            handler, env=self.env if env is None else env,
            base_url=SITE, data_dir=self.private,
            launch_status=self.status if status is None else status,
            square_get_opener=self.get,
        )
        return handler

    def test_buyer_to_signed_paid_and_replay_same_private_ledger(self):
        initial = self.buy()
        self.assertEqual(initial.code, 200)
        self.assertEqual(len(self.posts), 1)
        self.assertEqual(self.gets, [SQUARE_GET + "/orders/" + SQUARE_ORDER])
        order_id = initial.responses[-1][1]["order_id"]
        self.assertEqual(self.ledger.status(order_id)["state"], "checkout_recorded")
        self.assertEqual(initial.responses[-1][1]["checkout_url"], LINK_URL)

        # Shopper emergency shutoff occurs *before* the buyer finishes paying.
        env_closed = {**self.env, "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "0"}
        stopped = self.buy(env=env_closed)
        self.assertEqual(stopped.code, 404)
        self.assertEqual(stopped.rfile.tell(), 0)
        self.assertEqual(len(self.posts), 1)

        # Signed payment confirmation STILL works for the prior order.
        receipt = self.signed_payment(env=env_closed)
        self.assertEqual(receipt.responses[-1], (200, {"ok": True}))
        self.assertEqual(self.ledger.status(order_id)["state"], "paid_verified")
        self.assertEqual(self.gets[-2:], [
            SQUARE_GET + "/payments/" + PAYMENT,
            SQUARE_GET + "/orders/" + SQUARE_ORDER,
        ])
        replay = self.signed_payment(env=env_closed)
        self.assertEqual(replay.responses[-1], (200, {"ok": True}))
        self.assertEqual(self.ledger.status(order_id)["state"], "paid_verified")
        self.assertEqual(len(self.posts), 1)
        with sqlite3.connect(self.ledger.db_file) as conn:
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM food_live_checkout_intent"
            ).fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM food_live_order_ledger"
            ).fetchone()[0], 1)
            self.assertEqual(conn.execute(
                "SELECT COUNT(*) FROM food_live_signed_payment_events"
            ).fetchone()[0], 1)
        contents = Path(self.ledger.db_file).read_bytes()
        for forbidden in (
            API_KEY, WEBHOOK_SECRET, "FAKE BUYER NEVER SEND",
            "SYNTHETIC SHIPPING ADDRESS", "fake@example.invalid",
        ):
            self.assertNotIn(forbidden.encode(), contents)

    def test_refund_and_bad_signature_after_purchase_cannot_mark_paid(self):
        buy = self.buy()
        self.assertEqual(buy.code, 200)
        id_ = buy.responses[-1][1]["order_id"]
        env = {**self.env, "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "0"}
        self.payment["refunded_money"]["amount"] = TOTAL
        self.assertEqual(self.signed_payment(env=env).code, 503)
        self.assertEqual(self.ledger.status(id_)["state"], "checkout_recorded")
        h = self.signed_notice()
        h.headers["X-Square-Hmacsha256-Signature"] = "A" * 43 + "="
        before = len(self.gets)
        self.assertEqual(self.signed_payment(env=env, handler=h).code, 401)
        self.assertEqual(len(self.gets), before)

    def test_unconfigured_actual_manifest_never_makes_any_payment(self):
        from shop_payments.retail_launch_guard import load_and_check
        ready, missing = load_and_check()
        self.assertFalse(ready)
        self.assertTrue(missing)
        buyer = self.buy(status={
            **self.status,
            "launch_checks": {
                **self.status["launch_checks"], "proprietor_approval": False,
            },
        })
        self.assertEqual(buyer.code, 404)
        self.assertEqual(len(self.posts), 0)
        self.assertFalse(Path(self.ledger.db_file).exists())
        # Incoming events without the explicit operator Square configuration
        # cannot read a body or initialize an empty private DB.
        h = self.signed_notice()
        self.assertEqual(self.signed_payment(env={
            **self.env,
            "BIGPAW_SHOP_SQUARE_LIVE_WEBHOOK_ENABLED": "0",
        }, handler=h).code, 404)
        self.assertEqual(h.rfile.tell(), 0)
        self.assertFalse(Path(self.ledger.db_file).exists())


if __name__ == "__main__":
    unittest.main()
