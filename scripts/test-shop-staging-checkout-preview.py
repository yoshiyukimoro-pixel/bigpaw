"""No-network integration tests for password-gated customer Sandbox checkout.

Uses loopback HTTP plus HTTPS-equivalent headers. All Square calls are mocked.
Public BIG PAW services and real users are never contacted.
"""
import base64
from contextlib import contextmanager
from http.client import HTTPConnection
import json
import re
import sqlite3
from urllib.parse import urlencode
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.staging_https_webhook import StageWebhookServer, WEBHOOK_PATH
from shop_payments.sandbox_runtime_guard import (
    EXISTING_TEST_ENVIRONMENT, EXISTING_TEST_SERVICE, LEGACY_BIGPAW_PROJECT,
)

HOST = "bigpaw-test-production.up.railway.app"
ORIGIN = "https://" + HOST
PASSWORD = "not-a-production-password-32-characters"
OPERATOR_PASSWORD = "not-a-real-operator-password-long-enough"
ATTEMPT = "12345678-1234-4234-8234-123456789abc"
ORDER = "FOOD" + ATTEMPT.replace("-", "")
BASE = {
    "RAILWAY_PROJECT_ID": LEGACY_BIGPAW_PROJECT,
    "RAILWAY_ENVIRONMENT_ID": EXISTING_TEST_ENVIRONMENT,
    "RAILWAY_SERVICE_ID": EXISTING_TEST_SERVICE,
    "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID": LEGACY_BIGPAW_PROJECT,
    "BIGPAW_ENV": "sandbox",
    "BIGPAW_SHOP_STAGING_ISOLATED": "1",
    "BIGPAW_SHOP_STAGING_HTTPS_ENABLED": "1",
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "NOT_A_REAL_SANDBOX_TOKEN",
    "BIGPAW_SQUARE_SANDBOX_LOCATION_ID": "SANDBOX_LOCATION_12345",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY": "NOT_A_REAL_SIGNATURE",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL": ORIGIN + WEBHOOK_PATH,
    "BIGPAW_SHOP_STAGE_PREVIEW_ENABLED": "1",
    "BIGPAW_SHOP_STAGE_PREVIEW_USER": "shoptester",
    "BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD": PASSWORD,
    "BIGPAW_SHOP_STAGE_OPERATOR_ENABLED": "1",
    "BIGPAW_SHOP_STAGE_OPERATOR_USER": "operationstest",
    "BIGPAW_SHOP_STAGE_OPERATOR_PASSWORD": OPERATOR_PASSWORD,
}


@contextmanager
def server_with_env(config=None, shipping_opener=None, refund_opener=None):
    folder = tempfile.TemporaryDirectory()
    db = SandboxOrderStore(Path(folder.name) / "orders.sqlite3")
    calls = []
    def creator(payload, *, token):
        assert token == "NOT_A_REAL_SANDBOX_TOKEN"
        assert payload["order"]["line_items"][0]["base_price_money"]["amount"] == 21450
        calls.append(payload["idempotency_key"])
        return {
            "url": "https://sandbox.square.link/u/NO_REAL_CHARGE",
            "square_order_id": "MOCK_SQUARE_ORDER_123456",
            "square_link_id": "MOCK_SQUARE_LINK_123456",
        }
    srv = StageWebhookServer(
        env={**BASE, **(config or {})}, store=db,
        host="127.0.0.1", port=0, checkout_creator=creator,
        shipping_opener=shipping_opener, refund_opener=refund_opener,
    )
    task = Thread(target=srv.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    task.start()
    try:
        yield srv, db, calls
    finally:
        srv.shutdown()
        task.join(timeout=3)
        srv.server_close()
        folder.cleanup()


def request(srv, path, *, method="GET", data=None, auth=True, headers=None):
    conn = HTTPConnection("127.0.0.1", srv.server_port, timeout=4)
    h = {"Host": HOST, **(headers or {})}
    if auth and "Authorization" not in h:
        admin = (path.startswith("/shop-test-orders.html") or
                 path.startswith("/shop-live-orders-preview.html") or
                 path == "/api/shop/sandbox/operator/check-current-payment" or
                 path.startswith("/api/shop/sandbox/operator/draft?") or
                 path in ("/api/shop/sandbox/operator/transition",
                          "/api/shop/sandbox/operator/tracking",
                          "/api/shop/sandbox/operator/review-customer",
                          "/api/shop/sandbox/operator/revoke-customer-review",
                          "/api/shop/sandbox/operator/simulate-customer-notice",
                          "/api/shop/sandbox/operator/mock-customer-mail",
                          "/api/shop/sandbox/operator/verify-full-refund",
                          "/api/shop/sandbox/operator/service-case"))
        credentials = (("operationstest:" + OPERATOR_PASSWORD) if admin
                       else ("shoptester:" + PASSWORD))
        h["Authorization"] = "Basic " + base64.b64encode(
            credentials.encode()
        ).decode()
    try:
        conn.request(method, path, body=data, headers=h)
        res = conn.getresponse()
        body = res.read()
        return res.status, res.headers, body
    finally:
        conn.close()


def json_data(response):
    return json.loads(response[2])


class CheckoutPreviewTests(unittest.TestCase):
    def test_operator_current_square_payment_read_only_recheck(self):
        """Only operator CSRF can verify current Sandbox GET without DB changes."""
        from shop_payments.retail_catalog import load_sale_catalog
        payment_id = "MOCK_SQUARE_PAYMENT_123456"
        square_order_id = "MOCK_SQUARE_ORDER_123456"
        current = {"status": "COMPLETED", "refund": 0, "amount": 21450}
        queries = []
        class Reply:
            status = 200
            def __init__(self, obj):
                self.obj = json.dumps(obj).encode()
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return False
            def read(self, size=None):
                return self.obj if size is None else self.obj[:size]
        def fake_square(req, timeout):
            self.assertEqual(timeout, 10)
            self.assertEqual(req.get_method(), "GET")
            self.assertEqual(req.headers["Authorization"],
                             "Bearer NOT_A_REAL_SANDBOX_TOKEN")
            queries.append(req.full_url)
            if req.full_url.endswith("/payments/" + payment_id):
                return Reply({"payment": {
                    "id": payment_id,
                    "order_id": square_order_id,
                    "location_id": "SANDBOX_LOCATION_12345",
                    "status": current["status"],
                    "amount_money": {
                        "amount": current["amount"], "currency": "JPY"},
                    "refunded_money": {
                        "amount": current["refund"], "currency": "JPY"},
                    "buyer_email_address": "fake.buyer@example.invalid",
                }})
            if req.full_url.endswith("/orders/" + square_order_id):
                return Reply({"order": {
                    "id": square_order_id,
                    "location_id": "SANDBOX_LOCATION_12345",
                    "state": "OPEN",
                    "total_money": {
                        "amount": current["amount"], "currency": "JPY"},
                    "fulfillments": [{
                        "type": "SHIPMENT",
                        "shipment_details": {"recipient": {
                            "display_name": "SECRET DEMO BUYER",
                            "email_address": "fake.buyer@example.invalid",
                        }},
                    }],
                }})
            self.fail("unexpected Square endpoint or credentials")

        with server_with_env(shipping_opener=fake_square) as (srv, db, calls):
            path = "/api/shop/sandbox/operator/check-current-payment"
            db.add_pending_order(
                order_id=ORDER, cart={"A02": 1},
                verified_prices=load_sale_catalog(), shipping_yen=0,
                location_id="SANDBOX_LOCATION_12345",
            )
            db.save_link(ORDER, {
                "url": "https://sandbox.square.link/u/NO_REAL_CHARGE",
                "square_order_id": square_order_id,
                "square_link_id": "MOCK_SQUARE_LINK_123456",
            })
            def mark_paid():
                with sqlite3.connect(db.db_file) as conn:
                    conn.execute(
                        "UPDATE orders SET state='paid',square_payment_id=? "
                        "WHERE order_id=?",
                        (payment_id, ORDER),
                    )
            dashboard = request(srv, "/shop-test-orders.html")
            self.assertEqual(dashboard[0], 200)
            self.assertNotIn(b"/api/shop/sandbox/operator/check-current-payment",
                             dashboard[2])
            cookie = dashboard[1]["Set-Cookie"].split(";", 1)[0]
            csrf = cookie.split("=", 1)[1]
            body = urlencode({"order_id": ORDER,
                              "csrf": csrf, "confirm": "read_only"}).encode()
            headers = {"Origin": ORIGIN,
                       "Content-Type": "application/x-www-form-urlencoded",
                       "Cookie": cookie}
            def send(data=body, h=headers, auth=True):
                return request(srv, path, method="POST",
                               data=data, headers=h, auth=auth)
            self.assertEqual(send(auth=False)[0], 401)
            shopper = "Basic " + base64.b64encode(
                ("shoptester:" + PASSWORD).encode()).decode()
            self.assertEqual(send(h={**headers, "Authorization": shopper})[0],
                             401)
            self.assertEqual(send(h={**headers, "Origin": "https://bad.invalid"})[0],
                             403)
            self.assertEqual(send(h={**headers, "Cookie": "invalid=token"})[0], 403)
            self.assertEqual(send(data=urlencode({
                "order_id": ORDER, "csrf": csrf, "confirm": "issue_refund",
            }).encode())[0], 400)
            self.assertEqual(send()[0], 409,
                             "unpaid journal must not reach Square")
            self.assertEqual(queries, [])
            mark_paid()
            visible = request(srv, "/shop-test-orders.html")
            self.assertIn(b"/api/shop/sandbox/operator/check-current-payment",
                          visible[2])
            before = Path(db.db_file).read_bytes()
            ok = send()
            self.assertEqual(ok[0], 200)
            self.assertIn("最新情報".encode(), ok[2])
            self.assertIn("未返金".encode(), ok[2])
            self.assertIn(b"21,450", ok[2])
            self.assertNotIn(b"fake.buyer@example.invalid", ok[2])
            self.assertNotIn(b"SECRET DEMO BUYER", ok[2])
            self.assertNotIn(payment_id.encode(), ok[2])
            self.assertEqual(len(queries), 2)
            self.assertEqual(Path(db.db_file).read_bytes(), before)
            self.assertEqual(calls, [])
            current["refund"] = 1
            refunded = send()
            self.assertEqual(refunded[0], 503,
                             "refunded payment must never appear verified")
            self.assertIn("現在の入金・未返金を確認できません".encode(), refunded[2])
            self.assertIn("進めないでください".encode(), refunded[2])
            self.assertNotIn(b"fake.buyer@example.invalid", refunded[2])
            current["refund"] = 0
            current["amount"] += 1
            self.assertEqual(send()[0], 503, "price mismatch fails closed")
            current["amount"] = 21450
            current["status"] = "PENDING"
            self.assertEqual(send()[0], 503, "payment pending fails closed")
            self.assertEqual(Path(db.db_file).read_bytes(), before)
            self.assertEqual(calls, [])
            self.assertEqual(db.status(ORDER), "paid")

    def test_operator_only_future_order_display_is_readonly_and_private(self):
        """The new future-ledger view never grants shopper login admin powers."""
        from shop_payments.live_order_ledger import LiveOrderLedger
        from shop_payments.retail_catalog import load_sale_catalog
        import json as json_lib
        with server_with_env() as (srv, store, calls):
            url = "/shop-live-orders-preview.html"
            self.assertEqual(request(srv, url, auth=False)[0], 401)
            shopper = "Basic " + base64.b64encode(
                ("shoptester:" + PASSWORD).encode()
            ).decode()
            self.assertEqual(
                request(srv, url, headers={"Authorization": shopper})[0], 401
            )
            self.assertEqual(
                request(srv, url, headers={"Host": "bigpaw.site"})[0], 400
            )
            no_orders = request(srv, url)
            self.assertEqual(no_orders[0], 200)
            self.assertIn("まだありません".encode(), no_orders[2])
            self.assertIn("読み取り専用".encode(), no_orders[2])
            self.assertIn(b"DEMO-ORDER-001", no_orders[2])
            self.assertIn(b"DEMO-ORDER-002", no_orders[2])
            self.assertIn("架空の注文".encode(), no_orders[2])
            self.assertIn("noindex", no_orders[1]["X-Robots-Tag"])
            self.assertEqual(no_orders[1]["X-Frame-Options"], "DENY")
            self.assertEqual(calls, [])
            ledger = LiveOrderLedger(store.db_file)
            sku = next(iter(load_sale_catalog()))
            live_id = "FOOD" + "f" * 32
            ledger.register_checkout(
                order_id=live_id,
                square_order_id="SYNTHETICORDERSTAGING12345",
                location_id="SYNTHETICLOCATION12345",
                cart={sku: 1},
            )
            # A hostile item name in an existing record may never produce a
            # script tag in the administrator's HTML view.
            with sqlite3.connect(store.db_file) as db:
                snapshot = json_lib.loads(db.execute(
                    "SELECT cart_snapshot FROM food_live_order_ledger "
                    "WHERE order_id=?", (live_id,)
                ).fetchone()[0])
                snapshot[0]["name"] = '<script>alert("bad")</script>'
                db.execute(
                    "UPDATE food_live_order_ledger SET cart_snapshot=? "
                    "WHERE order_id=?",
                    (json_lib.dumps(snapshot), live_id),
                )
            before = Path(store.db_file).read_bytes()
            result = request(srv, url)
            self.assertEqual(result[0], 200)
            self.assertIn(live_id.encode(), result[2])
            self.assertIn(b"&lt;script&gt;", result[2])
            self.assertNotIn(b'<script>alert("bad")</script>', result[2])
            self.assertIn("現在の入金".encode(), result[2])
            self.assertEqual(Path(store.db_file).read_bytes(), before)
            self.assertEqual(calls, [])
            shop_dashboard = request(srv, "/shop-test-orders.html")
            self.assertEqual(shop_dashboard[0], 200)
            self.assertIn(b"/shop-live-orders-preview.html", shop_dashboard[2])

    def test_future_order_display_is_disabled_without_operator(self):
        with server_with_env({"BIGPAW_SHOP_STAGE_OPERATOR_ENABLED": "0"}) as (srv, db, calls):
            self.assertEqual(
                request(srv, "/shop-live-orders-preview.html")[0], 404
            )
            self.assertEqual(calls, [])

    def test_only_password_access_can_view_shop_and_assets(self):
        with server_with_env() as (srv, db, calls):
            self.assertEqual(request(srv, "/shop.html", auth=False)[0], 401)
            self.assertEqual(request(srv, "/shop.html", headers={"Authorization": "Basic incorrect"})[0], 401)
            self.assertEqual(request(srv, "/shop.html", headers={"Host": "bigpaw.site"})[0], 400)
            r = request(srv, "/shop.html")
            self.assertEqual(r[0], 200)
            self.assertIn(b"shop-sandbox-checkout.js", r[2])
            self.assertIn("【Sandbox専用】".encode(), r[2])
            self.assertIn(b"stageOrdersDashboardLink", r[2])
            shopper_authorization = "Basic " + base64.b64encode(
                ("shoptester:" + PASSWORD).encode()).decode()
            self.assertEqual(request(srv, "/shop-test-orders.html",
                                     headers={"Authorization": shopper_authorization})[0], 401,
                             "checkout login must never grant operator access")
            self.assertIn("noindex", r[1]["X-Robots-Tag"])
            review = request(srv, "/shop.html?order=review")
            self.assertEqual(review[0], 200)
            self.assertIn(b"shop-sandbox-review.js", review[2])
            self.assertNotIn(b'src="shop-sandbox-checkout.js"', review[2])
            self.assertEqual(request(srv, "/shop-test-orders.html", auth=False)[0], 401)
            empty_dashboard = request(srv, "/shop-test-orders.html")
            self.assertEqual(empty_dashboard[0], 200)
            self.assertIn("手動進捗テスト".encode(), empty_dashboard[2])
            self.assertIn("注文の記録はありません".encode(), empty_dashboard[2])
            self.assertNotIn(b"RESEND_API_KEY", empty_dashboard[2])
            self.assertNotIn(b"square_payment_id", empty_dashboard[2])
            self.assertEqual(request(srv, "/shop-sandbox-review.js")[0], 200)
            self.assertEqual(request(srv, "/shop-cart-preview.js")[0], 200)
            self.assertEqual(request(srv, "/assets/shop-details/products/A02/ingredients.webp")[0], 200)
            for path in ("/admin", "/.env", "/app/backend/server.py",
                         "/shop_payments/retail_pricebook.json", "/api/me",
                         "/api/shop/sandbox/order/FOOD_invalid"):
                self.assertEqual(request(srv, path)[0], 404)
            self.assertEqual(calls, [])

    def test_readonly_quote_uses_server_price_without_any_square_or_db_write(self):
        with server_with_env() as (srv, db, calls):
            config = json_data(request(srv, "/api/shop/sandbox/config"))
            token = config["csrf_token"]
            payload = json.dumps({"cart": {"A02": 2}}).encode()
            good = {
                "Origin": ORIGIN, "Content-Type": "application/json",
                "X-Shop-CSRF": token,
                "Cookie": "bigpaw_shop_sandbox_csrf=" + token,
            }
            def quote(body=payload, headers=good, auth=True):
                return request(
                    srv, "/api/shop/sandbox/quote", method="POST",
                    data=body, auth=auth, headers=headers,
                )
            self.assertEqual(quote(auth=False)[0], 401)
            self.assertEqual(quote(headers={**good, "Origin": "https://evil.invalid"})[0], 403)
            self.assertEqual(quote(headers={**good, "X-Shop-CSRF": "0"*42})[0], 403)
            self.assertEqual(quote(body=json.dumps({"cart": {"A02": 1}, "price": 1}).encode())[0], 400)
            self.assertEqual(quote(body=b'{"cart":{"A02":1},"cart":{"A02":2}}')[0], 400)
            self.assertEqual(quote(body=json.dumps({"cart": {"A02": True}}).encode())[0], 400)
            self.assertEqual(quote(body=json.dumps({"cart": {"BAD": 1}}).encode())[0], 400)
            self.assertEqual(quote(body=json.dumps({"cart": {"A02": 11}}).encode())[0], 400)
            success = quote()
            self.assertEqual(success[0], 200)
            data = json_data(success)
            self.assertEqual(data, {
                "sandbox": True, "real_payments": False,
                "verified": True, "amount_yen": 42900, "shipping_yen": 0,
            })
            self.assertEqual(calls, [], "read-only quote must not create link")
            with sqlite3.connect(db.db_file) as conn:
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM orders"
                ).fetchone()[0], 0, "read-only quote cannot create order")
                self.assertEqual(conn.execute(
                    "SELECT COUNT(*) FROM checkout_link_claims"
                ).fetchone()[0], 0)

    def test_checkout_requires_origin_csrf_authorization_and_server_prices(self):
        with server_with_env() as (srv, db, calls):
            status, headers, body = request(srv, "/api/shop/sandbox/config")
            self.assertEqual(status, 200)
            config = json.loads(body)
            self.assertTrue(config["sandbox"])
            self.assertFalse(config["real_payments"])
            self.assertIn("Secure", headers["Set-Cookie"])
            self.assertIn("HttpOnly", headers["Set-Cookie"])
            self.assertIn("SameSite=Strict", headers["Set-Cookie"])
            token = config["csrf_token"]
            payload = json.dumps({"cart": {"A02": 1}, "attempt_id": ATTEMPT}).encode()
            good = {
                "Origin": ORIGIN, "Content-Type": "application/json",
                "X-Shop-CSRF": token,
                "Cookie": "bigpaw_shop_sandbox_csrf=" + token,
            }
            self.assertEqual(request(srv, "/api/shop/sandbox/checkout", method="POST", data=payload, auth=False, headers=good)[0], 401)
            self.assertEqual(request(srv, "/api/shop/sandbox/checkout", method="POST", data=payload, headers={**good, "Origin": "https://evil.example"})[0], 403)
            self.assertEqual(request(srv, "/api/shop/sandbox/checkout", method="POST", data=payload, headers={**good, "X-Shop-CSRF": "a" * 40})[0], 403)
            self.assertEqual(request(srv, "/api/shop/sandbox/checkout", method="POST", data=json.dumps({
                "cart": {"A02": 1}, "attempt_id": ATTEMPT, "price": 1}).encode(), headers=good)[0], 400)
            self.assertEqual(calls, [])
            ok = request(srv, "/api/shop/sandbox/checkout", method="POST", data=payload, headers=good)
            self.assertEqual(ok[0], 200)
            response = json_data(ok)
            self.assertEqual(response["amount_yen"], 21450)
            self.assertEqual(response["shipping_yen"], 0)
            self.assertEqual(response["order_id"], ORDER)
            self.assertEqual(response["checkout_url"], "https://sandbox.square.link/u/NO_REAL_CHARGE")
            self.assertEqual(db.status(ORDER), "payment_pending")
            self.assertEqual(len(calls), 1)
            second = request(srv, "/api/shop/sandbox/checkout", method="POST", data=payload, headers=good)
            self.assertEqual(second[0], 200)
            self.assertEqual(json_data(second)["checkout_url"], response["checkout_url"])
            self.assertEqual(len(calls), 1)
            status = request(srv, "/api/shop/sandbox/order/" + ORDER)
            self.assertEqual(json_data(status)["order_status"], "payment_pending")
            self.assertEqual(request(srv, "/api/shop/sandbox/order/" + ORDER, auth=False)[0], 401)
            dashboard = request(srv, "/shop-test-orders.html")
            self.assertEqual(dashboard[0], 200)
            self.assertIn(ORDER.encode(), dashboard[2])
            self.assertIn("決済確認待ち".encode(), dashboard[2])
            self.assertIn("21,450円".encode(), dashboard[2])
            self.assertIn("パピーラージ".encode(), dashboard[2])
            self.assertIn("決済確定前".encode(), dashboard[2])

    def test_timeout_repeated_request_never_creates_second_sandbox_link(self):
        """HTTP integration: persist attempt before fake Square timeout."""
        from shop_payments.sandbox_connector import SquareSandboxError
        with server_with_env() as (srv, db, calls):
            cfg = request(srv, "/api/shop/sandbox/config")
            token = json_data(cfg)["csrf_token"]
            good = {
                "Origin": ORIGIN,
                "Content-Type": "application/json",
                "X-Shop-CSRF": token,
                "Cookie": "bigpaw_shop_sandbox_csrf=" + token,
            }
            body = json.dumps({
                "cart": {"A02": 1}, "attempt_id": ATTEMPT
            }).encode()
            def fake_timeout(payload, *, token):
                calls.append(payload["idempotency_key"])
                raise SquareSandboxError("fake lost Square response")
            srv.checkout_creator = fake_timeout
            first = request(
                srv, "/api/shop/sandbox/checkout",
                method="POST", data=body, headers=good
            )
            self.assertEqual(first[0], 502)
            self.assertEqual(json_data(first)["error"],
                             "sandbox_checkout_result_uncertain")
            self.assertEqual(len(calls), 1)
            with sqlite3.connect(db.db_file) as conn:
                state = conn.execute(
                    "SELECT state FROM checkout_link_claims WHERE order_id=?",
                    (ORDER,)
                ).fetchone()[0]
                self.assertEqual(state, "attempt_unknown")
            second = request(
                srv, "/api/shop/sandbox/checkout",
                method="POST", data=body, headers=good
            )
            self.assertEqual(second[0], 409)
            self.assertEqual(json_data(second)["error"],
                             "sandbox_checkout_operator_review_required")
            self.assertEqual(len(calls), 1, "never silently retry Square POST")
            self.assertEqual(db.status(ORDER), "created")
            # Manual reconciliation, exact same id and link, recovers without
            # a fresh POST and without deleting prior Sandbox records.
            link = {
                "url": "https://sandbox.square.link/u/NO_REAL_CHARGE",
                "square_order_id": "MOCK_SQUARE_ORDER_123456",
                "square_link_id": "MOCK_SQUARE_LINK_123456",
            }
            db.save_link(ORDER, link)
            third = request(
                srv, "/api/shop/sandbox/checkout",
                method="POST", data=body, headers=good
            )
            self.assertEqual(third[0], 200)
            self.assertEqual(json_data(third)["checkout_url"], link["url"])
            self.assertEqual(len(calls), 1)

    def test_concurrent_square_link_claims_allow_only_one_attempt(self):
        """Parallel shop requests must reserve exactly one Square POST slot."""
        from concurrent.futures import ThreadPoolExecutor
        from shop_payments.sandbox_connector import SquareSandboxError
        from shop_payments.retail_catalog import load_sale_catalog
        with server_with_env() as (srv, store, calls):
            store.add_pending_order(
                order_id=ORDER, cart={"A02": 1},
                verified_prices=load_sale_catalog(), shipping_yen=0,
                location_id=BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
            )
            def claim(_):
                try:
                    store.claim_checkout_link_attempt(ORDER)
                    return "won"
                except SquareSandboxError:
                    return "blocked"
            with ThreadPoolExecutor(max_workers=8) as pool:
                results = list(pool.map(claim, range(8)))
            self.assertEqual(results.count("won"), 1)
            self.assertEqual(results.count("blocked"), 7)
            self.assertEqual(store.status(ORDER), "created")
            self.assertEqual(calls, [], "claiming never sends a Square POST")
            with sqlite3.connect(store.db_file) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM checkout_link_claims "
                    "WHERE order_id=? AND state='attempt_unknown'", (ORDER,)
                ).fetchone()[0]
            self.assertEqual(count, 1)

    def test_pre_upgrade_created_order_without_claim_fails_closed(self):
        """Existing pre-upgrade 'created' data must never be re-posted."""
        from shop_payments.retail_catalog import load_sale_catalog
        with server_with_env() as (srv, db, calls):
            db.add_pending_order(
                order_id=ORDER, cart={"A02": 1},
                verified_prices=load_sale_catalog(), shipping_yen=0,
                location_id=BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
            )
            with sqlite3.connect(db.db_file) as conn:
                conn.execute(
                    "DELETE FROM checkout_link_claims WHERE order_id=?", (ORDER,)
                )
            cfg = request(srv, "/api/shop/sandbox/config")
            token = json_data(cfg)["csrf_token"]
            body = json.dumps({
                "cart": {"A02": 1}, "attempt_id": ATTEMPT
            }).encode()
            response = request(
                srv, "/api/shop/sandbox/checkout",
                method="POST", data=body, headers={
                    "Origin": ORIGIN,
                    "Content-Type": "application/json",
                    "X-Shop-CSRF": token,
                    "Cookie": "bigpaw_shop_sandbox_csrf=" + token,
                }
            )
            self.assertEqual(response[0], 409)
            self.assertEqual(calls, [])
            self.assertEqual(db.status(ORDER), "created")

    def test_shop_commerce_disclosures_are_private_and_never_enable_sales(self):
        with server_with_env() as (srv, store, calls):
            self.assertEqual(request(srv, "/shop-commerce.html", auth=False)[0], 401)
            response = request(srv, "/shop-commerce.html")
            self.assertEqual(response[0], 200)
            self.assertIn("text/html", response[1]["Content-Type"])
            html = response[2].decode("utf-8")
            self.assertIn("特定商取引法に基づく表記（下書き）", html)
            self.assertIn("返品・キャンセル", html)
            self.assertIn("販売業者の氏名", html)
            self.assertIn("事業者の所在地・電話番号", html)
            self.assertIn("個人事業", html)
            self.assertIn("受け付けていません", html)
            returns = request(srv, "/shop-returns.html")
            self.assertEqual(returns[0], 200)
            self.assertIn("text/html", returns[1]["Content-Type"])
            self.assertIn("正式な返品特約ではありません".encode(), returns[2])
            self.assertIn("欠品・配送遅延".encode(), returns[2])
            self.assertIn("8日以内".encode(), returns[2])
            self.assertEqual(request(srv, "/shop-returns.html", auth=False)[0], 401)
            shop = request(srv, "/shop.html")
            self.assertEqual(shop[0], 200)
            self.assertIn('href="shop-commerce.html"', shop[2].decode())
            self.assertIn('id="previewCheckout" disabled', shop[2].decode())
            self.assertEqual(calls, [], "reading terms must not create Square payment")

    def test_dashboard_paid_order_shows_next_action_and_drafts_without_sending(self):
        # Test DB only: synthetic 'paid' fixture. This is NOT evidence of a real
        # Square payment. The route must remain read-only and never notify anyone.
        from shop_payments.retail_catalog import load_sale_catalog
        with server_with_env() as (srv, store, calls):
            store.add_pending_order(
                order_id=ORDER, cart={"A02": 1},
                verified_prices=load_sale_catalog(), shipping_yen=0,
                location_id=BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
            )
            with sqlite3.connect(store.db_file) as conn:
                conn.execute(
                    "UPDATE orders SET state='paid', paid_at=1761780000, "
                    "square_payment_id='MOCK_NOT_REAL_PAYMENT', "
                    "square_order_id='MOCK_NOT_REAL_ORDER' WHERE order_id=?",
                    (ORDER,),
                )
                conn.execute("""
                    CREATE TABLE food_notification_drafts(
                        order_id TEXT NOT NULL, kind TEXT NOT NULL,
                        audience TEXT NOT NULL, created_at INTEGER NOT NULL,
                        PRIMARY KEY(order_id, kind)
                    )
                """)
                conn.executemany(
                    "INSERT INTO food_notification_drafts VALUES (?,?,?,?)",
                    ((ORDER, kind, audience, 1761780000) for kind, audience in (
                        ("operator_new_order", "operator"),
                        ("supplier_purchase_request", "supplier"),
                        ("customer_order_confirmed", "customer"),
                    )),
                )
                conn.commit()
            self.assertEqual(request(srv, "/shop-test-orders.html", auth=False)[0], 401)
            first = request(srv, "/shop-test-orders.html")
            second = request(srv, "/shop-test-orders.html")
            self.assertEqual(first[0], 200)
            self.assertEqual(
                re.sub(rb'name="csrf" value="[^"]+"', b'name="csrf" value="REDACTED"', first[2]),
                re.sub(rb'name="csrf" value="[^"]+"', b'name="csrf" value="REDACTED"', second[2]),
                "refresh must not change order content (CSRF rotates on each request)"
            )
            html = first[2].decode("utf-8")
            self.assertIn("入金確認済み（Sandbox）", html)
            self.assertIn("仕入先に在庫・納期を確認", html)
            self.assertIn("通知の下書き：3件", html)
            self.assertIn("仕入先：在庫・納期確認と発注内容", html)
            self.assertIn("お客様：決済・注文確認", html)
            self.assertIn("未送信下書き", html)
            self.assertIn("メールは送られません", html)
            self.assertNotIn("MOCK_NOT_REAL_PAYMENT", html)
            self.assertNotIn("MOCK_NOT_REAL_ORDER", html)
            self.assertEqual(calls, [], "no Square checkout calls")
            with sqlite3.connect(store.db_file) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM food_notification_drafts"
                ).fetchone()[0]
            self.assertEqual(count, 3, "dashboard must not send or change drafts")

    def test_operator_post_requires_verified_paid_state_origin_csrf_and_confirmation(self):
        from shop_payments.retail_catalog import load_sale_catalog
        with server_with_env() as (srv, store, calls):
            store.add_pending_order(order_id=ORDER, cart={"A02": 1},
                                    verified_prices=load_sale_catalog(), shipping_yen=0,
                                    location_id=BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"])
            dashboard = request(srv, "/shop-test-orders.html")
            self.assertEqual(dashboard[0], 200)
            header = dashboard[1]["Set-Cookie"]
            self.assertIn("__Host-bigpaw_shop_operator_csrf=", header)
            cookie_pair = header.split(";", 1)[0]
            token = cookie_pair.split("=", 1)[1]
            action = "/api/shop/sandbox/operator/transition"
            data = {"order_id": ORDER, "stage": "supplier_ordered",
                    "expected": "awaiting_supplier_order", "csrf": token,
                    "confirm": "record_only"}
            def send(values=data, *, auth=True, origin=ORIGIN, cookie=cookie_pair):
                return request(srv, action, method="POST", auth=auth,
                    data=urlencode(values).encode(), headers={
                        "Origin": origin, "Cookie": cookie,
                        "Content-Type": "application/x-www-form-urlencoded",
                    })
            self.assertEqual(send(auth=False)[0], 401)
            self.assertEqual(send(origin="https://untrusted.invalid")[0], 403)
            self.assertEqual(send(cookie="invalid=x")[0], 403)
            self.assertEqual(send({**data, "confirm": "not_confirmed"})[0], 400)
            self.assertEqual(send()[0], 409, "unpaid orders cannot advance")
            self.assertEqual(calls, [])
            with sqlite3.connect(store.db_file) as conn:
                conn.execute(
                    "UPDATE orders SET state='paid',paid_at=1761780000,"
                    "square_payment_id='MOCK_PAID_ID',square_order_id='MOCK_ORDER_ID' "
                    "WHERE order_id=?", (ORDER,)
                )
            paid_dashboard = request(srv, "/shop-test-orders.html")
            self.assertEqual(paid_dashboard[0], 200)
            html = paid_dashboard[2].decode()
            self.assertIn("手動の進捗記録", html)
            self.assertIn("supplier_ordered", html)
            self.assertNotIn('name="stage" value="shipped"', html)
            csrf = paid_dashboard[1]["Set-Cookie"].split(";",1)[0]
            form = dict(data, csrf=csrf.split("=",1)[1])
            def record(values):
                return send(values, cookie=csrf)
            first = record(form)
            self.assertEqual(first[0], 303)
            self.assertEqual(first[1]["Location"], "/shop-test-orders.html?updated=1")
            self.assertEqual(record(form)[0], 409, "stale form must fail")
            with sqlite3.connect(store.db_file) as conn:
                n = conn.execute("SELECT COUNT(*) FROM food_procurement_events "
                                 "WHERE order_id=?", (ORDER,)).fetchone()[0]
            self.assertEqual(n, 1, "stale retries never append duplicate events")
            self.assertEqual(record({**form,"stage":"shipped"})[0], 409)
            self.assertEqual(record({**form,"stage":"refunded"})[0], 400)
            self.assertEqual(record({**form,"stage":"received_at_shop"})[0], 409)
            next_page = request(srv, "/shop-test-orders.html")
            self.assertIn("発注済み（テスト記録）".encode(), next_page[2])
            self.assertIn("入荷・検品をテスト記録".encode(), next_page[2])
            new_cookie = next_page[1]["Set-Cookie"].split(";",1)[0]
            step2 = dict(form, stage="received_at_shop", expected="supplier_ordered",
                         csrf=new_cookie.split("=",1)[1])
            self.assertEqual(send(step2,cookie=new_cookie)[0], 303)
            final = request(srv, "/shop-test-orders.html")
            self.assertIn("入荷検品済み（テスト記録）".encode(), final[2])
            self.assertNotIn("MOCK_PAID_ID".encode(), final[2])
            self.assertEqual(calls, [], "recording never creates Square checkout links")
            with sqlite3.connect(store.db_file) as conn:
                states = [x[0] for x in conn.execute(
                    "SELECT stage FROM food_procurement_events WHERE order_id=? ORDER BY id",
                    (ORDER,))]
            self.assertEqual(states, ["supplier_ordered", "received_at_shop"])

    def test_shipment_requires_live_square_sandbox_address_check_then_creates_unsent_draft(self):
        from shop_payments.retail_catalog import load_sale_catalog
        from shop_payments.sandbox_procurement import SandboxProcurementOps
        import urllib.parse
        square_order = "MOCKSQUAREORDER12345"

        class FakeResponse:
            status = 200
            def __init__(self, complete):
                recipient = {"display_name": "PRIVATE", "phone_number": "09012345678", "address": {
                    "country": "JP", "address_line_1": "PRIVATE STREET" if complete else "",
                    "postal_code": "000-0000"}}
                self.payload = json.dumps({"order": {
                    "id": square_order,
                    "fulfillments": [{"type": "SHIPMENT", "shipment_details": {
                        "recipient": recipient}}]
                }}).encode()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return self.payload[:n]

        state = {"complete": False, "calls": 0}
        def shipping_opener(req, timeout):
            self.assertEqual(req.get_method(), "GET", "no shipping POSTs")
            self.assertEqual(req.full_url,
                             "https://connect.squareupsandbox.com/v2/orders/" + square_order)
            self.assertEqual(timeout, 10)
            state["calls"] += 1
            return FakeResponse(state["complete"])

        with server_with_env(shipping_opener=shipping_opener) as (srv, store, calls):
            store.add_pending_order(order_id=ORDER, cart={"A02": 1},
                                    verified_prices=load_sale_catalog(), shipping_yen=0,
                                    location_id=BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"])
            with sqlite3.connect(store.db_file) as conn:
                conn.execute(
                    "UPDATE orders SET state='paid',paid_at=1761780000,"
                    "square_payment_id='MOCK_PAID_ID',square_order_id=? WHERE order_id=?",
                    (square_order, ORDER),
                )
            ops = SandboxProcurementOps(store)
            ops.transition(ORDER, "supplier_ordered")
            ops.transition(ORDER, "received_at_shop")
            page = request(srv, "/shop-test-orders.html")
            self.assertEqual(page[0], 200)
            self.assertIn("発送済みをテスト記録".encode(), page[2])
            csrf = page[1]["Set-Cookie"].split(";", 1)[0]
            data = {"order_id": ORDER, "stage": "shipped",
                    "expected": "received_at_shop", "csrf": csrf.split("=",1)[1],
                    "confirm": "record_only"}
            def record(payload=data, *, origin=ORIGIN):
                return request(srv, "/api/shop/sandbox/operator/transition", method="POST",
                               data=urlencode(payload).encode(), headers={
                                   "Origin": origin, "Content-Type": "application/x-www-form-urlencoded",
                                   "Cookie": csrf})
            self.assertEqual(record(origin="https://attacker.invalid")[0], 403)
            self.assertEqual(state["calls"], 0)
            self.assertEqual(record()[0], 409, "incomplete shipping recipient blocks shipped")
            self.assertEqual(ops.state(ORDER), "received_at_shop")
            self.assertEqual(state["calls"], 1)
            state["complete"] = True
            success = record()
            self.assertEqual(success[0], 303)
            self.assertEqual(ops.state(ORDER), "shipped")
            self.assertEqual(state["calls"], 2)
            self.assertEqual(record()[0], 409, "duplicate/stale form cannot reverify or resend")
            self.assertEqual(state["calls"], 2)
            self.assertEqual(calls, [], "no Square checkout calls")
            page = request(srv, "/shop-test-orders.html")
            self.assertIn("発送済み（テスト記録）".encode(), page[2])
            self.assertIn("発送のお知らせ".encode(), page[2])
            self.assertNotIn("PRIVATE STREET".encode(), page[2])
            link = ("/api/shop/sandbox/operator/draft?" + urlencode({
                "order_id": ORDER, "kind": "customer_shipment_notice"}))
            self.assertEqual(request(srv, link, auth=False)[0], 401)
            draft = request(srv, link)
            self.assertEqual(draft[0], 200)
            body = draft[2].decode("utf-8")
            self.assertIn("ドッグフード発送のお知らせ", body)
            self.assertIn("配送会社：【運営が確認して入力】", body)
            self.assertIn("追跡番号：【運営が確認して入力】", body)
            self.assertIn("メールは送れません", body)
            self.assertNotIn("PRIVATE STREET", body)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/draft?order_id="+ORDER+"&kind=not_valid")[0], 400)
            with sqlite3.connect(store.db_file) as conn:
                n = conn.execute(
                    "SELECT COUNT(*) FROM food_notification_drafts "
                    "WHERE order_id=? AND kind='customer_shipment_notice'", (ORDER,)
                ).fetchone()[0]
                events = [row[0] for row in conn.execute(
                    "SELECT stage FROM food_procurement_events WHERE order_id=? ORDER BY id",
                    (ORDER,)
                )]
            self.assertEqual(n, 1, "shipping must enqueue exactly one unsent draft")
            self.assertEqual(events, ["supplier_ordered", "received_at_shop", "shipped"])

            # Delivery references are not sent: only an operator can record one.
            track_page = request(srv, "/shop-test-orders.html")
            self.assertIn("配送会社・追跡番号（テスト記録）".encode(), track_page[2])
            tcookie = track_page[1]["Set-Cookie"].split(";", 1)[0]
            track_path = "/api/shop/sandbox/operator/tracking"
            payload = {
                "order_id": ORDER, "carrier_code": "yamato",
                "tracking_number": "1234-5678-9012",
                "csrf": tcookie.split("=", 1)[1],
                "confirm": "record_only",
            }
            def track(params=payload, *, auth=True, cookie=tcookie, origin=ORIGIN):
                return request(srv, track_path, method="POST", auth=auth,
                               data=urlencode(params).encode(), headers={
                                    "Origin": origin, "Cookie": cookie,
                                    "Content-Type": "application/x-www-form-urlencoded",
                               })
            self.assertEqual(track(auth=False)[0], 401)
            self.assertEqual(track(cookie="missing=x")[0], 403)
            self.assertEqual(track(origin="https://attacker.invalid")[0], 403)
            self.assertEqual(track({**payload,"confirm":"wrong"})[0], 400)
            self.assertEqual(track({**payload,"tracking_number":"bad"})[0], 409)
            self.assertEqual(track({**payload,"carrier_code":"not_real"})[0], 409)
            self.assertEqual(track()[0], 303)
            self.assertEqual(track()[0], 303, "exact retry is idempotent")
            self.assertEqual(track({**payload,"tracking_number":"9999-0000-1111"})[0], 409)
            updated = request(srv, "/shop-test-orders.html")
            self.assertEqual(updated[0], 200)
            self.assertIn("配送情報（テスト記録）".encode(), updated[2])
            self.assertIn("ヤマト運輸".encode(), updated[2])
            self.assertIn(b"1234-5678-9012", updated[2])
            self.assertNotIn(b'form method="post" action="/api/shop/sandbox/operator/tracking"', updated[2])
            draft = request(srv, link)
            self.assertEqual(draft[0], 200)
            self.assertIn("配送会社：ヤマト運輸".encode(), draft[2])
            self.assertIn(b"1234-5678-9012", draft[2])
            self.assertNotIn("配送会社：【運営が確認して入力】".encode(), draft[2])
            self.assertIn("メールは送れません".encode(), draft[2])
            self.assertNotIn("PRIVATE STREET".encode(), draft[2])
            self.assertEqual(calls, [], "registering tracking must never issue Square payments")
            with sqlite3.connect(store.db_file) as conn:
                entries = conn.execute(
                    "SELECT carrier_code,tracking_number FROM food_sandbox_tracking WHERE order_id=?",
                    (ORDER,)
                ).fetchall()
                notice_count = conn.execute(
                    "SELECT COUNT(*) FROM food_notification_drafts WHERE order_id=? "
                    "AND kind='customer_shipment_notice'", (ORDER,)
                ).fetchone()[0]
            self.assertEqual(entries, [("yamato", "1234-5678-9012")])
            self.assertEqual(notice_count, 1, "shipment notice is draft only, never resent")

    def test_customer_review_checks_square_email_and_records_without_sending(self):
        # Fake Square Sandbox response: no real buyer email is used or contacted.
        from shop_payments.retail_catalog import load_sale_catalog
        from shop_payments.sandbox_notifications import SandboxNotificationDrafts
        from shop_payments.sandbox_customer_review import SandboxCustomerReview
        square_order = "SQUAREORDEREMAIL12345"
        state = {"address": "buyer-test@example.invalid", "calls": 0}
        class FakeResponse:
            status = 200
            def __init__(self, address):
                self.body = json.dumps({"order": {"id": square_order,
                    "fulfillments": [{"type": "SHIPMENT", "shipment_details": {
                        "recipient": {
                            "display_name": "PRIVATE NAME",
                            "phone_number": "09012345678",
                            "email_address": address,
                            "address": {"country": "JP", "postal_code": "123-4567",
                                        "address_line_1": "PRIVATE ADDRESS"}
                        }
                    }}]}}).encode()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return self.body[:n]
        def square_get(request, timeout):
            self.assertEqual(request.get_method(), "GET", "read-only Square API")
            self.assertEqual(request.full_url,
                "https://connect.squareupsandbox.com/v2/orders/" + square_order)
            state["calls"] += 1
            return FakeResponse(state["address"])
        with server_with_env(shipping_opener=square_get) as (srv,store,calls):
            store.add_pending_order(order_id=ORDER, cart={"A02": 1},
                                    verified_prices=load_sale_catalog(), shipping_yen=0,
                                    location_id=BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"])
            with sqlite3.connect(store.db_file) as conn:
                conn.execute(
                    "UPDATE orders SET state='paid', paid_at=1761780000,"
                    "square_payment_id='SQUAREPAYMENTEMAIL12345',"
                    "square_order_id=? WHERE order_id=?", (square_order, ORDER)
                )
            notices=SandboxNotificationDrafts(store)
            self.assertEqual(notices.sync_paid(ORDER), 3)
            path="/api/shop/sandbox/operator/draft?" + urlencode({
                "order_id": ORDER, "kind": "customer_order_confirmed"})
            self.assertEqual(request(srv,path,auth=False)[0],401)
            state["address"]=""
            no_contact=request(srv,path)
            self.assertEqual(no_contact[0],200)
            self.assertIn("連絡先または配送情報が不十分".encode(),no_contact[2])
            self.assertNotIn(b'name="confirm" value="review_only"',no_contact[2])
            review_path="/api/shop/sandbox/operator/review-customer"
            invalid_body={"order_id":ORDER,"kind":"customer_order_confirmed",
                          "csrf":"x"*43,"confirm":"review_only"}
            def approve(values, *, cookie="", origin=ORIGIN, auth=True):
                return request(srv,review_path,method="POST",
                    data=urlencode(values).encode(),auth=auth,headers={
                    "Origin":origin,"Cookie":cookie,
                    "Content-Type":"application/x-www-form-urlencoded"})
            self.assertEqual(approve(invalid_body,auth=False)[0],401)
            self.assertEqual(approve(invalid_body)[0],403)
            state["address"]="buyer-test@example.invalid"
            preview=request(srv,path)
            self.assertEqual(preview[0],200)
            html=preview[2].decode("utf-8")
            self.assertIn("送信前の確認",html)
            self.assertIn("b***@e***",html)
            self.assertNotIn("buyer-test@example.invalid",html)
            self.assertIn("送信しない",html)
            cookie=preview[1]["Set-Cookie"].split(";",1)[0]
            data=dict(invalid_body,csrf=cookie.split("=",1)[1])
            self.assertEqual(approve(data,cookie=cookie,origin="https://evil.invalid")[0],403)
            self.assertEqual(approve({**data,"confirm":"yes"},cookie=cookie)[0],400)
            self.assertEqual(approve({**data,"kind":"supplier_purchase_request"},cookie=cookie)[0],400)
            state["address"]="invalid.address.example"
            self.assertEqual(approve(data,cookie=cookie)[0],409)
            self.assertFalse(SandboxCustomerReview(store).reviewed(ORDER,"customer_order_confirmed"))
            state["address"]="buyer-test@example.invalid"
            self.assertEqual(approve(data,cookie=cookie)[0],303)
            self.assertTrue(SandboxCustomerReview(store).reviewed(ORDER,"customer_order_confirmed"))
            self.assertEqual(approve(data,cookie=cookie)[0],303,"review action idempotent")
            done=request(srv,path)
            self.assertIn("送信前チェック済み・未送信".encode(),done[2])
            self.assertIn("未送信".encode(),done[2])
            self.assertNotIn("buyer-test@example.invalid".encode(),done[2])
            with sqlite3.connect(store.db_file) as conn:
                rows=conn.execute("SELECT * FROM food_sandbox_customer_reviews").fetchall()
            self.assertEqual(len(rows),1)
            self.assertEqual(len(rows[0]),6,"DB stores keyed hashes and a revoke flag, no raw recipient")
            self.assertNotIn("buyer-test@example.invalid",str(rows))
            self.assertEqual(len(rows[0][3]),64)
            self.assertEqual(len(rows[0][4]),64)
            dashboard = request(srv, "/shop-test-orders.html")
            self.assertEqual(dashboard[0], 200)
            self.assertIn("送信前チェックの記録あり・現在の有効性は要再照合".encode(), dashboard[2])
            self.assertNotIn("buyer-test@example.invalid".encode(), dashboard[2])
            self.assertEqual(calls,[],"No Square checkout POST allowed")
            self.assertGreaterEqual(state["calls"],4,"Read-only Square checks occurred")
            # Operator can revoke a preview review, without sending mail or
            # changing the Square payment, then explicitly approve it again.
            revoke_path = "/api/shop/sandbox/operator/revoke-customer-review"
            revoke_page = request(srv, path)
            self.assertIn("送信前チェックを取り消す（送信しない）".encode(),
                          revoke_page[2])
            revoke_cookie = revoke_page[1]["Set-Cookie"].split(";", 1)[0]
            revoke_data = {"order_id": ORDER,
                           "kind": "customer_order_confirmed",
                           "csrf": revoke_cookie.split("=", 1)[1],
                           "confirm": "revoke_only"}
            def revoke(fields=revoke_data, *, auth=True, origin=ORIGIN,
                       cookie=revoke_cookie):
                return request(srv, revoke_path, method="POST", auth=auth,
                    data=urlencode(fields).encode(), headers={
                        "Origin": origin, "Cookie": cookie,
                        "Content-Type": "application/x-www-form-urlencoded"})
            self.assertEqual(revoke(auth=False)[0], 401)
            self.assertEqual(revoke(origin="https://evil.invalid")[0], 403)
            self.assertEqual(revoke({**revoke_data, "csrf": "bad"})[0], 403)
            self.assertEqual(revoke({**revoke_data, "confirm": "send_now"})[0], 400)
            self.assertEqual(revoke()[0], 303)
            self.assertEqual(revoke()[0], 409, "revocation must be idempotent fail closed")
            stale = request(srv, path)
            self.assertIn("以前の確認は失効しました".encode(), stale[2])
            self.assertNotIn("送信せずに最終チェックをテストする".encode(), stale[2])
            self.assertEqual(approve(data, cookie=cookie)[0], 303)

            # After fifteen minutes, an old approval can no longer be
            # treated as active, even if the Square contact has not changed.
            import time
            with sqlite3.connect(store.db_file) as conn:
                conn.execute("UPDATE food_sandbox_customer_reviews "
                             "SET reviewed_at=? WHERE order_id=? AND kind=?",
                             (int(time.time()) - 901, ORDER, "customer_order_confirmed"))
            expired = request(srv, path)
            self.assertIn("以前の確認は失効しました".encode(), expired[2])
            self.assertNotIn("送信せずに最終チェックをテストする".encode(),
                             expired[2])
            self.assertEqual(approve(data, cookie=cookie)[0], 303)

            # A changed Square contact invalidates old approvals even if the
            # masked preview looks identical. No message is sent.
            simulate_path = "/api/shop/sandbox/operator/simulate-customer-notice"
            new_draft = request(srv,path)
            self.assertIn("送信せずに最終チェックをテストする".encode(),new_draft[2])
            current_cookie=new_draft[1]["Set-Cookie"].split(";",1)[0]
            simulation={"order_id":ORDER,"kind":"customer_order_confirmed",
                        "csrf":current_cookie.split("=",1)[1],
                        "confirm":"simulate_only"}
            def dryrun(values=simulation,*,cookie=current_cookie,origin=ORIGIN,auth=True):
                return request(srv,simulate_path,method="POST",auth=auth,
                    data=urlencode(values).encode(),headers={
                    "Origin":origin,"Cookie":cookie,
                    "Content-Type":"application/x-www-form-urlencoded"})
            self.assertEqual(dryrun(auth=False)[0],401)
            self.assertEqual(dryrun(origin="https://untrusted.invalid")[0],403)
            self.assertEqual(dryrun({**simulation,"confirm":"actually_send"})[0],400)
            self.assertEqual(dryrun()[0],303)
            self.assertEqual(dryrun()[0],303,"retries must not duplicate the dryrun")
            sent_status=request(srv,path)
            self.assertIn("メール送信結果のオフライン試験".encode(),sent_status[2])
            self.assertIn("実メールは一切送信せず".encode(),sent_status[2])
            mock_cookie=sent_status[1]["Set-Cookie"].split(";",1)[0]
            mock_data={
                "order_id":ORDER,
                "kind":"customer_order_confirmed",
                "csrf":mock_cookie.split("=",1)[1],
                "confirm":"offline_only",
                "outcome":"simulated_unknown",
            }
            mock_path="/api/shop/sandbox/operator/mock-customer-mail"
            def mocked(data=mock_data,*,auth=True,origin=ORIGIN,cookie=mock_cookie):
                return request(srv,mock_path,method="POST",auth=auth,
                    data=urlencode(data).encode(),headers={
                        "Origin":origin,"Cookie":cookie,
                        "Content-Type":"application/x-www-form-urlencoded",
                    })
            self.assertEqual(mocked(auth=False)[0],401)
            self.assertEqual(mocked(origin="https://untrusted.invalid")[0],403)
            self.assertEqual(mocked(cookie="invalid=x")[0],403)
            self.assertEqual(mocked({**mock_data,"outcome":"send_real_email"})[0],400)
            self.assertEqual(mocked({**mock_data,"confirm":"actually_send"})[0],400)
            self.assertEqual(mocked()[0],303)
            self.assertEqual(mocked({**mock_data,"outcome":"simulated_accepted"})[0],303,
                             "uncertain results must NEVER be automatically retried")
            mock_status=request(srv,path)
            self.assertIn("送信シミュレーション完了".encode(),mock_status[2])
            self.assertIn("模擬通信結果不明".encode(),mock_status[2])
            self.assertIn("実メール未送信".encode(),mock_status[2])
            dashboard=request(srv,"/shop-test-orders.html")
            self.assertIn("模擬通信結果不明".encode(),dashboard[2])
            self.assertIn("実メール未送信".encode(),dashboard[2])
            self.assertNotIn("buyer-test@example.invalid".encode(),dashboard[2])
            state["address"]="b-UPDATED@example.invalid"
            changed=request(srv,path)
            self.assertIn("以前の確認は失効".encode(),changed[2])
            self.assertNotIn("送信シミュレーション完了".encode(),changed[2])
            self.assertEqual(dryrun()[0],409,"stale contact must block dryrun")
            changed_cookie=changed[1]["Set-Cookie"].split(";",1)[0]
            updated_review=dict(data,csrf=changed_cookie.split("=",1)[1])
            self.assertEqual(approve(updated_review,cookie=changed_cookie)[0],303)
            self.assertEqual(dryrun()[0],409,"old dryrun snapshot must never be replaced silently")
            with sqlite3.connect(store.db_file) as conn:
                saved=conn.execute(
                    "SELECT status,snapshot_digest FROM food_sandbox_customer_dryrun"
                ).fetchall()
                hashed=conn.execute(
                    "SELECT contact_fingerprint FROM food_sandbox_customer_reviews"
                ).fetchone()[0]
                attempted=conn.execute(
                    "SELECT status,snapshot_digest FROM food_sandbox_customer_mail_attempts"
                ).fetchall()
            self.assertEqual(len(saved),1)
            self.assertEqual(attempted[0][0],"simulated_unknown")
            self.assertEqual(len(attempted),1)
            self.assertEqual(len(attempted[0][1]),64)
            self.assertEqual(saved[0][0],"simulated_only")
            self.assertEqual(len(saved[0][1]),64)
            self.assertEqual(len(hashed),64)
            self.assertNotIn("b-UPDATED@example.invalid",str(saved)+str(hashed))
            self.assertEqual(calls,[],"no provider email or new checkout ever sent")

    def test_verified_full_refund_operator_action_never_initiates_square_refund(self):
        from shop_payments.retail_catalog import load_sale_catalog
        from shop_payments.sandbox_procurement import SandboxProcurementOps
        payment_id = "MOCKSQUAREPAYMENTFULL12345"
        square_order = "MOCKSQUAREORDERFULL12345"
        state = {"refunded": 0, "reads": 0}

        class MockResponse:
            status = 200
            def __init__(self):
                self.body = json.dumps({"payment": {
                    "id": payment_id, "order_id": square_order,
                    "location_id": BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
                    "status": "COMPLETED",
                    "amount_money": {"amount": 21450, "currency": "JPY"},
                    "refunded_money": {"amount": state["refunded"], "currency": "JPY"},
                }}).encode()
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def read(self, n): return self.body[:n]

        def refund_opener(request, timeout):
            self.assertEqual(request.get_method(), "GET", "refund API MUST be read-only")
            self.assertEqual(request.full_url,
                "https://connect.squareupsandbox.com/v2/payments/" + payment_id)
            self.assertEqual(timeout, 10)
            state["reads"] += 1
            return MockResponse()

        with server_with_env(refund_opener=refund_opener) as (srv, store, calls):
            store.add_pending_order(
                order_id=ORDER, cart={"A02": 1},
                verified_prices=load_sale_catalog(), shipping_yen=0,
                location_id=BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
            )
            with sqlite3.connect(store.db_file) as conn:
                conn.execute(
                    "UPDATE orders SET state='paid',paid_at=1761780000,"
                    "square_payment_id=?,square_order_id=? WHERE order_id=?",
                    (payment_id, square_order, ORDER)
                )
            ops = SandboxProcurementOps(store)
            ops.transition(ORDER, "refund_review")
            page = request(srv, "/shop-test-orders.html")
            self.assertEqual(page[0], 200)
            self.assertIn("Square全額返金済みを照合する".encode(), page[2])
            cookie = page[1]["Set-Cookie"].split(";", 1)[0]
            data = {
                "order_id": ORDER, "csrf": cookie.split("=", 1)[1],
                "confirm": "verify_read_only",
            }
            path = "/api/shop/sandbox/operator/verify-full-refund"
            def check(payload=data, *, auth=True, origin=ORIGIN, cookie_value=cookie):
                return request(srv, path, auth=auth, method="POST",
                    data=urlencode(payload).encode(),
                    headers={"Origin": origin, "Cookie": cookie_value,
                             "Content-Type": "application/x-www-form-urlencoded"})
            self.assertEqual(check(auth=False)[0], 401)
            self.assertEqual(check(origin="https://untrusted.invalid")[0], 403)
            self.assertEqual(check(cookie_value="invalid=x")[0], 403)
            self.assertEqual(check({**data, "confirm": "refund_now"})[0], 400)
            self.assertEqual(state["reads"], 0, "invalid requests cannot read Square")
            self.assertEqual(check()[0], 409, "no refund cannot mark as refunded")
            self.assertEqual(ops.state(ORDER), "refund_review")
            state["refunded"] = 500
            self.assertEqual(check()[0], 409, "partial refund cannot mark as full")
            self.assertEqual(ops.state(ORDER), "refund_review")
            state["refunded"] = 21450
            success = check()
            self.assertEqual(success[0], 303)
            self.assertEqual(success[1]["Location"],
                             "/shop-test-orders.html?refund_verified=1")
            self.assertEqual(ops.state(ORDER), "refunded")
            self.assertEqual(check()[0], 303, "duplicate GET never duplicates events")
            self.assertEqual(calls, [], "never create another checkout")
            with sqlite3.connect(store.db_file) as conn:
                events = [r[0] for r in conn.execute(
                    "SELECT stage FROM food_procurement_events "
                    "WHERE order_id=? ORDER BY id", (ORDER,)
                )]
                drafts = conn.execute(
                    "SELECT COUNT(*) FROM food_notification_drafts "
                    "WHERE order_id=? AND kind='customer_refund_completed'", (ORDER,)
                ).fetchone()[0]
            self.assertEqual(events, ["refund_review", "refunded"])
            self.assertEqual(drafts, 1, "refund notice is a draft, never emailed")
            completed = request(srv, "/shop-test-orders.html")
            self.assertIn("返金確認済み（テスト記録）".encode(), completed[2])
            self.assertNotIn("Square全額返金済みを照合する".encode(), completed[2])
            self.assertEqual(state["reads"], 4)
            self.assertNotIn("MOCKSQUAREPAYMENTFULL12345".encode(), completed[2])

    def test_service_case_workflow_is_paid_only_authorized_and_never_contacts_buyers(self):
        from shop_payments.retail_catalog import load_sale_catalog
        from shop_payments.sandbox_service_cases import SandboxServiceCases
        with server_with_env() as (srv, store, calls):
            store.add_pending_order(
                order_id=ORDER, cart={"A02": 1},
                verified_prices=load_sale_catalog(), shipping_yen=0,
                location_id=BASE["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
            )
            path = "/api/shop/sandbox/operator/service-case"
            self.assertEqual(request(srv, path, method="POST", auth=False,
                                     data=b"{}")[0], 401)
            not_paid = request(srv, "/shop-test-orders.html")
            self.assertNotIn("問い合わせ対応（テスト記録）".encode(), not_paid[2])
            # Obtain fresh per-page, operator-only CSRF cookie.
            cookie = not_paid[1]["Set-Cookie"].split(";",1)[0]
            base = {
                "order_id": ORDER,
                "kind": "out_of_stock",
                "expected": "none",
                "status": "open",
                "csrf": cookie.split("=",1)[1],
                "confirm": "record_only",
            }
            def action(data=base, *, auth=True, origin=ORIGIN, cook=cookie):
                return request(srv, path, method="POST", auth=auth,
                               data=urlencode(data).encode(),
                               headers={"Origin": origin, "Cookie": cook,
                               "Content-Type": "application/x-www-form-urlencoded"})
            self.assertEqual(action(auth=False)[0], 401)
            self.assertEqual(action(origin="https://attacker.invalid")[0], 403)
            self.assertEqual(action(cook="fake=x")[0], 403)
            self.assertEqual(action({**base, "kind":"other_unknown"})[0], 400)
            self.assertEqual(action({**base, "status":"resolved"})[0], 400)
            self.assertEqual(action({**base, "confirm":"really_refund"})[0], 400)
            self.assertEqual(action()[0], 409, "unpaid orders cannot create service cases")
            self.assertEqual(SandboxServiceCases(store).snapshot(ORDER), [])
            with sqlite3.connect(store.db_file) as db:
                db.execute(
                    "UPDATE orders SET state='paid',paid_at=1761780000,"
                    "square_payment_id='MOCKPAID_CASES123',"
                    "square_order_id='MOCKORDER_CASES123' WHERE order_id=?", (ORDER,)
                )
            page = request(srv, "/shop-test-orders.html")
            self.assertEqual(page[0], 200)
            self.assertIn("問い合わせ対応（テスト記録）".encode(), page[2])
            self.assertIn("模擬問い合わせの種類".encode(), page[2])
            cookie = page[1]["Set-Cookie"].split(";",1)[0]
            first = {**base,"csrf":cookie.split("=",1)[1]}
            self.assertEqual(action(first,cook=cookie)[0], 303)
            self.assertEqual(action(first,cook=cookie)[0], 409,
                             "duplicate stale case must not create a second case")
            self.assertEqual(SandboxServiceCases(store).snapshot(ORDER)[0]["status"],"open")
            page = request(srv, "/shop-test-orders.html")
            self.assertIn("仕入先欠品の対応".encode(), page[2])
            self.assertIn("対応待ち（テスト）".encode(), page[2])
            second_cookie = page[1]["Set-Cookie"].split(";",1)[0]
            next_action={**first,"status":"awaiting_customer","expected":"open",
                         "csrf":second_cookie.split("=",1)[1]}
            self.assertEqual(action(next_action,cook=second_cookie)[0],303)
            self.assertEqual(action(next_action,cook=second_cookie)[0],409)
            self.assertEqual(SandboxServiceCases(store).snapshot(ORDER)[0]["status"],
                             "awaiting_customer")
            next_page = request(srv, "/shop-test-orders.html")
            self.assertIn("お客様への確認待ち（連絡はしていません）".encode(),next_page[2])
            third_cookie=next_page[1]["Set-Cookie"].split(";",1)[0]
            done={**next_action,"expected":"awaiting_customer","status":"resolved",
                  "csrf":third_cookie.split("=",1)[1]}
            self.assertEqual(action(done,cook=third_cookie)[0],303)
            self.assertEqual(action(done,cook=third_cookie)[0],409)
            self.assertEqual(SandboxServiceCases(store).snapshot(ORDER)[0]["status"],"resolved")
            # An unrelated category has a completely independent state history.
            fourth_page=request(srv,"/shop-test-orders.html")
            fourth_cookie=fourth_page[1]["Set-Cookie"].split(";",1)[0]
            another={**first,"kind":"damaged_or_wrong",
                     "csrf":fourth_cookie.split("=",1)[1]}
            self.assertEqual(action(another,cook=fourth_cookie)[0],303)
            with sqlite3.connect(store.db_file) as db:
                events=db.execute(
                    "SELECT kind,status FROM food_sandbox_service_case_events "
                    "WHERE order_id=? ORDER BY event_id",(ORDER,)
                ).fetchall()
            self.assertEqual(events,[
                ("out_of_stock","open"),
                ("out_of_stock","awaiting_customer"),
                ("out_of_stock","resolved"),
                ("damaged_or_wrong","open"),
            ])
            self.assertEqual(calls,[], "recording must not create Square links or contacts")
            self.assertNotIn("MOCKPAID_CASES123".encode(),fourth_page[2])

    def test_preview_is_off_by_default_and_wrong_railway_services_rejected(self):
        with server_with_env({"BIGPAW_SHOP_STAGE_OPERATOR_ENABLED": "0"}) as (srv, _, _):
            self.assertEqual(request(srv, "/shop.html")[0], 200)
            self.assertEqual(request(srv, "/shop-test-orders.html")[0], 404)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/transition",
                                     method="POST", data=b"{}")[0], 404)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/tracking",
                                     method="POST", data=b"{}")[0], 404)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/review-customer",
                                     method="POST", data=b"{}")[0], 404)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/simulate-customer-notice",
                                     method="POST", data=b"{}")[0], 404)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/mock-customer-mail",
                                     method="POST", data=b"{}")[0], 404)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/verify-full-refund",
                                     method="POST", data=b"{}")[0], 404)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/service-case",
                                     method="POST", data=b"{}")[0], 404)
        for config in (
            {"BIGPAW_SHOP_STAGE_PREVIEW_ENABLED": "0"},
            {"BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD": ""},
            {"BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD": "short"},
            {"BIGPAW_ENV": "production"},
            {"RAILWAY_SERVICE_ID": "32e31163-1049-41d3-84f8-dd61a0a7019e"},
            {"RAILWAY_SERVICE_ID": "1ad6d952-c284-4886-9237-a30c364132fd"},
        ):
            # StageWebhookServer itself rejects unsafe environment identities;
            # when identity is valid, private preview URLs stay 404.
            from shop_payments.staging_https_webhook import stage_identity_ok
            with self.subTest(config=config):
                env={**BASE,**config}
                if not stage_identity_ok(env):
                    self.assertFalse(stage_identity_ok(env))
                    continue
                with server_with_env(config) as (srv, db, calls):
                    self.assertEqual(request(srv, "/shop.html")[0], 404)
                    self.assertEqual(request(srv, "/shop-test-orders.html")[0], 404)
                    self.assertEqual(request(srv, "/api/shop/sandbox/config")[0], 404)
                    self.assertEqual(request(srv, "/api/shop/sandbox/checkout", method="POST",
                                             data=b'{}')[0], 404)
                    self.assertEqual(calls, [])

if __name__ == "__main__":
    unittest.main()
