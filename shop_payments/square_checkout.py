"""Square checkout planning helpers for BIG PAW dog-food shop.

STAGING ONLY. This module does not make HTTP requests or register any server
routes. It has no production credentials, no customer data storage, and never
changes existing BIG PAW payment flows.

Square reference: POST /v2/online-checkout/payment-links (2026-09-16).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import re
from dataclasses import dataclass
from typing import Mapping


MAX_QTY_PER_PRODUCT = 10
MAX_CART_ITEMS = 35
MAX_ORDER_YEN = 2_000_000


@dataclass(frozen=True)
class SaleItem:
    product_id: str
    name: str
    size: str
    sale_price_yen: int  # Approved MSRP as tax-inclusive selling price, NEVER wholesale.


def _positive_yen(value: int, field: str, *, allow_zero: bool = False) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer number of JPY")
    if value < 0 or (not allow_zero and value == 0):
        raise ValueError(f"{field} must be {'non-negative' if allow_zero else 'positive'}")
    if value > MAX_ORDER_YEN:
        raise ValueError(f"{field} exceeds safety limit")
    return value


def build_square_link_payload(
    *,
    cart: Mapping[str, int],
    verified_prices: Mapping[str, SaleItem],
    shipping_yen: int,
    square_location_id: str,
    local_order_id: str,
    shipping_confirmed: bool,
) -> tuple[dict, int]:
    """Build a draft CreatePaymentLink request, with no network activity.

    Caller MUST have persisted a pending order and its verified price/quantity/
    shipping snapshot atomically before using this payload in a future
    server-only Square integration. Client-submitted prices are NEVER accepted.

    The merchant approved manufacturer MSRP as the tax-inclusive sale price,
    with shipping included and no extra delivery charge in BIG PAW checkout.
    Do not ever include procurement/wholesale prices.
    """
    if not shipping_confirmed:
        raise ValueError("shipping must be confirmed before creating payment link")
    if not isinstance(cart, Mapping) or not cart or len(cart) > MAX_CART_ITEMS:
        raise ValueError("invalid cart length")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", square_location_id):
        raise ValueError("invalid Square location ID")
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", local_order_id):
        raise ValueError("invalid internal order ID")
    shipping = _positive_yen(shipping_yen, "shipping_yen", allow_zero=True)
    total = shipping
    rows = []
    for pid, qty in sorted(cart.items()):
        if not isinstance(pid, str) or pid not in verified_prices:
            raise ValueError("unknown product; reject stale or tampered cart")
        if isinstance(qty, bool) or not isinstance(qty, int) or not (1 <= qty <= MAX_QTY_PER_PRODUCT):
            raise ValueError("invalid product quantity")
        product = verified_prices[pid]
        if product.product_id != pid or not product.name.strip() or not product.size.strip():
            raise ValueError("invalid server catalog entry")
        unit = _positive_yen(product.sale_price_yen, "sale_price_yen")
        total += unit * qty
        rows.append({
            "name": (product.name + " " + product.size)[:120],
            "quantity": str(qty),
            "base_price_money": {"amount": unit, "currency": "JPY"},
        })
    if shipping:
        rows.append({
            "name": "送料",
            "quantity": "1",
            "base_price_money": {"amount": shipping, "currency": "JPY"},
        })
    if total > MAX_ORDER_YEN:
        raise ValueError("order total exceeds safety limit")
    # Stable per *persisted* order; never reuse local_order_id for a new order.
    idempotency = "bigpaw-food-" + hashlib.sha256(local_order_id.encode()).hexdigest()[:48]
    payload = {
        "idempotency_key": idempotency,
        "order": {
            "location_id": square_location_id,
            "line_items": rows,
            "taxes": [{
                "uid": "BIGPAW_JP_TAX10_INCLUSIVE",
                "name": "消費税10%（内税）",
                "type": "INCLUSIVE",
                "percentage": "10",
                "scope": "ORDER",
            }],
        },
        "checkout_options": {"ask_for_shipping_address": True, "allow_tipping": False},
        "payment_note": "BIG PAW food order " + local_order_id,
    }
    return payload, total


def verify_square_webhook(
    *, raw_body: bytes, signature_header: str, signature_key: str, notification_url: str
) -> dict:
    """Validate Square's HMAC-SHA256 signature of URL + *raw* request body.

    HTTPS notification URL must exactly match the one configured in Square.
    Caller must persist and deduplicate event_id in its own durable storage.
    Never mark paid from a redirect URL or unverified client callback.
    """
    if not signature_key or not signature_header or not notification_url.startswith("https://"):
        raise ValueError("Square webhook verification not configured")
    if not isinstance(raw_body, bytes) or len(raw_body) > 256_000:
        raise ValueError("invalid webhook body")
    actual = base64.b64encode(
        hmac.new(signature_key.encode("utf-8"), notification_url.encode("utf-8") + raw_body, hashlib.sha256).digest()
    ).decode("ascii")
    if not hmac.compare_digest(actual, signature_header):
        raise ValueError("invalid Square webhook signature")
    try:
        event = json.loads(raw_body)
    except (ValueError, UnicodeDecodeError) as exc:
        raise ValueError("invalid webhook JSON") from exc
    if not isinstance(event, dict) or not isinstance(event.get("event_id"), str):
        raise ValueError("webhook lacks event ID")
    return event


def completed_payment_matches(
    event: dict, *, square_order_id: str, amount_yen: int, location_id: str
) -> bool:
    """A *verified* Square event also must match the persisted order snapshot.

    The event may arrive out of order or more than once; a real endpoint must
    fetch current payment state if needed and transactionally deduplicate.
    """
    _positive_yen(amount_yen, "amount_yen")
    if event.get("type") not in {"payment.created", "payment.updated"}:
        return False
    pay = event.get("data", {}).get("object", {}).get("payment", {})
    if not isinstance(pay, dict):
        return False
    money = pay.get("amount_money", {})
    return bool(
        pay.get("status") == "COMPLETED"
        and pay.get("order_id") == square_order_id
        and pay.get("location_id") == location_id
        and isinstance(money, dict)
        and money.get("currency") == "JPY"
        and type(money.get("amount")) is int
        and money["amount"] == amount_yen
    )
