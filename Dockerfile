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

ENV PORT=8080
EXPOSE 8080
CMD ["python3", "backend/server.py"]