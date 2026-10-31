"""Verified seller-contact disclosure adapter. Separate from retail checkout.

Development branch only; returns 404 unless all private merchant details, the
Resend sender key and explicit auto-disclosure switch are configured.
The ordinary support ticket is committed first, so failed mail never loses it.
Private contact data is sent ONLY after possession of the emailed one-time token.
"""
from __future__ import annotations

import json
import os
import re
from urllib.parse import urlsplit

from shop_payments import seller_disclosure_automation as disclosure

CONFIRM_PATH = "/api/shop/seller-disclosure/confirm"
ALLOWED_HOSTS = {"bigpaw.site", "www.bigpaw.site"}
MAX_CONFIRM_BYTES = 512


def request_challenge(conn, ticket_id, recipient, *, env=None, sender=None):
    """Run after ticket COMMIT. Never expose private seller contact in HTTP."""
    env = dict(os.environ if env is None else env)
    if not disclosure.ready(env):
        return "disabled"
    args = {"env": env}
    if sender is not None:
        args["sender"] = sender
    return disclosure.request_for_ticket(conn, ticket_id, recipient, **args)


def _respond(handler, status, code):
    handler.send_json({"status": status} if code == 200 else {"error": status},
                      code, extra={"Cache-Control": "no-store",
                                   "Referrer-Policy": "no-referrer"})
    return True


def _trusted_browser_request(handler, base_url):
    if base_url not in ("https://bigpaw.site", "https://www.bigpaw.site"):
        return False
    # Never accept a cross-site form POST or a forged Host.
    host = handler.headers.get("Host", "").lower()
    if host not in ALLOWED_HOSTS:
        return False
    if handler.headers.get("Origin", "") != "https://" + host:
        return False
    if handler.headers.get("X-Forwarded-Host", "").lower() not in ("", host):
        return False
    if handler.headers.get("X-Forwarded-Proto", "").lower() not in ("", "https"):
        return False
    if handler.headers.get("Sec-Fetch-Site", "").lower() not in ("", "same-origin"):
        return False
    if (handler.headers.get("Transfer-Encoding")
            or handler.headers.get("Authorization")):
        return False
    return True


def handle_confirm(handler, *, env=None, base_url="", db_factory=None,
                   rate_limited=None, sender=None):
    if handler.path != CONFIRM_PATH:
        return False
    env = dict(os.environ if env is None else env)
    if not disclosure.ready(env):
        return _respond(handler, "seller_disclosure_unavailable", 404)
    if not _trusted_browser_request(handler, base_url):
        return _respond(handler, "invalid_origin", 403)
    if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
        return _respond(handler, "invalid_request", 415)
    size = handler.headers.get("Content-Length", "")
    if not re.fullmatch(r"[0-9]{1,3}", size) or not (1 <= int(size) <= MAX_CONFIRM_BYTES):
        return _respond(handler, "invalid_request", 400)
    if rate_limited and rate_limited("shop-seller-disclosure-confirm:" +
                                    handler.client_address[0], 8, 3600):
        return _respond(handler, "rate_limited", 429)
    try:
        data = json.loads(handler.rfile.read(int(size)).decode("utf-8"))
    except (ValueError, UnicodeError):
        return _respond(handler, "invalid_request", 400)
    if not isinstance(data, dict) or set(data) != {"token"}:
        return _respond(handler, "invalid_request", 400)
    if db_factory is None:
        return _respond(handler, "seller_disclosure_unavailable", 503)
    conn = None
    try:
        conn = db_factory()
        opts = {"env": env}
        if sender is not None:
            opts["sender"] = sender
        result = disclosure.confirm_request(conn, data["token"], **opts)
    except Exception:
        # Do not log a private address, phone, token, message body or mail key.
        return _respond(handler, "disclosure_confirmation_unavailable", 503)
    finally:
        if conn is not None:
            conn.close()
    if result == "provider_accepted":
        return _respond(handler, "provider_accepted", 200)
    if result == "invalid_or_expired":
        return _respond(handler, "invalid_or_expired", 400)
    return _respond(handler, "disclosure_confirmation_unavailable", 503)
