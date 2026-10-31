"""Explicit one-time delivery of a *previously verified* Sandbox order alert.

For the pre-existing bigpaw-test service only. Recovers the verified paid
order from its private SQLite volume after the Webhook was processed with
email disabled. Unlike a new webhook this has NO external payment lookup:
the journal and the operator draft were already committed after Square API
confirmation by SandboxOrderStore.accept_webhook. NEVER run in production.
"""
from __future__ import annotations

import re

from .sandbox_runtime_guard import (
    EXISTING_TEST_ENVIRONMENT, EXISTING_TEST_SERVICE, LEGACY_BIGPAW_PROJECT,
)
from .sandbox_connector import SandboxOrderStore
from .sandbox_operator_email import SandboxOperatorEmail, SafeMailError, send_resend
from .staging_seed_order import ORDER_ID

_KEY = re.compile(r"^re_[A-Za-z0-9_-]{8,256}$")


def maybe_send_verified_test_order(env: dict, *, sender=send_resend,
                                   output=print) -> str:
    """Return only sanitized status. Never retry on ambiguous send responses."""
    if env.get("BIGPAW_SHOP_SANDBOX_PAID_MAIL_ONCE_ENABLED") != "1":
        return "disabled"
    if (env.get("BIGPAW_ENV") != "sandbox"
            or env.get("BIGPAW_SHOP_STAGING_ISOLATED") != "1"
            or env.get("RAILWAY_PROJECT_ID") != LEGACY_BIGPAW_PROJECT
            or env.get("RAILWAY_ENVIRONMENT_ID") != EXISTING_TEST_ENVIRONMENT
            or env.get("RAILWAY_SERVICE_ID") != EXISTING_TEST_SERVICE
            or env.get("BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID") != LEGACY_BIGPAW_PROJECT
            or env.get("BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED") != "1"):
        output("SHOP_SANDBOX_PAID_MAIL=BLOCKED_WRONG_RUNTIME")
        return "blocked"
    key = env.get("RESEND_API_KEY", "")
    if not isinstance(key, str) or not _KEY.fullmatch(key):
        output("SHOP_SANDBOX_PAID_MAIL=BLOCKED_MISSING_KEY")
        return "blocked"
    order_id = env.get("BIGPAW_SHOP_SANDBOX_SEED_ORDER_ID", "")
    db = env.get("BIGPAW_SHOP_SANDBOX_DB", "")
    if not isinstance(order_id, str) or not ORDER_ID.fullmatch(order_id) or not db:
        output("SHOP_SANDBOX_PAID_MAIL=BLOCKED_ORDER_CONFIG")
        return "blocked"
    try:
        store = SandboxOrderStore(db)
        if store.status(order_id) != "paid" or not store.paid_order_snapshot(order_id):
            output("SHOP_SANDBOX_PAID_MAIL=NOT_VERIFIED_PAID")
            return "not_paid"
        mail = SandboxOperatorEmail(store).send_once(
            order_id, api_key=key, enabled=True, confirmed=True, sender=sender,
        )
    except (OSError, ValueError, KeyError, SafeMailError):
        output("SHOP_SANDBOX_PAID_MAIL=CHECK_REQUIRED")
        return "unavailable"
    if not mail["new_send"]:
        output("SHOP_SANDBOX_PAID_MAIL=ALREADY_HANDLED")
        return "already_handled"
    if mail["status"] == "accepted":
        output("SHOP_SANDBOX_PAID_MAIL=ACCEPTED_DELIVERY_UNVERIFIED")
        return "accepted"
    output("SHOP_SANDBOX_PAID_MAIL=UNKNOWN_NO_RETRY")
    return "unknown"
