"""Isolated localhost-only preview of the BIG PAW Square Sandbox checkout.

NEVER imported or served by BIG PAW production app/backend/server.py.
Run locally: PYTHONPATH=. python3 -m shop_payments.local_preview
Only accepts Square *Sandbox* credentials from environment variables;
binds to 127.0.0.1, never a public network interface.
"""
from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import re
import secrets
from urllib.parse import urlsplit

from .retail_catalog import load_sale_catalog
from .sandbox_reconcile import retrieve_verified_sandbox_payment
from .sandbox_connector import (
    SandboxOrderStore, SquareSandboxError, create_square_sandbox_payment_link,
)

ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = {
    "/shop-cart-preview.js": ROOT / "app" / "shop-cart-preview.js",
    "/shop-detail-images.js": ROOT / "app" / "shop-detail-images.js",
    "/shop-detail-gallery.js": ROOT / "app" / "shop-detail-gallery.js",
    "/shop-detail-gallery.css": ROOT / "app" / "shop-detail-gallery.css",
    "/shop-order-review.js": ROOT / "app" / "shop-order-review.js",
    "/shop-order-review.css": ROOT / "app" / "shop-order-review.css",
    "/shop-sandbox-checkout.js": ROOT / "shop_payments" / "preview_checkout.js",
}
ASSET_PATH = re.compile(r"^/assets/(?:shop-products/[a-z0-9-]+|shop-details/(?:products/[AOZC][0-9]{2}|shared/(?:acana|orijen|ziwi|charm))/[a-z0-9-]+)\.webp$")
ORDER_PATH = re.compile(r"^/api/shop/sandbox/order/(FOOD[A-Za-z0-9_-]{20,60})$")
CSRF_PATTERN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
MAX_BODY = 4096


def sandbox_configured() -> bool:
    names = (
        "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN",
        "BIGPAW_SQUARE_SANDBOX_LOCATION_ID",
        "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY",
        "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL",
    )
    return all(os.environ.get(name, "").strip() for name in names) and os.environ[
        "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL"].startswith("https://")


class PreviewServer(ThreadingHTTPServer):
    allow_reuse_address = True

    def __init__(self, port=8765, store=None):
        self.store = store or SandboxOrderStore(
            os.environ.get("BIGPAW_SQUARE_SANDBOX_DB", str(ROOT / ".bigpaw-square-sandbox.sqlite3"))
        )
        # Hardcoded loopback; no externally hosted checkout or public API.
        super().__init__(("127.0.0.1", port), PreviewHandler)


class PreviewHandler(BaseHTTPRequestHandler):
    server: PreviewServer

    def log_message(self, fmt, *args):
        # Avoid printing cookies, raw requests, order details, tokens or webhook payloads.
        return None

    def _valid_host(self):
        allowed = {"127.0.0.1:%s" % self.server.server_port,
                   "localhost:%s" % self.server.server_port}
        return self.headers.get("Host", "") in allowed

    def _headers(self, status, mime, body_size, *, cookie=None):
        self.send_response(status)
        self.send_header("Content-Type", mime)
        self.send_header("Content-Length", str(body_size))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        if cookie:
            self.send_header("Set-Cookie", cookie)
        self.end_headers()

    def _respond(self, status, data, *, cookie=None):
        raw = json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        self._headers(status, "application/json; charset=utf-8", len(raw), cookie=cookie)
        self.wfile.write(raw)

    def _serve_bytes(self, content, mime):
        self._headers(HTTPStatus.OK, mime, len(content))
        self.wfile.write(content)

    def _csrf_ok(self):
        host = self.headers.get("Host", "")
        origin = "http://" + host
        if not self._valid_host() or self.headers.get("Origin", "") != origin:
            return False
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return False
        try:
            cookies = SimpleCookie()
            cookies.load(self.headers.get("Cookie", ""))
            stored = cookies.get("bigpaw_shop_sandbox_csrf")
            token = stored.value if stored else ""
        except Exception:
            return False
        return bool(CSRF_PATTERN.fullmatch(token) and secrets.compare_digest(
            token, self.headers.get("X-Shop-CSRF", "")
        ))

    def do_GET(self):
        if not self._valid_host():
            return self._respond(HTTPStatus.BAD_REQUEST, {"error": "invalid_host"})
        path = urlsplit(self.path).path
        if path == "/api/shop/sandbox/config":
            token = secrets.token_urlsafe(32)
            cookie = "bigpaw_shop_sandbox_csrf=%s; Path=/api/shop/sandbox; HttpOnly; SameSite=Strict" % token
            return self._respond(HTTPStatus.OK, {
                "sandbox": True, "ready": sandbox_configured(),
                "csrf_token": token, "shipping_included": True,
                "real_payments": False,
            }, cookie=cookie)
        match = ORDER_PATH.fullmatch(path)
        if match:
            # Status is a capability URL with 192+ bits of random entropy. Local only.
            state = self.server.store.status(match.group(1))
            return self._respond(HTTPStatus.OK if state != "not_found" else HTTPStatus.NOT_FOUND, {
                "order_status": state,
            })
        if path == "/":
            self.send_response(HTTPStatus.FOUND)
            self.send_header("Location", "/shop.html")
            self.end_headers()
            return
        if path == "/shop.html":
            html = (ROOT / "app" / "shop.html").read_text(encoding="utf-8")
            # This injection exists ONLY in this local preview handler. It does not
            # alter the public shop.html or production deployment.
            script = '<script src="shop-sandbox-checkout.js" defer></script>'
            if script in html or "</body>" not in html:
                return self._respond(HTTPStatus.INTERNAL_SERVER_ERROR, {"error": "unexpected_template"})
            html = html.replace("</body>", script + "\n</body>", 1)
            return self._serve_bytes(html.encode("utf-8"), "text/html; charset=utf-8")
        if path in PUBLIC_FILES:
            file_path = PUBLIC_FILES[path]
            mime = "text/css; charset=utf-8" if path.endswith(".css") else "text/javascript; charset=utf-8"
        elif ASSET_PATH.fullmatch(path):
            file_path = ROOT / "app" / path.lstrip("/")
            mime = "image/webp"
        else:
            return self._respond(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        if not file_path.is_file():
            return self._respond(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        return self._serve_bytes(file_path.read_bytes(), mime)

    def _read_body(self, *, max_bytes):
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            return None
        if length < 1 or length > max_bytes:
            return None
        data = self.rfile.read(length)
        return data if len(data) == length else None

    def do_POST(self):
        if not self._valid_host():
            return self._respond(HTTPStatus.BAD_REQUEST, {"error": "invalid_host"})
        path = urlsplit(self.path).path
        if path == "/api/shop/sandbox/webhook":
            if not sandbox_configured():
                return self._respond(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "sandbox_not_configured"})
            body = self._read_body(max_bytes=256_000)
            if body is None:
                return self._respond(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, {"error": "bad_body"})
            try:
                status = self.server.store.accept_webhook(
                    raw_body=body,
                    signature_header=self.headers.get("X-Square-Hmacsha256-Signature", ""),
                    signature_key=os.environ["BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY"],
                    notification_url=os.environ["BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL"],
                    payment_lookup=lambda pid: retrieve_verified_sandbox_payment(
                        pid, token=os.environ["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]
                    ),
                )
            except ValueError:
                return self._respond(HTTPStatus.FORBIDDEN, {"error": "invalid_signature_or_event"})
            except SquareSandboxError:
                return self._respond(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "square_verification_unavailable"})
            # Ask Square to retry when order-link creation is racing or the
            # independent Square Payments API cannot yet confirm completion.
            if status in ("unmatched", "unverified"):
                return self._respond(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "awaiting_square_confirmation"})
            return self._respond(HTTPStatus.OK, {"ok": True})
        if path != "/api/shop/sandbox/checkout":
            return self._respond(HTTPStatus.NOT_FOUND, {"error": "not_found"})
        if not self._csrf_ok():
            return self._respond(HTTPStatus.FORBIDDEN, {"error": "request_not_authorized"})
        if not sandbox_configured():
            return self._respond(HTTPStatus.SERVICE_UNAVAILABLE, {"error": "sandbox_not_configured"})
        raw = self._read_body(max_bytes=MAX_BODY)
        if raw is None:
            return self._respond(HTTPStatus.BAD_REQUEST, {"error": "invalid_payload"})
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict) or set(payload) != {"cart", "attempt_id"}:
                raise ValueError("Only product IDs, quantities and attempt ID are accepted")
            cart = payload["cart"]
            # Do not accept client-supplied prices, shipping, addresses, or totals.
            if not isinstance(cart, dict) or len(cart) > 35:
                raise ValueError("Invalid cart")
            attempt_id = payload["attempt_id"]
            if not isinstance(attempt_id, str) or not re.fullmatch(
                r"[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}",
                attempt_id,
            ):
                raise ValueError("Invalid random checkout attempt")
            order_id = "FOOD" + attempt_id.replace("-", "")
            order, amount = self.server.store.add_pending_order(
                order_id=order_id, cart=cart,
                verified_prices=load_sale_catalog(), shipping_yen=0,
                location_id=os.environ["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
            )
            previous_link = self.server.store.checkout_link_if_exists(order_id)
        except (ValueError, TypeError, KeyError):
            return self._respond(HTTPStatus.BAD_REQUEST, {"error": "invalid_cart"})
        try:
            if previous_link:
                link = previous_link
            else:
                link = create_square_sandbox_payment_link(
                    order, token=os.environ["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]
                )
                self.server.store.save_link(order_id, link)
        except (SquareSandboxError, ValueError, OSError):
            # Keep the pending record; never silently authorize a second charge.
            return self._respond(HTTPStatus.BAD_GATEWAY, {"error": "square_sandbox_unavailable"})
        return self._respond(HTTPStatus.OK, {
            "sandbox": True,
            "checkout_url": link["url"], "order_id": order_id,
            "amount_yen": amount, "shipping_yen": 0,
        })


def main():
    import argparse
    parser = argparse.ArgumentParser(description="BIG PAW localhost-only Square Sandbox preview")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    server = PreviewServer(port=args.port)
    print("Sandbox-only preview: http://127.0.0.1:%s/shop.html" % server.server_port, flush=True)
    print("Square Sandbox configured:", sandbox_configured(), flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
