from pathlib import Path
# Extra privacy guard: hide direct-contact identifiers if they are accidentally rendered on public breeder pages.
for fn in ['breeders.html','breeder-detail.html']:
 p=Path(fn)
 if not p.exists(): continue
 s=p.read_text(encoding='utf-8',errors='replace')
 inject=r'''<script id="bp-public-contact-privacy">(function(){function clean(){document.querySelectorAll('a[href^="mailto:"],a[href^="tel:"]').forEach(e=>e.remove());document.querySelectorAll('a').forEach(e=>{const h=(e.getAttribute('href')||'').toLowerCase();if(h.includes('instagram.com')||h.includes('line.me')||h.includes('lin.ee'))e.remove()})}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',clean);else clean();new MutationObserver(clean).observe(document.documentElement,{childList:true,subtree:true})})();</script>'''
 if 'bp-public-contact-privacy' not in s:s=s.replace('</body>',inject+'</body>')
 p.write_text(s,encoding='utf-8')
