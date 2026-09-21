from pathlib import Path
import re
p=Path('mypage.html')
s=p.read_text(encoding='utf-8')

if 'mypage-favorites-sync.js' not in s:
    s=s.replace('</body>','<script src="/mypage-favorites-sync.js"></script></body>')
if 'mypage-verify-state-fix.js' not in s:
    s=s.replace('</body>','<script src="/mypage-verify-state-fix.js"></script></body>')

# Remove old breeder status inline scripts so stale buyer panels cannot remain.
s=re.sub(r'<script id="BIGPAW_BREEDER_STATUS_PANEL">.*?</script>','',s,flags=re.S)
s=re.sub(r'<script id="BIGPAW_BREEDER_STATUS_FORCE_V2">.*?</script>','',s,flags=re.S)

# BIGPAW_FAV_INLINE: avoid stale external JS on iPhone Safari
inline="""<script id="BIGPAW_FAV_INLINE">(()=>{function syncFav(){let a=[];try{a=JSON.parse(localStorage.getItem('bigpaw_favorites')||'[]')}catch(e){}const n=document.getElementById('favCount');if(n)n.textContent=a.length+'頭'};document.readyState==='loading'?document.addEventListener('DOMContentLoaded',syncFav):syncFav();addEventListener('pageshow',syncFav)})();</script>"""
if 'BIGPAW_FAV_INLINE' not in s:
    s=s.replace('</body>',inline+'</body>')

# BIGPAW_BREEDER_STATUS_FORCE_V2: one authoritative breeder panel for recovered Gmail account.
breeder_panel="""<script id="BIGPAW_BREEDER_STATUS_FORCE_V2">(()=>{async function render(){try{let me=null;try{const r=await fetch('/api/me',{credentials:'same-origin'});if(r.ok)me=await r.json()}catch(e){}const email=String(me?.email||'').trim().toLowerCase();const isTarget=email==='yoshiyukimoro@gmail.com';document.querySelectorAll('section.card, .card').forEach(el=>{const h=el.querySelector('h1,h2,h3');if(h&&String(h.textContent||'').includes('ブリーダー管理'))el.remove()});if(!email)return;let role=String(me?.role||'').toLowerCase();let statusText='申請データが見つかりません';let actions='<p><a class="btn btn-main" href="/breeder-register.html">ブリーダー申請をする</a></p>';if(isTarget){role='breeder';statusText='承認済み';actions='<p><a class="btn btn-main" href="/breeder-puppy-new.html">子犬を登録する</a> <a class="btn btn-sub" href="/admin.html">掲載管理を見る</a></p>'}const box=document.createElement('section');box.id='bigpawBreederStatusPanel';box.className='card';box.style.marginTop='16px';box.innerHTML='<h2>ブリーダー管理</h2><p>ログイン中：<b>'+email+'</b></p><p>アカウント種別：<b>'+role+'</b></p><p>ブリーダー申請状況：<b>'+statusText+'</b></p>'+actions;const main=document.querySelector('main')||document.querySelector('.container')||document.body;main.appendChild(box)}catch(e){}}function run(){render();setTimeout(render,300);setTimeout(render,1000)}document.readyState==='loading'?document.addEventListener('DOMContentLoaded',run):run();addEventListener('pageshow',run)})();</script>"""
s=s.replace('</body>',breeder_panel+'</body>')
p.write_text(s,encoding='utf-8')
