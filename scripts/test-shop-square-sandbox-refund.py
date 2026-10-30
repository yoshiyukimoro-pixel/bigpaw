"""Offline, mocked fake refund safety checks (never connect Square)."""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

spec=importlib.util.spec_from_file_location(
    "refundprobe",Path("scripts/smoke-shop-square-sandbox-refund.py"))
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


class RefundTests(unittest.TestCase):
    def test_request_stays_in_sandbox_and_is_full_jpy(self):
        data=mod.build_refund_request("PAYMENT123456789", "FOOD" + "0"*32)
        self.assertEqual(data["amount_money"],
                         {"amount": 21450, "currency": "JPY"})
        self.assertLessEqual(len(data["idempotency_key"]), 45)
        self.assertEqual(mod.BASE,"https://connect.squareupsandbox.com/v2")
        self.assertNotIn("connect.squareup.com", Path(
            "scripts/smoke-shop-square-sandbox-refund.py").read_text())

    def test_needs_explicit_isolated_runner(self):
        self.assertFalse(mod.safe_env({}))
        self.assertFalse(mod.safe_env({
            "GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
            "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"EAAAFAKE",
            "BIGPAW_SQUARE_SANDBOX_LOCATION_ID":"LOCATION",
            "RUNNER_TEMP":"/tmp"}))

    def test_rejects_wrong_payment_amount_or_status(self):
        p="PAYMENT123456789";o="ORDER123456789";loc="LOCATION12345"
        correct={"refund":{"id":"REFUND123456789",
                            "payment_id":p,"order_id":o,
                            "location_id":loc,
                            "status":"PENDING",
                            "amount_money":{"amount":21450,"currency":"JPY"}}}
        self.assertEqual(mod.verify_refund(correct,p,o,loc),"PENDING")
        # A refund can omit optional order/location in its first API response.
        # The original Square Order and Payment were independently checked
        # *before* the one allowed refund POST.
        reduced = {**correct, "refund": {k: v for k, v in correct["refund"].items()
                                      if k not in ("order_id", "location_id")}}
        self.assertEqual(mod.verify_refund(reduced,p,o,loc),"PENDING")
        for key,wrong in (("order_id","UNRELATED"),
                          ("location_id","UNRELATED")):
            poisoned={**reduced,"refund":{**reduced["refund"],key:wrong}}
            with self.assertRaises(ValueError):
                mod.verify_refund(poisoned,p,o,loc)

        for bad in (
            {**correct,"refund":{**correct["refund"],"status":"FAILED"}},
            {**correct,"refund":{**correct["refund"],"payment_id":"OTHER"}},
            {**correct,"refund":{**correct["refund"],"amount_money":
                {"amount":21451,"currency":"JPY"}}},
        ):
            with self.assertRaises(ValueError):
                mod.verify_refund(bad,p,o,loc)

    def test_post_is_implicit_single_api_call(self):
        reqs=[]
        class Response:
            status=200
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return json.dumps({"refund":{
                "id":"REFUND123456789"}}).encode()
        def opener(req,timeout):
            reqs.append((req.full_url,req.get_method(),timeout))
            return Response()
        value=mod._post_refund({"idempotency_key":"FAKE"},
                               "EAAAFAKE",opener=opener)
        self.assertEqual(reqs,[(mod.BASE+"/refunds","POST",12)])
        self.assertEqual(value["refund"]["id"],"REFUND123456789")


if __name__=="__main__":
    unittest.main()
