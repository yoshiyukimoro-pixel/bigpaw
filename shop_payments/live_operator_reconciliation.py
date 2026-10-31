"""Dormant, operator-only Square live payment reconciliation endpoint.

Enabled only by an explicit production environment switch. This operation
performs Square GET requests and records a verified local payment state; it
never creates/charges/refunds payments, ships orders, or contacts customers.
"""
from __future__ import annotations

from http.cookies import SimpleCookie
import re
import secrets
from urllib.parse import urlsplit

from .live_order_ledger import LiveOrderBlocked, LiveOrderLedger

TOKEN = re.compile(r"^[A-Za-z0-9_-]{32,128}$")
ORDER = re.compile(r"^FOOD[0-9a-f]{32}$")
PAYMENT = re.compile(r"^[A-Za-z0-9_-]{8,192}$")
COOKIE = "__Host-bigpaw_live_shop_csrf"


def enabled(env: dict, *, is_production: bool) -> bool:
    """Require deliberate production enablement and a dedicated live key."""
    return bool(
        is_production
        and env.get("BIGPAW_SHOP_LIVE_OPERATOR_RECONCILIATION_ENABLED") == "1"
        and isinstance(env.get("BIGPAW_SQUARE_LIVE_ACCESS_TOKEN"), str)
        and len(env["BIGPAW_SQUARE_LIVE_ACCESS_TOKEN"].strip()) >= 32
    )


def _same_origin(handler, base_url: str) -> bool:
    try:
        base = urlsplit(base_url)
        expected_host = (base.hostname or "").lower()
        host = handler.headers.get("Host", "").lower().split(":", 1)[0]
        return bool(
            base.scheme == "https" and expected_host and host == expected_host
            and handler.headers.get("Origin") == base_url.rstrip("/")
        )
    except (TypeError, ValueError):
        return False


def issue_csrf(handler, *, env: dict, is_production: bool,
               base_url: str) -> bool:
    if handler.path.split("?", 1)[0] != "/api/operator/shop-orders/reconcile-token":
        return False
    if not enabled(env, is_production=is_production):
        handler.send_json({"error": "reconciliation_unavailable"}, 404)
        return True
    user = handler.require(["operator"])
    if not user:
        return True
    token = secrets.token_urlsafe(32)
    handler.send_json(
        {"csrf_token": token},
        extra={"Set-Cookie": f"{COOKIE}={token}; Path=/; Secure; HttpOnly; SameSite=Strict",
               "Cache-Control": "private, no-store"},
    )
    return True


def handle_shipping_address_post(handler, *, env: dict,
                                 is_production: bool, base_url: str,
                                 data_dir) -> bool:
    """OFF by default: operator gets one verified live shipping destination.

    POST requires production-only launch switches, operator session, strict
    HTTPS Origin and double-submit CSRF. This does not dispatch, email,
    update the journal, or store recipient PII.
    """
    if handler.path.split("?", 1)[0] != "/api/operator/shop-orders/shipping-address":
        return False
    if not (enabled(env, is_production=is_production)
            and env.get("BIGPAW_SHOP_LIVE_ADDRESS_VIEW_ENABLED") == "1"):
        handler.send_json({"error": "shipping_address_unavailable"}, 404)
        return True
    if not _same_origin(handler, base_url):
        handler.send_json({"error": "invalid_origin_or_csrf"}, 403)
        return True
    if (handler.headers.get("Transfer-Encoding")
            or handler.headers.get("Content-Type","").split(";",1)[0].strip().lower()
                != "application/json"):
        handler.send_json({"error": "invalid_shipping_request"}, 400)
        return True
    try:
        size = int(handler.headers.get("Content-Length","0"))
    except ValueError:
        size = 0
    if not 1 <= size <= 1024:
        handler.send_json({"error": "invalid_shipping_request"}, 400)
        return True
    user = handler.require(["operator"])
    if not user:
        return True
    try:
        cookies = SimpleCookie()
        cookies.load(handler.headers.get("Cookie", ""))
        cookie_token = cookies[COOKIE].value
    except (KeyError, ValueError):
        cookie_token = ""
    body = handler.json_body()
    token = body.get("csrf_token") if isinstance(body,dict) else None
    if (not isinstance(token,str) or not TOKEN.fullmatch(token)
            or not TOKEN.fullmatch(cookie_token)
            or not secrets.compare_digest(token,cookie_token)):
        handler.send_json({"error":"invalid_origin_or_csrf"},403)
        return True
    if (not isinstance(body,dict)
            or set(body) != {"order_id","csrf_token","confirmation"}
            or not isinstance(body["order_id"],str)
            or not ORDER.fullmatch(body["order_id"])
            or body["confirmation"] != "view_delivery_label_once"):
        handler.send_json({"error":"invalid_shipping_request"},400)
        return True
    path = data_dir / "bigpaw-shop-live-orders.sqlite3"
    if not path.is_file():
        handler.send_json({"error":"verified_paid_order_required"},409)
        return True
    try:
        from .live_shipping_address_view import read_live_recipient_for_dispatch
        ledger = LiveOrderLedger(path)
        trusted = ledger.paid_notice_snapshot(body["order_id"])
        label = read_live_recipient_for_dispatch(
            snapshot=trusted, api_key=env["BIGPAW_SQUARE_LIVE_ACCESS_TOKEN"]
        )
    except LiveOrderBlocked:
        handler.send_json({"error":"verified_paid_order_required"},409)
        return True
    except Exception:
        # The provider or PII must never leak into HTTP errors or logs.
        handler.send_json({"error":"current_paid_shipping_not_verified"},409)
        return True
    handler.send_json(
        {"recipient":label,"temporary_view_only":True,
         "message":"購入者が指定した配送先です。発送伝票への転記前にご確認ください。"},
        extra={"Cache-Control":"private, no-store, max-age=0",
               "Pragma":"no-cache","Referrer-Policy":"no-referrer",
               "X-Robots-Tag":"noindex, nofollow, noarchive",
               "X-Content-Type-Options":"nosniff"}
    )
    return True


def handle_post(handler, *, env: dict, is_production: bool,
                base_url: str, data_dir) -> bool:
    if handle_shipping_address_post(
            handler,env=env,is_production=is_production,
            base_url=base_url,data_dir=data_dir):
        return True
    if handler.path.split("?", 1)[0] != "/api/operator/shop-orders/reconcile":
        return False
    if not enabled(env, is_production=is_production):
        handler.send_json({"error": "reconciliation_unavailable"}, 404)
        return True
    if not _same_origin(handler, base_url):
        handler.send_json({"error": "invalid_origin_or_csrf"}, 403)
        return True
    try:
        size = int(handler.headers.get("Content-Length", "0"))
    except ValueError:
        size = 0
    if not 1 <= size <= 2048:
        handler.send_json({"error": "invalid_reconciliation_request"}, 400)
        return True
    user = handler.require(["operator"])
    if not user:
        return True
    try:
        cookies = SimpleCookie()
        cookies.load(handler.headers.get("Cookie", ""))
        cookie_token = cookies[COOKIE].value
    except (KeyError, ValueError):
        cookie_token = ""
    body = handler.json_body()
    token = body.get("csrf_token") if isinstance(body, dict) else None
    if (not isinstance(token, str) or not TOKEN.fullmatch(token)
            or not TOKEN.fullmatch(cookie_token)
            or not secrets.compare_digest(token, cookie_token)):
        handler.send_json({"error": "invalid_origin_or_csrf"}, 403)
        return True
    if not isinstance(body, dict) or set(body) != {"order_id", "payment_id", "csrf_token"}:
        handler.send_json({"error": "invalid_reconciliation_request"}, 400)
        return True
    if (not isinstance(body["order_id"], str) or not ORDER.fullmatch(body["order_id"])
            or not isinstance(body["payment_id"], str)
            or not PAYMENT.fullmatch(body["payment_id"])):
        handler.send_json({"error": "invalid_reconciliation_request"}, 400)
        return True
    journal_path = data_dir / "bigpaw-shop-live-orders.sqlite3"
    if not journal_path.is_file():
        handler.send_json({"error": "square_verification_failed_or_order_unavailable"}, 409)
        return True
    try:
        ledger = LiveOrderLedger(journal_path)
        try:
            result = ledger.reconcile_payment(
                order_id=body["order_id"], payment_id=body["payment_id"],
                api_key=env["BIGPAW_SQUARE_LIVE_ACCESS_TOKEN"],
                audit_actor_id=user["id"],
            )
        except Exception:
            # Authorized attempts are auditable even when Square is unavailable
            # or its evidence does not match. Never persist the submitted ID.
            try:
                ledger.record_operator_reconciliation_failure(
                    order_id=body["order_id"], actor_id=user["id"])
            except Exception:
                pass
            raise
    except LiveOrderBlocked:
        handler.send_json({"error": "square_verification_failed_or_order_unavailable"}, 409)
        return True
    except Exception:
        # Do not leak credentials, provider payloads, PII, or local paths.
        handler.send_json({"error": "reconciliation_unavailable"}, 503)
        return True
    handler.send_json({"state": result["state"],
                       "new_transition": result["new_transition"],
                       "message": "Squareの最新情報を照合し、操作監査記録を保存しました。"},
                       extra={"Cache-Control": "private, no-store"})
    return True
