FROM python:3.13-slim
WORKDIR /app
COPY bigpaw-app.zip /tmp/bigpaw-app.zip
RUN python3 -c "import zipfile; zipfile.ZipFile('/tmp/bigpaw-app.zip').extractall('/app')"
WORKDIR /app/BIG_PAW_v1.0_FINAL3_domain_ready_package
COPY breeder-register-fix.js /tmp/breeder-register-fix.js
COPY auth-return-fix.js /tmp/auth-return-fix.js
COPY mypage-email-verify.js /tmp/mypage-email-verify.js
COPY smtp_patch.py /tmp/smtp_patch.py
RUN python3 -c "from pathlib import Path; p=Path('breeder-register.html'); s=p.read_text(encoding='utf-8'); tag='<script src=\"/breeder-register-fix.js\"></script>'; p.write_text(s.replace('</body>',tag+'</body>') if tag not in s else s,encoding='utf-8')"
RUN cp /tmp/breeder-register-fix.js ./breeder-register-fix.js
RUN cp /tmp/auth-return-fix.js ./auth-return-fix.js
RUN cp /tmp/mypage-email-verify.js ./mypage-email-verify.js
RUN python3 -c "from pathlib import Path; files=['mypage.html','my-page.html','account.html']; tag='<script src=\\\"/mypage-email-verify.js\\\"></script>'; [(lambda p,s: p.write_text(s.replace('</body>',tag+'</body>') if tag not in s else s,encoding='utf-8'))(Path(x),Path(x).read_text(encoding='utf-8')) for x in files if Path(x).exists()]"
RUN python3 -c "from pathlib import Path; tag='<script src=\\\"/auth-return-fix.js\\\"></script>'; files=['breeder-register.html','login.html','register.html','verify-email.html']; [(lambda p,s: p.write_text(s.replace('</body>',tag+'</body>') if tag not in s else s,encoding='utf-8'))(Path(x),Path(x).read_text(encoding='utf-8')) for x in files if Path(x).exists()]"
RUN python3 -c "from pathlib import Path; p=Path('backend/server.py'); s=p.read_text(encoding='utf-8'); old=\"SMTP_HOST = os.environ.get('BIGPAW_SMTP_HOST','').strip()\"; new=\"SMTP_HOST = os.environ.get('BIGPAW_SMTP_HOST','').strip()\\n# Gmail/Railway: use implicit TLS on port 465 when configured.\"; s=s.replace(old,new,1); old2=\"if SMTP_TLS:\\n            ctx=ssl.create_default_context()\\n            with smtplib.SMTP(SMTP_HOST,SMTP_PORT,timeout=15) as smtp:\\n                smtp.starttls(context=ctx)\"; new2=\"if SMTP_TLS:\\n            ctx=ssl.create_default_context()\\n            if SMTP_PORT == 465:\\n                smtp_ctx = smtplib.SMTP_SSL(SMTP_HOST,SMTP_PORT,timeout=15,context=ctx)\\n            else:\\n                smtp_ctx = smtplib.SMTP(SMTP_HOST,SMTP_PORT,timeout=15)\\n            with smtp_ctx as smtp:\\n                if SMTP_PORT != 465: smtp.starttls(context=ctx)\"; s=s.replace(old2,new2,1); old3=\"if IS_PRODUCTION and not sent: print('[BIG PAW] verification mail not sent: SMTP not configured or failed')\\n            return self.send_json(out)\"; new3=\"if IS_PRODUCTION and not sent:\\n                print('[BIG PAW] verification mail not sent: SMTP not configured or failed')\\n                return self.send_json({'error':'email_send_failed','message':'認証メールを送信できませんでした。しばらくしてから再度お試しください。'},502)\\n            return self.send_json(out)\"; s=s.replace(old3,new3,1); p.write_text(s,encoding='utf-8')"
RUN python3 -c "from pathlib import Path; p=Path('backend/server.py'); s=p.read_text(encoding='utf-8'); reps={\"os.environ.get('BIGPAW_SMTP_HOST','')\":\"os.environ.get('BIGPAW_SMTP_HOST') or os.environ.get('SMTP_HOST','')\",\"os.environ.get('BIGPAW_SMTP_USER','')\":\"os.environ.get('BIGPAW_SMTP_USER') or os.environ.get('SMTP_USER','')\",\"os.environ.get('BIGPAW_SMTP_PASSWORD','')\":\"os.environ.get('BIGPAW_SMTP_PASSWORD') or os.environ.get('SMTP_PASSWORD','')\",\"os.environ.get('BIGPAW_SMTP_FROM','')\":\"os.environ.get('BIGPAW_SMTP_FROM') or os.environ.get('SMTP_FROM','')\",\"os.environ.get('BIGPAW_SMTP_PORT','587')\":\"os.environ.get('BIGPAW_SMTP_PORT') or os.environ.get('SMTP_PORT','587')\"}; [None for a,b in reps.items() if not (s:=s.replace(a,b))]; p.write_text(s,encoding='utf-8')"
RUN python3 /tmp/smtp_patch.py
RUN python3 - <<'PY'
from pathlib import Path
for fn in ['backend/server.py','operator-breeders.html','breeder-puppy-new.html','mypage.html']:
 p=Path(fn)
 if not p.exists(): continue
 lines=p.read_text(encoding='utf-8',errors='replace').splitlines()
 print('=== INSPECT',fn,'===')
 for i,line in enumerate(lines):
  if any(k in line.lower() for k in ['breeder','審査','puppy','approve','application']):
   print(f'{i+1}: {line[:500]}')
PY
RUN python3 - <<'PY'
from pathlib import Path
files=['backend/server.py','breeder-fee-agreement.html','operator-breeders.html','breeder-puppy-new.html','assets/api.js','assets/workflow.js']
out=[]
for fn in files:
 p=Path(fn)
 if p.exists():
  out.append('=== '+fn+' ===')
  for i,line in enumerate(p.read_text(encoding='utf-8',errors='replace').splitlines()):
   if any(k in line.lower() for k in ['breeder','application','approve','puppy','審査','申請','承認','子犬']): out.append(f'{i+1}: {line[:1200]}')
Path('flow-inspect.txt').write_text('\\n'.join(out),encoding='utf-8')
PY
COPY inspect_flow.py /tmp/inspect_flow.py
RUN python3 /tmp/inspect_flow.py && cp inspection.txt /tmp/inspection.txt
RUN cat inspection.txt
COPY inspect_flow2.py /tmp/inspect_flow2.py
RUN python3 /tmp/inspect_flow2.py && cat inspection2.txt
COPY breeder-flow-fix.py /tmp/breeder-flow-fix.py
RUN python3 /tmp/breeder-flow-fix.py
COPY mypage-state-fix.py /tmp/mypage-state-fix.py
RUN python3 /tmp/mypage-state-fix.py
RUN python3 - <<'PY'
from pathlib import Path
p=Path('mypage.html')
if p.exists():
 s=p.read_text(encoding='utf-8',errors='replace')
 s=s.replace('掲載審査のお申し込みにはメール認証が必要です。','お問い合わせ・見学のお申し込みにはメール認証が必要です。')
 p.write_text(s,encoding='utf-8')
PY
RUN python3 - <<'PY'
from pathlib import Path
p=Path('mypage.html'); s=p.read_text(encoding='utf-8',errors='replace')
print('MYPAGEFAVSCRIPT|', 'mypage-favorites-sync.js' in s)
for i,line in enumerate(s.splitlines()):
 if 'お気に入り' in line or '保存中' in line or 'favorite' in line.lower(): print('MYPAGEFAV|%s|%s'%(i+1,line[:1500]))
PY

COPY mypage-verify-state-fix.js ./mypage-verify-state-fix.js
COPY mypage-favorites-sync.js ./mypage-favorites-sync.js
RUN python3 -c "from pathlib import Path; p=Path('operator-breeders.html'); src=Path('operator-admin.html'); p.write_text(src.read_text(encoding='utf-8'),encoding='utf-8') if (not p.exists() and src.exists()) else None"
COPY breeder-proof-fix.py /tmp/breeder-proof-fix.py
RUN python3 /tmp/breeder-proof-fix.py
COPY admin-seed-fix.py /tmp/admin-seed-fix.py
RUN python3 /tmp/admin-seed-fix.py
COPY puppy-editor-fix.py /tmp/puppy-editor-fix.py
RUN python3 /tmp/puppy-editor-fix.py
COPY search-ui-fix.py /tmp/search-ui-fix.py
RUN python3 /tmp/search-ui-fix.py
RUN python3 -c "from pathlib import Path; s=Path('search.html').read_text(encoding='utf-8'); print('SEARCHLAYERS|'+ ' || '.join([x.strip().replace(chr(10),' ') for x in s.split('<') if any(k in x.lower() for k in ['position:fixed','position: fixed','overlay','modal','backdrop','opacity'])][:80]))"
RUN python3 -c "from pathlib import Path; files=[Path('search.html')]+list(Path('assets').glob('*.js'))+list(Path('assets').glob('*.css')); terms=['position:fixed','position: fixed','inset:0','inset: 0','rgba(255','opacity:','backdrop','overlay','modal','loading']; [(print('LAYERJS|'+str(p)+'|'+term+'|'+t[max(0,i-350):i+900].replace(chr(10),' '))) for p in files if p.exists() for t in [p.read_text(encoding='utf-8',errors='ignore')] for term in terms for i in [t.lower().find(term)] if i>=0]"
RUN python3 -c "from pathlib import Path; files=[Path('search.html')]+list(Path('assets').glob('*.js'))+list(Path('assets').glob('*.css')); terms=['result-card','result-grid','filter-card','finder','filter:','visibility:','disabled','aria-disabled','classlist.add','style.opacity']; [(print('CARDSTATE|'+str(p)+'|'+term+'|'+t[max(0,i-500):i+1400].replace(chr(10),' '))) for p in files if p.exists() for t in [p.read_text(encoding='utf-8',errors='ignore')] for term in terms for i in [t.lower().find(term)] if i>=0]"
RUN python3 -c "from pathlib import Path; files=[Path('search.html')]+list(Path('assets').glob('*.css'))+list(Path('assets').glob('*.js')); terms=['#fff8ee','#fff1f7','#fff4f8','#f8e9ef','#f7e4ec','cream','background:linear-gradient','background-color']; [(print('CREAMTRACE|'+str(p)+'|'+term+'|'+t[max(0,i-700):i+1800].replace(chr(10),' '))) for p in files if p.exists() for t in [p.read_text(encoding='utf-8',errors='ignore')] for term in terms for i in [t.lower().find(term.lower())] if i>=0]"
RUN python3 -c "from pathlib import Path; files=[Path('search.html')]+list(Path('assets').glob('*.css'))+list(Path('assets').glob('*.js')); terms=['::before','::after','position:absolute','z-index:','rgba(255,255,255','opacity:0.','opacity: 0.']; [(print('MASKTRACE|'+str(p)+'|'+term+'|'+t[max(0,i-900):i+2200].replace(chr(10),' '))) for p in files if p.exists() for t in [p.read_text(encoding='utf-8',errors='ignore')] for term in terms for i in [t.lower().find(term.lower())] if i>=0]"
COPY final-inspect.py /tmp/final-inspect.py
RUN python3 /tmp/final-inspect.py && cat final-inspection.txt && cat delete-inspection.txt
COPY detail-gallery-fix.py /tmp/detail-gallery-fix.py
RUN python3 /tmp/detail-gallery-fix.py
RUN python3 - <<'PY'
from pathlib import Path
p=Path('puppy-detail.html')
if p.exists():
 s=p.read_text(encoding='utf-8',errors='replace')
 # Force-remove any legacy favorite controls after all build-time patches.
 inject=r'''<style id="bigpaw-force-hide-old-fav">button:not(#bigpawFavButton)[data-action="favorite"],a:not(#bigpawFavButton)[data-action="favorite"],.favorite-btn:not(#bigpawFavButton){display:none!important}</style><script id="bigpaw-force-remove-old-fav">(()=>{function x(){[...document.querySelectorAll('button,a')].forEach(e=>{if(e.id==='bigpawFavButton')return;let t=(e.textContent||'').replace(/\\s/g,'');if(t.includes('お気に入りに保存')||t.includes('お気に入り保存済み'))e.remove()})}document.readyState==='loading'?document.addEventListener('DOMContentLoaded',x):x();new MutationObserver(x).observe(document.documentElement,{childList:true,subtree:true});setInterval(x,1000)})();</script>'''
 if 'bigpaw-force-remove-old-fav' not in s:s=s.replace('</body>',inject+'</body>')
 p.write_text(s,encoding='utf-8')
PY
RUN python3 - <<'PY'
from pathlib import Path
for fn in ['index.html','home.html']:
 p=Path(fn)
 if not p.exists(): continue
 s=p.read_text(encoding='utf-8',errors='replace')
 inject=r'''<script id="bigpaw-remove-sample-new-puppies">(()=>{function x(){[...document.querySelectorAll('h1,h2,h3,h4')].forEach(h=>{let t=(h.textContent||'').replace(/\\s/g,'');if(t.includes('新着の子犬')){let sec=h.closest('section');if(sec)sec.remove();else{let p=h.parentElement;if(p)p.remove()}}})}document.readyState==='loading'?document.addEventListener('DOMContentLoaded',x):x();new MutationObserver(x).observe(document.documentElement,{childList:true,subtree:true})})();</script>'''
 if 'bigpaw-remove-sample-new-puppies' not in s:s=s.replace('</body>',inject+'</body>')
 p.write_text(s,encoding='utf-8')
PY
RUN python3 - <<'PY'
from pathlib import Path
for fn in ['breed-guide.html','assets/breed-data.js','assets/breed-picker-v6.js']:
 p=Path(fn)
 if p.exists():
  print('BREEDGUIDEFILE|'+fn)
  print(p.read_text(encoding='utf-8',errors='replace')[:50000])
PY

COPY breed-guide-detail.js ./breed-guide-detail.js
COPY breed-guide-build.py /tmp/breed-guide-build.py
RUN python3 /tmp/breed-guide-build.py

COPY hide-registration-proof.py /tmp/hide-registration-proof.py
RUN python3 /tmp/hide-registration-proof.py

COPY inspect-breeder-admin.py /tmp/inspect-breeder-admin.py
RUN python3 /tmp/inspect-breeder-admin.py

COPY operator-breeder-management.py /tmp/operator-breeder-management.py
RUN python3 /tmp/operator-breeder-management.py

COPY operator-breeder-management-v2.py /tmp/operator-breeder-management-v2.py
RUN python3 /tmp/operator-breeder-management-v2.py

COPY privacy-breeder-public-name.py /tmp/privacy-breeder-public-name.py
RUN python3 /tmp/privacy-breeder-public-name.py

COPY public-contact-privacy.py /tmp/public-contact-privacy.py
RUN python3 /tmp/public-contact-privacy.py

COPY inspect-public-breeder-api.py /tmp/inspect-public-breeder-api.py
RUN python3 /tmp/inspect-public-breeder-api.py

COPY public-breeder-api-privacy.py /tmp/public-breeder-api-privacy.py
RUN python3 /tmp/public-breeder-api-privacy.py

COPY inspect-breeder-register-privacy.py /tmp/inspect-breeder-register-privacy.py
RUN python3 /tmp/inspect-breeder-register-privacy.py

COPY breeder-register-privacy-ui.py /tmp/breeder-register-privacy-ui.py
RUN python3 /tmp/breeder-register-privacy-ui.py

COPY inspect-operator-management-v3.py /tmp/inspect-operator-management-v3.py
RUN python3 /tmp/inspect-operator-management-v3.py

COPY operator-breeder-management-v3.py /tmp/operator-breeder-management-v3.py
RUN python3 /tmp/operator-breeder-management-v3.py

COPY inspect-public-puppy-api.py /tmp/inspect-public-puppy-api.py
RUN python3 /tmp/inspect-public-puppy-api.py

COPY inspect-public-puppy-routes.py /tmp/inspect-public-puppy-routes.py
RUN python3 /tmp/inspect-public-puppy-routes.py

COPY public-puppy-api-privacy.py /tmp/public-puppy-api-privacy.py
RUN python3 /tmp/public-puppy-api-privacy.py

COPY inspect-breeder-profile-input.py /tmp/inspect-breeder-profile-input.py
RUN python3 /tmp/inspect-breeder-profile-input.py

COPY breeder-public-profile-validation.py /tmp/breeder-public-profile-validation.py
RUN python3 /tmp/breeder-public-profile-validation.py

COPY inspect-inquiry-message-privacy.py /tmp/inspect-inquiry-message-privacy.py
RUN python3 /tmp/inspect-inquiry-message-privacy.py

COPY inspect-online-visit.py /tmp/inspect-online-visit.py
RUN python3 /tmp/inspect-online-visit.py

RUN python3 - <<'PY'
from pathlib import Path
r=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
p=r/'messages.html'
s=p.read_text(encoding='utf-8')
s=s.replace('商談・お迎え管理</a>','商談・お迎え管理</a><a id="onlineVisit" class="btn btn-main btn-wide" style="margin-top:10px" href="online-visit.html">📹 オンライン見学</a>')
s=s.replace("dealLink.href='deal.html?inquiry='+encodeURIComponent(id);","dealLink.href='deal.html?inquiry='+encodeURIComponent(id);onlineVisit.href='online-visit.html?inquiry='+encodeURIComponent(id);")
p.write_text(s,encoding='utf-8')
v=r/'online-visit.html'
v.write_text('''<!doctype html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow"><title>オンライン見学｜BIG PAW</title><link rel="stylesheet" href="assets/style.css"></head><body><div class="topbar">🐾 BIG PAW オンライン見学</div><header class="site-header"><div class="wrap nav"><a class="logo" href="index.html">🐾 BIG PAW</a><a class="btn btn-sub" href="messages.html">戻る</a></div></header><main class="wrap"><section class="section"><div class="card pad"><h1>オンライン見学</h1><p>購入希望者からブリーダーへオンライン見学を申し込み、日時確定後にこの画面から参加します。</p><div class="notice">電話番号・LINE・メールを交換せず、BIG PAW内で見学できる仕組みを準備しています。</div><button class="btn btn-main btn-wide" disabled>ビデオ通話（準備中）</button></div></section></main></body></html>''',encoding='utf-8')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
anchor="        m=re.fullmatch(r'/api/inquiries/([^/]+)/visit',path)\n        if m:"
block="""        m=re.fullmatch(r'/api/inquiries/([^/]+)/video-room',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            import hashlib
            room='BIGPAW-'+hashlib.sha256((m.group(1)+'|online-visit').encode()).hexdigest()[:32]
            con.close(); return self.send_json({'room':room,'inquiryId':m.group(1),'role':u['role']})
"""
if "'/api/inquiries/([^/]+)/video-room'" not in s:s=s.replace(anchor,block+anchor,1)
p.write_text(s,encoding='utf-8')
PY
RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/online-visit.html')
s=p.read_text(encoding='utf-8')
s=s.replace('<button class="btn btn-main btn-wide" disabled>ビデオ通話（準備中）</button>','<button id="joinBtn" class="btn btn-main btn-wide" onclick="joinRoom()">カメラを準備して入室</button><div id="room" style="display:none;height:68vh;min-height:480px;margin-top:12px;border-radius:18px;overflow:hidden;background:#111"></div>')
s=s.replace('</body>','<script src="assets/api.js"></script><script src="https://meet.jit.si/external_api.js"></script><script>async function joinRoom(){try{const q=new URLSearchParams(location.search).get("inquiry");if(!q)throw Error("問い合わせを選択してください");const r=await fetch("/api/inquiries/"+encodeURIComponent(q)+"/video-room",{credentials:"same-origin"});if(!r.ok)throw Error("このオンライン見学には参加できません");const v=await r.json();joinBtn.style.display="none";room.style.display="block";new JitsiMeetExternalAPI("meet.jit.si",{roomName:v.room,parentNode:room,width:"100%",height:"100%",configOverwrite:{prejoinPageEnabled:true},interfaceConfigOverwrite:{MOBILE_APP_PROMO:false}})}catch(e){alert(e.message||"接続できませんでした")}}</script></body>')
p.write_text(s,encoding='utf-8')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/online-visit.html')
s=p.read_text(encoding='utf-8')
old='new JitsiMeetExternalAPI("meet.jit.si",{roomName:v.room,parentNode:room,width:"100%",height:"100%",configOverwrite:{prejoinPageEnabled:true},interfaceConfigOverwrite:{MOBILE_APP_PROMO:false}})'
new='''const api=new JitsiMeetExternalAPI("meet.jit.si",{roomName:v.room,parentNode:room,width:"100%",height:"100%",configOverwrite:{prejoinPageEnabled:true,startWithAudioMuted:false,startWithVideoMuted:false},interfaceConfigOverwrite:{MOBILE_APP_PROMO:false}});api.addListener("videoConferenceJoined",()=>{console.log("BIGPAW_VIDEO_JOINED")});api.addListener("cameraError",e=>{alert("カメラを利用できません。ブラウザのカメラ許可を確認してください。")});api.addListener("micError",e=>{alert("マイクを利用できません。ブラウザのマイク許可を確認してください。")});api.addListener("readyToClose",()=>{location.href="messages.html?inquiry="+encodeURIComponent(q)})'''
if old in s:s=s.replace(old,new)
p.write_text(s,encoding='utf-8')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/online-visit.html')
s=p.read_text(encoding='utf-8')
if 'オンライン見学を申し込む' not in s:
    s=s.replace('<button id="joinBtn"', '<div style="margin:18px 0;padding:16px;border:1px solid #ddd;border-radius:14px"><h2>オンライン見学の日時</h2><p>購入希望者から希望日時を送り、ブリーダーが確認して確定します。</p><label>希望日 <input id="videoDate" type="date"></label> <label>希望時間 <input id="videoTime" type="time"></label><button type="button" onclick="requestOnlineVisit()">オンライン見学を申し込む</button><p id="videoStatus"></p></div><button id="joinBtn"',1)
    js='async function requestOnlineVisit(){const q=new URLSearchParams(location.search).get("inquiry"),d=document.getElementById("videoDate").value,t=document.getElementById("videoTime").value;if(!q||!d||!t){alert("希望日と時間を選んでください");return}const r=await fetch("/api/inquiries/"+encodeURIComponent(q)+"/visit",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({date:d,time:t,transport:"オンライン見学",status:"proposed",faceToFaceConfirmed:false})});document.getElementById("videoStatus").textContent=r.ok?"オンライン見学を申し込みました。ブリーダーの確認をお待ちください。":"申し込みを送信できませんでした。"}'
    s=s.replace('async function joinRoom()',js+'\\nasync function joinRoom()',1)
p.write_text(s,encoding='utf-8')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/online-visit.html')
s=p.read_text(encoding='utf-8')
if 'confirmOnlineVisit' not in s:
    s=s.replace('<p id="videoStatus"></p>', '<p id="videoStatus"></p><button id="confirmVideoBtn" type="button" onclick="confirmOnlineVisit()" style="display:none">この日時で承認する</button>',1)
    js='''async function loadOnlineVisit(){const q=new URLSearchParams(location.search).get("inquiry");if(!q)return;const r=await fetch("/api/inquiries/"+encodeURIComponent(q)+"/visit",{credentials:"same-origin"});if(!r.ok)return;const v=await r.json();if(!v||!v.id)return;const st=document.getElementById("videoStatus");if(v.transport==="オンライン見学"){document.getElementById("videoDate").value=v.visit_date||"";document.getElementById("videoTime").value=v.visit_time||"";st.textContent=v.status==="confirmed"?"オンライン見学は確定しています。":"オンライン見学の希望日時が届いています。";if(v.status!=="confirmed")document.getElementById("confirmVideoBtn").style.display="inline-block";else document.getElementById("joinBtn").style.display="inline-block";}} async function confirmOnlineVisit(){const q=new URLSearchParams(location.search).get("inquiry"),d=document.getElementById("videoDate").value,t=document.getElementById("videoTime").value;const r=await fetch("/api/inquiries/"+encodeURIComponent(q)+"/visit",{method:"POST",credentials:"same-origin",headers:{"Content-Type":"application/json"},body:JSON.stringify({date:d,time:t,transport:"オンライン見学",status:"confirmed",faceToFaceConfirmed:false})});if(r.ok){document.getElementById("videoStatus").textContent="オンライン見学を確定しました。";document.getElementById("confirmVideoBtn").style.display="none";document.getElementById("joinBtn").style.display="inline-block"}else alert("承認できませんでした")};window.addEventListener("DOMContentLoaded",loadOnlineVisit);'''
    s=s.replace('async function requestOnlineVisit()',js+'\\nasync function requestOnlineVisit()',1)
p.write_text(s,encoding='utf-8')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
old="""m=re.fullmatch(r'/api/inquiries/([^/]+)/visit',path)\n        if m:\n            u=self.require()"""
new="""m=re.fullmatch(r'/api/inquiries/([^/]+)/visit',path)\n        if m:\n            u=self.require()"""
# Harden POST visit: only breeder/operator may confirm; buyer may only propose.
needle="body=self.json_body(); con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)"
guard="body=self.json_body(); con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)\n            if body.get('status') == 'confirmed' and u.get('role') not in ('breeder','operator'):\n                con.close(); return self.send_json({'error':'breeder_only_confirmation'},403)"
if needle in s and 'breeder_only_confirmation' not in s:
    # target the visit POST occurrence nearest the route by replacing last occurrence
    pos=s.rfind(needle)
    if pos>=0:s=s[:pos]+s[pos:].replace(needle,guard,1)
p.write_text(s,encoding='utf-8')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
needle="import hashlib\n    room='BIGPAW-'"
guard="""vr=con.execute(\"SELECT status,transport FROM visits WHERE inquiry_id=?\",(m.group(1),)).fetchone()\n    if not vr or vr['status'] != 'confirmed' or vr['transport'] != 'オンライン見学':\n        con.close(); return self.send_json({'error':'online_visit_not_confirmed'},403)\n    import hashlib\n    room='BIGPAW-'"""
if needle in s and 'online_visit_not_confirmed' not in s:s=s.replace(needle,guard,1)
p.write_text(s,encoding='utf-8')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
needle="if not vr or vr['status'] != 'confirmed' or vr['transport'] != 'オンライン見学':\n        con.close(); return self.send_json({'error':'online_visit_not_confirmed'},403)"
guard="""if not vr or vr['status'] != 'confirmed' or vr['transport'] != 'オンライン見学':\n        con.close(); return self.send_json({'error':'online_visit_not_confirmed'},403)\n    # Room opens 30 minutes before and closes 2 hours after the scheduled JST time.\n    from datetime import datetime, timedelta, timezone\n    full=con.execute(\"SELECT visit_date,visit_time FROM visits WHERE inquiry_id=?\",(m.group(1),)).fetchone()\n    try:\n        scheduled=datetime.strptime((full['visit_date'] or '')+' '+(full['visit_time'] or ''),'%Y-%m-%d %H:%M').replace(tzinfo=timezone(timedelta(hours=9)))\n        current=datetime.now(timezone(timedelta(hours=9)))\n        if current < scheduled-timedelta(minutes=30) or current > scheduled+timedelta(hours=2):\n            con.close(); return self.send_json({'error':'outside_online_visit_window'},403)\n    except Exception:\n        con.close(); return self.send_json({'error':'invalid_online_visit_time'},403)"""
if needle in s and 'outside_online_visit_window' not in s:s=s.replace(needle,guard,1)
p.write_text(s,encoding='utf-8')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
for term in ['/api/breeder-profile','/api/favorites','breeder_name','breeder-applications','def inquiry_for_user']:
 print('\\n=== SECURITY INSPECT',term,'===')
 start=0
 while True:
  i=s.find(term,start)
  if i<0: break
  print(s[max(0,i-900):i+1800])
  start=i+len(term)
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
# Buyers must never receive or edit internal breeder records.
old="""if path=='/api/breeder-profile':
            u=self.require(['buyer','breeder','operator']);"""
new="""if path=='/api/breeder-profile':
            u=self.require(['breeder','operator']);"""
s=s.replace(old,new)
s=s.replace("return self.send_json([puppy_json(r) for r in rows])\\n        if path=='/api/inquiries':", "return self.send_json([public_puppy_json(r) for r in rows])\\n        if path=='/api/inquiries':",1)
needle="rows=con.execute('SELECT i.*,p.name puppy_name,p.breeder_name,p.price puppy_price FROM inquiries i JOIN puppies p ON p.id=i.puppy_id WHERE buyer_id=? ORDER BY i.created_at DESC',(u['id'],)).fetchall()"
replacement=needle + chr(10) + "                rows=[dict(r) for r in rows]" + chr(10) + "                for r in rows: r['breeder_name']='BIGPAW認定ブリーダー'"
s=s.replace(needle,replacement)
p.write_text(s,encoding='utf-8')
import py_compile
py_compile.compile(str(p), doraise=True)
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
print('=== SECURITY ROUTE INSPECTION ===')
for term in ["INSERT INTO messages","INSERT INTO inquiries","/api/breeder-applications/","/api/breeder/puppies","/api/parent-dogs","/api/health-records"]:
    print('---',term,'---')
    start=0
    while True:
        i=s.find(term,start)
        if i<0: break
        print(s[max(0,i-1400):i+2200])
        start=i+len(term)
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
# Critical: breeder application review must require an authenticated operator and normal origin validation.
s=s.replace("if not re.fullmatch(r'/api/breeder-applications/[^/]+',path) and not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)", "if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)")
s=s.replace("m=re.fullmatch(r'/api/breeder-applications/([^/]+)',path)" + chr(10) + "        if m:" + chr(10) + "            u={'role':'operator'}", "m=re.fullmatch(r'/api/breeder-applications/([^/]+)',path)" + chr(10) + "        if m:" + chr(10) + "            u=self.require(['operator'])" + chr(10) + "            if not u:return")
# Internal breeder-management endpoints are not buyer APIs.
s=s.replace("if path=='/api/breeder/puppies':\\n            u=self.require(['buyer','breeder','operator']);", "if path=='/api/breeder/puppies':\\n            u=self.require(['breeder','operator']);")
s=s.replace("if path=='/api/parent-dogs':\\n            u=self.require(['buyer','breeder','operator']);", "if path=='/api/parent-dogs':\\n            u=self.require(['breeder','operator']);")
s=s.replace("if path=='/api/health-records':\\n            u=self.require(['buyer','breeder','operator']);", "if path=='/api/health-records':\\n            u=self.require(['breeder','operator']);")
p.write_text(s,encoding='utf-8')
# Mandatory pre-production checks for every code change.
assert "u={'role':'operator'}" not in s[s.find("m=re.fullmatch(r'/api/breeder-applications/"):s.find("m=re.fullmatch(r'/api/breeder-applications/")+500]
assert "u=self.require(['operator'])" in s[s.find("m=re.fullmatch(r'/api/breeder-applications/"):s.find("m=re.fullmatch(r'/api/breeder-applications/")+500]
import py_compile
py_compile.compile(str(p), doraise=True)
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
print('=== CONTACT PRIVACY TARGETS ===')
for term in ["INSERT INTO messages","INSERT INTO inquiries"]:
    start=0
    while True:
        i=s.find(term,start)
        if i<0: break
        print('---',term,'---')
        print(s[max(0,i-2200):i+1800])
        start=i+len(term)
import py_compile
py_compile.compile(str(p), doraise=True)
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
# Block direct contact details in buyer/breeder inquiry messages and initial inquiry text.
msg_anchor="            if len(text)>2000: return self.send_json({'error':'message_too_long'},400)"
msg_new=msg_anchor + chr(10) + "            if u.get('role')!='operator' and public_profile_has_direct_contact(text): return self.send_json({'error':'direct_contact_not_allowed','message':'電話番号・メール・LINE・SNS・外部URLなどの直接連絡先は送信できません。BIGPAW内のメッセージをご利用ください。'},400)"
assert s.count(msg_anchor)==1, s.count(msg_anchor)
s=s.replace(msg_anchor,msg_new,1)
inq_anchor="            body=self.json_body(); puppy_id=str(body.get('puppyId','')); con=db(); p=con.execute"
inq_new="            body=self.json_body(); puppy_id=str(body.get('puppyId','')); inquiry_message=str(body.get('message','')).strip()" + chr(10) + "            if public_profile_has_direct_contact(inquiry_message): return self.send_json({'error':'direct_contact_not_allowed','message':'問い合わせ本文に電話番号・メール・LINE・SNS・外部URLなどの直接連絡先は記載できません。'},400)" + chr(10) + "            con=db(); p=con.execute"
assert s.count(inq_anchor)==1, s.count(inq_anchor)
s=s.replace(inq_anchor,inq_new,1)
p.write_text(s,encoding='utf-8')
assert "direct_contact_not_allowed" in s
import py_compile
py_compile.compile(str(p), doraise=True)
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
print('=== FAVORITES + UPLOAD PRIVACY INSPECTION ===')
for term in ["if path=='/api/favorites'", "'/uploads/", 'uploads/', 'registration_proof']:
    print('---',term,'---')
    start=0; hits=0
    while True:
        i=s.find(term,start)
        if i<0: break
        print(s[max(0,i-1300):i+2200]); hits+=1; start=i+len(term)
    print('hits=',hits)
import py_compile
py_compile.compile(str(p), doraise=True)
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
# Favorites must use the already-sanitized public puppy serializer.
fav_old="return self.send_json([puppy_json(r) for r in rows])" + chr(10) + "        if path=='/api/inquiries':"
fav_new="return self.send_json([public_puppy_json(r) for r in rows])" + chr(10) + "        if path=='/api/inquiries':"
if fav_old in s:
    assert s.count(fav_old)==1, s.count(fav_old)
    s=s.replace(fav_old,fav_new,1)
else:
    assert fav_new in s, 'favorites serializer anchor missing'
p.write_text(s,encoding='utf-8')
assert fav_new in s
import py_compile
py_compile.compile(str(p), doraise=True)
print('FAVORITES_PRIVACY_CHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
print('=== INQUIRY + BILLING PRIVACY INSPECTION ===')
for term in ["if path=='/api/inquiries'", "if path=='/api/breeder/billing-config'", "body.get('phone'", "body.get('email'"]:
    print('---',term,'---')
    start=0; hits=0
    while True:
        i=s.find(term,start)
        if i<0: break
        print(s[max(0,i-1600):i+3000]); hits+=1; start=i+len(term)
    print('hits=',hits)
import py_compile
py_compile.compile(str(p), doraise=True)
print('INQUIRY_BILLING_INSPECTION_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
# Buyers must not read internal health records; only breeders/operators manage them.
health_old="if path=='/api/health-records':" + chr(10) + "            u=self.require(['buyer','breeder','operator']);"
health_new="if path=='/api/health-records':" + chr(10) + "            u=self.require(['breeder','operator']);"
assert s.count(health_old)>=1, s.count(health_old)
s=s.replace(health_old,health_new)
# Billing config contains operator bank/account data and is for breeder billing only.
bill_old="if path=='/api/breeder/billing-config':" + chr(10) + "            u=self.require(['buyer','breeder','operator'])"
bill_new="if path=='/api/breeder/billing-config':" + chr(10) + "            u=self.require(['breeder','operator'])"
assert s.count(bill_old)==1, s.count(bill_old)
s=s.replace(bill_old,bill_new,1)
# Breeder-facing inquiry list must not expose buyer email/phone; operator retains full data.
breeder_anchor="            out=[dict(r) for r in rows]; con.close(); return self.send_json(out)"
assert s.count(breeder_anchor)==1, s.count(breeder_anchor)
breeder_new="            out=[dict(r) for r in rows]" + chr(10) + "            if u['role']=='breeder':" + chr(10) + "                for r in out: r['email']=''; r['phone']=''" + chr(10) + "            con.close(); return self.send_json(out)"
s=s.replace(breeder_anchor,breeder_new,1)
p.write_text(s,encoding='utf-8')
assert health_new in s
assert bill_new in s
assert "for r in out: r['email']=''; r['phone']=''" in s
import py_compile
py_compile.compile(str(p), doraise=True)
print('INQUIRY_HEALTH_BILLING_PRIVACY_CHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
print('=== MUTATION AUTHORIZATION INSPECTION ===')
for term in ["def do_POST", "def do_PATCH", "def do_DELETE", "self.require(['buyer','breeder','operator'])", "if path=='/api/uploads'", "if path=='/api/parent-dogs'", "if path=='/api/breeder/puppies'"]:
    print('---',term,'---')
    start=0; hits=0
    while True:
        i=s.find(term,start)
        if i<0: break
        print(s[max(0,i-1200):i+3200]); hits+=1; start=i+len(term)
    print('hits=',hits)
import py_compile
py_compile.compile(str(p), doraise=True)
print('MUTATION_AUTH_INSPECTION_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
# Internal breeder puppy and parent-dog collections are never buyer-readable.
for route in ['/api/breeder/puppies','/api/parent-dogs']:
    old="if path=='"+route+"':" + chr(10) + "            u=self.require(['buyer','breeder','operator']);"
    new="if path=='"+route+"':" + chr(10) + "            u=self.require(['breeder','operator']);"
    assert s.count(old)>=1, (route,s.count(old))
    s=s.replace(old,new)
# Generic upload endpoint: buyer may upload only when explicitly bound to their own inquiry flow later; current breeder-proof/puppy upload is internal.
upload_old="if path=='/api/uploads':" + chr(10) + "            u=self.require(['buyer','breeder','operator']);"
upload_new="if path=='/api/uploads':" + chr(10) + "            u=self.require(['breeder','operator']);"
assert s.count(upload_old)==1, s.count(upload_old)
s=s.replace(upload_old,upload_new,1)
p.write_text(s,encoding='utf-8')
for route in ['/api/breeder/puppies','/api/parent-dogs']:
    assert ("if path=='"+route+"':" + chr(10) + "            u=self.require(['breeder','operator']);") in s
assert upload_new in s
import py_compile
py_compile.compile(str(p), doraise=True)
print('INTERNAL_MUTATION_AUTH_CHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
print('=== UPLOAD PROOF PRIVACY INSPECTION ===')
for term in ["if path=='/api/uploads'", "UPLOADS", "registrationProofUrl", "[REGISTRATION_PROOF]", "'/uploads/'", '"/uploads/']:
    print('---',term,'---')
    start=0; hits=0
    while True:
        i=s.find(term,start)
        if i<0: break
        print(s[max(0,i-1800):i+4200]); hits+=1; start=i+len(term)
    print('hits=',hits)
import py_compile
py_compile.compile(str(p), doraise=True)
print('UPLOAD_PROOF_PRIVACY_INSPECTION_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
print('=== PROOF STATIC ROUTE TARGETED INSPECTION ===')
for term in ["startswith('/uploads/')", "path.startswith('/uploads/')", "UPLOADS /", "registrationProofUrl"]:
    print('---',term,'---')
    start=0
    while True:
        i=s.find(term,start)
        if i<0: break
        print(s[max(0,i-900):i+2200]); start=i+len(term)
import py_compile; py_compile.compile(str(p),doraise=True)
print('PROOF_STATIC_ROUTE_INSPECTION_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
x="u=self.require(['breeder','operator']);"+chr(10)+"            if not u:return"+chr(10)+"            ctype=self.headers.get('Content-Type','')"
assert x in s
s=s.replace(x,"u=self.require(['buyer','breeder','operator']);"+chr(10)+"            if not u:return"+chr(10)+"            ctype=self.headers.get('Content-Type','')",1)
x="if file_part is None: return self.send_json({'error':'file_required'},400)"+chr(10)+"            raw=file_part.get_payload(decode=True) or b''"
assert x in s
s=s.replace(x,"if file_part is None: return self.send_json({'error':'file_required'},400)"+chr(10)+"            if u['role']=='buyer' and puppy_id!='breeder-proof': return self.send_json({'error':'forbidden'},403)"+chr(10)+"            raw=file_part.get_payload(decode=True) or b''",1)
p.write_text(s,encoding='utf-8')
import py_compile; py_compile.compile(str(p),doraise=True)
assert "u['role']=='buyer' and puppy_id!='breeder-proof'" in p.read_text(encoding='utf-8')
print('BREEDER_PROOF_UPLOAD_FLOW_CHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
x="if clean.startswith('/uploads/'):"+chr(10)+"            name=Path(clean).name"+chr(10)+"            return str(UPLOADS / name)"
assert x in s, 'public uploads route anchor missing'
y="if clean.startswith('/uploads/'):"+chr(10)+"            name=Path(clean).name"+chr(10)+"            con=db(); hidden=con.execute('SELECT 1 FROM uploads WHERE stored_name=? AND puppy_id IS NULL LIMIT 1',(name,)).fetchone(); con.close()"+chr(10)+"            if hidden: return str(ROOT / '__not_public__')"+chr(10)+"            return str(UPLOADS / name)"
s=s.replace(x,y,1)
p.write_text(s,encoding='utf-8')
import py_compile; py_compile.compile(str(p),doraise=True)
q=p.read_text(encoding='utf-8')
assert "hidden=con.execute('SELECT 1 FROM uploads WHERE stored_name=? AND puppy_id IS NULL LIMIT 1'" in q
assert "__not_public__" in q
print('PRIVATE_PROOF_STATIC_CHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
print('=== OPERATOR PROOF REVIEW INSPECTION ===')
for term in ["breeder-applications", "registration_proof", "REGISTRATION_PROOF", "profile"]:
    print('---',term,'---')
    start=0; hits=0
    while True:
        i=s.find(term,start)
        if i<0: break
        print(s[max(0,i-1000):i+2600]); hits+=1; start=i+len(term)
    print('hits=',hits)
import py_compile; py_compile.compile(str(p),doraise=True)
print('OPERATOR_PROOF_REVIEW_INSPECTION_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
p=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package/backend/server.py')
s=p.read_text(encoding='utf-8')
anchor="        if path=='/api/operator/listings':"
assert anchor in s, 'operator route anchor missing'
route="""        m=re.fullmatch(r'/api/operator/breeder-proof/([^/]+)',path)
        if m:
            u=self.require(['operator'])
            if not u:return
            con=db(); row=con.execute('SELECT stored_name,mime FROM uploads WHERE id=? AND puppy_id IS NULL',(m.group(1),)).fetchone(); con.close()
            if not row:return self.send_json({'error':'not_found'},404)
            fp=UPLOADS / row['stored_name']
            if not fp.exists():return self.send_json({'error':'not_found'},404)
            raw=fp.read_bytes(); self.send_response(200); self.send_header('Content-Type',row['mime'] or 'application/octet-stream'); self.send_header('Content-Length',str(len(raw))); self.send_header('Cache-Control','private, no-store'); self.end_headers(); self.wfile.write(raw); return
"""
s=s.replace(anchor,route+anchor,1)
p.write_text(s,encoding='utf-8')
import py_compile; py_compile.compile(str(p),doraise=True)
q=p.read_text(encoding='utf-8')
assert "'/api/operator/breeder-proof/([^/]+)'" in q
assert "self.require(['operator'])" in q
assert "Cache-Control','private, no-store'" in q
print('OPERATOR_PRIVATE_PROOF_ROUTE_CHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
print('=== OPERATOR APPLICATION UI INSPECTION ===')
for p in root.rglob('*'):
    if not p.is_file() or p.suffix.lower() not in ('.html','.js'): continue
    try: t=p.read_text(encoding='utf-8')
    except: continue
    if '/api/breeder-applications' in t or 'REGISTRATION_PROOF' in t or '掲載審査' in t:
        print('FILE',p.relative_to(root))
        for term in ['/api/breeder-applications','REGISTRATION_PROOF','掲載審査']:
            i=t.find(term)
            if i>=0: print(t[max(0,i-1400):i+3200])
import py_compile; py_compile.compile(str(root/'backend/server.py'),doraise=True)
print('OPERATOR_APPLICATION_UI_INSPECTION_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
for name in ['operator-admin.html','operator-breeders.html','operator-breeder-applications.html']:
 p=root/name
 if p.exists():
  t=p.read_text(encoding='utf-8')
  print('TARGET',name,'LEN',len(t),'apps',t.count('breeder-applications'),'proof',t.count('REGISTRATION_PROOF'))
import py_compile; py_compile.compile(str(root/'backend/server.py'),doraise=True)
print('OPERATOR_PROOF_UI_TARGET_CHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
p=root/'operator-breeders.html'; t=p.read_text(encoding='utf-8')
print('=== OPERATOR BREEDERS PROOF CONTEXT ===')
for term in ['REGISTRATION_PROOF','breeder-applications']:
 start=0
 while True:
  i=t.find(term,start)
  if i<0: break
  print(t[max(0,i-1200):i+2600]); start=i+len(term)
import py_compile; py_compile.compile(str(root/'backend/server.py'),doraise=True)
print('OPERATOR_BREEDERS_PROOF_CONTEXT_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
p=root/'backend/server.py'; t=p.read_text(encoding='utf-8')
print('=== BUYER REGISTER ORIGIN INSPECTION ===')
for term in ['invalid_origin','Invalid Origin','invalid origin','/api/register','register','Origin','allowed_origin','mutation_origin']:
 print('TERM',term)
 start=0; n=0
 while n<8:
  i=t.find(term,start)
  if i<0: break
  print(t[max(0,i-1100):i+2300]); start=i+len(term); n+=1
for q in root.rglob('*register*'):
 if q.is_file() and q.suffix.lower() in ('.html','.js'):
  try: x=q.read_text(encoding='utf-8')
  except: continue
  print('REGISTER_FILE',q.relative_to(root)); print(x[:10000])
import py_compile; py_compile.compile(str(p),doraise=True)
print('BUYER_REGISTER_ORIGIN_INSPECTION_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
p=root/'backend/server.py'; t=p.read_text(encoding='utf-8')
i=t.find('def mutation_origin_allowed')
assert i>=0, 'mutation_origin_allowed missing'
print(t[i:i+5000])
for q in [root/'register.html',root/'assets/api.js']:
 if q.exists():
  x=q.read_text(encoding='utf-8'); print('FILE',q.name); print(x[:12000])
import py_compile; py_compile.compile(str(p),doraise=True)
print('ORIGIN_FUNCTION_EXACT_CHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package'); p=root/'backend/server.py'
t=p.read_text(encoding='utf-8')
old="allowed={PUBLIC_BASE_URL.rstrip('/'),'https://www.bigpaw.site','https://bigpaw.site'}\n        return origin.rstrip('/') in allowed"
new="allowed={PUBLIC_BASE_URL.rstrip('/'),'https://www.bigpaw.site','https://bigpaw.site'}\n        try:\n            o=urlparse(origin)\n            host=(o.hostname or '').lower().rstrip('.')\n            return o.scheme=='https' and (host=='bigpaw.site' or host.endswith('.bigpaw.site')) and (o.port in (None,443))\n        except Exception:\n            return False"
assert old in t, 'origin validation anchor missing'
t=t.replace(old,new,1); p.write_text(t,encoding='utf-8')
import py_compile; py_compile.compile(str(p),doraise=True)
x=p.read_text(encoding='utf-8')
assert "host=='bigpaw.site' or host.endswith('.bigpaw.site')" in x
assert "o.scheme=='https'" in x and "o.port in (None,443)" in x
assert "if not origin: return True" in x
print('BUYER_REGISTRATION_ORIGIN_FIX_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package'); p=root/'backend/server.py'; t=p.read_text(encoding='utf-8')
print('=== PROOF ROUTE AND OPERATOR UI FINAL PRECHECK ===')
for term in ["/api/operator/breeder-proof/", "if path=='/api/breeder-applications':"]:
 i=t.find(term); assert i>=0, term+' missing'; print(t[max(0,i-1400):i+4200])
q=root/'operator-breeders.html'; assert q.exists(); x=q.read_text(encoding='utf-8')
for term in ['REGISTRATION_PROOF','breeder-applications']:
 i=x.find(term); assert i>=0, term+' UI missing'; print(x[max(0,i-1800):i+4500])
import py_compile; py_compile.compile(str(p),doraise=True)
print('PROOF_FINAL_PRECHECK_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package'); p=root/'backend/server.py'; t=p.read_text(encoding='utf-8')
old="host=='bigpaw.site' or host.endswith('.bigpaw.site')"
new="host=='bigpaw.site' or host.endswith('.bigpaw.site') or host=='bigpaw-site-production.up.railway.app'"
assert old in t, 'registration origin host anchor missing'
t=t.replace(old,new,1); p.write_text(t,encoding='utf-8')
import py_compile; py_compile.compile(str(p),doraise=True)
x=p.read_text(encoding='utf-8'); assert new in x; assert "o.scheme=='https'" in x and "o.port in (None,443)" in x
print('REGISTRATION_LINE_ORIGIN_FIX_OK')
PY

RUN python3 - <<'PY'
from pathlib import Path
import re, py_compile
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
p=root/'backend/server.py'; t=p.read_text(encoding='utf-8')
pat=r"(?ms)^        m=re\.fullmatch\(r'/api/operator/breeder-proof/\(\[\^/\]\+\)',path\).*?(?=^        (?:m=|if path==))"
m=re.search(pat,t); assert m, 'existing proof route missing'
old=m.group(0); assert "SELECT stored_name,mime FROM uploads WHERE id=? AND puppy_id IS NULL" in old, 'unexpected proof route'
new="""        m=re.fullmatch(r'/api/operator/breeder-proof/([^/]+)',path)
        if m:
            u=self.require(['operator']);
            if not u:return
            con=db(); app=con.execute("SELECT id,user_id,profile FROM breeder_applications WHERE id=?",(m.group(1),)).fetchone()
            if not app:
                con.close(); return self.send_json({'error':'not_found'},404)
            mm=re.search(r'\\[REGISTRATION_PROOF\\](/uploads/[^\\s]+)',str(app['profile'] or ''))
            if not mm:
                con.close(); return self.send_json({'error':'proof_not_found'},404)
            stored=Path(urlparse(mm.group(1)).path).name
            up=con.execute("SELECT stored_name,mime FROM uploads WHERE user_id=? AND stored_name=? AND puppy_id IS NULL",(app['user_id'],stored)).fetchone(); con.close()
            if not up or not str(up['mime'] or '').lower().startswith('image/'): return self.send_json({'error':'proof_not_found'},404)
            fp=UPLOADS/up['stored_name']
            if not fp.exists(): return self.send_json({'error':'proof_not_found'},404)
            data=fp.read_bytes(); self.send_response(200); self.send_header('Content-Type',up['mime']); self.send_header('Content-Length',str(len(data))); self.send_header('Cache-Control','private, no-store'); self.send_header('X-Content-Type-Options','nosniff'); self.end_headers(); self.wfile.write(data); return
"""
t=t.replace(old,new,1)
anchor="if path=='/api/breeder-applications':"; i=t.find(anchor); assert i>=0
j=t.find("return self.send_json([dict(r) for r in rows])",i); assert j>=0 and j<i+5000, 'raw application response missing'
raw="return self.send_json([dict(r) for r in rows])"
safe="""out=[]
            for r in rows:
                d=dict(r); prof=str(d.get('profile') or '')
                has=bool(re.search(r'\\[REGISTRATION_PROOF\\]/uploads/[^\\s]+',prof))
                d['profile']=re.sub(r'\\n?\\[REGISTRATION_PROOF\\]/uploads/[^\\s]+','',prof).strip()
                d['has_registration_proof']=has
                d['registration_proof_url']=('/api/operator/breeder-proof/'+str(d['id'])) if has else None
                out.append(d)
            return self.send_json(out)"""
t=t[:j]+safe+t[j+len(raw):]
p.write_text(t,encoding='utf-8'); py_compile.compile(str(p),doraise=True)
x=p.read_text(encoding='utf-8')
assert "SELECT id,user_id,profile FROM breeder_applications WHERE id=?" in x
assert "X-Content-Type-Options','nosniff'" in x
assert 'registration_proof_url' in x
assert "SELECT stored_name,mime FROM uploads WHERE id=? AND puppy_id IS NULL" not in x
q=root/'operator-breeders.html'; s=q.read_text(encoding='utf-8')
# Replace direct profile-marker link expression in the main card.
start=s.find("${String(a.profile||'').match(/\\[REGISTRATION_PROOF")
if start>=0:
    end=s.find("${a.status==='pending'?",start); assert end>start
    repl="${a.registration_proof_url?'<div style=\\\"margin-top:10px\\\"><a class=\\\"btn btn-sub proof-link\\\" target=\\\"_blank\\\" rel=\\\"noopener\\\" href=\\\"'+esc(a.registration_proof_url)+'\\\">第一種動物取扱業 登録証の写しを確認</a></div>':''}"
    s=s[:start]+repl+s[end:]
# Remove three legacy proof-scraping scripts.
for key in ['function add(){document.querySelectorAll', 'function addProofLinks(){', 'function sync(){var rows=window.__bpProofRows']:
    k=s.find(key)
    if k>=0:
        a=s.rfind('<script>',0,k); b=s.find('</script>',k); assert a>=0 and b>=0; s=s[:a]+s[b+9:]
q.write_text(s,encoding='utf-8')
u=q.read_text(encoding='utf-8')
assert 'registration_proof_url' in u
assert '[REGISTRATION_PROOF]' not in u
assert '__bpProofRows' not in u
py_compile.compile(str(p),doraise=True)
print('OPERATOR_PROOF_SECURE_FINAL_OK')
PY


RUN python3 - <<'PY'
from pathlib import Path
import py_compile
root=Path('/app/BIG_PAW_v1.0_FINAL3_domain_ready_package')
p=root/'online-visit.html'; s=p.read_text(encoding='utf-8')
assert 'id="joinBtn"' in s and 'async function joinRoom()' in s, 'online visit UI anchors missing'
old='''async function joinRoom(){try{const q=new URLSearchParams(location.search).get("inquiry");if(!q)throw Error("問い合わせを選択してください");const r=await fetch("/api/inquiries/"+encodeURIComponent(q)+"/video-room",{credentials:"same-origin"});if(!r.ok)throw Error("このオンライン見学には参加できません");const v=await r.json();joinBtn.style.display="none";room.style.display="block";'''
assert old in s, 'joinRoom exact anchor missing'
new='''async function joinRoom(){try{const q=new URLSearchParams(location.search).get("inquiry");if(!q)throw Error("問い合わせを選択してください");const r=await fetch("/api/inquiries/"+encodeURIComponent(q)+"/video-room",{credentials:"same-origin"});if(!r.ok){let e={};try{e=await r.json()}catch(_){ }if(e.error==="online_visit_not_confirmed")throw Error("ブリーダーの日時承認後に入室できます。");if(e.error==="outside_online_visit_window")throw Error("入室できるのは予約時刻の30分前から2時間後までです。");throw Error("このオンライン見学には参加できません");}const v=await r.json();if(typeof JitsiMeetExternalAPI==="undefined")throw Error("ビデオ通話の読み込みに失敗しました。Safariで再読み込みしてください。");joinBtn.style.display="none";room.style.display="block";'''
s=s.replace(old,new,1)
# Make the join button state explicit: hidden until confirmed, then enabled only in the valid window.
s=s.replace('<button id="joinBtn" class="btn btn-main btn-wide" onclick="joinRoom()">','<button id="joinBtn" class="btn btn-main btn-wide" onclick="joinRoom()" style="display:none">',1)
p.write_text(s,encoding='utf-8')
# Backend already gates confirmed status and time window; verify those exact protections still exist.
srv=(root/'backend/server.py').read_text(encoding='utf-8')
assert "online_visit_not_confirmed" in srv
assert "outside_online_visit_window" in srv
assert "scheduled-timedelta(minutes=30)" in srv and "scheduled+timedelta(hours=2)" in srv
py_compile.compile(str(root/'backend/server.py'),doraise=True)
x=p.read_text(encoding='utf-8')
assert 'style="display:none"' in x
assert 'ブリーダーの日時承認後に入室できます。' in x
assert 'JitsiMeetExternalAPI==="undefined"' in x
print('ONLINE_VISIT_MOBILE_ENTRY_FIX_OK')
PY

ENV PORT=8080
EXPOSE 8080
CMD ["python3", "backend/server.py"]