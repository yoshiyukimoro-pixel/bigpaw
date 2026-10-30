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
def server_with_env(config=None, shipping_opener=None):
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
        shipping_opener=shipping_opener,
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
                 path == "/api/shop/sandbox/operator/transition")
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
                recipient = {"display_name": "PRIVATE", "address": {
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

    def test_preview_is_off_by_default_and_wrong_railway_services_rejected(self):
        with server_with_env({"BIGPAW_SHOP_STAGE_OPERATOR_ENABLED": "0"}) as (srv, _, _):
            self.assertEqual(request(srv, "/shop.html")[0], 200)
            self.assertEqual(request(srv, "/shop-test-orders.html")[0], 404)
            self.assertEqual(request(srv, "/api/shop/sandbox/operator/transition",
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
