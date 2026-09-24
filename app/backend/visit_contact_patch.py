from pathlib import Path

p = Path('/app/backend/server.py')
s = p.read_text(encoding='utf-8')

# Add private breeder visit-contact fields.
a = "    ensure_column(con,'breeders','billing_suspension_reason',\"TEXT DEFAULT ''\")"
b = a + "\n    ensure_column(con,'breeders','visit_address',\"TEXT DEFAULT ''\")\n    ensure_column(con,'breeders','visit_phone',\"TEXT DEFAULT ''\")\n    ensure_column(con,'breeders','visit_access',\"TEXT DEFAULT ''\")"
assert s.count(a) == 1, ('visit_columns_marker', s.count(a))
s = s.replace(a, b, 1)

# Never expose private visit details through public breeder APIs.
a = "for k in ('user_id','registration_no','registration_proof','registration_proof_path','email','phone','address','postal_code','line','line_id','instagram','sns','website','url'):"
b = "for k in ('user_id','registration_no','registration_proof','registration_proof_path','email','phone','address','postal_code','line','line_id','instagram','sns','website','url','visit_address','visit_phone','visit_access'):"
assert s.count(a) == 1, ('public_breeder_private_fields_marker', s.count(a))
s = s.replace(a, b, 1)

# Return private visit contact only to the participants after an in-person visit is confirmed.
a = "            r=con.execute('SELECT * FROM visits WHERE inquiry_id=?',(m.group(1),)).fetchone(); con.close(); return self.send_json(dict(r) if r else None)"
b = "            r=con.execute('SELECT * FROM visits WHERE inquiry_id=?',(m.group(1),)).fetchone()\n            out=dict(r) if r else None\n            if out and out.get('status')=='confirmed' and out.get('transport')!='オンライン見学' and qrow['breeder_id']:\n                bc=con.execute('SELECT visit_address,visit_phone,visit_access FROM breeders WHERE id=?',(qrow['breeder_id'],)).fetchone()\n                if bc:\n                    out['visitContact']={'address':bc['visit_address'] or '', 'phone':bc['visit_phone'] or '', 'access':bc['visit_access'] or ''}\n            con.close(); return self.send_json(out)"
assert s.count(a) == 1, ('visit_get_marker', s.count(a))
s = s.replace(a, b, 1)

# Allow breeder/operator to maintain private visit contact fields without affecting public profile.
a = "            kennel=str(body.get('kennelName',b['kennel_name'])).strip(); prefecture=str(body.get('prefecture',b['prefecture'])).strip(); profile=str(body.get('profile',b['profile'])).strip(); reg=str(body.get('registrationNo',b['registration_no'])).strip(); con.execute('UPDATE breeders SET kennel_name=?,prefecture=?,profile=?,registration_no=? WHERE id=?',(kennel,prefecture,profile,reg,b['id'])); con.execute('UPDATE puppies SET breeder_name=?,area=?,area_key=? WHERE breeder_id=?',(kennel,prefecture,AREA_KEYS.get(prefecture,'other'),b['id'])); audit(con,u['id'],'breeder_profile_updated','breeder',b['id']); con.commit(); out=con.execute('SELECT * FROM breeders WHERE id=?',(b['id'],)).fetchone(); con.close(); return self.send_json(dict(out))"
b = "            kennel=str(body.get('kennelName',b['kennel_name'])).strip(); prefecture=str(body.get('prefecture',b['prefecture'])).strip(); profile=str(body.get('profile',b['profile'])).strip(); reg=str(body.get('registrationNo',b['registration_no'])).strip(); visit_address=str(body.get('visitAddress',b['visit_address'] if 'visit_address' in b.keys() else '')).strip(); visit_phone=str(body.get('visitPhone',b['visit_phone'] if 'visit_phone' in b.keys() else '')).strip(); visit_access=str(body.get('visitAccess',b['visit_access'] if 'visit_access' in b.keys() else '')).strip(); con.execute('UPDATE breeders SET kennel_name=?,prefecture=?,profile=?,registration_no=?,visit_address=?,visit_phone=?,visit_access=? WHERE id=?',(kennel,prefecture,profile,reg,visit_address,visit_phone,visit_access,b['id'])); con.execute('UPDATE puppies SET breeder_name=?,area=?,area_key=? WHERE breeder_id=?',(kennel,prefecture,AREA_KEYS.get(prefecture,'other'),b['id'])); audit(con,u['id'],'breeder_profile_updated','breeder',b['id']); con.commit(); out=con.execute('SELECT * FROM breeders WHERE id=?',(b['id'],)).fetchone(); con.close(); return self.send_json(dict(out))"
assert s.count(a) == 1, ('breeder_profile_update_marker', s.count(a))
s = s.replace(a, b, 1)

# An in-person visit cannot be confirmed until a private address and same-day phone are registered.
a = "            if visit_status == 'confirmed' and u.get('role') not in ('breeder','operator'):\n                con.close(); return self.send_json({'error':'breeder_only_confirmation'},403)"
b = a + "\n            if visit_status=='confirmed' and body.get('transport')!='オンライン見学' and qrow['breeder_id']:\n                vc=con.execute('SELECT visit_address,visit_phone FROM breeders WHERE id=?',(qrow['breeder_id'],)).fetchone()\n                if not vc or not str(vc['visit_address'] or '').strip() or not str(vc['visit_phone'] or '').strip():\n                    con.close(); return self.send_json({'error':'visit_contact_required','message':'対面見学を確定する前に、犬舎プロフィールで見学場所の住所と当日の連絡先を登録してください。'},409)"
assert s.count(a) == 1, ('visit_confirmation_contact_guard_marker', s.count(a))
s = s.replace(a, b, 1)

# On confirmed in-person visits, notify the buyer and send the private location by email.
a = "            inquiry_status='見学確定' if visit_status=='confirmed' else '見学調整中'\n            con.execute('UPDATE inquiries SET status=? WHERE id=?',(inquiry_status,m.group(1)))\n            con.commit(); r=con.execute('SELECT * FROM visits WHERE id=?',(vid,)).fetchone(); con.close()\n            if body.get('transport')=='オンライン見学': self.online_visit_email(m.group(1), visit_status, body.get('date',''), body.get('time',''))\n            return self.send_json(dict(r),201)"
b = "            inquiry_status='見学確定' if visit_status=='confirmed' else '見学調整中'\n            con.execute('UPDATE inquiries SET status=? WHERE id=?',(inquiry_status,m.group(1)))\n            private_visit_mail=None\n            if visit_status=='confirmed' and body.get('transport')!='オンライン見学' and qrow['breeder_id']:\n                info=con.execute('SELECT b.visit_address,b.visit_phone,b.visit_access,u.id buyer_user_id,u.email buyer_email FROM breeders b JOIN inquiries i ON i.breeder_id=b.id JOIN users u ON u.id=i.buyer_id WHERE i.id=?',(m.group(1),)).fetchone()\n                if info:\n                    private_visit_mail=dict(info)\n                    con.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(make_id('n_'),info['buyer_user_id'],'visit','見学日時が確定しました',f\"{body.get('date','')} {body.get('time','')} / 見学場所は見学日程画面で確認できます。\",0,now()))\n            con.commit(); r=con.execute('SELECT * FROM visits WHERE id=?',(vid,)).fetchone(); con.close()\n            if body.get('transport')=='オンライン見学':\n                self.online_visit_email(m.group(1), visit_status, body.get('date',''), body.get('time',''))\n            elif private_visit_mail and private_visit_mail.get('buyer_email'):\n                addr=private_visit_mail.get('visit_address') or ''; phone=private_visit_mail.get('visit_phone') or ''; access=private_visit_mail.get('visit_access') or ''\n                access_line=('\\nアクセス・駐車場：'+access) if access else ''\n                send_mail(private_visit_mail['buyer_email'],'【BIG PAW】見学日時が確定しました',f\"見学日時が確定しました。\\n\\n日時：{body.get('date','')} {body.get('time','')}\\n見学場所：{addr}\\n当日の連絡先：{phone}{access_line}\\n\\nこの住所・電話番号は見学のために共有された情報です。第三者への共有はお控えください。\\n\\nBIG PAW\\n{PUBLIC_BASE_URL}/visit-confirm.html?inquiry={m.group(1)}\")\n            return self.send_json(dict(r),201)"
assert s.count(a) == 1, ('in_person_visit_mail_marker', s.count(a))
s = s.replace(a, b, 1)

p.write_text(s, encoding='utf-8')
print('VISIT_CONTACT_PRIVACY_OK|public=prefecture_only|confirmed_in_person=address_phone_access|email=buyer_only', flush=True)
