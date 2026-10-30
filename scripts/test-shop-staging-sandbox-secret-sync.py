"""Offline checks only: no real Square or Railway credentials or requests."""
import importlib.util
import json
from pathlib import Path
from urllib.error import URLError
import unittest

spec=importlib.util.spec_from_file_location(
    "staging_sync",Path("scripts/sync-shop-staging-sandbox-secrets.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ENV={
    "GITHUB_ACTIONS":"true","GITHUB_REF":m.REF,
    "BIGPAW_SHOP_STAGING_SECRET_SYNC_OPT_IN":"1",
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE_SQUARE_TOKEN_LONG_ONLY",
    "BIGPAW_SQUARE_SANDBOX_LOCATION_ID":"FAKELOCATION12345",
    "BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN":"FAKE_RAILWAY_PROJECT_TOKEN_LONG",
}
SID="wbhk_FAKE_SUBSCRIPTION_12345"
KEY="FAKE_SIGNING_KEY_FOR_OFFLINE_TEST_12345"

class Response:
    status=200
    def __init__(self,value):self.raw=json.dumps(value).encode()
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,size):return self.raw[:size]

def provider(*,calls,wrong_scope=False,enabled=False,fail_write=False):
    def reply(request,timeout):
        payload=json.loads(request.data) if request.data else None
        calls.append((request.get_method(),request.full_url))
        if request.full_url==m.RAILWAY and "projectToken" in (payload or {}).get("query",""):
            return Response({"data":{"projectToken":{
                "projectId":"WRONG_PROJECT" if wrong_scope else m.PROJECT,
                "environmentId":m.ENVIRONMENT}}})
        if request.full_url==m.SQUARE+"?include_disabled=true&limit=100":
            return Response({"subscriptions":[{
                "id":SID,"notification_url":m.WEBHOOK,"enabled":enabled}]})
        if request.full_url==m.SQUARE+"/"+SID:
            return Response({"subscription":{
                "id":SID,"notification_url":m.WEBHOOK,"enabled":enabled,
                "event_types":["payment.updated"],"signature_key":KEY}})
        if request.full_url==m.RAILWAY:
            if fail_write:raise URLError("synthetic connection reset")
            inp=payload["variables"]["input"]
            assert inp["projectId"]==m.PROJECT
            assert inp["environmentId"]==m.ENVIRONMENT
            assert inp["serviceId"]==m.SERVICE
            assert inp["skipDeploys"] is True
            assert set(inp["variables"])=={
                "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN",
                "BIGPAW_SQUARE_SANDBOX_LOCATION_ID",
                "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY",
            }
            assert inp["variables"]["BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY"]==KEY
            return Response({"data":{"variableCollectionUpsert":True}})
        raise AssertionError("unexpected URL")
    return reply

class Tests(unittest.TestCase):
    def test_exact_isolated_target_only_and_no_deploy(self):
        calls=[]
        value,code=m.sync(ENV,opener=provider(calls=calls))
        self.assertEqual(code,0)
        self.assertEqual([x[0] for x in calls],["POST","GET","GET","POST"])
        for sensitive in (SID,KEY,"FAKE_SQUARE_TOKEN","FAKE_RAILWAY_PROJECT"):
            self.assertNotIn(sensitive,value)
    def test_wrong_project_token_no_square_read_or_railway_write(self):
        calls=[]
        self.assertEqual(m.sync(ENV,opener=provider(calls=calls,wrong_scope=True))[1],2)
        self.assertEqual(len(calls),1)
    def test_enabled_target_never_writes_railway(self):
        calls=[]
        self.assertEqual(m.sync(ENV,opener=provider(calls=calls,enabled=True))[1],2)
        self.assertEqual([x[0] for x in calls],["POST","GET"])
    def test_uncertain_mutation_never_retries(self):
        calls=[]
        self.assertEqual(m.sync(ENV,opener=provider(calls=calls,fail_write=True))[1],2)
        self.assertEqual(len(calls),4)
    def test_no_optin_no_network(self):
        self.assertEqual(m.sync({},opener=lambda *_:self.fail("network"))[1],3)

if __name__=="__main__":
    unittest.main()
