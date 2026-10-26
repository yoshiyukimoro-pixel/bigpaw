"""HTTP integration regression for isolated planned litter workflow.

This script always creates a disposable database, never accesses production.
Run from /app (built container) or app/ directory with Python 3.13.
"""
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import secrets
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPCookieProcessor

BASE_DIR = Path(__file__).resolve().parents[1]


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def call(base, method, path, body=None, token=None, expected=200):
    req = Request(base+path, method=method)
    req.add_header('Accept', 'application/json')
    if token:
        req.add_header('Authorization', 'Bearer '+token)
    if body is not None:
        req.add_header('Content-Type','application/json')
        req.data = json.dumps(body, ensure_ascii=False).encode()
    try:
        from urllib.request import urlopen
        with urlopen(req, timeout=7) as response:
            code=response.status
            raw=response.read()
    except HTTPError as exc:
        code=exc.code
        raw=exc.read()
    check(code==expected, method+' '+path+': expected '+str(expected)+', got '+str(code)+': '+raw.decode(errors='replace')[:400])
    return json.loads(raw or b'{}')


def main():
    with tempfile.TemporaryDirectory(prefix='bigpaw-planned-litter-') as td:
        with socket.socket() as sock:
            sock.bind(('127.0.0.1',0))
            port=sock.getsockname()[1]
        base='http://127.0.0.1:'+str(port)
        env=dict(os.environ,PORT=str(port),BIGPAW_ENV='development',BIGPAW_DATA_DIR=td,
                 BIGPAW_PUBLIC_BASE_URL=base,BIGPAW_DEV_LINKS='0',
                 BIGPAW_AUTOMATION_INTERVAL_SECONDS='86400')
        proc=subprocess.Popen([sys.executable,str(BASE_DIR/'backend'/'server.py')],
                             cwd=str(BASE_DIR),env=env,stdout=subprocess.DEVNULL,
                             stderr=subprocess.STDOUT)
        try:
            for _ in range(120):
                if proc.poll() is not None:
                    raise AssertionError('server stopped during startup: '+str(proc.returncode))
                try:
                    if call(base,'GET','/api/health')['ok']:
                        break
                except (URLError,AssertionError,TimeoutError):
                    time.sleep(.25)
            else:
                raise AssertionError('server health timeout')
            print('server started; separate dev database')
            check(call(base,'GET','/api/planned-litters')==[],'new DB must not show planned litters')
            check(call(base,'GET','/api/puppies'),'existing puppies API must stay available')
            check(call(base,'GET','/api/planned-litters/mine',expected=401)['error']=='auth_required','auth on mine')
            check(call(base,'POST','/api/planned-litters',{},expected=401)['error']=='auth_required','auth on create')
            buyer=call(base,'POST','/api/login',{'email':'demo@bigpaw.jp','password':'demo1234'})['token']
            breeder=call(base,'POST','/api/login',{'email':'dog44@bigpaw.jp','password':'demo1234'})['token']
            operator=call(base,'POST','/api/login',{'email':'admin@bigpaw.jp','password':'admin1234'})['token']
            check(bool(buyer and breeder and operator),'demo authentication')
            valid={'breed':'スタンダードプードル','breedKey':'standard-poodle',
                   'title':'2027年春 出産予定・予約希望受付中','phase':'交配予定',
                   'plannedMating':'2027-01-10','expectedBirth':'2027-03-10',
                   'description':'父犬・母犬の情報や出産予定について事前相談を受け付けています。',
                   'status':'受付中'}
            check(call(base,'POST','/api/planned-litters',valid,buyer,403)['error']=='forbidden','buyer cannot create')
            invalid=dict(valid,description='LINE: abc123')
            check(call(base,'POST','/api/planned-litters',invalid,breeder,400)['error']=='direct_contact_not_allowed','public contact blocked')
            check(call(base,'POST','/api/planned-litters',dict(valid,plannedMating='tomorrow'),breeder,400)['error']=='invalid_date','invalid date')
            item=call(base,'POST','/api/planned-litters',valid,breeder,201)
            lid=item['id']
            check(item['breeder_id']=='b_dog44','correct kennel')
            check(len(call(base,'GET','/api/planned-litters'))==1,'public list exposes approved item')
            check(len(call(base,'GET','/api/planned-litters/mine',token=breeder))==1,'owner can see own items')
            check(call(base,'GET','/api/planned-litters/mine',token=operator,expected=403)['error']=='approved_breeder_required','operator must pick kennel')
            check(len(call(base,'GET','/api/planned-litters/mine?breederId=b_dog44',token=operator))==1,'operator selected kennel')
            check(call(base,'GET','/api/planned-litters/'+lid)['id']==lid,'public detail')
            check(call(base,'POST','/api/planned-litters/'+lid+'/inquiries',{'message':'ぜひ予約したいと思います。','preferredGender':'どちらでも'},expected=401)['error']=='auth_required','public inquiry auth')
            check(call(base,'POST','/api/planned-litters/'+lid+'/inquiries',{'message':'ぜひ予約したいと思います。'},token=breeder,expected=403)['error']=='forbidden','breeder cannot send buyer interest')
            inquiry=call(base,'POST','/api/planned-litters/'+lid+'/inquiries',
                         {'message':'まだ子犬が生まれる前ですが、お迎えを希望しているので詳細を教えてください。','preferredGender':'女の子'},buyer,201)
            check(inquiry['status']=='新着','inquiry status')
            check(call(base,'POST','/api/planned-litters/'+lid+'/inquiries',
                       {'message':'重複問い合わせテストの文章です。'},buyer,429)['error']=='recent_inquiry_exists','duplicate throttle')
            check(call(base,'GET','/api/planned-litters/inquiries',token=buyer,expected=403)['error']=='forbidden','buyer cannot read buyer PII')
            own=call(base,'GET','/api/planned-litters/inquiries',token=breeder)
            check(len(own)==1 and own[0]['preferred_gender']=='女の子','breeder receives correct inquiry')
            check(call(base,'PATCH','/api/planned-litters/inquiries/'+inquiry['id'],{'status':'仮予約希望'},buyer,403)['error']=='forbidden','buyer cannot change inquiry status')
            check(call(base,'PATCH','/api/planned-litters/inquiries/'+inquiry['id'],{'status':'仮予約希望'},breeder)['status']=='仮予約希望','breeder manages interest status')
            check(call(base,'PATCH','/api/planned-litters/'+lid,{'status':'非公開'},breeder)['status']=='非公開','private status update')
            check(call(base,'GET','/api/planned-litters')==[],'private hidden from public')
            check(call(base,'GET','/api/planned-litters/'+lid,expected=404)['error']=='not_found','private detail hidden')
            check(call(base,'POST','/api/planned-litters/'+lid+'/inquiries',{'message':'新規に相談したいと考えています。'},buyer,409)['error']=='not_accepting_inquiries','private inquiry disabled')
            check(call(base,'PATCH','/api/planned-litters/'+lid,{'status':'受付中'},breeder)['status']=='受付中','resume publication')
            check(len(call(base,'GET','/api/planned-litters'))==1,'public returns on resume')
            check(call(base,'PATCH','/api/planned-litters/'+lid,{'status':'終了'},operator)['status']=='終了','operator closes item')
            check(call(base,'GET','/api/planned-litters')==[],'completed hidden')
            # A second approved kennel may neither edit nor read first kennel private requests.
            con=sqlite3.connect(str(Path(td)/'bigpaw.sqlite3'))
            pw='separate-test-pass-1234'; salt=secrets.token_hex(16)
            digest=hashlib.pbkdf2_hmac('sha256',pw.encode(),salt.encode(),180000).hex()
            con.execute("INSERT INTO users (id,role,email,last,first,display_name,salt,password_hash,created_at) VALUES (?,?,?,?,?,?,?,?,?)",
                        ('u_other','breeder','other-test@bigpaw.jp','他犬舎','担当','他犬舎',salt,digest,int(time.time())))
            con.execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES (?,?,?,?,?,?,?)",
                        ('b_other','u_other','他の犬舎','東京都','','','approved'))
            con.commit()
            before=con.execute('SELECT COUNT(*) FROM deals').fetchone()[0]
            before_pay=con.execute('SELECT COUNT(*) FROM payments').fetchone()[0]
            after_regular=con.execute('SELECT COUNT(*) FROM puppies').fetchone()[0]
            con.close()
            other=call(base,'POST','/api/login',{'email':'other-test@bigpaw.jp','password':pw})['token']
            check(call(base,'GET','/api/planned-litters/inquiries',token=other)==[],'cross-kennel private inquiries hidden')
            check(call(base,'GET','/api/planned-litters/mine',token=other)==[],'cross-kennel planned listings hidden')
            check(call(base,'PATCH','/api/planned-litters/'+lid,{'status':'受付中'},other,403)['error']=='forbidden','cross-kennel edit rejected')
            check(call(base,'PATCH','/api/planned-litters/inquiries/'+inquiry['id'],{'status':'相談中'},other,403)['error']=='forbidden','cross-kennel request update rejected')
            check(call(base,'POST','/api/planned-litters',dict(valid,breederId='b_dog44'),other,201)['breeder_id']=='b_other','breeder cannot spoof breederId')
            # Suspending own kennel must also remove planned litter from public API.
            con=sqlite3.connect(str(Path(td)/'bigpaw.sqlite3'))
            con.execute("UPDATE breeders SET billing_suspended=1 WHERE id='b_other'")
            con.commit()
            con.close()
            check(not any(x['breeder_id']=='b_other' for x in call(base,'GET','/api/planned-litters')),'suspended kennel hidden')
            con=sqlite3.connect(str(Path(td)/'bigpaw.sqlite3'))
            check(con.execute('SELECT COUNT(*) FROM deals').fetchone()[0]==before,'planned interest never created deals')
            check(con.execute('SELECT COUNT(*) FROM payments').fetchone()[0]==before_pay,'planned interest never created payments')
            check(con.execute('SELECT COUNT(*) FROM puppies').fetchone()[0]==after_regular,'planned interest never created individual puppies')
            con.close()
            print('PLANNED_LITTER_HTTP_INTEGRATION_OK: ownership, privacy, statuses, interest, no payments/deals, existing puppy list')
        finally:
            proc.terminate()
            try: proc.wait(timeout=5)
            except subprocess.TimeoutExpired: proc.kill();proc.wait(timeout=5)


if __name__=='__main__':
    main()
