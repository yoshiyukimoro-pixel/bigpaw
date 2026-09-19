from pathlib import Path
p=Path('mypage.html')
s=p.read_text(encoding='utf-8')
if 'mypage-favorites-sync.js' not in s:
 s=s.replace('</body>','<script src="/mypage-favorites-sync.js"></script></body>')
if 'mypage-verify-state-fix.js' not in s:
 s=s.replace('</body>','<script src="/mypage-verify-state-fix.js"></script></body>')
# BIGPAW_FAV_INLINE: avoid stale external JS on iPhone Safari
inline="""<script id="BIGPAW_FAV_INLINE">(()=>{function syncFav(){let a=[];try{a=JSON.parse(localStorage.getItem('bigpaw_favorites')||'[]')}catch(e){}const n=document.getElementById('favCount');if(n)n.textContent=a.length+'頭'};document.readyState==='loading'?document.addEventListener('DOMContentLoaded',syncFav):syncFav();addEventListener('pageshow',syncFav)})();</script>"""
if 'BIGPAW_FAV_INLINE' not in s:
 s=s.replace('</body>',inline+'</body>')
p.write_text(s,encoding='utf-8')
