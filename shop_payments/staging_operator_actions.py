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
TRACKING_PATH = "/api/shop/sandbox/operator/tracking"
REVIEW_PATH = "/api/shop/sandbox/operator/review-customer"
DRYRUN_PATH = "/api/shop/sandbox/operator/simulate-customer-notice"
MAIL_MOCK_PATH = "/api/shop/sandbox/operator/mock-customer-mail"
REFUND_VERIFY_PATH = "/api/shop/sandbox/operator/verify-full-refund"
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
    if kind == "customer_shipment_notice":
        from .sandbox_tracking import SandboxTrackingJournal
        recorded = SandboxTrackingJournal(handler.server.store).read(order_id)
        if recorded:
            draft["body"] = draft["body"].replace(
                "配送会社：【運営が確認して入力】",
                "配送会社：" + recorded["carrier_label"]
            ).replace(
                "追跡番号：【運営が確認して入力】",
                "追跡番号：" + recorded["tracking_number"]
            )
        else:
            draft["body"] += (
                "\\n\\n【未完成】配送会社と追跡番号はまだ登録されていません。"
                "実運送・お客様への送信は行わないでください。"
            )
    review_panel = ""
    extra_header = None
    if kind in ("customer_order_confirmed", "customer_shipment_notice"):
        from .sandbox_customer_review import SandboxCustomerReview
        reviewer = SandboxCustomerReview(handler.server.store)
        opts = {"token": handler.server.env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]}
        if handler.server.shipping_opener is not None:
            opts["opener"] = handler.server.shipping_opener
        try:
            status = reviewer.readiness(order_id, kind, **opts)
        except (SquareSandboxError, ValueError, KeyError):
            status = {"ready": False, "masked": None,
                      "reviewed": False,
                      "review_history": reviewer.reviewed(order_id, kind)}
        if status["ready"] and status["reviewed"]:
            from .sandbox_customer_dispatch import SandboxDryRunOutbox
            dryrun = SandboxDryRunOutbox(handler.server.store)
            if dryrun.inspected(order_id, kind):
                from .sandbox_customer_mail_attempts import SandboxCustomerMailAttempts
                from .staging_orders_dashboard import MOCK_MAIL_LABELS
                attempt = SandboxCustomerMailAttempts(handler.server.store)
                state = attempt.status(order_id, kind)
                if state:
                    review_panel = (
                        '<p><strong>送信シミュレーション完了（テスト記録）。'
                        '実際のメールは未送信です。</strong></p>'
                        '<p>模擬送信履歴：' +
                        escape(MOCK_MAIL_LABELS.get(state, "未確認"), quote=True) +
                        '</p><p>既存の予約を再実行しません。</p>'
                    )
                else:
                    csrf, cookie = new_csrf_cookie()
                    extra_header = {"Set-Cookie": cookie}
                    review_panel = (
                        '<section><h3>メール送信結果のオフライン試験</h3>'
                        '<p>実メールは一切送信せず、成功・拒否・結果不明の'
                        'いずれかの状態をテスト記録します。</p>'
                        '<form method="post" action="' + MAIL_MOCK_PATH + '">'
                        '<input type="hidden" name="order_id" value="' +
                        escape(order_id, quote=True) + '">'
                        '<input type="hidden" name="kind" value="' +
                        escape(kind, quote=True) + '">'
                        '<input type="hidden" name="csrf" value="' +
                        escape(csrf, quote=True) + '">'
                        '<label>模擬結果<select name="outcome" required>'
                        '<option value="">選択してください</option>'
                        '<option value="simulated_accepted">模擬受付成功</option>'
                        '<option value="simulated_refused">模擬受付拒否</option>'
                        '<option value="simulated_unknown">模擬通信結果不明</option>'
                        '</select></label>'
                        '<label><input type="checkbox" name="confirm" value="offline_only" required>'
                        '実メール・仕入先連絡・Square決済などの処理は一切行わないと確認</label>'
                        '<button type="submit">模擬結果だけを記録する（送信しない）</button>'
                        '</form></section>'
                    )
            else:
                csrf, cookie = new_csrf_cookie()
                extra_header = {"Set-Cookie": cookie}
                review_panel = (
                    '<section><p><strong>送信前チェック済み・未送信</strong></p>'
                    '<p>Squareの宛先と本文の最新版を再確認して、'
                    'メールを送らずに送信直前の手順だけテストできます。</p>'
                    '<form method="post" action="' + DRYRUN_PATH + '">'
                    '<input type="hidden" name="order_id" value="' + escape(order_id, quote=True) + '">'
                    '<input type="hidden" name="kind" value="' + escape(kind, quote=True) + '">'
                    '<input type="hidden" name="csrf" value="' + escape(csrf, quote=True) + '">'
                    '<label><input type="checkbox" name="confirm" value="simulate_only" required>'
                    '実メールを送信しないシミュレーションであることを確認</label>'
                    '<button type="submit">送信せずに最終チェックをテストする</button>'
                    '</form></section>'
                )
        elif status["ready"]:
            csrf, cookie = new_csrf_cookie()
            extra_header = {"Set-Cookie": cookie}
            review_panel = (
                '<section><h3>送信前の確認（メールは送られません）</h3>' +
                ('<p><strong>以前の確認は失効しました。'
                 'Squareの宛先または本文が変わったため再確認してください。</strong></p>'
                 if status.get("review_history") else '') +
                '<p>Square Sandbox注文情報の連絡先：' +
                escape(status["masked"], quote=True) +
                '（一部のみ表示、メールアドレスの本人確認は未実施）</p>'
                '<form method="post" action="' + REVIEW_PATH + '">'
                '<input type="hidden" name="order_id" value="' + escape(order_id, quote=True) + '">'
                '<input type="hidden" name="kind" value="' + escape(kind, quote=True) + '">'
                '<input type="hidden" name="csrf" value="' + escape(csrf, quote=True) + '">'
                '<label><input type="checkbox" name="confirm" value="review_only" required>'
                '宛先と下書きを確認し、テスト記録だけを付けます。'
                '実際の送信を承認したことにはなりません。</label>'
                '<button type="submit">送信前チェック済みとして記録（送信しない）</button>'
                '</form></section>'
            )
        else:
            review_panel = (
                '<p>Square Sandboxの連絡先または配送情報が不十分なため、'
                '送信準備の確認はできません。メールは未送信です。</p>'
            )
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
        '<pre>' + escape(draft["body"], quote=True) + '</pre>' +
        review_panel +
        '<p>この画面には送信機能はありません。購入者への通知は未送信です。</p>'
        '<a href="/shop-test-orders.html">注文管理に戻る</a>'
        '</body></html>'
    )
    _send(handler, 200, html.encode("utf-8"), "text/html; charset=utf-8",
          extra=extra_header)
    return True


def handle_customer_review_post(handler) -> bool:
    """Require operator credentials + CSRF + fresh Square GET. NEVER send mail."""
    from .staging_checkout_preview import _send
    from .sandbox_customer_review import SandboxCustomerReview, CUSTOMER_KINDS
    if handler.path != REVIEW_PATH:
        return False
    if not authenticate(handler):
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
    if length < 1 or length > 500:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    raw = handler.rfile.read(length)
    if len(raw) != length:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    try:
        values = parse_qs(raw.decode("ascii"), keep_blank_values=True,
                          strict_parsing=True, max_num_fields=4)
        if set(values) != {"order_id", "kind", "csrf", "confirm"} or any(
            len(v) != 1 for v in values.values()
        ):
            raise ValueError("unexpected_form")
        values = {k: v[0] for k, v in values.items()}
    except (ValueError, UnicodeError):
        _send(handler, 400, {"error": "invalid_form"})
        return True
    if not _csrf_ok(handler, values["csrf"]):
        _send(handler, 403, {"error": "invalid_origin_or_csrf"})
        return True
    if (not ORDER.fullmatch(values["order_id"]) or
        values["kind"] not in CUSTOMER_KINDS or
        values["confirm"] != "review_only"):
        _send(handler, 400, {"error": "invalid_customer_review"})
        return True
    opts = {"token": handler.server.env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]}
    if handler.server.shipping_opener is not None:
        opts["opener"] = handler.server.shipping_opener
    try:
        SandboxCustomerReview(handler.server.store).mark_reviewed(
            values["order_id"], values["kind"], **opts
        )
    except SquareSandboxError:
        _send(handler, 503, {"error": "square_contact_read_unavailable"})
        return True
    except (ValueError, KeyError):
        _send(handler, 409, {"error": "recipient_or_shipment_not_ready"})
        return True
    from urllib.parse import urlencode
    # No outbound send; return only to the private draft inspection page.
    handler.send_response(303)
    handler.send_header("Location", "/api/shop/sandbox/operator/draft?" +
                        urlencode({"order_id": values["order_id"], "kind": values["kind"]}))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Length", "0")
    handler.end_headers()
    return True


def handle_dryrun_post(handler) -> bool:
    """No send operation. Record only an idempotent reviewed dry run."""
    from .staging_checkout_preview import _send
    from .sandbox_customer_dispatch import SandboxDryRunOutbox
    from .sandbox_customer_review import CUSTOMER_KINDS
    if handler.path != DRYRUN_PATH:
        return False
    if not authenticate(handler):
        return True
    if handler.headers.get("Transfer-Encoding"):
        _send(handler, 400, {"error": "invalid_body"})
        return True
    if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
        _send(handler, 415, {"error": "invalid_type"})
        return True
    try:
        size = int(handler.headers.get("Content-Length", ""))
    except ValueError:
        size = 0
    if not 1 <= size <= 500:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    raw = handler.rfile.read(size)
    if len(raw) != size:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    try:
        values = parse_qs(raw.decode("ascii"), keep_blank_values=True,
                          strict_parsing=True, max_num_fields=4)
        if set(values) != {"order_id", "kind", "csrf", "confirm"} or any(
            len(v) != 1 for v in values.values()
        ):
            raise ValueError("invalid_form")
        fields = {k: v[0] for k, v in values.items()}
    except (ValueError, UnicodeError):
        _send(handler, 400, {"error": "invalid_form"})
        return True
    if not _csrf_ok(handler, fields["csrf"]):
        _send(handler, 403, {"error": "invalid_origin_or_csrf"})
        return True
    if (not ORDER.fullmatch(fields["order_id"]) or
        fields["kind"] not in CUSTOMER_KINDS or
        fields["confirm"] != "simulate_only"):
        _send(handler, 400, {"error": "invalid_simulation_request"})
        return True
    opts = {"token": handler.server.env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]}
    if handler.server.shipping_opener is not None:
        opts["opener"] = handler.server.shipping_opener
    try:
        SandboxDryRunOutbox(handler.server.store).simulate_once(
            fields["order_id"], fields["kind"], **opts
        )
    except SquareSandboxError:
        _send(handler, 503, {"error": "square_contact_read_unavailable"})
        return True
    except (ValueError, KeyError):
        _send(handler, 409, {"error": "review_stale_or_simulation_conflict"})
        return True
    from urllib.parse import urlencode
    handler.send_response(303)
    handler.send_header("Location", "/api/shop/sandbox/operator/draft?" +
                        urlencode({"order_id": fields["order_id"], "kind": fields["kind"]}))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Length", "0")
    handler.end_headers()
    return True


def handle_refund_verify_post(handler) -> bool:
    """Verify an existing full Square Sandbox refund; NEVER initiate one."""
    from .staging_checkout_preview import _send
    if handler.path != REFUND_VERIFY_PATH:
        return False
    if not authenticate(handler):
        return True
    if handler.headers.get("Transfer-Encoding"):
        _send(handler, 400, {"error": "invalid_body"})
        return True
    if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
        _send(handler, 415, {"error": "invalid_type"})
        return True
    try:
        size = int(handler.headers.get("Content-Length", ""))
    except ValueError:
        size = 0
    if not 1 <= size <= 400:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    raw = handler.rfile.read(size)
    if len(raw) != size:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    try:
        values = parse_qs(raw.decode("ascii"), keep_blank_values=True,
                          strict_parsing=True, max_num_fields=3)
        if set(values) != {"order_id", "csrf", "confirm"} or any(
            len(v) != 1 for v in values.values()
        ):
            raise ValueError("invalid_form")
        data = {k: v[0] for k, v in values.items()}
    except (ValueError, UnicodeError):
        _send(handler, 400, {"error": "invalid_form"})
        return True
    if not _csrf_ok(handler, data["csrf"]):
        _send(handler, 403, {"error": "invalid_origin_or_csrf"})
        return True
    if not ORDER.fullmatch(data["order_id"]) or data["confirm"] != "verify_read_only":
        _send(handler, 400, {"error": "invalid_refund_verification"})
        return True
    # Only a Sandbox-verified full refund on exactly the same order, currency,
    # location and payment can mark the test procurement journal refunded.
    # Never use Square's create-refund endpoint or alter payment amounts.
    opts = {"token": handler.server.env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]}
    if handler.server.refund_opener is not None:
        opts["opener"] = handler.server.refund_opener
    try:
        SandboxProcurementOps(handler.server.store).confirm_full_refund(
            data["order_id"], **opts
        )
    except SquareSandboxError:
        _send(handler, 503, {"error": "square_refund_read_unavailable"})
        return True
    except (ValueError, KeyError):
        _send(handler, 409, {"error": "full_sandbox_refund_not_confirmed"})
        return True
    handler.send_response(303)
    handler.send_header("Location", "/shop-test-orders.html?refund_verified=1")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Length", "0")
    handler.end_headers()
    return True


def handle_mock_mail_post(handler) -> bool:
    """Operator-only no-network email state test. Cannot call mail providers."""
    from .staging_checkout_preview import _send
    from .sandbox_customer_mail_attempts import SandboxCustomerMailAttempts, OUTCOMES
    from .sandbox_customer_review import CUSTOMER_KINDS
    if handler.path != MAIL_MOCK_PATH:
        return False
    if not authenticate(handler):
        return True
    if handler.headers.get("Transfer-Encoding"):
        _send(handler, 400, {"error": "invalid_body"})
        return True
    if handler.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/x-www-form-urlencoded":
        _send(handler, 415, {"error": "invalid_type"})
        return True
    try:
        size = int(handler.headers.get("Content-Length", ""))
    except ValueError:
        size = 0
    if not 1 <= size <= 560:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    raw = handler.rfile.read(size)
    if len(raw) != size:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    try:
        values = parse_qs(raw.decode("ascii"), keep_blank_values=True,
                          strict_parsing=True, max_num_fields=5)
        if set(values) != {"order_id", "kind", "csrf", "confirm", "outcome"} or any(
            len(v) != 1 for v in values.values()
        ):
            raise ValueError("invalid_form")
        fields = {k: v[0] for k, v in values.items()}
    except (ValueError, UnicodeError):
        _send(handler, 400, {"error": "invalid_form"})
        return True
    if not _csrf_ok(handler, fields["csrf"]):
        _send(handler, 403, {"error": "invalid_origin_or_csrf"})
        return True
    if (not ORDER.fullmatch(fields["order_id"]) or
        fields["kind"] not in CUSTOMER_KINDS or
        fields["outcome"] not in OUTCOMES or
        fields["confirm"] != "offline_only"):
        _send(handler, 400, {"error": "invalid_mock_mail_request"})
        return True
    opts = {"sandbox_token": handler.server.env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"],
            "outcome": fields["outcome"]}
    if handler.server.shipping_opener is not None:
        opts["opener"] = handler.server.shipping_opener
    try:
        SandboxCustomerMailAttempts(handler.server.store).simulate_attempt_once(
            fields["order_id"], fields["kind"], **opts
        )
    except SquareSandboxError:
        _send(handler, 503, {"error": "square_contact_read_unavailable"})
        return True
    except (ValueError, KeyError):
        _send(handler, 409, {"error": "mail_review_expired_or_attempt_conflict"})
        return True
    from urllib.parse import urlencode
    handler.send_response(303)
    handler.send_header("Location", "/api/shop/sandbox/operator/draft?" +
                        urlencode({"order_id": fields["order_id"], "kind": fields["kind"]}))
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Length", "0")
    handler.end_headers()
    return True


def handle_tracking_post(handler) -> bool:
    """Manually record a shipping reference; NEVER send it to a recipient."""
    from .staging_checkout_preview import _send
    from .sandbox_tracking import SandboxTrackingJournal
    if handler.path != TRACKING_PATH:
        return False
    if not authenticate(handler):
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
    if not 1 <= length <= 600:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    raw = handler.rfile.read(length)
    if len(raw) != length:
        _send(handler, 400, {"error": "invalid_body"})
        return True
    try:
        form = parse_qs(raw.decode("ascii"), strict_parsing=True,
                        keep_blank_values=True, max_num_fields=5)
        if set(form) != {"order_id", "carrier_code", "tracking_number", "csrf", "confirm"} or any(
            len(v) != 1 for v in form.values()
        ):
            raise ValueError("invalid_form")
        fields = {k: v[0] for k, v in form.items()}
    except (UnicodeError, ValueError):
        _send(handler, 400, {"error": "invalid_form"})
        return True
    if not _csrf_ok(handler, fields["csrf"]):
        _send(handler, 403, {"error": "invalid_origin_or_csrf"})
        return True
    if fields["confirm"] != "record_only" or not ORDER.fullmatch(fields["order_id"]):
        _send(handler, 400, {"error": "invalid_operator_action"})
        return True
    try:
        SandboxTrackingJournal(handler.server.store).record_once(
            fields["order_id"], fields["carrier_code"], fields["tracking_number"]
        )
    except ValueError:
        _send(handler, 409, {"error": "paid_shipped_order_or_reference_required"})
        return True
    handler.send_response(303)
    handler.send_header("Location", "/shop-test-orders.html?tracking=1")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Referrer-Policy", "no-referrer")
    handler.send_header("Content-Length", "0")
    handler.end_headers()
    return True


def handle_post(handler) -> bool:
    """Operator-only Sandbox stage update, or independent tracking record."""
    if handler.path == TRACKING_PATH:
        return handle_tracking_post(handler)
    if handler.path == REVIEW_PATH:
        return handle_customer_review_post(handler)
    if handler.path == DRYRUN_PATH:
        return handle_dryrun_post(handler)
    if handler.path == MAIL_MOCK_PATH:
        return handle_mock_mail_post(handler)
    if handler.path == REFUND_VERIFY_PATH:
        return handle_refund_verify_post(handler)
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
