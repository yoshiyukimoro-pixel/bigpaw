from pathlib import Path
p=Path('backend/server.py')
s=p.read_text(encoding='utf-8')
old="con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(aid,)).fetchone(); con.close(); return self.send_json(dict(r),201)"
new="""con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(aid,)).fetchone()
            applicant_email=u['email']
            operators=con.execute("SELECT email FROM users WHERE role='operator'").fetchall()
            con.close()
            send_mail(applicant_email,'BIG PAW 掲載審査申請を受け付けました',f"{r['kennel_name']} 様\\n\\n掲載審査申請を受け付けました。現在、運営による審査中です。\\n審査完了後、メールでお知らせします。\\n\\n申請状況: {PUBLIC_BASE_URL}/breeder-register.html")
            for op in operators:
                send_mail(op['email'],'BIG PAW ブリーダー掲載審査申請',f"新しいブリーダー掲載審査申請が届きました。\\n\\n犬舎名: {r['kennel_name']}\\n代表者: {r['representative']}\\n都道府県: {r['prefecture']}\\n\\n運営管理: {PUBLIC_BASE_URL}/operator-breeders.html")
            return self.send_json(dict(r),201)"""
if old not in s: raise SystemExit('apply target not found')
s=s.replace(old,new,1)
old2="con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(a['id'],)).fetchone(); con.close(); return self.send_json(dict(r))"
new2="""con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(a['id'],)).fetchone()
            applicant=con.execute('SELECT email FROM users WHERE id=?',(a['user_id'],)).fetchone()
            con.close()
            if applicant:
                if status=='approved':
                    send_mail(applicant['email'],'BIG PAW 掲載審査が承認されました',f"{a['kennel_name']} 様\\n\\n掲載審査が承認されました。ブリーダー管理画面から子犬を登録できます。\\n\\n子犬を登録する: {PUBLIC_BASE_URL}/breeder-puppy-new.html\\n管理画面: {PUBLIC_BASE_URL}/admin.html")
                elif status=='rejected':
                    send_mail(applicant['email'],'BIG PAW 掲載審査について',f"{a['kennel_name']} 様\\n\\n掲載審査の内容をご確認ください。\\n{note or '申請内容をご確認のうえ、再申請してください。'}\\n\\n{PUBLIC_BASE_URL}/breeder-register.html")
            return self.send_json(dict(r))"""
if old2 not in s: raise SystemExit('review target not found')
s=s.replace(old2,new2,1)
p.write_text(s,encoding='utf-8')

p=Path('breeder-register.html'); s=p.read_text(encoding='utf-8')
s=s.replace("current.textContent='現在の申請状況：'+({pending:'審査中',approved:'承認済み',rejected:'差し戻し'}[rows[0].status]||rows[0].status)+(rows[0].review_note?'｜'+rows[0].review_note:'');if(rows[0].status!=='rejected')submitBtn.disabled=true",
"""const st=rows[0].status;current.innerHTML=st==='pending'?'<b>掲載審査申請済み・審査中</b><br>審査が完了するとメールでお知らせします。':st==='approved'?'<b>掲載審査が承認されました。</b><br><a class="btn btn-main" style="margin-top:10px" href="breeder-puppy-new.html">子犬を登録する</a>':('<b>申請内容をご確認ください。</b>'+(rows[0].review_note?'<br>'+rows[0].review_note:''));if(st!=='rejected')submitBtn.disabled=true""")
p.write_text(s,encoding='utf-8')
