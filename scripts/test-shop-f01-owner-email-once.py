"""Offline only: prove single internal Resend send cannot leak or retry."""
import importlib.util
from pathlib import Path
import io
import json
from urllib.error import HTTPError, URLError
import unittest

spec=importlib.util.spec_from_file_location(
    "f01",Path("scripts/check-shop-f01-owner-email-once.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ENV={
    "GITHUB_ACTIONS":"true","GITHUB_REF":m.REF,"GITHUB_RUN_ATTEMPT":"1",
    "BIGPAW_ONE_SHOP_SENDER_TEST_OPT_IN":"1",
    "RESEND_API_KEY":"re_FAKE_TEST_ONLY_123456",
}
class Response:
    status=201
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,n):return b'{"id":"synthetic12345678"}'

class Cases(unittest.TestCase):
    def test_no_approval_no_network(self):
        self.assertEqual(m.once({},opener=lambda *_:self.fail("unexpected network"))[1],3)
    def test_rerun_never_sends(self):
        self.assertEqual(m.once({**ENV,"GITHUB_RUN_ATTEMPT":"2"},opener=lambda *_:self.fail("unexpected network"))[1],3)
    def test_one_internal_email_only_to_owner(self):
        calls=[]
        def opener(req,timeout):
            calls.append((req.get_method(),req.full_url))
            assert req.get_method()=="POST"
            assert req.full_url=="https://api.resend.com/emails"
            d=json.loads(req.data)
            assert d["from"]==m.FROM
            assert d["to"]==[m.TO]
            assert "実注文ではありません" in d["subject"]
            assert req.get_header("Idempotency-key")==m.KEY
            return Response()
        result,code=m.once(ENV,opener=opener)
        self.assertEqual((result,code),("RESEND_ACCEPTED_ONE_INTERNAL_TEST_DELIVERY_UNCONFIRMED",0))
        self.assertEqual(len(calls),1)
    def test_permission_denial_no_retry(self):
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            raise HTTPError(req.full_url,403,"fake",None,io.BytesIO(b"PRIVATE"))
        self.assertEqual(m.once(ENV,opener=opener)[1],2)
        self.assertEqual(len(calls),1)
    def test_network_uncertainty_no_retry(self):
        calls=[]
        def opener(req,timeout):
            calls.append(req.full_url)
            raise URLError("synthetic timeout")
        result,code=m.once(ENV,opener=opener)
        self.assertEqual((result,code),("RESEND_NETWORK_RESULT_UNKNOWN_DO_NOT_RETRY",2))
        self.assertEqual(len(calls),1)

if __name__=="__main__":
    unittest.main()
