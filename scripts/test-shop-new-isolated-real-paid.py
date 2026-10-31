"""Offline fail-closed tests for isolated real Square Sandbox hosted checkout.
ALL Railway and Square network calls are mocked; never charge a card or
construct a production checkout. These are contract tests, not payment proof.
"""
import base64
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import uuid
import unittest

spec=importlib.util.spec_from_file_location(
    "isolated",Path("scripts/smoke-shop-new-isolated-paid-checkout.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ORDER_UUID=uuid.UUID("aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa")
ORDER_ID="FOOD"+str(ORDER_UUID).replace("-","")
TOKEN="SANDBOX_FAKE_TOKEN"
LOCATION="TEST_SANDBOX_LOCATION"
SIGNING="synthetic-signing-key-only-for-offline-tests-123"
CONF={"user":"localtest","password":"synthetic-local-32-character-password",
      "sigkey":SIGNING,"square_token":TOKEN,"location":LOCATION}
SQUARE_ORDER="SQUARE_SANDBOX_ORDER_123"
PAYMENT_ID="SQUARE_SANDBOX_PAYMENT_123"
LINK="https://sandbox.square.link/u/NOT_A_REAL_CHECKOUT"
AMOUNT=21450

class ReadOnlyTests(unittest.TestCase):
    def test_environment_guard_denies_without_network(self):
        with patch.dict(m.os.environ,{},clear=True):
            with self.assertRaises(ValueError):
                m._scope(None)

    def test_prepare_creates_one_link_only_and_confirms_pending(self):
        calls=[]
        def fake(path,auth=None,*,method="GET",body=None,extra=None,accept_status=None):
            calls.append((path,method))
            self.assertIs(auth,CONF)
            if path=="/shop.html":
                return 200,{},b"SHOP"
            if path=="/api/shop/sandbox/config":
                return 200,{"Set-Cookie":"bigpaw_shop_sandbox_csrf=abcxyz; Path=/"},json.dumps(
                    {"ready":True,"sandbox":True,"csrf_token":"z"*48}).encode()
            if path=="/api/shop/sandbox/checkout":
                self.assertEqual(method,"POST")
                self.assertEqual(extra["Origin"],m.BASE)
                self.assertEqual(json.loads(body),{"attempt_id":str(ORDER_UUID),"cart":{"A02":1}})
                return 200,{},json.dumps({
                    "order_id":ORDER_ID,"checkout_url":LINK,
                    "amount_yen":AMOUNT,"shipping_yen":0}).encode()
            if path=="/api/shop/sandbox/order/"+ORDER_ID:
                return 200,{},b'{"order_status":"payment_pending"}'
            self.fail("Unexpected API path")
        with tempfile.TemporaryDirectory() as folder:
            state=Path(folder)/"run.json"
            with patch.object(m,"_scope",return_value=CONF),patch.object(m,"_http",side_effect=fake),patch.object(m,"_file",return_value=state),patch.object(m.uuid,"uuid4",return_value=ORDER_UUID):
                m.prepare()
            self.assertEqual([c for c in calls if c[1]=="POST"],
                             [("/api/shop/sandbox/checkout","POST")])
            saved=json.loads(state.read_text())
            self.assertEqual(saved["shop_order_id"],ORDER_ID)
            self.assertEqual(saved["amount_yen"],AMOUNT)

    def test_remote_receipt_hmac_repeat_without_duplicate_square_post(self):
        calls=[]
        state={"link_url":LINK,"shop_order_id":ORDER_ID,"amount_yen":AMOUNT}
        sqget=[]
        payment={"id":PAYMENT_ID,"order_id":SQUARE_ORDER,
                 "status":"COMPLETED","location_id":LOCATION,
                 "amount_money":{"amount":AMOUNT,"currency":"JPY"}}
        def square(url,token):
            self.assertEqual(token,TOKEN)
            sqget.append(url)
            self.assertTrue(url.startswith(m.SQUARE+"/"))
            if "/online-checkout/payment-links?" in url:
                return {"payment_links":[{"url":LINK,"order_id":SQUARE_ORDER}]}
            if url.endswith("/orders/"+SQUARE_ORDER):
                return {"order":{"id":SQUARE_ORDER,"tenders":[{"id":PAYMENT_ID}]}}
            if url.endswith("/payments/"+PAYMENT_ID):
                return {"payment":payment}
            self.fail("Unexpected Square request")
        def fake(path,auth=None,*,method="GET",body=None,extra=None,accept_status=None):
            calls.append((path,method))
            if path.endswith(ORDER_ID):
                return 200,{},json.dumps({"order_status":"paid" if len(
                    [c for c in calls if c[0]=="/api/shop/sandbox/webhook"])>=1 else "payment_pending"}).encode()
            if path=="/api/shop/sandbox/webhook":
                self.assertIsNone(auth)
                self.assertEqual(method,"POST")
                self.assertEqual(extra["Square-Environment"],"Sandbox")
                self.assertEqual(json.loads(body)["data"]["object"]["payment"],payment)
                signature=base64.b64encode(hmac.new(SIGNING.encode(),m.WEBHOOK.encode()+body,hashlib.sha256).digest()).decode()
                self.assertEqual(signature,extra["X-Square-Hmacsha256-Signature"])
                return 200,{},b'{"status":"received"}'
            self.fail("Unexpected webhook path")
        with tempfile.TemporaryDirectory() as folder:
            f=Path(folder)/"state.json"
            f.write_text(json.dumps(state))
            with patch.object(m,"_scope",return_value=CONF),patch.object(m,"_square_get",side_effect=square),patch.object(m,"_http",side_effect=fake),patch.object(m,"_file",return_value=f):
                m.verify()
        self.assertEqual(len(sqget),3)
        self.assertEqual([c[1] for c in calls if c[1]=="POST"],["POST","POST"])
        self.assertEqual(len([c for c in calls if c[0]=="/api/shop/sandbox/checkout"]),0)

if __name__=="__main__":
    unittest.main()
