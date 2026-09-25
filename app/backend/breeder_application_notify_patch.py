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
print('BREEDER_APPLICATION_NOTIFY_OK|email=all_operator_accounts|review_link=operator_breeders', flush=True)
