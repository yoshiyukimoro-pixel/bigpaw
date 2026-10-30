"""DISCONNECTED future production checkout controller (not an HTTP route).

This is the missing boundary between a future approved shopper request and
the existing LiveCheckoutIntent / real Square CreatePaymentLink adapter.
NO active BIG PAW site, staging server, service entrypoint, or UI imports it.

The current launch manifest fails closed (all signoffs false) and no live
environment keys are provisioned by this module. The code must remain unwired
until the owner approves statutory merchant information, returns, exact terms,
shipment process, pricing, Square production, email and environment separation.

Trust boundaries:
- Client submits only a uuid4 checkout attempt, SKU/quantities and the SHA-256
  of the final seller-approved terms it saw. NEVER buyer-supplied price/total.
- A server-trusted session ID + distinct 32+ byte server secret HMAC-scopes the
  local order ID; even equal browser attempts in different sessions are unique.
- A server-supplied, unguessable CSRF token is matched in constant time. The
  future HTTP adapter MUST validate TLS edge/Host/session/CSRF cookie and
  enable rate limits. This controller does not authenticate the buyer itself.
- Check owner approval and manifest BEFORE creating SQLite intent or calling
  Square. No automatic retry after timeout; unknown results require audit.
- No customer name/email/address or payment credentials are stored in SQLite.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import re
from urllib.parse import urlsplit

from .live_checkout_intent import LiveCheckoutIntent
from .live_order_ledger import LiveOrderBlocked
from .retail_launch_guard import check
from .square_live_checkout_adapter import create_live_square_link

_UUID4 = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$"
)
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_SKU = re.compile(r"^[AOZC][0-9]{2}$")


def _no_duplicate_keys(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate request keys")
        result[key] = value
    return result


def _approved_public_launch(status, env):
    ready, missing = check(status)
    if not ready or missing:
        raise LiveOrderBlocked("Merchant launch conditions have not been approved")
    if not isinstance(env, dict) or any(env.get(k) != v for k, v in {
        "BIGPAW_ENV": "live",
        "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "1",
        "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "1",
    }.items()):
        raise LiveOrderBlocked("Public live shop authorization is disabled")
    terms = env.get("BIGPAW_SHOP_APPROVED_TERMS_SHA256")
    if not isinstance(terms, str) or not _SHA256.fullmatch(terms):
        raise LiveOrderBlocked("Final terms have not been approved")
    token = env.get("BIGPAW_SQUARE_LIVE_ACCESS_TOKEN")
    location = env.get("BIGPAW_SQUARE_LIVE_LOCATION_ID")
    if not isinstance(token, str) or len(token.strip()) < 20:
        raise LiveOrderBlocked("Square production credentials are unavailable")
    if (not isinstance(location, str) or
            not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", location)):
        raise LiveOrderBlocked("Square merchant location is unapproved")
    return terms, token, location


def checkout_live_request(
    *, intent: LiveCheckoutIntent, raw_body: bytes,
    origin: str, allowed_origin: str,
    csrf_header: str, server_csrf: str,
    trusted_session_id: str, server_order_secret: str,
    launch_status: dict, private_env: dict,
    post_opener=None, get_opener=None,
):
    """Never invoked in deployed app; test by injecting *fake* Square openers.

    On success returns only authenticated session's checkout URL, local order
    ID and server-price total. A future HTTP layer MUST bind the response to
    that same trusted session and handle exceptions without leaking secrets.
    """
    if not isinstance(intent, LiveCheckoutIntent):
        raise LiveOrderBlocked("Trusted private order journal required")
    # Gate BEFORE parse, I/O, SQLite writes, or Square requests.
    terms_digest, token, location = _approved_public_launch(
        launch_status, private_env
    )
    try:
        u = urlsplit(allowed_origin)
        if (not isinstance(origin, str) or origin != allowed_origin
                or u.scheme != "https" or not u.hostname
                or u.hostname in ("localhost", "127.0.0.1")
                or u.username is not None or u.password is not None
                or u.port not in (None, 443) or u.path not in ("", "/")
                or u.query or u.fragment):
            raise ValueError()
    except (TypeError, ValueError):
        raise LiveOrderBlocked("Checkout origin not authorized") from None

    if (not isinstance(csrf_header, str) or not isinstance(server_csrf, str)
            or not 32 <= len(csrf_header) <= 128
            or not 32 <= len(server_csrf) <= 128
            or not hmac.compare_digest(csrf_header, server_csrf)):
        raise LiveOrderBlocked("Trusted session CSRF check required")
    if (not isinstance(trusted_session_id, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{24,128}", trusted_session_id)
            or not isinstance(server_order_secret, str)
            or len(server_order_secret.encode("utf-8")) < 32):
        raise LiveOrderBlocked("Server session binding unavailable")
    if not isinstance(raw_body, bytes) or not 1 <= len(raw_body) <= 4096:
        raise LiveOrderBlocked("Invalid checkout body")

    try:
        request = json.loads(
            raw_body.decode("utf-8"), object_pairs_hook=_no_duplicate_keys
        )
        if not isinstance(request, dict) or set(request) != {
            "cart", "attempt_id", "terms_sha256"
        }:
            raise ValueError()
        cart = request["cart"]
        attempt = request["attempt_id"]
        shown_terms = request["terms_sha256"]
        if (not isinstance(attempt, str) or not _UUID4.fullmatch(attempt)
                or not isinstance(shown_terms, str)
                or not _SHA256.fullmatch(shown_terms)
                or not hmac.compare_digest(shown_terms, terms_digest)
                or not isinstance(cart, dict)
                or not 1 <= len(cart) <= 35):
            raise ValueError()
        if any(not isinstance(sku, str) or not _SKU.fullmatch(sku)
               or type(qty) is not int or not 1 <= qty <= 10
               for sku, qty in cart.items()):
            raise ValueError()
    except (ValueError, TypeError, UnicodeError):
        raise LiveOrderBlocked("Invalid order, quantity or final terms") from None

    # This is derived from the trusted *server* session; the user cannot
    # choose a saved order ID or claim a previous session's Square link.
    order_id = "FOOD" + hmac.new(
        server_order_secret.encode("utf-8"),
        ("bigpaw-food-checkout-v1\0" + trusted_session_id +
         "\0" + attempt).encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()[:32]
    plan = intent.prepare(
        order_id=order_id, location_id=location, cart=cart
    )
    if plan["state"] != "planned":
        raise LiveOrderBlocked("Existing checkout requires operator audit")
    claimed = intent.begin_attempt(order_id=order_id)
    # Future approved host adapter uses *real* Square POST exactly once.
    # Tests inject a fake opener, so no network is ever performed in CI.
    kwargs = dict(server_payload=claimed["server_only_payload"],
                  access_token=token)
    if post_opener is not None:
        kwargs["opener"] = post_opener
    link = create_live_square_link(**kwargs)
    verify = dict(order_id=order_id, link=link, api_key=token)
    if get_opener is not None:
        verify["opener"] = get_opener
    bound = intent.bind_square_result(**verify)
    if bound != {"state": "link_bound", "new_binding": True}:
        raise LiveOrderBlocked("Square link was not newly verified")
    return {
        "order_id": order_id,
        "checkout_url": link["url"],
        "amount_yen": plan["amount_yen"],
        "shipping_yen": 0,
    }
