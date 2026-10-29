"""Read-only Square *Sandbox* verification before acknowledging a food payment.

Never fetches a caller-chosen URL, uses Production credentials or stores PII.
The checkout link webhook is an event hint, not proof that money was received.
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .sandbox_connector import SquareSandboxError, SQUARE_VERSION

_API_BASE = "https://connect.squareupsandbox.com/v2"
_SQUARE_ID = re.compile(r"^[A-Za-z0-9_-]{8,192}$")


def _fetch_square_sandbox_resource(path: str, *, token: str, opener=urlopen) -> dict:
    if not isinstance(token, str) or not token.strip():
        raise SquareSandboxError("Sandbox token missing")
    if not (path.startswith("/payments/") or path.startswith("/orders/")):
        raise SquareSandboxError("Unsupported sandbox read path")
    identifier = path.rsplit("/", 1)[-1]
    if not _SQUARE_ID.fullmatch(identifier):
        raise SquareSandboxError("Invalid Square ID")
    request = Request(
        _API_BASE + path,
        headers={
            "Authorization": "Bearer " + token.strip(),
            "Square-Version": SQUARE_VERSION,
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with opener(request, timeout=10) as response:
            if getattr(response, "status", 200) != 200:
                raise SquareSandboxError("Square Sandbox status was not OK")
            payload = json.loads(response.read(262144))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        # Avoid logging credentials and Square's response body, which can include PII.
        raise SquareSandboxError("Square Sandbox read or verification unavailable") from None
    if not isinstance(payload, dict):
        raise SquareSandboxError("Malformed Square Sandbox response")
    return payload


def retrieve_verified_sandbox_payment(
    payment_id: str, *, token: str, opener=urlopen
) -> dict:
    """Get a fresh Payment; reject mismatched IDs, return the Payment object."""
    if not isinstance(payment_id, str) or not _SQUARE_ID.fullmatch(payment_id):
        raise SquareSandboxError("Invalid Square payment ID")
    data = _fetch_square_sandbox_resource("/payments/" + payment_id, token=token, opener=opener)
    pay = data.get("payment")
    if not isinstance(pay, dict) or pay.get("id") != payment_id:
        raise SquareSandboxError("Square Sandbox payment ID mismatch")
    return pay


def retrieve_sandbox_shipment_status(
    square_order_id: str, *, token: str, opener=urlopen
) -> dict:
    """Read shipping validation for operator workflow without returning customer PII.

    Actual shipping address/recipient can be displayed in a future operator-only
    authenticated interface. These checks do not authorize order fulfillment.
    """
    if not isinstance(square_order_id, str) or not _SQUARE_ID.fullmatch(square_order_id):
        raise SquareSandboxError("Invalid Square order ID")
    data = _fetch_square_sandbox_resource("/orders/" + square_order_id, token=token, opener=opener)
    order = data.get("order")
    if not isinstance(order, dict) or order.get("id") != square_order_id:
        raise SquareSandboxError("Square Sandbox order ID mismatch")
    fulfillments = order.get("fulfillments")
    valid = False
    if isinstance(fulfillments, list):
        for fulfillment in fulfillments:
            if not isinstance(fulfillment, dict) or fulfillment.get("type") != "SHIPMENT":
                continue
            details = fulfillment.get("shipment_details", {})
            if not isinstance(details, dict):
                continue
            recipient = details.get("recipient", {})
            if not isinstance(recipient, dict):
                continue
            address = recipient.get("address", {})
            if not isinstance(address, dict):
                continue
            if (
                address.get("country") == "JP"
                and isinstance(address.get("address_line_1"), str)
                and bool(address["address_line_1"].strip())
                and isinstance(address.get("postal_code"), str)
                and bool(address["postal_code"].strip())
                and isinstance(recipient.get("display_name"), str)
                and bool(recipient["display_name"].strip())
            ):
                valid = True
                break
    return {"square_order_id": square_order_id, "shipment_details_complete": valid}
