"""Operator-only HTML preview for the future live food-order read model.

STAGING DISPLAY ONLY: no public route, no live charge, no Square API traffic,
no buyer information, no file mutation. Mounted ONLY behind the existing
isolated bigpaw-test operator authentication in staging_checkout_preview.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from html import escape

from .live_order_ledger import LiveOrderLedger
from .live_order_overview import read_order_management_snapshot

JST = timezone(timedelta(hours=9))


def _safe(value):
    return escape(str(value), quote=True)


def _date(value):
    if type(value) is not int or value < 0:
        return "—"
    try:
        return datetime.fromtimestamp(value, JST).strftime("%Y/%m/%d %H:%M")
    except (OverflowError, OSError, ValueError):
        return "—"


def render_order_overview_preview(ledger: LiveOrderLedger) -> str:
    """Read a bounded snapshot and show *historic* payment state clearly.

    Does not call Square to check current refunds. The page intentionally
    provides no buttons/forms that initiate purchase/refund/shipping or mail.
    """
    data = read_order_management_snapshot(ledger=ledger, limit=100)
    rows = data["orders"]
    historic = sum(1 for order in rows
                   if order["payment_recorded_historically"])
    cards = []
    for order in rows:
        order_id = _safe(order["order_id"])
        items = "".join(
            "<li><strong>" + _safe(line["sku"]) + "</strong> " +
            _safe(line["name"]) + " / " + _safe(line["size"]) +
            "　×" + _safe(line["qty"]) + "　単価 " +
            f'{line["unit_yen"]:,}' + "円</li>"
            for line in order["items"]
        )
        if order["payment_recorded_historically"]:
            label = "過去のSquare入金確認記録あり"
            instruction = (
                "現在の入金・返金状況は未確認です。仕入れや発送の前に"
                "Square本番の決済・返金情報を再照合してください。"
            )
        else:
            label = "決済リンク作成後・入金確認記録なし"
            instruction = (
                "入金は確認されていません。"
                "仕入れ・発送やお客様への入金済み通知は行わないでください。"
            )
        cards.append(
            '<article class="order" aria-label="注文 ' + order_id + '">' +
            '<div class="top"><strong>' + _safe(label) + '</strong>' +
            '<span class="money">' + f'{order["amount_yen"]:,}' + '円</span></div>' +
            '<code>' + order_id + '</code>' +
            '<p class="date">注文記録：' + _safe(_date(order["created_at"])) +
            '　過去の入金確認：' + _safe(_date(order["paid_at"])) + '</p>' +
            '<ul>' + items + '</ul>' +
            '<p class="notice">' + _safe(instruction) + '</p>' +
            '<p class="date">署名付き決済通知の検証記録：' +
            str(order["verified_signed_event_count"]) +
            '件（現在の入金状態の保証ではありません）</p></article>'
        )
    demo = (
        '<section class="sample" aria-label="架空の画面サンプル">'
        '<h2>画面の見本（架空の注文・本物ではありません）</h2>'
        '<p class="warning">以下はデザインを確認するための架空データです。'
        '注文・決済・仕入れ・発送・通知記録ではありません。'
        '上に表示する注文件数にも含まれません。</p>'
        '<article class="order"><div class="top"><strong>入金確認記録なし（見本）'
        '</strong><span class="money">12,000円（仮の金額）</span></div>'
        '<code>DEMO-ORDER-001（実在しない注文）</code>'
        '<p class="date">注文日時：サンプル</p>'
        '<ul><li>サンプルのドッグフード ×1袋</li></ul>'
        '<p class="notice">まだ入金を確認していません。'
        '仕入れ・発送はできません。</p></article>'
        '<article class="order"><div class="top">'
        '<strong>過去の入金確認記録あり（見本）</strong>'
        '<span class="money">24,000円（仮の金額）</span></div>'
        '<code>DEMO-ORDER-002（実在しない注文）</code>'
        '<p class="date">入金確認日時：サンプル</p>'
        '<ul><li>サンプルのドッグフード ×2袋</li></ul>'
        '<p class="notice">現在の返金・入金状態は未確認です。'
        '最新のSquare情報を再照合する必要があります。</p>'
        '</article></section>'
    ) if not rows else ""
    return """<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow,noarchive">
<title>BIG PAW｜注文管理の表示確認（テスト専用）</title>
<style>
*{box-sizing:border-box}body{margin:0;background:#f5f8fc;color:#20314b;
font:15px/1.65 -apple-system,BlinkMacSystemFont,"Hiragino Sans",Meiryo,sans-serif}
header{background:#164f80;color:#fff;padding:20px max(16px,calc((100% - 960px)/2))}
header h1{font-size:22px;margin:0}header p{font-size:12px;margin:3px 0 0}
main{max-width:960px;margin:auto;padding:18px 14px 55px}
.warning{border-left:5px solid #c78a1c;background:#fff7df;padding:14px;border-radius:7px}
nav{margin:16px 0;display:flex;flex-wrap:wrap;gap:10px}
nav a{background:#fff;border:1px solid #d1dfea;border-radius:8px;padding:10px 12px;
color:#164f80;text-decoration:none;font-weight:750}
.stats{display:flex;gap:9px;flex-wrap:wrap}.stat{flex:1;min-width:145px;background:#fff;
border:1px solid #dae2ed;border-radius:10px;padding:13px}
.stat strong{display:block;font-size:26px}.stat span{font-size:12px}
.order{background:#fff;border:1px solid #d9e5f0;border-radius:12px;margin:12px 0;
padding:16px;overflow-wrap:anywhere}.top{display:flex;justify-content:space-between;
gap:12px;flex-wrap:wrap}.top strong{color:#164f80}.money{font-weight:850;font-size:19px}
code{font-size:12px;color:#526780}.date{font-size:12px;color:#67778a}
ul{padding-left:20px}.notice{background:#f1f6fb;border-left:4px solid #2874a4;
padding:10px;border-radius:5px}.empty{background:#fff;padding:25px;text-align:center;
border-radius:9px}@media(max-width:500px){header h1{font-size:19px}}
</style></head><body>
<header><h1>BIG PAW｜注文管理の表示確認</h1>
<p>テスト環境・読み取り専用・本番注文管理画面ではありません</p></header>
<main><p class="warning"><strong>⚠ これは管理画面の表示テストです。</strong>
実際の販売・入金・発注・発送・返金・メール送信は実行できません。
過去の入金記録は現在のSquare決済状態を保証しません。</p>
<nav><a href="/shop-test-orders.html">Square Sandboxの注文管理</a>
<a href="/shop-live-orders-preview.html">表示を更新</a>
<a href="/shop.html">テストショップへ戻る</a></nav>
<div class="stats"><div class="stat"><strong>""" + str(data["count"]) + """</strong>
<span>表示中の注文記録</span></div><div class="stat"><strong>""" + str(historic) + """</strong>
<span>過去の入金確認記録あり</span></div><div class="stat"><strong>""" + str(data["count"]-historic) + """</strong>
<span>入金確認記録なし</span></div></div>
<section aria-label="注文の表示確認"><h2>注文記録（最大100件）</h2>""" + (
        "".join(cards) if cards else
        '<p class="empty">この表示テスト用の注文記録はまだありません。'
        '既存のSquare Sandboxの注文は別画面で確認してください。</p>'
    ) + """</section>""" + demo + """
<p class="warning">このページで現在の決済/返金照会は実行しません。
実際のSquare本番API・実注文データや顧客の氏名、メール、住所にはアクセスしません。</p>
</main></body></html>"""
