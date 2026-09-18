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
