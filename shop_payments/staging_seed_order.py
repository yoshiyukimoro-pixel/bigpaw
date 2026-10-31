"""Explicit manual operator CLI to prepare one Square SANDBOX checkout.

This command must be run inside the dedicated staging environment alongside
the same persistent SQLite volume as staging_https_webhook. It does not serve
an HTTP endpoint. It cannot use Square production or BIG PAW production DBs.
Do NOT paste Sandbox checkout URLs into GitHub job logs or public channels.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import uuid

from .retail_catalog import load_sale_catalog
from .sandbox_connector import (
    SandboxOrderStore, SquareSandboxError, create_square_sandbox_payment_link,
)
from .staging_https_webhook import stage_ready

ORDER_ID = re.compile(r"^FOOD[0-9a-f]{32}$")
SKU = re.compile(r"^[AOZC][0-9]{2}$")


def prepare_test_checkout(*, env: dict, db_path: str, order_id: str,
                          sku: str, quantity: int,
                          creator=create_square_sandbox_payment_link) -> dict:
    if not stage_ready(env):
        raise ValueError("Dedicated Sandbox staging is not ready")
    if not ORDER_ID.fullmatch(order_id):
        raise ValueError("Invalid Sandbox order ID")
    if not isinstance(sku, str) or not SKU.fullmatch(sku):
        raise ValueError("Invalid test SKU")
    if type(quantity) is not int or not 1 <= quantity <= 2:
        raise ValueError("Test quantity must be 1 or 2")
    configured_db = env.get("BIGPAW_SHOP_SANDBOX_DB")
    if not configured_db or Path(db_path).resolve() != Path(configured_db).resolve():
        raise ValueError("Not the dedicated staging SQLite database")
    db = Path(configured_db).resolve()
    if not db.parent.is_dir() or db.is_symlink():
        raise ValueError("Unsafe staging DB path")
    catalog = load_sale_catalog()
    if sku not in catalog:
        raise ValueError("Unknown sale product")
    store = SandboxOrderStore(db)
    payload, total = store.add_pending_order(
        order_id=order_id, cart={sku: quantity},
        verified_prices=catalog, shipping_yen=0,
        location_id=env["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
    )
    prior = store.checkout_link_if_exists(order_id)
    if prior:
        return {"order_id": order_id, "url": prior["url"],
                "amount_yen": total, "reused": True, "sandbox": True}
    # Durable, atomic one-shot claim BEFORE any Square request. When the
    # provider times out or the process crashes, the same order stays
    # attempt_unknown for operator reconciliation; never create a second
    # link automatically. This also prevents concurrent CLI invocations
    # racing to produce distinct links for one order.
    store.claim_checkout_link_attempt(order_id)
    link = creator(
        payload, token=env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"],
    )
    store.save_link(order_id, link)
    return {"order_id": order_id, "url": link["url"],
            "amount_yen": total, "reused": False, "sandbox": True}


def main(argv=None, env=None):
    p = argparse.ArgumentParser(description="Prepare one test-only Square Sandbox order")
    p.add_argument("--order-id", help="Reuse FOOD + 32 lower-case hex chars on retry")
    p.add_argument("--sku", default="A02")
    p.add_argument("--qty", type=int, default=1)
    p.add_argument("--confirm-sandbox", action="store_true")
    p.add_argument("--show-test-link", action="store_true",
                   help="Display private Sandbox test-checkout URL in local terminal")
    args = p.parse_args(argv)
    variables = dict(os.environ if env is None else env)
    if not args.confirm_sandbox:
        print("BLOCKED: explicitly confirm isolated Sandbox first", file=sys.stderr)
        return 2
    if not stage_ready(variables):
        print("BLOCKED: dedicated Sandbox staging credentials not ready", file=sys.stderr)
        return 2
    order_id = args.order_id or "FOOD" + uuid.uuid4().hex
    try:
        result = prepare_test_checkout(
            env=variables, db_path=variables.get("BIGPAW_SHOP_SANDBOX_DB", ""),
            order_id=order_id, sku=args.sku, quantity=args.qty,
        )
    except (ValueError, OSError, SquareSandboxError):
        print("SANDBOX_CHECKOUT_UNAVAILABLE: preserve this order ID for review",
              file=sys.stderr)
        print(json.dumps({"order_id": order_id, "sandbox": True}))
        return 1
    if not args.show_test_link:
        result.pop("url")
        result["checkout_link_hidden"] = True
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
