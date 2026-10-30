"""Dormant BIG PAW customer checkout HTTP adapter; launch checks fail closed.

This module is mounted by app/backend/server.py ONLY on the Draft shop branch.
Production deployment, live terms/credentials, merchant approval and checkout
activation are NOT performed here. With the checked-in launch manifest it
always returns 404 before session lookup, DB, or Square calls.

When approved in a FUTURE release, the site session (not client-provided
user/total/order ID), strict canonical HTTPS Origin+Host, session-HMAC CSRF,
small bounded JSON, role and rate-limit protect checkout_live_request.
"""
from __future__ import annotations

from http.cookies import SimpleCookie
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
from urllib.parse import urlsplit

_SESSION = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
_SECRET_MIN = 32


def _fail(handler, reason="shop_checkout_unavailable", status=404):
    handler.send_json({"error": reason}, status)
    return True


def _csrf(secret: str, session_cookie: str, user_id: str) -> str:
    return hmac.new(secret.encode("utf-8"),
                    ("bigpaw-shop-checkout-csrf-v1\0" + session_cookie +
                     "\0" + user_id).encode("utf-8"),
                    hashlib.sha256).hexdigest()


def _load_manifest():
    from shop_payments.retail_launch_guard import MANIFEST
    return json.loads(MANIFEST.read_text(encoding="utf-8"))


def _gate(env, base_url, status):
    # The existing site uses BIGPAW_ENV=production, not "live". The pure
    # checkout controller's "live" label is adapted *after* these checks.
    from shop_payments.retail_launch_guard import check
    ready, missing = check(status)
    if not ready or missing:
        return False
    if not isinstance(env, dict) or any(env.get(k) != v for k, v in {
        "BIGPAW_ENV": "production",
        "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED": "1",
        "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED": "1",
    }.items()):
        return False
    if (not isinstance(env.get("BIGPAW_SHOP_ORDER_HMAC_SECRET"), str)
            or len(env["BIGPAW_SHOP_ORDER_HMAC_SECRET"].encode()) < _SECRET_MIN):
        return False
    if (not isinstance(base_url, str)
            or base_url not in ("https://bigpaw.site",
                                "https://www.bigpaw.site")):
        return False
    # Sandbox credentials must never be recycled as production credentials,
    # even if an operator accidentally copied stage variables into live.
    if (env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN")
            and env.get("BIGPAW_SQUARE_LIVE_ACCESS_TOKEN")
            == env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN")):
        return False
    if (env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID")
            and env.get("BIGPAW_SQUARE_LIVE_LOCATION_ID")
            == env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID")):
        return False
    # These are independently revalidated by checkout_live_request.
    if (not isinstance(env.get("BIGPAW_SHOP_APPROVED_TERMS_SHA256"), str)
            or not re.fullmatch(r"[0-9a-f]{64}",
                                env["BIGPAW_SHOP_APPROVED_TERMS_SHA256"])
            or not isinstance(env.get("BIGPAW_SQUARE_LIVE_ACCESS_TOKEN"), str)
            or len(env["BIGPAW_SQUARE_LIVE_ACCESS_TOKEN"].strip()) < 20
            or not isinstance(env.get("BIGPAW_SQUARE_LIVE_LOCATION_ID"), str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}",
                                env["BIGPAW_SQUARE_LIVE_LOCATION_ID"])):
        return False
    return True


def _session(handler):
    # Checkout only accepts the secure site cookie, never a Bearer token.
    # Duplicated cookie names are deliberately rejected.
    if handler.headers.get("Authorization", ""):
        return None
    raw = handler.headers.get("Cookie", "")
    if not isinstance(raw, str) or len(raw) > 4096:
        return None
    if len(re.findall(r"(?:^|;)\s*bigpaw_session\s*=", raw)) != 1:
        return None
    cookies = SimpleCookie()
    try:
        cookies.load(raw)
        token = cookies["bigpaw_session"].value
    except (KeyError, ValueError):
        return None
    if not _SESSION.fullmatch(token):
        return None
    user = handler.current_user()
    if (not isinstance(user, dict) or user.get("role") != "buyer"
            or not isinstance(user.get("id"), str)
            or not 1 <= len(user["id"]) <= 128):
        return None
    return token, user["id"]


def _origin_ok(handler, base_url, *, mutation):
    u = urlsplit(base_url)
    host = handler.headers.get("Host", "").lower()
    if host != u.netloc:
        return False
    if handler.headers.get("X-Forwarded-Host", "").lower() not in ("", u.netloc):
        return False
    if handler.headers.get("X-Forwarded-Proto", "").lower() not in ("", "https"):
        return False
    if urlsplit(handler.path).query:
        return False
    origin = handler.headers.get("Origin", "")
    if mutation and origin != base_url:
        return False
    if origin and origin != base_url:
        return False
    site = handler.headers.get("Sec-Fetch-Site", "")
    if site and site != "same-origin":
        return False
    return True


def handle_get(handler, *, env=None, base_url="",
               launch_status=None):
    if urlsplit(handler.path).path != "/api/shop/checkout/config":
        return False
    env = dict(os.environ if env is None else env)
    try:
        status = _load_manifest() if launch_status is None else launch_status
        if not _gate(env, base_url, status):
            return _fail(handler)
        if not _origin_ok(handler, base_url, mutation=False):
            return _fail(handler)
        session = _session(handler)
        if session is None:
            return _fail(handler, "auth_required", 401)
        token, user_id = session
        handler.send_json({
            "ready": True,
            "approved_terms_sha256": env["BIGPAW_SHOP_APPROVED_TERMS_SHA256"],
            "csrf_token": _csrf(env["BIGPAW_SHOP_ORDER_HMAC_SECRET"],
                                token, user_id),
            "shipping_included": True,
        }, 200)
        return True
    except (OSError, ImportError, ValueError, KeyError, TypeError):
        return _fail(handler)


def handle_post(handler, *, env=None, base_url="",
                data_dir=None, rate_limited=None, launch_status=None,
                post_opener=None, get_opener=None):
    if urlsplit(handler.path).path != "/api/shop/checkout":
        return False
    env = dict(os.environ if env is None else env)
    # Fail closed without touching the request body or initializing SQLite.
    try:
        status = _load_manifest() if launch_status is None else launch_status
        if not _gate(env, base_url, status):
            return _fail(handler)
        if not _origin_ok(handler, base_url, mutation=True):
            return _fail(handler, "invalid_origin", 403)
        session = _session(handler)
        if session is None:
            return _fail(handler, "auth_required", 401)
        if (handler.headers.get("Transfer-Encoding")
                or handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower()
                != "application/json"):
            return _fail(handler, "invalid_request", 400)
        try:
            n = int(handler.headers.get("Content-Length", ""))
        except (ValueError, TypeError):
            return _fail(handler, "invalid_request", 400)
        if not 1 <= n <= 4096:
            return _fail(handler, "invalid_request", 400)
        if not callable(rate_limited):
            return _fail(handler)
        token, user_id = session
        if rate_limited("shop_checkout:" + hashlib.sha256(token.encode()).hexdigest(),
                        5, 300):
            return _fail(handler, "rate_limited", 429)
        secret = env["BIGPAW_SHOP_ORDER_HMAC_SECRET"]
        csrf = handler.headers.get("X-Shop-CSRF", "")
        expected = _csrf(secret, token, user_id)
        if (not isinstance(csrf, str)
                or not hmac.compare_digest(csrf, expected)):
            return _fail(handler, "invalid_csrf", 403)
        if data_dir is None or not Path(data_dir).is_dir():
            return _fail(handler, "private_storage_unavailable", 503)
        raw = handler.rfile.read(n)
        if len(raw) != n:
            return _fail(handler, "invalid_request", 400)
        from shop_payments.live_checkout_controller import checkout_live_request
        from shop_payments.live_checkout_intent import LiveCheckoutIntent
        from shop_payments.live_order_ledger import LiveOrderLedger, LiveOrderBlocked
        private_env = {**env, "BIGPAW_ENV": "live"}
        trusted_session_id = hmac.new(
            secret.encode(), ("bigpaw-shop-session-v1\0" + token +
                              "\0" + user_id).encode(),
            hashlib.sha256).hexdigest()
        kwargs = {
            "intent": LiveCheckoutIntent(LiveOrderLedger(
                Path(data_dir) / "bigpaw-shop-live-orders.sqlite3")),
            "raw_body": raw, "origin": base_url, "allowed_origin": base_url,
            "csrf_header": csrf, "server_csrf": expected,
            "trusted_session_id": trusted_session_id,
            "server_order_secret": secret,
            "launch_status": status, "private_env": private_env,
        }
        if post_opener is not None:
            kwargs["post_opener"] = post_opener
        if get_opener is not None:
            kwargs["get_opener"] = get_opener
        result = checkout_live_request(**kwargs)
        handler.send_json(result, 200)
        return True
    except (OSError, ImportError, TypeError, ValueError, KeyError):
        # Safe errors: a payment link could already exist; never invite an
        # automatic second attempt or leak credential/provider diagnostics.
        return _fail(handler, "checkout_needs_operator_review", 409)
