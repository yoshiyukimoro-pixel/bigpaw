#!/usr/bin/env python3
"""HTTP integration tests against an isolated, fully built app and disposable data.
Email provider is captured locally; no customer emails are sent.
"""
import concurrent.futures, json, os, socket, sqlite3, subprocess, sys, tempfile, time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from datetime import datetime,timezone,timedelta

app=Path(sys.argv[1]).resolve(); repo=Path(__file__).resolve().parents[2]
work=Path(tempfile.mkdtemp(prefix='bigpaw-fee-test-')); data=work/'data'; data.mkdir()
with socket.socket() as sock: sock.bind(('127.0.0.1',0)); port=sock.getsockname()[1]
base=f'http://127.0.0.1:{port}'
# The capture transport is injected ONLY into a scratch copy, never repository files.
server=app/'backend/server.py'; raw=server.read_text()
hook="""def _capture_test_mail(to_email, subject, text):
    import json
    with open(os.environ['BIGPAW_TEST_MAIL_CAPTURE'], 'a') as f:
        f.write(json.dumps({'to':to_email,'subject':subject,'text':text},ensure_ascii=False)+'\\n')
    return True
send_mail = _capture_test_mail
"""
marker='from first_sale_workflow import install as _install_first_sale_workflow'
assert marker in raw; server.write_text(raw.replace(marker,hook+'\n'+marker))
env=os.environ.copy(); env.update(PORT=str(port),BIGPAW_DATA_DIR=str(data),BIGPAW_ENV='development',BIGPAW_TEST_MAIL_CAPTURE=str(work/'mail.jsonl'),BIGPAW_PUBLIC_BASE_URL=base,BIGPAW_AUTOMATION_INTERVAL_SECONDS='3600')
for key in ('RESEND_API_KEY','SMTP_HOST','SMTP_PASSWORD','BIGPAW_SMTP_PASSWORD'): env.pop(key,None)
log=open(work/'server.log','w'); process=subprocess.Popen([sys.executable,str(server)],cwd=app,env=env,stdout=log,stderr=log)
conn=lambda:sqlite3.connect(data/'bigpaw.sqlite3',timeout=20)
def query(sql,params=()):
    c=conn();c.row_factory=sqlite3.Row
    try:return [dict(r) for r in c.execute(sql,params).fetchall()]
    finally:c.close()
def execute(sql,params=()):
    with conn() as c:c.execute(sql,params)
def request(method,path,body=None,user=None,origin=True):
    headers={'Content-Type':'application/json'}
    if user:headers['Cookie']='bigpaw_session=test-'+user
    if origin:headers['Origin']='https://bigpaw.site'
    r=Request(base+path,data=None if body is None else json.dumps(body).encode(),method=method,headers=headers)
    try:
        with urlopen(r,timeout=10) as out:
            blob=out.read();return out.status,json.loads(blob or b'{}')
    except HTTPError as e:return e.code,json.loads(e.read() or b'{}')
def check(cond,name):
    if not cond:raise AssertionError(name)
    print('PASS',name,flush=True)
def post(path,body,user='u_dog44',code=200):
    status,res=request('POST',path,body,user);check(status==code,f'{path}: HTTP {code} (got {status}, {res})');return res
TODAY=datetime.now(timezone(timedelta(hours=9))).date().isoformat()
def deal(tag,breeder='b_dog44',buyer='u_demo'):
    pid='wf-p-'+tag; iid='wf-i-'+tag;did='wf-d-'+tag
    execute("INSERT INTO puppies(id,breeder_id,name,breed,breed_key,gender,gender_key,color,price,status,area,area_key,created_at,review_status) VALUES(?,?,?,'スタンダードプードル','standard','男の子','male','ブラック',300000,'募集中','埼玉県','saitama',?,'approved')",(pid,breeder,'試験'+tag,int(time.time())))
    execute("INSERT INTO inquiries(id,puppy_id,buyer_id,breeder_id,name,email,created_at) VALUES(?,?,?,?,?,?,?)",(iid,pid,buyer,breeder,'試験購入者',buyer+'@example.invalid',int(time.time())))
    execute('INSERT INTO deals VALUES(?,?,?,?,?,?,?,?,?)',(did,iid,pid,buyer,breeder,300000,100000,'negotiating',int(time.time())))
    return did,pid
BODY={'finalSaleAmount':300000,'pickupDate':TODAY,'buyerName':'試験購入者','agreeFirstSaleTerms':True,'agreeAccurateReporting':True}
def confirmation(did,kind):return query("SELECT * FROM sale_confirmations WHERE deal_id=? AND kind=? AND state='pending'",(did,kind))[0]
def answer(did,kind,value='yes',user='u_demo'):
    sc=confirmation(did,kind)
    return post('/api/buyer/sale-confirmations/answer',{'id':sc['id'],'answer':value},user)
try:
    for _ in range(100):
        try:
            if request('GET','/api/health')[0]==200:break
        except Exception:time.sleep(.1)
    else:raise RuntimeError('server startup failed: '+(work/'server.log').read_text()[-3000:])
    if os.environ.get('BIGPAW_TEST_AGENT_BROWSER'):
        cli=['node',os.environ['BIGPAW_TEST_AGENT_BROWSER'],'--session','bigpaw-first-sale-test','--executable-path',os.environ['BIGPAW_TEST_CHROMIUM_PATH'],'--args','--no-sandbox,--disable-dev-shm-usage']
        try:
            for args in (['open',base],['snapshot','-i'],['screenshot',str(work/'homepage.png')],['eval',"document.body.innerText.trim().length>100?'HAS_CONTENT':'BLANK'"]):
                subprocess.run(cli+args,check=True,timeout=40)
        finally: subprocess.run(cli+['close'],timeout=15)
    for uid in ('u_demo','u_dog44','u_admin'):
        execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-'+uid,uid,int(time.time()),int(time.time())+86400))
    # Production mode, cookie+CSRF checks and schema migration on a populated DB.
    process.terminate();process.wait(timeout=5)
    env.update(BIGPAW_ENV='production',BIGPAW_ADMIN_EMAIL='admin@example.invalid',BIGPAW_ADMIN_PASSWORD='ProductionTestOnly123!',BIGPAW_DEV_LINKS='0')
    process=subprocess.Popen([sys.executable,str(server)],cwd=app,env=env,stdout=log,stderr=log)
    for _ in range(100):
        try:
            if request('GET','/api/health')[0]==200:break
        except Exception:time.sleep(.1)
    else:raise RuntimeError('production restart failed')
    first,pid=deal('first')
    check(request('POST','/api/deals/'+first+'/sale-report',BODY,'u_dog44',False)[0]==403,'production CSRF rejects missing origin')
    check(request('POST','/api/deals/'+first+'/sale-report',BODY,'u_demo')[0]==403,'buyer cannot claim breeder benefit')
    b=dict(BODY);b.pop('agreeFirstSaleTerms');post('/api/deals/'+first+'/sale-report',b,code=400)
    no_consent=dict(BODY);no_consent.pop('agreeAccurateReporting');post('/api/deals/'+first+'/sale-report',no_consent,code=400)
    check(not query('SELECT * FROM first_sale_benefits'),'missing consent never consumes benefit')
    res=post('/api/deals/'+first+'/sale-report',BODY);check(res['waived'],'first application is free')
    post('/api/deals/'+first+'/sale-report',BODY);check(len(query('SELECT * FROM sale_confirmations WHERE deal_id=?',(first,)))==1,'duplicate application sends one confirmation')
    sc=confirmation(first,'sale')
    check(request('POST','/api/buyer/sale-confirmations/answer',{'id':sc['id'],'answer':'yes'},'u_dog44')[0]==403,'breeder cannot answer buyer confirmation')
    answer(first,'sale')
    post('/api/deals/'+first+'/completion-report',BODY);answer(first,'pickup')
    check(query('SELECT status FROM deals WHERE id=?',(first,))[0]['status']=='completed','breeder pickup report completes deal automatically')
    check(not query('SELECT * FROM commission_invoices WHERE deal_id=?',(first,)),'first completion creates no invoice')
    second,pid2=deal('second');post('/api/deals/'+second+'/sale-report',BODY);answer(second,'sale');post('/api/deals/'+second+'/completion-report',BODY)
    check(len(query('SELECT * FROM commission_invoices WHERE deal_id=?',(second,)))==1,'invoice issued immediately without buyer response')
    post('/api/deals/'+second+'/completion-report',BODY)
    check(len(query('SELECT * FROM commission_invoices WHERE deal_id=?',(second,)))==1,'duplicate pickup report creates exactly one invoice')
    sc=confirmation(second,'pickup');answer(second,'pickup')
    inv=query('SELECT * FROM commission_invoices WHERE deal_id=?',(second,));check(len(inv)==1 and inv[0]['fee_amount']==15000 and inv[0]['due_at']-inv[0]['issued_at']==7*86400,'second completion bills exactly 5% with seven-day deadline')
    post('/api/buyer/sale-confirmations/answer',{'id':sc['id'],'answer':'yes'},'u_demo');check(len(query('SELECT * FROM commission_invoices WHERE deal_id=?',(second,)))==1,'duplicate buyer answer never duplicates invoice')
    check(query('SELECT * FROM sale_report_consents WHERE deal_id=?',(second,))[0]['user_id']=='u_dog44','consent records actor, text, version and timestamp')
    denied,_=deal('pickup-denied');post('/api/deals/'+denied+'/sale-report',BODY);post('/api/deals/'+denied+'/completion-report',BODY)
    answer(denied,'pickup','no')
    check(query('SELECT status FROM commission_invoices WHERE deal_id=?',(denied,))[0]['status']=='review_hold','buyer denial holds invoiced fee')
    execute('UPDATE commission_invoices SET due_at=1 WHERE deal_id=?',(denied,))
    request('GET','/api/puppies')
    check(query("SELECT billing_suspended FROM breeders WHERE id='b_dog44'")[0]['billing_suspended']==0,'held overdue invoice cannot suspend listing')
    held=query('SELECT id FROM commission_invoices WHERE deal_id=?',(denied,))[0]['id']
    check(request('PATCH','/api/operator/invoices/'+held,{'action':'remind'},'u_admin')[0]==409,'manual reminders blocked while review held')
    ds=query('SELECT id FROM sale_disputes WHERE deal_id=?',(denied,))[0]['id']
    check(request('PATCH','/api/operator/sale-disputes/'+ds,{'action':'confirmed_cancelled','note':'双方にキャンセルを確認'},'u_admin')[0]==200,'operator cancels invoice after factual review')
    check(query('SELECT status FROM commission_invoices WHERE deal_id=?',(denied,))[0]['status']=='void','cancelled pickup invoice is void')
    resumed,_=deal('pickup-resume');post('/api/deals/'+resumed+'/sale-report',BODY);post('/api/deals/'+resumed+'/completion-report',BODY);answer(resumed,'pickup','no')
    rs=query('SELECT id FROM sale_disputes WHERE deal_id=?',(resumed,))[0]['id']
    check(request('PATCH','/api/operator/sale-disputes/'+rs,{'action':'confirmed_pickup','note':'実際のお迎え完了を双方に確認'},'u_admin')[0]==200,'operator resumes fee after confirming real pickup')
    ri=query('SELECT * FROM commission_invoices WHERE deal_id=?',(resumed,))[0]
    check(ri['status']=='issued' and abs(ri['due_at']-int(time.time())-7*86400)<5,'resumed invoice provides seven days to pay')
    # A second breeder demonstrates cancellation after consuming the first benefit.
    execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES('u_test_b2','breeder','b2@example.invalid','s','h',?)",(int(time.time()),))
    execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES('b_test2','u_test_b2','試験犬舎2','埼玉県','','','approved')")
    execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-u_test_b2','u_test_b2',int(time.time()),int(time.time())+86400))
    cancelled,cp=deal('cancel','b_test2');r=post('/api/deals/'+cancelled+'/sale-report',BODY,'u_test_b2');check(r['waived'],'new breeder independently receives one benefit')
    post('/api/deals/'+cancelled+'/cancel-report',{'note':'キャンセル','agreeAccurateReporting':True},'u_test_b2');answer(cancelled,'cancellation')
    check(not query('SELECT * FROM commission_invoices WHERE deal_id=?',(cancelled,)),'cancelled transaction is never invoiced')
    check(len(query('SELECT * FROM first_sale_benefits WHERE breeder_id=?',('b_test2',)))==1,'cancellation does not restore first benefit')
    post('/api/deals/'+cancelled+'/sale-report',BODY,'u_test_b2',409)
    nextd,np=deal('aftercancel','b_test2');r=post('/api/deals/'+nextd+'/sale-report',BODY,'u_test_b2');check(not r['waived'],'first benefit stays used after cancellation')
    # Superseded and expired confirmation cannot complete a changed report.
    old=confirmation(nextd,'sale'); changed=dict(BODY,finalSaleAmount=320000);post('/api/deals/'+nextd+'/sale-report',changed,'u_test_b2')
    post('/api/buyer/sale-confirmations/answer',{'id':old['id'],'answer':'yes'},'u_demo',409)
    live=confirmation(nextd,'sale');execute('UPDATE sale_confirmations SET expires_at=1 WHERE id=?',(live['id'],));post('/api/buyer/sale-confirmations/answer',{'id':live['id'],'answer':'yes'},'u_demo',409)
    # False cancellation is disputed, not auto-punished or billed.
    disputed,dp=deal('disputed');post('/api/deals/'+disputed+'/sale-report',BODY);post('/api/deals/'+disputed+'/cancel-report',{'note':'申告','agreeAccurateReporting':True})
    answer(disputed,'cancellation','no');check(not query('SELECT * FROM commission_invoices WHERE deal_id=?',(disputed,)),'disputed cancellation is not billed')
    dispute=query('SELECT * FROM sale_disputes WHERE deal_id=?',(disputed,))[0]
    check(query("SELECT compliance_suspended FROM breeders WHERE id='b_dog44'")[0]['compliance_suspended']==0,'disagreement alone never suspends breeder')
    check(request('PATCH','/api/operator/sale-disputes/'+dispute['id'],{'action':'confirmed_false','note':'購入者と履歴を確認'},'u_dog44')[0]==403,'breeder cannot impose or remove suspension')
    code,_=request('PATCH','/api/operator/sale-disputes/'+dispute['id'],{'action':'confirmed_false','note':'購入者と履歴を確認'},'u_admin');check(code==200,'operator confirms false report and suspends')
    check(request('POST','/api/puppies',{'name':'掲載不可'},'u_dog44')[0]==403,'suspended breeder cannot create listing')
    check(request('PATCH','/api/puppies/'+dp,{'status':'募集中'},'u_dog44')[0]==403,'suspended breeder cannot republish listing')
    check(request('GET','/api/puppies/'+dp)[0]==404,'suspended listing is hidden from public detail')
    code,public=request('GET','/api/puppies');check(code==200 and all(p['id']!=dp for p in public),'suspended listings are hidden from search')
    code,msgres=request('POST','/api/inquiries/wf-i-disputed/messages',{'body':'運営確認中です'},'u_dog44');check(code==201,'suspended breeder can continue existing customer conversation')
    code,_=request('PATCH','/api/operator/breeders/b_dog44/compliance-resume',{'note':'解決を確認'},'u_admin');check(code==200,'only operator can resume compliance suspension')
    # Removal keeps consumed-benefit and transaction history.
    code,_=request('DELETE','/api/puppies/'+cp,{},'u_test_b2');check(code==200,'listing with deal is safely archived')
    check(query('SELECT * FROM deals WHERE id=?',(cancelled,)) and query('SELECT * FROM first_sale_benefits WHERE breeder_id=?',('b_test2',)),'archiving never deletes deal or benefit history')
    # Simultaneous first applications for a fresh breeder: one winner only.
    execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES('u_test_b3','breeder','b3@example.invalid','s','h',?)",(int(time.time()),))
    execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES('b_test3','u_test_b3','試験犬舎3','埼玉県','','','approved')")
    execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-u_test_b3','u_test_b3',int(time.time()),int(time.time())+86400))
    d3a,_=deal('race-a','b_test3');d3b,_=deal('race-b','b_test3')
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        rs=list(pool.map(lambda d:request('POST','/api/deals/'+d+'/sale-report',BODY,'u_test_b3'),[d3a,d3b]))
    check(all(x[0]==200 for x in rs) and sum(x[1]['waived'] for x in rs)==1,'simultaneous applications allocate exactly one free transaction')
    # Cancellation monitoring covers paid transactions too and counts distinct deals, never retries.
    for suffix in ('monitor-a','monitor-b'):
        md,mp=deal(suffix,'b_test2');post('/api/deals/'+md+'/sale-report',BODY,'u_test_b2');post('/api/deals/'+md+'/cancel-report',{'agreeAccurateReporting':True},'u_test_b2')
        post('/api/deals/'+md+'/cancel-report',{'agreeAccurateReporting':True},'u_test_b2')
    alerts=query("SELECT * FROM cancellation_alerts WHERE breeder_id='b_test2' AND reason LIKE '30日%' ")
    check(len(alerts)==1 and len(query("SELECT * FROM cancellation_events WHERE breeder_id='b_test2'"))==3,'three distinct cancellations in 30 days trigger one alert; duplicate reports not counted')
    check(query("SELECT compliance_suspended FROM breeders WHERE id='b_test2'")[0]['compliance_suspended']==0,'cancellation count alone never suspends breeder')
    aid=alerts[0]['id']; endpoint='/api/operator/cancellation-alerts/'+aid
    check(request('PATCH',endpoint,{'action':'warn','note':'確認','message':'警告'},'u_dog44')[0]==403,'only operator can send cancellation warning')
    st,monitor=request('GET','/api/operator/sale-confirmations',user='u_admin');check(st==200 and any(a['id']==aid for a in monitor['alerts']),'operator can see cancellation alert and buyer answers')
    check(request('PATCH',endpoint,{'action':'warn','note':'購入者と履歴を確認','message':monitor['warningTemplate']},'u_admin')[0]==200,'operator sends reviewed warning message')
    check(request('PATCH',endpoint,{'action':'warn','note':'重複','message':'警告'},'u_admin')[0]==409,'warning retry never queues second message')
    check(len(query('SELECT * FROM cancellation_warnings WHERE alert_id=?',(aid,)))==1,'warning stores operator reason exact message and timestamp')
    md,mp=deal('monitor-after-warning','b_test2');post('/api/deals/'+md+'/sale-report',BODY,'u_test_b2');post('/api/deals/'+md+'/cancel-report',{'agreeAccurateReporting':True},'u_test_b2')
    recurrence=query("SELECT * FROM cancellation_alerts WHERE breeder_id='b_test2' AND reason='警告後に新たなキャンセル申告'")
    check(len(recurrence)==1,'new cancellation after warning triggers recurrence alert')
    check(query("SELECT compliance_suspended FROM breeders WHERE id='b_test2'")[0]['compliance_suspended']==0,'recurrence still requires operator decision')
    st,_=request('PATCH','/api/puppies/'+mp,{'status':'非公開'},'u_test_b2');check(st==200,'cancelled listing can be made private')
    check(query('SELECT * FROM cancellation_listing_history WHERE puppy_id=?',(mp,)),'cancelled listing nonpublic history retained')
    st,_=request('DELETE','/api/puppies/'+mp,{},'u_test_b2');check(st==200,'cancelled listing archive succeeds')
    check(len(query('SELECT * FROM cancellation_listing_history WHERE puppy_id=?',(mp,)))==2,'archive and nonpublic actions recorded separately')
    request('DELETE','/api/puppies/'+mp,{},'u_test_b2');check(len(query('SELECT * FROM cancellation_listing_history WHERE puppy_id=?',(mp,)))==2,'duplicate archive does not create repeated alert')
    check(request('PATCH','/api/operator/cancellation-alerts/'+recurrence[0]['id'],{'action':'suspend','note':'警告後の履歴と購入者の回答を確認'},'u_admin')[0]==200,'operator can suspend after reviewed recurrence')
    check(request('POST','/api/puppies',{'name':'不可'},'u_test_b2')[0]==403,'reviewed recurrence suspension blocks new listing')
    # Mail capture proves event links and content are queued and delivered once in the test transport.
    for _ in range(60):
        mail=query('SELECT * FROM sale_mail_outbox')
        if mail and all(m['sent_at'] for m in mail):break
        time.sleep(.05)
    captured=[json.loads(line) for line in (work/'mail.jsonl').read_text().splitlines()]
    check(any('/buyer-sale-confirmation.html?token=' in x['text'] for x in captured),'confirmation email contains answer page link')
    check(any('15,000' in x['text'] and '7日' in x['text'] for x in captured),'invoice email contains amount and deadline')
    check(any('キャンセル申告の確認が必要' in x['subject'] for x in captured),'operator alert email sent through local test transport')
    check(any('今後、虚偽申告や手数料回避' in x['text'] for x in captured),'reviewed breeder warning delivered through local test transport')
    check(any('0円' in x['text'] for x in captured),'free completion email states no invoice')
    check(all(m['sent_at'] for m in mail),'outbox delivers all test mails')
    # Existing functionality: registration/login, listing edits, photos/order, favorites, search, handover and operator APIs.
    uid='u_dog44'
    st,login=request('POST','/api/login',{'email':'dog44@bigpaw.jp','password':'demo1234'})
    check(st==200,'existing breeder password login')
    st,r=request('POST','/api/puppies',{'name':'回帰試験犬','breed':'スタンダードプードル','breedKey':'standard-poodle','gender':'男の子','color':'ブラック','price':300000,'area':'埼玉県','desc':'写真とお気に入りの試験'},uid)
    check(st==201,'existing puppy creation');rp=r['id']
    st,r=request('PATCH','/api/puppies/'+rp,{'price':310000,'desc':'紹介文\n改行の確認','appealPoint':'元気な男の子'},uid)
    check(st==200 and r['price']==310000,'existing puppy price/description editing')
    import io
    from PIL import Image
    photos=[]
    for color in ('red','blue'):
        buf=io.BytesIO();Image.new('RGB',(48,48),color).save(buf,format='PNG')
        boundary='BIGPAWTESTBOUNDARY'
        rawbody=(f'--{boundary}\r\nContent-Disposition: form-data; name="puppyId"\r\n\r\n{rp}\r\n--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="test-{color}.png"\r\nContent-Type: image/png\r\n\r\n').encode()+buf.getvalue()+f'\r\n--{boundary}--\r\n'.encode()
        req=Request(base+'/api/uploads',data=rawbody,method='POST',headers={'Cookie':'bigpaw_session=test-'+uid,'Origin':'https://bigpaw.site','Content-Type':'multipart/form-data; boundary='+boundary})
        with urlopen(req,timeout=10) as out:check(out.status==201,'existing photo upload '+color);photos.append(json.loads(out.read())['id'])
    st,r=request('PATCH','/api/puppies/'+rp+'/photos/order',{'ids':photos[::-1]},uid);check(st==200,'existing photo order persistence')
    st,r=request('GET','/api/puppies/'+rp);check(st==200 and len(r['photos'])==2 and '\n' in r['desc'],'existing public gallery keeps multiple photos and line breaks')
    st,r=request('POST','/api/favorites/'+rp,{},'u_demo');check(st==200 and r['favorite'],'existing favorite save')
    st,r=request('GET','/api/favorites',user='u_demo');check(st==200 and any(x['id']==rp for x in r),'existing favorites readback')
    st,r=request('GET','/api/puppies?breed=standard-poodle&area=saitama');check(st==200 and any(x['id']==rp for x in r),'existing breed and area search')
    st,r=request('GET','/api/operator/breeders',user='u_admin');check(st==200,'existing operator breeder management API')
    st,r=request('GET','/api/operator/invoices',user='u_admin');check(st==200,'existing operator invoice management API')
    st,r=request('POST','/api/breeder/sales-handover-settings',{'reservationAmount':100000,'minHandoverDays':57,'healthExamIncluded':True,'microchipIncluded':True},uid);check(st==200,'existing sales handover settings save')
    st,r=request('GET','/api/breeder/sales-handover-settings',user=uid);check(st==200 and r['reservationAmount']==100000,'existing sales handover settings readback')
    bd,bp=deal('browser');execute('UPDATE puppies SET name=? WHERE id=?',('ブラウザー試験犬',bp))
    # Save fixtures for browser tests against the still-running server.
    context={'base':base,'data':str(data),'work':str(work),'serverPid':process.pid,'port':port,'today':TODAY,'browserInquiry':'wf-i-browser','regressionPuppy':rp}
    context_path=Path(os.environ.get('BIGPAW_TEST_CONTEXT_PATH',str(repo/'test-context.json')))
    context_path.write_text(json.dumps(context))
    print('FIRST_SALE_HTTP_SUITE_OK',json.dumps(context),flush=True)
    if os.environ.get('BIGPAW_TEST_CHROMIUM_PATH'):
        subprocess.run(['node',str(repo/'scripts/test-first-sale-browser.cjs'),str(context_path)],check=True,timeout=120,env=env)
finally:
    server.write_text(raw)
    if process is not None:process.terminate();process.wait(timeout=5)
    log.close()
