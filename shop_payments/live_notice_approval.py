"""Offline-only durable owner approval for a future customer order email.

Not imported by live routes, Sandbox services, or any email transport. This is
not an authorization or delivery service. Future caller MUST authenticate the
operator using independent session/role/CSRF checks and provide explicit
per-order confirmation; booleans here do NOT authenticate a user.

Every approval binds to the exact HMAC fingerprint from an independent fresh
Square Payments+Orders lookup and immutable, paid order ledger. No customer
PII, live API tokens, provider keys, or message text is saved in SQLite.
An approval expires after 15 minutes and must be reviewed again if the buyer's
email, payment, refund status, shipment data, or message changes.
The only output is a review result. There is NO sendable payload or mail call.
"""
from __future__ import annotations

from contextlib import closing
import hmac
import re
import sqlite3
import time

from .live_customer_notice_preview import preview_paid_order_confirmation
from .live_order_ledger import LiveOrderBlocked, LiveOrderLedger

FINGERPRINT = re.compile(r"^[0-9a-f]{64}$")
APPROVAL_SECONDS = 15 * 60
KIND = "customer_order_confirmed"


def _guard(ledger, order_id, reviewed_fingerprint=None):
    if not isinstance(ledger, LiveOrderLedger):
        raise LiveOrderBlocked("Private live ledger required")
    if not isinstance(order_id, str) or not re.fullmatch(r"FOOD[0-9a-f]{32}", order_id):
        raise LiveOrderBlocked("Invalid local order reference")
    if reviewed_fingerprint is not None and (
        not isinstance(reviewed_fingerprint, str)
        or FINGERPRINT.fullmatch(reviewed_fingerprint) is None
    ):
        raise LiveOrderBlocked("Invalid reviewed fingerprint")


class LiveNoticeApproval:
    """Only future authenticated backend code may instantiate and call this."""

    def __init__(self, ledger: LiveOrderLedger):
        if not isinstance(ledger, LiveOrderLedger):
            raise LiveOrderBlocked("Private live ledger required")
        self.ledger = ledger

    def _open(self):
        # Reuse the private order ledger's SQLite journal; no PII is written.
        return self.ledger._open()

    @staticmethod
    def _install(db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS food_live_notice_review (
                order_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                fingerprint TEXT NOT NULL,
                state TEXT NOT NULL CHECK(state IN ('approved','revoked')),
                approved_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL,
                PRIMARY KEY(order_id, kind)
            )
        """)

    def approve(self, *, order_id, reviewed_fingerprint, authorized=False,
                confirmed=False, api_key=None, review_secret=None,
                opener=None, verifier=None, now=None):
        """Record a distinct human's decision after fresh validation.

        The operator must have seen the matching fingerprint in a protected
        backend UI and explicitly confirmed this exact preview. No method
        initiates email sending or calls the live Resend adapter.
        """
        _guard(self.ledger, order_id, reviewed_fingerprint)
        if authorized is not True or confirmed is not True:
            raise LiveOrderBlocked("Authorized explicit review required")
        when = int(time.time() if now is None else now)
        if when < 1:
            raise LiveOrderBlocked("Invalid review clock")
        params = dict(ledger=self.ledger, order_id=order_id,
                      api_key=api_key, review_secret=review_secret)
        if opener is not None:
            params["opener"] = opener
        if verifier is not None:
            params["verifier"] = verifier
        # Reads fresh Square payment/refund, Order and recipient details.
        draft = preview_paid_order_confirmation(**params)
        if (draft.get("review_only") is not True
                or draft.get("send_enabled") is not False
                or not hmac.compare_digest(
                    draft["review_fingerprint"], reviewed_fingerprint)):
            raise LiveOrderBlocked("Reviewed order or contact changed")
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                db.execute(
                    "INSERT INTO food_live_notice_review "
                    "(order_id,kind,fingerprint,state,approved_at,expires_at) "
                    "VALUES (?,?,?,'approved',?,?) "
                    "ON CONFLICT(order_id,kind) DO UPDATE SET "
                    "fingerprint=excluded.fingerprint,state='approved',"
                    "approved_at=excluded.approved_at,expires_at=excluded.expires_at",
                    (order_id, KIND, reviewed_fingerprint, when,
                     when + APPROVAL_SECONDS),
                )
                db.execute("COMMIT")
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"approved": True, "order_id": order_id,
                "expires_at": when + APPROVAL_SECONDS,
                "send_enabled": False, "sent": False}

    def check(self, *, order_id, api_key=None, review_secret=None,
              opener=None, verifier=None, now=None):
        """Revalidate latest Square facts against the current human approval.

        This is a no-send dry-run ONLY, never permission to invoke a provider.
        For any future provider send a separate, fresh, atomic authorization
        and live-launch integration is still required.
        """
        _guard(self.ledger, order_id)
        when = int(time.time() if now is None else now)
        if when < 1:
            raise LiveOrderBlocked("Invalid verification clock")
        with closing(self._open()) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_live_notice_review'"
            ).fetchone()
            if exists is None:
                raise LiveOrderBlocked("No operator review")
            row = db.execute(
                "SELECT fingerprint,state,approved_at,expires_at "
                "FROM food_live_notice_review WHERE order_id=? AND kind=?",
                (order_id, KIND),
            ).fetchone()
        if (row is None or row["state"] != "approved"
                or row["approved_at"] > when or row["expires_at"] <= when):
            raise LiveOrderBlocked("Approval missing, revoked or expired")
        params = dict(ledger=self.ledger, order_id=order_id,
                      api_key=api_key, review_secret=review_secret)
        if opener is not None:
            params["opener"] = opener
        if verifier is not None:
            params["verifier"] = verifier
        current = preview_paid_order_confirmation(**params)
        if not hmac.compare_digest(row["fingerprint"], current["review_fingerprint"]):
            raise LiveOrderBlocked("Latest Square evidence invalidates review")
        # No receiver address or sendable payload is exposed.
        return {"approved": True, "order_id": order_id,
                "masked_recipient": current["masked_recipient"],
                "expires_at": row["expires_at"],
                "send_enabled": False, "sent": False}

    def revoke(self, *, order_id, authorized=False, confirmed=False):
        """Fail closed immediately without contacting Square."""
        _guard(self.ledger, order_id)
        if authorized is not True or confirmed is not True:
            raise LiveOrderBlocked("Authorized explicit revocation required")
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                cursor = db.execute(
                    "UPDATE food_live_notice_review SET state='revoked' "
                    "WHERE order_id=? AND kind=? AND state='approved'",
                    (order_id, KIND),
                )
                db.execute("COMMIT")
                changed = cursor.rowcount > 0
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
        return {"revoked": changed, "sent": False}
