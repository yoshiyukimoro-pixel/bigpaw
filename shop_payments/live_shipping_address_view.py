"""Dormant Square Production recipient read for the authenticated BIG PAW operator.

Never run by a shopper, webhook, or background job. This module performs only
three fixed Square Production GET requests, and only when the caller has an
immutable paid order from the private ledger and an explicitly authorized
operator workflow. It does not persist, log, email, charge, or dispatch anything.

The future HTTP route has a separate OFF-by-default launch switch.
"""
from __future__ import annotations

from .square_live_readonly import (
    LiveSquareNotVerified, _square_get, verify_paid_live_shipment,
)
from .sandbox_reconcile import _valid_japanese_shipping_recipient


def _safe_extra(value):
    if value is None or value == "":
        return ""
    if (not isinstance(value, str) or len(value.strip()) > 200
            or any(ord(ch) < 32 or ord(ch) == 127 for ch in value)):
        raise LiveSquareNotVerified("Unverified optional delivery address")
    return value.strip()


def read_live_recipient_for_dispatch(*, snapshot, api_key, opener=None):
    """Return minimally necessary address fields in memory for ONE order.

    The snapshot must come from LiveOrderLedger.paid_notice_snapshot(),
    not from an incoming web request. Successful Square verification is
    mandatory and must include the current unrefunded payment.
    """
    if not isinstance(snapshot, dict) or set(snapshot) != {
            "order_id", "square_order_id", "location_id",
            "payment_id", "amount_yen", "lines"}:
        raise LiveSquareNotVerified("Trusted paid journal required")
    arguments = {
        "payment_id": snapshot["payment_id"],
        "square_order_id": snapshot["square_order_id"],
        "location_id": snapshot["location_id"],
        "amount_yen": snapshot["amount_yen"],
        "api_key": api_key,
    }
    if opener is not None:
        arguments["opener"] = opener
    evidence = verify_paid_live_shipment(**arguments)
    if (not isinstance(evidence, dict)
            or evidence.get("live_square_verified") is not True
            or any(evidence.get(k) != val for k, val in (
                ("payment_id", snapshot["payment_id"]),
                ("square_order_id", snapshot["square_order_id"]),
                ("location_id", snapshot["location_id"]),
                ("amount_yen", snapshot["amount_yen"]),
            ))):
        raise LiveSquareNotVerified("Provider payment no longer verified")
    kwargs = {"api_key": api_key}
    if opener is not None:
        kwargs["opener"] = opener
    payload = _square_get("orders", snapshot["square_order_id"], **kwargs)
    order = payload.get("order") if isinstance(payload, dict) else None
    if (not isinstance(order, dict)
            or order.get("id") != snapshot["square_order_id"]
            or order.get("location_id") != snapshot["location_id"]
            or order.get("state") not in ("OPEN", "COMPLETED")
            or not isinstance(order.get("total_money"), dict)
            or order["total_money"].get("currency") != "JPY"
            or type(order["total_money"].get("amount")) is not int
            or order["total_money"]["amount"] != snapshot["amount_yen"]):
        raise LiveSquareNotVerified("Current Square order differs")
    fulfillments = order.get("fulfillments")
    if (not isinstance(fulfillments, list) or len(fulfillments) != 1
            or not isinstance(fulfillments[0], dict)
            or fulfillments[0].get("type") != "SHIPMENT"):
        raise LiveSquareNotVerified("Shipping destination ambiguous")
    details = fulfillments[0].get("shipment_details")
    recipient = details.get("recipient") if isinstance(details, dict) else None
    if not _valid_japanese_shipping_recipient(recipient):
        raise LiveSquareNotVerified("Current Square shipping recipient incomplete")
    address = recipient["address"]
    return {
        "name": recipient["display_name"].strip(),
        "phone": recipient["phone_number"].strip(),
        "postal": address["postal_code"],
        "prefecture": address["administrative_district_level_1"].strip(),
        "city": address["locality"].strip(),
        "line1": address["address_line_1"].strip(),
        "line2": _safe_extra(address.get("address_line_2")),
        "line3": _safe_extra(address.get("address_line_3")),
    }
