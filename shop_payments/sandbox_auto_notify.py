"""Post-commit operator mail bridge for verified Square *Sandbox* payments.

Only a dedicated isolated Sandbox preview or staging webhook may call this. The Square webhook has
already passed signature verification AND an independent Square Payments API
reconciliation in SandboxOrderStore.accept_webhook before this function runs.

No email by default. No customer/supplier mail, no production credentials,
no card/address data and no automatic retry after uncertain send results.
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
from contextlib import closing

from .sandbox_runtime_guard import is_allowed_sandbox_runtime
from .sandbox_connector import SandboxOrderStore
from .sandbox_operator_email import (
    SandboxOperatorEmail, SafeMailError, send_resend,
)

SQUARE_REFERENCE = re.compile(r"^[A-Za-z0-9_-]{8,192}$")
API_KEY_FORMAT = re.compile(r"^re_[A-Za-z0-9_-]{8,256}$")


def _opted_in(env: dict) -> bool:
    """Fail closed unless explicitly running the isolated Sandbox preview."""
    return (
        env.get("BIGPAW_ENV") == "sandbox"
        and env.get("BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED") == "1"
        and env.get("BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED") == "1"
        and is_allowed_sandbox_runtime(env)
    )





def maybe_notify_verified_payment(
    store: SandboxOrderStore, *, webhook_status: str, raw_body: bytes,
    env: dict | None = None, sender=send_resend,
) -> str:
    """Dispatch exactly one operator test email after a NEW verified paid event.

    Returns only sanitized outcome labels; caller must never respond with
    provider IDs, credentials or order content. All notifications are Sandbox
    samples marked NOT a real order. Only 'paid' (not duplicates) can dispatch.
    """
    if webhook_status != "paid":
        return "not_newly_paid"
    env = os.environ if env is None else env
    if not _opted_in(env):
        return "disabled"
    key = env.get("RESEND_API_KEY", "")
    if not isinstance(key, str) or not API_KEY_FORMAT.fullmatch(key):
        return "missing_send_key"
    try:
        payload = json.loads(raw_body)
        payment = payload["data"]["object"]["payment"]
        square_order_id = payment["order_id"]
        payment_id = payment["id"]
        if not (isinstance(square_order_id, str)
                and SQUARE_REFERENCE.fullmatch(square_order_id)
                and isinstance(payment_id, str)
                and SQUARE_REFERENCE.fullmatch(payment_id)):
            return "unmatched"
        # Event content is not authorization: match the *committed* verified
        # payment and Square order IDs from the local paid journal.
        with closing(sqlite3.connect(store.db_file, timeout=10)) as db:
            rows = db.execute(
                "SELECT order_id FROM orders WHERE square_order_id=? "
                "AND square_payment_id=? AND state='paid'",
                (square_order_id, payment_id),
            ).fetchall()
        if len(rows) != 1:
            return "unmatched"
        order_id = rows[0][0]
        result = SandboxOperatorEmail(store).send_once(
            order_id, api_key=key, enabled=True, confirmed=True,
            sender=sender,
        )
        if not result.get("new_send"):
            return "already_handled"
        return "accepted" if result["status"] == "accepted" else "unknown"
    except (ValueError, KeyError, TypeError, sqlite3.Error, OSError, SafeMailError):
        return "unavailable"
