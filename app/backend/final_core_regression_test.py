#!/usr/bin/env python3
"""Regression of current final BIG PAW server paths on a disposable database."""
import base64,json,os,socket,sqlite3,subprocess,sys,tempfile,time,uuid
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError

APP=Path(__file__).resolve().parents[1]

def check(v,name):
    if not v: raise AssertionError(name)
    print('PASS',name,flush=True)

def free_port():
    with socket.socket() as s:
        s.bind(('127.0.0.1',0)); return s.getsockname()[1]

def main():
    work=Path(tempfile.mkdtemp(prefix='bigpaw-final-core-')); data=work/'data'; data.mkdir()
    port=free_port(); base=f'http://127.0.0.1:{port}'
    env={k:v for k,v in os.environ.items() if not k.startswith(('BIGPAW_','SMTP_','RESEND_'))}
    env.update(PORT=str(port),BIGPAW_ENV='development',BIGPAW_DATA_DIR=str(data),
               BIGPAW_PUBLIC_BASE_URL=base,BIGPAW_DEV_LINKS='0',
               BIGPAW_AUTOMATION_INTERVAL_SECONDS='86400')
    log=open(work/'server.log','w')
    proc=subprocess.Popen([sys.executable,str(APP/'backend/server.py')],cwd=APP,env=env,stdout=log,stderr=log)
    def call(method,path,body=None,user=None,expected=200):
        headers={'Accept':'application/json','Origin':'https://bigpaw.site'}
        if user: headers['Cookie']='bigpaw_session=test-'+user
        raw=None
        if body is not None:
            raw=json.dumps(body,ensure_ascii=False).encode(); headers['Content-Type']='application/json'
        req=Request(base+path,data=raw,method=method,headers=headers)
        try:
            with urlopen(req,timeout=10) as out: code=out.status; blob=out.read()
        except HTTPError as e: code=e.code; blob=e.read()
        check(code==expected,f'{method} {path} -> {expected} (got {code}: {blob.decode(errors="replace")[:200]})')
        return json.loads(blob or b'{}')
    def upload(pid):
        png=base64.b64decode('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9ZQmcAAAAASUVORK5CYII=')
        boundary='----bp'+uuid.uuid4().hex
        body=(f'--{boundary}\r\nContent-Disposition: form-data; name="puppyId"\r\n\r\n{pid}\r\n'
              f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="core.png"\r\nContent-Type: image/png\r\n\r\n').encode()+png+f'\r\n--{boundary}--\r\n'.encode()
        req=Request(base+'/api/uploads',data=body,method='POST',headers={
            'Cookie':'bigpaw_session=test-u_dog44','Origin':'https://bigpaw.site',
            'Content-Type':'multipart/form-data; boundary='+boundary,'Content-Length':str(len(body))})
        try:
            with urlopen(req,timeout=10) as out: code=out.status; blob=out.read()
        except HTTPError as e: code=e.code; blob=e.read()
        check(code==201,f'photo upload -> 201 (got {code}: {blob.decode(errors="replace")[:200]})')
        return json.loads(blob)
    try:
        for _ in range(120):
            if proc.poll() is not None: raise AssertionError('server stopped')
            try:
                with urlopen(base+'/api/health',timeout=1) as r:
                    if r.status==200: break
            except Exception: time.sleep(.1)
        else: raise AssertionError('health timeout')
        db=data/'bigpaw.sqlite3'
        con=sqlite3.connect(db)
        expiry=int(time.time())+86400
        for uid in ('u_demo','u_dog44','u_admin'):
            con.execute('INSERT OR REPLACE INTO sessions VALUES(?,?,?,?)',('test-'+uid,uid,int(time.time()),expiry))
        con.commit(); con.close()

        public=call('GET','/api/puppies')
        check(any(p['id']=='p1' for p in public),'existing public puppy')
        created=call('POST','/api/puppies',{
            'breed':'スタンダードプードル','breedKey':'standard-poodle','gender':'男の子',
            'genderKey':'male','color':'回帰ブラック','price':321000,'area':'埼玉県',
            'areaKey':'saitama','name':'最終回帰犬','desc':'通常掲載の回帰確認','health':True
        },user='u_dog44',expected=201)
        pid=created['id']
        check(created.get('reviewStatus')=='approved','approved breeder conventional create stays public')
        check(call('GET','/api/puppies/'+pid)['id']==pid,'new puppy public detail')

        up=upload(pid); check(up.get('url','').startswith('/uploads/'),'existing photo upload')
        edited=call('PATCH','/api/puppies/'+pid,{'imageUrl':up['url'],'price':322000},user='u_dog44')
        check(edited.get('imageUrl')==up['url'] and int(edited.get('price'))==322000,'existing edit and main photo')
        photos=call('GET','/api/puppies/'+pid+'/photos',user='u_dog44')
        check(any(x.get('url')==up['url'] for x in photos),'photo metadata')
        search=call('GET','/api/puppies?breed=standard-poodle&area=saitama')
        check(any(x['id']==pid for x in search),'breed and area search')

        check(call('POST','/api/favorites/'+pid,{},user='u_demo')['favorite'] is True,'favorite add')
        check(any(x['id']==pid for x in call('GET','/api/favorites',user='u_demo')),'favorite list')
        inquiry=call('POST','/api/inquiries',{'puppyId':pid,'message':'通常問い合わせ回帰'},user='u_demo',expected=201)
        qid=inquiry['id']
        check(any(x['id']==qid for x in call('GET','/api/inquiries',user='u_dog44')),'breeder inquiry received')

        deal=call('POST','/api/inquiries/'+qid+'/deal',{},user='u_demo',expected=201); did=deal['id']
        check(deal['puppy_id']==pid,'deal linked')
        pay=call('POST','/api/deals/'+did+'/reservation',{'amount':100000},user='u_demo',expected=201)
        check(pay['status']=='paid','reservation payment development path')
        visit=call('POST','/api/inquiries/'+qid+'/visit',{'date':'2026-11-10','time':'13:00','status':'confirmed','partySize':2},user='u_dog44',expected=201)
        check(visit.get('status')=='confirmed','breeder confirms visit before contract')
        c1=call('POST','/api/deals/'+did+'/contract-sign',{'signerName':'BIG PAW 試験ブリーダー','faceToFaceConfirmed':True},user='u_dog44',expected=201)
        check(c1.get('breeder_signed_at') and c1.get('breeder_signer_name'),'breeder face-to-face contract sign')
        c2=call('POST','/api/deals/'+did+'/contract-sign',{'signerName':'山田 太郎'},user='u_demo',expected=201)
        check(c2.get('buyer_signed_at') and c2.get('status')=='signed','buyer contract sign completes contract')
        pickup=call('POST','/api/deals/'+did+'/pickup',{'date':'2026-11-15','time':'14:00','status':'scheduled'},user='u_demo',expected=201)
        check(pickup.get('pickup_date')=='2026-11-15','pickup scheduling')
        billing=call('GET','/api/breeder/billing-config',user='u_dog44')
        check(int(billing.get('commissionRateBps',0))>0,'billing config')
        check(isinstance(call('GET','/api/operator/stats',user='u_admin'),dict),'operator stats')
        check(call('POST','/api/favorites/'+pid,{},user='u_demo')['favorite'] is False,'favorite remove')
        print('FINAL_CORE_REGRESSION_OK|listing|photo|search|favorite|inquiry|deal|reservation|contract|pickup|billing|operator',flush=True)
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill(); proc.wait(timeout=5)
        log.close()

if __name__=='__main__':
    main()
