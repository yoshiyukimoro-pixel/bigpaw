"""Offline read-only Resend diagnosis regression: never send email."""
import importlib.util
import io
import json
from pathlib import Path
import unittest

spec=importlib.util.spec_from_file_location(
    "audit_owner",Path("scripts/audit-shop-operator-resend-attempt.py"))
audit=importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeResponse:
    status=200
    def __init__(self,payload):
        self.body=json.dumps(payload).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return None
    def read(self,n):return self.body


class AuditTests(unittest.TestCase):
    def test_only_gets_resend_no_send_or_public_data(self):
        requests=[]
        def opener(req,timeout):
            requests.append((req.full_url,req.get_method()))
            self.assertEqual(req.get_method(),"GET")
            self.assertTrue(req.full_url.startswith("https://api.resend.com/"))
            if "/emails?" in req.full_url:
                return FakeResponse({"data":[
                    {"id":"a","to":["info@bigpaw.site"],
                     "from":audit.FROM,"subject":audit.SUBJECT,
                     "created_at":"2026-10-29T22:59:20+00:00","last_event":"delivered"},
                    {"id":"b","to":["somebody@example.com"],
                     "from":audit.FROM,"subject":audit.SUBJECT,
                     "created_at":"2026-10-29T22:59:20+00:00","last_event":"delivered"},
                ],"has_more":False})
            return FakeResponse({"data":[]})
        got=audit.search_provider_records("FAKE",opener=opener)
        self.assertEqual(got,{"result":"provider_message_found","event":"delivered"})
        self.assertEqual(requests,[("https://api.resend.com/emails","GET")])

    def test_missing_mail_does_not_claim_delivery(self):
        def opener(req,timeout):
            return FakeResponse({"data":[],"has_more":True})
        got=audit.search_provider_records("FAKE",opener=opener)
        self.assertEqual(got["result"],"not_found_in_first_100")
        self.assertTrue(got["has_more"])

    def test_duplicate_candidate_does_not_claim_delivery(self):
        item={"to":[audit.TARGET],"from":audit.FROM,"subject":audit.SUBJECT,
              "created_at":"2026-10-29T22:59:20+00:00","last_event":"delivered"}
        def opener(req,timeout):
            return FakeResponse({"data":[item,item],"has_more":False})
        got=audit.search_provider_records("FAKE",opener=opener)
        self.assertEqual(got["result"],"ambiguous_multiple_matches")

    def test_invalid_branch_blocks_provider_request(self):
        def opener(req,timeout):self.fail("unexpected network request")
        import contextlib
        output=io.StringIO()
        with contextlib.redirect_stdout(output):
            result=audit.main(env={"GITHUB_ACTIONS":"true","GITHUB_REF":"refs/heads/main",
                                   "RESEND_API_KEY":"FAKE"},opener=opener)
        self.assertEqual(result,3)
        self.assertIn("BLOCKED",output.getvalue())

    def test_logs_print_only_status_codes(self):
        def opener(req,timeout):
            return FakeResponse({"data":[
                {"method":"POST","path":"/emails","status_code":403,
                 "created_at":"2026-10-29T22:59:23Z","headers":{"Authorization":"SENSITIVE"}},
                {"method":"POST","path":"/inboxes","status_code":200,
                 "created_at":"2026-10-29T22:59:23Z"},
            ]})
        got=audit.search_api_log_status("FAKE",opener=opener)
        self.assertEqual(got["status_codes"],[403])
        self.assertNotIn("SENSITIVE",json.dumps(got))


if __name__=="__main__":
    unittest.main()
