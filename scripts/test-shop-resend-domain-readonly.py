"""Resend domain read-only audit regression: all responses synthetic."""
import importlib.util
import json
from pathlib import Path
import unittest

p = Path(__file__).with_name("audit-shop-resend-domain-readonly.py")
spec = importlib.util.spec_from_file_location("resend_domain", p)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
ENV = {"GITHUB_ACTIONS": "true", "GITHUB_REF": mod.REF,
       "RESEND_API_KEY": "re_synthetic_key_not_real_123456"}


class Response:
    status = 200
    def __init__(self, obj):
        self.data = json.dumps(obj).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, size): return self.data[:size]


class ReadOnlyDomainTests(unittest.TestCase):
    def opener(self, body, calls):
        def fetch(req, timeout):
            calls.append((req.get_method(), req.full_url, timeout,
                          req.headers.get("User-agent")))
            return Response(body)
        return fetch

    def test_verified_sending_and_get_only(self):
        calls = []
        value, code = mod.audit(ENV, self.opener({"data": [
            {"id": "SECRET_DOMAIN_ID", "name": "bigpaw.site",
             "status": "verified", "capabilities": {"sending": "enabled"}},
            {"name": "other.example", "status": "verified"},
        ]}, calls))
        self.assertEqual((value, code),
                         ("domain_verified_sending_enabled_read_only", 0))
        self.assertEqual(calls, [("GET", mod.ENDPOINT, 12,
                                  "BIGPAW-Sender-Domain-ReadOnly/1.0")])
        self.assertNotIn("SECRET_DOMAIN_ID", value)

    def test_pending_if_unverified_or_scope_unknown(self):
        for candidate in (
            {"name":"bigpaw.site", "status":"pending",
             "capabilities":{"sending":"enabled"}},
            {"name":"bigpaw.site", "status":"verified"},
            {"name":"bigpaw.site", "status":"verified",
             "capabilities":{"sending":"disabled"}},
        ):
            with self.subTest(candidate=candidate):
                result, code=mod.audit(ENV,self.opener({"data":[candidate]}, []))
                self.assertEqual(code,2)
                self.assertNotIn("enabled_read_only",result)

    def test_rejects_non_ci_no_network(self):
        result, code=mod.audit({"RESEND_API_KEY":"re_test"},
            opener=lambda *_:self.fail("must never contact provider"))
        self.assertEqual((result,code),("blocked_wrong_environment",3))


if __name__ == "__main__":
    unittest.main()
