"""Future customer transactional email transport, explicitly NOT wired to BIG PAW.

This module is designed for a separately approved live application. No staging
route imports it, no background worker invokes it, and its live guard defaults
to DENY. It requires a verified, freshly prepared order message from an
independent LIVE Square implementation (the current preflight is SANDBOX and
must NOT be used for real customer delivery).

Resend idempotency keys last only 24 hours; persistent SQLite reservation
before network send prevents a crash, timeout, or later retry from sending the
same order notification twice. A disputed outcome needs manual audit, NEVER
automatic retry. SQL stores no name, email, address, message, API credential.
"""
from __future__ import annotations

from contextlib import closing
import json
import re
import sqlite3
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://api.resend.com/emails"
FROM = "BIG PAW <noreply@bigpaw.site>"
REPLY_TO = "info@bigpaw.site"
KIND = frozenset(("customer_order_confirmed", "customer_shipment_notice"))
ORDER = re.compile(r"^FOOD[0-9a-f]{32}$")
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")
RECEIPT = re.compile(r"^[A-Za-z0-9_-]{8,100}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class CustomerMailBlocked(ValueError):
    pass


def live_gate(env: dict) -> bool:
    """Requires *several* independent live, operator-approved checks.

    The present Sandbox container can NEVER pass this gate. This is NOT an
    approval mechanism: the final live service must also enforce legal,
    recipient and identity checks before invoking this sender.
    """
    if not isinstance(env, dict):
        return False
    return (
        env.get("BIGPAW_ENV") == "live"
        and env.get("BIGPAW_SHOP_CUSTOMER_EMAIL_ENABLED") == "1"
        and env.get("BIGPAW_SHOP_PUBLIC_LIVE_ENABLED") == "1"
        and env.get("BIGPAW_SHOP_OWNER_LAUNCH_APPROVED") == "1"
        and env.get("BIGPAW_SHOP_STAGING_ISOLATED") != "1"
        and env.get("BIGPAW_SHOP_STAGE_PREVIEW_ENABLED") != "1"
    )


def _safe_message(prepared: dict):
    if not isinstance(prepared, dict) or prepared.get("prepared_only") is not True:
        raise CustomerMailBlocked("Fresh, authorized live payment verification required")
    order_id = prepared.get("order_id")
    kind = prepared.get("kind")
    dest = prepared.get("to")
    digest = prepared.get("snapshot_digest")
    subject = prepared.get("subject")
    body = prepared.get("body")
    if not isinstance(order_id, str) or not ORDER.fullmatch(order_id):
        raise CustomerMailBlocked("Invalid order reference")
    if kind not in KIND:
        raise CustomerMailBlocked("Invalid transactional notification kind")
    if (not isinstance(dest, str) or len(dest) > 254 or not EMAIL.fullmatch(dest)
            or ".." in dest or dest.startswith(".")):
        raise CustomerMailBlocked("Ambiguous customer recipient")
    if not isinstance(digest, str) or not SHA256.fullmatch(digest):
        raise CustomerMailBlocked("Invalid approved snapshot digest")
    if not isinstance(subject, str) or not 1 <= len(subject) <= 180 or "\n" in subject or "\r" in subject:
        raise CustomerMailBlocked("Invalid message subject")
    if not isinstance(body, str) or not 1 <= len(body.encode("utf-8")) <= 30_000:
        raise CustomerMailBlocked("Invalid message body")
    if "[運営が確認して入力]" in body or "【運営が確認して入力】" in body:
        raise CustomerMailBlocked("Unfilled shipment template")
    if prepared.get("live_square_verified") is not True:
        # Sandbox preflight returns no such marker, intentionally.
        raise CustomerMailBlocked("Live Square verification missing")
    return (order_id, kind, dest, digest, subject, body)


def resend_customer(*, api_key, recipient, subject, body, key, opener=urlopen):
    """Real provider adapter. MUST NOT be called on Sandbox or by HTTP routes."""
    if not isinstance(api_key, str) or len(api_key) < 20:
        raise CustomerMailBlocked("No approved email provider credentials")
    if not isinstance(key, str) or not 1 <= len(key) <= 256:
        raise CustomerMailBlocked("Invalid delivery key")
    # Validate using the same path as the durable delivery journal.
    if not isinstance(recipient, str) or not EMAIL.fullmatch(recipient):
        raise CustomerMailBlocked("Invalid recipient")
    payload = json.dumps({
        "from": FROM, "to": [recipient], "reply_to": REPLY_TO,
        "subject": subject, "text": body,
    }, ensure_ascii=False).encode("utf-8")
    req = Request(ENDPOINT, data=payload, method="POST", headers={
        "Authorization": "Bearer " + api_key,
        "Idempotency-Key": key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "BIGPAW-Transactional-Mail/1.0",
    })
    try:
        with opener(req, timeout=10) as resp:
            if resp.status not in (200, 201):
                raise CustomerMailBlocked("Provider response not accepted")
            result = json.loads(resp.read(4096))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        # Provider may have received it: no retry can be assumed safe.
        raise CustomerMailBlocked("Provider acceptance unconfirmed") from None
    provider_id = result.get("id") if isinstance(result, dict) else None
    if not isinstance(provider_id, str) or not RECEIPT.fullmatch(provider_id):
        raise CustomerMailBlocked("Provider receipt invalid")
    return provider_id


class CustomerEmailJournal:
    def __init__(self, db_file):
        self.db_file = db_file

    def _open(self):
        db = sqlite3.connect(self.db_file, timeout=10, isolation_level=None)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    @staticmethod
    def _install(db):
        db.execute("""
            CREATE TABLE IF NOT EXISTS food_customer_email_delivery (
                order_id TEXT NOT NULL,
                kind TEXT NOT NULL,
                snapshot_digest TEXT NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('reserved','accepted','unknown')),
                provider_id TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL,
                PRIMARY KEY(order_id,kind)
            )
        """)

    def history(self, order_id, kind):
        if not isinstance(order_id,str) or not ORDER.fullmatch(order_id) or kind not in KIND:
            return None
        with closing(self._open()) as db:
            if db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' "
                "AND name='food_customer_email_delivery'"
            ).fetchone() is None:
                return None
            row = db.execute(
                "SELECT status,provider_id,created_at,updated_at "
                "FROM food_customer_email_delivery WHERE order_id=? AND kind=?",
                (order_id,kind)
            ).fetchone()
        return dict(row) if row else None

    def send_once(self, prepared, *, env=None, api_key=None,
                  confirmed=False, sender=resend_customer):
        """One irreversible reservation then one attempted provider operation.

        A caller is not allowed to supply an unapproved Sandbox preflight.
        Never returns recipient, subject, body or API credentials.
        """
        if not confirmed or not live_gate(env):
            raise CustomerMailBlocked("Customer delivery is NOT enabled")
        order_id, kind, dest, digest, subject, body = _safe_message(prepared)
        if not isinstance(api_key, str) or len(api_key) < 20:
            raise CustomerMailBlocked("Missing provider key")
        now = int(time.time())
        with closing(self._open()) as db:
            self._install(db)
            try:
                db.execute("BEGIN IMMEDIATE")
                previous = db.execute(
                    "SELECT snapshot_digest,status FROM food_customer_email_delivery "
                    "WHERE order_id=? AND kind=?", (order_id,kind)
                ).fetchone()
                if previous:
                    if previous["snapshot_digest"] != digest:
                        raise CustomerMailBlocked("Message changed after reserved send")
                    db.execute("COMMIT")
                    return {"status":previous["status"],"new_send":False,"customer_contacted":None}
                db.execute(
                    "INSERT INTO food_customer_email_delivery "
                    "(order_id,kind,snapshot_digest,status,created_at,updated_at) "
                    "VALUES (?,?,?,'reserved',?,?)",
                    (order_id,kind,digest,now,now)
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise

        # Idempotency protects against 24h in provider, but our database
        # prevents even a years-later duplicate or any ambiguous retry.
        key = "bigpaw-shop-customer/v1/" + order_id + "/" + kind
        try:
            message_id = sender(api_key=api_key,recipient=dest,
                                subject=subject,body=body,key=key)
            if not isinstance(message_id,str) or not RECEIPT.fullmatch(message_id):
                raise CustomerMailBlocked("Invalid provider receipt")
            state = "accepted"
        except Exception:
            state = "unknown"
            message_id = None
        with closing(self._open()) as db:
            db.execute(
                "UPDATE food_customer_email_delivery "
                "SET status=?,provider_id=?,updated_at=? "
                "WHERE order_id=? AND kind=? AND status='reserved'",
                (state,message_id,int(time.time()),order_id,kind)
            )
        return {"status":state,"new_send":True,"customer_contacted":None}
