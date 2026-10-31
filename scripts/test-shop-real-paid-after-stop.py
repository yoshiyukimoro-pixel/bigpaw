"""No-network tests for the isolated paid-order durability proof after STOP."""
import base64
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
from unittest.mock import patch
import unittest

spec=importlib.util.spec_from_file_location("poststop",Path("scripts/check-shop-real-sandbox-paid-after-stop.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
TOKEN="SANDBOX_FAKE_TOKEN"
LOCATION="FAKE_SANDBOX_LOCATION"
SECRET="FAKE_STAGING_PRIVATE_SIGNATURE"
SQUARE_ORDER="SQ_ORDER_TEST"
PID="SQ_PAYMENT_TEST"

class Tests(unittest.TestCase):
    def test_only_exact_timewindow_and_one_link(self):
        sample={
            "payment_links":[
                {"created_at":"2026-10-31T01:13:18Z",
                 "payment_note":"BIG PAW food order FOOD"+"a"*32,
                 "order_id":SQUARE_ORDER},
                {"created_at":"2026-10-31T00:13:18Z",
                 "payment_note":"BIG PAW food order FOOD"+"b"*32,
                 "order_id":"WRONG"},
            ]
        }
        with patch.object(m.base,"_square_get",return_value=sample):
            self.assertEqual(m._test_link(TOKEN),SQUARE_ORDER)
        sample["payment_links"][1]["created_at"]="2026-10-31T01:13:18Z"
        with patch.object(m.base,"_square_get",return_value=sample):
            with self.assertRaises(ValueError):m._test_link(TOKEN)
    def test_existing_paid_order_persists_without_sandbox_writes(self):
        calls=[]
        payment={
            "id":PID,"order_id":SQUARE_ORDER,
            "location_id":LOCATION,"status":"COMPLETED",
            "amount_money":{"amount":21450,"currency":"JPY"},
            "refunded_money":{"amount":0,"currency":"JPY"},
        }
        def sq(url,token):
            self.assertEqual(token,TOKEN)
            calls.append(("square",url))
            self.assertTrue(url.startswith(m.SQUARE+"/"))
            if url.endswith("/orders/"+SQUARE_ORDER):
                return {"order":{"id":SQUARE_ORDER,"tenders":[{"id":PID}]}}
            if url.endswith("/payments/"+PID):
                return {"payment":payment}
            self.fail("Unexpected Square URL")
        def http(path,*,method,body,accept_status,extra):
            calls.append(("new_webhook",path,method))
            self.assertEqual(path,"/api/shop/sandbox/webhook")
            self.assertEqual(method,"POST")
            self.assertEqual(accept_status,200)
            self.assertEqual(extra["Square-Environment"],"Sandbox")
            signed=base64.b64encode(hmac.new(
                SECRET.encode(),m.TARGET.encode()+body,hashlib.sha256).digest()).decode()
            self.assertEqual(extra["X-Square-Hmacsha256-Signature"],signed)
            self.assertEqual(json.loads(body)["data"]["object"]["payment"],payment)
            return 200,{},b'{"status":"received"}'
        with patch.object(m,"_scope",return_value=(TOKEN,LOCATION,SECRET)),patch.object(m.base,"_assert_square_subscription_safety",return_value=True),patch.object(m,"_test_link",return_value=SQUARE_ORDER),patch.object(m.base,"_square_get",side_effect=sq),patch.object(m.base,"_http",side_effect=http):
            m.audit()
        self.assertEqual([c[0] for c in calls],["square","square","new_webhook"])
    def test_provider_refund_never_replays_hmac(self):
        pay={
            "id":PID,"order_id":SQUARE_ORDER,"location_id":LOCATION,
            "status":"COMPLETED","amount_money":{"amount":21450,"currency":"JPY"},
            "refunded_money":{"amount":21450,"currency":"JPY"},
        }
        def sq(url,token):
            if "/orders/" in url:return {"order":{"id":SQUARE_ORDER,"tenders":[{"id":PID}]}}
            return {"payment":pay}
        with patch.object(m,"_scope",return_value=(TOKEN,LOCATION,SECRET)),patch.object(m.base,"_assert_square_subscription_safety",return_value=True),patch.object(m,"_test_link",return_value=SQUARE_ORDER),patch.object(m.base,"_square_get",side_effect=sq),patch.object(m.base,"_http") as http:
            with self.assertRaises(ValueError):m.audit()
            http.assert_not_called()

if __name__=="__main__":unittest.main()
