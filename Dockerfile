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

ENV PORT=8080
EXPOSE 8080
CMD ["python3", "backend/server.py"]