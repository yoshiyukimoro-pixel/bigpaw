"""Offline-only wiring of the future live food-shop checkout components.

This module is a *test harness* and is NEVER imported by an active HTTP route.
It cannot call Square or create a real payment: the caller MUST supply a
synthetic checkout creator and synthetic Square Orders read adapter, and the
test_mode flag must explicitly be True. No defaults point to the network.

This assembles the pieces that a future approved production endpoint will
need: pricebook cart -> immutable intent -> one-time claimed POST -> response
-> independent Square GET verification -> atomic private ledger binding.

DO NOT turn test_mode into an environment variable or expose this as a
public route. Production still needs owner-approved legal terms, session
binding, rate limits, fraud controls, and explicit launch authorization.
"""
from __future__ import annotations

from collections.abc import Callable

from .live_checkout_intent import LiveCheckoutIntent
from .live_order_ledger import LiveOrderBlocked


def exercise_checkout_components(
    *, intent: LiveCheckoutIntent,
    trusted_order_id: str, trusted_location_id: str, trusted_cart: dict,
    fake_creator: Callable | None = None,
    fake_square_order_get: Callable | None = None,
    test_mode: bool = False,
) -> dict:
    """Execute the assembled flow against *injected* offline fakes only.

    Starts with a fully trusted server order ID and server-priced cart.
    Doesn't accept a buyer's payment amount. No automatic retry on failure.
    On an uncertain POST result, leaves the durable record in attempt_unknown.
    Returns the fake link URL ONLY after independent GET and atomic ledger
    insert, never on a partially committed transaction.
    """
    if (test_mode is not True or not isinstance(intent, LiveCheckoutIntent)
            or not callable(fake_creator) or not callable(fake_square_order_get)):
        raise LiveOrderBlocked("Offline injected test checkout only; live route disabled")
    planned = intent.prepare(
        order_id=trusted_order_id,
        location_id=trusted_location_id,
        cart=trusted_cart,
    )
    if planned["state"] != "planned":
        raise LiveOrderBlocked(
            "Already attempted checkout; manual reconciliation required"
        )
    once = intent.begin_attempt(order_id=trusted_order_id)
    # The creator receives only the immutable server-generated payload, not
    # user-provided card data or prices. A crash or connection failure leaves
    # the attempt marked unknown, never silently retried.
    link = fake_creator(once["server_only_payload"])
    result = intent.bind_square_result(
        order_id=trusted_order_id,
        link=link,
        api_key="FAKE-KEY-SQUARE-GET-ONLY-NOT-REAL-123456",
        opener=fake_square_order_get,
    )
    if result != {"state": "link_bound", "new_binding": True}:
        raise LiveOrderBlocked("Square response not newly bound")
    return {
        "checkout_url": link["url"],
        "order_id": trusted_order_id,
        "amount_yen": planned["amount_yen"],
        "shipping_yen": 0,
        "test_only": True,
        "real_payments": False,
    }
