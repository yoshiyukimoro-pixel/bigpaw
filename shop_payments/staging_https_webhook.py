"""Standalone Square Sandbox HTTPS-webhook backend (TLS terminated by host).

NEVER import or run from BIG PAW production. Deployment is disabled by default.
Only a dedicated, isolated test service may opt in. There are no shopper,
operator, checkout, download, administrative or database read HTTP endpoints.
The only public paths are GET /healthz and POST /api/shop/sandbox/webhook.

The webhook acknowledges a Square event promptly after verification, before
triggering a daemon thread for optional, idempotent test operator email. A
crash after payment confirmation may leave an unsent draft; the durable
SQLite journal must be audited before public release.
"""
from __future__ import annotations

import json
import os
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Thread
from urllib.parse import urlsplit

from .sandbox_connector import SandboxOrderStore, SquareSandboxError, create_square_sandbox_payment_link
from .sandbox_reconcile import retrieve_verified_sandbox_payment
from .sandbox_auto_notify import maybe_notify_verified_payment
from .sandbox_runtime_guard import is_allowed_sandbox_runtime

WEBHOOK_PATH = "/api/shop/sandbox/webhook"
MAX_EVENT_BYTES = 256_000
REQUIRED_SECRETS = (
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL",
    "BIGPAW_SQUARE_SANDBOX_LOCATION_ID",
)


def stage_identity_ok(env: dict) -> bool:
    """Can start the isolated test server, without enabling webhook processing."""
    if env.get("BIGPAW_ENV") != "sandbox":
        return False
    if env.get("BIGPAW_SHOP_STAGING_ISOLATED") != "1":
        return False
    if env.get("BIGPAW_SHOP_STAGING_HTTPS_ENABLED") != "1":
        return False
    raw_url = env.get("BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL", "")
    if not isinstance(raw_url, str):
        return False
    url = urlsplit(raw_url)
    if (url.scheme != "https" or not url.hostname or url.username
            or url.password or url.query or url.fragment
            or url.port not in (None, 443) or url.path != WEBHOOK_PATH):
        return False
    if not is_allowed_sandbox_runtime(env):
        return False
    # Existing bigpaw-test must use only its already-owned domain.
    if env.get("RAILWAY_SERVICE_ID") == "1a1a32bd-e885-4848-a6b5-fde5ef9ac902":
        if url.hostname != "bigpaw-test-production.up.railway.app":
            return False
    return True


def stage_ready(env: dict) -> bool:
    """Only live Square credentials enable the public webhook route."""
    return stage_identity_ok(env) and all(
        isinstance(env.get(k), str) and bool(env[k].strip())
        for k in REQUIRED_SECRETS
    )


class StageWebhookServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, *, env: dict, store: SandboxOrderStore, host="127.0.0.1", port=0,
                 payment_lookup=None, notify=None, checkout_creator=None):
        if not stage_identity_ok(env):
            raise ValueError("Dedicated Square Sandbox staging identity required")
        self.env = dict(env)
        self.store = store
        self.payment_lookup = payment_lookup or (
            lambda payment_id: retrieve_verified_sandbox_payment(
                payment_id, token=self.env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]
            )
        )
        self.notify = notify or maybe_notify_verified_payment
        self.checkout_creator = checkout_creator or create_square_sandbox_payment_link
        super().__init__((host, port), StageWebhookHandler)


class StageWebhookHandler(BaseHTTPRequestHandler):
    server: StageWebhookServer

    def log_message(self, fmt, *args):
        # Never log signed request contents, tokens, addresses or payment IDs.
        pass

    def _answer(self, status: int, code: str):
        payload = json.dumps({"status": code}, separators=(",", ":")).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/healthz":
            return self._answer(
                HTTPStatus.OK,
                "sandbox_webhook_ready" if stage_ready(self.server.env)
                else "sandbox_webhook_standby",
            )
        # Optional password-gated customer checkout preview, never production.
        from .staging_checkout_preview import handle_get
        if handle_get(self):
            return
        return self._answer(HTTPStatus.NOT_FOUND, "not_found")

    def do_POST(self):
        if self.path != WEBHOOK_PATH:
            from .staging_checkout_preview import handle_post
            if handle_post(self):
                return
            return self._answer(HTTPStatus.NOT_FOUND, "not_found")
        if not stage_ready(self.server.env):
            return self._answer(HTTPStatus.SERVICE_UNAVAILABLE, "sandbox_not_configured")
        if self.headers.get("Square-Environment", "").lower() != "sandbox":
            return self._answer(HTTPStatus.FORBIDDEN, "invalid_environment")
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            return self._answer(HTTPStatus.UNSUPPORTED_MEDIA_TYPE, "invalid_media_type")
        if self.headers.get("Transfer-Encoding"):
            return self._answer(HTTPStatus.BAD_REQUEST, "invalid_body")
        try:
            size = int(self.headers.get("Content-Length", ""))
        except ValueError:
            return self._answer(HTTPStatus.BAD_REQUEST, "invalid_body")
        if not (1 <= size <= MAX_EVENT_BYTES):
            return self._answer(HTTPStatus.REQUEST_ENTITY_TOO_LARGE, "invalid_body")
        raw = self.rfile.read(size)
        if len(raw) != size:
            return self._answer(HTTPStatus.BAD_REQUEST, "invalid_body")
        try:
            state = self.server.store.accept_webhook(
                raw_body=raw,
                signature_header=self.headers.get("X-Square-Hmacsha256-Signature", ""),
                signature_key=self.server.env["BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY"],
                notification_url=self.server.env["BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL"],
                payment_lookup=self.server.payment_lookup,
            )
        except ValueError:
            return self._answer(HTTPStatus.FORBIDDEN, "invalid_signature_or_event")
        except (SquareSandboxError, TimeoutError, OSError):
            return self._answer(HTTPStatus.SERVICE_UNAVAILABLE, "sandbox_verification_unavailable")
        if state in ("unmatched", "unverified"):
            return self._answer(HTTPStatus.SERVICE_UNAVAILABLE, "awaiting_square_confirmation")
        if state == "paid":
            # Square recommends acknowledging promptly. Never delay its
            # response for Resend (an independent external service).
            Thread(
                target=self.server.notify,
                kwargs={"store": self.server.store, "webhook_status": state,
                        "raw_body": raw, "env": self.server.env},
                daemon=True,
                name="sandbox-operator-mail-once",
            ).start()
        return self._answer(HTTPStatus.OK, "received")


def main():
    env = dict(os.environ)
    if not stage_identity_ok(env):
        raise SystemExit("Disabled: dedicated Square Sandbox staging identity required")
    db = env.get("BIGPAW_SHOP_SANDBOX_DB", "")
    if not db:
        raise SystemExit("Dedicated persistent Sandbox DB path missing")
    db_path = Path(db).resolve()
    if not db_path.parent.is_dir():
        raise SystemExit("Sandbox persistent data directory missing")
    port = int(env.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise SystemExit("Invalid staging port")
    server = StageWebhookServer(
        env=env, store=SandboxOrderStore(db_path),
        host="0.0.0.0", port=port,
    )
    # One explicitly selected test order may be seeded on this isolated
    # test service; never from a public endpoint or from production.
    from .staging_seed_boot import create_enabled_test_link
    create_enabled_test_link(env)
    # An independently verified prior payment may need its one-time operator
    # notice when the Resend key was installed after the payment. This call
    # is disabled unless all exact sandbox, service and mail opt-ins match.
    from .staging_paid_mail_once import maybe_send_verified_test_order
    maybe_send_verified_test_order(env)
    # Hosting must terminate HTTPS and forward to this private HTTP port.
    # The configured Square notification URL is exact and never reconstructed.
    print("BIGPAW_SANDBOX_WEBHOOK_READY", flush=True)
    try:
        server.serve_forever(poll_interval=0.1)
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
