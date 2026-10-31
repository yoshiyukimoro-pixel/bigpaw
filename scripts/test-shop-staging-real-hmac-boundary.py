"""Offline contract tests for the new isolated Square Sandbox HTTPS HMAC probe."""
import base64
import hashlib
import hmac
import importlib.util
import io
import json
from pathlib import Path
from urllib.error import HTTPError
import unittest

spec=importlib.util.spec_from_file_location(
    "boundary_probe",Path("scripts/check-shop-staging-real-hmac-boundary.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ENV = {"GITHUB_ACTIONS": "true", "GITHUB_REF": m.BRANCH,
       "BIGPAW_SANDBOX_HMAC_BOUNDARY_OPT_IN": "1",
       "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "FAKE_ACCESS_TOKEN_123456789"}
KEY = "FAKE_SUBSCRIPTION_SPECIFIC_SIGNING_KEY_123456789"
SID = "wbhk_FAKE_SANDBOX_TARGET_123456"
NONCE = "abcde12345abcde12345abcde12345ab"

class Response:
    def __init__(self,value):
        self.status=200
        self.raw=json.dumps(value).encode()
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,size):return self.raw[:size]

def provider(calls,*,old_enabled=True,new_disabled=True,incorrect_key=False):
    def perform(req,timeout):
        method=req.get_method()
        calls.append((method,req.full_url))
        if req.full_url.startswith(m.API):
            assert method=="GET", "Square API must never be written"
            assert req.get_header("Authorization")=="Bearer "+ENV["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]
            if req.full_url==m.API+"?include_disabled=true&limit=100":
                return Response({"subscriptions":[
                    {"id":"wbhk_FAKE_OLD_12345","notification_url":m.OLD,"enabled":old_enabled,
                     "event_types":["payment.updated"]},
                    {"id":SID,"notification_url":m.TARGET,"enabled":not new_disabled,
                     "event_types":["payment.updated"]}]})
            if req.full_url==m.API+"/"+SID:
                return Response({"subscription":{
                    "id":SID,"notification_url":m.TARGET,"enabled":False,
                    "event_types":["payment.updated"],
                    "signature_key":KEY}})
            raise AssertionError("Invalid Square API path")
        assert method=="POST" and req.full_url==m.TARGET, "No other outbound host"
        assert req.get_header("Content-type")=="application/json"
        assert b"SYNTHETIC_ORDER_" in req.data
        assert b'"amount":1' in req.data
        sig=req.get_header("X-square-hmacsha256-signature")
        expected=base64.b64encode(hmac.new(
            KEY.encode(),m.TARGET.encode()+req.data,hashlib.sha256).digest()).decode()
        if req.get_header("Square-environment") != "Sandbox":
            status,code=403,"invalid_environment"
        elif sig!=expected:
            status,code=403,"invalid_signature_or_event"
        else:
            status,code=503,"awaiting_square_confirmation"
        if incorrect_key and len(calls)==3:
            code="not_the_expected_code"
        raise HTTPError(req.full_url,status,"synthetic",None,
                        io.BytesIO(json.dumps({"status":code}).encode()))
    return perform

class HMACBoundaryTests(unittest.TestCase):
    def test_only_new_service_three_controlled_posts_and_square_gets(self):
        calls=[]
        result,code=m.verify(ENV,opener=provider(calls),nonce=NONCE)
        self.assertEqual((result,code),(
            "correct_signature_safe_rejection_and_invalid_signatures_blocked",0))
        self.assertEqual([x[0] for x in calls],["GET","GET","POST","POST","POST"])
        self.assertTrue(all(url==m.TARGET for method,url in calls if method=="POST"))
        self.assertNotIn(KEY,result)
        self.assertNotIn(NONCE,result)
    def test_missing_opt_in_never_networks(self):
        self.assertEqual(m.verify({},opener=lambda *_:self.fail("Unexpected network"))[1],3)
    def test_old_subscription_invariant_blocks_before_post(self):
        calls=[]
        result,code=m.verify(ENV,opener=provider(calls,old_enabled=False),nonce=NONCE)
        self.assertEqual(code,2)
        self.assertEqual([x[0] for x in calls],["GET"])
    def test_new_subscription_must_remain_disabled(self):
        calls=[]
        self.assertEqual(m.verify(ENV,opener=provider(calls,new_disabled=False),nonce=NONCE)[1],2)
        self.assertEqual([x[0] for x in calls],["GET"])
    def test_receiver_mismatch_stops_without_retry(self):
        calls=[]
        result,code=m.verify(ENV,opener=provider(calls,incorrect_key=True),nonce=NONCE)
        self.assertEqual(code,2)
        self.assertEqual(result,"rejected_boundary_correct_hmac_unknown_order_no_retry")
        self.assertEqual([x[0] for x in calls],["GET","GET","POST"])

if __name__=="__main__":
    unittest.main()
