"""OFFLINE-INTEGRATION-ONLY Square PRODUCTION payment event intake.

This is an *unwired library*, not an HTTP route or active webhook receiver.
Never run against real credentials until the owner approves legal/checkout
terms, the Square merchant, and the separate live service + webhook endpoint.
No payment link, charge, refund, email or shipment is created here.

Order is ALWAYS resolved from the previously registered private journal using
Square's signed order and location IDs. Every reported payment is independently
re-fetched by the trusted Square production Payments AND Orders GET verifier.
An event is a hint, NOT evidence that money was received. Duplicate events
only yield the journal's existing idempotent paid status.

The future authenticated server endpoint must enforce an exact HTTPS
notification URL, raw request body, bounded Content-Length, event type and
additional HTTP / operational checks. Do not expose this helper to the
untrusted browser and never copy real customer data into logs.
"""
from __future__ import annotations

import hashlib
import re

from .live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from .square_checkout import verify_square_webhook

_EVENT_ID = re.compile(r"^[A-Za-z0-9_-]{8,192}$")
_SQUARE_ID = re.compile(r"^[A-Za-z0-9_-]{8,192}$")
_TYPES = frozenset({"payment.created", "payment.updated"})


def record_verified_live_payment_event(
    *, ledger: LiveOrderLedger, raw_body: bytes, signature_header: str,
    signature_key: str, notification_url: str, api_key: str,
    opener=None, verifier=None,
) -> dict:
    """Signed event -> existing order -> fresh Square GET -> idempotent paid.

    Does NOT expose payment or buyer identifiers in result. Unknown/unmatched
    payment or an unsafe/malformed event fails closed; nonpayment events are
    ignored and never query Square or write journal state. The caller decides
    webhook HTTP semantics; this function sends no HTTP response.
    """
    if not isinstance(ledger, LiveOrderLedger):
        raise LiveOrderBlocked("Trusted live order ledger required")
    if not isinstance(notification_url, str) or not notification_url.startswith("https://"):
        raise LiveOrderBlocked("Exact approved Square notification URL required")
    if not isinstance(api_key, str) or not api_key.strip():
        raise LiveOrderBlocked("Square production read credential missing")
    if not isinstance(raw_body, bytes) or not 1 <= len(raw_body) <= 256_000:
        raise LiveOrderBlocked("Invalid signed notification body")
    event = verify_square_webhook(
        raw_body=raw_body,
        signature_header=signature_header,
        signature_key=signature_key,
        notification_url=notification_url,
    )
    event_id = event.get("event_id")
    if not isinstance(event_id, str) or not _EVENT_ID.fullmatch(event_id):
        raise LiveOrderBlocked("Invalid Square event identity")
    if event.get("type") not in _TYPES:
        return {"state": "ignored", "new_transition": False}
    data = event.get("data")
    obj = data.get("object") if isinstance(data, dict) else None
    pay = obj.get("payment") if isinstance(obj, dict) else None
    if not isinstance(pay, dict):
        raise LiveOrderBlocked("Square signed notification missing Payment")

    payment_id, square_order_id, location_id = (
        pay.get("id"), pay.get("order_id"), pay.get("location_id")
    )
    if any(not isinstance(v, str) or not _SQUARE_ID.fullmatch(v)
           for v in (payment_id, square_order_id, location_id)):
        raise LiveOrderBlocked("Incomplete Square signed Payment identity")
    if pay.get("status") != "COMPLETED":
        return {"state": "awaiting_square", "new_transition": False}
    money = pay.get("amount_money")
    if (not isinstance(money, dict)
            or money.get("currency") != "JPY"
            or type(money.get("amount")) is not int
            or money["amount"] <= 0):
        raise LiveOrderBlocked("Invalid signed JPY payment amount")

    # No caller-provided local order ID or total: both originate from the DB.
    order_id = ledger.order_id_for_square_order(square_order_id, location_id)
    private = ledger.checkout_payment_match(order_id)
    if private["amount_yen"] != money["amount"]:
        raise LiveOrderBlocked("Signed amount differs from saved checkout")

    fingerprint = hashlib.sha256(raw_body).hexdigest()
    ledger.assert_signed_event_identity(
        event_id=event_id, fingerprint=fingerprint
    )
    # Fresh Square read MUST confirm paid, unrefunded, JPY total, store/location
    # and complete shipment before a single durable transition is recorded.
    result = ledger.reconcile_payment(
        order_id=order_id, payment_id=payment_id, api_key=api_key,
        **({"opener": opener} if opener is not None else {}),
        **({"verifier": verifier} if verifier is not None else {}),
    )
    # Record the signed event only AFTER the independent, fresh Square GET
    # has succeeded. Unknown/unsigned/refunded events never enter the journal.
    # A crash between paid transition and this write can be safely recovered
    # by receiving the same event again (with another fresh GET).
    ledger.record_signed_payment_event(
        event_id=event_id, fingerprint=fingerprint,
        order_id=order_id, payment_id=payment_id,
    )
    if result["new_transition"] is False:
        # Historic paid record is NOT proof the payment remains unrefunded.
        # The duplicate was verified against Square just now but doesn't
        # produce a second new-paid business transition.
        return {"state": "already_recorded", "new_transition": False}
    return result
