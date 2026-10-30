"""Offline-only tests for future transactional customer email transport.

All supposed 'live' context is synthetic, no real buyer, provider, Square,
Railway environment changes or outbound network requests.
"""
from pathlib import Path
from tempfile import TemporaryDirectory
import json
import sqlite3
import unittest

from shop_payments.customer_email_transport import (
    CustomerEmailJournal, CustomerMailBlocked, live_gate, resend_customer,
)

ORDER = "FOOD" + "a" * 32
KEY = "test-only-not-a-real-resend-key-123456789"
LIVE = {
    "BIGPAW_ENV": "live",
    "BIGPAW_SHOP_CUSTOMER_EMAIL_ENABLED": "1",
    "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "1",
    "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "1",
}
# Deliberately fake data. No real buyer email or Square payment.
PREPARED = {
    "order_id": ORDER,
    "kind": "customer_order_confirmed",
    "to": "synthetic-buyer@example.invalid",
    "subject": "ご注文について（オフライン試験）",
    "body": "模擬注文の内容をお知らせします。",
    "snapshot_digest": "b"*64,
    "prepared_only": True,
    "live_square_verified": True,
}


class TransportSafetyTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "journal.sqlite"
        self.journal = CustomerEmailJournal(self.path)
        self.calls = []
        def fake_sender(**values):
            self.calls.append(values)
            return "syntheticProviderReceipt12345"
        self.sender = fake_sender

    def call(self, prepared=None, env=None, confirmed=True, sender=None):
        return self.journal.send_once(
            prepared if prepared is not None else PREPARED,
            env=env if env is not None else LIVE,
            confirmed=confirmed, api_key=KEY,
            sender=sender if sender is not None else self.sender,
        )

    def test_default_and_sandbox_can_never_send(self):
        self.assertFalse(live_gate({}))
        self.assertFalse(live_gate(None))
        self.assertFalse(live_gate({"BIGPAW_ENV":"sandbox"}))
        self.assertFalse(live_gate({**LIVE,"BIGPAW_ENV":"sandbox"}))
        self.assertFalse(live_gate({**LIVE,"BIGPAW_SHOP_STAGING_ISOLATED":"1"}))
        self.assertFalse(live_gate({**LIVE,"BIGPAW_SHOP_STAGE_PREVIEW_ENABLED":"1"}))
        for field in ("BIGPAW_SHOP_CUSTOMER_EMAIL_ENABLED",
                      "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED",
                      "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED"):
            self.assertFalse(live_gate({**LIVE,field:"0"}))
        with self.assertRaises(CustomerMailBlocked):
            self.journal.send_once(PREPARED,api_key=KEY,sender=self.sender)
        with self.assertRaises(CustomerMailBlocked):
            self.call(env={**LIVE,"BIGPAW_ENV":"sandbox"})
        with self.assertRaises(CustomerMailBlocked):
            self.call(confirmed=False)
        with self.assertRaises(CustomerMailBlocked):
            self.call(prepared={**PREPARED,"live_square_verified":False})
        self.assertEqual(self.calls,[])
        self.assertFalse(self.path.exists())

    def test_one_provider_attempt_then_permanent_idempotency(self):
        response = self.call()
        self.assertEqual(response,{"status":"accepted","new_send":True,
                                   "customer_contacted":None})
        self.assertEqual(len(self.calls),1)
        args = self.calls[0]
        self.assertEqual(args["recipient"],PREPARED["to"])
        self.assertEqual(args["key"],
                         "bigpaw-shop-customer/v1/" + ORDER + "/customer_order_confirmed")
        self.assertEqual(args["subject"],PREPARED["subject"])
        self.assertEqual(args["body"],PREPARED["body"])
        self.assertEqual(self.call()["new_send"],False)
        self.assertEqual(len(self.calls),1)
        self.assertEqual(self.journal.history(ORDER,"customer_order_confirmed")["status"],"accepted")
        raw=self.path.read_bytes()
        for forbidden in (PREPARED["to"],PREPARED["subject"],
                          PREPARED["body"],KEY):
            self.assertNotIn(forbidden.encode("utf-8"),raw)
        # Even a recipient change with unchanged digest cannot re-send.
        self.assertEqual(self.call({**PREPARED,"to":"new@example.invalid"})["new_send"],False)
        with self.assertRaises(CustomerMailBlocked):
            self.call({**PREPARED,"snapshot_digest":"c"*64})

    def test_ambiguous_failure_is_never_retried(self):
        def uncertain(**kwargs):
            self.calls.append(kwargs)
            raise TimeoutError("uncertain network delivery")
        first=self.call(sender=uncertain)
        self.assertEqual(first["status"],"unknown")
        self.assertEqual(first["customer_contacted"],None)
        self.assertEqual(self.call()["new_send"],False)
        self.assertEqual(self.journal.history(ORDER,"customer_order_confirmed")["status"],"unknown")
        self.assertEqual(len(self.calls),1)

    def test_crash_after_reservation_must_not_resend(self):
        with sqlite3.connect(self.path) as db:
            self.journal._install(db)
            db.execute(
                "INSERT INTO food_customer_email_delivery "
                "(order_id,kind,snapshot_digest,status,created_at,updated_at) "
                "VALUES (?,?,?,'reserved',1,1)",
                (ORDER,"customer_order_confirmed",PREPARED["snapshot_digest"])
            )
        self.assertEqual(self.call()["status"],"reserved")
        self.assertEqual(self.calls,[])

    def test_validation_rejects_unsupported_kinds_and_broken_drafts(self):
        invalids=(
            {"kind":"customer_refund_completed"},
            {"order_id":"UNKNOWN"},
            {"to":"not-an-email"},
            {"to":"buyer@example.invalid\nBcc:bad@example.invalid"},
            {"prepared_only":False},
            {"live_square_verified":False},
            {"snapshot_digest":"wrong"},
            {"subject":"hello\nBCC: somebody"},
            {"body":""},
            {"body":"【運営が確認して入力】"},
        )
        for values in invalids:
            with self.subTest(values=values):
                with self.assertRaises(CustomerMailBlocked):
                    self.call({**PREPARED,**values})
        self.assertFalse(self.path.exists())

    def test_provider_request_uses_approved_api_recipient_and_key(self):
        class FakeResponse:
            status=201
            def __enter__(self):return self
            def __exit__(self,*args):return False
            def read(self,n):return json.dumps({"id":"TEST-Resend-Receipt1234"}).encode()
        def open_fake(req,timeout):
            self.assertEqual(req.get_method(),"POST")
            self.assertEqual(req.full_url,"https://api.resend.com/emails")
            self.assertEqual(timeout,10)
            self.assertEqual(req.headers["Idempotency-key"],"mail-test-123")
            self.assertTrue(req.headers["Authorization"].startswith("Bearer "))
            payload=json.loads(req.data)
            self.assertEqual(payload["to"],[PREPARED["to"]])
            self.assertEqual(payload["reply_to"],"info@bigpaw.site")
            self.assertNotIn("cc",payload)
            self.assertNotIn("bcc",payload)
            return FakeResponse()
        provider_id=resend_customer(
            api_key=KEY,recipient=PREPARED["to"],subject=PREPARED["subject"],
            body=PREPARED["body"],key="mail-test-123",opener=open_fake,
        )
        self.assertEqual(provider_id,"TEST-Resend-Receipt1234")
        def err(req,timeout): raise TimeoutError("network lost")
        with self.assertRaises(CustomerMailBlocked):
            resend_customer(api_key=KEY,recipient=PREPARED["to"],
                subject="test",body="test",key="k",opener=err)

if __name__=="__main__":
    unittest.main()
