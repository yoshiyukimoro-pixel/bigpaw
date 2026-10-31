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


def _valid_japanese_shipping_recipient(recipient: dict) -> bool:
    """Validate one ship-to recipient; never return or persist personal data.

    Square requires a phone for shipment recipients. For postal shipping to
    Japan, the postcode must contain exactly seven digits (optionally 3-4),
    and the normalized phone must start with domestic zero and have 10/11
    digits. Accept the common +81 international format too.
    """
    if not isinstance(recipient, dict):
        return False
    address = recipient.get("address")
    name = recipient.get("display_name")
    phone = recipient.get("phone_number")
    if (not isinstance(address, dict) or address.get("country") != "JP"
            or not isinstance(name, str) or not 1 <= len(name.strip()) <= 255
            or not isinstance(phone, str) or not 10 <= len(phone) <= 24
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in phone)):
        return False
    line = address.get("address_line_1")
    post = address.get("postal_code")
    # A zip code and street alone do not identify a dispatchable Japanese
    # destination. Require Square's prefecture and city/ward address fields.
    prefecture = address.get("administrative_district_level_1")
    city = address.get("locality")
    if (not isinstance(line, str) or not 1 <= len(line.strip()) <= 200
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in line)
            or not isinstance(prefecture, str)
            or not 1 <= len(prefecture.strip()) <= 100
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in prefecture)
            or not isinstance(city, str)
            or not 1 <= len(city.strip()) <= 100
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in city)
            or not isinstance(post, str)
            or not re.fullmatch(r"[0-9]{3}-?[0-9]{4}", post)):
        return False
    compact = re.sub(r"[\s()\-]", "", phone)
    if compact.startswith("+81"):
        compact = "0" + compact[3:]
    return bool(re.fullmatch(r"0[0-9]{9,10}", compact))


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
    # A shipping-only dog-food order cannot silently choose one recipient
    # among multiple delivery destinations. Keep it in address_review for
    # manual handling whenever Square reports no or ambiguous fulfillments.
    if (isinstance(fulfillments, list) and len(fulfillments) == 1
            and isinstance(fulfillments[0], dict)
            and fulfillments[0].get("type") == "SHIPMENT"):
        for fulfillment in fulfillments:
            if not isinstance(fulfillment, dict) or fulfillment.get("type") != "SHIPMENT":
                continue
            details = fulfillment.get("shipment_details", {})
            if not isinstance(details, dict):
                continue
            recipient = details.get("recipient", {})
            if not isinstance(recipient, dict):
                continue
            if _valid_japanese_shipping_recipient(recipient):
                valid = True
                break
    return {"square_order_id": square_order_id, "shipment_details_complete": valid}


def verify_current_sandbox_payment(*, snapshot: dict, token: str, opener=urlopen) -> dict:
    """Fresh READ-ONLY Square Sandbox Payments + Orders reconciliation.

    Only an operator-provided trusted, previously verified paid-order snapshot
    may be passed. No recipient, address, email or card data is returned. A
    historical paid record alone is never a current status assertion.
    Never calls create-payment, refund, or Square Production endpoints.
    """
    if not isinstance(snapshot, dict) or set(snapshot) != {
        "order_id", "amount_yen", "square_order_id", "square_location_id",
        "square_payment_id", "cart"
    }:
        raise SquareSandboxError("Trusted paid sandbox snapshot required")
    order_id = snapshot["order_id"]
    payment_id = snapshot["square_payment_id"]
    square_order_id = snapshot["square_order_id"]
    location_id = snapshot["square_location_id"]
    amount = snapshot["amount_yen"]
    if (not isinstance(order_id, str)
            or not re.fullmatch(r"FOOD[0-9a-f]{32}", order_id)
            or any(not isinstance(v, str) or not _SQUARE_ID.fullmatch(v)
                   for v in (payment_id, square_order_id, location_id))
            or type(amount) is not int or not 1 <= amount <= 2_000_000):
        raise SquareSandboxError("Invalid private paid snapshot")
    payment = retrieve_verified_sandbox_payment(
        payment_id, token=token, opener=opener
    )
    money = payment.get("amount_money")
    # Square may omit refunded_money while no refunds exist; a present
    # structure must still be valid JPY with an exact zero amount.
    # Omitted optional refunded_money is normal. An explicitly present null,
    # false, empty object, wrong currency, or non-integer value is NOT proof
    # that a completed payment remains unrefunded.
    refund = (payment["refunded_money"] if "refunded_money" in payment
              else {"amount": 0, "currency": "JPY"})
    if (payment.get("status") != "COMPLETED"
            or payment.get("order_id") != square_order_id
            or payment.get("location_id") != location_id
            or not isinstance(money, dict)
            or money.get("currency") != "JPY"
            or type(money.get("amount")) is not int
            or money["amount"] != amount
            or not isinstance(refund, dict)
            or refund.get("currency") != "JPY"
            or type(refund.get("amount")) is not int
            or refund["amount"] != 0):
        raise SquareSandboxError("Sandbox payment no longer verified or is refunded")
    order_data = _fetch_square_sandbox_resource(
        "/orders/" + square_order_id, token=token, opener=opener
    )
    square_order = order_data.get("order")
    total = square_order.get("total_money") if isinstance(square_order, dict) else None
    if (not isinstance(square_order, dict)
            or square_order.get("id") != square_order_id
            or square_order.get("location_id") != location_id
            or square_order.get("state") not in ("OPEN", "COMPLETED")
            or not isinstance(total, dict)
            or total.get("currency") != "JPY"
            or type(total.get("amount")) is not int
            or total["amount"] != amount):
        raise SquareSandboxError("Sandbox order no longer matches verified payment")
    # This is a moment-in-time Sandbox check, not shipping authorization.
    return {"order_id": order_id, "amount_yen": amount,
            "current_payment_verified": True, "unrefunded_verified": True,
            "sandbox_only": True}
