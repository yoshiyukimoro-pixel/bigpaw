from pathlib import Path
p=Path('search.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 # A stale full-screen breed-picker overlay can remain visually active on iOS after navigation.
 # Force all picker/modal overlays closed once search.html loads; the normal picker can reopen them explicitly.
 marker='</head>'
 css='''<style id="bigpaw-search-overlay-safety">\n/* Search results must never start behind a stale picker/modal overlay. */\nbody:not(.breed-picker-open) .breed-picker-overlay,body:not(.breed-picker-open) .breed-picker-modal,body:not(.breed-picker-open) [data-breed-picker-overlay],#bpv6Modal,#bpBreedModal{display:none!important;pointer-events:none!important;opacity:0!important}\n</style>\n'''
 if 'bigpaw-search-overlay-safety' not in s and marker in s:s=s.replace(marker,css+marker,1)
 # Clear stale open-state classes/inline overlays on page show (including Safari bfcache).
 js='''<script id="bigpaw-search-overlay-reset">\n(function(){function reset(){document.body.classList.remove('breed-picker-open','modal-open','no-scroll');document.querySelectorAll('.breed-picker-overlay,.breed-picker-modal,[data-breed-picker-overlay],#bpv6Modal,#bpBreedModal').forEach(function(e){e.style.display='none';e.style.pointerEvents='none';e.style.opacity='0'})}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',reset);else reset();window.addEventListener('pageshow',reset)})();\n</script>\n'''
 if 'bigpaw-search-overlay-reset' not in s:s=s.replace('</body>',js+'</body>',1)

 # iOS Safari/bfcache hard reset: search content itself must always render fully opaque and interactive.
 hard='''<style id="bigpaw-search-ios-visibility">
html,body{opacity:1!important;visibility:visible!important;filter:none!important}
main.finder,.filter-card,.result-grid,.result-card,.sticky{opacity:1!important;visibility:visible!important;filter:none!important;pointer-events:auto!important}
</style>
<script id="bigpaw-search-ios-reset">
(function(){function hardReset(){var a=[document.documentElement,document.body,document.querySelector('main.finder'),document.querySelector('.filter-card'),document.querySelector('.result-grid')];a.forEach(function(e){if(!e)return;e.style.opacity='1';e.style.visibility='visible';e.style.filter='none';e.style.pointerEvents='auto'});document.querySelectorAll('.result-card').forEach(function(e){e.style.opacity='1';e.style.visibility='visible';e.style.filter='none';e.style.pointerEvents='auto'})}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',hardReset);else hardReset();window.addEventListener('pageshow',hardReset);window.addEventListener('focus',hardReset)})();
</script>
'''
 if 'bigpaw-search-ios-visibility' not in s:s=s.replace('</body>',hard+'</body>',1)


 # Search page only: neutral white canvas and normal contrast.
 white='''<style id="bigpaw-search-white-canvas">
html,body{background:#fff!important;color:#222!important}
main.finder{background:#fff!important;color:#222!important}
.filter-card,.result-card{background:#fff!important;color:#222!important}
.result-card *{opacity:1!important;visibility:visible!important}
</style>
'''
 if 'bigpaw-search-white-canvas' not in s:s=s.replace('</head>',white+'</head>',1)


 diag='''<script id="bigpaw-render-diagnostic">
(function(){
function snap(){
 try{
  var pts=[[innerWidth/2,innerHeight/2],[innerWidth/2,Math.min(innerHeight-1,180)],[innerWidth/2,Math.max(0,innerHeight-120)]],out=[];
  pts.forEach(function(p){
   out.push(document.elementsFromPoint(p[0],p[1]).slice(0,8).map(function(e){
    var c=getComputedStyle(e),r=e.getBoundingClientRect();
    return {t:e.tagName,i:e.id||'',c:(e.className&&String(e.className).slice(0,80))||'',bg:c.backgroundColor,o:c.opacity,f:c.filter,pe:c.pointerEvents,pos:c.position,z:c.zIndex,w:Math.round(r.width),h:Math.round(r.height)}
   }))
  });
  var b=getComputedStyle(document.body),h=getComputedStyle(document.documentElement);
  var d={v:'renderdiag-1',url:location.href,body:{bg:b.backgroundColor,o:b.opacity,f:b.filter},html:{bg:h.backgroundColor,o:h.opacity,f:h.filter},pts:out};
  (new Image()).src='/__renderdiag?d='+encodeURIComponent(JSON.stringify(d).slice(0,6000))+'&t='+Date.now()
 }catch(e){(new Image()).src='/__renderdiag?err='+encodeURIComponent(String(e))}
}
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(snap,700)});else setTimeout(snap,700);
window.addEventListener('pageshow',function(){setTimeout(snap,700)})
})();
</script>
'''
 if 'bigpaw-render-diagnostic' not in s:s=s.replace('</body>',diag+'</body>',1)


 fix='''<style id="bigpaw-ios-backdrop-fix">
.site-header{-webkit-backdrop-filter:none!important;backdrop-filter:none!important;background:#fff!important}
html,body,main.finder{background:#fff!important}
</style>
<script id="bigpaw-ios-backdrop-reset">
(function(){function x(){var h=document.querySelector('.site-header');if(h){h.style.webkitBackdropFilter='none';h.style.backdropFilter='none';h.style.background='#fff'}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',x);else x();window.addEventListener('pageshow',x)})();
</script>
'''
 if 'bigpaw-ios-backdrop-fix' not in s:s=s.replace('</head>',fix+'</head>',1)


 kill='''<style id="bigpaw-kill-hidden-native-select">
#fBreed{display:none!important;opacity:1!important;position:static!important;width:auto!important;height:auto!important}
</style>
<script id="bigpaw-kill-select-layer">
(function(){function k(){var s=document.getElementById('fBreed');if(s){s.style.setProperty('display','none','important');s.style.setProperty('opacity','1','important');s.style.setProperty('pointer-events','none','important');s.style.setProperty('position','static','important');s.blur&&s.blur()}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',k);else k();window.addEventListener('pageshow',k)})();
</script>
'''
 if 'bigpaw-kill-hidden-native-select' not in s:s=s.replace('</head>',kill+'</head>',1)


 nuclear='''<style id="bigpaw-search-layer-reset">
#bpv6Modal,#bpBreedModal,.breed-picker-overlay,.breed-picker-modal,[data-breed-picker-overlay]{display:none!important}
.result-grid{position:relative!important;z-index:2147482000!important;background:#fff!important;isolation:isolate!important}
.result-card{position:relative!important;z-index:2147482001!important;background:#fff!important;opacity:1!important;filter:none!important;mix-blend-mode:normal!important}
.result-card,.result-card *{visibility:visible!important;opacity:1!important;filter:none!important}
.sticky{z-index:2147483002!important}
</style>
<script id="bigpaw-search-layer-reset-js">
(function(){function r(){document.querySelectorAll('#bpv6Modal,#bpBreedModal,.breed-picker-overlay,.breed-picker-modal,[data-breed-picker-overlay]').forEach(function(e){e.remove()});var g=document.querySelector('.result-grid');if(g){g.style.setProperty('z-index','2147482000','important');g.style.setProperty('position','relative','important')}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',function(){setTimeout(r,0)});else setTimeout(r,0);window.addEventListener('pageshow',r)})();
</script>
'''
 if 'bigpaw-search-layer-reset' not in s:s=s.replace('</head>',nuclear+'</head>',1)


 clean='''<style id="bigpaw-search-rebuild">
html,body{background:#fff!important}
main.finder{display:block!important;background:#fff!important;opacity:1!important;filter:none!important}
#bigpawFreshSearch{position:relative;z-index:2147483000;background:#fff;color:#222;min-height:100vh;padding:18px 16px 110px}
#bigpawFreshSearch .fresh-title{font-size:24px;font-weight:900;margin:0 0 14px}

#bigpawFreshSearch .fresh-filters{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:14px 0 18px}
#bigpawFreshSearch .fresh-filters select{width:100%;height:48px;border:1px solid #eadfe5;border-radius:12px;background:#fff;padding:0 10px;font-size:14px}
#bigpawFreshSearch .fresh-head{display:flex;justify-content:space-between;align-items:center;margin:8px 0}
#bigpawFreshSearch .fresh-card{border:1px solid #eadfe5;border-radius:16px;background:#fff;overflow:hidden;margin-top:14px;box-shadow:0 4px 16px rgba(0,0,0,.05)}
#bigpawFreshSearch .fresh-card img{display:block;width:100%;height:260px;object-fit:cover;background:#f8e9ef}
#bigpawFreshSearch .fresh-body{padding:14px}
#bigpawFreshSearch .fresh-breed{font-size:18px;font-weight:900}
#bigpawFreshSearch .fresh-meta{margin-top:5px;color:#6f666b}
#bigpawFreshSearch .fresh-price{margin-top:8px;font-size:20px;font-weight:900}
</style>
<script id="bigpaw-search-rebuild-js">
(function(){async function build(){var old=document.querySelector('main.finder');if(!old)return;var root=document.createElement('main');root.id='bigpawFreshSearch';root.innerHTML='<h1 class="fresh-title">子犬を探す</h1><div class="fresh-filters"><select id="freshGender"><option value="all">性別：すべて</option><option value="male">男の子</option><option value="female">女の子</option></select><select id="freshArea"><option value="all">地域：すべて</option></select><select id="freshMin"><option value="0">最低価格なし</option><option value="200000">20万円〜</option><option value="300000">30万円〜</option><option value="400000">40万円〜</option></select><select id="freshMax"><option value="999999999">最高価格なし</option><option value="300000">〜30万円</option><option value="400000">〜40万円</option><option value="500000">〜50万円</option></select></div><div class="fresh-head"><b>検索結果</b><span id="freshCount">読み込み中...</span></div><div id="freshResults"></div>';old.replaceWith(root);document.querySelectorAll('#bpv6Modal,#bpBreedModal,.breed-picker-overlay,.breed-picker-modal,[data-breed-picker-overlay],.sticky').forEach(function(e){e.remove()});try{var all=await BigPawBridge.puppies();var source=all.slice();var q=new URLSearchParams(location.search),keys=(q.get('breed')||'').split(',').filter(Boolean);function renderFresh(){all=source.slice();if(keys.length)all=all.filter(function(p){return keys.indexOf(p.breedKey)>=0});var g=document.getElementById('freshGender').value,a=document.getElementById('freshArea').value,mi=Number(document.getElementById('freshMin').value),ma=Number(document.getElementById('freshMax').value);if(g!=='all')all=all.filter(function(p){return p.genderKey===g});if(a!=='all')all=all.filter(function(p){return p.areaKey===a||p.area===a});all=all.filter(function(p){var n=Number(p.price)||0;return n>=mi&&n<=ma});document.getElementById('freshCount').textContent=all.length+'頭';var box=document.getElementById('freshResults');box.innerHTML='';all.forEach(function(p){var a=document.createElement('article');a.className='fresh-card';var img=p.imageUrl?'<img src="'+BigPaw.esc(p.imageUrl)+'" alt="">':'<div style="height:220px;display:grid;place-items:center;font-size:72px;background:#f8e9ef">🐩</div>';a.innerHTML=img+'<div class="fresh-body"><div class="fresh-breed">'+BigPaw.esc(p.breed||'')+'｜'+BigPaw.esc(p.gender||'')+'</div><div class="fresh-meta">'+BigPaw.esc(p.color||'')+' ・ '+BigPaw.esc(p.area||'')+'</div><div class="fresh-price">'+BigPaw.currency(p.price)+' <small>税込</small></div></div>';a.onclick=function(){location.href='puppy-detail.html?id='+encodeURIComponent(p.id)};box.appendChild(a)})}var area=document.getElementById('freshArea'),areas=[];source.forEach(function(p){var v=p.areaKey||p.area;if(v&&areas.indexOf(v)<0)areas.push(v)});areas.forEach(function(v){var o=document.createElement('option');o.value=v;o.textContent=v;area.appendChild(o)});document.querySelectorAll('.fresh-filters select').forEach(function(x){x.onchange=renderFresh});renderFresh()}catch(e){document.getElementById('freshCount').textContent='読み込みに失敗しました'}}function go(){if(window.BigPawBridge)build();else setTimeout(go,50)}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',go);else go()})();
</script>
'''
 if 'bigpaw-search-rebuild' not in s:s=s.replace('</body>',clean+'</body>',1)

 p.write_text(s,encoding='utf-8')
