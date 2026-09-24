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

p.write_text(s, encoding='utf-8')
print('VISIT_CONTACT_PRIVACY_OK|public=hidden|confirmed_in_person=disclosed', flush=True)
