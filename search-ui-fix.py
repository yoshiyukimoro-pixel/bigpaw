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

 p.write_text(s,encoding='utf-8')
