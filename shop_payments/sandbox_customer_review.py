"""Sandbox-only customer email readiness and human pre-send review.

Never sends emails, contacts a customer, or stores recipient email, phone,
postal address, name, credentials, or card data. Only a fresh READ from the
Square Sandbox Order API may establish that a checkout recipient email exists.
This is NOT proof of ownership/consent nor authorization to send.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import hmac
import re
import sqlite3
import time

from .sandbox_connector import SquareSandboxError
from .sandbox_notifications import SandboxNotificationDrafts
from .sandbox_procurement import SandboxProcurementOps
from .sandbox_reconcile import _fetch_square_sandbox_resource

CUSTOMER_KINDS = frozenset(("customer_order_confirmed", "customer_shipment_notice"))
REVIEW_TTL_SECONDS = 15 * 60  # Sandbox review, NOT authority to send real mail.
ORDER_ID = re.compile(r"^FOOD[0-9a-f]{32}$")
# Deliberately conservative ASCII email parsing, no dynamic send destination.
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


def lookup_masked_recipient(square_order_id: str, *, token: str, opener=None) -> dict:
    """Check Square Sandbox shipment recipient; return ONLY masked email + flag."""
    opts = {"token": token}
    if opener is not None:
        opts["opener"] = opener
    value = _fetch_square_sandbox_resource("/orders/" + square_order_id, **opts)
    order = value.get("order")
    if not isinstance(order, dict) or order.get("id") != square_order_id:
        raise SquareSandboxError("Square Sandbox order ID mismatch")
    fulfillments = order.get("fulfillments")
    if not isinstance(fulfillments, list):
        return {"ready": False, "masked": None}
    found = set()
    for fulfillment in fulfillments:
        if not isinstance(fulfillment, dict) or fulfillment.get("type") != "SHIPMENT":
            continue
        details = fulfillment.get("shipment_details", {})
        recipient = details.get("recipient", {}) if isinstance(details, dict) else {}
        if not isinstance(recipient, dict):
            continue
        email = recipient.get("email_address")
        if not isinstance(email, str) or len(email) > 254 or not EMAIL.fullmatch(email):
            continue
        if ".." in email or email.startswith(".") or "@" not in email:
            continue
        found.add(email.lower())
    if len(found) != 1:
        # Absent or multiple different recipients: never guess the destination.
        return {"ready": False, "masked": None}
    email = found.pop()
    local, domain = email.rsplit("@", 1)
    masked = local[:1] + "***@" + domain[:1] + "***"
    # HMAC key is the server-only Square SANDBOX token; no raw email stored.
    # Token rotation intentionally invalidates prior approvals.
    fingerprint = hmac.new(
        token.encode("utf-8"), email.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    return {"ready": True, "masked": masked, "fingerprint": fingerprint}


def _draft_fingerprint(store, order_id: str, kind: str) -> str:
    """Hash exact message content, including carrier/tracking from Sandbox DB."""
    draft = SandboxNotificationDrafts(store).preview(order_id, kind)
    body = draft["body"]
    if kind == "customer_shipment_notice":
        from .sandbox_tracking import SandboxTrackingJournal
        tracking = SandboxTrackingJournal(store).read(order_id)
        if tracking is None:
            raise ValueError("Shipment tracking is required")
        body = body.replace(
            "配送会社：【運営が確認して入力】",
            "配送会社：" + tracking["carrier_label"]
        ).replace(
            "追跡番号：【運営が確認して入力】",
            "追跡番号：" + tracking["tracking_number"]
        )
    return hashlib.sha256((draft["subject"] + "\\0" + body).encode("utf-8")).hexdigest()


class SandboxCustomerReview:
    def __init__(self, store):
        self.store = store

    def _open(self):
        conn = sqlite3.connect(self.store.db_file, timeout=10, isolation_level=None)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA busy_timeout=10000")
        return conn

    @staticmethod
    def _install(db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS food_sandbox_customer_reviews (
                order_id TEXT NOT NULL,
                kind TEXT NOT NULL CHECK(kind IN
                    ('customer_order_confirmed','customer_shipment_notice')),
                reviewed_at INTEGER NOT NULL,
                contact_fingerprint TEXT,
                content_fingerprint TEXT,
                revoked_at INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (order_id, kind)
            )
        """)
        # Existing test DBs contain 3-column rows: migrate in-place and
        # invalidate those old approvals until the operator reviews again.
        names = {
            column[1] for column in db.execute(
                "PRAGMA table_info(food_sandbox_customer_reviews)"
            )
        }
        for name in ("contact_fingerprint", "content_fingerprint"):
            if name not in names:
                db.execute(
                    "ALTER TABLE food_sandbox_customer_reviews ADD COLUMN " + name + " TEXT"
                )
        if "revoked_at" not in names:
            db.execute(
                "ALTER TABLE food_sandbox_customer_reviews "
                "ADD COLUMN revoked_at INTEGER NOT NULL DEFAULT 0"
            )

    def reviewed(self, order_id: str, kind: str) -> bool:
        if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id) or kind not in CUSTOMER_KINDS:
            return False
        with closing(self._open()) as db:
            exists = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_sandbox_customer_reviews'"
            ).fetchone()
            if not exists:
                return False
            return db.execute(
                "SELECT 1 FROM food_sandbox_customer_reviews "
                "WHERE order_id=? AND kind=?", (order_id, kind)
            ).fetchone() is not None

    def readiness(self, order_id: str, kind: str, *, token: str, opener=None) -> dict:
        if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id) or kind not in CUSTOMER_KINDS:
            raise ValueError("Unsupported Sandbox customer draft")
        snapshot = self.store.paid_order_snapshot(order_id)
        if not snapshot or not snapshot.get("square_order_id") or not snapshot.get("square_payment_id"):
            raise ValueError("Square-verified paid Sandbox order required")
        draft = SandboxNotificationDrafts(self.store).preview(order_id, kind)
        if draft["audience"] != "customer":
            raise ValueError("Customer draft required")
        if kind == "customer_shipment_notice":
            if SandboxProcurementOps(self.store).state(order_id) != "shipped":
                raise ValueError("Sandbox shipment stage required")
            from .sandbox_tracking import SandboxTrackingJournal
            if not SandboxTrackingJournal(self.store).read(order_id):
                return {"ready": False, "masked": None, "reviewed": False,
                        "review_history": self.reviewed(order_id, kind)}
        opts = {"token": token}
        if opener is not None:
            opts["opener"] = opener
        status = lookup_masked_recipient(snapshot["square_order_id"], **opts)
        if not status["ready"]:
            return {"ready": False, "masked": None, "reviewed": False,
                    "review_history": self.reviewed(order_id, kind)}
        content_fingerprint = _draft_fingerprint(self.store, order_id, kind)
        with closing(self._open()) as db:
            cols = {
                c[1] for c in db.execute("PRAGMA table_info(food_sandbox_customer_reviews)")
            }
            old = (db.execute(
                "SELECT contact_fingerprint, content_fingerprint, reviewed_at, revoked_at "
                "FROM food_sandbox_customer_reviews WHERE order_id=? AND kind=?",
                (order_id, kind)
            ).fetchone() if {"contact_fingerprint", "content_fingerprint", "revoked_at"} <= cols
                else None)
        now = int(time.time())
        current = bool(
            old and old["contact_fingerprint"] == status["fingerprint"]
            and old["content_fingerprint"] == content_fingerprint
            and old["revoked_at"] == 0
            and 0 <= now - old["reviewed_at"] < REVIEW_TTL_SECONDS
        )
        return {"ready": True, "masked": status["masked"], "reviewed": current,
                "review_history": old is not None,
                "_fingerprints": (status["fingerprint"], content_fingerprint)}

    def mark_reviewed(self, order_id: str, kind: str, *, token: str, opener=None) -> bool:
        status = self.readiness(order_id, kind, token=token, opener=opener)
        if not status["ready"]:
            raise ValueError("Recipient from Square is not ready for manual review")
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                before = db.execute(
                    "SELECT contact_fingerprint,content_fingerprint,reviewed_at,revoked_at "
                    "FROM food_sandbox_customer_reviews WHERE order_id=? AND kind=?",
                    (order_id, kind)
                ).fetchone()
                now = int(time.time())
                same = bool(
                    before
                    and (before["contact_fingerprint"], before["content_fingerprint"])
                        == status["_fingerprints"]
                    and before["revoked_at"] == 0
                    and 0 <= now - before["reviewed_at"] < REVIEW_TTL_SECONDS
                )
                if not same:
                    db.execute(
                        "INSERT INTO food_sandbox_customer_reviews "
                        "(order_id,kind,reviewed_at,contact_fingerprint,content_fingerprint,revoked_at) "
                        "VALUES (?,?,?,?,?,0) ON CONFLICT(order_id,kind) DO UPDATE SET "
                        "reviewed_at=excluded.reviewed_at,"
                        "contact_fingerprint=excluded.contact_fingerprint,"
                        "content_fingerprint=excluded.content_fingerprint,"
                        "revoked_at=0",
                        (order_id, kind, now, *status["_fingerprints"])
                    )
                db.execute("COMMIT")
                return not same
            except Exception:
                db.execute("ROLLBACK")
                raise

    def revoke_review(self, order_id: str, kind: str) -> bool:
        """Operator-initiated Sandbox revoke: persist history, invalidate approval.

        Authentication, same-origin and CSRF checks are enforced by the route,
        NOT by this persistence helper. Never sends an email.
        """
        if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id) or kind not in CUSTOMER_KINDS:
            raise ValueError("Invalid Sandbox review to revoke")
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                cursor = db.execute(
                    "UPDATE food_sandbox_customer_reviews SET revoked_at=? "
                    "WHERE order_id=? AND kind=? AND revoked_at=0",
                    (int(time.time()), order_id, kind),
                )
                db.execute("COMMIT")
                return cursor.rowcount > 0
            except Exception:
                if db.in_transaction:
                    db.execute("ROLLBACK")
                raise
