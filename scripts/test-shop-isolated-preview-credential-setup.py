"""No-network tests for a one-time disabled isolated preview credential setup."""
import importlib.util
import json
from pathlib import Path
from urllib.error import URLError
import unittest

spec=importlib.util.spec_from_file_location(
    "setup",Path("scripts/setup-shop-isolated-preview-credentials-once.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
ENV={"GITHUB_ACTIONS":"true","GITHUB_REF":m.REF,
     "BIGPAW_SHOP_PREVIEW_CREDENTIAL_SETUP_OPT_IN":"1",
     "BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN":"FAKE_STAGING_TOKEN_NO_SECRET"}
class Response:
    status=200
    def __init__(self,data):self.data=json.dumps({"data":data}).encode()
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,size):return self.data[:size]
def provider(record,*,wrong_scope=False,already_enabled=False,preexisting=False,uncertain=False):
    def opener(req,timeout):
        assert req.full_url==m.RAILWAY
        assert req.get_header("User-agent")=="BIGPAW-SandboxPreviewSetup/1.0"
        obj=json.loads(req.data)
        query=obj["query"]
        record.append(query)
        if "projectToken" in query:
            return Response({"projectToken":{"projectId":"WRONG" if wrong_scope else m.PROJECT,
                                            "environmentId":m.ENV}})
        if query.startswith("query variables"):
            return Response({"variables":{"BIGPAW_ENV":"sandbox",
                "BIGPAW_SHOP_STAGE_PREVIEW_ENABLED":"1" if already_enabled else "0",
                **({"BIGPAW_SHOP_STAGE_PREVIEW_USER":"old_credential"} if preexisting else {})}})
        assert query.startswith("mutation")
        vars=obj["variables"]["input"]
        assert vars["projectId"]==m.PROJECT
        assert vars["environmentId"]==m.ENV
        assert vars["serviceId"]==m.TARGET
        assert vars["skipDeploys"] is True
        assert set(vars["variables"])=={
          "BIGPAW_SHOP_STAGE_PREVIEW_USER",
          "BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD",
          "BIGPAW_SHOP_STAGE_PREVIEW_ENABLED",
        }
        assert vars["variables"]["BIGPAW_SHOP_STAGE_PREVIEW_ENABLED"]=="0"
        assert len(vars["variables"]["BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD"])>=32
        if uncertain: raise URLError("Synthetic timeout")
        return Response({"variableCollectionUpsert":True})
    return opener

class Safety(unittest.TestCase):
    def test_opt_in_required_no_connect(self):
        self.assertEqual(m.run({},opener=lambda *_:self.fail("unexpected"))[1],3)
    def test_one_secret_write_exact_staging_scope_disabled(self):
        calls=[]
        result,code=m.run(ENV,opener=provider(calls))
        self.assertEqual((result,code),("credentials_configured_preview_disabled_no_deployment",0))
        self.assertEqual(len(calls),3)
    def test_preexisting_password_never_overwritten(self):
        calls=[]
        self.assertEqual(m.run(ENV,opener=provider(calls,preexisting=True))[1],2)
        self.assertEqual(len(calls),2)
    def test_already_enabled_never_overwritten(self):
        calls=[]
        self.assertEqual(m.run(ENV,opener=provider(calls,already_enabled=True))[1],2)
        self.assertEqual(len(calls),2)
    def test_wrong_token_scope_rejects_without_mutation(self):
        calls=[]
        self.assertEqual(m.run(ENV,opener=provider(calls,wrong_scope=True))[1],2)
        self.assertEqual(len(calls),1)
    def test_timeout_never_retries_secret_post(self):
        calls=[]
        result,code=m.run(ENV,opener=provider(calls,uncertain=True))
        self.assertEqual(code,2)
        self.assertEqual(len(calls),3)
        self.assertNotIn("FAKE_STAGING_TOKEN",result)

if __name__=="__main__":unittest.main()
