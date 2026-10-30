"""Offline-only tests for the dormant BIG PAW live checkout HTTP adapter.

Every positive Square request is intercepted by fake adapters. Real production
manifest and app settings remain disabled, no external calls or live payments.
"""
import hashlib
import hmac
import io
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "backend"))
import shop_live_checkout_bridge as bridge

from shop_payments.retail_launch_guard import REQUIRED
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.square_live_checkout_adapter import ENDPOINT as POST_ENDPOINT
from shop_payments.square_live_readonly import ENDPOINT as GET_ENDPOINT

SITE = "https://bigpaw.site"
TOKEN = "THIS_IS_A_FAKE_LIVE_SQUARE_TOKEN_FOR_TEST"
LOCATION = "SYNTHETICLOCATION1234"
ORDER = "SYNTHETICSQUAREORDER123456"
LINK = "SYNTHETICPAYMENTLINK123456"
URL = "https://square.link/u/NEVER_REAL"
SECRET = "fake-shop-order-hmac-secret-at-least-32-characters"
SESSION = "test_session_cookie_1234567890abcdef_1234567890"
USER = "synthetic-buyer-123"
CART = next(iter(load_sale_catalog()))


class FakeResponse:
    def __init__(self, payload, status=200):
        self.data = json.dumps(payload).encode()
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, size):
        return self.data[:size]


class FakeHandler:
    def __init__(self, method="POST", body=b"{}", role="buyer", cookie=SESSION):
        self.path = "/api/shop/checkout" if method == "POST" else "/api/shop/checkout/config"
        self.headers = {
            "Host": "bigpaw.site",
            "Origin": SITE,
            "Sec-Fetch-Site": "same-origin",
            "Cookie": "bigpaw_session=" + cookie,
            "Content-Type": "application/json",
            "Content-Length": str(len(body)),
        }
        self.rfile = io.BytesIO(body)
        self.role = role
        self.responses = []
        self.auth_reads = 0
    def current_user(self):
        self.auth_reads += 1
        return {"role": self.role, "id": USER} if self.role is not None else None
    def send_json(self, data, code=200):
        self.responses.append((code, data))
    @property
    def code(self):
        return self.responses[-1][0]


class DormantCheckoutRouteTests(unittest.TestCase):
    def setUp(self):
        temporary = TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.status = {
            "business_structure": "individual_proprietor",
            "sandbox_only": True,
            "public_live_checkout_enabled": False,
            "launch_checks": {k: True for k in REQUIRED},
        }
        self.env = {
            "BIGPAW_ENV": "production",
            "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "1",
            "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "1",
            "BIGPAW_SHOP_ORDER_HMAC_SECRET": SECRET,
            "BIGPAW_SHOP_APPROVED_TERMS_SHA256": hashlib.sha256(
                b"FAKE APPROVED TEXT FOR OFFLINE TEST").hexdigest(),
            "BIGPAW_SQUARE_LIVE_ACCESS_TOKEN": TOKEN,
            "BIGPAW_SQUARE_LIVE_LOCATION_ID": LOCATION,
        }
        self.events = []
        self.amount = load_sale_catalog()[CART].sale_price_yen

    def fake_post(self, request, timeout):
        self.assertEqual((request.get_method(), request.full_url),
                         ("POST", POST_ENDPOINT))
        self.assertEqual(timeout, 12)
        self.events.append("POST")
        value = json.loads(request.data)
        self.assertEqual(value["order"]["line_items"][0][
            "base_price_money"]["amount"], self.amount)
        return FakeResponse({"payment_link": {
            "id": LINK, "order_id": ORDER, "url": URL
        }}, 201)

    def fake_get(self, request, timeout):
        self.assertEqual((request.get_method(), request.full_url),
                         ("GET", GET_ENDPOINT + "/orders/" + ORDER))
        self.events.append("GET")
        return FakeResponse({"order": {
            "id": ORDER, "location_id": LOCATION,
            "state": "OPEN",
            "total_money": {"currency": "JPY", "amount": self.amount},
        }}, 200)

    def request(self, handler, **override):
        args = {
            "env": self.env, "base_url": SITE, "data_dir": self.root,
            "launch_status": self.status,
            "rate_limited": lambda *args: False,
            "post_opener": self.fake_post, "get_opener": self.fake_get,
        }
        args.update(override)
        return bridge.handle_post(handler, **args)

    def make_body(self):
        return json.dumps({
            "attempt_id": "12345678-1234-4234-8234-123456789abc",
            "terms_sha256": self.env["BIGPAW_SHOP_APPROVED_TERMS_SHA256"],
            "cart": {CART: 1},
        }).encode()

    def test_actual_checked_in_manifest_blocks_before_cookie_or_body_or_db(self):
        h = FakeHandler(body=self.make_body())
        self.request(h, launch_status=None)
        self.assertEqual(h.code, 404)
        self.assertEqual(h.rfile.tell(), 0)
        self.assertEqual(h.auth_reads, 0)
        self.assertEqual(self.events, [])
        self.assertFalse(list(self.root.iterdir()))
        cfg = FakeHandler(method="GET")
        bridge.handle_get(cfg, env=self.env, base_url=SITE)
        self.assertEqual(cfg.code, 404)
        self.assertEqual(cfg.auth_reads, 0)

    def test_no_approval_flags_or_secret_never_create_db_or_square_post(self):
        variations = (
            {"BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "0"},
            {"BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "0"},
            {"BIGPAW_ENV": "sandbox"},
            {"BIGPAW_SHOP_ORDER_HMAC_SECRET": "too-short"},
            {"BIGPAW_SHOP_APPROVED_TERMS_SHA256": ""},
            {"BIGPAW_SQUARE_LIVE_ACCESS_TOKEN": ""},
        )
        for diff in variations:
            with self.subTest(diff=diff):
                h = FakeHandler(body=self.make_body())
                self.request(h, env={**self.env, **diff})
                self.assertEqual(h.code, 404)
                self.assertEqual(h.auth_reads, 0)
                self.assertEqual(h.rfile.tell(), 0)
                self.assertFalse(list(self.root.iterdir()))
        unapproved = {**self.status, "launch_checks": {
            **self.status["launch_checks"], "proprietor_approval": False,
        }}
        h = FakeHandler(body=self.make_body())
        self.request(h, launch_status=unapproved)
        self.assertEqual(h.code, 404)
        self.assertFalse(list(self.root.iterdir()))
        self.assertEqual(self.events, [])

    def test_session_bound_csrf_config_and_exactly_one_synthetic_square_link(self):
        cfg = FakeHandler(method="GET")
        bridge.handle_get(cfg, env=self.env, base_url=SITE,
                          launch_status=self.status)
        self.assertEqual(cfg.code, 200)
        token = cfg.responses[-1][1]["csrf_token"]
        self.assertEqual(len(token), 64)
        h = FakeHandler(body=self.make_body())
        h.headers["X-Shop-CSRF"] = token
        self.request(h)
        self.assertEqual(h.code, 200)
        self.assertEqual(h.responses[-1][1]["checkout_url"], URL)
        self.assertEqual(h.responses[-1][1]["amount_yen"], self.amount)
        self.assertEqual(self.events, ["POST", "GET"])
        self.events.clear()
        again = FakeHandler(body=self.make_body())
        again.headers["X-Shop-CSRF"] = token
        self.request(again)
        self.assertEqual(again.code, 409)
        self.assertEqual(self.events, [], "duplicate attempt must not POST")
        raw = (self.root / "bigpaw-shop-live-orders.sqlite3").read_bytes()
        for item in (TOKEN, SECRET, SESSION, "fake.buyer@example.invalid"):
            self.assertNotIn(item.encode(), raw)

    def test_origin_session_csrf_rate_and_payload_validation(self):
        body = self.make_body()
        def check(modifier, expected):
            h = FakeHandler(body=body)
            h.headers["X-Shop-CSRF"] = bridge._csrf(SECRET, SESSION, USER)
            modifier(h)
            self.request(h)
            self.assertEqual(h.code, expected)
            self.assertEqual(self.events, [])
            self.assertFalse(list(self.root.iterdir()))
        check(lambda h:h.headers.update({"Origin":"https://evil.invalid"}),403)
        check(lambda h:h.headers.update({"Host":"evil.invalid"}),403)
        check(lambda h:h.headers.update({"Sec-Fetch-Site":"cross-site"}),403)
        check(lambda h:h.headers.pop("Origin"),403)
        check(lambda h:h.headers.update({"X-Forwarded-Proto":"http"}),403)
        check(lambda h:h.headers.update({"X-Shop-CSRF":"wrong"}),403)
        check(lambda h:h.headers.update({"Transfer-Encoding":"chunked"}),400)
        check(lambda h:h.headers.update({"Authorization":"Bearer whatever"}),401)
        check(lambda h:setattr(h,"role","breeder"),401)
        check(lambda h:setattr(h,"role",None),401)
        check(lambda h:h.headers.update({
            "Cookie":"bigpaw_session="+SESSION+"; bigpaw_session="+SESSION
        }),401)
        check(lambda h:h.headers.update({"Content-Length":"9999999"}),400)
        check(lambda h:h.headers.update({"Content-Type":"text/plain"}),400)
        h = FakeHandler(body=body)
        h.headers["X-Shop-CSRF"] = bridge._csrf(SECRET, SESSION, USER)
        self.request(h, rate_limited=lambda *args:True)
        self.assertEqual(h.code,429)
        self.assertFalse(list(self.root.iterdir()))
        bad = FakeHandler(body=b'{ "amount_yen":1 }')
        bad.headers["X-Shop-CSRF"] = bridge._csrf(SECRET, SESSION, USER)
        self.request(bad)
        self.assertEqual(bad.code,409)
        self.assertEqual(self.events, [])
        self.assertFalse(list(self.root.iterdir()))

    def test_get_config_requires_valid_buyer_session_and_canonical_host(self):
        for change in ("wrong_host", "wrong_role", "duplicate_cookie"):
            h = FakeHandler(method="GET")
            if change=="wrong_host":h.headers["Host"]="fake.invalid"
            if change=="wrong_role":h.role="breeder"
            if change=="duplicate_cookie":
                h.headers["Cookie"]+="; bigpaw_session="+SESSION
            bridge.handle_get(h, env=self.env, base_url=SITE,
                              launch_status=self.status)
            self.assertIn(h.code,(401,404))
            self.assertNotIn("csrf_token", h.responses[-1][1])

    def test_project_production_server_routes_and_docker_keep_gate(self):
        project = Path(__file__).resolve().parents[1]
        s = (project/"app/backend/server.py").read_text(encoding="utf-8")
        docker = (project/"Dockerfile").read_text(encoding="utf-8")
        self.assertIn("import shop_live_checkout_bridge as bp_shop_checkout",s)
        self.assertIn("bp_shop_checkout.handle_post(",s)
        self.assertIn("bp_shop_checkout.handle_get(",s)
        self.assertIn("COPY shop_payments/ /app/shop_payments/",docker)
        self.assertIn("ENV PYTHONPATH=/app:/app/backend",docker)
        self.assertNotIn('shop-sandbox-checkout.js',(
            project/"app/shop.html").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
