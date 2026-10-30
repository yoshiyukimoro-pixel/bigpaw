"""Future Square PRODUCTION payment + shipment READ-ONLY verifier.

NOT imported or invoked by the current BIG PAW site, sandbox service,
checkout flow, or email route. No production credentials exist here.
This code must be wired only after owner approves real merchant account,
refund/return rules, legal disclosures and production webhooks.

Queries only fixed Square Production GET URLs; rejects mismatched price, order,
location, currency, refund, shipping address, and ambiguous buyer contact.
Returns a short-lived in-memory recipient email; never persists PII.
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .sandbox_connector import SQUARE_VERSION

ENDPOINT = "https://connect.squareup.com/v2"
ID = re.compile(r"^[A-Za-z0-9_-]{8,192}$")
EMAIL = re.compile(r"^[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+$")


class LiveSquareNotVerified(ValueError):
    pass


def _square_get(resource, identifier, *, api_key, opener=urlopen):
    if resource not in ("payments", "orders"):
        raise LiveSquareNotVerified("Unsupported Square resource")
    if not isinstance(identifier, str) or not ID.fullmatch(identifier):
        raise LiveSquareNotVerified("Invalid Square identifier")
    if not isinstance(api_key, str) or not api_key.strip():
        raise LiveSquareNotVerified("No live Square authentication")
    req = Request(
        ENDPOINT + "/" + resource + "/" + identifier,
        headers={
            "Authorization": "Bearer " + api_key,
            "Square-Version": SQUARE_VERSION,
            "Accept": "application/json",
        }, method="GET"
    )
    try:
        with opener(req, timeout=10) as response:
            if getattr(response, "status", 200) != 200:
                raise LiveSquareNotVerified("Square production verification unavailable")
            raw = response.read(262145)
            if len(raw) > 262144:
                raise LiveSquareNotVerified("Oversize Square response")
            payload = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        raise LiveSquareNotVerified("Square production read unavailable") from None
    if not isinstance(payload, dict):
        raise LiveSquareNotVerified("Invalid Square production payload")
    return payload


def verify_paid_live_shipment(*, payment_id, square_order_id, location_id,
                              amount_yen, api_key, opener=urlopen):
    """Validate real, independently recorded Square payment and shipping.

    Caller must separately ensure the expected order/amount/location came from
    a secure, non-browser controlled *live* database journal. Never accept
    totals supplied by an end user's client. This is NOT a webhook handler.
    """
    if any(not isinstance(x, str) or not ID.fullmatch(x)
           for x in (payment_id, square_order_id, location_id)):
        raise LiveSquareNotVerified("Missing expected live Square identifiers")
    if type(amount_yen) is not int or not 1 <= amount_yen <= 5_000_000:
        raise LiveSquareNotVerified("Invalid server-side order total")
    data = _square_get("payments", payment_id, api_key=api_key, opener=opener)
    payment = data.get("payment")
    if not isinstance(payment, dict) or payment.get("id") != payment_id:
        raise LiveSquareNotVerified("Payment ID mismatch")
    money = payment.get("amount_money")
    # Square may omit refunded_money on a never-refunded payment. A PRESENT
    # value of null, {}, false or otherwise malformed is ambiguous and must
    # not be treated as the same trusted zero-JPY refund amount.
    refunded = (payment["refunded_money"] if "refunded_money" in payment
                else {"amount": 0, "currency": "JPY"})
    if (payment.get("status") != "COMPLETED"
        or payment.get("order_id") != square_order_id
        or payment.get("location_id") != location_id
        or not isinstance(money, dict)
        or money.get("currency") != "JPY"
        or type(money.get("amount")) is not int
        or money["amount"] != amount_yen
        or not isinstance(refunded, dict)
        or refunded.get("currency") != "JPY"
        or type(refunded.get("amount")) is not int
        or refunded["amount"] != 0):
        raise LiveSquareNotVerified("Live Square payment not fully valid")

    data = _square_get("orders", square_order_id, api_key=api_key, opener=opener)
    order = data.get("order")
    if (not isinstance(order, dict) or
        order.get("id") != square_order_id or
        order.get("location_id") != location_id):
        raise LiveSquareNotVerified("Order ID or location mismatch")
    # This payment-link shop is shipment-only. No pickup or digital fulfillment.
    if order.get("state") not in ("OPEN", "COMPLETED"):
        raise LiveSquareNotVerified("Square order not payable/fulfilled")
    total = order.get("total_money")
    if (not isinstance(total, dict) or total.get("currency") != "JPY"
        or type(total.get("amount")) is not int
        or total["amount"] != amount_yen):
        raise LiveSquareNotVerified("Square order total mismatch")
    fulfillments = order.get("fulfillments")
    if not isinstance(fulfillments, list):
        raise LiveSquareNotVerified("No shipping fulfillment")
    emails = set()
    found_complete = False
    for f in fulfillments:
        if not isinstance(f, dict) or f.get("type") != "SHIPMENT":
            continue
        details = f.get("shipment_details")
        person = details.get("recipient") if isinstance(details, dict) else None
        if not isinstance(person, dict):
            continue
        addr = person.get("address")
        if not isinstance(addr, dict):
            continue
        email = person.get("email_address")
        if (addr.get("country") != "JP" or
            not isinstance(addr.get("address_line_1"), str)
            or not addr["address_line_1"].strip()
            or not isinstance(addr.get("postal_code"), str)
            or not addr["postal_code"].strip()
            or not isinstance(person.get("display_name"), str)
            or not person["display_name"].strip()
            or not isinstance(email,str) or len(email)>254
            or not EMAIL.fullmatch(email) or ".." in email or email.startswith(".")):
            continue
        found_complete = True
        emails.add(email.lower())
    if not found_complete or len(emails) != 1:
        raise LiveSquareNotVerified("Missing or ambiguous verified recipient")
    email=emails.pop()
    return {
        "live_square_verified": True,
        "payment_id": payment_id,
        "square_order_id": square_order_id,
        "location_id": location_id,
        "amount_yen": amount_yen,
        "recipient_email": email,  # in memory only; never log/store in DB
    }
