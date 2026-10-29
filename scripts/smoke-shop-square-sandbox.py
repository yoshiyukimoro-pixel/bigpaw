"""Opt-in Square Sandbox API connectivity test. NO payment is collected.

Run manually ONLY via GitHub Actions with its two Sandbox secrets.
A payment *link* is created in Sandbox (not a charged payment).
Do not print tokens, link URLs, payments or any customer information.
Never fall back to Square Production API.
"""
from __future__ import annotations

import os
import secrets
import sys

from shop_payments.retail_catalog import build_shipping_included_square_order
from shop_payments.sandbox_connector import (
    SANDBOX_ENDPOINT,
    SquareSandboxError,
    create_square_sandbox_payment_link,
)


def main(*, env=None, link_creator=create_square_sandbox_payment_link) -> int:
    env = os.environ if env is None else env
    token = str(env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", "")).strip()
    location = str(env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID", "")).strip()
    if not token or not location:
        print("SQUARE_SANDBOX_NOT_CONFIGURED: Set both Sandbox secrets before the manual test.")
        return 2
    if "squareupsandbox.com" not in SANDBOX_ENDPOINT or "connect.squareup.com" in SANDBOX_ENDPOINT:
        print("SQUARE_SANDBOX_SAFETY_BLOCK: Unexpected API host.")
        return 3
    try:
        payload, amount = build_shipping_included_square_order(
            cart={"A02": 1},
            square_location_id=location,
            local_order_id="FOOD" + secrets.token_hex(16),
        )
        if amount != 21450 or len(payload["order"]["line_items"]) != 1:
            raise ValueError("approved tax-included price mismatch")
        tax = payload["order"]["taxes"][0]
        if (tax["type"], tax["scope"], tax["percentage"]) != ("INCLUSIVE", "ORDER", "10"):
            raise ValueError("incorrect Square Japan tax calculation")
        if payload["checkout_options"]["ask_for_shipping_address"] is not True:
            raise ValueError("shipping address missing")
        link = link_creator(payload, token=token)
        if not link.get("url", "").startswith("https://sandbox.square.link/"):
            raise ValueError("response was not a Square Sandbox link")
        if not link.get("square_order_id") or not link.get("square_link_id"):
            raise ValueError("Square response identifiers missing")
    except (SquareSandboxError, ValueError, TypeError, KeyError):
        print("SQUARE_SANDBOX_SMOKE_FAILED: Check Sandbox application, token permissions and Location ID.")
        return 1
    print(
        "SQUARE_SANDBOX_SMOKE_OK: Checkout link created in Sandbox; "
        "1x A02, JPY 21,450 total, delivery included, JP 10% inclusive tax. "
        "No payment was collected; no URL or credentials printed."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
