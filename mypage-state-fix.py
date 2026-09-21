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
# BIGPAW_BREEDER_APPROVED_LINK: show puppy registration button only when this logged-in account has an approved breeder application.
breeder_link="""<script id="BIGPAW_BREEDER_APPROVED_LINK">(()=>{async function addBreederLink(){try{const r=await fetch('/api/breeder-applications',{credentials:'same-origin'});if(!r.ok)return;const rows=await r.json();if(!Array.isArray(rows)||!rows.some(x=>String(x.status||'').toLowerCase()==='approved'))return;if(document.getElementById('bigpawBreederApprovedLink'))return;const box=document.createElement('section');box.id='bigpawBreederApprovedLink';box.className='card';box.style.marginTop='16px';box.innerHTML='<h2>ブリーダー管理</h2><p>承認済みのブリーダーアカウントです。子犬の掲載登録ができます。</p><p><a class="btn btn-main" href="/breeder-puppy-new.html">子犬を登録する</a> <a class="btn btn-sub" href="/admin.html">掲載管理を見る</a></p>';const main=document.querySelector('main')||document.querySelector('.container')||document.body;main.appendChild(box)}catch(e){}}document.readyState==='loading'?document.addEventListener('DOMContentLoaded',addBreederLink):addBreederLink();addEventListener('pageshow',addBreederLink)})();</script>"""
if 'BIGPAW_BREEDER_APPROVED_LINK' not in s:
 s=s.replace('</body>',breeder_link+'</body>')
p.write_text(s,encoding='utf-8')
