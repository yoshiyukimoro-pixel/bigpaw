"""All Square webhook subscriptions examples below are fake."""
import importlib.util, json, unittest
from pathlib import Path
from io import BytesIO
from urllib.error import HTTPError
spec=importlib.util.spec_from_file_location("audit",Path("scripts/audit-shop-square-subscriptions-readonly.py"))
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)
ENV={"GITHUB_ACTIONS":"true","GITHUB_REF":audit.REF,
     "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE_SANDBOX_TOKEN_LONG_ENOUGH"}

class Response:
    status=200
    def __init__(self,obj):self.body=json.dumps(obj).encode()
    def __enter__(self):return self
    def __exit__(self,*_):return False
    def read(self,n):return self.body[:n]

class Tests(unittest.TestCase):
    def test_subscription_list_get_only_and_no_private_endpoints_logged(self):
        requests=[]
        def fake(req,timeout):
            requests.append((req.get_method(),req.full_url,timeout))
            return Response({"subscriptions":[
                {"id":"HIDDEN_OLD","notification_url":audit.LEGACY,"enabled":True,
                 "event_types":["payment.updated"]},
                {"id":"HIDDEN_NEW","notification_url":audit.NEW,"enabled":False,
                 "event_types":["payment.updated"]},
                {"id":"PRIVATE","notification_url":"https://private.example/secret",
                 "enabled":True,"event_types":["payment.updated"]},
            ]})
        status,code=audit.audit(ENV,opener=fake)
        self.assertEqual(code,0)
        self.assertEqual(status,"old_enabled_payment_updated__new_disabled_payment_updated__read_only")
        self.assertEqual(len(requests),1)
        self.assertEqual(requests[0][0],"GET")
        self.assertTrue(requests[0][1].startswith(audit.API+"?"))
        self.assertEqual(requests[0][2],12)
        for x in ("HIDDEN_","PRIVATE","private.example","FAKE_SANDBOX_TOKEN"):
            self.assertNotIn(x,status)
    def test_no_matches_is_not_claimed_ready(self):
        self.assertEqual(audit.audit(ENV,opener=lambda req,timeout:Response({"subscriptions":[]})),
                         ("old_none__new_none__read_only",0))
    def test_provider_denied_is_unverified(self):
        def denied(req,timeout):
            raise HTTPError(req.full_url,403,"Denied",{},BytesIO(b'{}'))
        self.assertEqual(audit.audit(ENV,opener=denied),
                         ("provider_token_lacks_subscription_permission",2))
    def test_without_correct_branch_no_request(self):
        def bad(*args):self.fail("must not make a request")
        self.assertEqual(audit.audit({},opener=bad),("wrong_execution_scope",3))

if __name__=="__main__":unittest.main()
