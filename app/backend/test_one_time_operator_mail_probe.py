#!/usr/bin/env python3
"""Offline unit tests for the one-time BIG PAW real-sender email probe."""
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

target = Path(__file__).with_name("one_time_operator_mail_probe.py")
spec = importlib.util.spec_from_file_location("one_time_operator_mail_probe", target)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self
    def __exit__(self, *args):
        self.close()


class OperatorMailProbeTests(unittest.TestCase):
    def test_exact_destination_and_single_send(self):
        sent = []
        def sender(to, subject, content):
            sent.append((to, subject, content))
            return True
        with tempfile.TemporaryDirectory() as directory:
            result, accepted = probe.send_once("20261010-A", directory, sender)
            self.assertEqual((result, accepted), ("provider_accepted", True))
            result2, accepted2 = probe.send_once("20261010-A", directory, sender)
            self.assertEqual((result2, accepted2), ("already_attempted", False))
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0][0], "info@bigpaw.site")
            self.assertIn("配信テスト", sent[0][1])
            self.assertIn("実際のブリーダー申請があったわけではありません", sent[0][2])
            markers = list(Path(directory).glob(".bigpaw-mail-test-*.once"))
            self.assertEqual(len(markers), 1)

    def test_real_application_subject_and_body_are_safe(self):
        sent = []
        def sender(to, subject, body):
            sent.append((to, subject, body))
            return True
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(
                probe.send_once("20261010-realistic-1", directory, sender,
                                mode="breeder_application"),
                ("provider_accepted", True),
            )
            self.assertEqual(len(sent), 1)
            self.assertEqual(sent[0][0], "info@bigpaw.site")
            self.assertEqual(sent[0][1], "【BIG PAW】新しいブリーダー掲載申請")
            self.assertIn("新しいブリーダー掲載申請が届きました。", sent[0][2])
            self.assertIn("実際のブリーダー申請はありません", sent[0][2])
            self.assertIn("test-only@example.invalid", sent[0][2])
            self.assertIn("operator-breeders.html", sent[0][2])
            self.assertEqual(
                probe.send_once("20261010-realistic-1", directory, sender,
                                mode="breeder_application"),
                ("already_attempted", False),
            )

    def test_real_subject_delivery_audit_skips_older_notifications(self):
        recorded = []
        pages = [
            {"data": [
                {"id": "old", "to": ["info@bigpaw.site"],
                 "subject": "【BIG PAW】新しいブリーダー掲載申請",
                 "created_at": "2026-10-09T13:07:07+00:00", "last_event": "delivered"},
                {"id": "test1", "to": ["info@bigpaw.site"],
                 "subject": "【BIG PAW】新しいブリーダー掲載申請",
                 "created_at": "2026-10-10T00:00:02+00:00", "last_event": "sent"},
            ]},
            {"data": [
                {"id": "test1", "to": ["info@bigpaw.site"],
                 "subject": "【BIG PAW】新しいブリーダー掲載申請",
                 "created_at": "2026-10-10T00:00:02+00:00", "last_event": "delivered"},
            ]},
        ]
        def opener(req, timeout):
            recorded.append(req)
            return FakeResponse(json.dumps(pages[len(recorded) - 1]).encode("utf-8"))
        from datetime import datetime
        lower_bound = datetime.fromisoformat("2026-10-10T00:00:00+00:00").timestamp()
        event, mail_id = probe.check_resend_status(
            "20261010-realistic-1", "fake-key", opener=opener,
            sleeper=lambda _: None, mode="breeder_application",
            since_timestamp=lower_bound,
        )
        self.assertEqual((event, mail_id), ("delivered", "test1"))
        self.assertTrue(all(r.get_method() == "GET" for r in recorded))

    def test_reject_invalid_identifier_before_sending(self):
        sent = []
        with tempfile.TemporaryDirectory() as directory:
            result = probe.send_once("../../bad", directory, lambda *args: sent.append(args))
            self.assertEqual(result, ("invalid_probe_id", False))
            self.assertFalse(sent)

    def test_failed_mail_is_never_repeated_after_restart(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertEqual(probe.send_once("20261010-failure", directory, lambda *args: False),
                             ("provider_rejected", False))
            self.assertEqual(probe.send_once("20261010-failure", directory, lambda *args: True),
                             ("already_attempted", False))

    def test_status_is_resend_event_for_unique_subject_and_fixed_recipient(self):
        observed = []
        samples = [
            {"data": [{"id": "bad", "to": ["other@example.com"],
                        "subject": probe.subject_for("20261010-A"),
                        "last_event": "delivered"},
                       {"id": "mail-id", "to": ["info@bigpaw.site"],
                        "subject": probe.subject_for("20261010-A"),
                        "last_event": "sent"}]},
            {"data": [{"id": "mail-id", "to": ["info@bigpaw.site"],
                       "subject": probe.subject_for("20261010-A"),
                       "last_event": "delivered"}]},
        ]
        def opener(req, timeout):
            observed.append(req)
            return FakeResponse(json.dumps(samples[len(observed)-1]).encode("utf-8"))
        event, msg_id = probe.check_resend_status("20261010-A", "fake-key", opener=opener,
                                                sleeper=lambda _: None)
        self.assertEqual((event, msg_id), ("delivered", "mail-id"))
        self.assertEqual([r.get_method() for r in observed], ["GET", "GET"])
        self.assertTrue(all(r.full_url.startswith("https://api.resend.com/emails") for r in observed))

    def test_real_backend_mail_function_can_be_safely_extracted(self):
        sender = probe.live_send_mail()
        self.assertEqual(sender.__name__, "send_mail")
        self.assertIn("RESEND_API_KEY", sender.__code__.co_consts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
