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

def render(store) -> str:
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
            "<br>運営メール：" + _safe(mail_text) + "</p></article>"
        )
    paid = sum(row["state"] == "paid" for row in records)
    pending = len(records) - paid
    return """<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>BIG PAW｜Sandbox注文管理（閲覧専用）</title>
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
.empty{padding:30px;text-align:center;background:#fff;border-radius:10px}
@media(max-width:500px){.stats{gap:6px}.stats div{padding:10px}.stats strong{font-size:22px}}
</style></head><body>
<header><h1>BIG PAW｜注文管理</h1><p>Square Sandbox・閲覧専用テスト画面</p></header>
<main><p class="warning"><strong>⚠ これはテスト注文です。</strong>本物の入金・在庫確保・発注・発送を示すものではありません。
トランペッツへの仕入れ発注や商品の発送は行わないでください。</p>
<nav><a href="/shop.html">テストショップを見る</a><a href="/shop-test-orders.html">最新の注文状態へ更新</a></nav>
<div class="stats"><div><strong>""" + str(len(records)) + """</strong><span>注文件数</span></div>
<div><strong>""" + str(paid) + """</strong><span>入金確認済み（テスト）</span></div>
<div><strong>""" + str(pending) + """</strong><span>決済待ち・準備中</span></div></div>
<section aria-label="注文一覧"><h2>注文一覧（直近100件）</h2>""" + (
        "".join(cards) if cards else '<p class="empty">テスト注文の記録はありません。</p>'
    ) + """</section>
<p class="warning">このページから注文変更・返金・自動発注・メール再送はできません。
配送先などの個人情報は表示しません。</p>
</main></body></html>"""
