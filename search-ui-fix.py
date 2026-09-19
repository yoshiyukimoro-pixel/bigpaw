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

 p.write_text(s,encoding='utf-8')
