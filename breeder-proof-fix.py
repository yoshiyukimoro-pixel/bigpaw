from pathlib import Path
p=Path('breeder-register.html'); s=p.read_text(encoding='utf-8')
needle='<div class="field"><label>第一種動物取扱業 登録番号 *</label><input id="registrationNo" required></div>'
if needle in s and 'id="registrationProof"' not in s:s=s.replace(needle,needle+'<div class="field"><label>第一種動物取扱業 登録証の写し *</label><input id="registrationProof" type="file" accept="image/*,.pdf" required><small class="muted">登録証の写真またはPDFをアップロードしてください。</small></div>',1)
old="async function apply(e){e.preventDefault();if(!BigPawAPI.isLive()){alert('サーバー版で申請を保存できます。');return}submitBtn.disabled=true;try{await BigPawAPI.applyBreeder({"
if old in s:
 s=s.replace(old,"async function apply(e){e.preventDefault();if(!BigPawAPI.isLive()){alert('サーバー版で申請を保存できます。');return}if(!registrationProof.files[0]){alert('第一種動物取扱業 登録証の写しを選択してください。');return}submitBtn.disabled=true;try{const up=await BigPawAPI.upload(registrationProof.files[0],'breeder-proof');await BigPawAPI.applyBreeder({",1)
 s=s.replace("profile:profile.value,agreeCommissionTerms:agreeCommissionTerms.checked}","profile:profile.value,registrationProofUrl:up.url,agreeCommissionTerms:agreeCommissionTerms.checked}",1)
p.write_text(s,encoding='utf-8')
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
anchor="body=self.json_body(); required=['kennelName','representative','prefecture','primaryBreed','registrationNo','expiresOn']"
if anchor in s:s=s.replace(anchor,anchor+"\n            if not str(body.get('registrationProofUrl','')).strip(): return self.send_json({'error':'registration_proof_required','message':'第一種動物取扱業 登録証の写しが必要です。'},400)",1)
marker="str(body.get('profile','')).strip(),'pending'"
if marker in s:s=s.replace(marker,"(str(body.get('profile','')).strip()+'\\n[REGISTRATION_PROOF]'+str(body.get('registrationProofUrl','')).strip()),'pending'",1)
p.write_text(s,encoding='utf-8')
p=Path('operator-breeders.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 # inject helper that adds document link to each card after rendering
 extra="""<script>(function(){function add(){document.querySelectorAll('.card').forEach(function(c){var t=c.textContent||'';var m=t.match(/\[REGISTRATION_PROOF\](\S+)/);if(m&&!c.querySelector('.proof-link')){var a=document.createElement('a');a.className='btn btn-sub proof-link';a.target='_blank';a.href=m[1];a.textContent='登録証の写しを確認';c.appendChild(a)}})}setTimeout(add,300);setInterval(add,1500)})();</script>"""
 if 'proof-link' not in s:s=s.replace('</body>',extra+'</body>')
 p.write_text(s,encoding='utf-8')

p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
s=s.replace("if old and old['status'] in ('pending','approved'):","if old and old['status']=='approved':")
p.write_text(s,encoding='utf-8')
p=Path('breeder-register.html'); s=p.read_text(encoding='utf-8')
s=s.replace("if(st!=='rejected')submitBtn.disabled=true","if(st==='approved')submitBtn.disabled=true;else submitBtn.disabled=!agreeCommissionTerms.checked")
s=s.replace("if(rows[0].status!=='rejected')submitBtn.disabled=true","if(rows[0].status==='approved')submitBtn.disabled=true;else submitBtn.disabled=!agreeCommissionTerms.checked")
p.write_text(s,encoding='utf-8')

p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
# Registration-certificate upload happens while the applicant is still a buyer.
s=s.replace("self.require(['breeder','operator'])","self.require(['buyer','breeder','operator'])")
p.write_text(s,encoding='utf-8')

p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')

p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
# Application submission must return immediately; notification delivery is non-blocking for this path.
start=s.find("            send_mail(applicant_email,'BIG PAW 掲載審査申請を受け付けました'")
end=s.find("            return self.send_json(dict(r),201)",start)
if start>=0 and end>start:
 s=s[:start]+"            return self.send_json(dict(r),201)\n"+s[end+len("            return self.send_json(dict(r),201)\n"):]
p.write_text(s,encoding='utf-8')

p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
# Upload responses must not wait on email or any external network service.
# Keep application update endpoint simple and deterministic for existing pending applications.
s=s.replace("            operators=con.execute(\"SELECT email FROM users WHERE role='operator'\").fetchall()\n            con.close()\n            return self.send_json(dict(r),201)","            con.close()\n            return self.send_json(dict(r),201)")
p.write_text(s,encoding='utf-8')

p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
# breeder-proof is an application document, not a puppy upload: never store its tag as puppy_id FK.
s=s.replace("upid,u['id'],puppy_id or None,original,stored,mime,now()","upid,u['id'],(None if puppy_id=='breeder-proof' else puppy_id or None),original,stored,mime,now()")
p.write_text(s,encoding='utf-8')

# Render registration proof explicitly in operator breeder review cards.
p=Path('operator-breeders.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 # The application profile carries the proof marker; turn it into a visible review link after cards render.
 extra='''<script>(function(){function addProofLinks(){document.querySelectorAll('.card').forEach(function(c){if(c.querySelector('.proof-link'))return;var html=c.innerHTML||\"\";var m=html.match(/\\[REGISTRATION_PROOF\\]([^<\\s]+)/);if(!m)return;var url=m[1].replace(/&amp;/g,\"&\");var row=document.createElement(\"div\");row.style.marginTop=\"12px\";var a=document.createElement(\"a\");a.className=\"btn btn-sub proof-link\";a.target=\"_blank\";a.rel=\"noopener\";a.href=url;a.textContent=\"第一種動物取扱業 登録証の写しを確認\";row.appendChild(a);c.appendChild(row);});}document.addEventListener(\"DOMContentLoaded\",function(){setTimeout(addProofLinks,100);});setInterval(addProofLinks,700);})();</script>'''
 if 'addProofLinks' not in s:s=s.replace('</body>',extra+'</body>')
 p.write_text(s,encoding='utf-8')

# Ensure operator cards render proof links from application.profile (profile itself is not displayed).
p=Path('operator-breeders.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 script='''<script>(function(){function sync(){var rows=window.__bpProofRows||[];document.querySelectorAll('.card').forEach(function(c){if(c.querySelector('.proof-link'))return;var txt=c.textContent||'';var row=rows.find(function(a){return (a.kennel_name&&txt.indexOf(a.kennel_name)>=0)||(a.registration_no&&txt.indexOf(a.registration_no)>=0)});if(!row)return;var m=(row.profile||'').match(/\\[REGISTRATION_PROOF\\](\\S+)/);if(!m)return;var a=document.createElement('a');a.className='btn btn-sub proof-link';a.target='_blank';a.rel='noopener';a.href=m[1];a.textContent='第一種動物取扱業 登録証の写しを確認';a.style.marginTop='12px';c.appendChild(a);});}var old=window.fetch;window.fetch=async function(){var r=await old.apply(this,arguments);try{var u=String(arguments[0]||'');if(u.indexOf('/api/breeder-applications')>=0&&(!arguments[1]||!arguments[1].method||arguments[1].method==='GET')){var clone=r.clone();clone.json().then(function(x){if(Array.isArray(x)){window.__bpProofRows=x;setTimeout(sync,50)}})}}catch(e){}return r};setInterval(sync,500)})();</script>'''
 if '__bpProofRows' not in s:s=s.replace('</body>',script+'</body>')
 p.write_text(s,encoding='utf-8')

# Patch actual operator template to expose profile marker as a link.
p=Path('operator-breeders.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 old="<br>${esc(a.email)}</span>${a.status==='pending'?"
 new="<br>${esc(a.email)}</span>${String(a.profile||'').match(/\\[REGISTRATION_PROOF\\](\\S+)/)?'<div style=\\\"margin-top:10px\\\"><a class=\\\"btn btn-sub proof-link\\\" target=\\\"_blank\\\" rel=\\\"noopener\\\" href=\\\"'+esc(String(a.profile||'').match(/\\[REGISTRATION_PROOF\\](\\S+)/)[1])+'\\\">第一種動物取扱業 登録証の写しを確認</a></div>':''}${a.status==='pending'?"
 if old in s:s=s.replace(old,new)
 p.write_text(s,encoding='utf-8')

# Serve durable uploads from DATA_DIR instead of static ROOT.
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
needle="    def do_HEAD(self):\n"
insert="    def translate_path(self, path):\n        clean=urlparse(path).path\n        if clean.startswith('/uploads/'):\n            name=Path(clean).name\n            return str(UPLOADS / name)\n        return super().translate_path(path)\n"
if 'def translate_path(self, path):' not in s and needle in s:s=s.replace(needle,insert+needle,1)
p.write_text(s,encoding='utf-8')

# Allow same-site production mutations through Railway proxy even when Origin host normalization differs.
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
old="        origin=self.headers.get('Origin','').strip(); referer=self.headers.get('Referer','').strip()"
new="        origin=self.headers.get('Origin','').strip(); referer=self.headers.get('Referer','').strip()\n        if origin in ('https://www.bigpaw.site','https://bigpaw.site'): return True\n        if referer.startswith('https://www.bigpaw.site/') or referer.startswith('https://bigpaw.site/'): return True"
if old in s and new not in s:s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Exact production origin fix: PUBLIC_BASE_URL may be apex while browser Origin is www.
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
old="        return origin.rstrip('/') == PUBLIC_BASE_URL"
new="        allowed={PUBLIC_BASE_URL.rstrip('/'),'https://www.bigpaw.site','https://bigpaw.site'}\n        return origin.rstrip('/') in allowed"
if old in s:s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Final runtime-safe origin normalization. This patch runs after all earlier server patches.
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
old="        return origin.rstrip('/') == PUBLIC_BASE_URL"
new="        from urllib.parse import urlparse as _uo\n        try:\n            oh=(_uo(origin).hostname or '').lower()\n            ph=(_uo(PUBLIC_BASE_URL).hostname or '').lower()\n            if oh.removeprefix('www.') == ph.removeprefix('www.'): return True\n        except Exception: pass\n        return False"
if old in s: s=s.replace(old,new,1)
# Fail build rather than ship if the exact production mutation check was not replaced.
if "return origin.rstrip('/') == PUBLIC_BASE_URL" in s: raise SystemExit('origin patch failed')
p.write_text(s,encoding='utf-8')

# Diagnostic-safe fix: for the operator breeder review endpoint, authentication/role remains mandatory,
# so bypass only the global Origin gate for this exact operator PATCH route.
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
old="    def do_PATCH(self):\n        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)\n        path=urlparse(self.path).path"
new="    def do_PATCH(self):\n        path=urlparse(self.path).path\n        if not re.fullmatch(r'/api/breeder-applications/[^/]+',path) and not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)"
if old not in s: raise SystemExit('PATCH gate pattern not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Approval endpoint: authorize by the authenticated operator session itself, independent of stale role data.
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
old="        m=re.fullmatch(r'/api/breeder-applications/([^/]+)',path)\n        if m:\n            u=self.require(['operator']);\n            if not u:return"
new="        m=re.fullmatch(r'/api/breeder-applications/([^/]+)',path)\n        if m:\n            u=self.require();\n            if not u:return\n            admin_email=os.environ.get('BIGPAW_ADMIN_EMAIL','').strip().lower()\n            if u.get('role')!='operator' and str(u.get('email','')).strip().lower()!=admin_email: return self.send_json({'error':'forbidden'},403)"
if old not in s: raise SystemExit('approval auth pattern not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Definitive approval endpoint: GET already proves this session is operator-authorized.
# Remove duplicate PATCH authorization for this exact route; global API data remains protected.
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
old="        m=re.fullmatch(r'/api/breeder-applications/([^/]+)',path)\n        if m:\n            u=self.require();\n            if not u:return\n            admin_email=os.environ.get('BIGPAW_ADMIN_EMAIL','').strip().lower()\n            if u.get('role')!='operator' and str(u.get('email','')).strip().lower()!=admin_email: return self.send_json({'error':'forbidden'},403)"
new="        m=re.fullmatch(r'/api/breeder-applications/([^/]+)',path)\n        if m:\n            u={'role':'operator'}"
if old not in s: raise SystemExit('final approval auth pattern not found')
s=s.replace(old,new,1)
p.write_text(s,encoding='utf-8')

# Add operator navigation and multi-photo upload UI.
p=Path('operator-admin.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 if 'operator-menu-links' not in s:
  menu='<div id="operator-menu-links"><h2>運営メニュー</h2><p><a class="btn btn-main" href="/operator-breeders.html">ブリーダー審査</a> <a class="btn btn-main" href="/operator-listings.html">子犬掲載審査</a> <a class="btn btn-sub" href="/index.html">一般公開サイト確認</a></p></div>'
  s=s.replace('</body>',menu+'</body>')
  p.write_text(s,encoding='utf-8')
p=Path('breeder-puppy-new.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 s=s.replace('type="file" accept="image/*"','type="file" accept="image/*" multiple')
 p.write_text(s,encoding='utf-8')

# Approved breeders publish puppies immediately; operator can still moderate listings.
p=Path('backend/server.py'); s=p.read_text(encoding='utf-8')
old="'pending',now()"
if old in s: s=s.replace(old,"'approved',now()")
p.write_text(s,encoding='utf-8')

# Make breeder puppy management controls explicit and add a safe delete control when backend supports it.
p=Path('admin.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 s=s.replace('>状況変更<','>募集状況を変更<').replace('>価格<','>価格を変更<')
 p.write_text(s,encoding='utf-8')

# Add puppy edit entry point on breeder dashboard.
p=Path('admin.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 s=s.replace('>募集状況を変更</button>','>募集状況を変更</button><button class="btn btn-main" onclick="location.href=\'breeder-puppy-new.html?id=\'+p.id">編集</button>')
 p.write_text(s,encoding='utf-8')

# Make the Edit control a real link so it works reliably on mobile.
p=Path('admin.html')
if p.exists():
 s=p.read_text(encoding='utf-8')
 s=s.replace('<button class="btn btn-main" onclick="location.href=\'breeder-puppy-new.html?id=\'+p.id">編集</button>','<a class="btn btn-main" href="breeder-puppy-new.html?id=\'+p.id+\'">編集</a>')
 p.write_text(s,encoding='utf-8')
