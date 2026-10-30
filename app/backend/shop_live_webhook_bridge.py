"""Dormant Square Production payment webhook adapter for BIG PAW food shop.

A Square webhook is NOT a browser session and carries no buyer CSRF cookie.
Its sole authentication is the exact-URL + raw-body Square HMAC signature;
a signature by itself NEVER marks an order paid. The signed payment is mapped
to the immutable private checkout journal and independently re-fetched via
Square Production GET Payments + Orders before the journal is updated.

With the checked-in unapproved launch manifest, this route always returns 404
BEFORE reading any request body, accessing a database or sending Square GETs.
No provider endpoint, merchant credential or webhook is configured/enabled.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from urllib.parse import urlsplit

from shop_live_checkout_bridge import _gate, _load_manifest

PATH = "/api/shop/square-webhook"
MAX_BYTES = 256_000


def _send(handler, code: int, reason: str):
    # Never echo event IDs, payment IDs, customer fields, signatures or secrets.
    handler.send_json({"error": reason} if code >= 400 else {"ok": True}, code)
    return True


def _allowed(env, base_url, status):
    if not _gate(env, base_url, status):
        return False
    if env.get("BIGPAW_SHOP_SQUARE_LIVE_WEBHOOK_ENABLED") != "1":
        return False
    if env.get("BIGPAW_SQUARE_LIVE_WEBHOOK_URL") != base_url + PATH:
        return False
    signature_key = env.get("BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY")
    if (not isinstance(signature_key, str)
            or len(signature_key.encode("utf-8")) < 32
            or any(x in signature_key for x in "\r\n")):
        return False
    return True


def _trusted_request(handler, base_url):
    origin = urlsplit(base_url)
    if handler.path != PATH or handler.headers.get("Host", "").lower() != origin.netloc:
        return False
    if handler.headers.get("X-Forwarded-Host", "").lower() not in ("", origin.netloc):
        return False
    if handler.headers.get("X-Forwarded-Proto", "").lower() not in ("", "https"):
        return False
    # Square server-to-server notifications are not browser requests.
    if (handler.headers.get("Origin") or handler.headers.get("Cookie")
            or handler.headers.get("Authorization")
            or handler.headers.get("Sec-Fetch-Site")):
        return False
    if handler.headers.get("Transfer-Encoding"):
        return False
    return True


def handle_post(handler, *, env=None, base_url="", data_dir=None,
                launch_status=None, square_get_opener=None):
    if urlsplit(handler.path).path != PATH:
        return False
    env = dict(os.environ if env is None else env)
    try:
        status = _load_manifest() if launch_status is None else launch_status
        # Absolute first gate; with current manifest this cannot read the
        # webhook body, initialize SQLite, call Square or mark a payment.
        if not _allowed(env, base_url, status):
            return _send(handler, 404, "shop_webhook_unavailable")
        if not _trusted_request(handler, base_url):
            return _send(handler, 403, "webhook_request_rejected")
        if (handler.headers.get("Content-Type", "").split(";", 1)[0]
                .strip().lower() != "application/json"):
            return _send(handler, 415, "invalid_content_type")
        raw_length = handler.headers.get("Content-Length", "")
        if not isinstance(raw_length, str) or not re.fullmatch(r"[0-9]{1,6}", raw_length):
            return _send(handler, 400, "invalid_length")
        length = int(raw_length)
        if not 1 <= length <= MAX_BYTES:
            return _send(handler, 413, "invalid_length")
        signature = handler.headers.get("X-Square-Hmacsha256-Signature", "")
        if (not isinstance(signature, str)
                or not re.fullmatch(r"[A-Za-z0-9+/]{43}=", signature)):
            return _send(handler, 401, "invalid_signature")
        if not isinstance(data_dir, (str, Path)) or not Path(data_dir).is_dir():
            return _send(handler, 503, "private_store_unavailable")
        raw_body = handler.rfile.read(length)
        if len(raw_body) != length:
            return _send(handler, 400, "invalid_length")
        # Verify the signature before consulting the journal or Square.
        from shop_payments.square_checkout import verify_square_webhook
        try:
            verify_square_webhook(
                raw_body=raw_body, signature_header=signature,
                signature_key=env["BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY"],
                notification_url=env["BIGPAW_SQUARE_LIVE_WEBHOOK_URL"],
            )
        except (ValueError, UnicodeError):
            return _send(handler, 401, "invalid_signature")
        from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
        from shop_payments.live_payment_intake import record_verified_live_payment_event
        from shop_payments.square_live_readonly import LiveSquareNotVerified
        ledger = LiveOrderLedger(Path(data_dir) / "bigpaw-shop-live-orders.sqlite3")
        args = {
            "ledger": ledger, "raw_body": raw_body,
            "signature_header": signature,
            "signature_key": env["BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY"],
            "notification_url": env["BIGPAW_SQUARE_LIVE_WEBHOOK_URL"],
            "api_key": env["BIGPAW_SQUARE_LIVE_ACCESS_TOKEN"],
        }
        if square_get_opener is not None:
            args["opener"] = square_get_opener
        try:
            result = record_verified_live_payment_event(**args)
        except LiveOrderBlocked:
            # A signed but unrecognized event should be investigated; do not
            # acknowledge it as paid or expose order information.
            return _send(handler, 409, "payment_event_not_confirmed")
        except (LiveSquareNotVerified, OSError):
            # Provider errors/refunds are ambiguous; allow provider retry
            # without incorrectly claiming the customer paid.
            return _send(handler, 503, "square_payment_not_verified")
        if result.get("state") in ("ignored", "awaiting_square",
                                   "already_recorded", "paid_verified"):
            return _send(handler, 200, "")
        return _send(handler, 503, "unrecognized_payment_outcome")
    except (OSError, KeyError, ValueError, TypeError, ImportError):
        # Never expose secrets or payment details in a failure response.
        return _send(handler, 503, "shop_webhook_unavailable")
