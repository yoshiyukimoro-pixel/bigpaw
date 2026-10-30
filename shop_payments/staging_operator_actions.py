"""Separate operator-authenticated manual procurement records: Sandbox ONLY.

This module cannot issue real supplier orders, shipments, payments, refunds,
Square API calls or emails. It writes only into the existing isolated SQLite
test journal, and only for a Square-verified paid order. All POST actions require
their own operator credentials, HTTPS Origin and double-submit CSRF.
"""
from __future__ import annotations

import base64
from http.cookies import SimpleCookie
import re
import secrets
from urllib.parse import parse_qs, urlsplit, parse_qs as parse_query
from urllib.request import urlopen
from html import escape
from .sandbox_procurement import SandboxProcurementOps, TRANSITIONS
from .sandbox_connector import SquareSandboxError

HOST = "bigpaw-test-production.up.railway.app"
ORIGIN = "https://" + HOST
COOKIE = "__Host-bigpaw_shop_operator_csrf"
PATH = "/api/shop/sandbox/operator/transition"
STAGES = frozenset(("supplier_ordered", "supplier_backorder",
                    "received_at_shop", "refund_review", "shipped"))
ORDER = re.compile(r"^FOOD[0-9a-f]{32}$")
TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
USERNAME = re.compile(r"^[A-Za-z0-9_-]{4,32}$")


def enabled(env) -> bool:
    from .staging_checkout_preview import enabled as preview_enabled
    username = env.get("BIGPAW_SHOP_STAGE_OPERATOR_USER", "")
    password = env.get("BIGPAW_SHOP_STAGE_OPERATOR_PASSWORD", "")
    return bool(
        preview_enabled(env) and
        env.get("BIGPAW_SHOP_STAGE_OPERATOR_ENABLED") == "1" and
        isinstance(username, str) and USERNAME.fullmatch(username) and
        isinstance(password, str) and 32 <= len(password) <= 128 and
        all(x.isalnum() or x in "_-" for x in password) and
        (username, password) != (
            env.get("BIGPAW_SHOP_STAGE_PREVIEW_USER"),
            env.get("BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD")
        )
    )


def authenticate(handler) -> bool:
    from .staging_checkout_preview import _send
    env = handler.server.env
    if not enabled(env):
        _send(handler, 404, {"error": "operator_unavailable"})
        return False
    if handler.headers.get("Host", "").lower() not in (HOST, HOST + ":443"):
        _send(handler, 400, {"error": "wrong_host"})
        return False
    raw = handler.headers.get("Authorization", "")
    good = False
    if raw.startswith("Basic ") and len(raw) <= 320:
        try:
            decoded = base64.b64decode(raw[6:], validate=True).decode("utf-8")
            expected = env["BIGPAW_SHOP_STAGE_OPERATOR_USER"] + ":" + env["BIGPAW_SHOP_STAGE_OPERATOR_PASSWORD"]
            good = secrets.compare_digest(decoded.encode(), expected.encode())
        except (UnicodeError, ValueError):
            pass
    if not good:
        _send(handler, 401, {"error": "operator_login_required"}, extra={
            "WWW-Authenticate": 'Basic realm="BIG PAW SHOP OPERATOR Sandbox ONLY", charset="UTF-8"'
        })
    return good


def new_csrf_cookie() -> tuple[str, str]:
    token = secrets.token_urlsafe(32)
    return (token, COOKIE + "=" + token +
            "; Path=/; Secure; HttpOnly; SameSite=Strict")


def _csrf_ok(handler, token: str) -> bool:
    if handler.headers.get("Origin") != ORIGIN:
        return False
    if not isinstance(token, str) or not TOKEN.fullmatch(token):
        return False
    try:
        cookies = SimpleCookie()
        cookies.load(handler.headers.get("Cookie", ""))
        actual = cookies[COOKIE].value
        return bool(TOKEN.fullmatch(actual) and secrets.compare_digest(actual, token))
    except (KeyError, ValueError):
        return False


def handle_draft_get(handler) -> bool:
    """Operator-only HTML preview of an existing unsent notification draft."""
    from .staging_checkout_preview import _send
    from .sandbox_notifications import SandboxNotificationDrafts, ALL_TYPES
    if urlsplit(handler.path).path != "/api/shop/sandbox/operator/draft":
        return False
    if not authenticate(handler):
        return True
    query = parse_query(urlsplit(handler.path).query, keep_blank_values=True)
    if set(query) != {"order_id", "kind"} or any(len(v) != 1 for v in query.values()):
        _send(handler, 400, {"error": "invalid_draft_query"})
        return True
    order_id, kind = query["order_id"][0], query["kind"][0]
    if not ORDER.fullmatch(order_id) or kind not in ALL_TYPES:
        _send(handler, 400, {"error": "invalid_draft_query"})
        return True
    try:
        # This creates no send attempt; merely formats the already queued draft.
        draft = SandboxNotificationDrafts(handler.server.store).preview(order_id, kind)
    except ValueError:
        _send(handler, 404, {"error": "draft_unavailable"})
        return True
    html = (
        '<!doctype html><html lang="ja"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        '<meta name="robots" content="noindex,nofollow">'
        '<title>BIG PAW Sandbox 未送信下書き</title>'
        '<style>body{font:15px/1.7 -apple-system,sans-serif;'
        'max-width:750px;margin:30px auto;padding:0 14px;background:#f7f9fb;'
        'color:#20314b}pre{white-space:pre-wrap;overflow-wrap:anywhere;'
        'background:white;border:1px solid #ddd;padding:16px;border-radius:12px}'
        'a{color:#175c8a}</style></head><body>'
        '<h1>BIG PAW・通知の下書き</h1>'
        '<p><strong>テスト・未送信です。ここからメールは送れません。</strong></p>'
        '<p>送信先種別：' + escape(draft["audience"], quote=True) + '</p>'
        '<h2>' + escape(draft["subject"], quote=True) + '</h2>'
        '<pre>' + escape(draft["body"], quote=True) + '</pre>'
        '<a href="/shop-test-orders.html">注文管理に戻る</a>'
        '</body></html>'
    )
    _send(handler, 200, html.encode("utf-8"), "text/html; charset=utf-8")
    return True


def handle_post(handler) -> bool:
    """POST /api/shop/sandbox/operator/transition; false for other routes."""
    from .staging_checkout_preview import _send
    from .sandbox_runtime_guard import is_allowed_sandbox_runtime
    if handler.path != PATH:
        return False
    if not authenticate(handler):
        return True
    if not is_allowed_sandbox_runtime(handler.server.env):
        _send(handler, 404, {"error": "operator_unavailable"})
        return True
    if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
        _send(handler, 415, {"error": "invalid_type"})
        return True
    if handler.headers.get("Transfer-Encoding"):
        _send(handler, 400, {"error": "invalid_body"})
        return True
    try:
        length = int(handler.headers.get("Content-Length", ""))
    except ValueError:
        length = 0
    if not 1 <= length <= 500:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    raw = handler.rfile.read(length)
    if len(raw) != length:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    try:
        form = parse_qs(raw.decode("ascii"), strict_parsing=True, keep_blank_values=True,
                        max_num_fields=5)
        if set(form) != {"order_id", "stage", "expected", "csrf", "confirm"} or any(
            len(values) != 1 for values in form.values()
        ):
            raise ValueError("unexpected_form")
        values = {k: v[0] for k, v in form.items()}
    except (UnicodeError, ValueError):
        _send(handler, 400, {"error": "invalid_form"})
        return True
    if not _csrf_ok(handler, values["csrf"]):
        _send(handler, 403, {"error": "invalid_origin_or_csrf"})
        return True
    if (not ORDER.fullmatch(values["order_id"]) or
        values["stage"] not in STAGES or
        values["expected"] not in TRANSITIONS or
        values["confirm"] != "record_only"):
        _send(handler, 400, {"error": "invalid_operator_action"})
        return True
    ops = SandboxProcurementOps(handler.server.store)
    try:
        current = ops.state(values["order_id"])
        if current != values["expected"]:
            _send(handler, 409, {"error": "order_changed_reload"})
            return True
        if values["stage"] not in TRANSITIONS.get(current, ()):
            _send(handler, 409, {"error": "stage_transition_not_allowed"})
            return True
        if values["stage"] == "shipped":
            # Requires a fresh read of Square Sandbox shipping details.
            # It NEVER creates a delivery or sends any message.
            kwargs = {"token": handler.server.env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]}
            if handler.server.shipping_opener is not None:
                kwargs["opener"] = handler.server.shipping_opener
            ops.transition(values["order_id"], values["stage"], **kwargs)
        else:
            ops.transition(values["order_id"], values["stage"])
    except SquareSandboxError:
        _send(handler, 503, {"error": "square_sandbox_shipping_check_unavailable"})
        return True
    except (ValueError, KeyError):
        _send(handler, 409, {"error": "verified_paid_order_required"})
        return True
    handler.send_response(303)
    handler.send_header("Location", "/shop-test-orders.html?updated=1")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Length", "0")
    handler.end_headers()
    return True
