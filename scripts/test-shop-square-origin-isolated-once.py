"""Offline safety tests: only NEW disabled Square Sandbox subscriber toggled.

No provider calls, no funds, no mail; fakes strictly reject any write to
the old active subscription or to Square Production.
"""
import importlib.util
import io
import json
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
import unittest

spec=importlib.util.spec_from_file_location(
    "square_origin",Path("scripts/run-shop-new-sandbox-square-origin-e2e.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

TOKEN="FAKE_SQUARE_TOKEN"
SID="wbhk_FAKE_NEW_SUBSCRIPTION"
OLDID="wbhk_FAKE_OLD_SUBSCRIPTION"
NEW={ "id":SID,"notification_url":m.NEW,"enabled":False,
      "event_types":["payment.updated"]}
OLD={ "id":OLDID,"notification_url":m.OLD,"enabled":True,
      "event_types":["payment.updated"]}
ENV={"GITHUB_ACTIONS":"true","GITHUB_REF":m.REF,
     "BIGPAW_SQUARE_ORIGIN_NEW_STAGING_ONESHOT_OPT_IN":"1",
     "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":TOKEN+"_"*4}

class FakeResponse:
    status=200
    def __init__(self,data):self.body=json.dumps(data).encode()
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,size):return self.body[:size]

class Cases(unittest.TestCase):
    def test_no_unapproved_scope(self):
        with patch.dict(m.os.environ,{},clear=True):
            with self.assertRaises(ValueError):m._allowed()
    def test_enable_changes_only_new_subscriber_once(self):
        calls=[]
        with patch.dict(m.os.environ,ENV),patch.object(m.base,"_scope",return_value={}),patch.object(m,"_subs",side_effect=[
            (SID,dict(NEW)),(SID,{**NEW,"enabled":True})]),patch.object(m,"_update",side_effect=lambda t,s,e:calls.append((t,s,e))):
            m.turn_on()
        self.assertEqual(calls,[(ENV["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"],SID,True)])
    def test_cleanup_disables_new_even_if_existing_old_unexpected(self):
        calls=[]
        with patch.dict(m.os.environ,ENV),patch.object(m,"_subs",side_effect=[
            (SID,{**NEW,"enabled":True}), (SID,{**NEW,"enabled":False})]) as read,patch.object(m,"_update",side_effect=lambda t,s,e:calls.append((s,e))):
            m.turn_off()
        self.assertEqual(calls,[(SID,False)])
        self.assertTrue(all(x.kwargs.get("strict_old") is False for x in read.call_args_list))
    def test_cleanup_idempotent_already_disabled(self):
        with patch.dict(m.os.environ,ENV),patch.object(m,"_subs",return_value=(SID,dict(NEW))),patch.object(m,"_update") as update:
            m.turn_off()
            update.assert_not_called()
    def test_exact_isolated_subscription_and_legacy_read_only(self):
        args=[]
        def square(url,token):
            args.append(url)
            self.assertTrue(url.startswith("https://connect.squareupsandbox.com/v2/"))
            return {"subscriptions":[dict(OLD),dict(NEW)]}
        with patch.object(m.base,"_square_get",side_effect=square):
            result=m._subs(TOKEN)
        self.assertEqual(result[0],SID)
        self.assertEqual(len(args),1)
        self.assertIn("include_disabled=true",args[0])
        with patch.object(m.base,"_square_get",return_value={"subscriptions":[
            {**OLD,"enabled":False},dict(NEW)]}):
            with self.assertRaises(ValueError):m._subs(TOKEN)
            self.assertEqual(m._subs(TOKEN,strict_old=False)[0],SID)
    def test_put_request_never_writes_legacy_or_production(self):
        requests=[]
        def opener(req,timeout):
            requests.append((req.full_url,req.get_method(),json.loads(req.data)))
            self.assertEqual(req.full_url,m.API+"/"+SID)
            self.assertEqual(req.get_method(),"PUT")
            self.assertEqual(json.loads(req.data),{"subscription":{"enabled":True}})
            self.assertTrue(req.get_header("Authorization").startswith("Bearer "))
            return FakeResponse({"subscription":{**NEW,"enabled":True}})
        with patch.object(m,"urlopen",side_effect=opener):
            m._update(TOKEN,SID,True)
        self.assertEqual(len(requests),1)
        self.assertNotIn(OLDID,str(requests))
    def test_bad_provider_response_fails_without_second_put(self):
        requests=[]
        def opener(req,timeout):
            requests.append(req.full_url)
            return FakeResponse({"subscription":{**OLD,"enabled":True}})
        with patch.object(m,"urlopen",side_effect=opener):
            with self.assertRaises(ValueError):m._update(TOKEN,SID,True)
        self.assertEqual(len(requests),1)

if __name__=="__main__":unittest.main()
