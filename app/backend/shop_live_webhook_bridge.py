"""Dormant Square Production payment webhook adapter for BIG PAW food shop.

A Square webhook is NOT a browser session and carries no buyer CSRF cookie.
Its sole authentication is the exact-URL + raw-body Square HMAC signature;
a signature by itself NEVER marks an order paid. The signed payment is mapped
to the immutable private checkout journal and independently re-fetched via
Square Production GET Payments + Orders before the journal is updated.

Webhook reconciliation has its own explicit operator authorization and stays
available to existing orders if public checkout is suspended. Neither checked-in
Railway project has configured live Square webhook credentials; the route
therefore remains disabled until the owner explicitly provisions them.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
from urllib.parse import urlsplit


PATH = "/api/shop/square-webhook"
MAX_BYTES = 256_000


def _send(handler, code: int, reason: str):
    # Never echo event IDs, payment IDs, customer fields, signatures or secrets.
    handler.send_json({"error": reason} if code >= 400 else {"ok": True}, code)
    return True


def _allowed(env, base_url, status):
    # IMPORTANT: disabling new checkout does NOT cancel pending Square links.
    # Keep signed reconciliation available for already-issued orders when
    # BIGPAW_SHOP_PUBLIC_LIVE_ENABLED=0 or checkout approval checks fail.
    # Only independently authorized webhook configuration permits this.
    if not isinstance(env, dict):
        return False
    if base_url not in ("https://bigpaw.site", "https://www.bigpaw.site"):
        return False
    if (env.get("BIGPAW_ENV") != "production"
            or env.get("BIGPAW_SHOP_OWNER_LAUNCH_APPROVED") != "1"
            or env.get("BIGPAW_SHOP_SQUARE_LIVE_WEBHOOK_ENABLED") != "1"):
        return False
    if env.get("BIGPAW_SQUARE_LIVE_WEBHOOK_URL") != base_url + PATH:
        return False
    token = env.get("BIGPAW_SQUARE_LIVE_ACCESS_TOKEN")
    location = env.get("BIGPAW_SQUARE_LIVE_LOCATION_ID")
    signature_key = env.get("BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY")
    if (not isinstance(token, str) or len(token.strip()) < 20
            or not isinstance(location, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}", location)
            or not isinstance(signature_key, str)
            or len(signature_key.encode("utf-8")) < 32
            or any(x in signature_key for x in "\r\n")):
        return False
    if (token == env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN")
            or location == env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID")):
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
        # Webhook reconciliation is an INDEPENDENT authorization gate.
        # No public purchase approvals or storefront kill-switch are required;
        # a paid link created BEFORE checkout suspension still needs handling.
        # Checked-in Railway environments lack a live Square signing key, so
        # this remains disabled without operator-approved runtime credentials.
        if not _allowed(env, base_url, launch_status):
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
        # A signed notification cannot bootstrap a private order journal;
        # it must match a link created previously by the trusted checkout.
        db_path = Path(data_dir) / "bigpaw-shop-live-orders.sqlite3"
        if not db_path.is_file():
            return _send(handler, 503, "private_order_journal_missing")
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
        ledger = LiveOrderLedger(db_path)
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
