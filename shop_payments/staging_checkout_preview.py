"""Password-protected, Sandbox-only shopper-to-Square preview for bigpaw-test.

This route module is never used by the BIG PAW production website. It is
disabled by default. A random, staging-specific Basic Auth password, HTTPS
hostname, Origin check and double-submit CSRF protect test checkout requests.
Payment amounts are calculated from the server-only approved 35-SKU pricebook.
The public Square webhook route stays independent of this authentication.
"""
from __future__ import annotations

import base64
from http import HTTPStatus
from http.cookies import SimpleCookie
import json
import mimetypes
import re
import secrets
import sqlite3
from pathlib import Path
from urllib.parse import urlsplit

from .retail_catalog import load_sale_catalog
from .sandbox_connector import SquareSandboxError, create_square_sandbox_payment_link
from .staging_https_webhook import stage_ready

ROOT = Path(__file__).resolve().parents[1]
HOST = "bigpaw-test-production.up.railway.app"
ORIGIN = "https://" + HOST
CSRF = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
ORDER = re.compile(r"^/api/shop/sandbox/order/(FOOD[0-9a-f]{32})$")
ASSETS = re.compile(
    r"^/assets/(?:shop-products/[a-z0-9-]+|shop-details/"
    r"(?:products/[AOZC][0-9]{2}|shared/(?:acana|orijen|ziwi|charm))/"
    r"[a-z0-9-]+)\.webp$"
)
FILES = {
    "/shop-cart-preview.js": ROOT / "app/shop-cart-preview.js",
    "/shop-detail-images.js": ROOT / "app/shop-detail-images.js",
    "/shop-detail-gallery.js": ROOT / "app/shop-detail-gallery.js",
    "/shop-detail-gallery.css": ROOT / "app/shop-detail-gallery.css",
    "/shop-order-review.js": ROOT / "app/shop-order-review.js",
    "/shop-order-review.css": ROOT / "app/shop-order-review.css",
    "/shop-sandbox-checkout.js": ROOT / "shop_payments/preview_checkout.js",
    "/shop-sandbox-review.js": ROOT / "shop_payments/review_sandbox_checkout.js",
}

def enabled(env):
    username = env.get("BIGPAW_SHOP_STAGE_PREVIEW_USER", "")
    password = env.get("BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD", "")
    return (
        stage_ready(env)
        and env.get("BIGPAW_SHOP_STAGE_PREVIEW_ENABLED") == "1"
        and isinstance(username, str) and re.fullmatch(r"[A-Za-z0-9_-]{4,32}", username)
        and isinstance(password, str) and len(password) >= 32
        and len(password) <= 128
        and all(ch.isalnum() or ch in "_-" for ch in password)
        and env.get("RAILWAY_SERVICE_ID") == "1a1a32bd-e885-4848-a6b5-fde5ef9ac902"
    )

def _send(handler, code, payload, mime="application/json; charset=utf-8", extra=None):
    if isinstance(payload, dict):
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    elif isinstance(payload, bytes):
        body = payload
    else:
        raise ValueError("Unexpected preview response")
    handler.send_response(code)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(len(body)))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("X-Content-Type-Options", "nosniff")
    handler.send_header("X-Robots-Tag", "noindex, nofollow, noarchive")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("X-Frame-Options", "DENY")
    handler.send_header("Vary", "Authorization")
    if extra:
        for k, v in extra.items():
            handler.send_header(k, v)
    handler.end_headers()
    handler.wfile.write(body)

def _authenticated(handler):
    env = handler.server.env
    if not enabled(env):
        _send(handler, 404, {"error": "preview_unavailable"})
        return False
    if handler.headers.get("Host", "").lower() not in (HOST, HOST + ":443"):
        _send(handler, 400, {"error": "wrong_host"})
        return False
    raw = handler.headers.get("Authorization", "")
    if not raw.startswith("Basic ") or len(raw) > 320:
        _send(handler, 401, {"error": "preview_login_required"}, extra={
            "WWW-Authenticate": 'Basic realm="BIG PAW Sandbox test only", charset="UTF-8"'
        })
        return False
    try:
        decoded = base64.b64decode(raw[6:], validate=True).decode("utf-8")
    except (ValueError, UnicodeError):
        decoded = ""
    expected = env["BIGPAW_SHOP_STAGE_PREVIEW_USER"] + ":" + env["BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD"]
    if not secrets.compare_digest(decoded.encode(), expected.encode()):
        _send(handler, 401, {"error": "preview_login_required"}, extra={
            "WWW-Authenticate": 'Basic realm="BIG PAW Sandbox test only", charset="UTF-8"'
        })
        return False
    return True

def _get_cookie(handler):
    cookie = SimpleCookie()
    try:
        cookie.load(handler.headers.get("Cookie", ""))
        return cookie["bigpaw_shop_sandbox_csrf"].value
    except (KeyError, ValueError):
        return ""

def _csrf_valid(handler):
    if handler.headers.get("Origin", "") != ORIGIN:
        return False
    if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
        return False
    cookie = _get_cookie(handler)
    provided = handler.headers.get("X-Shop-CSRF", "")
    return bool(CSRF.fullmatch(cookie) and
                CSRF.fullmatch(provided) and
                secrets.compare_digest(cookie, provided))

def handle_get(handler):
    path = urlsplit(handler.path).path
    allowed = path in ("/shop.html", "/shop-test-orders.html") or path in FILES or path == "/api/shop/sandbox/config" or ORDER.fullmatch(path) or ASSETS.fullmatch(path)
    if not allowed:
        return False
    if not _authenticated(handler):
        return True
    if path == "/api/shop/sandbox/config":
        token = secrets.token_urlsafe(32)
        _send(handler, 200, {"sandbox": True, "ready": True, "shipping_included": True,
                              "real_payments": False, "csrf_token": token}, extra={
            "Set-Cookie": "bigpaw_shop_sandbox_csrf=" + token +
                          "; Path=/api/shop/sandbox; Secure; HttpOnly; SameSite=Strict"
        })
        return True
    match = ORDER.fullmatch(path)
    if match:
        state = handler.server.store.status(match.group(1))
        _send(handler, 404 if state == "not_found" else 200,
              {"order_status": state} if state != "not_found" else {"error": "not_found"})
        return True
    if path == "/shop-test-orders.html":
        from .staging_orders_dashboard import render
        try:
            html = render(handler.server.store)
        except (OSError, ValueError):
            _send(handler, 503, {"error": "test_dashboard_unavailable"})
            return True
        except sqlite3.Error:
            _send(handler, 503, {"error": "test_dashboard_unavailable"})
            return True
        _send(handler, 200, html.encode("utf-8"), "text/html; charset=utf-8")
        return True
    if path == "/shop.html":
        html = (ROOT / "app/shop.html").read_text(encoding="utf-8")
        script = ('shop-sandbox-review.js' if urlsplit(handler.path).query == "order=review"
                  else 'shop-sandbox-checkout.js')
        if "</body>" not in html:
            _send(handler, 503, {"error": "template_unavailable"})
            return True
        html = html.replace("</body>", '<script src="' + script + '" defer></script>\n</body>', 1)
        # No real shopper can confuse this with the unlaunched public store.
        html = html.replace("大型犬専門 BIG PAW｜ドッグフード販売準備中",
                            "【Sandbox専用】BIG PAW ドッグフード決済テスト", 1)
        html = html.replace("</header>",
            '</header><div style="text-align:right;max-width:1180px;margin:10px auto 0;padding:0 16px">'
            '<a id="stageOrdersDashboardLink" href="/shop-test-orders.html" '
            'style="display:inline-block;padding:10px 15px;background:#174f7f;color:white;'
            'border-radius:9px;font-size:13px;font-weight:800">テスト注文管理を見る</a></div>', 1)
        _send(handler, 200, html.encode(), "text/html; charset=utf-8")
        return True
    file = FILES.get(path)
    if file is None:
        file = ROOT / "app" / path.lstrip("/")
    if not file.is_file():
        _send(handler, 404, {"error": "not_found"})
        return True
    mime = "image/webp" if path.endswith(".webp") else (
        "text/css; charset=utf-8" if path.endswith(".css")
        else "text/javascript; charset=utf-8"
    )
    _send(handler, 200, file.read_bytes(), mime)
    return True

def handle_post(handler):
    path = urlsplit(handler.path).path
    if path != "/api/shop/sandbox/checkout":
        return False
    if not _authenticated(handler):
        return True
    if not _csrf_valid(handler):
        _send(handler, 403, {"error": "request_not_authorized"})
        return True
    if handler.headers.get("Transfer-Encoding"):
        _send(handler, 400, {"error": "invalid_body"})
        return True
    try:
        size = int(handler.headers.get("Content-Length", ""))
    except ValueError:
        size = 0
    if size < 1 or size > 4096:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    body = handler.rfile.read(size)
    try:
        obj = json.loads(body)
        if not isinstance(obj, dict) or set(obj) != {"cart", "attempt_id"}:
            raise ValueError("invalid payload")
        cart = obj["cart"]
        if not isinstance(cart, dict) or not 1 <= len(cart) <= 35:
            raise ValueError("invalid cart")
        attempt_id = obj["attempt_id"]
        if not isinstance(attempt_id, str) or not re.fullmatch(
            r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
            attempt_id
        ):
            raise ValueError("invalid checkout attempt")
        local_order_id = "FOOD" + attempt_id.replace("-", "")
        # Sale prices are read only from the server-owned approved pricebook.
        payload, amount = handler.server.store.add_pending_order(
            order_id=local_order_id, cart=cart,
            verified_prices=load_sale_catalog(), shipping_yen=0,
            location_id=handler.server.env["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"]
        )
        prior = handler.server.store.checkout_link_if_exists(local_order_id)
    except (ValueError, TypeError, KeyError, UnicodeError):
        _send(handler, 400, {"error": "invalid_cart"})
        return True
    except OSError:
        _send(handler, 503, {"error": "sandbox_db_unavailable"})
        return True
    try:
        if prior:
            link = prior
        else:
            link = handler.server.checkout_creator(
                payload, token=handler.server.env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]
            )
            handler.server.store.save_link(local_order_id, link)
    except (SquareSandboxError, ValueError, OSError):
        _send(handler, 502, {"error": "sandbox_checkout_unavailable"})
        return True
    _send(handler, 200, {
        "sandbox": True, "checkout_url": link["url"], "order_id": local_order_id,
        "amount_yen": amount, "shipping_yen": 0
    })
    return True
