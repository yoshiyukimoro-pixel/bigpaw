"""Offline safety tests for the read-only emergency-stop exposure audit."""
import contextlib
import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

spec = importlib.util.spec_from_file_location(
    "stop_audit", Path("scripts/audit-shop-stop-readiness.py"))
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


class StopReadinessTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.file = Path(self.temp.name) / "synthetic-orders.sqlite3"
        with sqlite3.connect(self.file) as db:
            db.execute("""CREATE TABLE food_live_checkout_intent (
                order_id TEXT PRIMARY KEY, state TEXT,
                square_link_id TEXT, square_order_id TEXT,
                synthetic_buyer_email TEXT
            )""")
            db.execute("""CREATE TABLE food_live_order_ledger (
                order_id TEXT PRIMARY KEY, state TEXT
            )""")
            db.executemany(
                "INSERT INTO food_live_checkout_intent VALUES(?,?,?,?,?)", [
                    ("FOODPLANNED", "planned", None, None, "private@example.invalid"),
                    ("FOODUNKNOWN", "attempt_unknown", None, None, "private@example.invalid"),
                    ("FOODLINK1", "link_bound", "LINK_SECRET1", "SQORDER1", "private@example.invalid"),
                    ("FOODLINK2", "link_bound", "LINK_SECRET2", "SQORDER2", "private@example.invalid"),
                ])
            db.executemany("INSERT INTO food_live_order_ledger VALUES(?,?)", [
                ("FOODLINK1", "checkout_recorded"),
                ("FOODLINK2", "paid_verified"),
            ])

    def test_readonly_counts_are_complete_but_never_expose_ids_or_pii(self):
        before = hashlib.sha256(self.file.read_bytes()).hexdigest()
        result = audit.inspect(self.file)
        self.assertEqual(result["planned_no_link"], 1)
        self.assertEqual(result["attempt_unknown_requires_square_review"], 1)
        self.assertEqual(result["link_bound_total_requires_square_link_review"], 2)
        self.assertEqual(result["link_bound_payment_verified"], 1)
        self.assertEqual(result["link_bound_not_payment_verified"], 1)
        self.assertTrue(result["needs_external_square_dashboard_review"])
        self.assertFalse(result["existing_links_automatically_cancelled"])
        self.assertFalse(result["square_contacted"])
        text = json.dumps(result)
        for value in ("FOODLINK1", "LINK_SECRET", "private@example.invalid",
                      "SQORDER"):
            self.assertNotIn(value, text)
        self.assertEqual(before, hashlib.sha256(self.file.read_bytes()).hexdigest())

    def test_unknown_order_needs_review_even_without_bound_link(self):
        with sqlite3.connect(self.file) as db:
            db.execute("DELETE FROM food_live_checkout_intent WHERE state='link_bound'")
            db.execute("DELETE FROM food_live_order_ledger")
        result = audit.inspect(self.file)
        self.assertEqual(result["link_bound_total_requires_square_link_review"], 0)
        self.assertTrue(result["needs_external_square_dashboard_review"])

    def test_empty_local_journal_is_not_proof_square_has_no_links(self):
        with sqlite3.connect(self.file) as db:
            db.execute("DELETE FROM food_live_checkout_intent")
            db.execute("DELETE FROM food_live_order_ledger")
        result = audit.inspect(self.file)
        self.assertFalse(result["needs_external_square_dashboard_review"])
        self.assertFalse(result["existing_links_automatically_cancelled"])
        self.assertEqual(result["scope"], "local_readonly_aggregate_only")

    def test_absent_database_does_not_create_file(self):
        missing = Path(self.temp.name) / "not-there.sqlite3"
        with self.assertRaises(audit.AuditBlocked):
            audit.inspect(missing)
        self.assertFalse(missing.exists())
        with contextlib.redirect_stdout(io.StringIO()) as out:
            self.assertEqual(audit.main(["--db", str(missing)]), 2)
        self.assertIn("BLOCKED", out.getvalue())
        self.assertFalse(missing.exists())

    def test_corrupt_or_incorrect_schema_fails_without_identifiers(self):
        wrong = Path(self.temp.name) / "wrong.sqlite3"
        wrong.write_bytes(b"not sqlite and never a valid customer db")
        with self.assertRaises(audit.AuditBlocked):
            audit.inspect(wrong)
        with sqlite3.connect(self.file) as db:
            db.execute("DROP TABLE food_live_order_ledger")
        with self.assertRaises(audit.AuditBlocked):
            audit.inspect(self.file)

    def test_cli_prints_only_aggregate_fields(self):
        stdout = io.StringIO()
        with contextlib.redirect_stdout(stdout):
            self.assertEqual(audit.main(["--db", str(self.file)]), 0)
        record = json.loads(stdout.getvalue())
        self.assertEqual(record["link_bound_total_requires_square_link_review"], 2)
        self.assertNotIn("LINK_SECRET1", stdout.getvalue())
        self.assertNotIn("private@example.invalid", stdout.getvalue())


if __name__ == "__main__":
    unittest.main()
