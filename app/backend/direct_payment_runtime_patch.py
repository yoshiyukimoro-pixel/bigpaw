#!/usr/bin/env python3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(path: Path, old: str, new: str, label: str):
    s = path.read_text(encoding='utf-8')
    if old not in s:
        raise RuntimeError(f'DIRECT_PAYMENT_PATCH_FAIL|{label}|marker_missing')
    path.write_text(s.replace(old, new, 1), encoding='utf-8')

# 1) 商談画面: BIG PAWが予約金・残金を管理する表示を廃止
p = ROOT / 'deal.html'
replace_once(
    p,
    '<div class="trow" id="stepPay"><div class="dot">3</div><div class="tcontent"><b>予約金・契約</b><span class="muted" id="payText">未完了</span></div></div>',
    '<div class="trow" id="stepPay"><div class="dot">3</div><div class="tcontent"><b>支払い条件・契約</b><span class="muted" id="payText">予約金・残金は当事者間で直接精算</span></div></div>',
    'deal_step'
)
replace_once(
    p,
    '<div class="fact"><span>生体価格</span><b id="total">-</b></div><div class="fact"><span>予約金</span><b id="reserve">-</b></div><div class="fact"><span>ステータス</span><b id="status">-</b></div><div class="fact"><span>残金</span><b id="balance">-</b></div>',
    '<div class="fact"><span>生体価格</span><b id="total">-</b></div><div class="fact"><span>代金の支払い</span><b>購入者 → ブリーダー</b></div><div class="fact"><span>ステータス</span><b id="status">-</b></div><div class="fact"><span>BIG PAW</span><b>代金の受領・保管なし</b></div>',
    'deal_facts'
)
replace_once(
    p,
    '<a id="reservationLink" class="card pad" href="reservation.html"><b>💳 予約金</b><div class="muted">金額・支払い状況</div></a>',
    '<a id="reservationLink" class="card pad" href="reservation.html"><b>💰 支払い条件</b><div class="muted">予約金・残金はブリーダーへ直接支払い</div></a>',
    'deal_quick'
)
replace_once(
    p,
    "total.textContent=BigPawWorkflow.yen(d.total_price);reserve.textContent=BigPawWorkflow.yen(d.reservation_amount);balance.textContent=BigPawWorkflow.yen(d.total_price-d.reservation_amount);status.textContent=d.status;",
    "total.textContent=BigPawWorkflow.yen(d.total_price);status.textContent=d.status;",
    'deal_js_amounts'
)
replace_once(
    p,
    "if(sum.payment?.status==='paid'){stepPay.classList.add('done');payText.textContent='予約金入金済み'}if(sum.contract?.status==='signed')payText.textContent+='・契約署名済み';",
    "if(sum.contract?.status==='signed'){stepPay.classList.add('done');payText.textContent='支払い条件確認・契約署名済み'}",
    'deal_js_step'
)

# 2) 予約金ページは「支払い条件」案内ページへ変更。プラットフォーム入金操作を撤去
reservation = '''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>支払い条件｜BIG PAW</title><link rel="stylesheet" href="assets/style.css"></head><body><div class="topbar">🐾 BIG PAW｜支払い条件</div><header class="site-header"><div class="wrap nav"><a class="logo" href="index.html"><span class="logo-mark">🐾</span>BIG PAW</a><nav class="navlinks"><a id="dealBackTop" href="deal.html">商談管理</a><a href="messages.html">メッセージ</a></nav></div></header><div class="hero-mini"><div class="wrap"><h1>支払い条件の確認</h1><p>子犬代金の支払いは、購入者とブリーダーの当事者間で直接行います。</p></div></div><main class="wrap"><section class="section" style="max-width:820px;margin:auto"><div class="card pad"><div class="stepbar"><div class="step">1. 見学</div><div class="step active">2. 支払い条件</div><div class="step">3. 契約</div><div class="step">4. お迎え</div></div><div class="tablelike"><div class="table-row"><div>対象</div><div id="target">-</div></div><div class="table-row"><div>生体価格</div><div><b id="price">-</b></div></div><div class="table-row"><div>支払い先</div><div><b>販売ブリーダーへ直接</b></div></div><div class="table-row"><div>BIG PAWの役割</div><div>売買代金の受領・保管・決済・返金は行いません</div></div></div><div class="notice" style="margin-top:16px"><b>予約金・残金について</b><br>予約金の有無・金額・支払方法・支払時期・キャンセル時の取扱い、残金の支払方法は、購入者とブリーダーで確認して決めてください。BIG PAWはその金銭を預かりません。</div><div class="notice" style="margin-top:12px">成約後、ブリーダーからBIG PAWへ最終生体販売価格とお迎え完了日を申請し、運営確認後にブリーダーへ成約手数料5%を請求します。</div><a id="contractGo" class="btn btn-main btn-wide" style="margin-top:18px" href="contract.html">契約内容を確認する</a><a id="dealBack" class="btn btn-sub btn-wide" style="margin-top:10px" href="deal.html">商談管理に戻る</a></div></section></main><script src="assets/app.js"></script><script src="assets/api.js"></script><script src="assets/bridge.js"></script><script src="assets/workflow.js"></script><script>(async()=>{try{const ctx=await BigPawWorkflow.context();if(!ctx.inquiry||!ctx.deal)throw new Error();target.textContent=(ctx.puppy?.breed||'')+'｜'+(ctx.puppy?.name||'子犬');price.textContent=BigPawWorkflow.yen(ctx.deal.total_price||ctx.puppy?.price||0);const q='?inquiry='+encodeURIComponent(ctx.inquiry.id);contractGo.href='contract.html'+q;dealBack.href='deal.html'+q;dealBackTop.href='deal.html'+q}catch(e){target.textContent='ログインして商談から開いてください。'}})();</script><script src="/auth-return-fix.js"></script></body></html>'''
(ROOT / 'reservation.html').write_text(reservation, encoding='utf-8')

# 3) 契約画面: 予約金をBIG PAWが管理するように見える表示を撤去
p = ROOT / 'contract.html'
replace_once(p, '<div class="step">2. 予約金</div>', '<div class="step">2. 支払い条件</div>', 'contract_step')
replace_once(
    p,
    '<div class="table-row"><div>生体価格</div><div id="price">-</div></div><div class="table-row"><div>予約金</div><div id="reservation">-</div></div><div class="table-row"><div>残金</div><div id="balance">-</div></div>',
    '<div class="table-row"><div>生体価格</div><div id="price">-</div></div><div class="table-row"><div>代金の支払い</div><div>購入者から販売ブリーダーへ直接支払い</div></div>',
    'contract_amounts'
)
replace_once(
    p,
    '<div id="statusBox" class="notice" style="margin-top:18px">署名状況を読み込み中…</div>',
    '<div class="notice" style="margin-top:18px">予約金・残金を含む売買代金の受領・保管・決済・返金にBIG PAWは関与しません。金額・支払方法・キャンセル条件は購入者とブリーダー間で確認してください。</div><div id="statusBox" class="notice" style="margin-top:12px">署名状況を読み込み中…</div>',
    'contract_notice'
)
replace_once(
    p,
    "price.textContent=BigPawWorkflow.yen(sum.deal.total_price);reservation.textContent=BigPawWorkflow.yen(sum.deal.reservation_amount);balance.textContent=BigPawWorkflow.yen(sum.deal.total_price-sum.deal.reservation_amount);",
    "price.textContent=BigPawWorkflow.yen(sum.deal.total_price);",
    'contract_js_amounts'
)

# 4) お迎え画面: 残金額のプラットフォーム管理表示を撤去
p = ROOT / 'pickup.html'
replace_once(p, '<p>日時・残金・持ち物・引渡状況をひとつの画面で確認。</p>', '<p>日時・持ち物・引渡状況をひとつの画面で確認。</p>', 'pickup_hero')
replace_once(p, '<div class="step">2. 予約金</div>', '<div class="step">2. 支払い条件</div>', 'pickup_step')
replace_once(p, '<label class="list-item"><input type="checkbox"> 残金の確認</label>', '<label class="list-item"><input type="checkbox"> 代金精算の確認（購入者 ↔ ブリーダー）</label>', 'pickup_check')
replace_once(
    p,
    '<aside><div class="card pad sticky"><h2>お支払い</h2><div class="fact"><span>生体価格</span><b id="total">-</b></div><div class="fact" style="margin-top:8px"><span>予約金</span><b id="reserve">-</b></div><div class="fact" style="margin-top:8px"><span>お迎え時残金</span><b id="balance">-</b></div><div id="pickupStatus" class="notice" style="margin-top:14px">未登録</div>',
    '<aside><div class="card pad sticky"><h2>取引確認</h2><div class="fact"><span>掲載時生体価格</span><b id="total">-</b></div><div class="notice" style="margin-top:10px">売買代金は購入者からブリーダーへ直接支払います。BIG PAWは予約金・残金を受領、保管、決済、返金しません。</div><div id="pickupStatus" class="notice" style="margin-top:14px">未登録</div>',
    'pickup_side'
)
replace_once(
    p,
    "total.textContent=BigPawWorkflow.yen(sum.deal.total_price);reserve.textContent=BigPawWorkflow.yen(sum.deal.reservation_amount);balance.textContent=BigPawWorkflow.yen(sum.deal.total_price-sum.deal.reservation_amount);",
    "total.textContent=BigPawWorkflow.yen(sum.deal.total_price);",
    'pickup_js_amounts'
)

# 5) 運営の成約管理: 予約金の手動入金確認機能を表示しない
p = ROOT / 'operator-deals.html'
replace_once(
    p,
    '見学から成約までの実データを確認し、手動決済時は予約金の入金確認を行います。',
    '見学から成約までの実データを確認します。子犬代金は購入者とブリーダー間で直接精算され、BIG PAWは決済を管理しません。',
    'operator_deals_lead'
)
s = p.read_text(encoding='utf-8')
start = s.find('async function markPaid(')
end = s.find('async function load()', start)
if start == -1 or end == -1:
    raise RuntimeError('DIRECT_PAYMENT_PATCH_FAIL|operator_deals_markpaid|marker_missing')
s = s[:start] + s[end:]
old_row = "<span class=\"chip\">商談: ${esc(x.status)}</span><span class=\"chip\">予約金: ${esc(x.reservation_status||'未入金')}</span><span class=\"chip\">契約: ${esc(x.contract_status||'未作成')}</span><span class=\"chip\">お迎え: ${esc(x.pickup_status||'未設定')}</span></div>${x.reservation_status!=='paid'?`<button class=\"btn btn-main\" style=\"margin-top:10px\" onclick=\"markPaid('${x.id}',${x.reservation_amount})\">予約金 ${yen(x.reservation_amount)} を入金確認</button>`:''}"
new_row = "<span class=\"chip\">商談: ${esc(x.status)}</span><span class=\"chip\">代金精算: 当事者間</span><span class=\"chip\">契約: ${esc(x.contract_status||'未作成')}</span><span class=\"chip\">お迎え: ${esc(x.pickup_status||'未設定')}</span></div>"
if old_row not in s:
    raise RuntimeError('DIRECT_PAYMENT_PATCH_FAIL|operator_deals_row|marker_missing')
p.write_text(s.replace(old_row, new_row, 1), encoding='utf-8')

# 6) 運営の売上画面: BIG PAWが予約金を受領したような集計を表示しない
p = ROOT / 'operator-revenue.html'
replace_once(p, '<span>予約金入金総額</span><b id="realReservation">-</b>', '<span>生体代金決済</span><b id="realReservation">当事者間</b>', 'operator_revenue_label')
replace_once(p, 'realReservation.textContent=yen(rev.reservationTotal);', "realReservation.textContent='当事者間';", 'operator_revenue_js')

# 7) 規約にも資金非関与を明記
p = ROOT / 'terms.html'
replace_once(
    p,
    '<h2>5. 売買契約・価格・予約金・保証</h2><p>子犬の売買契約、販売価格、予約金、残金、キャンセル、返金、生命保証、健康保証、引渡しその他の個別取引条件は、購入者とブリーダーとの間で定めるものとします。購入希望者は、契約前に掲載情報だけでなく、ブリーダーから提示される契約条件および重要事項を確認してください。</p>',
    '<h2>5. 売買契約・価格・予約金・保証</h2><p>子犬の売買契約、販売価格、予約金、残金、キャンセル、返金、生命保証、健康保証、引渡しその他の個別取引条件は、購入者とブリーダーとの間で定めるものとします。予約金および残金を含む生体代金は購入者からブリーダーへ直接支払い、BIG PAW運営はこれらの金銭の受領、保管、決済、送金または返金を行いません。購入希望者は、契約前に掲載情報だけでなく、ブリーダーから提示される契約条件および重要事項を確認してください。</p>',
    'terms_payment'
)

# Validation
checks = {
    'deal.html': ['予約金・残金は当事者間で直接精算', '代金の受領・保管なし'],
    'reservation.html': ['売買代金の受領・保管・決済・返金は行いません', '成約手数料5%'],
    'contract.html': ['売買代金の受領・保管・決済・返金にBIG PAWは関与しません'],
    'pickup.html': ['BIG PAWは予約金・残金を受領、保管、決済、返金しません'],
    'operator-deals.html': ['代金精算: 当事者間'],
    'operator-revenue.html': ['生体代金決済'],
    'terms.html': ['BIG PAW運営はこれらの金銭の受領、保管、決済、送金または返金を行いません'],
}
for fn, needles in checks.items():
    text = (ROOT / fn).read_text(encoding='utf-8')
    for needle in needles:
        if needle not in text:
            raise RuntimeError(f'DIRECT_PAYMENT_PATCH_FAIL|validation|{fn}|{needle}')

print('DIRECT_PAYMENT_FLOW_OK|buyer_to_breeder_direct=1|platform_custody=0|platform_refund=0|commission=5pct_post_completion', flush=True)
