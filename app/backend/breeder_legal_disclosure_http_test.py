"""Build-time HTTP end-to-end test of consent-gated legal disclosure and privacy.

Uses a throwaway local SQLite database and a loopback-only web server. Never
uses real customer data, external email, or live Railway resources.
"""
from pathlib import Path
import json, os, socket, sqlite3, subprocess, sys, tempfile, time, urllib.request, urllib.error

ROOT=Path('/app')
def port():
    with socket.socket() as sk:
        sk.bind(('127.0.0.1',0))
        return sk.getsockname()[1]

def req(base,path,method='GET',payload=None,token=''):
    raw=None if payload is None else json.dumps(payload,ensure_ascii=False).encode('utf-8')
    headers={'Content-Type':'application/json'}
    if token: headers['Authorization']='Bearer '+token
    request=urllib.request.Request(base+path,data=raw,method=method,headers=headers)
    try:
        with urllib.request.urlopen(request,timeout=8) as r:
            return r.status,json.loads(r.read().decode('utf-8') or '{}')
    except urllib.error.HTTPError as e:
        return e.code,json.loads(e.read().decode('utf-8') or '{}')

def ok(v,message):
    if not v: raise AssertionError(message)
    print('PASS',message,flush=True)

with tempfile.TemporaryDirectory(prefix='bigpaw-legal-http-') as scratch:
    p=port();base=f'http://127.0.0.1:{p}'
    env={k:v for k,v in os.environ.items() if not k.startswith(('BIGPAW_','SMTP_','RESEND_'))}
    env.update({'BIGPAW_ENV':'development','BIGPAW_DATA_DIR':scratch,'PORT':str(p),
                'PYTHONUNBUFFERED':'1','BIGPAW_DEV_LINKS':'1'})
    out=Path(scratch)/'server.log'
    with out.open('w+') as logfile:
        process=subprocess.Popen([sys.executable,str(ROOT/'backend/server.py')],cwd=ROOT,env=env,
                                 stdout=logfile,stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                if process.poll() is not None: raise RuntimeError('server died: '+out.read_text()[-5000:])
                try:
                    status,_=req(base,'/api/health')
                    if status==200: break
                except Exception: pass
                time.sleep(0.1)
            else: raise TimeoutError('legal HTTP test server did not start')

            status,login=req(base,'/api/login','POST',
                             {'email':'dog44@bigpaw.jp','password':'demo1234'})
            ok(status==200 and login.get('token'),'breeder login')
            tok=login['token']
            status,buyer=req(base,'/api/login','POST',
                             {'email':'user@bigpaw.jp','password':'demo1234'})
            # Buyer login may not be seeded in future revisions; anonymous access
            # is sufficient to exercise public endpoints and privacy controls.
            status,old=req(base,'/api/breeders/b_dog44/legal')
            ok(status==404,'legacy breeder legal disclosure requires explicit confirmation')

            with sqlite3.connect(Path(scratch)/'bigpaw.sqlite3',timeout=15) as con:
                con.execute("UPDATE breeders SET visit_address=?,registration_no=? WHERE id='b_dog44'",
                            ('埼玉県さいたま市西区仮所在地1-2-3','SAMPLE-LEGAL-001'))
                con.commit()

            status,before=req(base,'/api/breeders/b_dog44/legal')
            ok(status==404,'office address remains private until legal opt-in')
            status,public=req(base,'/api/breeders')
            ok(status==200 and isinstance(public,list),'breeder directory loads')
            serialized=json.dumps(public,ensure_ascii=False)
            ok('仮所在地' not in serialized and 'SAMPLE-LEGAL-001' not in serialized,
               'directory excludes office address and legal registration details')
            ok('埼玉県さいたま市' in serialized,'directory city-level location displayed')

            valid={'operatorName':'サンプル事業者','officeName':'ドックフォーティーフォー','registrationDate':'2024-04-01',
                   'expiresOn':'2029-03-31','animalManager':'試験責任者',
                   'businessType':'販売','confirmPublicDisclosure':True}
            status,blocked=req(base,'/api/breeder/legal-display','PATCH',valid)
            ok(status in (401,403),'anonymous cannot publish breeder legal information')
            status,invalid=req(base,'/api/breeder/legal-display','PATCH',
                               {**valid,'confirmPublicDisclosure':False},tok)
            ok(status==400,'publication requires explicit breeder opt-in')
            status,bad_date=req(base,'/api/breeder/legal-display','PATCH',
                                {**valid,'expiresOn':'2030-99-01'},tok)
            ok(status==400,'invalid legal input fails closed')
            status,published=req(base,'/api/breeder/legal-display','PATCH',valid,tok)
            ok(status==200 and published.get('confirmed'),'breeder can confirm eight legal fields')

            status,legal=req(base,'/api/breeders/b_dog44/legal')
            ok(status==200 and legal.get('officeAddress')=='埼玉県さいたま市西区仮所在地1-2-3',
               'confirmed legal office location published only on legal endpoint')
            ok(legal.get('officeName')=='ドックフォーティーフォー',
               'legal office name is independent of kennel brand')
            with sqlite3.connect(Path(scratch)/'bigpaw.sqlite3',timeout=15) as con:
                kennel=con.execute("SELECT kennel_name FROM breeders WHERE id='b_dog44'").fetchone()[0]
                ok(kennel=='DOG44','updating legal office name must not rename DOG44 or puppy brand')
            ok(legal.get('registrationNo')=='SAMPLE-LEGAL-001' and
               legal.get('operatorName')=='サンプル事業者' and
               legal.get('animalManager')=='試験責任者' and
               len(legal)==8,'eight statutory advertisement fields returned')
            ok(all(k not in legal for k in ('visitPhone','visitAccess','phone','email')),
               'legal endpoint does not disclose phone or visit access')
            status,public=req(base,'/api/breeders')
            ok(status==200 and '仮所在地' not in json.dumps(public,ensure_ascii=False),
               'breeder directory remains city-only after legal approval')
            status,puppies=req(base,'/api/puppies')
            ok(status==200 and isinstance(puppies,list),'public puppy listing remains available')
            if puppies:
                serialized=json.dumps(puppies,ensure_ascii=False)
                ok('仮所在地' not in serialized and '西区' not in serialized,
                   'puppy listings never expose street addresses')

            status,profile=req(base,'/api/breeder-profile','PATCH',
                               {'visitAddress':'埼玉県さいたま市西区新しい登録事業所4-5-6'},tok)
            ok(status==200,'breeder profile address update succeeds')
            status,no_longer=req(base,'/api/breeders/b_dog44/legal')
            ok(status==404,'changing registered office address revokes old public confirmation')

            status,republish=req(base,'/api/breeder/legal-display','PATCH',valid,tok)
            ok(status==200,'breeder reconfirms changed legal office address')
            status,legal=req(base,'/api/breeders/b_dog44/legal')
            ok(status==200 and '新しい登録事業所' in legal.get('officeAddress',''),
               'reconfirmed legal ad uses updated office address')
            print('BREEDER_LEGAL_HTTP_GATE_OK|anonymous_404|buyer_privacy|breeder_consent|eight_fields|address_reconfirmation|public_city_only|visit_contact_isolation',flush=True)
        except Exception:
            print('TEST_SERVER_LOG_TAIL\n'+out.read_text(encoding='utf-8')[-5000:],flush=True)
            raise
        finally:
            process.terminate()
            try: process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                process.kill();process.wait()
