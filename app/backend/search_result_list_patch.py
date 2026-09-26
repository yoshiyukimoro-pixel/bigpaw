from pathlib import Path
import re

p=Path('/app/search.html')
s=p.read_text(encoding='utf-8')

# Remove the old client render diagnostic. It serializes DOM/computed-style data
# into repeated /__renderdiag requests and is not part of the product UI.
removed_diag=0
for block in re.findall(r'<script\b[^>]*>.*?</script>',s,flags=re.S|re.I):
    if '__renderdiag' in block:
        s=s.replace(block,'',1); removed_diag+=1

old_css=".result-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:12px}.result-card{overflow:hidden}.result-pic{height:145px;background:#f8e9ef;overflow:hidden;display:grid;place-items:center;font-size:55px}.result-pic img{width:100%;height:100%;object-fit:cover}"
new_css=".result-grid{display:block!important;background:#fff!important}.result-card{position:relative!important;display:block!important;overflow:visible!important;margin:0!important;padding:15px 0 20px!important;border:0!important;border-bottom:1px solid #e8e1e4!important;border-radius:0!important;box-shadow:none!important;text-decoration:none!important;color:inherit!important;background:#fff!important;content-visibility:visible!important}.result-card:first-child{border-top:1px solid #e8e1e4!important}.result-title{font-size:20px!important;font-weight:900!important;line-height:1.35!important;padding:0 2px 12px!important;color:#38252e!important}.result-row{display:grid!important;grid-template-columns:minmax(0,49%) minmax(0,51%)!important;gap:0!important;padding:0!important;align-items:start!important}.result-pic-wrap{position:relative!important;min-width:0!important}.result-pic{width:100%!important;aspect-ratio:1/1!important;background:#f8f4f6!important;overflow:hidden!important;display:grid!important;place-items:center!important;font-size:55px!important;border-radius:5px!important;border:1px solid #eee5e9!important}.result-pic img{width:100%!important;height:100%!important;object-fit:contain!important;object-position:center!important;display:block!important;background:#f8f4f6!important}.result-gender{position:absolute!important;right:4px!important;bottom:4px!important;padding:3px 7px!important;border-radius:4px!important;background:rgba(255,255,255,.96)!important;border:1px solid #d8e4f4!important;color:#3d75a8!important;font-size:12px!important;font-weight:900!important;line-height:1.2!important}.result-info{min-width:0!important;padding:1px 2px 0 16px!important}.result-meta{display:flex!important;align-items:center!important;gap:7px!important;flex-wrap:wrap!important;font-size:14px!important;margin-bottom:8px!important;color:#4f333e!important}.result-status{display:inline-flex!important;align-items:center!important;padding:3px 7px!important;border-radius:4px!important;background:#e7f4e8!important;color:#3c7744!important;border:1px solid #b9dcbf!important;font-weight:800!important}.result-line{font-size:14px!important;line-height:1.65!important;color:#4e383f!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}.result-info .price{font-size:22px!important;line-height:1.35!important;color:#ef5c74!important;font-weight:900!important;margin-top:7px!important;white-space:nowrap!important}.result-appeal{font-size:12px!important;line-height:1.5!important;color:#81747a!important;margin-top:7px!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;overflow:hidden!important}.result-breeder{font-size:12px!important;line-height:1.4!important;color:#b85d82!important;margin-top:8px!important;font-weight:800!important}.result-card:active{opacity:.78!important}@media(max-width:390px){.result-title{font-size:18px!important}.result-row{grid-template-columns:minmax(0,48%) minmax(0,52%)!important}.result-info{padding-left:12px!important}.result-meta,.result-line{font-size:13px!important}.result-info .price{font-size:20px!important}}"
if old_css in s:
    s=s.replace(old_css,new_css,1)
elif new_css not in s:
    raise SystemExit(('search_result_css_marker_missing',s.count(old_css),s.count(new_css)))

old_media="@media(min-width:700px){.result-grid{grid-template-columns:repeat(3,1fr)}.result-pic{height:170px}}"
new_media="@media(min-width:700px){.result-card{padding:18px 0 24px!important}.result-title{font-size:22px!important}.result-row{grid-template-columns:330px minmax(0,1fr)!important}.result-info{padding-left:22px!important}.result-line{font-size:15px!important}.result-info .price{font-size:25px!important}.result-appeal{font-size:13px!important}}"
if old_media in s:
    s=s.replace(old_media,new_media,1)
elif new_media not in s:
    raise SystemExit(('search_result_media_marker_missing',s.count(old_media),s.count(new_media)))

old_card="`<a class=\"card result-card\" href=\"puppy-detail.html?id=${encodeURIComponent(p.id)}\"><div class=\"result-pic\">${p.imageUrl?`<img src=\"${BigPaw.esc(p.imageUrl)}\" alt=\"${BigPaw.esc(p.breed)}\">`:'🐾'}</div><div class=\"pad\"><h3 style=\"font-size:15px\">${BigPaw.esc(p.breed)}｜${BigPaw.esc(p.gender)}</h3><div class=\"muted\">${BigPaw.esc(p.color)}・${BigPaw.esc(p.area)}</div><div class=\"price\" style=\"font-size:20px\">${BigPaw.currency(p.price)}</div></div></a>`"
new_card="`<a class=\"card result-card\" href=\"puppy-detail.html?id=${encodeURIComponent(p.id)}\"><div class=\"result-title\">${BigPaw.esc(p.breed)}</div><div class=\"result-row\"><div class=\"result-pic-wrap\"><div class=\"result-pic\">${p.imageUrl?`<img src=\"${BigPaw.esc(String(p.imageUrl).replace('kind=card','kind=list'))}\" alt=\"${BigPaw.esc(p.breed)}\" loading=\"eager\" decoding=\"async\" fetchpriority=\"auto\">`:'🐾'}</div>${p.gender?`<span class=\"result-gender\">${BigPaw.esc(p.gender)}</span>`:''}</div><div class=\"result-info\"><div class=\"result-meta\"><span class=\"result-status\">${BigPaw.esc(p.status||'募集中')}</span><span>${BigPaw.esc(p.area||'')}</span></div><div class=\"result-line\">誕生：${BigPaw.esc(String(p.birth||'未登録').replace(/-/g,'/'))}</div><div class=\"result-line\">毛色：${BigPaw.esc(p.color||'未登録')}</div><div class=\"price\">${BigPaw.currency(p.price)} <span style=\"font-size:12px;color:#5c5357;font-weight:700\">(税込)</span></div>${p.desc?`<div class=\"result-appeal\">${BigPaw.esc(p.desc)}</div>`:''}<div class=\"result-breeder\">この子の詳細を見る ›</div></div></div></a>`"
if old_card in s:
    s=s.replace(old_card,new_card,1)
elif new_card not in s:
    raise SystemExit(('search_result_card_marker_missing',s.count(old_card),s.count(new_card)))

# Final runtime guard. Even if an older renderer runs later in the browser, every
# result card is normalized back to the required horizontal layout. This only
# runs on search.html and never touches puppy-detail.html.
for pat in (
    r'<style id="bigpaw-search-final-layout-v1">.*?</style>',
    r'<script id="bigpaw-search-final-layout-v1-js">.*?</script>',
):
    s=re.sub(pat,'',s,flags=re.S)

final_style=r'''<style id="bigpaw-search-final-layout-v1">
#results.result-grid{display:block!important;background:#fff!important;position:relative!important}
#results .result-card{display:block!important;position:relative!important;width:100%!important;margin:0!important;padding:16px 0 20px!important;border:0!important;border-bottom:1px solid #e7dfe3!important;border-radius:0!important;box-shadow:none!important;background:#fff!important;text-decoration:none!important;color:inherit!important;overflow:visible!important}
#results .result-card:first-child{border-top:1px solid #e7dfe3!important}
#results .result-title{font-size:20px!important;font-weight:900!important;line-height:1.35!important;margin:0!important;padding:0 2px 12px!important;color:#3e1723!important}
#results .result-row{display:grid!important;grid-template-columns:minmax(0,49%) minmax(0,51%)!important;gap:0!important;align-items:start!important;padding:0!important}
#results .result-pic-wrap{position:relative!important;min-width:0!important}
#results .result-pic{width:100%!important;height:auto!important;aspect-ratio:1/1!important;margin:0!important;border:1px solid #eee5e9!important;border-radius:4px!important;background:#f7f3f5!important;overflow:hidden!important;display:grid!important;place-items:center!important}
#results .result-pic img{width:100%!important;height:100%!important;display:block!important;object-fit:contain!important;object-position:center!important;background:#f7f3f5!important}
#results .result-gender{position:absolute!important;right:4px!important;bottom:4px!important;padding:3px 7px!important;border-radius:3px!important;background:rgba(255,255,255,.97)!important;border:1px solid #d8e4f4!important;color:#3d75a8!important;font-size:12px!important;font-weight:900!important;line-height:1.2!important}
#results .result-info{min-width:0!important;padding:1px 2px 0 16px!important}
#results .result-meta{display:flex!important;align-items:center!important;gap:7px!important;flex-wrap:wrap!important;font-size:14px!important;margin:0 0 8px!important;color:#4f333e!important}
#results .result-status{display:inline-flex!important;align-items:center!important;padding:3px 7px!important;border-radius:3px!important;background:#e7f4e8!important;color:#3c7744!important;border:1px solid #b9dcbf!important;font-weight:800!important}
#results .result-line{font-size:14px!important;line-height:1.65!important;color:#4e383f!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
#results .result-info .price{font-size:22px!important;line-height:1.35!important;color:#ef5c74!important;font-weight:900!important;margin:7px 0 0!important;white-space:nowrap!important}
#results .result-appeal{font-size:12px!important;line-height:1.5!important;color:#81747a!important;margin-top:7px!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;overflow:hidden!important}
#results .result-breeder{font-size:12px!important;line-height:1.4!important;color:#b85d82!important;margin-top:8px!important;font-weight:800!important}
@media(max-width:390px){#results .result-title{font-size:18px!important}#results .result-row{grid-template-columns:minmax(0,48%) minmax(0,52%)!important}#results .result-info{padding-left:12px!important}#results .result-meta,#results .result-line{font-size:13px!important}#results .result-info .price{font-size:20px!important}}
@media(min-width:700px){#results .result-row{grid-template-columns:330px minmax(0,1fr)!important}#results .result-info{padding-left:22px!important}}
</style>'''
assert '</head>' in s,'search_final_head_missing'
s=s.replace('</head>','<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">'+final_style+'</head>',1)

final_script=r'''<script id="bigpaw-search-final-layout-v1-js">
(function(){
  if(window.__BIGPAW_SEARCH_FINAL_LAYOUT_V1__)return;window.__BIGPAW_SEARCH_FINAL_LAYOUT_V1__=1;
  let queued=false,running=false,observer=null;
  const esc=v=>(window.BigPaw&&BigPaw.esc)?BigPaw.esc(String(v??'')):String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
  const money=v=>(window.BigPaw&&BigPaw.currency)?BigPaw.currency(v):Number(v||0).toLocaleString('ja-JP')+'円';
  async function source(){
    try{if(typeof all!=='undefined'&&Array.isArray(all)&&all.length)return all}catch(_e){}
    try{if(window.BigPawBridge&&typeof BigPawBridge.puppies==='function'){const a=await BigPawBridge.puppies();if(Array.isArray(a))return a}}catch(_e){}
    return [];
  }
  function puppyId(card){try{return new URL(card.getAttribute('href')||'',location.href).searchParams.get('id')||''}catch(_e){return''}}
  async function normalize(){
    queued=false;if(running)return;running=true;
    try{
      const rows=await source(),byId=new Map(rows.map(x=>[String(x.id),x]));
      document.querySelectorAll('#results a.result-card').forEach(card=>{
        const p=byId.get(String(puppyId(card)));if(!p)return;
        const img=p.imageUrl?`<img src="${esc(String(p.imageUrl).replace('kind=card','kind=list'))}" alt="${esc(p.breed||'子犬')}" loading="eager" decoding="async">`:'🐾';
        card.dataset.bpFinalLayout='20260926-final1';
        card.innerHTML=`<div class="result-title">${esc(p.breed||'子犬')}</div><div class="result-row"><div class="result-pic-wrap"><div class="result-pic">${img}</div>${p.gender?`<span class="result-gender">${esc(p.gender)}</span>`:''}</div><div class="result-info"><div class="result-meta"><span class="result-status">${esc(p.status||'募集中')}</span><span>${esc(p.area||'')}</span></div><div class="result-line">誕生：${esc(String(p.birth||'未登録').replace(/-/g,'/'))}</div><div class="result-line">毛色：${esc(p.color||'未登録')}</div><div class="price">${money(p.price)} <span style="font-size:12px;color:#5c5357;font-weight:700">(税込)</span></div>${p.desc?`<div class="result-appeal">${esc(p.desc)}</div>`:''}<div class="result-breeder">この子の詳細を見る ›</div></div></div>`;
      });
      document.documentElement.dataset.bpSearchLayout='20260926-final1';
    }finally{running=false}
  }
  function queue(){if(queued)return;queued=true;requestAnimationFrame(normalize)}
  function install(){const root=document.getElementById('results');if(!root)return;if(!observer){observer=new MutationObserver(queue);observer.observe(root,{childList:true})}queue()}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
  window.addEventListener('pageshow',queue);
})();
</script>'''
assert '</body>' in s,'search_final_body_missing'
s=s.replace('</body>',final_script+'</body>',1)

# Build gate: do not allow a deployment that lacks the final layout hardening.
required=(
    'bigpaw-search-final-layout-v1',
    'bigpaw-search-final-layout-v1-js',
    "grid-template-columns:minmax(0,49%) minmax(0,51%)",
    "data-bp-final-layout",
    "String(p.imageUrl).replace('kind=card','kind=list')",
    '誕生：',
    '毛色：',
)
for marker in required:
    if marker not in s:
        raise SystemExit('PUBLIC_SEARCH_FINAL_GATE_FAIL|missing='+marker)

p.write_text(s,encoding='utf-8')
verify=p.read_text(encoding='utf-8')
if verify.count('id="bigpaw-search-final-layout-v1"')!=1 or verify.count('id="bigpaw-search-final-layout-v1-js"')!=1:
    raise SystemExit('PUBLIC_SEARCH_FINAL_GATE_FAIL|duplicate_or_missing_runtime_guard')
print(f'PUBLIC_SEARCH_LIST_OK|layout=min_breeder_reference|photo_left=49|info_right=51|mobile=two_column|image=full_contain|list_variant=preserve_aspect|eager_images=enabled|card_shadow=removed|birth_color_gender_price=shown|breeder_identity=hidden|renderdiag_removed={removed_diag}',flush=True)
print('PUBLIC_SEARCH_FINAL_GATE_OK|scope=search_only|runtime_dom_guard=enabled|photo_left_info_right=locked|detail_page=untouched|cache_meta=no_store|version=20260926-final1',flush=True)
