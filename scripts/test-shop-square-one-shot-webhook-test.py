"""Offline safety checks for isolated Square-issued test event (no network)."""
import importlib.util
from pathlib import Path
import json
import unittest
from urllib.error import HTTPError

spec=importlib.util.spec_from_file_location(
    "shop_one_shot", Path("scripts/shop-square-one-shot-webhook-test.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ENV={"GITHUB_ACTIONS":"true", "GITHUB_REF":m.REF,
     "BIGPAW_SQUARE_ONE_SHOT_DISABLED_TEST_OPT_IN":"1",
     "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE_NO_REAL_ACCESS_TOKEN"}
SID="wbhk_TEST1234567890"

class Res:
    def __init__(self, body, status=200):
        self.status=status
        self.body=json.dumps(body).encode()
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self, size):return self.body[:size]

def fake_provider(calls, *, old_enabled=True, new_disabled=True,
                  detail_matches=True, test_code=503, throw_post=False):
    def reply(req,timeout):
        method=req.get_method()
        calls.append((method,req.full_url))
        assert req.full_url.startswith("https://connect.squareupsandbox.com/")
        assert req.get_header("User-agent")=="BIGPAW-Isolated-Square-Test/1.0"
        if method=="GET" and req.full_url.endswith("include_disabled=true&limit=100"):
            return Res({"subscriptions":[
                {"id":"wbhk_OLDTEST12345","notification_url":m.OLD,
                 "enabled":old_enabled,"event_types":["payment.updated"]},
                {"id":SID,"notification_url":m.NEW,
                 "enabled":not new_disabled,"event_types":["payment.updated"]}]})
        if method=="GET" and req.full_url==m.API+"/"+SID:
            return Res({"subscription":{"id":SID,"notification_url":m.NEW,
                       "enabled":False if detail_matches else True,
                       "event_types":["payment.updated"]}})
        if method=="POST" and req.full_url==m.API+"/"+SID+"/test":
            assert req.data==b'{"event_type":"payment.updated"}'
            if throw_post:raise HTTPError(req.full_url,400,"synthetic",None,None)
            return Res({"subscription_test_result":{"status_code":test_code,
                         "payload":"PRIVATE TEST EVENT MUST NOT PRINT"}})
        raise AssertionError("unexpected network operation")
    return reply

class Cases(unittest.TestCase):
    def test_one_test_post_exactly_once_and_only_target(self):
        requests=[]
        status,code=m.execute(ENV,opener=fake_provider(requests))
        self.assertEqual((status,code),("square_generated_test_delivered_receiver_http_503",0))
        self.assertEqual([x[0] for x in requests],["GET","GET","POST"])
        self.assertEqual(requests[-1][1],m.API+"/"+SID+"/test")
    def test_legacy_changed_blocks_before_write(self):
        calls=[]
        result,code=m.execute(ENV,opener=fake_provider(calls,old_enabled=False))
        self.assertEqual(code,2)
        self.assertTrue(result.endswith("no_post"))
        self.assertEqual(len(calls),1)
    def test_new_enabled_blocks_before_write(self):
        calls=[]
        self.assertEqual(m.execute(ENV,opener=fake_provider(calls,new_disabled=False))[1],2)
        self.assertEqual(len(calls),1)
    def test_subscription_detail_changed_blocks_before_write(self):
        calls=[]
        self.assertEqual(m.execute(ENV,opener=fake_provider(calls,detail_matches=False))[1],2)
        self.assertEqual([x[0] for x in calls],["GET","GET"])
    def test_no_opt_in_never_connects(self):
        self.assertEqual(m.execute({},opener=lambda *_:self.fail("Unexpected network"))[1],3)
    def test_square_api_refusal_no_retry_or_sensitive_response(self):
        calls=[]
        state,code=m.execute(ENV,opener=fake_provider(calls,throw_post=True))
        self.assertEqual((state,code),("square_test_api_rejected_http_400",2))
        self.assertEqual(len(calls),3)
        self.assertNotIn("PRIVATE",state)
    def test_square_returns_receiver_403_without_falsely_claiming_success(self):
        calls=[]
        state,code=m.execute(ENV,opener=fake_provider(calls,test_code=403))
        self.assertEqual((state,code),("square_generated_test_delivered_receiver_http_403",0))
        self.assertEqual(len(calls),3)

if __name__=="__main__":
    unittest.main()
