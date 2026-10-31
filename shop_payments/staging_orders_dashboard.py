"""Read-only, operator-only overview of the isolated BIG PAW Square Sandbox journal.

No changes to orders, shipping, supplier, refunds, or real emails. No PII:
only opaque internal order IDs, product SKUs, price, and states.
Authenticated by staging_checkout_preview before rendering. Never route
this module from the BIG PAW production app.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape
import sqlite3
from contextlib import closing

from .retail_catalog import load_sale_catalog
from .sandbox_procurement import TRANSITIONS
from .sandbox_tracking import SandboxTrackingJournal, CARRIERS
from .sandbox_service_cases import CASE_TYPES, CASE_STATUSES, NEXT
from urllib.parse import urlencode

JP = timezone(timedelta(hours=9))
PAYMENT_LABELS = {
    "created": "注文準備中",
    "payment_pending": "決済確認待ち",
    "paid": "入金確認済み（Sandbox）",
}
MAIL_LABELS = {
    "accepted": "Resend受付済み",
    "reserved": "送信確認中",
    "unknown": "送信結果が不明・要確認",
}
# These are prepared notifications, not evidence of actual delivery.
DRAFT_LABELS = {
    "operator_new_order": "運営：新規注文の確認",
    "supplier_purchase_request": "仕入先：在庫・納期確認と発注内容",
    "customer_order_confirmed": "お客様：決済・注文確認",
    "operator_supplier_ordered": "運営：仕入先への発注記録",
    "operator_supplier_shortage": "運営：欠品対応",
    "customer_supplier_shortage": "お客様：欠品のご案内",
    "operator_goods_received": "運営：入荷・検品の確認",
    "customer_shipment_notice": "お客様：発送のお知らせ",
    "operator_refund_action_needed": "運営：返金対応の確認",
    "customer_refund_completed": "お客様：返金の確認",
}
MOCK_MAIL_LABELS = {
    "reserved": "送信テスト予約中・結果未確定（実メール未送信）",
    "simulated_accepted": "模擬受付成功（実メール未送信）",
    "simulated_refused": "模擬受付拒否（実メール未送信）",
    "simulated_unknown": "模擬通信結果不明（再操作禁止・実メール未送信）",
}
NEXT_ACTIONS = {
    "awaiting_supplier_order": "入金確認後、仕入先に在庫・納期を確認（自動発注はしません）",
    "supplier_ordered": "仕入先からの入荷を待ち、届いた商品の数量と状態を確認",
    "supplier_backorder": "欠品の連絡・入荷待ちか全額返金かを確認",
    "received_at_shop": "お届け先と梱包内容を確認して発送準備",
    "shipped": "配送状況を確認し、必要な対応を行う",
    "refund_review": "Squareの返金状況を別途確認（この画面では返金しません）",
    "refunded": "返金の記録を確認",
}
PROCUREMENT_LABELS = {
    "awaiting_supplier_order": "仕入れ手配待ち（未発注）",
    "supplier_ordered": "発注済み（テスト記録）",
    "supplier_backorder": "欠品確認中",
    "received_at_shop": "入荷検品済み（テスト記録）",
    "shipped": "発送済み（テスト記録）",
    "refund_review": "返金確認待ち",
    "refunded": "返金確認済み（テスト記録）",
}

def _safe(text) -> str:
    return escape(str(text), quote=True)

def _when(timestamp) -> str:
    if not isinstance(timestamp, int):
        return "—"
    try:
        return datetime.fromtimestamp(timestamp, JP).strftime("%Y/%m/%d %H:%M")
    except (ValueError, OverflowError, OSError):
        return "—"

def render(store, *, csrf: str = "") -> str:
    """Render a sanitized HTML snapshot from the existing SQLite database only."""
    catalog = load_sale_catalog()
    with closing(sqlite3.connect(store.db_file, timeout=5)) as db:
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA query_only=ON")
        records = db.execute("""
            SELECT order_id, state, amount_yen, created_at, paid_at
            FROM orders ORDER BY created_at DESC,order_id DESC LIMIT 100
        """).fetchall()
        mail_states = {}
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='food_operator_email_dispatch'").fetchone():
            mail_states = {
                row["order_id"]: row["status"]
                for row in db.execute("""
                    SELECT order_id,status
                    FROM food_operator_email_dispatch
                    WHERE kind='operator_new_order'
                """).fetchall()
            }
        procurement_states = {}
        if db.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name='food_procurement'").fetchone():
            procurement_states = {
                row["order_id"]: row["stage"]
                for row in db.execute("SELECT order_id,stage FROM food_procurement").fetchall()
            }
        drafts_by_order = {}
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='food_notification_drafts'"
        ).fetchone():
            for notice in db.execute("""
                SELECT order_id,kind,audience FROM food_notification_drafts
                ORDER BY created_at,order_id,kind
            """).fetchall():
                drafts_by_order.setdefault(notice["order_id"], []).append(
                    (notice["kind"], notice["audience"])
                )
        reviewed_customer_drafts = set()
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='food_sandbox_customer_reviews'"
        ).fetchone():
            reviewed_customer_drafts = {
                (x["order_id"], x["kind"]) for x in db.execute(
                    "SELECT order_id,kind FROM food_sandbox_customer_reviews"
                ).fetchall()
            }
        mocked_mail_status = {}
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='food_sandbox_customer_mail_attempts'"
        ).fetchone():
            mocked_mail_status = {
                (x["order_id"], x["kind"]): x["status"]
                for x in db.execute(
                    "SELECT order_id,kind,status "
                    "FROM food_sandbox_customer_mail_attempts"
                ).fetchall()
            }
        service_cases_by_order = {}
        if db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' "
            "AND name='food_sandbox_service_cases'"
        ).fetchone():
            for c in db.execute(
                "SELECT order_id,kind,status FROM food_sandbox_service_cases "
                "ORDER BY created_at,kind"
            ).fetchall():
                if c["kind"] in CASE_TYPES and c["status"] in CASE_STATUSES:
                    service_cases_by_order.setdefault(c["order_id"], []).append(
                        (c["kind"], c["status"])
                    )
        items_by_order = {}
        for row in records:
            items_by_order[row["order_id"]] = [
                (item["sku"], item["quantity"])
                for item in db.execute(
                    "SELECT sku,quantity FROM order_items WHERE order_id=? ORDER BY sku",
                    (row["order_id"],)
                ).fetchall()
            ]
    cards = []
    for order in records:
        order_id = order["order_id"]
        lines = []
        for sku, count in items_by_order[order_id]:
            item = catalog.get(sku)
            name = (item.name + " " + item.size) if item else "商品情報を確認してください"
            lines.append(
                "<li><strong>" + _safe(sku) + "</strong> " +
                _safe(name) + " ×" + _safe(count) + "</li>"
            )
        mail = mail_states.get(order_id)
        mail_text = MAIL_LABELS.get(mail, "未送信・記録なし") if mail else "未送信・記録なし"
        procurement = procurement_states.get(order_id)
        procurement_text = PROCUREMENT_LABELS.get(procurement, "未発注（テスト）") if order["state"] == "paid" else "決済確定前"
        if order["state"] != "paid":
            action = "決済完了の確認待ちです。入金済みとして処理しないでください"
        else:
            action = NEXT_ACTIONS.get(procurement or "awaiting_supplier_order",
                                      "仕入れ状況を確認してください")
        notices = drafts_by_order.get(order_id, [])
        draft_items = "".join(
            "<li>" + _safe(DRAFT_LABELS.get(kind, "通知内容の確認が必要")) +
            "（" + _safe({"operator": "運営", "supplier": "仕入先",
                         "customer": "お客様"}.get(audience, "宛先要確認")) +
            "向け・未送信下書き） " +
            ("【送信テスト：" + _safe(
                MOCK_MAIL_LABELS.get(mocked_mail_status[(order_id, kind)],
                                     "状態確認が必要・実メール未送信")
            ) + "】 " if (order_id, kind) in mocked_mail_status else "") +
            ("【送信前チェックの記録あり・現在の有効性は要再照合】 " if
             (order_id, kind) in reviewed_customer_drafts else
             "【送信前未チェック】 " if audience == "customer" else "") +
            '<a href="/api/shop/sandbox/operator/draft?' +
            _safe(urlencode({"order_id": order_id, "kind": kind})) +
            '">下書き本文を見る（送信されません）</a></li>'
            for kind, audience in notices
        )
        drafts_html = (
            '<details class="drafts"><summary>通知の下書き：' +
            str(len(notices)) + "件（メールは送られません）</summary><ul>" +
            draft_items + "</ul></details>"
        ) if notices else '<p class="draft-empty">通知の下書きはまだありません</p>'
        # Operator-only sandbox stage records; never actually issue purchases,
        # send goods or refund payments. All allowed actions require paid state.
        allowed_actions = {
            "supplier_ordered": "仕入先へ発注したことをテスト記録",
            "supplier_backorder": "欠品をテスト記録",
            "received_at_shop": "入荷・検品をテスト記録",
            "refund_review": "返金確認が必要とテスト記録",
            "shipped": "発送済みをテスト記録（Square配送先の照合必須）",
        }
        current_stage = procurement or "awaiting_supplier_order"
        transitions = (TRANSITIONS.get(current_stage, ()) if
                       order["state"] == "paid" and csrf else ())
        forms = []
        for candidate, label in allowed_actions.items():
            if candidate not in transitions:
                continue
            # Form fields contain no Square ID, card data, supplier contact or PII.
            forms.append(
                '<form method="post" action="/api/shop/sandbox/operator/transition" class="stage-form">'
                '<input type="hidden" name="order_id" value="' + _safe(order_id) + '">'
                '<input type="hidden" name="stage" value="' + _safe(candidate) + '">'
                '<input type="hidden" name="expected" value="' + _safe(current_stage) + '">'
                '<input type="hidden" name="csrf" value="' + _safe(csrf) + '">'
                '<label><input type="checkbox" name="confirm" value="record_only" required>'
                'これはテスト上の記録のみで、実際の発注・発送・返金ではないことを確認。'
                '発送済みの記録はSquareの配送先確認が完了した場合だけ可能</label>'
                '<button type="submit">' + _safe(label) + '</button></form>'
            )
        controls = ('<section class="stage-controls"><h3>手動の進捗記録（Sandboxのみ）</h3>'
                    '<p>操作した内容はテスト用注文履歴に残ります。'
                    '実際の発注・入荷・返金・発送処理は行われません。</p>' +
                    "".join(forms) + '</section>') if forms else ""
        tracking_html = ""
        if order["state"] == "paid" and current_stage == "shipped" and csrf:
            recorded = SandboxTrackingJournal(store).read(order_id)
            if recorded:
                tracking_html = (
                    '<section class="tracking-box"><strong>配送情報（テスト記録）</strong>'
                    '<p>配送会社：' + _safe(recorded["carrier_label"]) +
                    '<br>追跡番号：<code>' +
                    _safe(recorded["tracking_number"]) +
                    '</code></p><p>この画面では変更・発送・メール送信しません。</p></section>'
                )
            else:
                options = "".join(
                    '<option value="' + _safe(code) + '">' + _safe(name) + '</option>'
                    for code, name in CARRIERS.items()
                )
                tracking_html = (
                    '<section class="tracking-box"><h3>配送会社・追跡番号（テスト記録）</h3>'
                    '<p>実際の配送は手配しません。登録済みの内容はこの画面から変更できません。</p>'
                    '<form method="post" action="/api/shop/sandbox/operator/tracking" class="stage-form">'
                    '<input type="hidden" name="order_id" value="' + _safe(order_id) + '">'
                    '<input type="hidden" name="csrf" value="' + _safe(csrf) + '">'
                    '<label>配送会社<select name="carrier_code" required>'
                    '<option value="">選択してください</option>' + options + '</select></label>'
                    '<label>追跡番号<input name="tracking_number" type="text"'
                    ' required minlength="8" maxlength="35" pattern="[A-Za-z0-9-]{8,35}"'
                    ' autocomplete="off" placeholder="半角英数字・ハイフン"></label>'
                    '<label><input type="checkbox" name="confirm" value="record_only" required>'
                    'これはテスト記録であり、実際の配送・メール送信ではないことを確認</label>'
                    '<button type="submit">配送情報をテスト登録</button></form></section>'
                )
        refund_html = ""
        if order["state"] == "paid" and current_stage == "refund_review" and csrf:
            refund_html = (
                '<section class="tracking-box"><h3>Square全額返金を照合（Sandboxのみ）</h3>'
                '<p>Squareの決済履歴を読み取って「返金済み」を確認します。'
                'この操作で実際の返金・メール送信は行いません。'
                '全額返金が確認できない場合、状態は変更されません。</p>'
                '<form method="post" action="/api/shop/sandbox/operator/verify-full-refund"'
                ' class="stage-form">'
                '<input type="hidden" name="order_id" value="' + _safe(order_id) + '">'
                '<input type="hidden" name="csrf" value="' + _safe(csrf) + '">'
                '<label><input type="checkbox" name="confirm" value="verify_read_only" required>'
                'すでにSquareで返金操作が完了していることを読み取るだけで、'
                'ここから返金は実行しないと確認</label>'
                '<button type="submit">Square全額返金済みを照合する（テスト）</button>'
                '</form></section>'
            )
        case_html = ""
        if order["state"] == "paid" and csrf:
            existing_cases = service_cases_by_order.get(order_id, [])
            existing_kinds = {k for k, _ in existing_cases}
            available = [(key, label) for key, label in CASE_TYPES.items()
                         if key not in existing_kinds]
            case_forms = []
            if available:
                options = "".join(
                    '<option value="' + _safe(k) + '">' + _safe(v) + '</option>'
                    for k, v in available
                )
                case_forms.append(
                    '<form method="post" action="/api/shop/sandbox/operator/service-case" class="stage-form">'
                    '<input type="hidden" name="order_id" value="' + _safe(order_id) + '">'
                    '<input type="hidden" name="expected" value="none">'
                    '<input type="hidden" name="status" value="open">'
                    '<input type="hidden" name="csrf" value="' + _safe(csrf) + '">'
                    '<label>模擬問い合わせの種類<select name="kind" required>'
                    '<option value="">選択してください</option>' + options + '</select></label>'
                    '<label><input type="checkbox" name="confirm" value="record_only" required>'
                    'これはテスト用の問い合わせ管理記録のみ。実際の返品受付・返金・顧客連絡はしない</label>'
                    '<button type="submit">対応記録を作成（テスト）</button></form>'
                )
            for kind, current_status in existing_cases:
                case_forms.append(
                    '<p><strong>' + _safe(CASE_TYPES[kind]) + '</strong>：' +
                    _safe(CASE_STATUSES[current_status]) + '</p>'
                )
                for next_status in sorted(NEXT[current_status]):
                    label = CASE_STATUSES[next_status]
                    case_forms.append(
                        '<form method="post" action="/api/shop/sandbox/operator/service-case" class="stage-form">'
                        '<input type="hidden" name="order_id" value="' + _safe(order_id) + '">'
                        '<input type="hidden" name="kind" value="' + _safe(kind) + '">'
                        '<input type="hidden" name="expected" value="' + _safe(current_status) + '">'
                        '<input type="hidden" name="status" value="' + _safe(next_status) + '">'
                        '<input type="hidden" name="csrf" value="' + _safe(csrf) + '">'
                        '<label><input type="checkbox" name="confirm" value="record_only" required>'
                        '画面上の状況を記録するだけで、実際の連絡や返金は行わない</label>'
                        '<button type="submit">' + _safe(label) + 'として記録</button></form>'
                    )
            case_html = (
                '<details class="service-cases"><summary>問い合わせ対応（テスト記録）：' +
                str(len(existing_cases)) + '件</summary>'
                '<p>未承認の返品・キャンセル条件を適用しません。'
                'お客様や仕入先への連絡、Square返金は実行されません。</p>' +
                "".join(case_forms) + '</details>'
            )
        payment_recheck = ""
        if order["state"] == "paid" and csrf:
            payment_recheck = (
                '<section class="tracking-box"><h3>Square Sandboxの現在の入金状態を再確認</h3>'
                '<p>一覧の入金済み表示は過去の記録です。返金後の可能性もあるため、'
                '必要なときにSquareの最新の決済・注文情報を読み取って確認できます。'
                '照会した結果はDBに保存しません。発注・返金・発送は実行しません。</p>'
                '<form method="post" action="/api/shop/sandbox/operator/check-current-payment" '
                'class="stage-form">'
                '<input type="hidden" name="order_id" value="' + _safe(order_id) + '">'
                '<input type="hidden" name="csrf" value="' + _safe(csrf) + '">'
                '<label><input type="checkbox" name="confirm" value="read_only" required>'
                'Square Sandboxの最新状態を読み取るだけで、決済・返金等を実行しないことを確認</label>'
                '<button type="submit">現在のSquare入金・未返金を再確認（Sandbox）</button>'
                '</form></section>'
            )
        shipping_recheck = ""
        if order["state"] == "paid" and csrf:
            shipping_recheck = (
                '<section class="tracking-box"><h3>📦 配送先の必須項目を最新確認（Sandbox）</h3>'
                '<p>入金済みだけでは発送できません。Square Ordersから住所・氏名・'
                '電話番号・郵便番号の有無だけを読み取り、個人情報は表示しません。'
                '結果はこの画面に保存しません。</p>'
                '<form method="post" action="/api/shop/sandbox/operator/check-current-shipping" '
                'class="stage-form">'
                '<input type="hidden" name="order_id" value="' + _safe(order_id) + '">'
                '<input type="hidden" name="csrf" value="' + _safe(csrf) + '">'
                '<label><input type="checkbox" name="confirm" value="read_only" required>'
                'Squareの入金状態と配送先情報を読み取るだけで、発送・連絡は行わない</label>'
                '<button type="submit">配送先が揃っているか確認する（Sandbox）</button>'
                '</form></section>'
            )
        cards.append(
            '<article class="order"><div class="order-top"><strong>' +
            _safe(PAYMENT_LABELS.get(order["state"], "状態確認が必要")) +
            "</strong><span class=\"amount\">" +
            f'{int(order["amount_yen"]):,}' + '円</span></div>' +
            "<code>" + _safe(order_id) + "</code>" +
            "<p class=\"date\">注文：" + _safe(_when(order["created_at"])) +
            "　入金：" + _safe(_when(order["paid_at"])) + "</p>" +
            "<ul>" + "".join(lines) + "</ul>" +
            '<p class="status">仕入れ：' + _safe(procurement_text) +
            "<br>運営メール：" + _safe(mail_text) + "</p>" +
            '<div class="next-action"><strong>次の確認作業</strong><p>' +
            _safe(action) + "</p></div>" + payment_recheck + shipping_recheck + drafts_html + controls + tracking_html + refund_html + case_html + "</article>"
        )
    paid = sum(row["state"] == "paid" for row in records)
    pending = len(records) - paid
    return """<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>BIG PAW｜Sandbox注文管理（手動進捗テスト）</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f4f7fb;color:#20314b;font:15px/1.6 -apple-system,BlinkMacSystemFont,"Hiragino Sans",Meiryo,sans-serif}
header{background:#164f80;color:white;padding:19px max(16px,calc((100% - 960px)/2))}
header h1{font-size:23px;margin:0}header p{font-size:12px;margin:2px 0 0}
main{max-width:960px;margin:auto;padding:18px 14px 65px}
.warning{background:#fff6dd;border-left:5px solid #bf841e;padding:13px;border-radius:6px;font-size:13px}
nav{margin:18px 0;display:flex;flex-wrap:wrap;gap:9px}
nav a{display:inline-block;background:white;border:1px solid #ccd8e5;border-radius:8px;padding:9px 12px;color:#174f7f;text-decoration:none;font-weight:700}
.stats{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:15px 0}
.stats div{background:white;border:1px solid #dae3ed;border-radius:10px;padding:13px}
.stats strong{display:block;font-size:26px}.stats span{font-size:12px}
.order{background:white;border:1px solid #dae3ed;border-radius:12px;padding:17px;margin:12px 0;overflow-wrap:anywhere}
.order-top{display:flex;justify-content:space-between;gap:10px;align-items:center}
.order-top strong{color:#176e55}.amount{font-size:19px;font-weight:850}
code{font-size:11px;color:#56657a}.date{font-size:12px;color:#6b7888}
ul{padding-left:21px;margin:8px 0}.status{font-size:13px;background:#f1f6fa;border-radius:8px;padding:10px}
.next-action{background:#eaf4ee;border-left:4px solid #367b59;border-radius:6px;padding:10px 12px;font-size:13px}
.next-action p{margin:4px 0 0}
.drafts{margin-top:12px;border:1px solid #d9e3ef;border-radius:8px;padding:9px 11px;font-size:13px}
.drafts summary{cursor:pointer;font-weight:800;color:#285681}
.drafts li{padding:3px 0}
.service-cases{margin-top:14px;border:1px solid #d2d5df;border-radius:10px;background:#fcfcff;padding:12px}
.service-cases summary{font-weight:800;cursor:pointer;color:#2e567f}
.service-cases p{font-size:13px;margin:9px 0}
.service-cases select{width:100%;background:white;border:1px solid #aabfce;border-radius:7px;padding:10px}
.service-cases .stage-form label:has(input[type=checkbox]){display:flex}

.draft-empty{color:#718197;font-size:12px}
.stage-controls{margin-top:14px;padding:12px;border:1px solid #bfd9e9;border-radius:9px;background:#f6faff}
.stage-controls h3{margin:0 0 5px;font-size:15px}.stage-controls p{font-size:12px;margin:0 0 10px}
.stage-form{border-top:1px solid #dbe8f0;padding:10px 0;display:grid;gap:9px}
.stage-form label{font-size:12px;display:flex;align-items:flex-start;gap:7px}
.stage-form input{margin-top:4px}
.stage-form button{background:#205b85;color:white;border:0;border-radius:8px;padding:10px;cursor:pointer;font-weight:700}
.stage-form button:focus-visible{outline:3px solid #f0ae40;outline-offset:3px}
.tracking-box{margin-top:14px;padding:13px;border:1px solid #b6d4da;border-radius:10px;background:#f0fafb}
.tracking-box h3{font-size:15px;margin:0 0 7px}
.tracking-box p{font-size:12px;margin:7px 0}
.tracking-box select,.tracking-box input[type=text]{width:100%;padding:11px;border:1px solid #aabfce;border-radius:7px;background:#fff;font-size:15px}
.tracking-box .stage-form label{display:grid;gap:5px}
.tracking-box .stage-form label:has(input[type=checkbox]){display:flex}

.empty{padding:30px;text-align:center;background:#fff;border-radius:10px}
@media(max-width:500px){.stats{gap:6px}.stats div{padding:10px}.stats strong{font-size:22px}}
</style></head><body>
<header><h1>BIG PAW｜注文管理</h1><p>Square Sandbox・手動進捗テスト（発注・発送・返金は実行しません）</p></header>
<main><p class="warning"><strong>⚠ これはテスト注文です。</strong>本物の入金・在庫確保・発注・発送を示すものではありません。
トランペッツへの仕入れ発注や商品の発送は行わないでください。</p>
<nav><a href="/shop.html">テストショップを見る</a><a href="/shop-test-orders.html">最新の注文状態へ更新</a><a href="/shop-live-orders-preview.html">将来の注文管理画面を見る（表示テスト・読み取り専用）</a></nav>
<div class="stats"><div><strong>""" + str(len(records)) + """</strong><span>注文件数</span></div>
<div><strong>""" + str(paid) + """</strong><span>入金確認済み（テスト）</span></div>
<div><strong>""" + str(pending) + """</strong><span>決済待ち・準備中</span></div></div>
<p class="warning" role="status"><strong>📦 入金済みと配送先確認済みは別です。</strong>
Square Sandboxのテスト決済画面は配送先が未入力のまま完了する場合があります。
注文が入金済みでも、氏名・電話番号・郵便番号・住所をSquare Ordersから最新確認できない場合は、発送済みの操作は拒否されます。
この画面の入金済み表示だけで、住所確認・発送手配を進めないでください。</p>
<section aria-label="注文一覧"><h2>注文一覧（直近100件）</h2>""" + (
        "".join(cards) if cards else '<p class="empty">テスト注文の記録はありません。</p>'
    ) + """</section>
<p class="warning">このページはSandboxの手動進捗記録です。仕入先・お客様向けの通知は未送信下書きのため、別途連絡が必要です。実際の仕入れ発注・発送・返金・メール送信はできません。
配送先などの個人情報は表示しません。</p>
</main></body></html>"""
