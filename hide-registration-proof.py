from pathlib import Path
for fn in ['breeders.html','breeder-detail.html']:
 p=Path(fn)
 if not p.exists(): continue
 s=p.read_text(encoding='utf-8',errors='replace')
 inject=r'''<script id="bp-hide-registration-proof">(function(){function clean(){const w=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);const a=[];while(w.nextNode())a.push(w.currentNode);for(const n of a){const v=n.nodeValue||'';if(v.includes('[REGISTRATION_PROOF]')){n.nodeValue=v.replace(/\[REGISTRATION_PROOF\][^\s<]*/g,'').trim();}}}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',clean);else clean();new MutationObserver(clean).observe(document.documentElement,{childList:true,subtree:true,characterData:true});})();</script>'''
 if 'bp-hide-registration-proof' not in s:s=s.replace('</body>',inject+'</body>')
 p.write_text(s,encoding='utf-8')
