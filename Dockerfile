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
ENV PORT=8080
EXPOSE 8080
CMD ["python3", "backend/server.py"]