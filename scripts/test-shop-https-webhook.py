"""Offline HTTP tests for the isolated Square Sandbox staging webhook.

All HTTP traffic is loopback; Square API and Resend API are mocked, and no
production site, credentials, Square card or provider inbox is contacted.
"""
import base64
from contextlib import contextmanager
import hashlib
import hmac
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Event, Thread
import unittest

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.sandbox_notifications import SandboxNotificationDrafts
from shop_payments.staging_https_webhook import (
    StageWebhookServer, WEBHOOK_PATH, stage_ready,
)

URL = "https://shop-sandbox.example.invalid" + WEBHOOK_PATH
KEY = "FAKE_STAGE_SIGNATURE"
ORDER = "FOOD" + "b" * 32
SQUARE_ORDER = "SANDBOX_ORDER_12345"
PAYMENT = "SANDBOX_PAYMENT_12345"
LOCATION = "SANDBOX_LOCATION_12345"
STAGING = {
    "BIGPAW_ENV": "sandbox",
    "BIGPAW_SHOP_STAGING_ISOLATED": "1",
    "BIGPAW_SHOP_STAGING_HTTPS_ENABLED": "1",
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "sandbox-not-real-token",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY": KEY,
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL": URL,
    "BIGPAW_SQUARE_SANDBOX_LOCATION_ID": LOCATION,
}
FULL_PAYMENT = {
    "id": PAYMENT,
    "order_id": SQUARE_ORDER,
    "location_id": LOCATION,
    "status": "COMPLETED",
    "amount_money": {"amount": 21450, "currency": "JPY"},
}


@contextmanager
def stage_server(*, payment_lookup=None, notify=None):
    folder = tempfile.TemporaryDirectory()
    store = SandboxOrderStore(Path(folder.name) / "shop-stage.sqlite3")
    store.add_pending_order(
        order_id=ORDER, cart={"A02": 1}, verified_prices=load_sale_catalog(),
        shipping_yen=0, location_id=LOCATION,
    )
    store.save_link(ORDER, {
        "url": "https://sandbox.square.link/u/staging-test",
        "square_order_id": SQUARE_ORDER,
        "square_link_id": "SANDBOX_LINK_12345",
    })
    server = StageWebhookServer(
        env=STAGING, store=store, host="127.0.0.1", port=0,
        payment_lookup=payment_lookup or (lambda _: dict(FULL_PAYMENT)),
        notify=notify or (lambda **_: None),
    )
    runner = Thread(target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True)
    runner.start()
    try:
        yield server, store
    finally:
        server.shutdown()
        runner.join(timeout=3)
        server.server_close()
        folder.cleanup()


def event(*, event_id="sandbox-stage-event-1", status="COMPLETED"):
    pay = {**FULL_PAYMENT, "status": status}
    return json.dumps({
        "event_id": event_id, "type": "payment.updated",
        "data": {"object": {"payment": pay}},
    }).encode()


def signature(body: bytes, url=URL):
    return base64.b64encode(hmac.new(
        KEY.encode(), url.encode() + body, hashlib.sha256,
    ).digest()).decode()


def request(server, *, method="POST", path=WEBHOOK_PATH, body=None, headers=None):
    conn = HTTPConnection("127.0.0.1", server.server_port, timeout=3)
    try:
        conn.request(method, path, body=body, headers=headers or {})
        resp = conn.getresponse()
        return resp.status, json.loads(resp.read())
    finally:
        conn.close()


def signed_headers(body, **overrides):
    return {
        "Content-Type": "application/json",
        "Square-Environment": "Sandbox",
        "X-Square-Hmacsha256-Signature": signature(body),
        **overrides,
    }


class TestStageWebhook(unittest.TestCase):
    def test_fails_closed_on_prod_and_bad_urls(self):
        self.assertTrue(stage_ready(STAGING))
        for env in (
            {**STAGING, "BIGPAW_ENV": "production"},
            {**STAGING, "BIGPAW_SHOP_STAGING_ISOLATED": "0"},
            {**STAGING, "BIGPAW_SHOP_STAGING_HTTPS_ENABLED": "0"},
            {**STAGING, "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL": URL + "/"},
            {**STAGING, "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL": URL.replace("https", "http")},
            {**STAGING, "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": ""},
            {**STAGING, "RAILWAY_PROJECT_ID": "afb79723-1a2d-4c43-b498-f166e501760c"},
            {**STAGING, "RAILWAY_PROJECT_ID": "d70f7165-f5eb-41e8-95a0-62f85ff90478"},
            {**STAGING, "RAILWAY_PROJECT_ID": "unknown"},
        ):
            self.assertFalse(stage_ready(env))
        isolated = {**STAGING,
                    "RAILWAY_PROJECT_ID": "isolated-sandbox-project",
                    "RAILWAY_ENVIRONMENT_ID": "staging-only",
                    "RAILWAY_SERVICE_ID": "webhook-only",
                    "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID": "isolated-sandbox-project"}
        self.assertTrue(stage_ready(isolated))
        existing_test = {**STAGING,
            "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL":
                "https://bigpaw-test-production.up.railway.app" + WEBHOOK_PATH,
            "RAILWAY_PROJECT_ID": "d70f7165-f5eb-41e8-95a0-62f85ff90478",
            "RAILWAY_ENVIRONMENT_ID": "ecc9fcbf-496f-4b51-a651-65a46a971588",
            "RAILWAY_SERVICE_ID": "1a1a32bd-e885-4848-a6b5-fde5ef9ac902",
            "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID":
                "d70f7165-f5eb-41e8-95a0-62f85ff90478",
        }
        self.assertTrue(stage_ready(existing_test))
        for service_id in (
            "32e31163-1049-41d3-84f8-dd61a0a7019e",  # bigpaw-site
            "1ad6d952-c284-4886-9237-a30c364132fd",  # bigpaw-web
            "wrong-service-id",
        ):
            self.assertFalse(stage_ready({
                **existing_test, "RAILWAY_SERVICE_ID": service_id
            }))
        self.assertFalse(stage_ready({
            **existing_test, "RAILWAY_ENVIRONMENT_ID": "wrong-environment"
        }))
        self.assertFalse(stage_ready({
            **existing_test, "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID": ""
        }))

    def test_standby_server_never_accepts_webhook_without_secrets(self):
        import copy
        from shop_payments.staging_https_webhook import stage_identity_ok
        standby = {**STAGING, "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "",
                   "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY": ""}
        self.assertTrue(stage_identity_ok(standby))
        self.assertFalse(stage_ready(standby))
        with tempfile.TemporaryDirectory() as folder:
            store = SandboxOrderStore(Path(folder) / "safe-standby.sqlite3")
            server = StageWebhookServer(
                env=standby, store=store, host="127.0.0.1", port=0,
            )
            runner = Thread(target=server.serve_forever,
                            kwargs={"poll_interval": 0.01}, daemon=True)
            runner.start()
            try:
                status, payload = request(server, method="GET", path="/healthz")
                self.assertEqual(status, 200)
                self.assertEqual(payload["status"], "sandbox_webhook_standby")
                body = event()
                self.assertEqual(
                    request(server, body=body, headers=signed_headers(body))[0],
                    503,
                )
                self.assertEqual(store.status(ORDER), "not_found")
            finally:
                server.shutdown()
                runner.join(timeout=3)
                server.server_close()

    def test_only_health_and_signed_webhook_are_exposed(self):
        with stage_server() as (server, store):
            self.assertEqual(request(server, method="GET", path="/healthz")[0], 200)
            for path in ("/", "/shop.html", "/admin", "/api/shop/sandbox/checkout",
                         "/api/shop/sandbox/order/FOODxxx", "/.env"):
                self.assertEqual(request(server, method="GET", path=path)[0], 404)
            self.assertEqual(request(server, body=b'{}', headers={})[0], 403)
            body = event()
            self.assertEqual(request(server, body=body, headers=signed_headers(
                body, **{"Square-Environment": "Production"}))[0], 403)
            self.assertEqual(request(server, body=body, headers={
                **signed_headers(body), "Content-Type": "text/plain"})[0], 415)
            self.assertEqual(request(server, body=body, headers={
                **signed_headers(body), "X-Square-Hmacsha256-Signature": "bad"})[0], 403)
            self.assertEqual(store.status(ORDER), "payment_pending")

    def test_verified_paid_acknowledged_once_and_mail_after_commit(self):
        notice = Event()
        sent = []
        lookups = []
        def lookup(pid):
            lookups.append(pid)
            return dict(FULL_PAYMENT)
        def notify(**kwargs):
            self.assertEqual(kwargs["webhook_status"], "paid")
            self.assertEqual(kwargs["store"].status(ORDER), "paid")
            self.assertEqual(kwargs["env"]["BIGPAW_ENV"], "sandbox")
            sent.append(1)
            notice.set()
        with stage_server(payment_lookup=lookup, notify=notify) as (server, store):
            body = event()
            self.assertEqual(request(server, body=body, headers=signed_headers(body))[0], 200)
            self.assertTrue(notice.wait(2))
            self.assertEqual(store.status(ORDER), "paid")
            self.assertEqual(lookups, [PAYMENT])
            self.assertEqual(len(SandboxNotificationDrafts(store).pending()), 3)
            self.assertEqual(request(server, body=body, headers=signed_headers(body))[0], 200)
            self.assertEqual(len(sent), 1)
            self.assertEqual(lookups, [PAYMENT])

    def test_pending_or_nonmatching_sandbox_payment_never_notifies(self):
        calls = []
        with stage_server(payment_lookup=lambda pid: {
                **FULL_PAYMENT, "status": "PENDING"},
                notify=lambda **kwargs: calls.append(kwargs)) as (server, store):
            body = event()
            self.assertEqual(request(server, body=body, headers=signed_headers(body))[0], 503)
            self.assertEqual(store.status(ORDER), "payment_pending")
            self.assertEqual(calls, [])
            self.assertEqual(SandboxNotificationDrafts(store).pending(), [])

    def test_wrong_amount_from_api_not_paid(self):
        with stage_server(payment_lookup=lambda pid: {
                **FULL_PAYMENT, "amount_money": {"amount": 1, "currency": "JPY"}}
                ) as (server, store):
            body = event()
            self.assertEqual(request(server, body=body, headers=signed_headers(body))[0], 503)
            self.assertEqual(store.status(ORDER), "payment_pending")

    def test_signature_url_must_match_exactly(self):
        with stage_server() as (server, store):
            body = event()
            self.assertEqual(request(server, body=body, headers={
                **signed_headers(body), "X-Square-Hmacsha256-Signature":
                signature(body, url=URL + "/")})[0], 403)
            self.assertEqual(store.status(ORDER), "payment_pending")


if __name__ == "__main__":
    unittest.main()
