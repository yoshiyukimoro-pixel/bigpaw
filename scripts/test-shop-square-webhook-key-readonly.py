"""Square Sandbox webhook key preflight uses only synthetic provider responses."""
import importlib.util
import json
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "square_key", Path("scripts/audit-shop-square-webhook-key-readonly.py"))
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

ENV = {
    "GITHUB_ACTIONS": "true", "GITHUB_REF": m.REF,
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "FAKE_TOKEN_FOR_TESTS_ONLY_123456",
}
ID = "wbhk_SYNTHETIC_TEST_12345"
KEY = "synthetic_signing_key_for_test_only_123456"

class Response:
    status = 200
    def __init__(self, value):
        self.raw = json.dumps(value).encode()
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, limit): return self.raw[:limit]

def responses(*, enabled=False, key=KEY, detail_url=m.TARGET, duplicate=False):
    def get(request, timeout):
        assert request.get_method() == "GET"
        assert request.full_url.startswith(m.API)
        if request.full_url.endswith("limit=100"):
            rows = [{"id": ID, "notification_url": m.TARGET,
                     "enabled": enabled}]
            if duplicate:
                rows.append(dict(rows[0]))
            return Response({"subscriptions": rows})
        if request.full_url == m.API + "/" + ID:
            return Response({"subscription": {
                "id": ID, "notification_url": detail_url,
                "enabled": enabled, "event_types": ["payment.updated"],
                "signature_key": key,
            }})
        raise AssertionError("Unexpected Square API target")
    return get

class Tests(unittest.TestCase):
    def test_disabled_key_retrieval_and_local_hmac_no_delivery(self):
        value, code = m.audit(ENV, opener=responses())
        self.assertEqual(code, 0)
        self.assertEqual(value,
                         "new_disabled_subscription_key_readable_local_hmac_ok")
        for sensitive in (ID, KEY, "FAKE_TOKEN_FOR_TESTS_ONLY"):
            self.assertNotIn(sensitive, value)

    def test_missing_key_or_wrong_url_is_not_verified(self):
        for kwargs in ({"key": ""}, {"key": None},
                       {"detail_url": m.TARGET + "/"},
                       {"enabled": True}, {"duplicate": True}):
            with self.subTest(kwargs=kwargs):
                self.assertEqual(m.audit(ENV, opener=responses(**kwargs))[1], 2)

    def test_wrong_environment_never_contacts_square(self):
        self.assertEqual(m.audit({}, opener=lambda *_: self.fail("network"))[1], 3)

if __name__ == "__main__":
    unittest.main()
