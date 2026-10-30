"""Prepare at most one explicitly opted-in payment link for Square SANDBOX.

A sandbox payment link is not a charge. This runs only during controlled
bigpaw-test startup and never exposes a public checkout-creation endpoint.
Square token/IDs and user data must not be logged.
"""
from __future__ import annotations

import re

from .sandbox_connector import SquareSandboxError
from .sandbox_runtime_guard import (
    EXISTING_TEST_ENVIRONMENT, EXISTING_TEST_SERVICE, LEGACY_BIGPAW_PROJECT
)

_ORDER = re.compile(r"^FOOD[0-9a-f]{32}$")
_TEST_SKU = "A02"


def create_enabled_test_link(env: dict, *, creator=None, output=print) -> str:
    """Return 'disabled', 'blocked', 'created', 'reused', 'already_paid' or 'failed'.

    Only bigpaw-test (exact environment/service identity) may perform a real
    sandbox API request. The operator enables one fixed order ID explicitly.
    The idempotency key and persisted SQLite allow safe restart/retry.
    """
    if env.get("BIGPAW_SHOP_SANDBOX_SEED_ENABLED") != "1":
        return "disabled"
    if (
        env.get("RAILWAY_PROJECT_ID") != LEGACY_BIGPAW_PROJECT
        or env.get("RAILWAY_ENVIRONMENT_ID") != EXISTING_TEST_ENVIRONMENT
        or env.get("RAILWAY_SERVICE_ID") != EXISTING_TEST_SERVICE
    ):
        output("SHOP_SANDBOX_SEED=BLOCKED_INVALID_SERVICE")
        return "blocked"
    order_id = env.get("BIGPAW_SHOP_SANDBOX_SEED_ORDER_ID", "")
    if not isinstance(order_id, str) or not _ORDER.fullmatch(order_id):
        output("SHOP_SANDBOX_SEED=BLOCKED_INVALID_ORDER_ID")
        return "blocked"
    from .staging_https_webhook import stage_ready
    if not stage_ready(env):
        output("SHOP_SANDBOX_SEED=BLOCKED_NO_SQUARE_CONFIG")
        return "blocked"
    # Read only our explicitly allowed test order. Do not print payment IDs,
    # customer fields or private credentials. This confirms the durable journal
    # after a real Sandbox webhook, not merely an HTTP 200 receipt.
    from .sandbox_connector import SandboxOrderStore
    try:
        state = SandboxOrderStore(env["BIGPAW_SHOP_SANDBOX_DB"]).status(order_id)
    except (OSError, ValueError):
        output("SHOP_SANDBOX_ORDER_STATUS=UNAVAILABLE")
        return "failed"
    if state not in ("not_found", "created", "payment_pending", "paid"):
        output("SHOP_SANDBOX_ORDER_STATUS=UNEXPECTED")
        return "blocked"
    output("SHOP_SANDBOX_ORDER_STATUS=" + state.upper())
    if state == "paid":
        # A previously completed test checkout must never be created again.
        output("SHOP_SANDBOX_SEED=ALREADY_PAID_NO_NEW_CHECKOUT")
        return "already_paid"
    from .staging_seed_order import prepare_test_checkout
    try:
        options = dict(
            env=env, db_path=env["BIGPAW_SHOP_SANDBOX_DB"],
            order_id=order_id, sku=_TEST_SKU, quantity=1,
        )
        if creator is not None:
            options["creator"] = creator
        result = prepare_test_checkout(**options)
    except (ValueError, OSError, SquareSandboxError, KeyError):
        output("SHOP_SANDBOX_SEED=FAILED_CHECK_SANDBOX_SETUP")
        return "failed"
    # Sandbox-only payment URL. No bearer token or personal/payment data.
    # Only accessible in Railway's authenticated service logs.
    output(
        "SHOP_SANDBOX_SEED=" + ("REUSED" if result["reused"] else "CREATED")
        + " order=" + order_id
        + " price_yen=" + str(result["amount_yen"])
        + " checkout=" + result["url"]
    )
    return "reused" if result["reused"] else "created"
