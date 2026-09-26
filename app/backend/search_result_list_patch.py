from pathlib import Path
import hashlib
import re

search=Path('/app/search.html')
detail=Path('/app/puppy-detail.html')
s=search.read_text(encoding='utf-8')
detail_hash=hashlib.sha256(detail.read_bytes()).hexdigest() if detail.exists() else ''
VERSION='20260926-final3'

# Remove any earlier experimental/final search-only guard so exactly one final
# implementation is present in the built HTML.
for pat in (
    r'<style id="bigpaw-search-final-layout-v[^"]*">.*?</style>',
    r'<script id="bigpaw-search-final-layout-v[^"]*-js">.*?</script>',
    r'<meta name="bigpaw-search-layout"[^>]*>',
    r'<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">',
):
    s=re.sub(pat,'',s,flags=re.S|re.I)

style=r'''<style id="bigpaw-search-final-layout-v3">
/* Search page only: Minna-no-Breeder-style list. No selector here targets puppy-detail.html. */
#results.result-grid{display:block!important;background:#fff!important;position:relative!important;z-index:1!important}
#results .result-card{width:100%!important;margin:0!important;padding:16px 0 20px!important;border:0!important;border-bottom:1px solid #e5dde1!important;border-radius:0!important;box-shadow:none!important;background:#fff!important;color:#321a22!important;text-decoration:none!important;overflow:visible!important;position:relative!important}
#results .result-card:first-child{border-top:1px solid #e5dde1!important}
/* Safety before JS normalization: even legacy cards are horizontal immediately. */
#results .result-card:not([data-bp-final-layout]){display:grid!important;grid-template-columns:minmax(0,49%) minmax(0,51%)!important;align-items:start!important}
#results .result-card:not([data-bp-final-layout])>.result-pic{grid-column:1!important;width:100%!important;height:auto!important;aspect-ratio:1/1!important;margin:0!important}
#results .result-card:not([data-bp-final-layout])>.pad{grid-column:2!important;padding:4px 2px 0 14px!important}
#results .result-title{font-size:20px!important;font-weight:900!important;line-height:1.35!important;margin:0!important;padding:0 2px 12px!important;color:#46151f!important}
#results .result-row{display:grid!important;grid-template-columns:minmax(0,49%) minmax(0,51%)!important;gap:0!important;align-items:start!important;padding:0!important}
#results .result-pic-wrap{position:relative!important;min-width:0!important}
#results .result-pic{width:100%!important;height:auto!important;aspect-ratio:1/1!important;margin:0!important;border:1px solid #ece2e7!important;border-radius:4px!important;background:#f8f4f6!important;overflow:hidden!important;display:grid!important;place-items:center!important}
#results .result-pic img{width:100%!important;height:100%!important;display:block!important;object-fit:contain!important;object-position:center!important;background:#f8f4f6!important}
#results .result-gender{position:absolute!important;right:4px!important;bottom:4px!important;padding:3px 7px!important;border-radius:3px!important;background:rgba(255,255,255,.97)!important;border:1px solid #d5e3f2!important;color:#3675ad!important;font-size:12px!important;font-weight:900!important;line-height:1.2!important}
#results .result-info{min-width:0!important;padding:1px 2px 0 15px!important}
#results .result-meta{display:flex!important;align-items:center!important;gap:7px!important;flex-wrap:wrap!important;font-size:14px!important;line-height:1.4!important;margin:0 0 7px!important;color:#532b35!important}
#results .result-status{display:inline-flex!important;align-items:center!important;padding:3px 7px!important;border-radius:3px!important;background:#e4f3e4!important;color:#3e7d47!important;border:1px solid #b7d8ba!important;font-weight:800!important}
#results .result-line{font-size:14px!important;line-height:1.58!important;color:#55353e!important;white-space:nowrap!important;overflow:hidden!important;text-overflow:ellipsis!important}
#results .result-info .price{font-size:22px!important;line-height:1.35!important;color:#ed5a70!important;font-weight:900!important;margin:7px 0 0!important;white-space:nowrap!important}
#results .result-appeal{font-size:12px!important;line-height:1.48!important;color:#81747a!important;margin-top:7px!important;display:-webkit-box!important;-webkit-line-clamp:2!important;-webkit-box-orient:vertical!important;overflow:hidden!important}
#results .result-more{font-size:12px!important;line-height:1.4!important;color:#a64f73!important;margin-top:8px!important;font-weight:800!important}
@media(max-width:390px){#results .result-title{font-size:18px!important}#results .result-row,#results .result-card:not([data-bp-final-layout]){grid-template-columns:minmax(0,48%) minmax(0,52%)!important}#results .result-info{padding-left:11px!important}#results .result-meta,#results .result-line{font-size:13px!important}#results .result-info .price{font-size:20px!important}}
@media(min-width:700px){#results .result-row{grid-template-columns:330px minmax(0,1fr)!important}#results .result-card:not([data-bp-final-layout]){grid-template-columns:330px minmax(0,1fr)!important}#results .result-info{padding-left:22px!important}}
</style>'''

script=r'''<script id="bigpaw-search-final-layout-v3-js">
(function(){
'use strict';
const VERSION='20260926-final3';
if(window.__BIGPAW_SEARCH_FINAL_LAYOUT_V3__)return;window.__BIGPAW_SEARCH_FINAL_LAYOUT_V3__=1;
let queued=false,running=false,observer=null;
const esc=v=>(window.BigPaw&&typeof BigPaw.esc==='function')?BigPaw.esc(String(v??'')):String(v??'').replace(/[&<>"']/g,m=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[m]));
const money=v=>(window.BigPaw&&typeof BigPaw.currency==='function')?BigPaw.currency(v):Number(v||0).toLocaleString('ja-JP')+'円';
function listImage(raw){
  if(!raw)return'';
  try{
    const u=new URL(String(raw),location.href);
    if(u.origin===location.origin&&u.pathname.indexOf('/uploads/')===0)u.pathname='/media/'+u.pathname.slice('/uploads/'.length);
    if(u.origin===location.origin&&u.pathname.indexOf('/media/')===0){u.searchParams.set('kind','list');u.searchParams.set('v',VERSION);return u.pathname+u.search;}
    if(u.searchParams.has('kind'))u.searchParams.set('kind','list');
    return u.origin===location.origin?u.pathname+u.search+u.hash:u.href;
  }catch(_e){return String(raw).replace('kind=card','kind=list')}
}
async function rows(){
  try{if(typeof all!=='undefined'&&Array.isArray(all)&&all.length)return all}catch(_e){}
  try{if(window.BigPawBridge&&typeof BigPawBridge.puppies==='function'){const a=await BigPawBridge.puppies();if(Array.isArray(a))return a}}catch(_e){}
  return[];
}
function idOf(card){try{return new URL(card.getAttribute('href')||'',location.href).searchParams.get('id')||''}catch(_e){return''}}
async function normalize(){
  queued=false;if(running)return;running=true;
  try{
    const data=await rows(),byId=new Map(data.map(p=>[String(p.id),p]));
    document.querySelectorAll('#results a.result-card').forEach(card=>{
      if(card.getAttribute('data-bp-final-layout')===VERSION)return;
      const p=byId.get(String(idOf(card)));if(!p)return;
      const src=listImage(p.imageUrl);
      const img=src?`<img src="${esc(src)}" alt="${esc(p.breed||'子犬')}" loading="eager" decoding="async">`:'🐾';
      card.setAttribute('data-bp-final-layout',VERSION);
      card.innerHTML=`<div class="result-title">${esc(p.breed||'子犬')}</div><div class="result-row"><div class="result-pic-wrap"><div class="result-pic">${img}</div>${p.gender?`<span class="result-gender">${esc(p.gender)}</span>`:''}</div><div class="result-info"><div class="result-meta"><span class="result-status">${esc(p.status||'募集中')}</span><span>${esc(p.area||'')}</span></div><div class="result-line">誕生：${esc(String(p.birth||'未登録').replace(/-/g,'/'))}</div><div class="result-line">毛色：${esc(p.color||'未登録')}</div><div class="price">${money(p.price)} <span style="font-size:12px;color:#5c5357;font-weight:700">(税込)</span></div>${p.desc?`<div class="result-appeal">${esc(p.desc)}</div>`:''}<div class="result-more">この子の詳細を見る ›</div></div></div>`;
    });
    document.documentElement.setAttribute('data-bp-search-layout',VERSION);
  }finally{running=false}
}
function queue(){if(queued)return;queued=true;requestAnimationFrame(normalize)}
function install(){const root=document.getElementById('results');if(!root)return;if(!observer){observer=new MutationObserver(queue);observer.observe(root,{childList:true})}queue()}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',install,{once:true});else install();
window.addEventListener('pageshow',queue);
})();
</script>'''

if '</head>' not in s or '</body>' not in s:
    raise SystemExit('PUBLIC_SEARCH_FINAL_GATE_FAIL|missing_document_markers')
s=s.replace('</head>',f'<meta name="bigpaw-search-layout" content="{VERSION}"><meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">{style}</head>',1)
s=s.replace('</body>',script+'</body>',1)

required=(
    'id="bigpaw-search-final-layout-v3"',
    'id="bigpaw-search-final-layout-v3-js"',
    'data-bp-final-layout',
    'grid-template-columns:minmax(0,49%) minmax(0,51%)',
    "u.searchParams.set('kind','list')",
    '誕生：','毛色：','この子の詳細を見る',
)
for marker in required:
    if marker not in s:
        raise SystemExit('PUBLIC_SEARCH_FINAL_GATE_FAIL|missing='+marker)
if s.count('id="bigpaw-search-final-layout-v3"')!=1 or s.count('id="bigpaw-search-final-layout-v3-js"')!=1:
    raise SystemExit('PUBLIC_SEARCH_FINAL_GATE_FAIL|duplicate_final_guard')

search.write_text(s,encoding='utf-8')
verify=search.read_text(encoding='utf-8')
for marker in required:
    if marker not in verify:
        raise SystemExit('PUBLIC_SEARCH_FINAL_GATE_FAIL|postwrite_missing='+marker)
if detail.exists() and hashlib.sha256(detail.read_bytes()).hexdigest()!=detail_hash:
    raise SystemExit('PUBLIC_SEARCH_FINAL_GATE_FAIL|detail_page_changed')

print('PUBLIC_SEARCH_LIST_OK|reference=min_breeder|mobile=horizontal|title=above|photo=left|info=right|birth_color_gender_price=shown|breeder_identity=hidden',flush=True)
print('PUBLIC_SEARCH_FINAL_GATE_OK|scope=search_only|legacy_cards=css_horizontal|runtime_dom_guard=enabled|media=list_preserve_aspect|detail_page=untouched|version='+VERSION,flush=True)
