#!/usr/bin/env python3
"""Offline regression tests for operator mail read-only delivery audit."""
import importlib.util
import io
import json
from pathlib import Path
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

module_path = Path(__file__).with_name("resend_operator_delivery_audit.py")
spec = importlib.util.spec_from_file_location("resend_operator_delivery_audit", module_path)
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class DeliveryAuditTest(unittest.TestCase):
    def test_exact_recipient_and_subject_only(self):
        emails = [
            {"id": "a1", "to": ["info@bigpaw.site"], "subject": "【BIG PAW】新しいブリーダー掲載申請",
             "created_at": "2026-10-09T13:07:00Z", "last_event": "bounced"},
            {"id": "a2", "to": ["else@example.com"], "subject": "新しいブリーダー掲載申請",
             "last_event": "delivered"},
            {"id": "a3", "to": ["info@bigpaw.site"], "subject": "その他",
             "last_event": "sent"},
            {"id": "a4", "to": ["INFO@BIGPAW.SITE"], "subject": "新しいブリーダー掲載申請",
             "last_event": "delivered"},
        ]
        entries = audit.operator_entries(emails)
        self.assertEqual([e["id"] for e in entries], ["a1", "a4"])
        self.assertEqual(entries[0]["event"], "bounced")
        self.assertNotIn("to", entries[0])
        self.assertNotIn("subject", entries[0])

    def test_read_only_paginated_statuses(self):
        requests = []
        pages = [
            {"data": [{"id": "x1", "to": ["info@bigpaw.site"], "subject": "新しいブリーダー掲載申請",
                        "last_event": "delivery_delayed"}], "has_more": True},
            {"data": [{"id": "x2", "to": ["info@bigpaw.site"], "subject": "新しいブリーダー掲載申請",
                        "last_event": "delivered"}], "has_more": False},
        ]
        def opener(req, timeout):
            requests.append(req)
            return FakeResponse(json.dumps(pages[len(requests) - 1]).encode("utf-8"))
        items = audit.fetch_recent("fake-token", opener=opener)
        self.assertEqual([e["event"] for e in items], ["delivery_delayed", "delivered"])
        self.assertEqual(len(requests), 2)
        self.assertIn("after=x1", requests[1].full_url)
        self.assertEqual([r.get_method() for r in requests], ["GET", "GET"])

    def test_domain_verification_is_read_only_and_omits_dns_secrets(self):
        requests = []
        pages = [
            {"data": [
                {"id": "ignored-id", "name": "other.example", "status": "verified"},
                {"id": "bigpaw-domain-id", "name": "bigpaw.site",
                 "status": "verified", "capabilities": {"sending": "enabled"}},
            ]},
            {"id": "bigpaw-domain-id", "name": "bigpaw.site", "status": "verified",
             "capabilities": {"sending": "enabled"},
             "records": [
                {"record": "DKIM", "status": "verified", "value": "secret-public-key"},
                {"record": "SPF", "status": "failed", "value": "unwanted-record-value"},
                {"record": "SPF", "status": "verified", "value": "unwanted-record-value2"},
                {"record": "Tracking", "status": "verified", "value": "tracking.example"},
             ]},
        ]
        def opener(req, timeout):
            requests.append(req)
            return FakeResponse(json.dumps(pages[len(requests) - 1]).encode("utf-8"))
        result = audit.fetch_sender_domain_status("fake-key", opener=opener)
        self.assertEqual(result["status"], "verified")
        self.assertEqual(result["sending"], "enabled")
        self.assertEqual(result["records"]["SPF"], ["failed", "verified"])
        self.assertEqual(result["records"]["DKIM"], ["verified"])
        self.assertNotIn("secret-public-key", json.dumps(result))
        self.assertNotIn("unwanted-record-value", json.dumps(result))
        self.assertEqual([x.get_method() for x in requests], ["GET", "GET"])
        self.assertEqual(requests[1].full_url, "https://api.resend.com/domains/bigpaw-domain-id")

    def test_missing_domain_is_reported_without_leak(self):
        def opener(_req, timeout):
            return FakeResponse(b'{"data": []}')
        result = audit.fetch_sender_domain_status("fake-key", opener=opener)
        self.assertEqual(result["status"], "missing")
        self.assertEqual(result["records"], {})

    def test_domain_permission_denied_does_not_crash(self):
        with patch.object(audit, "fetch_sender_domain_status", side_effect=HTTPError(
                "https://api.resend.com/domains", 403, "Forbidden", {}, None)):
            audit.audit_sender_domain("fake-token")

    def test_missing_key_requires_no_remote_call(self):
        with patch.dict(audit.os.environ, {"RESEND_API_KEY": ""}):
            self.assertEqual(audit.main(), 0)

    def test_insufficient_read_permissions_do_not_crash(self):
        def fail(_key):
            raise HTTPError("https://api.resend.com/emails", 403, "forbidden", {}, None)
        with patch.dict(audit.os.environ, {"RESEND_API_KEY": "fake"}):
            with patch.object(audit, "fetch_recent", side_effect=fail):
                self.assertEqual(audit.main(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
