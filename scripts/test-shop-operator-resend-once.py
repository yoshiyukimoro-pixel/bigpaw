"""Offline preflight for opt-in Resend mail probe, never send real messages."""
import importlib.util
import io
import contextlib
from pathlib import Path
import unittest
from unittest.mock import patch

spec=importlib.util.spec_from_file_location(
    "owner_mail_probe",Path("scripts/smoke-shop-operator-resend-once.py"))
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)
ENV={
    "GITHUB_ACTIONS":"true",
    "GITHUB_REF":"refs/heads/feature/dogfood-shop-staging-20261028",
    "BIGPAW_FOOD_MAIL_ONE_TIME":"1",
    "RESEND_API_KEY":"FAKE_SECRET_ONLY_NEVER_REAL",
}


class OwnerMailProbeTests(unittest.TestCase):
    def capture(self,**kwargs):
        log=io.StringIO()
        with contextlib.redirect_stdout(log):
            result=probe.run(**kwargs)
        self.assertNotIn(ENV["RESEND_API_KEY"],log.getvalue())
        return result,log.getvalue()

    def test_refuses_unapproved_network_send(self):
        calls=[]
        def sender(**k):calls.append(k);return "mock-provider-email-12345"
        for conf, env in [
            (False,ENV),
            (True,{**ENV,"GITHUB_REF":"refs/heads/main"}),
            (True,{**ENV,"GITHUB_ACTIONS":"false"}),
            (True,{**ENV,"BIGPAW_FOOD_MAIL_ONE_TIME":"0"}),
        ]:
            rc,_=self.capture(env=env,confirm=conf,sender=sender)
            self.assertEqual(rc,3)
        self.assertEqual(calls,[])

    def test_no_secret_refuses_to_send(self):
        calls=[]
        rc,txt=self.capture(env={**ENV,"RESEND_API_KEY":""},confirm=True,
            sender=lambda **kw:calls.append(kw))
        self.assertEqual(rc,2)
        self.assertIn("NOT_CONFIGURED",txt)
        self.assertEqual(calls,[])

    def test_sole_owner_address_test_only_body_and_delivery(self):
        calls=[]
        def sender(**k):
            calls.append(k)
            self.assertEqual(k["to"],"info@bigpaw.site")
            self.assertEqual(k["api_key"],ENV["RESEND_API_KEY"])
            self.assertIn("Sandbox",k["subject"])
            self.assertIn("実際のお客様からの注文・入金ではありません",k["body"])
            self.assertIn("トランペッツへ発注しないでください",k["body"])
            return "mock-provider-email-12345"
        checks=[]
        def reader(**kwargs):
            checks.append(kwargs)
            return "delivered" if len(checks)>1 else "sent"
        rc,txt=self.capture(env=ENV,confirm=True,sender=sender,
            reader=reader,sleep=lambda t:None)
        self.assertEqual(rc,0)
        self.assertEqual(len(calls),1)
        self.assertEqual(len(checks),2)
        self.assertIn("DELIVERED",txt)
        self.assertNotIn("mock-provider-email",txt)
        self.assertNotIn("SANDBOXONLY",txt)

    def test_failure_to_deliver_never_double_sends(self):
        calls=[]
        def sender(**kw):calls.append(kw);return "mock-provider-email-12345"
        rc,txt=self.capture(env=ENV,confirm=True,sender=sender,
            reader=lambda **k:"bounced",sleep=lambda _:None)
        self.assertEqual(rc,4)
        self.assertEqual(len(calls),1)
        self.assertIn("NOT_VERIFIED event=bounced",txt)

    def test_ambiguous_send_failure_no_retry(self):
        calls=[]
        def sender(**kw):calls.append(kw);raise TimeoutError("uncertain")
        rc,txt=self.capture(env=ENV,confirm=True,sender=sender,
            reader=lambda **k:self.fail("should not try delivery check"),
            sleep=lambda _:None)
        self.assertEqual(rc,1)
        self.assertEqual(len(calls),1)
        self.assertIn("ACCEPTANCE_UNCONFIRMED",txt)


if __name__=="__main__":
    unittest.main()
