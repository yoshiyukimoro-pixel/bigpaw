"""Sandbox-only, NO-NETWORK customer notification attempt journal.

Models the *state machine* required by a future mail provider integration:
one reservation per order and kind; accepted / refused / uncertain outcomes
are never automatically retried. A lost worker leaves 'reserved' and also
cannot automatically retry. This module does NOT import any mail sender.
No customer name, address, email, token, message body or tracking number is
stored here. Statuses are explicitly simulation statuses, NEVER real delivery.
"""
from __future__ import annotations

from contextlib import closing
import re
import sqlite3
import time

from .customer_mail_preflight import prepare_customer_email
from .sandbox_customer_review import CUSTOMER_KINDS, ORDER_ID

OUTCOMES = frozenset((
    "simulated_accepted", "simulated_refused", "simulated_unknown",
))
DIGEST = re.compile(r"^[0-9a-f]{64}$")


class SandboxCustomerMailAttempts:
    def __init__(self, store):
        self.store = store

    def _open(self):
        db = sqlite3.connect(self.store.db_file, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _install(db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS food_sandbox_customer_mail_attempts (
                order_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN
                    ('customer_order_confirmed','customer_shipment_notice')),
                snapshot_digest TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN (
                    'reserved','simulated_accepted',
                    'simulated_refused','simulated_unknown')),
                reserved_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY (order_id,kind)
            )
        """)

    def status(self, order_id, kind):
        if (not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id)
                or kind not in CUSTOMER_KINDS):
            return None
        with closing(self._open()) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_sandbox_customer_mail_attempts'"
            ).fetchone()
            if not exists:
                return None
            row = db.execute(
                "SELECT status FROM food_sandbox_customer_mail_attempts "
                "WHERE order_id=? AND kind=?", (order_id, kind)
            ).fetchone()
        return row["status"] if row else None

    def simulate_attempt_once(
        self, order_id, kind, *, sandbox_token: str,
        outcome: str, opener=None
    ) -> dict:
        """Simulate one attempt, without ANY mail provider activity.

        The ONLY external operation allowed to the preparer is a fresh Square
        Sandbox GET. Caller must explicitly pick one of three simulated
        outcomes. Once a reservation is recorded, it cannot be retried,
        including for 'reserved' or unknown (provider response ambiguous).
        """
        if (not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id)
                or kind not in CUSTOMER_KINDS or outcome not in OUTCOMES):
            raise ValueError("Invalid no-network simulation request")
        prepared = prepare_customer_email(
            self.store, order_id, kind, sandbox_token=sandbox_token,
            opener=opener,
        )
        digest = prepared["snapshot_digest"]
        if not isinstance(digest, str) or not DIGEST.fullmatch(digest):
            raise ValueError("Invalid customer notification snapshot")
        # Drop any reference to the ephemeral recipient before DB access.
        del prepared
        now = int(time.time())
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                row = db.execute(
                    "SELECT snapshot_digest,status FROM "
                    "food_sandbox_customer_mail_attempts "
                    "WHERE order_id=? AND kind=?", (order_id, kind)
                ).fetchone()
                if row:
                    if row["snapshot_digest"] != digest:
                        raise ValueError("Contact or draft changed since first attempt")
                    db.execute("COMMIT")
                    return {"status": row["status"], "first_attempt": False,
                            "sent": False}
                db.execute(
                    "INSERT INTO food_sandbox_customer_mail_attempts "
                    "(order_id,kind,snapshot_digest,status,reserved_at,updated_at) "
                    "VALUES (?,?,?,'reserved',?,?)",
                    (order_id, kind, digest, now, now)
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        # A real sender is intentionally NEVER invoked. This is an offline
        # deterministic simulation. If process stops now, 'reserved' remains
        # and repeat attempts are still blocked.
        with closing(self._open()) as db:
            db.execute(
                "UPDATE food_sandbox_customer_mail_attempts "
                "SET status=?,updated_at=? "
                "WHERE order_id=? AND kind=? AND snapshot_digest=? "
                "AND status='reserved'",
                (outcome, int(time.time()), order_id, kind, digest)
            )
        return {"status": outcome, "first_attempt": True, "sent": False}
