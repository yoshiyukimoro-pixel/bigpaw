"""Offline HTTP integration tests for the isolated, localhost-only Sandbox preview."""
from contextlib import contextmanager
from http.cookiejar import CookieJar
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from shop_payments import local_preview
from shop_payments.sandbox_connector import SandboxOrderStore

FAKE_CREDS = {
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "fake-sandbox-secret-for-offline-test",
    "BIGPAW_SQUARE_SANDBOX_LOCATION_ID": "SANDBOXLOCATION12345",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY": "fake-sandbox-signature-key",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL": "https://sandbox.example.invalid/api/shop/sandbox/webhook",
}
NO_CREDS = {k: "" for k in FAKE_CREDS}
ATTEMPT_ID = "12345678-1234-4234-8234-123456789abc"


@contextmanager
def test_server():
    with tempfile.TemporaryDirectory() as tmp:
        server = local_preview.PreviewServer(
            port=0, store=SandboxOrderStore(Path(tmp) / "shop.sqlite3")
        )
        thread = threading.Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
        thread.start()
        try:
            yield "http://127.0.0.1:%d" % server.server_port, server
        finally:
            server.shutdown()
            thread.join(timeout=5)
            server.server_close()


class TestIsolatedLocalPreview(unittest.TestCase):
    def setUp(self):
        self.configured = patch.dict(os.environ, NO_CREDS)
        self.configured.start()
        self.addCleanup(self.configured.stop)

    def _request(self, opener, url, *, method="GET", body=None, headers=None):
        req = Request(url, data=body, headers=headers or {}, method=method)
        try:
            with opener.open(req, timeout=3) as r:
                status = r.status
                data = r.read()
        except HTTPError as exc:
            status = exc.code
            data = exc.read()
        if data.startswith(b"{"):
            return status, json.loads(data)
        return status, data.decode("utf-8")

    def test_no_credentials_no_live_checkout_and_static_files_denied(self):
        with test_server() as (base, _server):
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            code, html = self._request(opener, base + "/shop.html")
            self.assertEqual(code, 200)
            self.assertIn('src="shop-sandbox-checkout.js"', html)
            self.assertIn("販売価格（税込・送料込み）", html)
            self.assertIn("shop-cart-preview.js", html)
            self.assertNotIn("shop-sandbox-checkout.js", (Path("app/shop.html").read_text()))
            self.assertEqual(self._request(opener, base + "/app/backend/server.py")[0], 404)
            self.assertEqual(self._request(opener, base + "/shop_payments/retail_pricebook.json")[0], 404)
            self.assertEqual(self._request(opener, base + "/.env")[0], 404)
            _, config = self._request(opener, base + "/api/shop/sandbox/config")
            self.assertEqual(config["ready"], False)
            self.assertTrue(config["sandbox"])
            code, error = self._request(opener, base + "/api/shop/sandbox/checkout", method="POST",
                body=json.dumps({"cart": {"A02": 1}, "attempt_id": ATTEMPT_ID}).encode(), headers={
                    "Origin": base, "Content-Type": "application/json",
                    "X-Shop-CSRF": config["csrf_token"]
                })
            self.assertEqual(code, 503)
            self.assertEqual(error["error"], "sandbox_not_configured")

    def test_sandbox_review_bridge_is_isolated_from_public_site(self):
        with test_server() as (base, _server):
            opener = build_opener(HTTPCookieProcessor(CookieJar()))
            code, review = self._request(opener, base + "/shop.html?order=review")
            self.assertEqual(code, 200)
            self.assertIn('src="shop-sandbox-review.js"', review)
            self.assertNotIn('src="shop-sandbox-checkout.js"', review)
            code, listing = self._request(opener, base + "/shop.html")
            self.assertEqual(code, 200)
            self.assertIn('src="shop-sandbox-checkout.js"', listing)
            self.assertNotIn('src="shop-sandbox-review.js"', listing)
            live_html = Path("app/shop.html").read_text(encoding="utf-8")
            self.assertNotIn('shop-sandbox-review.js', live_html)
            code, source = self._request(opener, base + "/shop-sandbox-review.js")
            self.assertEqual(code, 200)
            self.assertIn("squareReviewSandboxCheckout", source)
            self.assertNotIn("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", source)
            # No path traversal, keys, or actual credit card fields served.
            self.assertEqual(self._request(opener, base + "/.env")[0], 404)
            self.assertEqual(self._request(opener, base + "/shop_payments/retail_pricebook.json")[0], 404)
            with opener.open(base + "/assets/shop-details/products/A02/ingredients.webp") as image_response:
                self.assertEqual(image_response.status, 200)
                self.assertEqual(image_response.headers.get("Content-Type"), "image/webp")

    def test_forged_origin_and_browser_price_manipulation(self):
        with patch.dict(os.environ, FAKE_CREDS):
            with test_server() as (base, _server):
                opener = build_opener(HTTPCookieProcessor(CookieJar()))
                _, config = self._request(opener, base + "/api/shop/sandbox/config")
                self.assertTrue(config["ready"])
                no_csrf = {"Origin": "https://attacker.invalid", "Content-Type": "application/json",
                           "X-Shop-CSRF": config["csrf_token"]}
                self.assertEqual(self._request(opener, base + "/api/shop/sandbox/checkout",
                    method="POST", body=b'{"cart":{"A02":1}}',headers=no_csrf)[0], 403)
                req_headers = {"Origin": base, "Content-Type": "application/json",
                               "X-Shop-CSRF": config["csrf_token"]}
                malicious = json.dumps({"cart":{"A02":1},"attempt_id":ATTEMPT_ID,"price_yen":1}).encode()
                self.assertEqual(self._request(opener, base + "/api/shop/sandbox/checkout",
                    method="POST", body=malicious,headers=req_headers)[0], 400)
                fake_quantity = json.dumps({"cart":{"A02":"1"},"attempt_id":ATTEMPT_ID}).encode()
                self.assertEqual(self._request(opener, base + "/api/shop/sandbox/checkout",
                    method="POST", body=fake_quantity,headers=req_headers)[0], 400)

    def test_full_fake_checkout_and_signed_webhook(self):
        fake_link = {
            "url": "https://sandbox.square.link/u/mock-checkout",
            "square_order_id": "SQUAREORDER_FAKE001",
            "square_link_id": "SQUARELINK_FAKE001",
        }
        with patch.dict(os.environ, FAKE_CREDS):
            with test_server() as (base, server):
                opener = build_opener(HTTPCookieProcessor(CookieJar()))
                _, config = self._request(opener, base + "/api/shop/sandbox/config")
                self.assertTrue(config["ready"])
                headers = {"Origin": base, "Content-Type":"application/json",
                           "X-Shop-CSRF":config["csrf_token"]}
                with patch.object(local_preview, "create_square_sandbox_payment_link", return_value=fake_link) as mock:
                    code, order = self._request(opener, base + "/api/shop/sandbox/checkout",
                        method="POST",body=json.dumps({"cart":{"A02":2,"Z01":1},"attempt_id":ATTEMPT_ID}).encode(),
                        headers=headers)
                self.assertEqual(code, 200)
                self.assertEqual(order["amount_yen"], 85800)
                self.assertEqual(order["shipping_yen"], 0)
                self.assertEqual(order["checkout_url"], fake_link["url"])
                # Retry the same attempt. It MUST reuse the exact same link,
                # without contacting Square or creating another order.
                code2, again = self._request(opener, base + "/api/shop/sandbox/checkout",
                    method="POST",
                    body=json.dumps({"cart":{"A02":2,"Z01":1},"attempt_id":ATTEMPT_ID}).encode(),
                    headers=headers)
                self.assertEqual(code2, 200)
                self.assertEqual(again["order_id"], order["order_id"])
                self.assertEqual(again["checkout_url"], order["checkout_url"])
                self.assertEqual(mock.call_count, 1)
                self.assertEqual(self._request(opener, base + "/api/shop/sandbox/checkout",
                    method="POST",
                    body=json.dumps({"cart":{"A02":1},"attempt_id":ATTEMPT_ID}).encode(),
                    headers=headers)[0], 400)
                self.assertEqual(mock.call_count, 1)
                args, kwargs = mock.call_args
                self.assertEqual(args[0]["order"]["line_items"][0]["base_price_money"]["amount"],21450)
                self.assertEqual(len(args[0]["order"]["line_items"]), 2)
                order_id = order["order_id"]
                self.assertEqual(server.store.status(order_id),"payment_pending")
                code, state = self._request(opener, base + "/api/shop/sandbox/order/" + order_id)
                self.assertEqual(code, 200)
                self.assertEqual(state["order_status"], "payment_pending")

                event = {
                    "event_id":"sandbox-test-event-123", "type":"payment.updated",
                    "data":{"object":{"payment":{
                        "id":"PAYMENTTEST001",
                        "order_id":fake_link["square_order_id"],
                        "location_id":FAKE_CREDS["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
                        "status":"COMPLETED",
                        "amount_money":{"amount":85800,"currency":"JPY"},
                    }}}
                }
                raw = json.dumps(event).encode()
                signature = base64.b64encode(hmac.new(
                    FAKE_CREDS["BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY"].encode(),
                    FAKE_CREDS["BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL"].encode() + raw,
                    hashlib.sha256).digest()).decode()
                sig_headers = {"Content-Type":"application/json",
                               "X-Square-Hmacsha256-Signature":signature}
                # A signed webhook alone must NOT mark paid. Only a fresh
                # independent Square Payments API read can confirm.
                payment_from_square = {
                    "id":"PAYMENTTEST001",
                    "status":"COMPLETED",
                    "order_id":fake_link["square_order_id"],
                    "location_id":FAKE_CREDS["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
                    "amount_money":{"amount":85800,"currency":"JPY"}
                }
                with patch.object(local_preview, "retrieve_verified_sandbox_payment",
                                  return_value={**payment_from_square, "status":"PENDING"}):
                    self.assertEqual(self._request(opener, base+"/api/shop/sandbox/webhook",
                        method="POST",body=raw,headers=sig_headers)[0], 503)
                    self.assertEqual(server.store.status(order_id), "payment_pending")
                with patch.object(local_preview, "retrieve_verified_sandbox_payment",
                                  return_value=payment_from_square) as lookup:
                    self.assertEqual(self._request(opener, base+"/api/shop/sandbox/webhook",
                        method="POST",body=raw,headers=sig_headers)[0], 200)
                    self.assertEqual(lookup.call_count, 1)
                    self.assertEqual(server.store.status(order_id), "paid")
                    self.assertEqual(self._request(opener, base+"/api/shop/sandbox/webhook",
                        method="POST",body=raw,headers=sig_headers)[0], 200)
                    self.assertEqual(server.store.status(order_id), "paid")

    def test_bad_signature_rejected_and_no_fake_mark_paid(self):
        with patch.dict(os.environ, FAKE_CREDS):
            with test_server() as (base, _server):
                opener = build_opener()
                code, _ = self._request(opener, base+"/api/shop/sandbox/webhook",
                    method="POST", body=b'{"event_id":"forged"}',
                    headers={"X-Square-Hmacsha256-Signature": "fake"})
                self.assertEqual(code, 403)


if __name__ == "__main__":
    unittest.main()
