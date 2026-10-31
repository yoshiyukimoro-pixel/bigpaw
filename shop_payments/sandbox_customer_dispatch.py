"""NO-SEND dispatch simulation for isolated Square Sandbox customer notices.

This DOES NOT send anything. It reserves a test-only audit record after
re-fetching Square Sandbox recipient information, verifies operator review
is still valid for both masked contact identity and exact draft content, and
blocks future attempts with conflicting content/contact. No raw email is stored.
Production email delivery is deliberately outside this module.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import sqlite3
import time

from .sandbox_customer_review import SandboxCustomerReview, CUSTOMER_KINDS, ORDER_ID


class SandboxDryRunOutbox:
    def __init__(self, store):
        self.store = store
        self.reviewer = SandboxCustomerReview(store)

    def _open(self):
        db = sqlite3.connect(self.store.db_file, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _install(db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS food_sandbox_customer_dryrun (
                order_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN
                  ('customer_order_confirmed','customer_shipment_notice')),
                snapshot_digest TEXT NOT NULL,
                checked_at INTEGER NOT NULL,
                status TEXT NOT NULL DEFAULT 'simulated_only'
                  CHECK(status='simulated_only'),
                PRIMARY KEY(order_id,kind)
            )
        """)

    def inspected(self, order_id, kind) -> bool:
        if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id) or kind not in CUSTOMER_KINDS:
            return False
        with closing(self._open()) as db:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_sandbox_customer_dryrun'"
            ).fetchone() is None:
                return False
            return db.execute(
                "SELECT 1 FROM food_sandbox_customer_dryrun WHERE order_id=? AND kind=?",
                (order_id, kind)
            ).fetchone() is not None

    def simulate_once(self, order_id, kind, *, token: str, opener=None) -> bool:
        if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id) or kind not in CUSTOMER_KINDS:
            raise ValueError("Unsupported test customer notification")
        # Re-fetch current Square Sandbox checkout recipient and exact draft.
        kwargs = {"token": token}
        if opener is not None:
            kwargs["opener"] = opener
        status = self.reviewer.readiness(order_id, kind, **kwargs)
        if not status["ready"] or not status["reviewed"]:
            raise ValueError("No current operator review of Square address + message")
        a, b = status["_fingerprints"]
        digest = hashlib.sha256(
            (order_id + ":" + kind + ":" + a + ":" + b).encode("ascii")
        ).hexdigest()
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT snapshot_digest FROM food_sandbox_customer_dryrun "
                    "WHERE order_id=? AND kind=?", (order_id, kind)
                ).fetchone()
                if row:
                    if row["snapshot_digest"] != digest:
                        raise ValueError("Previously simulated different contact or content")
                    db.execute("COMMIT")
                    return False
                db.execute(
                    "INSERT INTO food_sandbox_customer_dryrun "
                    "(order_id,kind,snapshot_digest,checked_at,status) "
                    "VALUES (?,?,?,?,'simulated_only')",
                    (order_id, kind, digest, int(time.time()))
                )
                db.execute("COMMIT")
                return True
            except Exception:
                db.execute("ROLLBACK")
                raise
