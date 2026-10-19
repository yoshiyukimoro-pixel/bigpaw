"""Explicit and audited animal-handling business legal advertisement disclosure.

Legal information is disclosed only after the approved breeder explicitly confirms
the eight mandatory particulars. Never infer consent from an old private address.
"""
from pathlib import Path

ROOT=Path('/app')
path=ROOT/'backend/server.py'
src=path.read_text(encoding='utf-8')

def once(old,new,tag):
    global src
    assert src.count(old)==1,(tag,src.count(old))
    src=src.replace(old,new,1)

once("CREATE TABLE IF NOT EXISTS breeder_applications(",'''CREATE TABLE IF NOT EXISTS breeder_legal_disclosures(
 breeder_id TEXT PRIMARY KEY REFERENCES breeders(id) ON DELETE CASCADE,
 operator_name TEXT NOT NULL DEFAULT '',
 registration_date TEXT NOT NULL DEFAULT '',
 expires_on TEXT NOT NULL DEFAULT '',
 animal_manager TEXT NOT NULL DEFAULT '',
 business_type TEXT NOT NULL DEFAULT '販売',
 confirmed INTEGER NOT NULL DEFAULT 0,
 updated_at INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS breeder_applications(''','disclosure_table')

once("    ensure_column(con,'breeders','billing_suspension_reason',\"TEXT DEFAULT ''\")",
"""    ensure_column(con,'breeders','billing_suspension_reason',"TEXT DEFAULT ''")
    ensure_column(con,'breeder_applications','legal_registration_date',"TEXT DEFAULT ''")
    ensure_column(con,'breeder_applications','legal_animal_manager',"TEXT DEFAULT ''")
    ensure_column(con,'breeder_applications','legal_ad_consent',"INTEGER NOT NULL DEFAULT 0")""",
'legal_app_registration_fields')

# New applicants confirm explicitly that their registered business identity and
# registered address are public in the mandatory advertisement section.
before="            con=db(); old=con.execute('SELECT * FROM breeder_applications WHERE user_id=?',(u['id'],)).fetchone()"
new="""            legal_reg_date=str(body.get('legalRegistrationDate','')).strip()
            legal_manager=str(body.get('legalAnimalManager','')).strip()
            if not re.fullmatch(r'\\d{4}-\\d{2}-\\d{2}',legal_reg_date) or not legal_manager or not body.get('legalAdConsent'):
                return self.send_json({'error':'legal_ad_fields_required','message':'広告の法定表示に必要な登録年月日・動物取扱責任者名・事業者情報の公開確認が必要です。'},400)
            con=db(); old=con.execute('SELECT * FROM breeder_applications WHERE user_id=?',(u['id'],)).fetchone()"""
once(before,new,'application_legal_input_validation')

before="            con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(aid,)).fetchone()"
new="""            con.execute('UPDATE breeder_applications SET legal_registration_date=?,legal_animal_manager=?,legal_ad_consent=1 WHERE id=?',
                (legal_reg_date,legal_manager,aid))
            con.commit(); r=con.execute('SELECT * FROM breeder_applications WHERE id=?',(aid,)).fetchone()"""
once(before,new,'application_legal_fields_persisted')

before="""            if status=='approved':
                con.execute("UPDATE users SET role='breeder' WHERE id=? AND role!='operator'",(a['user_id'],))
                con.commit()"""
new="""            if status=='approved':
                bb=con.execute('SELECT * FROM breeders WHERE user_id=?',(a['user_id'],)).fetchone()
                if bb and a['legal_ad_consent'] and a['legal_registration_date'] and a['legal_animal_manager'] and a['expires_on'] and a['visit_address'] and a['registration_no']:
                    con.execute('''INSERT OR IGNORE INTO breeder_legal_disclosures
                        (breeder_id,operator_name,registration_date,expires_on,animal_manager,business_type,confirmed,updated_at)
                        VALUES(?,?,?,?,?,'販売',1,?)''',
                        (bb['id'],a['representative'],a['legal_registration_date'],a['expires_on'],a['legal_animal_manager'],now()))
                con.execute("UPDATE users SET role='breeder' WHERE id=? AND role!='operator'",(a['user_id'],))
                con.commit()"""
once(before,new,'approved_application_legal_disclosure')

# When a breeder changes registered identity, address, region or registration
# number, the previous public authorization must be invalidated.
needle="con.execute('UPDATE breeders SET kennel_name=?,prefecture=?,profile=?,registration_no=?,visit_address=?,visit_phone=?,visit_access=? WHERE id=?'"
assert src.count(needle)==1,('profile_legal_invalidate_hook',src.count(needle))
src=src.replace(needle,
    """(con.execute('UPDATE breeder_legal_disclosures SET confirmed=0 WHERE breeder_id=?',(b['id'],))
            if any((kennel!=b['kennel_name'],prefecture!=b['prefecture'],reg!=b['registration_no'],visit_address!=b['visit_address']))
            else None); """+needle,1)

# Public legal response is strictly opt-in and is built from an allowlist.
GET_MARKER="        if path=='/api/breeder-profile':\n"
GET_ADDITION="""        mlegal=re.fullmatch(r'/api/breeders/([^/]+)/legal',path)
        if mlegal:
            con=db()
            row=con.execute('''SELECT b.kennel_name,b.visit_address,b.registration_no,
                b.review_status,COALESCE(b.billing_suspended,0) billing_suspended,
                l.operator_name,l.registration_date,l.expires_on,l.animal_manager,l.business_type,l.confirmed
                FROM breeders b JOIN breeder_legal_disclosures l ON l.breeder_id=b.id
                WHERE b.id=?''',(mlegal.group(1),)).fetchone()
            con.close()
            if not row or row['review_status']!='approved' or row['billing_suspended'] or not row['confirmed']:
                return self.send_json({'error':'not_found'},404)
            vals=[row[k] for k in ('kennel_name','visit_address','registration_no','operator_name','registration_date','expires_on','animal_manager','business_type')]
            if not all(str(v or '').strip() for v in vals):
                return self.send_json({'error':'not_found'},404)
            return self.send_json({
                'operatorName':row['operator_name'],'officeName':row['kennel_name'],
                'officeAddress':row['visit_address'],'businessType':row['business_type'],
                'registrationNo':row['registration_no'],'registrationDate':row['registration_date'],
                'expiresOn':row['expires_on'],'animalManager':row['animal_manager']})
        if path=='/api/breeder/legal-display':
            u=self.require(['breeder','operator'])
            if not u:return
            con=db()
            if u['role']=='operator':
                bid=(q.get('breederId') or [''])[0]
                if not bid: con.close(); return self.send_json({'error':'breeder_id_required'},400)
                b=con.execute('SELECT * FROM breeders WHERE id=?',(bid,)).fetchone()
                owner_id=b['user_id'] if b else ''
            else:
                b=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                owner_id=u['id']
            if not b: con.close(); return self.send_json({'error':'not_found'},404)
            info=con.execute('SELECT * FROM breeder_legal_disclosures WHERE breeder_id=?',(b['id'],)).fetchone()
            ap=con.execute('SELECT representative,expires_on,legal_registration_date,legal_animal_manager FROM breeder_applications WHERE user_id=? ORDER BY updated_at DESC LIMIT 1',(owner_id,)).fetchone()
            con.close()
            d=dict(info) if info else {}
            return self.send_json({
                'officeName':b['kennel_name'],'officeAddress':b['visit_address'],
                'registrationNo':b['registration_no'],'businessType':d.get('business_type') or '販売',
                'operatorName':d.get('operator_name') or (ap['representative'] if ap else ''),
                'registrationDate':d.get('registration_date') or (ap['legal_registration_date'] if ap else ''),
                'expiresOn':d.get('expires_on') or (ap['expires_on'] if ap else ''),
                'animalManager':d.get('animal_manager') or (ap['legal_animal_manager'] if ap else ''),
                'confirmed':bool(d.get('confirmed',0))})
"""
assert src.count(GET_MARKER)>=1
first=src.index('    def do_GET(self):')
last=src.index('    def do_POST(self):')
get_section=src[first:last]
assert get_section.count(GET_MARKER)==1,('get_legal_route',get_section.count(GET_MARKER))
get_section=get_section.replace(GET_MARKER,GET_ADDITION+GET_MARKER,1)
src=src[:first]+get_section+src[last:]

PATCH_MARKER="        if path=='/api/breeder-profile':\n"
PATCH_ADDITION="""        if path=='/api/breeder/legal-display':
            u=self.require(['breeder'])
            if not u:return
            data=self.json_body()
            if not data.get('confirmPublicDisclosure'):
                return self.send_json({'error':'legal_ad_consent_required'},400)
            con=db(); b=con.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            if not b: con.close(); return self.send_json({'error':'not_found'},404)
            operator_name=str(data.get('operatorName','')).strip()
            registration_date=str(data.get('registrationDate','')).strip()
            expires_on=str(data.get('expiresOn','')).strip()
            manager=str(data.get('animalManager','')).strip()
            business_type=str(data.get('businessType','販売')).strip()
            if not all((operator_name,registration_date,expires_on,manager,business_type,
                        str(b['kennel_name'] or '').strip(),str(b['visit_address'] or '').strip(),str(b['registration_no'] or '').strip())):
                con.close(); return self.send_json({'error':'legal_required_fields'},400)
            try:
                import datetime as _legal_datetime
                reg_dt=_legal_datetime.date.fromisoformat(registration_date)
                exp_dt=_legal_datetime.date.fromisoformat(expires_on)
            except ValueError:
                con.close(); return self.send_json({'error':'invalid_legal_ad_fields'},400)
            if reg_dt>exp_dt or '販売' not in business_type:
                con.close(); return self.send_json({'error':'invalid_legal_ad_fields'},400)
            con.execute('''INSERT INTO breeder_legal_disclosures(
                breeder_id,operator_name,registration_date,expires_on,animal_manager,business_type,confirmed,updated_at)
                VALUES(?,?,?,?,?,?,1,?)
                ON CONFLICT(breeder_id) DO UPDATE SET operator_name=excluded.operator_name,
                registration_date=excluded.registration_date,expires_on=excluded.expires_on,
                animal_manager=excluded.animal_manager,business_type=excluded.business_type,
                confirmed=1,updated_at=excluded.updated_at''',
                (b['id'],operator_name,registration_date,expires_on,manager,business_type,now()))
            audit(con,u['id'],'legal_ad_disclosure_confirmed','breeder',b['id'])
            con.commit(); con.close()
            return self.send_json({'ok':True,'confirmed':True})
"""
pos=src.index('    def do_PATCH(self):')
patch=src[pos:]
assert patch.count(PATCH_MARKER)==1,('legal_patch_route',patch.count(PATCH_MARKER))
src=src[:pos]+patch.replace(PATCH_MARKER,PATCH_ADDITION+PATCH_MARKER,1)

compile(src,str(path),'exec')
path.write_text(src,encoding='utf-8')
print('BREEDER_LEGAL_DISCLOSURE_BACKEND_OK|eight_statutory_fields|explicit_public_consent|required_on_signup|safe_old_records|authenticated_changes|auto_visit_address',flush=True)
