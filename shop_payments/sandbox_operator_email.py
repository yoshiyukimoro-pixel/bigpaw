"""Opt-in, staging-only delivery of ONE operator food-order email to BIG PAW.

Never touches the production backend. Does not dispatch customer or supplier
messages. Strictly fixed destination info@bigpaw.site, fixed sender, Resend
HTTPS endpoint and explicit Sandbox opt-in + operator confirmation.

Uncertain network outcomes remain 'unknown' and are never auto-retried:
the provider may have accepted the email before the connection dropped.
The persistent reservation prevents duplicate sends even after restart.
'accepted' means Resend accepted the request, NOT inbox delivery.
"""
from __future__ import annotations

import json
import re
import sqlite3
import time
from contextlib import closing
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .sandbox_connector import SandboxOrderStore
from .sandbox_notifications import SandboxNotificationDrafts

OPERATOR_TO = "info@bigpaw.site"
FROM = "BIG PAW <noreply@bigpaw.site>"
API_URL = "https://api.resend.com/emails"
KIND = "operator_new_order"
# Deliberately do not allow real customer or supplier notification delivery yet.
EMAIL_ID = re.compile(r"^[A-Za-z0-9_-]{8,100}$")


class SafeMailError(ValueError):
    pass


def send_resend(*, api_key: str, to: str, subject: str, body: str,
                idempotency_key: str, opener=urlopen) -> str:
    """Returns provider message ID, never prints secrets or network errors."""
    if not api_key or to != OPERATOR_TO or not idempotency_key.startswith(
        "bigpaw-shop-sandbox-operator-new-order/"
    ):
        raise SafeMailError("Unsafe shop mail parameters")
    if not isinstance(subject, str) or not isinstance(body, str):
        raise SafeMailError("Invalid mail content")
    data = json.dumps({
        "from": FROM,
        "to": [OPERATOR_TO],
        "subject": subject,
        "text": body,
    }, ensure_ascii=False).encode("utf-8")
    req = Request(API_URL, data=data, method="POST", headers={
        "Authorization": "Bearer " + api_key,
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Idempotency-Key": idempotency_key,
        "User-Agent": "BIGPAW-Staging-Food-Mail/1.0",
    })
    try:
        with opener(req, timeout=10) as response:
            if response.status not in (200, 201):
                raise SafeMailError("Provider did not accept the request")
            payload = json.loads(response.read(4096))
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        # Ambiguous: an email might have been accepted despite a connection
        # failure. Reserve forever until a separate manual provider audit.
        raise SafeMailError("Provider acceptance not confirmed") from None
    identifier = payload.get("id") if isinstance(payload, dict) else None
    if not isinstance(identifier, str) or not EMAIL_ID.fullmatch(identifier):
        raise SafeMailError("Provider returned no valid mail ID")
    return identifier


EVENTS = frozenset((
    "sent", "delivered", "bounced", "complained", "failed",
    "delivery_delayed", "canceled", "queued", "scheduled",
    "opened", "clicked",
))


def read_resend_delivery(*, api_key: str, provider_id: str, opener=urlopen) -> str:
    """Read-only provider event lookup; recipient and ID must match."""
    if not api_key or not EMAIL_ID.fullmatch(provider_id):
        raise SafeMailError("Missing email status credentials or ID")
    req=Request(API_URL+"/"+provider_id,headers={
        "Authorization": "Bearer "+api_key,
        "Accept": "application/json",
        "User-Agent": "BIGPAW-Staging-Food-Mail-ReadOnly/1.0",
    },method="GET")
    try:
        with opener(req,timeout=10) as result:
            if result.status != 200:
                raise SafeMailError("Provider lookup status unavailable")
            value=json.loads(result.read(8192))
    except (HTTPError,URLError,TimeoutError,OSError,ValueError):
        raise SafeMailError("Provider delivery state unavailable") from None
    if not isinstance(value,dict) or value.get("id")!=provider_id:
        raise SafeMailError("Provider returned another email")
    recipients=value.get("to")
    if not isinstance(recipients,list) or recipients!=[OPERATOR_TO]:
        raise SafeMailError("Provider recipient mismatch")
    event=str(value.get("last_event") or "").lower()
    if event not in EVENTS:
        raise SafeMailError("Unknown provider delivery state")
    return event


class SandboxOperatorEmail:
    def __init__(self, store: SandboxOrderStore):
        self.store = store
        self.drafts = SandboxNotificationDrafts(store)
        with closing(self._open()) as db:
            db.execute("""
                CREATE TABLE IF NOT EXISTS food_operator_email_dispatch (
                  order_id TEXT NOT NULL,
                  kind TEXT NOT NULL,
                  recipient TEXT NOT NULL,
                  status TEXT NOT NULL CHECK (status IN ('reserved','accepted','unknown')),
                  provider_id TEXT,
                  last_event TEXT,
                  created_at INTEGER NOT NULL,
                  updated_at INTEGER NOT NULL,
                  PRIMARY KEY (order_id,kind)
                )
            """)
            columns={c["name"] for c in db.execute(
                "PRAGMA table_info(food_operator_email_dispatch)"
            )}
            if "last_event" not in columns:
                db.execute(
                    "ALTER TABLE food_operator_email_dispatch ADD COLUMN last_event TEXT"
                )

    def _open(self):
        db=sqlite3.connect(self.store.db_file, timeout=10, isolation_level=None)
        db.row_factory=sqlite3.Row
        db.execute("PRAGMA busy_timeout=10000")
        return db

    def history(self) -> list[dict]:
        with closing(self._open()) as db:
            rows=db.execute(
                "SELECT order_id,kind,recipient,status,provider_id,last_event,created_at,updated_at "
                "FROM food_operator_email_dispatch ORDER BY created_at DESC,order_id DESC"
            ).fetchall()
        return [dict(row) for row in rows]

    def send_once(self, order_id: str, *, api_key: str, enabled: bool,
                  confirmed: bool, sender=send_resend) -> dict:
        """Never auto-call. Sending requires both environment AND CLI opt-in."""
        if not enabled or not confirmed or not isinstance(api_key,str) or not api_key:
            raise SafeMailError("Sandbox mail is not explicitly enabled")
        # A real Square-confirmed paid order and its prepared draft are both
        # necessary. Unverified payments have no dispatch pathway.
        draft=self.drafts.preview(order_id,KIND)
        if draft["audience"]!="operator" or draft["status"]!="draft_not_sent":
            raise SafeMailError("Invalid operator draft")
        if not self.store.paid_order_snapshot(order_id):
            raise SafeMailError("Not a verified paid order")
        now=int(time.time())
        with closing(self._open()) as db:
            try:
                db.execute("BEGIN IMMEDIATE")
                previous=db.execute(
                    "SELECT status FROM food_operator_email_dispatch "
                    "WHERE order_id=? AND kind=?", (order_id,KIND)
                ).fetchone()
                if previous:
                    db.execute("COMMIT")
                    return {"order_id":order_id,"recipient":OPERATOR_TO,
                            "status":previous["status"],"new_send":False}
                db.execute(
                    "INSERT INTO food_operator_email_dispatch "
                    "(order_id,kind,recipient,status,created_at,updated_at) "
                    "VALUES (?,?,?,?,?,?)",
                    (order_id,KIND,OPERATOR_TO,"reserved",now,now),
                )
                db.execute("COMMIT")
            except Exception:
                db.execute("ROLLBACK")
                raise
        subject="[Square Sandboxテスト・実注文ではありません] " + draft["subject"]
        message=(
            "【テスト通知・運営用】\n"
            "本メールはBIG PAWドッグフードショップのSandbox動作検証です。\n"
            "実際のお客様からの注文・入金ではありません。\n"
            "トランペッツへ発注しないでください。\n\n"
            + draft["body"]
        )
        key="bigpaw-shop-sandbox-operator-new-order/"+order_id
        try:
            mail_id=sender(api_key=api_key,to=OPERATOR_TO,subject=subject,
                           body=message,idempotency_key=key)
            if not isinstance(mail_id,str) or not EMAIL_ID.fullmatch(mail_id):
                raise SafeMailError("No accepted provider message ID")
            status="accepted"
        except Exception:
            mail_id=None
            status="unknown"  # do not assume failure and auto-retry
        with closing(self._open()) as db:
            db.execute(
                "UPDATE food_operator_email_dispatch SET status=?,provider_id=?,updated_at=? "
                "WHERE order_id=? AND kind=? AND status='reserved'",
                (status,mail_id,int(time.time()),order_id,KIND),
            )
        return {"order_id":order_id,"recipient":OPERATOR_TO,
                "status":status,"new_send":True}

    def refresh_delivery(self, order_id: str, *, api_key: str,
                         reader=read_resend_delivery) -> dict:
        """Read provider status; 'delivered' is mail-server acceptance, not opened inbox."""
        with closing(self._open()) as db:
            row=db.execute(
                "SELECT provider_id,status,last_event FROM food_operator_email_dispatch "
                "WHERE order_id=? AND kind=?",(order_id,KIND)
            ).fetchone()
        if not row or row["status"]!="accepted" or not row["provider_id"]:
            raise SafeMailError("No accepted operator email to check")
        event=reader(api_key=api_key,provider_id=row["provider_id"])
        if event not in EVENTS:
            raise SafeMailError("Unknown email delivery event")
        with closing(self._open()) as db:
            db.execute(
                "UPDATE food_operator_email_dispatch SET last_event=?,updated_at=? "
                "WHERE order_id=? AND kind=? AND status='accepted' AND provider_id=?",
                (event,int(time.time()),order_id,KIND,row["provider_id"]),
            )
        return {
            "order_id":order_id,"recipient":OPERATOR_TO,
            "provider_event":event,"delivered_to_mail_server":event in (
                "delivered","opened","clicked",
            ),"opened_in_mailbox_confirmed":False,
        }
