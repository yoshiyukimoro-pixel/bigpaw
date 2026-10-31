"""Offline checks for standalone Square Sandbox fake-card verification."""
import importlib.util
import io
import contextlib
from pathlib import Path
import unittest
from shop_payments.sandbox_connector import SquareSandboxError

spec=importlib.util.spec_from_file_location(
    "standalone",Path("scripts/smoke-shop-square-standalone-payment.py"))
smoke=importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
ENV={"BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"fake-sandbox-secret-only",
     "BIGPAW_SQUARE_SANDBOX_LOCATION_ID":"TESTLOCATION1234"}

class TestStandalone(unittest.TestCase):
    def test_missing_credentials_makes_no_request(self):
        def forbidden(**k):self.fail("network must not happen")
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(smoke.main(env={},payment_creator=forbidden),2)

    def test_successful_sandbox_payment_requires_fresh_api_confirmation(self):
        calls=[]
        def create(**kwargs):
            self.assertIsNone(kwargs["order_id"])
            self.assertLessEqual(len(kwargs["idempotency_key"]),45)
            self.assertEqual(kwargs["location_id"],ENV["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"])
            calls.append("create")
            return {"id":"SQUARETESTPAYMENT123456"}
        def read(identifier,*,token):
            self.assertEqual(identifier,"SQUARETESTPAYMENT123456")
            calls.append("read")
            return {"id":identifier,"location_id":ENV["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
                    "status":"COMPLETED","amount_money":{"amount":21450,"currency":"JPY"}}
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            rc=smoke.main(env=ENV,payment_creator=create,payment_reader=read)
        self.assertEqual(rc,0)
        self.assertEqual(calls,["create","read"])
        self.assertIn("SQUARE_STANDALONE_SANDBOX_OK",out.getvalue())
        self.assertNotIn(ENV["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"],out.getvalue())
        self.assertNotIn("SQUARETESTPAYMENT123456",out.getvalue())

    def test_does_not_mark_paid_without_confirmed_payment(self):
        def create(**k):return {"id":"PAYMENTFAKE12345"}
        def pending(pid,*,token):
            return {"id":pid,"status":"PENDING","location_id":ENV["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
                    "amount_money":{"amount":21450,"currency":"JPY"}}
        out=io.StringIO()
        with contextlib.redirect_stdout(out):
            rc=smoke.main(env=ENV,payment_creator=create,payment_reader=pending)
        self.assertEqual(rc,1)
        self.assertIn("FAILED",out.getvalue())

    def test_api_connection_failure(self):
        def error(**k):raise SquareSandboxError("test")
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(smoke.main(env=ENV,payment_creator=error),1)
        self.assertNotIn("fake-sandbox-secret-only",out.getvalue())

if __name__=="__main__":
    unittest.main()
