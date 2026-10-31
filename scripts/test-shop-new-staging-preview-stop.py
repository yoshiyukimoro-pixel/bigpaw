"""Offline contract: isolated staging Sandbox preview can stop new checkout
while the same durable store still processes an authenticated paid webhook.
NO Square API, mail, production endpoint, or external network.
"""
import base64
from contextlib import contextmanager
import hashlib
import hmac
from http.client import HTTPConnection
import json
from pathlib import Path
import tempfile
from threading import Thread
import unittest

from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.staging_https_webhook import StageWebhookServer, WEBHOOK_PATH
from shop_payments.sandbox_runtime_guard import (
    NEW_STAGING_PROJECT, NEW_STAGING_ENVIRONMENT, NEW_SANDBOX_WEBHOOK_SERVICE,
)
HOST = "bigpaw-square-sandbox-staging-staging.up.railway.app"
ORIGIN = "https://" + HOST
USER = "isolatedonly"
PASSWORD = "synthetic-not-production-32char-test-password"
KEY = "synthetic-new-target-hmac-test-signing-key"
ORDER_ID = "FOOD" + "a" * 32
PAYMENT_ID = "SYNTHETIC_LOCAL_PAYMENT_1234"
SQUARE_ORDER = "SYNTHETIC_LOCAL_SQUARE_ORDER_1234"
LOCATION = "SANDBOX_LOCATION_12345"
ENV = {
    "RAILWAY_PROJECT_ID": NEW_STAGING_PROJECT,
    "RAILWAY_ENVIRONMENT_ID": NEW_STAGING_ENVIRONMENT,
    "RAILWAY_SERVICE_ID": NEW_SANDBOX_WEBHOOK_SERVICE,
    "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID": NEW_STAGING_PROJECT,
    "BIGPAW_ENV": "sandbox",
    "BIGPAW_SHOP_STAGING_ISOLATED": "1",
    "BIGPAW_SHOP_STAGING_HTTPS_ENABLED": "1",
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "NOT_A_REAL_SECRET",
    "BIGPAW_SQUARE_SANDBOX_LOCATION_ID": LOCATION,
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY": KEY,
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL": ORIGIN + WEBHOOK_PATH,
    "BIGPAW_SHOP_STAGE_PREVIEW_ENABLED": "1",
    "BIGPAW_SHOP_STAGE_PREVIEW_USER": USER,
    "BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD": PASSWORD,
    "BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED": "0",
}

def call(server, path, method="GET", body=None, *, host=HOST, auth=True, headers=None):
    h = {"Host": host, **(headers or {})}
    if auth:
        h["Authorization"] = "Basic " + base64.b64encode(
            (USER + ":" + PASSWORD).encode()).decode()
    if body is not None:
        h["Content-Type"] = "application/json"
    conn = HTTPConnection("127.0.0.1",server.server_port,timeout=5)
    try:
        conn.request(method,path,body=body,headers=h)
        resp = conn.getresponse()
        data = resp.read()
        return resp.status, dict(resp.getheaders()), data
    finally:
        conn.close()

class NewSandboxPreviewStop(unittest.TestCase):
    def test_optin_checkout_stop_and_verified_webhook_independent(self):
        from shop_payments.staging_checkout_preview import enabled
        self.assertTrue(enabled(ENV))
        self.assertFalse(enabled({**ENV, "BIGPAW_SHOP_STAGE_PREVIEW_ENABLED":"0"}))
        self.assertFalse(enabled({**ENV, "RAILWAY_SERVICE_ID":"WRONG_SERVICE"}))
        with tempfile.TemporaryDirectory() as folder:
            db=SandboxOrderStore(Path(folder)/"orders.sqlite3")
            calls=[]
            payment={
                "id":PAYMENT_ID, "order_id":SQUARE_ORDER,
                "location_id":LOCATION, "status":"COMPLETED",
                "amount_money":{"amount":21450,"currency":"JPY"},
            }
            def fake_creator(payload,*,token):
                calls.append(payload["idempotency_key"])
                self.assertEqual(token,"NOT_A_REAL_SECRET")
                return {
                    "url":"https://sandbox.square.link/u/SYNTHETIC_ONLY",
                    "square_order_id":SQUARE_ORDER,
                    "square_link_id":"SYNTHETIC_LOCAL_SQUARE_LINK_1234",
                }
            messages=[]
            svr=StageWebhookServer(
                env=ENV,store=db,checkout_creator=fake_creator,
                payment_lookup=lambda _:dict(payment),
                notify=lambda **kwargs:messages.append(kwargs),
                host="127.0.0.1",port=0,
            )
            t=Thread(target=svr.serve_forever,daemon=True)
            t.start()
            try:
                self.assertEqual(call(svr,"/shop.html",auth=False)[0],401)
                self.assertEqual(call(svr,"/shop.html",host="other.example.invalid")[0],400)
                self.assertEqual(call(svr,"/shop.html")[0],200)
                status,header,raw=call(svr,"/api/shop/sandbox/config")
                self.assertEqual(status,200)
                cfg=json.loads(raw)
                self.assertEqual(cfg["ready"],True)
                cookie=header["Set-Cookie"].split(";",1)[0]
                h={"Origin":ORIGIN,"Cookie":cookie,
                   "X-Shop-CSRF":cfg["csrf_token"]}
                self.assertEqual(call(svr,"/api/shop/sandbox/quote","POST",
                                      b'{"cart":{"A02":1}}',headers=h)[0],200)
                attempt = "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa"
                status,_,raw=call(svr,"/api/shop/sandbox/checkout","POST",
                    json.dumps({"attempt_id":attempt,"cart":{"A02":1}}).encode(),headers=h)
                self.assertEqual(status,200,raw)
                snapshot=json.loads(raw)
                self.assertEqual(snapshot["order_id"],ORDER_ID)
                self.assertEqual(snapshot["amount_yen"],21450)
                self.assertEqual(snapshot["shipping_yen"],0)
                self.assertEqual(db.status(ORDER_ID),"payment_pending")
                self.assertEqual(len(calls),1)
                # Emergency stop blocks all future test checkouts, including
                # a new distinct attempt; the old order remains payable.
                svr.env["BIGPAW_SHOP_STAGE_PREVIEW_ENABLED"]="0"
                status,_,_=call(svr,"/api/shop/sandbox/checkout","POST",
                    json.dumps({"attempt_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                                "cart":{"A02":1}}).encode(),headers=h)
                self.assertEqual(status,404)
                self.assertEqual(len(calls),1)
                self.assertEqual(db.status(ORDER_ID),"payment_pending")
                event={"event_id":"SYNTHETIC_LOCAL_PAID_EVENT_1234",
                       "type":"payment.updated",
                       "data":{"object":{"payment":dict(payment)}}}
                raw=json.dumps(event,separators=(",",":")).encode()
                sig=base64.b64encode(hmac.new(
                    KEY.encode(),(ORIGIN+WEBHOOK_PATH).encode()+raw,hashlib.sha256
                ).digest()).decode()
                status,_,_=call(svr,WEBHOOK_PATH,"POST",raw,auth=False,
                     headers={"Square-Environment":"Sandbox",
                              "X-Square-Hmacsha256-Signature":sig})
                self.assertEqual(status,200)
                self.assertEqual(db.status(ORDER_ID),"paid")
                self.assertIsNotNone(db.paid_order_snapshot(ORDER_ID))
                status,_,_=call(svr,WEBHOOK_PATH,"POST",raw,auth=False,
                     headers={"Square-Environment":"Sandbox",
                              "X-Square-Hmacsha256-Signature":sig})
                self.assertEqual(status,200)
                self.assertEqual(db.status(ORDER_ID),"paid")
            finally:
                svr.shutdown();t.join(timeout=4);svr.server_close()

if __name__=="__main__":
    unittest.main()
