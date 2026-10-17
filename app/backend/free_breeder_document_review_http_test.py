"""Isolated HTTP test: approval requires human review of a real uploaded certificate."""
from pathlib import Path
import os, tempfile, subprocess, sys, socket, json, time, sqlite3, base64
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def call(base,path,method='GET',body=None,token=''):
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    request=Request(base+path,method=method,data=None if body is None else json.dumps(body,ensure_ascii=False).encode('utf-8'),headers=headers)
    try:
        with urlopen(request,timeout=8) as resp:
            raw=resp.read()
            try: data=json.loads(raw)
            except Exception: data=raw
            return resp.status,data
    except HTTPError as e:
        try: return e.code,json.loads(e.read())
        except Exception: return e.code,{}

with tempfile.TemporaryDirectory(prefix='bigpaw-freeproof-') as tmp:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env={k:v for k,v in os.environ.items() if not k.startswith(('BIGPAW_','SMTP_','RESEND_'))}
    env.update({'BIGPAW_ENV':'development','BIGPAW_DATA_DIR':tmp,'PORT':str(port),'PYTHONUNBUFFERED':'1'})
    logfile=Path(tmp)/'runtime.log'
    with logfile.open('w') as log:
        process=subprocess.Popen([sys.executable,'/app/backend/server.py'],cwd='/app',env=env,stdout=log,stderr=subprocess.STDOUT)
        try:
            for i in range(100):
                if process.poll() is not None: raise RuntimeError('server crashed: '+logfile.read_text()[-4000:])
                try:
                    if call(base,'/api/health')[0]==200: break
                except Exception: pass
                time.sleep(.1)
            else: raise RuntimeError('server timeout')
            status,op=call(base,'/api/login','POST',{'email':'admin@bigpaw.jp','password':'admin1234'})
            assert status==200 and op.get('token'),('operator login',status,op)
            token=op['token']
            status,bu=call(base,'/api/login','POST',{'email':'demo@bigpaw.jp','password':'demo1234'})
            assert status==200 and bu.get('token'),('buyer login',status,bu)
            buyer=bu['token']
            db=Path(tmp)/'bigpaw.sqlite3'
            with sqlite3.connect(db) as con:
                con.execute("""INSERT INTO breeder_applications
                   (id,user_id,kennel_name,representative,prefecture,primary_breed,registration_no,
                    expires_on,profile,status,review_note,created_at,updated_at,
                    visit_address,visit_phone,visit_access,legal_registration_date,legal_animal_manager,
                    legal_ad_consent,legal_office_name)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                  ('ba_free','u_demo','PUBLIC-BRAND','申請者 太郎','埼玉県','サモエド','REG-0001',
                   '2029-10-01','公開情報\n[REGISTRATION_PROOF]/uploads/test-reg.png','pending','',1,1,
                   '埼玉県さいたま市西区試験町1-2','090-9999-9999','','2024-10-01','管理者 花子',1,'正式ケンネル名'))
                con.execute("""INSERT INTO uploads
                 (id,user_id,puppy_id,original_name,stored_name,mime_type,created_at)
                 VALUES (?,?,?,?,?,?,?)""",
                ('upload_free','u_demo',None,'registration.png','test-reg.png','image/png',1))
                con.commit()
            checklist={k:True for k in ('operatorName','officeName','officeAddress','businessType',
                    'registrationNo','registrationDate','expiresOn','animalManager')}
            payload={'status':'approved'}
            endpoint='/api/breeder-applications/ba_free'
            status,_=call(base,endpoint,'PATCH',payload,token)
            assert status==409,('must reject direct approval without comparison',status)
            status,_=call(base,endpoint,'PATCH',dict(payload,legalDocumentChecklist={**checklist,'officeName':False},proofViewed=True),token)
            assert status==409,('must reject missing office check',status)
            status,_=call(base,endpoint,'PATCH',dict(payload,legalDocumentChecklist=checklist,proofViewed=False),token)
            assert status==409,('must reject unseen proof image',status)
            status,_=call(base,endpoint,'PATCH',dict(payload,legalDocumentChecklist=checklist,proofViewed=True),token)
            assert status==409,('must reject missing file on disk',status)
            (Path(tmp)/'uploads'/'test-reg.png').write_bytes(base64.b64decode(
                'iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+jqT0AAAAASUVORK5CYII='))
            status,_=call(base,'/api/operator/breeder-proof/ba_free','GET',token=buyer)
            assert status in (401,403),('buyer must not read proof',status)
            status,raw=call(base,'/api/operator/breeder-proof/ba_free','GET',token=token)
            assert status==200 and isinstance(raw,bytes) and raw.startswith(b'\x89PNG'),('operator can view proof',status)
            status,_=call(base,endpoint,'PATCH',dict(payload,legalDocumentChecklist=checklist,proofViewed=True),token)
            assert status==200,('valid manual review approved',status)
            with sqlite3.connect(db) as con:
                state=con.execute("SELECT status FROM breeder_applications WHERE id='ba_free'").fetchone()[0]
                detail=con.execute("SELECT office_name FROM breeder_legal_disclosures WHERE breeder_id IN (SELECT id FROM breeders WHERE user_id='u_demo')").fetchone()
                events=con.execute("SELECT COUNT(*) FROM audit_logs WHERE action='breeder_registration_proof_manually_checked'").fetchone()[0]
                assert state=='approved' and detail and detail[0]=='正式ケンネル名' and events==1,(state,detail,events)
            print('FREE_BREEDER_DOCUMENT_HTTP_GATE_OK|reject_bypass|reject_partial|reject_unviewed|reject_missing_file|proof_operator_only|legal_office_preserved|audit_saved',flush=True)
        except Exception:
            print('TEST_SERVER_LOG_LAST\n'+logfile.read_text(encoding='utf-8')[-6500:],flush=True)
            raise
        finally:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
