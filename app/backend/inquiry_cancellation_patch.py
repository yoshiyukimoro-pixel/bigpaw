"""Install after existing workflow, with explicit guarded UI integration."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=ROOT/'backend/server.py';s=p.read_text()
marker="if __name__=='__main__':"
insert='from inquiry_cancellation import install as _install_inquiry_cancellation\n_install_inquiry_cancellation(globals())\n\n'
if insert not in s:
    assert s.count(marker)==1
    s=s.replace(marker,insert+marker,1);p.write_text(s)
p=ROOT/'backend/first_sale_workflow.py';s=p.read_text()
marker="    g['init_db']=migrate"
if "g['flush_sale_workflow_mail']" not in s:
    assert s.count(marker)==1
    s=s.replace(marker,"    g['flush_sale_workflow_mail']=flush_mail\n    g['monitor_inquiry_cancellation']=monitor_cancel\n"+marker);p.write_text(s)
# Existing mail transport stays intact; add HTML only for the new confirmation link.
p=ROOT/'backend/server.py';s=p.read_text()
a='payload=json.dumps({"from":"BIG PAW <noreply@bigpaw.site>","to":[to_email],"subject":subject,"text":text}).encode("utf-8")'
b='from inquiry_cancellation_email import confirmation_html; button_html=confirmation_html(text); payload=json.dumps({"from":"BIG PAW <noreply@bigpaw.site>","to":[to_email],"subject":subject,"text":text,**({"html":button_html} if button_html else {})}).encode("utf-8")'
if a in s:
    assert s.count(a)==1
    s=s.replace(a,b,1)
a='        msg.set_content(text)\n        ctx=ssl.create_default_context()'
b='        msg.set_content(text)\n        from inquiry_cancellation_email import confirmation_html\n        button_html=confirmation_html(text)\n        if button_html: msg.add_alternative(button_html,subtype="html")\n        ctx=ssl.create_default_context()'
if a in s:
    assert s.count(a)==1
    s=s.replace(a,b,1)
p.write_text(s)

# Keep new UI links independent of gallery, uploads and existing page handlers.
for name in ('breeder-inquiries.html','messages.html','operator-admin.html','operator-sale-confirmations.html','mypage.html'):
    p=ROOT/name;s=p.read_text();tag='<script src="assets/inquiry-cancellation-links.js"></script>'
    if tag not in s:
        assert '</body>' in s
        s=s.replace('</body>',tag+'</body>',1);p.write_text(s)
p=ROOT/'breeder-deal-report.html';s=p.read_text()
a="workflow.querySelectorAll('[data-cancel]').forEach(el=>el.onclick=()=>cancelSale(el.dataset.cancel));"
b="workflow.querySelectorAll('[data-cancel]').forEach(el=>{el.textContent='取引中止を申請';el.onclick=async()=>{try{const d=await api('/inquiries');const match=await Promise.all(d.map(async q=>{const deal=await BigPawAPI.deal(q.id).catch(()=>null);return deal?.id===el.dataset.cancel?q.id:null}));const id=match.find(Boolean);if(id)location.href='breeder-cancellation.html?inquiry='+encodeURIComponent(id);else msg('対象の問い合わせを問い合わせ管理から選んでください。')}catch(e){msg(e.message)}}});"
if a in s:s=s.replace(a,b,1);p.write_text(s)
print('INQUIRY_CANCELLATION_INSTALLED|isolated_module|legacy_cancel_route=guided|history_retained')

p=ROOT/'mobile-global-nav.js';s=p.read_text()
a="['🤝','成約管理','/operator-deals.html']"
b="['📝','取引中止申請','/operator-cancellations.html'],"+a
if b not in s:
    assert s.count(a)==1
    s=s.replace(a,b,1)
a="const breederPages=['/admin.html'"
b="const breederPages=['/breeder-cancellation.html','/admin.html'"
if a in s:s=s.replace(a,b,1)
a="['🔔','お知らせ','/notifications.html']"
b="['📝','取引中止の確認','/buyer-cancellation-confirmation.html'],"+a
if b not in s:
    assert s.count(a)==1
    s=s.replace(a,b,1)
p.write_text(s)
