from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

old_migration="""    ensure_column(con,'breeders','billing_suspension_reason',\"TEXT DEFAULT ''\")
    def seed_user(uid, role, email, pw, last='', first='', display=''):
"""
new_migration="""    ensure_column(con,'breeders','billing_suspension_reason',\"TEXT DEFAULT ''\")
    ensure_column(con,'contracts','buyer_signer_name',\"TEXT DEFAULT ''\")
    ensure_column(con,'contracts','breeder_signer_name',\"TEXT DEFAULT ''\")
    def seed_user(uid, role, email, pw, last='', first='', display=''):
"""
assert s.count(old_migration)==1, ('contract_migration_marker_count',s.count(old_migration))
s=s.replace(old_migration,new_migration,1)

old_contract="""        m=re.fullmatch(r'/api/deals/([^/]+)/contract-sign',path)
        if m:
            u=self.require(['buyer','breeder','operator']);
            if not u:return
            con=db(); d=self.deal_for_user(con,m.group(1),u)
            if not d: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            c=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone()
            cid=c['id'] if c else make_id('c_')
            if not c: con.execute('INSERT INTO contracts VALUES(?,?,?,?,?,?,?)',(cid,d['id'],'v1',None,None,'draft',now()))
            if u['role']=='buyer': con.execute('UPDATE contracts SET buyer_signed_at=?,updated_at=? WHERE deal_id=?',(now(),now(),d['id']))
            elif u['role'] in ('breeder','operator'): con.execute('UPDATE contracts SET breeder_signed_at=?,updated_at=? WHERE deal_id=?',(now(),now(),d['id']))
            c=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone()
            if c['buyer_signed_at'] and c['breeder_signed_at']:
                con.execute(\"UPDATE contracts SET status='signed',updated_at=? WHERE deal_id=?\",(now(),d['id'])); con.execute(\"UPDATE deals SET status='contract_signed' WHERE id=?\",(d['id'],))
            con.commit(); r=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone(); con.close(); return self.send_json(dict(r),201)
"""
new_contract="""        m=re.fullmatch(r'/api/deals/([^/]+)/contract-sign',path)
        if m:
            u=self.require(['buyer','breeder']);
            if not u:return
            body=self.json_body(); signer_name=str(body.get('signerName','')).strip()
            if len(signer_name)<2 or len(signer_name)>100:
                return self.send_json({'error':'signer_name_required','message':'署名者氏名を2〜100文字で入力してください。'},400)
            con=db(); d=self.deal_for_user(con,m.group(1),u)
            if not d: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            paid=con.execute(\"SELECT 1 FROM payments WHERE deal_id=? AND kind='reservation' AND status='paid' LIMIT 1\",(d['id'],)).fetchone()
            if not paid:
                con.close(); return self.send_json({'error':'reservation_payment_required','message':'予約金の入金確認後に契約へ進めます。'},409)
            visit=con.execute('SELECT * FROM visits WHERE inquiry_id=?',(d['inquiry_id'],)).fetchone()
            if not visit or visit['status']!='confirmed':
                con.close(); return self.send_json({'error':'visit_confirmation_required','message':'見学日時の確定後に契約へ進めます。'},409)
            c=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone()
            if u['role']=='buyer' and c and c['buyer_signed_at']:
                out=dict(c); con.close(); return self.send_json(out,200)
            if u['role']=='breeder' and c and c['breeder_signed_at']:
                out=dict(c); con.close(); return self.send_json(out,200)
            if u['role']=='breeder':
                if body.get('faceToFaceConfirmed') is not True:
                    con.close(); return self.send_json({'error':'face_to_face_confirmation_required','message':'対面での個体確認・説明完了を確認してください。'},409)
                con.execute('UPDATE visits SET face_to_face_confirmed=1,updated_at=? WHERE inquiry_id=?',(now(),d['inquiry_id']))
            else:
                if not int(visit['face_to_face_confirmed'] or 0):
                    con.close(); return self.send_json({'error':'face_to_face_confirmation_required','message':'ブリーダーによる対面確認・説明完了後に署名できます。'},409)
            cid=c['id'] if c else make_id('c_')
            if not c:
                con.execute('INSERT INTO contracts(id,deal_id,version,buyer_signed_at,breeder_signed_at,status,updated_at,buyer_signer_name,breeder_signer_name) VALUES(?,?,?,?,?,?,?,?,?)',(cid,d['id'],'v1',None,None,'draft',now(),'',''))
            stamp=now()
            if u['role']=='buyer':
                con.execute('UPDATE contracts SET buyer_signed_at=?,buyer_signer_name=?,updated_at=? WHERE deal_id=?',(stamp,signer_name,stamp,d['id']))
            else:
                con.execute('UPDATE contracts SET breeder_signed_at=?,breeder_signer_name=?,updated_at=? WHERE deal_id=?',(stamp,signer_name,stamp,d['id']))
            audit(con,u['id'],'contract_signed','deal',d['id'],'role='+u['role']+'; signer='+signer_name)
            c=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone()
            if c['buyer_signed_at'] and c['breeder_signed_at']:
                con.execute(\"UPDATE contracts SET status='signed',updated_at=? WHERE deal_id=?\",(now(),d['id'])); con.execute(\"UPDATE deals SET status='contract_signed' WHERE id=?\",(d['id'],))
            con.commit(); r=con.execute('SELECT * FROM contracts WHERE deal_id=?',(d['id'],)).fetchone(); con.close(); return self.send_json(dict(r),201)
"""
assert s.count(old_contract)==1, ('contract_sign_block_count',s.count(old_contract))
s=s.replace(old_contract,new_contract,1)

p.write_text(s,encoding='utf-8')
print('CONTRACT_SIGNING_GUARD_OK|roles=buyer_breeder|reservation=paid|required_visit=confirmed|face_to_face=breeder_confirmed|signer_name=persisted',flush=True)
