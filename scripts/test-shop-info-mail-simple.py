"""No-network safety checks for exactly one real info@bigpaw.site test email."""
import importlib.util
import io
import json
import contextlib
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location("probe",Path("scripts/smoke-shop-info-mail-simple.py"))
test=importlib.util.module_from_spec(spec);spec.loader.exec_module(test)
ENV={"GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/feature/dogfood-shop-staging-20261028",
     "BIGPAW_SINGLE_INFO_EMAIL_TEST":"1","RESEND_API_KEY":"re_FAKE_ONLY_NEVER_SECRET"}
class FakeResponse:
    status=200
    def __init__(self,obj):self.obj=obj
    def __enter__(self):return self
    def __exit__(self,*a):pass
    def read(self,n):return json.dumps(self.obj).encode()

class Tests(unittest.TestCase):
    def capture(self,**kwargs):
        o=io.StringIO()
        with contextlib.redirect_stdout(o):
            r=test.once(**kwargs)
        self.assertNotIn(ENV["RESEND_API_KEY"],o.getvalue())
        return r,o.getvalue()
    def test_refuses_without_single_use_opt_in_and_branch(self):
        calls=[]
        for env in ({},{**ENV,"GITHUB_REF":"refs/heads/main"},{**ENV,"BIGPAW_SINGLE_INFO_EMAIL_TEST":"0"}):
            self.assertEqual(self.capture(env=env,opener=lambda *a,**k:calls.append(a))[0],3)
        self.assertFalse(calls)
    def test_missing_or_malformed_key_never_contacts_provider(self):
        calls=[]
        for value in ("", "\\", "\\re_FAKE_ONLY_NEVER_SECRET", "NOT_A_RESEND_KEY", "re_has spaces"):
            status,_=self.capture(env={**ENV,"RESEND_API_KEY":value},opener=lambda *a,**k:calls.append(a))
            self.assertEqual(status,2)
        self.assertFalse(calls)
    def test_sends_only_one_real_mail_to_fixed_owner_not_customer(self):
        calls=[]
        def fake(req,timeout):
            self.assertEqual(req.full_url,"https://api.resend.com"+("/emails" if not calls else "/emails/mail-test-123456"))
            self.assertIn(req.get_method(),("POST","GET"))
            calls.append(req.get_method())
            if req.get_method()=="POST":
                data=json.loads(req.data)
                self.assertEqual(data["to"],["info@bigpaw.site"])
                self.assertEqual(data["from"],"BIG PAW <noreply@bigpaw.site>")
                self.assertIn("実注文ではありません",data["subject"])
                self.assertIn("発注は不要",data["text"])
                return FakeResponse({"id":"mail-test-123456"})
            return FakeResponse({"id":"mail-test-123456","to":["info@bigpaw.site"],"last_event":"delivered"})
        status,output=self.capture(env=ENV,opener=fake,delay=lambda s:None)
        self.assertEqual(status,0)
        self.assertEqual(calls,["POST","GET"])
        self.assertIn("DELIVERED",output)
        self.assertNotIn("mail-test-123456",output)
    def test_ambiguous_timeout_does_not_retry(self):
        calls=[]
        def broken(req,timeout):
            calls.append(req.get_method())
            raise TimeoutError("unknown")
        self.assertEqual(self.capture(env=ENV,opener=broken)[0],4)
        self.assertEqual(calls,["POST"])
    def test_accepted_but_unverified_never_resends(self):
        calls=[]
        def unavailable(req,timeout):
            calls.append(req.get_method())
            if req.get_method()=="POST":return FakeResponse({"id":"mail-test-123456"})
            return FakeResponse({"id":"mail-test-123456","to":["info@bigpaw.site"],"last_event":"sent"})
        status,output=self.capture(env=ENV,opener=unavailable,delay=lambda s:None)
        self.assertEqual(status,4)
        self.assertEqual(calls.count("POST"),1)
        self.assertIn("DELIVERY_UNVERIFIED",output)

if __name__=="__main__":unittest.main()
