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
    # REAL API E2E IN A PRIVATE SCRATCH DB: promotional puppy, first site-wide slot,
    # buyer sale/pickup confirmation and breeder-facing 3% invoice with a 7-day due date.
    start=request('GET','/api/campaign/first100')[1]
    check(start['status']=='active' and start['remaining']==100,
          'launch quota has all 100 slots before first promoted puppy')
    od,op=deal('oshicampaign-first')
    st,selection=request('POST','/api/oshiwan/'+op+'/selection',
                         {'enabled':True,'agreeOshiwanTerms':True},'u_dog44')
    check(st==200,'breeder explicitly opts in first campaign puppy to Oshiwan')
    # Inquiry must occur while 推しワン is selected; neither previous nor future inquiries
    # are silently retrofitted with the optional 3% charge.
    execute('UPDATE inquiries SET created_at=? WHERE id=?',(int(time.time()),'wf-i-oshicampaign-first'))
    claim=post('/api/deals/'+od+'/sale-report',BODY)
    check(claim['waived'] is True and claim['campaignWaived'] is True,
          'first Oshiwan contract qualifies for waived BASE 5 percent')
    frozen=query('SELECT waived,rate_bps FROM sale_fee_decisions WHERE deal_id=?',(od,))[0]
    check(frozen['waived']==1 and frozen['rate_bps']==800,
          'campaign claim freezes standard 5% plus Oshiwan 3%, waiving only the base')
    post('/api/deals/'+od+'/sale-report',BODY)
    remaining=request('GET','/api/campaign/first100')[1]
    check(remaining['remaining']==99 and len(query('SELECT deal_id FROM first100_campaign_claims'))==1,
          'repeat Oshiwan contract uses exactly one campaign slot, 100 down to 99')
    answer(od,'sale')
    post('/api/deals/'+od+'/completion-report',BODY)
    invoice_rows=query('SELECT * FROM commission_invoices WHERE deal_id=?',(od,))
    check(len(invoice_rows)==1 and invoice_rows[0]['rate_bps']==300
          and invoice_rows[0]['fee_amount']==9000 and invoice_rows[0]['status']=='issued',
          'Oshiwan during free-base campaign creates EXACTLY ONE 3% invoice: 9000 yen on 300000 yen')
    check(invoice_rows[0]['due_at']-invoice_rows[0]['issued_at']==7*86400,
          'Oshiwan campaign invoice payment deadline is exactly seven days after issue')
    check('先着100頭' in invoice_rows[0]['note'] and '推しワン' in invoice_rows[0]['note'],
          'invoice explicitly identifies campaign waiver and paid 3-percent promotion')
    billing_status,billing=request('GET','/api/breeder/invoices',user='u_dog44')
    check(billing_status==200 and any(v['deal_id']==od and v['fee_amount']==9000
          and v['due_at']==invoice_rows[0]['due_at'] for v in billing),
          'same live API used by breeder billing page shows actual 3% invoice and due date')
    config_status,config=request('GET','/api/breeder/billing-config',user='u_dog44')
    check(config_status==200 and config['commissionDueDays']==7,
          'billing and invoice page configuration advertises 7-day deadline')
    answer(od,'pickup')
    post('/api/deals/'+od+'/completion-report',BODY)
    check(len(query('SELECT * FROM commission_invoices WHERE deal_id=?',(od,)))==1,
          'duplicate pickup and buyer confirmations cannot issue a second 3-percent invoice')
    check(request('GET','/api/campaign/first100')[1]['remaining']==99,
          'pickup and invoice issuing do not consume extra campaign slots')
    print('OSHIWAN_CAMPAIGN_3PCT_7DAY_INVOICE_E2E_OK|first_slot_100_to_99|300000_yen_to_9000_yen|buyer_confirmed|invoice_shown_to_breeder|due_7_days|no_duplicate',flush=True)
    execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES('u_test_policy','breeder','policy@example.invalid','s','h',?)",(int(time.time()),))
    execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES('b_test_policy','u_test_policy','規約同意試験犬舎','埼玉県','','','approved')")
    execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-u_test_policy','u_test_policy',int(time.time()),int(time.time())+86400))
    legacy_policy_deal,_=deal('policy-before-consent','b_test_policy')
    check(request('GET','/api/breeder/deal-policy-consent',user='u_test_policy')[1]['accepted'] is False,'existing breeder starts without inferred policy consent')
    check(request('POST','/api/breeder/deal-policy-consent',{'accepted':True,'version':'wrong-version'},'u_test_policy')[0]==400,'stale policy version cannot be accepted')
    legacy_alternate=dict(BODY,soldAnimalType='adult',soldAnimalName='既存接点の成犬')
    check(request('POST','/api/deals/'+legacy_policy_deal+'/sale-report',legacy_alternate,'u_test_policy')[0]==409,'new scope cannot apply to a pre-consent inquiry')
    spoofed_original=dict(BODY,soldAnimalType='original',soldAnimalName='別の犬')
    check(request('POST','/api/deals/'+legacy_policy_deal+'/sale-report',spoofed_original,'u_test_policy')[0]==400,'original-puppy selection cannot bypass expanded-scope consent')
    check(not query('SELECT * FROM first_sale_benefits WHERE breeder_id=?',('b_test_policy',)),'blocked alternate report never consumes first-sale benefit')
    accepted=request('POST','/api/breeder/deal-policy-consent',{'accepted':True,'version':'2026-10-20-deal-scope-v3'},'u_test_policy')
    check(accepted[0]==200 and accepted[1]['accepted'],'existing breeder explicitly accepts the current scope')
    after_accept=request('GET','/api/breeder/deal-policy-consent',user='u_test_policy')
    check(after_accept[0]==200 and after_accept[1]['accepted'] and after_accept[1]['acceptance']['version']=='2026-10-20-deal-scope-v3','accepted policy remains accepted when reloaded')
    replay=request('POST','/api/breeder/deal-policy-consent',{'accepted':True,'version':'2026-10-20-deal-scope-v3'},'u_test_policy')
    check(replay[0]==200 and len(query('SELECT * FROM breeder_deal_policy_acceptances WHERE breeder_id=?',('b_test_policy',)))==1,'repeat consent keeps one immutable acceptance record')
    check(request('POST','/api/deals/'+legacy_policy_deal+'/sale-report',legacy_alternate,'u_test_policy')[0]==409,'post-consent cannot retroactively change an old inquiry')
    future,future_puppy=deal('alternate-after-consent','b_test_policy')
    accepted_at_ms=int(time.time()*1000)-100*24*60*60*1000
    execute('UPDATE breeder_deal_policy_acceptances SET accepted_at_ms=? WHERE breeder_id=?',(accepted_at_ms,'b_test_policy'))
    execute('UPDATE inquiries SET created_at=? WHERE id=?',(int(time.time())-89*24*60*60,'wf-i-alternate-after-consent'))
    expired,_=deal('alternate-expired','b_test_policy')
    execute('UPDATE inquiries SET created_at=? WHERE id=?',(int(time.time())-91*24*60*60,'wf-i-alternate-expired'))
    check(request('POST','/api/deals/'+expired+'/sale-report',dict(BODY,soldAnimalType='adult',soldAnimalName='期限超過の成犬'),'u_test_policy')[0]==409,'alternate sale after 90-day attribution window is rejected')
    alternate=dict(BODY,soldAnimalType='adult',soldAnimalName='成約確認対象の成犬')
    post('/api/deals/'+future+'/sale-report',alternate,'u_test_policy')
    flow=query('SELECT sold_animal_type,sold_animal_name FROM sale_workflow WHERE deal_id=?',(future,))[0]
    check(flow=={'sold_animal_type':'adult','sold_animal_name':'成約確認対象の成犬'},'alternate sale reported within 90 days persists the actual dog')
    check(query('SELECT expanded_scope_qualified_at_ms FROM sale_workflow WHERE deal_id=?',(future,))[0]['expanded_scope_qualified_at_ms']>0,'in-window first sale report records expanded-scope qualification')
    buyer_rows=request('GET','/api/buyer/sale-confirmations',user='u_demo')[1]
    check(any(x['deal_id']==future and x['puppy_name']=='成約確認対象の成犬' for x in buyer_rows),'buyer confirmation identifies the actual sold dog')
    answer(future,'sale')
    execute('UPDATE inquiries SET created_at=? WHERE id=?',(int(time.time())-91*24*60*60,'wf-i-alternate-after-consent'))
    post('/api/deals/'+future+'/completion-report',BODY,'u_test_policy');answer(future,'pickup')
    flow=query('SELECT sold_animal_type,sold_animal_name FROM sale_workflow WHERE deal_id=?',(future,))[0]
    check(flow=={'sold_animal_type':'adult','sold_animal_name':'成約確認対象の成犬'},'completion report preserves the actual sold dog')
    # Two real fixture claims exist: Oshiwan first puppy and policy-qualified adult.
    # Seed 97 immutable claims to reach 99 for the final-100th-slot test.
    execute("INSERT INTO first100_campaign_claims(deal_id,breeder_id,claimed_at) VALUES(?,?,?)",('seed-campaign-0','test',int(time.time())))
    for i in range(1,97):
        execute("INSERT INTO first100_campaign_claims(deal_id,breeder_id,claimed_at) VALUES(?,?,?)",('seed-campaign-'+str(i),'test',int(time.time())))
    state=request('GET','/api/campaign/first100')[1]
    check(state['status']=='active' and state['remaining'] is None and state['remainingLabel']=='残りわずか・受付中','last 20 campaign remaining slots are hidden')
    check(len(query('SELECT * FROM first100_campaign_claims'))==99,'fixture has 99 existing campaign claims')
    b=dict(BODY);b.pop('agreeFirstSaleTerms');post('/api/deals/'+first+'/sale-report',b,code=400)
    no_consent=dict(BODY);no_consent.pop('agreeAccurateReporting');post('/api/deals/'+first+'/sale-report',no_consent,code=400)
    check(not query('SELECT * FROM first_sale_benefits WHERE breeder_id=?',('b_dog44',)),'missing consent never consumes benefit')
    res=post('/api/deals/'+first+'/sale-report',BODY);check(res['waived'] and res['campaignWaived'],'100th site-wide sale report receives final free slot')
    check(request('GET','/api/campaign/first100')[1]['status']=='sold_out','100th reported deal ends promotion for everyone')
    post('/api/deals/'+first+'/sale-report',BODY);check(len(query('SELECT * FROM sale_confirmations WHERE deal_id=?',(first,)))==1,'duplicate application sends one confirmation')
    sc=confirmation(first,'sale')
    check(request('POST','/api/buyer/sale-confirmations/answer',{'id':sc['id'],'answer':'yes'},'u_dog44')[0]==403,'breeder cannot answer buyer confirmation')
    answer(first,'sale')
    post('/api/deals/'+first+'/completion-report',BODY);answer(first,'pickup')
    check(query('SELECT status FROM deals WHERE id=?',(first,))[0]['status']=='completed','breeder pickup report completes deal automatically')
    check(not query('SELECT * FROM commission_invoices WHERE deal_id=?',(first,)),'campaign-waived completion creates no invoice')
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
    cancelled,cp=deal('cancel','b_test2');r=post('/api/deals/'+cancelled+'/sale-report',BODY,'u_test_b2');check(not r['waived'],'new breeder does not get first-sale free once global 100 is spent')
    post('/api/deals/'+cancelled+'/cancel-report',{'note':'キャンセル','agreeAccurateReporting':True},'u_test_b2');answer(cancelled,'cancellation')
    check(not query('SELECT * FROM commission_invoices WHERE deal_id=?',(cancelled,)),'cancelled transaction is never invoiced')
    check(len(query('SELECT * FROM first100_campaign_claims'))==100,'cancellation does not restore site-wide campaign quota')
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
    check(query('SELECT * FROM deals WHERE id=?',(cancelled,)) and len(query('SELECT * FROM first100_campaign_claims'))==100,'archiving never resets global campaign history')
    # Simultaneous first applications for a fresh breeder: one winner only.
    execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES('u_test_b3','breeder','b3@example.invalid','s','h',?)",(int(time.time()),))
    execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES('b_test3','u_test_b3','試験犬舎3','埼玉県','','','approved')")
    execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-u_test_b3','u_test_b3',int(time.time()),int(time.time())+86400))
    d3a,_=deal('race-a','b_test3');d3b,_=deal('race-b','b_test3')
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        rs=list(pool.map(lambda d:request('POST','/api/deals/'+d+'/sale-report',BODY,'u_test_b3'),[d3a,d3b]))
    check(all(x[0]==200 for x in rs) and sum(x[1]['waived'] for x in rs)==0,'no breeder gets another free transaction once global quota is exhausted')
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
    # 推しワン integration: consent, ownership, kennel/breed quota, breed rotation,
    # fee attribution at inquiry time, immutable billing, sold cleanup and public PR.
    os_path='/api/oshiwan/'+rp
    check(request('POST',os_path+'/selection',{'enabled':True,'agreeOshiwanTerms':True},'u_demo')[0]==403,'Oshiwan buyer cannot promote another puppy')
    check(request('POST',os_path+'/selection',{'enabled':True},uid)[0]==400,'Oshiwan 3% consent is mandatory')
    st,os_state=request('GET',os_path+'/state',user=uid)
    check(st==200 and not os_state['enabled'] and os_state['kennelBreedCount']==0,'Oshiwan starts disabled for legacy listing')
    st,_=request('POST',os_path+'/selection',{'enabled':True,'agreeOshiwanTerms':True},uid)
    check(st==200,'Oshiwan breeder opts in explicitly')
    promoted=[rp]
    for i in range(2):
        st,pu=request('POST','/api/puppies',{'name':'推しワン登録試験'+str(i),'breed':'スタンダードプードル','breedKey':'standard-poodle','gender':'女の子','color':'ホワイト','price':300000},uid)
        check(st==201,'Oshiwan additional published puppy '+str(i))
        promoted.append(pu['id'])
    st,_=request('POST','/api/oshiwan/'+promoted[1]+'/selection',{'enabled':True,'agreeOshiwanTerms':True},uid)
    check(st==200,'Oshiwan second puppy same kennel allowed')
    st,_=request('POST','/api/oshiwan/'+promoted[2]+'/selection',{'enabled':True,'agreeOshiwanTerms':True},uid)
    check(st==409,'Oshiwan third puppy same kennel rejected')
    for i in range(6):
        suffix='oshik'+str(i)
        execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES(?,'breeder',?,'s','h',?)",('u_'+suffix,suffix+'@example.invalid',int(time.time())))
        execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,review_status) VALUES(?,?,?,'埼玉県','approved')",('b_'+suffix,'u_'+suffix,'推し犬舎'+str(i)))
        pid='oshitest-p-'+str(i)
        execute("INSERT INTO puppies(id,breeder_id,name,breed,breed_key,gender,gender_key,color,price,status,area,area_key,created_at,review_status) VALUES(?,?,?,'スタンダードプードル','standard-poodle','男の子','male','クリーム',300000,'募集中','埼玉県','saitama',?,'approved')",(pid,'b_'+suffix,'推し犬'+str(i),int(time.time())))
        st,_=request('POST','/api/oshiwan/'+pid+'/selection',{'enabled':True,'agreeOshiwanTerms':True},'u_admin')
        check(st==200,'Oshiwan operator can manage authorized proxy listing '+str(i))
    st,o1=request('GET','/api/oshiwan')
    st2,o2=request('GET','/api/oshiwan')
    group1=next(g for g in o1['groups'] if g['breed']=='スタンダードプードル')
    group2=next(g for g in o2['groups'] if g['breed']=='スタンダードプードル')
    ids1={p['id'] for p in group1['puppies']};ids2={p['id'] for p in group2['puppies']}
    check(st==200 and st2==200 and len(ids1)==len(ids2)==5,'Oshiwan public shows exactly five per breed')
    check(ids1!=ids2 and len(ids1|ids2)>5,'Oshiwan refresh rotates fairly across eligible puppies')
    check(o1['advertisement'] and o1['label']=='推しワン','Oshiwan public payload labels sponsored placement')
    # Sale inquiry created after promotion; dog44 already used its free first sale.
    os_i='oshiwan-test-inquiry';os_d='oshiwan-test-deal';t=int(time.time())
    execute("INSERT INTO inquiries(id,puppy_id,buyer_id,breeder_id,name,email,created_at) VALUES(?,?,?,?,?,?,?)",(os_i,rp,'u_demo','b_dog44','推しワン購入者','oshiwan@example.invalid',t))
    execute('INSERT INTO deals VALUES(?,?,?,?,?,?,?,?,?)',(os_d,os_i,rp,'u_demo','b_dog44',300000,100000,'negotiating',t))
    post('/api/deals/'+os_d+'/sale-report',BODY,uid)
    decision=query('SELECT * FROM sale_fee_decisions WHERE deal_id=?',(os_d,))
    check(len(decision)==1 and decision[0]['rate_bps']==800 and not decision[0]['waived'],'Oshiwan inquiry locks 5%+3% combined rate after site-wide 100 quota')
    post('/api/deals/'+os_d+'/completion-report',BODY,uid)
    inv=query('SELECT * FROM commission_invoices WHERE deal_id=?',(os_d,))
    check(len(inv)==1 and inv[0]['fee_amount']==24000 and inv[0]['rate_bps']==800,'Oshiwan invoice charges 5% plus 3% of the agreed sale price')
    check(inv[0]['due_at']-inv[0]['issued_at']==7*86400 and inv[0]['status']=='issued',
          'Oshiwan post-campaign 8% invoice also has exactly 7-day payment deadline')
    check('成約手数料5％＋推しワン利用料3％' in inv[0]['note'],'Oshiwan invoice distinctly itemizes both 5% and 3% fees')
    answer(os_d,'pickup')
    check(len(query('SELECT * FROM commission_invoices WHERE deal_id=?',(os_d,)))==1,'Oshiwan buyer confirmation cannot duplicate invoice')
    # First sale: standard fee is waived, but the optional sponsored slot remains 3%.
    execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES('u_oshi_first','breeder','oshifirst@example.invalid','s','h',?)",(int(time.time()),))
    execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,review_status) VALUES('b_oshi_first','u_oshi_first','初回推しワン犬舎','埼玉県','approved')")
    execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-u_oshi_first','u_oshi_first',int(time.time()),int(time.time())+86400))
    first_osh_d,first_osh_p=deal('oshi-first','b_oshi_first')
    st,_=request('POST','/api/oshiwan/'+first_osh_p+'/selection',{'enabled':True,'agreeOshiwanTerms':True},'u_oshi_first')
    check(st==200,'Oshiwan new breeder explicitly opts in before first inquiry')
    execute('UPDATE inquiries SET created_at=? WHERE id=?',(int(time.time()),'wf-i-oshi-first'))
    first_osh_sale=post('/api/deals/'+first_osh_d+'/sale-report',BODY,'u_oshi_first')
    check(not first_osh_sale['waived'],'first Oshiwan sale after first 100 is not additionally waived')
    first_osh_decision=query('SELECT waived,rate_bps FROM sale_fee_decisions WHERE deal_id=?',(first_osh_d,))[0]
    check(first_osh_decision['waived']==0 and first_osh_decision['rate_bps']==800,'Oshiwan first sale after campaign charges base 5% plus 3%')
    post('/api/deals/'+first_osh_d+'/completion-report',BODY,'u_oshi_first')
    first_osh_invoice=query('SELECT * FROM commission_invoices WHERE deal_id=?',(first_osh_d,))
    check(len(first_osh_invoice)==1 and first_osh_invoice[0]['rate_bps']==800 and first_osh_invoice[0]['fee_amount']==24000,'Oshiwan first sale after campaign correctly charges 24000 yen total fees')
    check(first_osh_invoice[0]['due_at']-first_osh_invoice[0]['issued_at']==7*86400,
          'Oshiwan new-breeder first sale AFTER quota expiry is due in seven days')
    check('推しワン利用料' in first_osh_invoice[0]['note'],'Oshiwan first-sale invoice identifies promotion separate from standard fee')
    check(not query('SELECT * FROM first_sale_benefits WHERE breeder_id=?',('b_oshi_first',)),'no new per-breeder first sale waiver is recorded')
    answer(first_osh_d,'pickup')
    check(len(query('SELECT * FROM commission_invoices WHERE deal_id=?',(first_osh_d,)))==1,'Oshiwan first-sale buyer confirmation remains idempotent')
    st,state=request('GET',os_path+'/state',user=uid)
    check(st==200 and not state['enabled'],'Oshiwan sold puppy leaves spotlight automatically')
    st,periods=request('GET','/api/oshiwan')
    check(st==200 and all(p['id']!=rp for g in periods['groups'] for p in g['puppies']),'Oshiwan sold puppy never appears on public homepage')
    st,_=request('POST','/api/oshiwan/'+promoted[2]+'/selection',{'enabled':True,'agreeOshiwanTerms':True},uid)
    check(st==200,'Oshiwan released kennel slot can be reused after sale')
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
