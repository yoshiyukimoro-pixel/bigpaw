"""UNWIRED Square PRODUCTION create-payment-link adapter.

WARNING: a future caller could cause a REAL remote checkout link to be
created. THIS MODULE HAS NO HTTP ROUTE, BACKGROUND JOB, CONFIGURATION, OR
APP STARTUP INTEGRATION. The current BIG PAW site and bigpaw-test never import
or invoke it. Do not connect until proprietor authorizes live launch.

The only valid calling sequence is:
  LiveCheckoutIntent.prepare -> begin_attempt -> create_live_square_link
  -> LiveCheckoutIntent.bind_square_result (Square GET verification).
The intent is marked uncertain *before* this POST. If request outcome is
unknown, do NOT retry automatically or use a new idempotency key.

The URL is a Square-controlled fixed production endpoint. No token, response
body, customer data or purchase details are included in error messages.
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .live_checkout_intent import _safe_link
from .live_order_ledger import LiveOrderBlocked
from .sandbox_connector import SQUARE_VERSION
from .square_checkout import build_square_link_payload

ENDPOINT = "https://connect.squareup.com/v2/online-checkout/payment-links"
_ID = re.compile(r"^[A-Za-z0-9_-]{8,192}$")
_INTERNAL = re.compile(r"^FOOD[0-9a-f]{32}$")


def _strict_request(payload):
    """Reject arbitrary browser-supplied prices, addresses and URLs by shape.

    The future caller MUST additionally prove this is the unchanged payload
    returned by a private LiveCheckoutIntent.begin_attempt transaction.
    """
    if not isinstance(payload, dict) or set(payload) != {
        "idempotency_key", "order", "checkout_options", "payment_note"
    }:
        raise LiveOrderBlocked("Unapproved Square create-link request")
    note = payload.get("payment_note")
    prefix = "BIG PAW food order "
    if not isinstance(note, str) or not note.startswith(prefix):
        raise LiveOrderBlocked("Missing server order note")
    order_id = note[len(prefix):]
    if not _INTERNAL.fullmatch(order_id):
        raise LiveOrderBlocked("Invalid server order note")
    order = payload.get("order")
    options = payload.get("checkout_options")
    if (not isinstance(order, dict) or
            set(order) != {"location_id", "line_items", "taxes"}
            or not isinstance(options, dict)
            or options != {"ask_for_shipping_address": True,
                           "allow_tipping": False}):
        raise LiveOrderBlocked("Square checkout order structure changed")
    location = order.get("location_id")
    if not isinstance(location, str) or not _ID.fullmatch(location):
        raise LiveOrderBlocked("Invalid merchant location")
    # Only exact immutable server-created payloads are allowed. Rebuild it
    # from its local line items then compare, not from current browser fields.
    # A trusted caller checks the persisted complete request and prices.
    lines = order["line_items"]
    if not isinstance(lines, list) or not 1 <= len(lines) <= 35:
        raise LiveOrderBlocked("Invalid line items")
    if (order["taxes"] != [{
        "uid": "BIGPAW_JP_TAX10_INCLUSIVE",
        "name": "消費税10%（内税）", "type": "INCLUSIVE",
        "percentage": "10", "scope": "ORDER",
    }]):
        raise LiveOrderBlocked("Unexpected Square tax configuration")
    total = 0
    for line in lines:
        if not isinstance(line, dict) or set(line) != {
            "name", "quantity", "base_price_money"
        }:
            raise LiveOrderBlocked("Invalid Square line")
        money = line.get("base_price_money")
        qty = line.get("quantity")
        name = line.get("name")
        if (not isinstance(name, str) or not 1 <= len(name) <= 120
                or "\n" in name or "\r" in name
                or not isinstance(qty, str) or not re.fullmatch(r"(?:[1-9]|10)", qty)
                or not isinstance(money, dict)
                or set(money) != {"amount", "currency"}
                or money.get("currency") != "JPY"
                or type(money.get("amount")) is not int
                or not 1 <= money["amount"] <= 2_000_000):
            raise LiveOrderBlocked("Unexpected Square price or item")
        total += int(qty) * money["amount"]
    if total > 2_000_000:
        raise LiveOrderBlocked("Square checkout amount too large")
    from hashlib import sha256
    expected = "bigpaw-food-" + sha256(order_id.encode()).hexdigest()[:48]
    if payload["idempotency_key"] != expected:
        raise LiveOrderBlocked("Square idempotency key changed")
    return total


def create_live_square_link(*, server_payload, access_token, opener=urlopen):
    """Make exactly ONE live Square POST; never automatically retry.

    Strictly for a future approved backend. In tests opener is synthetic and
    never makes a real HTTP connection. The returned data still requires a
    separate trusted Square Orders GET before link is bound or shown.
    """
    _strict_request(server_payload)
    if not isinstance(access_token, str) or len(access_token.strip()) < 20:
        raise LiveOrderBlocked("Live Square authorization unavailable")
    req = Request(
        ENDPOINT, data=json.dumps(server_payload, ensure_ascii=False,
                                  separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + access_token.strip(),
            "Square-Version": SQUARE_VERSION,
            "Accept": "application/json",
            "Content-Type": "application/json",
        }, method="POST",
    )
    try:
        with opener(req, timeout=12) as response:
            if getattr(response, "status", 200) not in (200, 201):
                raise LiveOrderBlocked("Square link creation result uncertain")
            raw = response.read(262145)
            if len(raw) > 262144:
                raise LiveOrderBlocked("Square link creation response invalid")
            data = json.loads(raw)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise LiveOrderBlocked(
            "Square link outcome unknown; operator audit required, no automatic retry"
        ) from None
    if not isinstance(data, dict) or not isinstance(data.get("payment_link"), dict):
        raise LiveOrderBlocked("Square link response incomplete; manual audit required")
    link = data["payment_link"]
    if (not isinstance(link.get("id"), str)
            or not _ID.fullmatch(link["id"])
            or not isinstance(link.get("order_id"), str)
            or not _ID.fullmatch(link["order_id"])
            or not _safe_link(link.get("url"))):
        raise LiveOrderBlocked("Square returned unexpected link; manual audit required")
    return {"id": link["id"], "order_id": link["order_id"],
            "url": link["url"]}
