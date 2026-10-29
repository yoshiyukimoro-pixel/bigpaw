"""Produce an OFFLINE, read-only Sandbox operator order dashboard.

This exports a local HTML snapshot with no external JS, tracking, HTTP
listener or access to production. It must never be deployed under app/.
"""
from __future__ import annotations
import argparse
from html import escape
import importlib.util
import os
from pathlib import Path
import sys

from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.sandbox_fulfillment import SandboxFulfillmentOps
from shop_payments.sandbox_procurement import SandboxProcurementOps
from shop_payments.sandbox_notifications import SandboxNotificationDrafts
from shop_payments.retail_catalog import load_sale_catalog

ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location(
    "sandbox_operator", Path(__file__).with_name("shop-sandbox-operator.py"))
operator=importlib.util.module_from_spec(spec)
spec.loader.exec_module(operator)

LABELS={
    "created":"注文準備中",
    "payment_pending":"入金確認待ち",
    "paid":"入金確認済み",
    "not_assessed":"発送確認前",
    "address_review":"配送先確認",
    "stock_review":"在庫確認",
    "ready_to_pack":"発送準備可",
    "shipped":"発送済み（記録）",
    "refund_review":"返金確認中",
    "refunded":"返金確認済み",
    "awaiting_supplier_order":"仕入先への発注待ち",
    "supplier_ordered":"仕入先へ発注済み（記録）",
    "supplier_backorder":"仕入先欠品・確認中",
    "received_at_shop":"埼玉の当店に入荷・検品済み（記録）",
    "payment_not_verified":"入金未確認",
}
def safe(value):return escape(str(value),quote=True)

def render(db:Path) -> str:
    order_store=SandboxOrderStore(db)
    ops=SandboxFulfillmentOps(order_store)
    SandboxProcurementOps(order_store)
    orders=operator._rows(db)
    drafts=SandboxNotificationDrafts(order_store).pending()
    catalog=load_sale_catalog()
    statuses={
        "pending":sum(o["payment_state"]!="paid" for o in orders),
        "paid":sum(o["payment_state"]=="paid" for o in orders),
        "supplier":sum(o["procurement_state"]=="awaiting_supplier_order" for o in orders),
        "ordered":sum(o["procurement_state"]=="supplier_ordered" for o in orders),
        "arrived":sum(o["procurement_state"]=="received_at_shop" for o in orders),
        "shortage":sum(o["procurement_state"]=="supplier_backorder" for o in orders),
    }
    cards="".join(
        '<div class="stat"><strong>'+str(value)+'</strong><span>'+safe(title)+'</span></div>'
        for title,value in (
            ("注文総数",len(orders)),("入金確認待ち",statuses["pending"]),
            ("入金確認済み",statuses["paid"]),("仕入先への発注待ち",statuses["supplier"]),
            ("仕入先へ発注済み",statuses["ordered"]),
            ("埼玉へ入荷済み",statuses["arrived"]),("仕入先欠品",statuses["shortage"]),
            ("通知の未送信下書き",len(drafts)),
        )
    )
    order_rows=""
    for o in orders:
        items="、".join(
            safe(item["sku"]+" "+item["product"]+" "+item["size"]+
                 " ×"+str(item["quantity"])) for item in o["items"])
        pay=LABELS.get(o["payment_state"],o["payment_state"])
        shipping=LABELS.get(o["fulfillment_state"],o["fulfillment_state"])
        supplier=LABELS.get(o["procurement_state"],o["procurement_state"])
        order_rows+=(
            "<tr><td><code>"+safe(o["order_id"])+"</code></td>"+
            "<td>"+safe(pay)+"</td><td>"+safe(supplier)+"</td><td>"+safe(shipping)+"</td>"+
            "<td>"+items+"</td><td class='number'>"+
            f'{int(o["amount_yen"]):,}'+"円</td><td class='number'>0円</td></tr>"
        )
    if not order_rows:
        order_rows='<tr><td colspan="7">Sandboxの注文記録はありません。</td></tr>'
    group_names={"operator":"運営","supplier":"仕入先","customer":"お客様"}
    notification_rows="".join(
        "<tr><td><code>"+safe(n["order_id"])+"</code></td><td>"+
        safe(group_names[n["audience"]])+"</td><td>"+safe(n["subject"])+
        "<details><summary>送信前に本文を確認する</summary><pre>"+
        safe(n["body"])+"</pre></details></td><td>未送信・確認待ち</td></tr>" for n in drafts)
    if not notification_rows:
        notification_rows='<tr><td colspan="4">送信待ちの下書きはありません。</td></tr>'
    brands={"A":"ACANA","O":"ORIJEN","Z":"ZIWI","C":"CHARM"}
    stock_rows="".join(
        "<tr><td>"+safe(sku)+"</td><td>"+
        safe(brands[sku[0]])+" "+safe(product.name)+" "+safe(product.size)+"</td><td class='number'>"+
        str(ops.stock(sku))+"</td></tr>"
        for sku,product in catalog.items())
    return """<!doctype html><html lang="ja"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="robots" content="noindex,nofollow">
<title>BIG PAW | Sandbox 注文管理（ローカル閲覧専用）</title>
<style>
*{box-sizing:border-box}body{background:#f6f7fb;color:#232c3c;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Hiragino Sans","Yu Gothic",sans-serif;margin:0}
header{background:#174a79;color:#fff;padding:24px max(16px,calc((100vw - 1150px)/2))}
header small{display:block;opacity:.9}main{max-width:1150px;padding:22px 16px 55px;margin:auto}
.banner{border-left:5px solid #b1812c;background:#fff7e7;padding:13px 16px;margin:0 0 22px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(145px,1fr));gap:12px;margin-bottom:22px}
.stat{background:#fff;border:1px solid #e0e4ec;border-radius:12px;padding:15px}
.stat strong{display:block;font-size:28px}.stat span{font-size:12px;color:#5e6979}
section{background:#fff;border:1px solid #e0e4ec;border-radius:12px;padding:16px;margin-bottom:20px;overflow:auto}
h1{margin:0;font-size:25px}h2{margin:0 0 14px;font-size:19px}
table{border-collapse:collapse;width:100%;min-width:760px}th,td{padding:12px;border-bottom:1px solid #e8ecf1;text-align:left;vertical-align:top}
th{font-size:12px;color:#526177;background:#f3f6fa}
.number{text-align:right;white-space:nowrap}code{font-size:11px;word-break:break-all}
details summary{cursor:pointer;color:#174a79;font-weight:700;margin:6px 0 15px}
pre{white-space:pre-wrap;overflow-wrap:anywhere;font:12px/1.7 inherit;background:#f6f8fb;border:1px solid #e2e7ed;padding:12px;border-radius:8px;margin:0 0 12px}
footer{color:#647085;font-size:12px;margin-top:12px}
</style></head><body>
<header><small>BIG PAW / PRIVATE SANDBOX ONLY</small>
<h1>注文・在庫管理（閲覧専用）</h1></header>
<main><p class="banner">この画面は開発用Sandboxデータを使ったローカルHTMLのスナップショットです。
受注発注方式：入金確認 → 九州の仕入先へ発注 → 埼玉の当店で入荷・検品 → お客様へ発送。
お届けの目安は通常4〜7日程度（休日や欠品で前後）。注文の受付・出荷・返金・住所表示・本番決済はできません。一般公開禁止。</p>
<div class="stats">"""+cards+"""</div>
<section><h2>注文一覧</h2><table>
<thead><tr><th>注文番号</th><th>決済状態</th><th>仕入・入荷状況</th><th>従来の発送状態（参考）</th><th>商品・数量</th>
<th class="number">税込合計</th><th class="number">追加送料</th></tr></thead>
<tbody>"""+order_rows+"""</tbody></table></section>
<section><h2>運営・仕入先・お客様向け通知下書き（未送信）</h2>
<p>Squareによる入金検証後または発注・発送の手動記録に応じて準備された下書きです。
メール・LINEの自動送信や仕入先への発注は行いません。宛先と内容を確認してください。</p>
<table><thead><tr><th>注文番号</th><th>対象</th><th>件名</th><th>状態</th></tr></thead>
<tbody>"""+notification_rows+"""</tbody></table></section>
<section><details><summary>35商品の手元在庫（参考・受注発注の判定には使用しません）</summary>
<p>未登録は0点と表示されますが、仕入先の欠品を意味しません。受注発注ではお支払い確認後、仕入先へ発注します。</p>
<table><thead><tr><th>SKU</th><th>商品名・容量</th><th class="number">登録在庫</th></tr></thead>
<tbody>"""+stock_rows+"""</tbody></table></details></section>
<footer>顧客氏名・住所・電話番号・カード番号・Square認証情報は含めません。
発送済みは内部記録であり、実配送の実行ではありません。</footer>
</main></body></html>"""


def main(argv=None):
    p=argparse.ArgumentParser()
    p.add_argument("--db",required=True)
    p.add_argument("--out",required=True,help="New private HTML outside the BIG PAW repository")
    args=p.parse_args(argv)
    try:
        db=operator._validated_db(args.db)
        output=Path(args.out).expanduser()
        target=output.resolve(strict=False)
        if (target.is_relative_to(ROOT) or target.is_symlink() or
                not target.parent.exists() or target.suffix!=".html"):
            raise ValueError("Private report path required outside repository")
        html=render(db).encode("utf-8")
        fd=os.open(target,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
        with os.fdopen(fd,"wb") as file:file.write(html)
    except (ValueError,OSError):
        print("SANDBOX_REPORT_FAILED: check isolated DB and private output path",file=sys.stderr)
        return 1
    print("SANDBOX_REPORT_OK: local read-only HTML created; no real orders, emails or requests")
    return 0

if __name__=="__main__":
    sys.exit(main())
