"""No-network integration tests for password-gated customer Sandbox checkout.

Uses loopback HTTP plus HTTPS-equivalent headers. All Square calls are mocked.
Public BIG PAW services and real users are never contacted.
"""
import base64
from contextlib import contextmanager
from http.client import HTTPConnection
import json
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
}


@contextmanager
def server_with_env(config=None):
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
        h["Authorization"] = "Basic " + base64.b64encode(
            ("shoptester:" + PASSWORD).encode()
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
            self.assertIn("noindex", r[1]["X-Robots-Tag"])
            review = request(srv, "/shop.html?order=review")
            self.assertEqual(review[0], 200)
            self.assertIn(b"shop-sandbox-review.js", review[2])
            self.assertNotIn(b'src="shop-sandbox-checkout.js"', review[2])
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

    def test_preview_is_off_by_default_and_wrong_railway_services_rejected(self):
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
                    self.assertEqual(request(srv, "/api/shop/sandbox/config")[0], 404)
                    self.assertEqual(request(srv, "/api/shop/sandbox/checkout", method="POST",
                                             data=b'{}')[0], 404)
                    self.assertEqual(calls, [])

if __name__ == "__main__":
    unittest.main()
