"""Synthetic-only tests for one-time Square Sandbox disabled subscription."""
import importlib.util,json,unittest
from pathlib import Path
from urllib.error import URLError
spec=importlib.util.spec_from_file_location(
    "registrar",Path("scripts/register-shop-square-disabled-sandbox-webhook.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
ENV={"GITHUB_ACTIONS":"true","GITHUB_REF":m.REF,
     "BIGPAW_SHOP_REGISTER_DISABLED_WEBHOOK":"1",
     "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE_SANDBOX_APP_TOKEN_LONG"}

class Response:
    def __init__(self,value,status=200):
        self.data=json.dumps(value).encode();self.status=status
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,n):return self.data[:n]

class Tests(unittest.TestCase):
    def test_create_only_when_absent_and_only_disabled(self):
        calls=[]
        def fake(req,timeout):
            calls.append((req.get_method(),req.full_url))
            self.assertTrue(req.full_url.startswith(m.API))
            self.assertEqual(timeout,12)
            if req.get_method()=="GET":
                return Response({"subscriptions":[
                    {"notification_url":"https://old-sandbox.example/path",
                     "enabled":True}]})
            payload=json.loads(req.data)
            self.assertEqual(payload["idempotency_key"],m.KEY)
            self.assertIs(payload["subscription"]["enabled"],False)
            self.assertEqual(payload["subscription"]["notification_url"],m.TARGET)
            self.assertEqual(set(payload["subscription"]["event_types"]),
                             {"payment.created","payment.updated"})
            return Response({"subscription":{**payload["subscription"],
                                             "signature_key":"MUST_NEVER_LOG",
                                             "id":"SECRET_ID"}},201)
        label,code=m.register_disabled(env=ENV,opener=fake)
        self.assertEqual((label,code),("new_target_created_disabled_no_delivery",0))
        self.assertEqual([x[0] for x in calls],["GET","POST"])
        self.assertNotIn("MUST_NEVER_LOG",label)
        self.assertNotIn("SECRET_ID",label)
    def test_skip_when_existing_disabled(self):
        actions=[]
        def fake(req,timeout):
            actions.append(req.get_method())
            return Response({"subscriptions":[{"notification_url":m.TARGET,"enabled":False}]})
        self.assertEqual(m.register_disabled(env=ENV,opener=fake),
                         ("new_target_already_registered_disabled",0))
        self.assertEqual(actions,["GET"])
    def test_never_mutate_existing_enabled_or_paginated(self):
        for value in ({"subscriptions":[{"notification_url":m.TARGET,"enabled":True}]},
                      {"subscriptions":[],"cursor":"anothervalidpage"}):
            methods=[]
            def fake(req,timeout):
                methods.append(req.get_method())
                return Response(value)
            self.assertEqual(m.register_disabled(env=ENV,opener=fake)[1],2)
            self.assertEqual(methods,["GET"])
    def test_no_post_retry_on_uncertain(self):
        count=[]
        def fake(req,timeout):
            count.append(req.get_method())
            if req.get_method()=="GET":return Response({"subscriptions":[]})
            raise URLError("SYNTHETIC_CONNECTION_RESET")
        self.assertEqual(m.register_disabled(env=ENV,opener=fake),
                         ("subscription_post_uncertain_no_retry_manual_get",2))
        self.assertEqual(count,["GET","POST"])
    def test_no_network_without_explicit_opt_in(self):
        def no(*args):self.fail("No Square call")
        self.assertEqual(m.register_disabled(env={},opener=no)[1],3)

if __name__=="__main__":unittest.main()
