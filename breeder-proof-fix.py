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
# Do not make notification email delivery part of the application request response path.
s=s.replace("send_mail(applicant_email,'BIG PAW 掲載審査申請を受け付けました'","__import__('threading').Thread(target=send_mail,args=(applicant_email,'BIG PAW 掲載審査申請を受け付けました'")
s=s.replace("send_mail(op_email,'BIG PAW ブリーダー掲載審査申請'","__import__('threading').Thread(target=send_mail,args=(op_email,'BIG PAW ブリーダー掲載審査申請'")
# Close only the injected thread calls if exact flow patch produced them.
s=s.replace("BASE_URL+'/breeder-register.html')","BASE_URL+'/breeder-register.html'),daemon=True).start()")
s=s.replace("BASE_URL+'/operator-breeders.html')","BASE_URL+'/operator-breeders.html'),daemon=True).start()")
p.write_text(s,encoding='utf-8')
