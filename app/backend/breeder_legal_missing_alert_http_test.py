"""End-to-end: breeder alerts appear for legacy gaps, disappear after confirmation,
and return when registration address changes. All in isolated disposable data.
"""
from pathlib import Path
import json,os,socket,sqlite3,subprocess,sys,tempfile,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError

def req(base,path,method='GET',body=None,token=''):
    headers={'Content-Type':'application/json'}
    if token:headers['Authorization']='Bearer '+token
    data=None if body is None else json.dumps(body,ensure_ascii=False).encode()
    try:
        with urlopen(Request(base+path,method=method,data=data,headers=headers),timeout=10) as res:
            return res.status,json.loads(res.read() or b'{}')
    except HTTPError as err:
        return err.code,json.loads(err.read() or b'{}')

def check(cond,label):
    assert cond,label
    print('PASS',label,flush=True)

with tempfile.TemporaryDirectory(prefix='bigpaw-alert-') as tmp:
    with socket.socket() as sock:
        sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
    base=f'http://127.0.0.1:{port}'
    env={k:v for k,v in os.environ.items() if not k.startswith(('BIGPAW_','SMTP_','RESEND_'))}
    env.update({'BIGPAW_ENV':'development','BIGPAW_DATA_DIR':tmp,'PORT':str(port),'PYTHONUNBUFFERED':'1'})
    logfile=Path(tmp)/'server.log'
    with logfile.open('w') as out:
        process=subprocess.Popen([sys.executable,'/app/backend/server.py'],cwd='/app',env=env,stdout=out,stderr=subprocess.STDOUT)
        try:
            for _ in range(100):
                if process.poll() is not None:raise RuntimeError('server exited')
                try:
                    if req(base,'/api/health')[0]==200:break
                except Exception:pass
                time.sleep(.1)
            else:raise TimeoutError('server did not become ready')

            status,anon=req(base,'/api/breeder/legal-status')
            check(status in (401,403),'anonymous cannot view breeder legal alert details')
            status,buyer=req(base,'/api/login','POST',{'email':'demo@bigpaw.jp','password':'demo1234'})
            check(status==200 and buyer.get('token'),'buyer login')
            status,private=req(base,'/api/breeder/legal-status',token=buyer['token'])
            check(status in (401,403),'buyer cannot view breeder legal alert details')

            status,breeder=req(base,'/api/login','POST',{'email':'dog44@bigpaw.jp','password':'demo1234'})
            check(status==200 and breeder.get('token'),'breeder login')
            token=breeder['token']
            status,missing=req(base,'/api/breeder/legal-status',token=token)
            check(status==200 and not missing['complete'] and missing['missingCount']>=4,
                  'legacy breeder with no legal record sees incomplete alert')
            check('事業所の正式名称（登録証どおり）' in missing['missing'] and
                  '法定情報の一般公開確認' in missing['missing'],
                  'alert identifies exact missing legal office and consent')

            with sqlite3.connect(Path(tmp)/'bigpaw.sqlite3') as con:
                con.execute("UPDATE breeders SET visit_address=?,registration_no=? WHERE id='b_dog44'",
                    ('埼玉県さいたま市西区仮所在地1-2-3','SAMPLE-2026-001'))
                con.commit()
            valid={'operatorName':'事業者サンプル','officeName':'登録証の事業所名',
                   'registrationDate':'2024-04-01','expiresOn':'2029-03-31',
                   'animalManager':'責任者サンプル','businessType':'販売',
                   'confirmPublicDisclosure':True}
            status,success=req(base,'/api/breeder/legal-display','PATCH',valid,token)
            check(status==200 and success.get('confirmed'),'breeder saves legal record with public consent')
            status,complete=req(base,'/api/breeder/legal-status',token=token)
            check(status==200 and complete['complete'] and complete['missingCount']==0 and complete['missing']==[],
                  'alert automatically disappears after successful full eight-field confirmation')

            status,profile=req(base,'/api/breeder-profile','PATCH',
                {'visitAddress':'埼玉県さいたま市西区住所更新4-5-6'},token)
            check(status==200,'breeder updates registered address')
            status,reopen=req(base,'/api/breeder/legal-status',token=token)
            check(status==200 and not reopen['complete'] and
                  '法定情報の一般公開確認' in reopen['missing'],
                  'changing legal address automatically restores alert')
            status,renew=req(base,'/api/breeder/legal-display','PATCH',valid,token)
            check(status==200,'breeder re-confirms legal information')
            status,again=req(base,'/api/breeder/legal-status',token=token)
            check(status==200 and again['complete'],'alert clears again on re-confirmation')

            with sqlite3.connect(Path(tmp)/'bigpaw.sqlite3') as con:
                con.execute("UPDATE breeder_legal_disclosures SET office_name='' WHERE breeder_id='b_dog44'")
                con.commit()
            status,wrong=req(base,'/api/breeder/legal-status',token=token)
            check(status==200 and not wrong['complete'] and
                  '事業所の正式名称（登録証どおり）' in wrong['missing'],
                  'legacy kennel-brand fallback is never mistaken for completed formal name')
            with sqlite3.connect(Path(tmp)/'bigpaw.sqlite3') as con:
                con.execute("UPDATE breeder_legal_disclosures SET office_name=?,expires_on=? WHERE breeder_id='b_dog44'",
                            ('登録証の事業所名','2024-01-01'))
                con.commit()
            status,expired=req(base,'/api/breeder/legal-status',token=token)
            check(status==200 and not expired['complete'] and
                  '登録有効期限が切れています' in expired['missing'],
                  'expired registration keeps alert visible')
            print('BREEDER_LEGAL_ALERT_HTTP_GATE_OK|anon_denied|buyer_denied|old_warn|confirmed_clear|address_change_realert|reconfirm_clear|formal_office_missing|expiry_warn',flush=True)
        except Exception:
            print('SERVER_LOG_LAST\n'+logfile.read_text(encoding='utf-8')[-4500:],flush=True)
            raise
        finally:
            process.terminate()
            try:process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
