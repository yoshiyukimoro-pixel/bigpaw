"""Offline tests for the opt-in seller disclosure HTTP bridge.
No live email, address, phone, checkout or external Square calls.
"""
import io
import json
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app" / "backend"))
import shop_seller_disclosure_bridge as bridge

TOKEN = "A" * 43
PRIVATE_ADDRESS = "Example prefecture private street TEST ONLY"
PRIVATE_PHONE = "0300000000"
ENV = {
    "BIGPAW_ENV": "production",
    "BIGPAW_SHOP_SELLER_DISCLOSURE_AUTO_ENABLED": "1",
    "RESEND_API_KEY": "re_TEST_ONLY_REDACTED_VALUE",
    "BIGPAW_SHOP_SELLER_NAME": "FAKE SELLER",
    "BIGPAW_SHOP_SELLER_POSTAL": "000-0000",
    "BIGPAW_SHOP_SELLER_ADDRESS": PRIVATE_ADDRESS,
    "BIGPAW_SHOP_SELLER_PHONE": PRIVATE_PHONE,
}


class Handler:
    def __init__(self, token=TOKEN, origin="https://bigpaw.site"):
        self.path = bridge.CONFIRM_PATH
        self.headers = {"Host": "bigpaw.site", "Origin": origin,
                        "Content-Type": "application/json",
                        "Sec-Fetch-Site": "same-origin"}
        body = json.dumps({"token": token}).encode()
        self.headers["Content-Length"] = str(len(body))
        self.rfile = io.BytesIO(body)
        self.client_address = ("127.0.0.1", 12345)
        self.calls = []

    def send_json(self, value, status=200, extra=None):
        self.calls.append((status, value, extra))


def database():
    db = sqlite3.connect(":memory:")
    db.execute("""CREATE TABLE support_tickets (
      id TEXT PRIMARY KEY, email TEXT NOT NULL, status TEXT NOT NULL,
      operator_note TEXT NOT NULL DEFAULT '', updated_at INTEGER NOT NULL)""")
    db.execute("""CREATE TABLE audit_logs (
      id TEXT PRIMARY KEY, user_id TEXT, action TEXT, target_type TEXT,
      target_id TEXT, detail TEXT, created_at INTEGER)""")
    db.execute("INSERT INTO support_tickets VALUES ('sup_TEST','buyer@example.invalid','open','',0)")
    db.commit()
    return db


class BridgeTests(unittest.TestCase):
    def test_off_has_no_db_and_no_read_or_mail(self):
        h = Handler()
        def unexpected_db():
            self.fail("disabled endpoint must not open any DB")
        self.assertTrue(bridge.handle_confirm(
            h, env={**ENV, "BIGPAW_SHOP_SELLER_DISCLOSURE_AUTO_ENABLED": "0"},
            base_url="https://bigpaw.site", db_factory=unexpected_db))
        self.assertEqual(h.calls[0][0], 404)
        self.assertEqual(h.rfile.tell(), 0)

    def test_origin_host_and_content_block_before_db(self):
        bad_headers = (
            ("Origin", "https://evil.invalid"),
            ("Host", "attacker.invalid"),
            ("Sec-Fetch-Site", "cross-site"),
            ("X-Forwarded-Proto", "http"),
            ("Authorization", "Bearer bad"),
        )
        for header, value in bad_headers:
            with self.subTest(header=header):
                h = Handler()
                h.headers[header] = value
                bridge.handle_confirm(h, env=ENV, base_url="https://bigpaw.site",
                                      db_factory=lambda: self.fail("unsafe DB access"))
                self.assertEqual(h.calls[0][0], 403)
                self.assertEqual(h.rfile.tell(), 0)
        h = Handler()
        h.headers["Content-Length"] = "99999"
        bridge.handle_confirm(h, env=ENV, base_url="https://bigpaw.site",
                              db_factory=lambda: self.fail("large body DB"))
        self.assertEqual(h.calls[0][0], 400)

    def test_verified_one_time_token_sends_private_details_once(self):
        db = database()
        outbox = []
        def mail(key, to, subject, body, idem):
            self.assertEqual(to, "buyer@example.invalid")
            outbox.append((subject, body))
            return "mail_TEST12345"
        with patch.object(bridge.disclosure.secrets, "token_urlsafe", return_value=TOKEN):
            self.assertEqual(bridge.request_challenge(
                db, "sup_TEST", "buyer@example.invalid", env=ENV, sender=mail),
                "verification_sent")
        self.assertEqual(len(outbox), 1)
        self.assertNotIn(PRIVATE_ADDRESS, outbox[0][1])
        self.assertNotIn(PRIVATE_PHONE, outbox[0][1])
        db_factory = lambda: db
        # Bridge closes its connection. Use a file-backed fixture for this path.
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            disk = Path(tmp) / "test.sqlite"
            clone = sqlite3.connect(disk)
            db.backup(clone)
            clone.close()
            db.close()
            def open_db():
                return sqlite3.connect(disk)
            with patch.object(bridge.disclosure, "time", __import__("time")):
                h = Handler()
                bridge.handle_confirm(h, env=ENV, base_url="https://bigpaw.site",
                                      db_factory=open_db, sender=mail)
                self.assertEqual(h.calls[0][0], 200)
                self.assertEqual(h.calls[0][1], {"status":"provider_accepted"})
                self.assertEqual(len(outbox), 2)
                self.assertIn(PRIVATE_ADDRESS, outbox[1][1])
                self.assertIn(PRIVATE_PHONE, outbox[1][1])
                second = Handler()
                bridge.handle_confirm(second, env=ENV, base_url="https://bigpaw.site",
                                      db_factory=open_db, sender=mail)
                self.assertEqual(second.calls[0][0], 400)
                self.assertEqual(len(outbox), 2)
            with open_db() as conn:
                audit = str(conn.execute("SELECT * FROM food_seller_disclosure").fetchall()) + str(
                    conn.execute("SELECT * FROM audit_logs").fetchall())
                self.assertNotIn(PRIVATE_ADDRESS, audit)
                self.assertNotIn(PRIVATE_PHONE, audit)

    def test_real_server_routing_remains_off_by_default(self):
        s = (ROOT / "app/backend/server.py").read_text(encoding="utf-8")
        get_part = s.split("    def do_GET(self):", 1)[1].split("    def do_POST(self):", 1)[0]
        post_part = s.split("    def do_POST(self):", 1)[1]
        self.assertNotIn("shop_seller_disclosure_bridge", get_part)
        self.assertIn("if path == '/api/shop/seller-disclosure/confirm':", post_part)
        self.assertIn("request_challenge(con, tid, email", post_part)
        self.assertIn("con.commit()\n            # A request email challenge", post_part)
        self.assertIn("if path in ('/api/operator/shop-orders/reconcile',", post_part)


if __name__ == "__main__":
    unittest.main()
