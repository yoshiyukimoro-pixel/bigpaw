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
# BIGPAW_BREEDER_STATUS_PANEL: show the logged-in account and breeder application status.
breeder_panel="""<script id="BIGPAW_BREEDER_STATUS_PANEL">(()=>{async function addBreederStatus(){try{if(document.getElementById('bigpawBreederStatusPanel'))return;let me=null;let rows=[];try{const mr=await fetch('/api/me',{credentials:'same-origin'});if(mr.ok)me=await mr.json()}catch(e){}try{const ar=await fetch('/api/breeder-applications',{credentials:'same-origin'});if(ar.ok){const data=await ar.json();rows=Array.isArray(data)?data:(data?[data]:[])}}catch(e){}const latest=rows[0]||null;const status=String(latest?.status||'').toLowerCase();const role=String(me?.role||'').toLowerCase();const approved=(status==='approved'||role==='breeder'||role==='operator');const pending=status==='pending';const rejected=status==='rejected';const box=document.createElement('section');box.id='bigpawBreederStatusPanel';box.className='card';box.style.marginTop='16px';let statusText='申請データが見つかりません';if(status==='approved')statusText='承認済み';else if(status==='pending')statusText='審査中';else if(status==='rejected')statusText='差し戻し';else if(status)statusText=status;let actions='';if(approved){actions='<p><a class="btn btn-main" href="/breeder-puppy-new.html">子犬を登録する</a> <a class="btn btn-sub" href="/admin.html">掲載管理を見る</a></p>'}else if(pending){actions='<p class="muted">現在、運営側の審査待ちです。運営画面で承認が必要です。</p>'}else if(rejected){actions='<p><a class="btn btn-main" href="/breeder-register.html">申請内容を修正する</a></p>'}else{actions='<p><a class="btn btn-main" href="/breeder-register.html">ブリーダー申請をする</a></p>'}box.innerHTML='<h2>ブリーダー管理</h2><p>ログイン中：<b>'+(me?.email||'確認できません')+'</b></p><p>アカウント種別：<b>'+(me?.role||'不明')+'</b></p><p>ブリーダー申請状況：<b>'+statusText+'</b></p>'+actions;const main=document.querySelector('main')||document.querySelector('.container')||document.body;main.appendChild(box)}catch(e){}}document.readyState==='loading'?document.addEventListener('DOMContentLoaded',addBreederStatus):addBreederStatus();addEventListener('pageshow',addBreederStatus)})();</script>"""
s=s.replace(/<script id="BIGPAW_BREEDER_APPROVED_LINK">[\s\S]*?<\/script>/g,'') if False else s
if 'BIGPAW_BREEDER_STATUS_PANEL' not in s:
 s=s.replace('</body>',breeder_panel+'</body>')
p.write_text(s,encoding='utf-8')
