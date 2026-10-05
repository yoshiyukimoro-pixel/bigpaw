"""Full HTTP workflow and regression checks; disposable DB and local mail capture."""
import concurrent.futures,json,os,re,socket,sqlite3,subprocess,sys,tempfile,time
from pathlib import Path
from urllib.request import Request,urlopen
from urllib.error import HTTPError
app=Path(sys.argv[1]).resolve();work=Path(tempfile.mkdtemp(prefix='bigpaw-cancel-test-'));data=work/'data';data.mkdir()
with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
base=f'http://127.0.0.1:{port}';server=app/'backend/server.py';raw=server.read_text()
hook='''def _capture_mail(to_email,subject,text):
    with open(os.environ['BIGPAW_TEST_MAIL_CAPTURE'],'a') as f:
        f.write(json.dumps({'to':to_email,'subject':subject,'text':text},ensure_ascii=False)+'\\n')
    return 'fail-mail' not in text
send_mail=_capture_mail
'''
marker='from first_sale_workflow import install as _install_first_sale_workflow'
assert marker in raw;server.write_text(raw.replace(marker,hook+'\n'+marker,1))
env={k:v for k,v in os.environ.items() if not k.startswith(('BIGPAW_','SMTP_','RESEND_'))}
env.update(PORT=str(port),BIGPAW_DATA_DIR=str(data),BIGPAW_ENV='development',BIGPAW_PUBLIC_BASE_URL=base,BIGPAW_AUTOMATION_INTERVAL_SECONDS='3600',BIGPAW_TEST_MAIL_CAPTURE=str(work/'mail.jsonl'))
log=open(work/'server.log','w');process=None

def execute(sql,args=()):
    with sqlite3.connect(data/'bigpaw.sqlite3',timeout=20) as c:c.execute(sql,args)
def query(sql,args=()):
    c=sqlite3.connect(data/'bigpaw.sqlite3',timeout=20);c.row_factory=sqlite3.Row
    try:return [dict(r) for r in c.execute(sql,args)]
    finally:c.close()
def req(method,path,body=None,user=None,origin='https://bigpaw.site'):
    headers={'Content-Type':'application/json'}
    if user:headers['Cookie']='bigpaw_session=test-'+user
    if origin:headers['Origin']=origin
    r=Request(base+path,method=method,data=json.dumps(body).encode() if body is not None else None,headers=headers)
    try:
        with urlopen(r,timeout=15) as out:return out.status,json.loads(out.read() or b'{}')
    except HTTPError as e:return e.code,json.loads(e.read() or b'{}')
def check(cond,name):
    if not cond:raise AssertionError(name)
    print('PASS',name,flush=True)
def expect(method,path,body=None,user=None,status=200,origin='https://bigpaw.site'):
    code,r=req(method,path,body,user,origin);check(code==status,f'{method} {path.split("?")[0]}: {status}, got {code} {r if code!=status else ""}');return r
def start():
    global process
    process=subprocess.Popen([sys.executable,str(server)],cwd=app,env=env,stdout=log,stderr=log)
    for _ in range(100):
        try:
            if req('GET','/api/health')[0]==200:return
        except Exception:time.sleep(.1)
    raise RuntimeError((work/'server.log').read_text()[-4000:])
def fixture(tag,deal=False,status='未返信'):
    pid='ic-p-'+tag;iid='ic-i-'+tag;did='ic-d-'+tag;t=int(time.time())
    execute("INSERT INTO puppies(id,breeder_id,name,breed,breed_key,gender,gender_key,color,price,status,area,area_key,created_at,review_status) VALUES(?,'b_dog44',?,'スタンダードプードル','standard','男の子','male','ブラック',300000,'募集中','埼玉県','saitama',?,'approved')",(pid,'試験犬 '+tag,t))
    execute("INSERT INTO inquiries(id,puppy_id,buyer_id,breeder_id,name,email,status,created_at) VALUES(?,?,'u_demo','b_dog44','試験購入者','private@example.invalid',?,?)",(iid,pid,status,t))
    if deal:execute("INSERT INTO deals VALUES(?,?,?,'u_demo','b_dog44',300000,100000,'negotiating',?)",(did,iid,pid,t))
    return iid,pid,did
def submit(iid,reason='visited_no_contract',note='',user='u_dog44'):
    return expect('POST','/api/inquiries/'+iid+'/cancellation',{'reason':reason,'note':note,'agreeAccurateReporting':True},user)
def gettoken(rid):
    row=query('SELECT body FROM sale_mail_outbox WHERE event_key=?',('ic-confirm:'+rid,))[0]
    return re.search(r'#token=([\w-]+)',row['body']).group(1)
def answer(rid,reason='visited_no_contract',note=''):
    return expect('POST','/api/cancellation-confirmation/answer',{'token':gettoken(rid),'reason':reason,'note':note})
def review(rid,action='approve',note='双方とやり取りを確認しました。'):
    return expect('PATCH','/api/operator/inquiry-cancellations/'+rid,{'action':action,'note':note},'u_admin')
try:
    start()
    for uid in ('u_demo','u_dog44','u_admin'):
        execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-'+uid,uid,int(time.time()),int(time.time())+86400))
    # Add populated fixtures, restart with production auth and check additive/idempotent migration.
    iid,pid,did=fixture('matching',True,'見学確定')
    execute("INSERT INTO visits VALUES('ic-v-match',?,'2026-10-03','17:00',1,'車','confirmed',1,?)",(iid,int(time.time())))
    process.terminate();process.wait(timeout=5)
    # Emulate the already deployed cancellation schema before alert columns existed.
    execute('ALTER TABLE inquiry_cancellations DROP COLUMN operator_seen_at')
    execute('ALTER TABLE inquiry_cancellations DROP COLUMN operator_seen_by')
    env.update(BIGPAW_ENV='production',BIGPAW_ADMIN_EMAIL='admin@example.invalid',BIGPAW_ADMIN_PASSWORD='ProductionTestOnly123!',BIGPAW_DEV_LINKS='0')
    start();check(len(query('SELECT * FROM inquiries WHERE id=?',(iid,)))==1,'populated inquiry survives production restart and migration')
    check(len(list((data/'backups').glob('before-inquiry-cancellation-*.sqlite3')))==2,'snapshots before initial schema and existing-table alert migration')
    check({'operator_seen_at','operator_seen_by'}<={r['name'] for r in query('PRAGMA table_info(inquiry_cancellations)')},'existing-table additive alert migration succeeds')
    execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES('u_ops2','operator','other-admin@example.invalid','s','h',?)",(int(time.time()),))
    url='/api/inquiries/'+iid+'/cancellation'
    expect('POST',url,{'reason':'visited_no_contract','agreeAccurateReporting':True},'u_demo',403)
    expect('POST',url,{'reason':'visited_no_contract','agreeAccurateReporting':True},'u_dog44',403,origin=None)
    expect('POST',url,{'reason':'visited_no_contract','agreeAccurateReporting':True},'u_dog44',403,origin='https://evil.example')
    expect('POST',url,{'agreeAccurateReporting':True},'u_dog44',400)
    expect('POST',url,{'reason':'other','agreeAccurateReporting':True},'u_dog44',400)
    execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES('u_out','breeder','outsider@example.invalid','s','h',?)",(int(time.time()),))
    execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES('b_out','u_out','別犬舎','埼玉県','','','approved')")
    execute('INSERT INTO sessions VALUES(?,?,?,?)',('test-u_out','u_out',int(time.time()),int(time.time())+86400))
    expect('POST',url,{'reason':'visited_no_contract','agreeAccurateReporting':True},'u_out',404)
    # Operators can use the breeder cancellation screen while administering a kennel; the action stays audited.
    oi,_,_=fixture('operator-submit')
    orow=expect('POST','/api/inquiries/'+oi+'/cancellation',{'reason':'visit_not_held','agreeAccurateReporting':True},'u_admin')
    check(query('SELECT actor_id FROM inquiry_cancellation_history WHERE request_id=? AND action=\'submitted\'',(orow['id'],))[0]['actor_id']=='u_admin','operator-submitted cancellation is audited to the operator account')
    expect('POST','/api/operator/inquiry-cancellations/'+orow['id']+'/acknowledge',{},'u_admin')
    answer(orow['id'],'visit_not_held')
    check(query('SELECT state FROM inquiry_cancellations WHERE id=?',(orow['id'],))[0]['state']=='closed','operator submission follows the same buyer-confirmation close workflow')
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        results=list(pool.map(lambda _:req('POST',url,{'reason':'visited_no_contract','agreeAccurateReporting':True},'u_dog44'),range(2)))
    check(all(r[0]==200 for r in results),'simultaneous duplicate applications succeed idempotently')
    rid=results[0][1]['id'] if 'id' in results[0][1] else query('SELECT id FROM inquiry_cancellations WHERE inquiry_id=?',(iid,))[0]['id']
    check(len(query('SELECT * FROM inquiry_cancellations WHERE inquiry_id=?',(iid,)))==1,'exactly one request for duplicate submissions')
    buyer_mail_count=lambda:len(query('SELECT * FROM sale_mail_outbox WHERE event_key=?',('ic-confirm:'+rid,)))
    check(buyer_mail_count()==1,'duplicate submission queues exactly one buyer confirmation email')
    repeat=expect('POST',url,{'reason':'visit_not_held','agreeAccurateReporting':True},'u_dog44')
    check(repeat.get('alreadySubmitted') is True and repeat.get('state')=='buyer_pending','repeat with changed form data is idempotent instead of 409')
    check(buyer_mail_count()==1,'idempotent repeat never sends a duplicate buyer email')
    # A historical closed request must not block a newer continued request from starting a fresh cancellation.
    hi,_,_=fixture('history-reopened')
    old=submit(hi,'visit_not_held')
    execute("UPDATE inquiry_cancellations SET state='closed' WHERE id=?",(old['id'],))
    execute("UPDATE inquiries SET status='取引終了' WHERE id=?",(hi,))
    execute("INSERT INTO inquiry_cancellations(id,inquiry_id,breeder_id,buyer_id,breeder_reason,breeder_note,state,previous_inquiry_status,token_hash,expires_at,created_at) SELECT ?,inquiry_id,breeder_id,buyer_id,breeder_reason,breeder_note,'continued','取引終了',?, ?, ? FROM inquiry_cancellations WHERE id=?",('ic-history-continued','f'*64,int(time.time())+86400,int(time.time())+1,old['id']))
    execute("UPDATE inquiries SET status='返信済み' WHERE id=?",(hi,))
    fresh=expect('POST','/api/inquiries/'+hi+'/cancellation',{'reason':'buyer_withdrew','agreeAccurateReporting':True},'u_dog44')
    check(fresh.get('alreadySubmitted') is not True and fresh.get('state')=='buyer_pending','latest continued cancellation permits a fresh cancellation submission')
    check(len(query("SELECT * FROM inquiry_cancellations WHERE inquiry_id=?",(hi,)))==3,'fresh cancellation is stored after historical closed and continued records')
    check(len(query("SELECT * FROM sale_mail_outbox WHERE event_key=?",('ic-confirm:'+fresh['id'],)))==1,'fresh cancellation queues a new buyer confirmation email')
    summary=lambda:expect('GET','/api/operator/inquiry-cancellations/summary',user='u_admin')
    acknowledge=lambda rid:expect('POST','/api/operator/inquiry-cancellations/'+rid+'/acknowledge',{},'u_admin')
    check(summary()=={'attention':1,'unread':1,'needsReview':0},'new submission immediately alerts operator before buyer response')
    expect('GET','/api/operator/inquiry-cancellations',user='u_admin')
    check(summary()['unread']==1,'viewing list never silently clears alert')
    expect('GET','/api/operator/inquiry-cancellations/summary',status=401)
    expect('GET','/api/operator/inquiry-cancellations/summary',user='u_demo',status=403)
    expect('POST','/api/operator/inquiry-cancellations/'+rid+'/acknowledge',{},'u_dog44',403)
    expect('POST','/api/operator/inquiry-cancellations/'+rid+'/acknowledge',{},'u_admin',403,origin='https://evil.example')
    acknowledge(rid);acknowledge(rid)
    check(summary()['attention']==0,'explicit operator acknowledgement clears pending alert')
    check(len(query("SELECT * FROM inquiry_cancellation_history WHERE request_id=? AND action='operator_acknowledged'",(rid,)))==1,'acknowledgement is idempotent and audited')
    opmail=query("SELECT * FROM sale_mail_outbox WHERE event_key LIKE ?",('ic-operator:'+rid+':%',))
    check(len(opmail)==1 and opmail[0]['recipient']=='info@bigpaw.site','one support mailbox email despite multiple operators and duplicate submissions')
    check(all(x in opmail[0]['body'] for x in ('運営管理画面','申請理由：','購入希望者：','試験犬 matching','operator-cancellations.html#request='+rid)),'operator email includes details and direct request link')
    token=gettoken(rid);check(len(query('SELECT * FROM sale_mail_outbox WHERE event_key=?',('ic-confirm:'+rid,)))==1,'exactly one buyer email event')
    check(token not in json.dumps(query('SELECT * FROM inquiry_cancellations')),'DB stores hash, not capability token')
    public=expect('POST','/api/cancellation-confirmation/view',{'token':token})
    check('buyer_id' not in public and 'buyer_name' not in public and 'kennel_name' not in public and 'history' not in public,'public link discloses no identities or internal history')
    check(query('SELECT buyer_reason FROM inquiry_cancellations WHERE id=?',(rid,))[0]['buyer_reason'] is None,'opening email link does not answer')
    expect('POST','/api/inquiries/'+iid+'/visit',{},'u_dog44',409)
    expect('POST','/api/inquiries/'+iid+'/deal',{},'u_dog44',409)
    expect('PATCH','/api/inquiries/'+iid,{'status':'返信済み'},'u_dog44',409)
    expect('POST','/api/deals/'+did+'/completion-report',{},'u_dog44',409)
    expect('POST','/api/deals/'+did+'/cancel-report',{},'u_dog44',409)
    expect('POST','/api/inquiries/'+iid+'/messages',{'body':'状況を確認しています'},'u_dog44',201)
    answer(rid);check(query('SELECT status FROM inquiries WHERE id=?',(iid,))[0]['status']=='取引終了','matching visit-stage reasons close inquiry')
    check(query('SELECT status FROM visits WHERE inquiry_id=?',(iid,))[0]['status']=='cancelled','closed inquiry cancels planned visit')
    check(query('SELECT status FROM deals WHERE id=?',(did,))[0]['status']=='cancelled','existing deal marked cancelled with history retained')
    check(query('SELECT status FROM puppies WHERE id=?',(pid,))[0]['status']=='募集中','does not change another customer or puppy listing state')
    answer(rid);check(len(query("SELECT * FROM inquiry_cancellation_history WHERE request_id=? AND action='buyer_answered'",(rid,)))==1,'same repeated answer is idempotent')
    closed_repeat=expect('POST',url,{'reason':'buyer_withdrew','agreeAccurateReporting':True},'u_dog44')
    check(closed_repeat.get('alreadySubmitted') is True and closed_repeat.get('state')=='closed','closed cancellation repeat returns completed state instead of 409')
    check(buyer_mail_count()==1,'closed repeat never sends a duplicate buyer email')
    expect('POST','/api/cancellation-confirmation/answer',{'token':token,'reason':'purchased'},status=409)
    expect('POST','/api/cancellation-confirmation/answer',{'token':'x'*43,'reason':'purchased'},status=401)
    expect('PATCH','/api/operator/inquiry-cancellations/'+rid,{'action':'approve','note':'再実行'},'u_admin',409)
    # Reason correspondence before visit, no-show and other puppy, without a deal or fee claim.
    for tag,br,by in [('before','buyer_withdrew','before_visit'),('no-show','visit_not_held','visit_not_held'),('other-pup','another_puppy','another_puppy')]:
        iq,_,_=fixture(tag);r=submit(iq,br);answer(r['id'],by)
        check(query('SELECT state FROM inquiry_cancellations WHERE id=?',(r['id'],))[0]['state']=='closed',tag+' matching reasons auto close')
    check(not query('SELECT * FROM first_sale_benefits'),'inquiry-stage cancellation never consumes first sale free benefit')
    # Different reasons, ongoing negotiation and purchase all require operator review.
    mismatch=[]
    for tag,by in [('different','visit_not_held'),('ongoing','negotiating'),('purchased','purchased'),('unreachable','before_visit'),('other','other')]:
        iq,_,_=fixture(tag);r=submit(iq,'unreachable' if tag=='unreachable' else 'other' if tag=='other' else 'visited_no_contract','補足' if tag=='other' else '')
        acknowledge(r['id'])
        answer(r['id'],by,'補足' if by=='other' else '');mismatch.append((r['id'],iq))
        check(query('SELECT state FROM inquiry_cancellations WHERE id=?',(r['id'],))[0]['state']=='operator_review',tag+' remains review, no automatic charge or closure')
        check(query('SELECT operator_seen_at FROM inquiry_cancellations WHERE id=?',(r['id'],))[0]['operator_seen_at'] is None,'buyer mismatch raises a fresh unread alert')
        before=summary()['attention'];acknowledge(r['id']);check(summary()['attention']==before,'acknowledged mismatch remains alert until decision')
    before=summary()['attention']
    review(mismatch[0][0]);review(mismatch[1][0],'continue')
    check(summary()['attention']==before-2,'operator completion clears only resolved alerts')
    expect('PATCH','/api/inquiries/'+mismatch[1][1],{'status':'返信済み'},'u_dog44')
    review(mismatch[2][0],'confirm_sale');check(not query('SELECT * FROM commission_invoices'),'operator sale decision never guesses purchase amount or issues invoice')
    expect('PATCH','/api/operator/inquiry-cancellations/'+mismatch[3][0],{'action':'approve','note':'不可'},'u_dog44',403)
    expect('PATCH','/api/operator/inquiry-cancellations/'+mismatch[3][0],{'action':'approve','note':''},'u_admin',400)
    review(mismatch[3][0],'request_details','双方へ現在の状況を確認します。')
    # Even matching answers with real signed contract/payment are reviewed by operator.
    iq,pp,dd=fixture('signed',True);execute("INSERT INTO contracts(id,deal_id,version,buyer_signed_at,breeder_signed_at,status,updated_at) VALUES('ic-contract',?,'v1',?,NULL,'draft',?)",(dd,int(time.time()),int(time.time())))
    r=submit(iq);answer(r['id']);check(query('SELECT state FROM inquiry_cancellations WHERE id=?',(r['id'],))[0]['state']=='operator_review','signed contract cannot auto close on matching reason');review(r['id'])
    # Expired links: no answer and no implicit cancellation; old links invalid on resend.
    iq,_,_=fixture('expire');r=submit(iq);acknowledge(r['id']);old_token=gettoken(r['id']);execute('UPDATE inquiry_cancellations SET expires_at=1 WHERE id=?',(r['id'],))
    expect('POST','/api/cancellation-confirmation/answer',{'token':old_token,'reason':'visited_no_contract'},status=409)
    expect('POST','/api/operator/run-automations',{},'u_admin')
    check(query('SELECT state FROM inquiry_cancellations WHERE id=?',(r['id'],))[0]['state']=='unanswered','seven day silence goes to operator, never closed')
    check(query('SELECT operator_seen_at FROM inquiry_cancellations WHERE id=?',(r['id'],))[0]['operator_seen_at'] is None,'seven-day expiry raises fresh unread operator alert')
    expect('POST','/api/operator/inquiry-cancellations/'+r['id']+'/resend',{},'u_admin')
    expect('POST','/api/cancellation-confirmation/view',{'token':old_token},status=404)
    body=query("SELECT body FROM sale_mail_outbox WHERE event_key LIKE 'ic-resend:%' ORDER BY rowid DESC LIMIT 1")[0]['body'];newtoken=re.search(r'#token=([\w-]+)',body).group(1)
    expect('POST','/api/cancellation-confirmation/answer',{'token':newtoken,'reason':'visited_no_contract'})
    # Buyer account view and outsider access checks.
    iq,_,_=fixture('account');r=submit(iq);expect('POST','/api/cancellation-confirmation/answer',{'id':r['id'],'reason':'visited_no_contract'},'u_demo')
    account=expect('GET','/api/buyer/inquiry-cancellations',user='u_demo');check(all('kennel_name' not in x and 'history' not in x for x in account['requests']),'buyer account also keeps breeder names and internal history private')
    expect('GET','/api/operator/inquiry-cancellations',user='u_demo',status=403)
    expect('GET','/api/inquiries/'+iq+'/cancellation',user='u_out',status=404)
    # Existing sale process after pending cancellation rejected: preserves benefit, then normal completion invoice.
    iq,pp,dd=fixture('sale',True)
    body={'finalSaleAmount':300000,'pickupDate':'2026-10-03','buyerName':'試験','agreeFirstSaleTerms':True,'agreeAccurateReporting':True}
    sr=expect('POST','/api/deals/'+dd+'/sale-report',body,'u_dog44');check(sr['waived'],'existing first-sale free benefit works')
    r=submit(iq);answer(r['id'],'purchased');review(r['id'],'continue')
    expect('POST','/api/deals/'+dd+'/sale-report',body,'u_dog44')
    expect('POST','/api/deals/'+dd+'/completion-report',body,'u_dog44');check(query('SELECT status FROM deals WHERE id=?',(dd,))[0]['status']=='completed','existing completion still finalizes')
    check(len(query('SELECT * FROM first_sale_benefits'))==1 and not query('SELECT * FROM commission_invoices WHERE deal_id=?',(dd,)),'cancellation and resume preserve free-benefit accounting')
    iq,pp,dd=fixture('sale-paid',True);expect('POST','/api/deals/'+dd+'/sale-report',body,'u_dog44');expect('POST','/api/deals/'+dd+'/completion-report',body,'u_dog44')
    invoice=query('SELECT * FROM commission_invoices WHERE deal_id=?',(dd,))[0]
    check(invoice['fee_amount']==15000 and invoice['due_at']-invoice['issued_at']==7*86400,'existing 5% invoice with seven-day term unchanged')
    # Real email outbox retry: failure remains durable and retry metadata is recorded.
    execute("INSERT INTO sale_mail_outbox(id,event_key,recipient,subject,body,created_at) VALUES('ic-fail','ic-fail','test@example.invalid','試験','fail-mail',?)",(int(time.time()),))
    expect('POST','/api/operator/run-automations',{},'u_admin')
    failed=query("SELECT * FROM sale_mail_outbox WHERE id='ic-fail'")[0];check(failed['sent_at'] is None and failed['attempts']>=1 and failed['next_attempt_at']>int(time.time()),'failed email stays queued with scheduled retry')
    execute("UPDATE sale_mail_outbox SET body='retry-success',next_attempt_at=0 WHERE id='ic-fail'")
    expect('POST','/api/operator/run-automations',{},'u_admin');check(query("SELECT sent_at FROM sale_mail_outbox WHERE id='ic-fail'")[0]['sent_at'],'failed email retries successfully')
    # Existing protected features: photos/order, search, favorites, inquiry creation, admin.
    from PIL import Image
    import io
    p=expect('POST','/api/puppies',{'name':'写真回帰試験','breed':'スタンダードプードル','breedKey':'standard','gender':'男の子','color':'ブラック','price':300000,'area':'埼玉県','desc':'紹介文'},'u_dog44',201);rp=p['id']
    expect('PATCH','/api/puppies/'+rp,{'price':310000,'desc':'紹介文\n改行'},'u_dog44')
    photos=[]
    for color in ('red','blue'):
        buf=io.BytesIO();Image.new('RGB',(48,48),color).save(buf,format='PNG');b='CANCELTESTBOUNDARY'
        rawbody=(f'--{b}\r\nContent-Disposition: form-data; name="puppyId"\r\n\r\n{rp}\r\n--{b}\r\nContent-Disposition: form-data; name="file"; filename="{color}.png"\r\nContent-Type: image/png\r\n\r\n').encode()+buf.getvalue()+f'\r\n--{b}--\r\n'.encode()
        request=Request(base+'/api/uploads',data=rawbody,method='POST',headers={'Cookie':'bigpaw_session=test-u_dog44','Origin':'https://bigpaw.site','Content-Type':'multipart/form-data; boundary='+b})
        with urlopen(request,timeout=15) as out:check(out.status==201,'existing '+color+' photo upload');photos.append(json.loads(out.read())['id'])
    expect('PATCH','/api/puppies/'+rp+'/photos/order',{'ids':photos[::-1]},'u_dog44')
    p=expect('GET','/api/puppies/'+rp);check(len(p['photos'])==2 and '\n' in p['desc'],'existing photo order and multiline introduction survive')
    expect('POST','/api/favorites/'+rp,{},'u_demo');check(any(p['id']==rp for p in expect('GET','/api/favorites',user='u_demo')),'existing favorite storage')
    check(any(p['id']==rp for p in expect('GET','/api/puppies?breed=standard&area=saitama')),'existing breed and prefecture search')
    expect('GET','/api/operator/breeders',user='u_admin');expect('GET','/api/operator/invoices',user='u_admin')
    expect('POST','/api/breeder/sales-handover-settings',{'reservationAmount':100000,'minHandoverDays':57,'healthExamIncluded':True,'microchipIncluded':True},'u_dog44')
    # Handover access: own breeder settings and explicit operator target remain isolated.
    settings='/api/breeder/sales-handover-settings'
    own=expect('GET',settings,user='u_dog44')
    check(own['breederId']=='b_dog44' and own['reservationAmount']==100000,'breeder settings read back without target selection')
    expect('POST',settings,{'vaccineIncluded':False,'vaccineNote':'別犬舎：ワクチン代別途8000円','reservationAmount':50000},'u_out')
    other=expect('GET',settings+'?breederId=b_out',user='u_admin')
    check(other['breederId']=='b_out' and other['reservationAmount']==50000,'operator reads explicitly selected breeder settings')
    check(expect('GET',settings+'?breederId=b_out',user='u_dog44')['breederId']=='b_dog44','breeder cannot switch settings owner through operator query')
    expect('GET',settings,user='u_admin',status=404)
    expect('GET',settings+'?breederId=missing',user='u_admin',status=404)
    expect('GET',settings+'?breederId=b_dog44',user='u_demo',status=403)
    expect('GET',settings,status=401)
    expect('POST',settings,{'breederId':'b_out','reservationAmount':999},'u_demo',403)
    check(expect('GET',settings,user='u_out')['reservationAmount']==50000,'unauthorized write never changes another breeder settings')
    execute("INSERT INTO users(id,role,email,salt,password_hash,created_at) VALUES('u_settings_empty','breeder','settings-empty@example.invalid','s','h',?)",(int(time.time()),))
    execute("INSERT INTO breeders(id,user_id,kennel_name,prefecture,registration_no,profile,review_status) VALUES('b_settings_empty','u_settings_empty','条件未登録犬舎','埼玉県','','','approved')")
    check(expect('GET',settings+'?breederId=b_settings_empty',user='u_admin')['configured'] is False,'existing breeder without settings is unconfigured, not a loading error')
    check(any(b['id']=='b_out' for b in expect('GET','/api/operator/breeders',user='u_admin')),'operator selector includes registered breeders')
    # Browser fixtures: one new inquiry for automatic close, another for operator mismatch.
    bi,bp,_=fixture('browser');mi,mp,_=fixture('browser-review')
    for _ in range(60):
        if not query('SELECT 1 FROM sale_mail_outbox WHERE sent_at IS NULL'):break
        time.sleep(.05)
    captured=[json.loads(x) for x in (work/'mail.jsonl').read_text().splitlines()]
    check(any('【取引状況を確認する】' in x['text'] and '#token=' in x['text'] and '7日間' in x['text'] for x in captured),'buyer email contains direct confirmation link, seven-day term and stage reason')
    check(not query('SELECT 1 FROM sale_mail_outbox WHERE sent_at IS NULL'),'all local capture emails sent or retried')
    ui=(app/'assets/breeder-cancellation.js').read_text();page=(app/'breeder-cancellation.html').read_text();check("'breeder-inquiries.html?cancellation='+(r.alreadySubmitted?'already':'submitted')" in ui,'successful or repeated cancellation returns to inquiry list');check('assets/breeder-cancellation.js?v=20261006b1' in page,'cancellation page cache-busts redirect script')
    links=(app/'assets/inquiry-cancellation-links.js').read_text();patch=(app/'backend/inquiry_cancellation_patch.py').read_text()
    check('breeder-cancellation.html?ui=20261006b1&inquiry=' in links and 'inquiry-cancellation-links.js?v=20261006b1' in patch,'breeder cancellation entry points are versioned against stale Safari restores')
    inquiries_page=(app/'breeder-inquiries.html').read_text()
    check("const active=q.filter(x=>x.status!=='取引終了')" in inquiries_page,'closed cancellations are excluded from active breeder inquiry list')
    check("closedRows=q.filter(x=>x.status==='取引終了')" in inquiries_page and '取引終了履歴を見る' in inquiries_page,'closed cancellations remain available in a separate history view')
    context={'base':base,'work':str(work),'data':str(data),'browserInquiry':bi,'mismatchInquiry':mi,'regressionPuppy':rp,'port':port,'pages':[p.name for p in sorted(app.glob('*.html'))]}
    context_path=work/'context.json';context_path.write_text(json.dumps(context));print('INQUIRY_CANCELLATION_HTTP_OK',context_path,flush=True)
    if os.environ.get('BIGPAW_TEST_CHROMIUM_PATH'):
        subprocess.run(['node',str(Path(os.environ['BIGPAW_TEST_BROWSER_SCRIPT'])),str(context_path)],check=True,timeout=360,env=os.environ.copy())
finally:
    server.write_text(raw)
    if process:process.terminate();process.wait(timeout=5)
    log.close()
    print('TEST_ARTIFACTS',work,flush=True)
