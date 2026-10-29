"""Offline safety/functional tests for opt-in Square Sandbox real-card probe."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location(
    "square_card_smoke",Path("scripts/smoke-shop-square-card-payment.py"))
smoke=importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
ENV={
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE_SANDBOX_SECRET_DO_NOT_LOG",
    "BIGPAW_SQUARE_SANDBOX_LOCATION_ID":"SANDBOXLOCATION12345",
}


class TestSquareCardSmoke(unittest.TestCase):
    def test_no_credentials_never_makes_network_request(self):
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result=smoke.main(env={},
                link_creator=lambda *a,**k:self.fail("network"),
                payment_creator=lambda **k:self.fail("network"),
                payment_reader=lambda *a,**k:self.fail("network"))
        self.assertEqual(result,2)
        self.assertIn("NOT_CONFIGURED",out.getvalue())

    def test_realistic_paid_order_and_duplicate_reconciliation_offline(self):
        calls={"payment":0,"read":0,"link":0}
        square_order="TESTSQUAREORDER123456"
        payment_id="TESTSQUAREPAYMENT123456"
        def link(payload,*,token):
            self.assertEqual(token,ENV["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"])
            self.assertEqual(payload["order"]["line_items"][0]["base_price_money"]["amount"],21450)
            self.assertEqual(payload["checkout_options"]["ask_for_shipping_address"],True)
            calls["link"]+=1
            return {"url":"https://sandbox.square.link/u/offline-123",
                    "square_order_id":square_order,"square_link_id":"TEST_LINK_123"}
        def create(*,order_id,location_id,token,idempotency_key):
            self.assertEqual(order_id,square_order)
            self.assertEqual(location_id,ENV["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"])
            self.assertGreaterEqual(len(idempotency_key),20)
            calls["payment"]+=1
            return {"id":payment_id}
        def read(payment_id_arg,*,token):
            self.assertEqual(payment_id_arg,payment_id)
            self.assertEqual(token,ENV["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"])
            calls["read"]+=1
            return {"id":payment_id,"status":"COMPLETED","order_id":square_order,
                "location_id":ENV["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
                "amount_money":{"amount":21450,"currency":"JPY"}}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result=smoke.main(env=ENV,link_creator=link,
                payment_creator=create,payment_reader=read)
        self.assertEqual(result,0)
        self.assertEqual(calls["link"],1)
        self.assertEqual(calls["payment"],1)
        self.assertGreaterEqual(calls["read"],2)
        self.assertIn("SQUARE_CARD_SANDBOX_OK",out.getvalue())
        self.assertNotIn(ENV["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"],out.getvalue())
        self.assertNotIn(square_order,out.getvalue())

    def test_wrong_amount_does_not_mark_paid(self):
        square_order="TESTSQUAREORDER123456"
        def link(*a,**k):
            return {"url":"https://sandbox.square.link/u/test",
                    "square_order_id":square_order,"square_link_id":"TEST_LINK"}
        def create(**k):return {"id":"SQUAREPAYMENT12345"}
        def read(*a,**k):
            return {"id":"SQUAREPAYMENT12345","status":"COMPLETED",
                    "order_id":square_order,
                    "location_id":ENV["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
                    "amount_money":{"amount":1,"currency":"JPY"}}
        with contextlib.redirect_stdout(io.StringIO()) as out:
            result=smoke.main(env=ENV,link_creator=link,
                payment_creator=create,payment_reader=read)
        self.assertEqual(result,1)
        self.assertIn("FAILED",out.getvalue())

    def test_payment_request_is_sandbox_only_and_fixed_test_token(self):
        recorded=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):pass
            def read(self,limit):
                return json.dumps({"payment":{"id":"SANDBOXPAYMENT12345"}}).encode()
        def fake_opener(request,timeout):
            self.assertEqual(request.full_url,"https://connect.squareupsandbox.com/v2/payments")
            self.assertEqual(request.get_method(),"POST")
            body=json.loads(request.data)
            self.assertEqual(body["source_id"],"cnon:card-nonce-ok")
            self.assertEqual(body["amount_money"],{"amount":21450,"currency":"JPY"})
            self.assertEqual(body["order_id"],"TESTSQUAREORDER")
            self.assertEqual(body["location_id"],ENV["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"])
            self.assertNotIn("card_number",str(body))
            recorded.append(True)
            return Response()
        paid=smoke.create_fake_card_payment(
            order_id="TESTSQUAREORDER",location_id=ENV["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
            token=ENV["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"],
            idempotency_key="shop-test-unique-123",opener=fake_opener)
        self.assertEqual(paid["id"],"SANDBOXPAYMENT12345")
        self.assertEqual(len(recorded),1)


if __name__=="__main__":
    unittest.main()
