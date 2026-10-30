"""Production checkout request boundary: all calls use SYNTHETIC Square fakes.

The public BIG PAW site is never mounted to this module. No network, email,
real customer data, credit-card charges or production Square credentials.
"""
from copy import deepcopy
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Lock
import time
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shop_payments.live_checkout_controller import checkout_live_request
from shop_payments.live_checkout_intent import LiveCheckoutIntent
from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.retail_launch_guard import load_and_check, REQUIRED
from shop_payments.square_live_checkout_adapter import ENDPOINT as POST_ENDPOINT
from shop_payments.square_live_readonly import ENDPOINT as GET_ENDPOINT

ORIGIN = "https://shop.example.invalid"
CSRF = "test-only-csrf-key-at-least-40-characters-1234567890"
SESSION = "test_session_opaque_id_1234567890"
ORDER_SECRET = "test-only-server-hmac-order-identity-secret-123456"
ATTEMPT = "12345678-1234-4234-8234-123456789abc"
TERMS = hashlib.sha256(b"Test mock signed legal terms, not real policy").hexdigest()
LOCATION = "SYNTHETICLOCATION1234"
SQUARE_ORDER = "SYNTHETICSQUAREORDER123456"
LINK_ID = "SYNTHETICPAYMENTLINK123456"
LINK_URL = "https://square.link/u/NEVER_REAL"
TOKEN = "NOT_A_REAL_SQUARE_PRODUCTION_TOKEN_1234"


class SquareResponse:
    def __init__(self, data, status=200):
        self.body = json.dumps(data).encode()
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, size):
        return self.body[:size]


class CheckoutBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "no-live-payment.sqlite"
        self.ledger = LiveOrderLedger(self.path)
        self.intent = LiveCheckoutIntent(self.ledger)
        self.sku, self.product = next(iter(load_sale_catalog().items()))
        self.cart = {self.sku: 1}
        self.calls = []
        self.status = {
            "business_structure": "individual_proprietor",
            "sandbox_only": True,
            "public_live_checkout_enabled": False,
            "launch_checks": {key: True for key in REQUIRED},
        }
        self.env = {
            "BIGPAW_ENV": "live",
            "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "1",
            "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "1",
            "BIGPAW_SHOP_APPROVED_TERMS_SHA256": TERMS,
            "BIGPAW_SQUARE_LIVE_ACCESS_TOKEN": TOKEN,
            "BIGPAW_SQUARE_LIVE_LOCATION_ID": LOCATION,
        }
        self.body = json.dumps({
            "attempt_id": ATTEMPT,
            "cart": self.cart,
            "terms_sha256": TERMS,
        }).encode()
        self.square_total = self.product.sale_price_yen
        self.square_order = SQUARE_ORDER
        self.square_link_id = LINK_ID

    def fake_post(self, request, timeout):
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(request.full_url, POST_ENDPOINT)
        self.assertEqual(request.headers["Authorization"], "Bearer " + TOKEN)
        self.assertEqual(timeout, 12)
        data = json.loads(request.data)
        self.assertEqual(data["order"]["location_id"], LOCATION)
        self.assertEqual(data["order"]["line_items"][0]
                         ["base_price_money"]["amount"], self.product.sale_price_yen)
        self.calls.append(("POST", POST_ENDPOINT))
        return SquareResponse({
            "payment_link": {"id": self.square_link_id, "order_id": self.square_order,
                             "url": LINK_URL},
        }, 201)

    def fake_get(self, request, timeout):
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(request.full_url,
                         GET_ENDPOINT + "/orders/" + self.square_order)
        self.assertEqual(request.headers["Authorization"], "Bearer " + TOKEN)
        self.assertEqual(timeout, 10)
        self.calls.append(("GET", GET_ENDPOINT + "/orders/" + self.square_order))
        return SquareResponse({"order": {
            "id": self.square_order,
            "state": "OPEN",
            "location_id": LOCATION,
            "total_money": {"amount": self.square_total, "currency": "JPY"},
        }})

    def send(self, **kwargs):
        args = dict(
            intent=self.intent, raw_body=self.body,
            origin=ORIGIN, allowed_origin=ORIGIN,
            csrf_header=CSRF, server_csrf=CSRF,
            trusted_session_id=SESSION, server_order_secret=ORDER_SECRET,
            launch_status=self.status, private_env=self.env,
            post_opener=self.fake_post, get_opener=self.fake_get,
        )
        args.update(kwargs)
        return checkout_live_request(**args)

    def test_actual_repository_manifest_blocks_before_sql_or_square(self):
        ready, pending = load_and_check()
        self.assertFalse(ready)
        self.assertIn("proprietor_approval", pending)
        with self.assertRaises(LiveOrderBlocked):
            self.send(launch_status={
                "business_structure": "individual_proprietor",
                "sandbox_only": True, "public_live_checkout_enabled": False,
                "launch_checks": {key: False for key in REQUIRED},
            })
        self.assertEqual(self.calls, [])
        self.assertFalse(self.path.exists())

    def test_complete_synthetic_approval_makes_exactly_one_post_then_get(self):
        result = self.send()
        self.assertEqual(result["checkout_url"], LINK_URL)
        self.assertEqual(result["amount_yen"], self.product.sale_price_yen)
        self.assertEqual(result["shipping_yen"], 0)
        self.assertRegex(result["order_id"], r"^FOOD[0-9a-f]{32}$")
        self.assertEqual(self.ledger.status(result["order_id"])["state"],
                         "checkout_recorded")
        self.assertEqual(self.intent.status(result["order_id"])["state"],
                         "link_bound")
        self.assertEqual(self.calls, [
            ("POST", POST_ENDPOINT),
            ("GET", GET_ENDPOINT + "/orders/" + SQUARE_ORDER),
        ])
        raw = self.path.read_bytes()
        for secret in (TOKEN, CSRF, ORDER_SECRET, "REAL BUYER",
                       "test@example.invalid"):
            self.assertNotIn(secret.encode(), raw)
        self.calls.clear()
        with self.assertRaises(LiveOrderBlocked):
            self.send()
        self.assertEqual(self.calls, [], "duplicate checkout must not make Square POST")

    def test_no_approval_env_or_final_terms_never_write_anything(self):
        for name, changed in (
            ("environment-off", {"BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "0"}),
            ("not-owner-approved", {"BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "0"}),
            ("wrong-environment", {"BIGPAW_ENV": "sandbox"}),
            ("missing-terms", {"BIGPAW_SHOP_APPROVED_TERMS_SHA256": ""}),
            ("missing-location", {"BIGPAW_SQUARE_LIVE_LOCATION_ID": ""}),
            ("missing-token", {"BIGPAW_SQUARE_LIVE_ACCESS_TOKEN": ""}),
        ):
            with self.subTest(name=name):
                with self.assertRaises(LiveOrderBlocked):
                    self.send(private_env={**self.env, **changed})
                self.assertFalse(self.path.exists())
        self.assertEqual(self.calls, [])

    def test_request_parser_refuses_tampering_before_any_external_call(self):
        edits = (
            {"cart": {self.sku: True}},
            {"cart": {self.sku: 0}},
            {"cart": {self.sku: 11}},
            {"cart": {"MADEUP": 1}},
            {"attempt_id": "NOTUUID"},
            {"terms_sha256": "0" * 64},
            {"amount_yen": 1},
        )
        for edited in edits:
            with self.subTest(edit=edited):
                original = json.loads(self.body)
                original.update(edited)
                with self.assertRaises(LiveOrderBlocked):
                    self.send(raw_body=json.dumps(original).encode())
        with self.assertRaises(LiveOrderBlocked):
            self.send(raw_body=b'{"cart":{},"cart":{},"attempt_id":"x","terms_sha256":"x"}')
        for invalid in (b'null', b'[]', b'{not-json}', b"x" * 4097, b''):
            with self.subTest(raw=invalid[:20]), self.assertRaises(LiveOrderBlocked):
                self.send(raw_body=invalid)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.path.exists())

    def test_origin_csrf_and_server_session_binding_required(self):
        invalid = (
            {"origin": "https://wrong.example.invalid"},
            {"allowed_origin": "http://shop.example.invalid",
             "origin": "http://shop.example.invalid"},
            {"csrf_header": "mismatched-csrf-header-test-123456789012345"},
            {"server_csrf": ""},
            {"trusted_session_id": "browser-made-up"},
            {"server_order_secret": "short"},
        )
        for change in invalid:
            with self.subTest(change=change), self.assertRaises(LiveOrderBlocked):
                self.send(**change)
        self.assertFalse(self.path.exists())
        self.assertEqual(self.calls, [])

    def test_same_client_attempt_from_another_server_session_is_different_order(self):
        first = self.send()
        # Simulate another buyer session with same attempt ID. Must not
        # disclose or re-use the other session's checkout order number.
        # Use an independent synthetic Square response to avoid conflict.
        self.calls.clear()
        self.square_order = "SECONDSESSIONORDER123456"
        self.square_link_id = "SECONDSESSIONLINK123456"
        other = self.send(
            trusted_session_id="another_session_opaque_1234567890"
        )
        self.assertNotEqual(first["order_id"], other["order_id"])
        self.assertEqual(len(self.calls), 2)

    def test_square_timeout_is_unknown_and_retry_remains_blocked(self):
        attempts = []
        def timeout(request, timeout):
            attempts.append(1)
            raise TimeoutError("synthetic connection loss")
        with self.assertRaises(LiveOrderBlocked):
            self.send(post_opener=timeout)
        self.assertEqual(len(attempts), 1)
        with self.assertRaises(LiveOrderBlocked):
            self.send()
        self.assertEqual(len(attempts), 1)
        self.assertEqual(self.calls, [])

    def test_parallel_same_checkout_attempt_one_square_post_only(self):
        """12 simultaneous shopper requests: only one irreversible POST claim."""
        n = 12
        barrier = Barrier(n)
        lock = Lock()
        post_count = []
        def delayed_square_post(request, timeout):
            with lock:
                post_count.append(request.data)
            time.sleep(0.09)
            return SquareResponse({
                "payment_link": {
                    "id": LINK_ID, "order_id": SQUARE_ORDER, "url": LINK_URL
                }
            }, 201)
        def caller(_):
            barrier.wait(timeout=5)
            try:
                return ("ok", self.send(post_opener=delayed_square_post))
            except LiveOrderBlocked:
                return ("blocked", None)
        with ThreadPoolExecutor(max_workers=n) as pool:
            results = list(pool.map(caller, range(n)))
        self.assertEqual(sum(x[0] == "ok" for x in results), 1)
        self.assertEqual(sum(x[0] == "blocked" for x in results), n-1)
        self.assertEqual(len(post_count), 1,
                         "parallel double click must never issue multiple links")
        self.assertEqual(self.calls, [
            ("GET", GET_ENDPOINT + "/orders/" + SQUARE_ORDER),
        ])
        order_id = next(x[1]["order_id"] for x in results if x[0] == "ok")
        self.assertEqual(self.ledger.status(order_id)["state"], "checkout_recorded")
        self.assertEqual(self.intent.status(order_id)["state"], "link_bound")
        before = len(post_count)
        for _ in range(3):
            with self.assertRaises(LiveOrderBlocked):
                self.send(post_opener=delayed_square_post)
        self.assertEqual(len(post_count), before)

    def test_get_connection_drop_after_one_post_requires_manual_binding(self):
        """POST may succeed while GET fails; automated retries remain blocked."""
        calls = []
        def fake_post(req, timeout):
            calls.append("POST")
            return SquareResponse({"payment_link": {
                "id": LINK_ID, "order_id": SQUARE_ORDER, "url": LINK_URL,
            }}, 201)
        def get_disconnect(req, timeout):
            calls.append("GET_LOST")
            raise TimeoutError("synthetic Square GET interrupted")
        with self.assertRaises(LiveOrderBlocked):
            self.send(post_opener=fake_post, get_opener=get_disconnect)
        self.assertEqual(calls, ["POST", "GET_LOST"])
        with self.assertRaises(LiveOrderBlocked):
            self.send(post_opener=fake_post)
        self.assertEqual(calls, ["POST", "GET_LOST"],
                         "retry never creates another Square link")
        import sqlite3
        with sqlite3.connect(self.path) as db:
            order_id = db.execute(
                "SELECT order_id FROM food_live_checkout_intent"
            ).fetchone()[0]
        self.assertEqual(self.intent.status(order_id)["state"], "attempt_unknown")
        self.assertEqual(self.ledger.status(order_id)["state"], "not_found")
        # Only a deliberate admin investigation of the EXISTING Square result
        # is allowed; the recovery performs Square GET, never another POST.
        result = self.intent.bind_square_result(
            order_id=order_id,
            link={"id": LINK_ID, "order_id": SQUARE_ORDER, "url": LINK_URL},
            api_key=TOKEN, opener=self.fake_get,
        )
        self.assertEqual(result, {"state":"link_bound","new_binding":True})
        self.assertEqual(self.intent.status(order_id)["state"], "link_bound")
        self.assertEqual(self.ledger.status(order_id)["state"], "checkout_recorded")
        with self.assertRaises(LiveOrderBlocked):
            self.send(post_opener=fake_post)
        self.assertEqual(calls, ["POST", "GET_LOST"])

    def test_square_get_price_mismatch_is_not_committed_to_order_ledger(self):
        self.square_total += 1
        with self.assertRaises(LiveOrderBlocked):
            self.send()
        self.assertEqual(self.calls, [
            ("POST", POST_ENDPOINT),
            ("GET", GET_ENDPOINT + "/orders/" + SQUARE_ORDER),
        ])
        with self.assertRaises(LiveOrderBlocked):
            self.send()
        self.assertEqual(len(self.calls), 2)


if __name__ == "__main__":
    unittest.main()
