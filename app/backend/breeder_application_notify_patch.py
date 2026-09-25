from pathlib import Path

p = Path('/app/backend/server.py')
s = p.read_text(encoding='utf-8')

old = """            con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(aid,)).fetchone()
            applicant_email=u['email']
            con.close()
            return self.send_json(dict(r),201)
"""

new = """            con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(aid,)).fetchone()
            applicant_email=u['email']
            operator_emails=[str(x['email']).strip() for x in con.execute(\"SELECT email FROM users WHERE role='operator' AND COALESCE(email,'')<>''\").fetchall() if str(x['email']).strip()]
            con.close()
            for operator_email in sorted(set(operator_emails)):
                send_mail(operator_email,'BIG PAW 新しいブリーダー掲載申請',f\"\"\"新しいブリーダー掲載申請が届きました。

犬舎名: {body.get('kennelName','')}
代表者: {body.get('representative','')}
都道府県: {body.get('prefecture','')}
主な取扱犬種: {body.get('primaryBreed','')}
第一種動物取扱業 登録番号: {body.get('registrationNo','')}
申請者メール: {applicant_email}

運営管理画面から申請内容を確認し、承認または差し戻しを行ってください。
{PUBLIC_BASE_URL}/operator-breeders.html\"\"\")
            return self.send_json(dict(r),201)
"""

if old not in s:
    raise SystemExit('BREEDER_APPLICATION_NOTIFY_PATCH_FAILED: application return block not found')

s = s.replace(old, new, 1)
p.write_text(s, encoding='utf-8')

# Surface pending breeder applications prominently on the operator dashboard.
admin = Path('/app/operator-admin.html')
html = admin.read_text(encoding='utf-8')
card_anchor = '<a class="statlink" href="operator-breeders.html" aria-label="掲載ブリーダーを確認"><div class="card statbox"><span class="muted">掲載ブリーダー</span><b id="opBreeders">-</b></div></a>'
card = card_anchor + '<a class="statlink" href="operator-breeders.html" aria-label="ブリーダー審査待ちを確認"><div class="card statbox"><span class="muted">ブリーダー審査待ち</span><b id="opBreederApps">-</b></div></a>'
if card_anchor not in html:
    raise SystemExit('BREEDER_APPLICATION_NOTIFY_PATCH_FAILED: operator dashboard card anchor not found')
html = html.replace(card_anchor, card, 1)
live_anchor = 'opUsers.textContent=s.users;opBreeders.textContent=s.breeders;opPuppies.textContent=s.openPuppies;'
live_new = 'opUsers.textContent=s.users;opBreeders.textContent=s.breeders;opBreederApps.textContent=s.pendingBreederApplications||0;opPuppies.textContent=s.openPuppies;'
if live_anchor not in html:
    raise SystemExit('BREEDER_APPLICATION_NOTIFY_PATCH_FAILED: operator dashboard live stats anchor not found')
html = html.replace(live_anchor, live_new, 1)
demo_anchor = 'opUsers.textContent=1;opBreeders.textContent=1;opPuppies.textContent=BigPaw.getPuppies().filter(p=>p.status===\'募集中\').length;'
demo_new = 'opUsers.textContent=1;opBreeders.textContent=1;opBreederApps.textContent=0;opPuppies.textContent=BigPaw.getPuppies().filter(p=>p.status===\'募集中\').length;'
if demo_anchor not in html:
    raise SystemExit('BREEDER_APPLICATION_NOTIFY_PATCH_FAILED: operator dashboard demo stats anchor not found')
html = html.replace(demo_anchor, demo_new, 1)
admin.write_text(html, encoding='utf-8')

print('BREEDER_APPLICATION_NOTIFY_OK|email=all_operator_accounts|dashboard=pending_count|review_link=operator_breeders', flush=True)
