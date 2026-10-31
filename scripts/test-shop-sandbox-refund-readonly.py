"""No network, no POST: GET-only audit for a prior uncertain refund."""
from pathlib import Path
import importlib.util
import json
import unittest

spec=importlib.util.spec_from_file_location("aud",
    Path("scripts/audit-shop-sandbox-refund-readonly.py"))
mod=importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ENV={"GITHUB_ACTIONS":"true","GITHUB_REF":mod.REF,
     "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE",
     "BIGPAW_SQUARE_SANDBOX_LOCATION_ID":"LOC-TEST"}


class FakeResp:
    status=200
    def __init__(self,body):self.body=json.dumps(body).encode()
    def __enter__(self):return self
    def __exit__(self,*args):pass
    def read(self,n):return self.body[:n]


class ReadOnlyRefundAuditTests(unittest.TestCase):
    def test_one_matching_completed_refund_and_get_only(self):
        calls=[]
        def op(req,timeout):
            calls.append((req.get_method(),req.full_url,timeout))
            return FakeResp({"refunds":[
                {"reason":mod.REASON,"location_id":"LOC-TEST",
                 "amount_money":{"amount":21450,"currency":"JPY"},
                 "status":"COMPLETED","id":"PRIVATE_ID"},
                {"reason":"other","location_id":"LOC-TEST",
                 "amount_money":{"amount":21450,"currency":"JPY"},
                 "status":"COMPLETED"}]})
        result,code=mod.audit(env=ENV,opener=op)
        self.assertEqual((result,code),("one_matching_refund_completed",0))
        self.assertEqual(len(calls),1)
        self.assertEqual(calls[0][0],"GET")
        self.assertTrue(calls[0][1].startswith(mod.BASE+"?"))
        self.assertNotIn("PRIVATE_ID",result)

    def test_none_is_unverified(self):
        result,code=mod.audit(env=ENV,opener=lambda req, timeout:FakeResp({}))
        self.assertEqual(code,1)
        self.assertIn("no_matching",result)

    def test_wrong_branch_blocks_external_access(self):
        result,code=mod.audit(
            env={**ENV,"GITHUB_REF":"refs/heads/main"},
            opener=lambda *_:self.fail("no external calls"))
        self.assertEqual(code,3)


if __name__=="__main__":
    unittest.main()
