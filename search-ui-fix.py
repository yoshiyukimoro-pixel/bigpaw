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
 p.write_text(s,encoding='utf-8')
