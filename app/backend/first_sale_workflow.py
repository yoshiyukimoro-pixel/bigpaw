"""Additive first-sale benefit and bilateral confirmation workflow.
Installed after build patches; existing invoices and fee acceptances stay intact.
"""
from datetime import datetime, timezone, timedelta
from urllib.parse import urlparse
import hashlib
import json
import re
import secrets
import threading

TERMS = '2026-10-03-first-sale-v2'
CONSENT_TEXT = '成約・お迎え完了・キャンセルについて正確に申告します。運営の確認により虚偽の申告が認められた場合、現在の掲載および今後の新規掲載・再掲載が停止されることに同意します。'
MAIL_LOCK = threading.Lock()
SCHEMA = '''
CREATE TABLE IF NOT EXISTS cancellation_events(
 deal_id TEXT PRIMARY KEY, breeder_id TEXT NOT NULL, puppy_id TEXT NOT NULL, reported_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cancellation_listing_history(
 id TEXT PRIMARY KEY, breeder_id TEXT NOT NULL, puppy_id TEXT NOT NULL, action TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS cancellation_alerts(
 id TEXT PRIMARY KEY, event_key TEXT UNIQUE NOT NULL, breeder_id TEXT NOT NULL,
 reason TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', note TEXT NOT NULL DEFAULT '', created_at INTEGER NOT NULL, reviewed_at INTEGER
);
CREATE TABLE IF NOT EXISTS cancellation_warnings(
 id TEXT PRIMARY KEY, alert_id TEXT UNIQUE NOT NULL, breeder_id TEXT NOT NULL,
 operator_id TEXT NOT NULL, reason TEXT NOT NULL, body TEXT NOT NULL, created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_report_consents(
 id TEXT PRIMARY KEY, deal_id TEXT NOT NULL, user_id TEXT NOT NULL, kind TEXT NOT NULL,
 terms_version TEXT NOT NULL, consent_text TEXT NOT NULL, accepted_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS first_sale_benefits(
 breeder_id TEXT PRIMARY KEY, deal_id TEXT UNIQUE NOT NULL, used_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_fee_decisions(
 deal_id TEXT PRIMARY KEY, breeder_id TEXT NOT NULL, waived INTEGER NOT NULL,
 rate_bps INTEGER NOT NULL, terms_version TEXT NOT NULL, applied_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_confirmations(
 id TEXT PRIMARY KEY, deal_id TEXT NOT NULL, buyer_id TEXT NOT NULL, kind TEXT NOT NULL,
 revision INTEGER NOT NULL, token_hash TEXT UNIQUE NOT NULL, expires_at INTEGER NOT NULL,
 state TEXT NOT NULL DEFAULT 'pending', answer TEXT, answered_at INTEGER,
 payload TEXT NOT NULL, created_at INTEGER NOT NULL, UNIQUE(deal_id,kind,revision)
);
CREATE TABLE IF NOT EXISTS sale_workflow(
 deal_id TEXT PRIMARY KEY, breeder_id TEXT NOT NULL, amount INTEGER NOT NULL,
 pickup_date TEXT NOT NULL DEFAULT '', buyer_name TEXT NOT NULL DEFAULT '', note TEXT NOT NULL DEFAULT '',
 state TEXT NOT NULL, revision INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS sale_disputes(
 id TEXT PRIMARY KEY, deal_id TEXT NOT NULL, confirmation_id TEXT UNIQUE NOT NULL,
 breeder_id TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open', note TEXT NOT NULL DEFAULT '',
 reviewed_by TEXT, created_at INTEGER NOT NULL, reviewed_at INTEGER
);
CREATE TABLE IF NOT EXISTS sale_mail_outbox(
 id TEXT PRIMARY KEY, event_key TEXT UNIQUE NOT NULL, recipient TEXT NOT NULL,
 subject TEXT NOT NULL, body TEXT NOT NULL, sent_at INTEGER, attempts INTEGER NOT NULL DEFAULT 0,
 next_attempt_at INTEGER NOT NULL DEFAULT 0, created_at INTEGER NOT NULL
);
'''


def install(g):
    H = g['Handler']
    db, now, audit, mid = (g[k] for k in ('db', 'now', 'audit', 'make_id'))
    original_init, original_invoice = g['init_db'], g['ensure_commission_invoice']
    original_auto = g['run_automations_once']
    old_get, old_post, old_patch, old_delete = H.do_GET, H.do_POST, H.do_PATCH, H.do_DELETE

    def migrate():
        original_init()
        with db() as c:
            c.executescript(SCHEMA)
            g['ensure_column'](c, 'breeders', 'compliance_suspended', 'INTEGER NOT NULL DEFAULT 0')
            g['ensure_column'](c, 'breeders', 'compliance_note', "TEXT NOT NULL DEFAULT ''")
            # No retrospective fee changes. New applications begin with an unused benefit.
        c.close()

    def enqueue(c, key, email, subject, body):
        if email:
            c.execute('INSERT OR IGNORE INTO sale_mail_outbox(id,event_key,recipient,subject,body,created_at) VALUES(?,?,?,?,?,?)',
                      (mid('so_'), key, email, subject, body, now()))

    def flush_mail():
        MAIL_LOCK.acquire()
        try:
            c = db()
            rows = c.execute('SELECT * FROM sale_mail_outbox WHERE sent_at IS NULL AND next_attempt_at<=? ORDER BY created_at LIMIT 20', (now(),)).fetchall()
            c.close()
            for row in rows:
                sent = g['send_mail'](row['recipient'], row['subject'], row['body'])
                c = db()
                c.execute('UPDATE sale_mail_outbox SET sent_at=?,attempts=attempts+1,next_attempt_at=? WHERE id=?',
                          (now() if sent else None, now()+min(3600, 60*(2**min(row['attempts'],6))), row['id']))
                c.commit(); c.close()
        finally:
            MAIL_LOCK.release()

    def fee_decision(c, d):
        existing = c.execute('SELECT * FROM sale_fee_decisions WHERE deal_id=?', (d['id'],)).fetchone()
        if existing: return existing
        # Called inside BEGIN IMMEDIATE: simultaneous first applications cannot both win.
        c.execute('INSERT OR IGNORE INTO first_sale_benefits VALUES(?,?,?)', (d['breeder_id'], d['id'], now()))
        claim = c.execute('SELECT * FROM first_sale_benefits WHERE breeder_id=?', (d['breeder_id'],)).fetchone()
        waived = int(claim['deal_id'] == d['id'])
        c.execute('INSERT INTO sale_fee_decisions VALUES(?,?,?,?,?,?)',
                  (d['id'], d['breeder_id'], waived, g['COMMISSION_RATE_BPS'], TERMS, now()))
        audit(c, None, 'first_sale_fee_decided', 'deal', d['id'], 'waived' if waived else 'standard')
        return c.execute('SELECT * FROM sale_fee_decisions WHERE deal_id=?', (d['id'],)).fetchone()

    def invoice(c, d):
        if not d or d['status'] != 'completed': return None
        existing = c.execute('SELECT * FROM commission_invoices WHERE deal_id=?', (d['id'],)).fetchone()
        if existing: return existing
        decision = c.execute('SELECT * FROM sale_fee_decisions WHERE deal_id=?', (d['id'],)).fetchone()
        if decision and decision['waived']: return None
        return original_invoice(c, d)

    def notify_ops(c, title, detail, key):
        for op in c.execute("SELECT id,email FROM users WHERE role='operator'").fetchall():
            c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)', (mid('n_'),op['id'],'sale_confirmation',title,detail,0,now()))
            enqueue(c, key+':'+op['id'], op['email'], 'BIG PAW '+title,
                    detail+'\n\n'+g['PUBLIC_BASE_URL']+'/operator-sale-confirmations.html')

    WARNING_TEXT = 'キャンセル申告が続いているため、取引状況を確認しています。成約・お迎え完了・キャンセルは正確にご報告ください。今後、虚偽申告や手数料回避が確認された場合は、掲載を停止します。'

    def cancel_alert(c, breeder, reason, event_key):
        existing=c.execute('SELECT id FROM cancellation_alerts WHERE event_key=?',(event_key,)).fetchone()
        if existing: return
        aid=mid('ca_')
        c.execute('INSERT INTO cancellation_alerts(id,event_key,breeder_id,reason,created_at) VALUES(?,?,?,?,?)',(aid,event_key,breeder,reason,now()))
        name=c.execute('SELECT kennel_name FROM breeders WHERE id=?',(breeder,)).fetchone()['kennel_name']
        notify_ops(c,'キャンセル申告の確認が必要です',name+' / '+reason+'。回数だけでは違反と断定しません。購入者の回答と履歴を確認してください。','cancel-alert:'+aid)

    def monitor_cancel(c,d):
        added=c.execute('INSERT OR IGNORE INTO cancellation_events VALUES(?,?,?,?)',(d['id'],d['breeder_id'],d['puppy_id'],now())).rowcount
        if not added: return
        count=c.execute('SELECT COUNT(*) n FROM cancellation_events WHERE breeder_id=? AND reported_at>=?',(d['breeder_id'],now()-30*86400)).fetchone()['n']
        warning=c.execute('SELECT id FROM cancellation_warnings WHERE breeder_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(d['breeder_id'],)).fetchone()
        if warning: cancel_alert(c,d['breeder_id'],'警告後に新たなキャンセル申告','repeat:'+d['id'])
        elif count>=3: cancel_alert(c,d['breeder_id'],'30日以内に'+str(count)+'件のキャンセル申告','count:'+d['id'])

    def listing_history(c,p,action):
        if not c.execute('SELECT 1 FROM cancellation_events WHERE puppy_id=?',(p['id'],)).fetchone(): return
        hid=mid('ch_')
        c.execute('INSERT INTO cancellation_listing_history VALUES(?,?,?,?,?)',(hid,p['breeder_id'],p['id'],action,now()))
        cancel_alert(c,p['breeder_id'],'キャンセル申告後に子犬掲載を'+action,'listing:'+hid)

    def confirmation(c, d, kind, w):
        revision = w['revision']
        if c.execute('SELECT 1 FROM sale_confirmations WHERE deal_id=? AND kind=? AND revision=?', (d['id'], kind, revision)).fetchone(): return
        c.execute("UPDATE sale_confirmations SET state='superseded' WHERE deal_id=? AND state='pending'", (d['id'],))
        token = secrets.token_urlsafe(32); cid = mid('sc_')
        payload = json.dumps(dict(w), ensure_ascii=False)
        c.execute('INSERT INTO sale_confirmations(id,deal_id,buyer_id,kind,revision,token_hash,expires_at,payload,created_at) VALUES(?,?,?,?,?,?,?,?,?)',
                  (cid,d['id'],d['buyer_id'],kind,revision,hashlib.sha256(token.encode()).hexdigest(),now()+30*86400,payload,now()))
        buyer = c.execute('SELECT email FROM users WHERE id=?', (d['buyer_id'],)).fetchone()
        labels = {'sale':'この子のお迎えが決まりましたか？','pickup':'お迎えは完了しましたか？','cancellation':'今回のお迎えはキャンセルになりましたか？'}
        link = g['PUBLIC_BASE_URL']+'/buyer-sale-confirmation.html?token='+token
        body = labels[kind]+'\n生体価格：'+format(w['amount'], ',')+'円\nお迎え日：'+(w['pickup_date'] or '未定')+'\n\nご本人のBIG PAWアカウントでログインし、下の画面で回答してください。メールを開くだけでは回答されません。\n'+link
        enqueue(c, 'confirm:'+cid, buyer['email'] if buyer else '', 'BIG PAW '+labels[kind], body)
        c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)', (mid('n_'),d['buyer_id'],'sale_confirmation',labels[kind],'マイページの成約確認から回答してください。',0,now()))

    def finalize(c, d, w):
        if c.execute("SELECT 1 FROM sale_workflow WHERE deal_id=? AND state='completed'",(d['id'],)).fetchone(): return
        date = w['pickup_date']; t = now()
        c.execute("UPDATE deals SET status='completed',total_price=? WHERE id=?", (w['amount'], d['id']))
        c.execute("UPDATE puppies SET status='成約済み' WHERE id=?", (d['puppy_id'],))
        c.execute("UPDATE inquiries SET status='成約済み' WHERE id=?", (d['inquiry_id'],))
        pk = c.execute('SELECT id FROM pickups WHERE deal_id=?', (d['id'],)).fetchone()
        if pk: c.execute("UPDATE pickups SET pickup_date=?,status='completed',completed_at=?,updated_at=? WHERE id=?", (date,t,t,pk['id']))
        else: c.execute('INSERT INTO pickups VALUES(?,?,?,?,?,?,?)', (mid('pk_'),d['id'],date,'','completed',t,t))
        c.execute("UPDATE deal_completion_reports SET status='approved',review_note='ブリーダーがお迎え完了を報告',updated_at=? WHERE deal_id=?", (t,d['id']))
        c.execute("UPDATE sale_workflow SET state='completed',updated_at=? WHERE deal_id=?", (t,d['id']))
        inv = invoice(c, c.execute('SELECT * FROM deals WHERE id=?', (d['id'],)).fetchone())
        breeder = c.execute('SELECT u.id,u.email FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?', (d['breeder_id'],)).fetchone()
        if inv:
            text = f"お迎え完了の報告を受け付けました。\n成約手数料：{inv['fee_amount']:,}円（5%・税込）\n請求番号：{inv['invoice_no']}\n支払期限：発行日から7日以内\n"+g['PUBLIC_BASE_URL']+'/breeder-billing.html'
        else:
            text = 'お迎え完了の報告を受け付けました。初回無料特典により成約手数料は0円です。請求書は発行されません。'
        if breeder:
            enqueue(c, 'completed:'+d['id'], breeder['email'], 'BIG PAW お迎え完了・成約手数料のご案内', text)
            c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)', (mid('n_'),breeder['id'],'billing','お迎え完了を確認しました',text,0,t))
        audit(c,None,'breeder_reported_completion','deal',d['id'],'invoice' if inv else 'first_sale_free')

    def blocked(h):
        u = h.current_user()
        if not u or u['role']!='breeder': return False
        c=db(); b=c.execute('SELECT compliance_suspended FROM breeders WHERE user_id=?',(u['id'],)).fetchone(); c.close()
        if b and b['compliance_suspended']:
            h.send_json({'error':'listing_suspended','message':'掲載は停止されています。運営にお問い合わせください。'},403); return True
        return False

    def get(h):
        path=urlparse(h.path).path
        if path not in ('/api/breeder/first-sale-benefit','/api/breeder/sale-workflow','/api/buyer/sale-confirmations','/api/operator/sale-confirmations'):
            return old_get(h)
        role = 'operator' if '/operator/' in path else 'buyer' if '/buyer/' in path else 'breeder'
        u=h.require([role]);
        if not u: return
        c=db()
        try:
            if role=='operator':
                disputes=[dict(r) for r in c.execute('SELECT s.*,b.kennel_name,b.compliance_suspended,sc.kind,sc.answer,sc.payload,p.name puppy_name,u.display_name buyer_display,d.inquiry_id FROM sale_disputes s JOIN breeders b ON b.id=s.breeder_id JOIN sale_confirmations sc ON sc.id=s.confirmation_id JOIN deals d ON d.id=s.deal_id JOIN puppies p ON p.id=d.puppy_id JOIN users u ON u.id=d.buyer_id ORDER BY s.created_at DESC')]
                pending=[dict(r) for r in c.execute("SELECT sc.id,sc.deal_id,sc.kind,sc.state,sc.created_at,b.kennel_name,p.name puppy_name FROM sale_confirmations sc JOIN deals d ON d.id=sc.deal_id JOIN breeders b ON b.id=d.breeder_id JOIN puppies p ON p.id=d.puppy_id WHERE sc.state='pending' ORDER BY sc.created_at")]
                alerts=[dict(r) for r in c.execute('SELECT a.*,b.kennel_name,b.compliance_suspended,(SELECT COUNT(*) FROM cancellation_events e WHERE e.breeder_id=a.breeder_id AND e.reported_at>=?) cancellation_count,(SELECT COUNT(*) FROM cancellation_warnings w WHERE w.breeder_id=a.breeder_id) warning_count FROM cancellation_alerts a JOIN breeders b ON b.id=a.breeder_id ORDER BY a.created_at DESC',(now()-30*86400,))]
                history=[dict(r) for r in c.execute("SELECT e.*,p.name puppy_name,b.kennel_name,w.state,(SELECT answer FROM sale_confirmations sc WHERE sc.deal_id=e.deal_id AND kind='cancellation' ORDER BY revision DESC LIMIT 1) buyer_answer FROM cancellation_events e JOIN puppies p ON p.id=e.puppy_id JOIN breeders b ON b.id=e.breeder_id LEFT JOIN sale_workflow w ON w.deal_id=e.deal_id ORDER BY e.reported_at DESC LIMIT 200")]
                listings=[dict(r) for r in c.execute('SELECT h.*,p.name puppy_name,b.kennel_name FROM cancellation_listing_history h JOIN puppies p ON p.id=h.puppy_id JOIN breeders b ON b.id=h.breeder_id ORDER BY h.created_at DESC LIMIT 200')]
                warnings=[dict(r) for r in c.execute("SELECT w.*,b.kennel_name,o.sent_at,o.attempts FROM cancellation_warnings w JOIN breeders b ON b.id=w.breeder_id LEFT JOIN sale_mail_outbox o ON o.event_key='warning:'||w.id ORDER BY w.created_at DESC LIMIT 200")]
                return h.send_json({'disputes':disputes,'pending':pending,'alerts':alerts,'cancellations':history,'listingHistory':listings,'warnings':warnings,'warningTemplate':WARNING_TEXT})
            if role=='buyer':
                rows=c.execute("SELECT sc.id,sc.deal_id,sc.kind,sc.revision,sc.state,sc.answer,sc.payload,sc.expires_at,p.name puppy_name FROM sale_confirmations sc JOIN deals d ON d.id=sc.deal_id JOIN puppies p ON p.id=d.puppy_id WHERE sc.buyer_id=? AND sc.state!='superseded' ORDER BY sc.created_at DESC",(u['id'],)).fetchall()
                return h.send_json([dict(r) for r in rows])
            b=c.execute('SELECT * FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
            if not b: return h.send_json({'error':'breeder_not_found'},404)
            if path.endswith('first-sale-benefit'):
                claim=c.execute('SELECT * FROM first_sale_benefits WHERE breeder_id=?',(b['id'],)).fetchone()
                return h.send_json({'used':bool(claim),'usedAt':claim['used_at'] if claim else None,'dealId':claim['deal_id'] if claim else None,'rateBps':g['COMMISSION_RATE_BPS'],'termsVersion':TERMS,'listingSuspended':bool(b['compliance_suspended'])})
            rows=c.execute('SELECT w.*,p.name puppy_name,f.waived FROM sale_workflow w JOIN deals d ON d.id=w.deal_id JOIN puppies p ON p.id=d.puppy_id LEFT JOIN sale_fee_decisions f ON f.deal_id=w.deal_id WHERE w.breeder_id=? ORDER BY w.updated_at DESC',(b['id'],)).fetchall()
            return h.send_json([dict(r) for r in rows])
        finally: c.close()

    def post(h):
        path=urlparse(h.path).path
        m=re.fullmatch(r'/api/deals/([^/]+)/(sale-report|completion-report|cancel-report)',path)
        answer_path=path=='/api/buyer/sale-confirmations/answer'
        if not m and not answer_path:
            if re.fullmatch(r'/api/deals/[^/]+/pickup',path):
                c=db(); exists=c.execute('SELECT 1 FROM sale_workflow WHERE deal_id=?',(path.split('/')[-2],)).fetchone(); c.close()
                if exists: return h.send_json({'error':'use_sale_workflow','message':'お迎え完了は成約確認画面から報告してください。'},409)
            if path=='/api/puppies' and blocked(h): return
            return old_post(h)
        if not h.mutation_origin_allowed(): return h.send_json({'error':'invalid_origin'},403)
        u=h.require(['buyer'] if answer_path else ['breeder'])
        if not u: return
        body=h.json_body()
        if not isinstance(body,dict): return h.send_json({'error':'invalid_body'},400)
        c=db()
        try:
            c.execute('BEGIN IMMEDIATE')
            if answer_path:
                if body.get('answer') not in ('yes','no'): return h.send_json({'error':'invalid_answer'},400)
                if body.get('token'):
                    sc=c.execute('SELECT * FROM sale_confirmations WHERE token_hash=?',(hashlib.sha256(str(body['token']).encode()).hexdigest(),)).fetchone()
                else:
                    sc=c.execute('SELECT * FROM sale_confirmations WHERE id=?',(str(body.get('id','')),)).fetchone()
                if not sc or sc['buyer_id']!=u['id']: return h.send_json({'error':'not_found'},404)
                if sc['state']=='answered':
                    if sc['answer']!=body['answer']: return h.send_json({'error':'answer_already_recorded'},409)
                    return h.send_json({'ok':True,'alreadyAnswered':True})
                if sc['state']!='pending' or sc['expires_at']<now(): return h.send_json({'error':'confirmation_expired_or_replaced'},409)
                d=c.execute('SELECT * FROM deals WHERE id=?',(sc['deal_id'],)).fetchone()
                w=c.execute('SELECT * FROM sale_workflow WHERE deal_id=?',(sc['deal_id'],)).fetchone()
                if not w or sc['revision']!=w['revision']: return h.send_json({'error':'confirmation_replaced'},409)
                c.execute("UPDATE sale_confirmations SET state='answered',answer=?,answered_at=? WHERE id=?",(body['answer'],now(),sc['id']))
                if body['answer']=='no':
                    dispute_id=mid('sd_')
                    c.execute('INSERT INTO sale_disputes(id,deal_id,confirmation_id,breeder_id,created_at) VALUES(?,?,?,?,?)',(dispute_id,d['id'],sc['id'],d['breeder_id'],now()))
                    c.execute("UPDATE sale_workflow SET state='disputed',updated_at=? WHERE deal_id=?",(now(),d['id']))
                    c.execute("UPDATE commission_invoices SET status='review_hold' WHERE deal_id=? AND status='issued'",(d['id'],))
                    g['sync_breeder_billing_suspension'](c,d['breeder_id'])
                    notify_ops(c,'成約報告と購入者の回答が食い違っています', '取引 '+d['id']+' / '+sc['kind']+'。内容を確認してください。','dispute:'+dispute_id)
                elif sc['kind']=='pickup':
                    audit(c,u['id'],'buyer_confirmed_pickup','deal',d['id'],'yes')
                elif sc['kind']=='sale': c.execute("UPDATE sale_workflow SET state='sale_confirmed',updated_at=? WHERE deal_id=?",(now(),d['id']))
                else:
                    c.execute("UPDATE sale_workflow SET state='cancelled',updated_at=? WHERE deal_id=?",(now(),d['id']))
                    c.execute("UPDATE deals SET status='cancelled' WHERE id=?",(d['id'],))
                    c.execute("UPDATE deal_completion_reports SET status='cancelled',updated_at=? WHERE deal_id=?",(now(),d['id']))
                    c.execute("UPDATE inquiries SET status='キャンセル' WHERE id=?",(d['inquiry_id'],))
                    c.execute("UPDATE puppies SET status='募集中' WHERE id=? AND status='商談中'",(d['puppy_id'],))
                audit(c,u['id'],'buyer_sale_confirmation','deal',sc['deal_id'],sc['kind']+':'+body['answer'])
                c.commit(); return h.send_json({'ok':True})
            d=h.deal_for_user(c,m.group(1),u)
            if not d: return h.send_json({'error':'not_found'},404)
            if d['status']=='completed':
                if m.group(2)=='completion-report': return h.send_json({'ok':True,'dealId':d['id'],'state':'completed','alreadySubmitted':True})
                return h.send_json({'error':'deal_already_completed'},409)
            w=c.execute('SELECT * FROM sale_workflow WHERE deal_id=?',(d['id'],)).fetchone()
            kind={'sale-report':'sale','completion-report':'pickup','cancel-report':'cancellation'}[m.group(2)]
            if body.get('agreeAccurateReporting') is not True:
                return h.send_json({'error':'accurate_reporting_consent_required','message':'正確な申告と、虚偽申告が確認された場合の掲載停止について同意してください。'},400)
            if w and w['state']=='cancelled': return h.send_json({'error':'cancelled_deal_locked','message':'キャンセル済みの取引は再申請できません。新しい問い合わせから手続きしてください。'},409)
            if w and w['state']=='disputed': return h.send_json({'error':'operator_review_required'},409)
            if kind=='cancellation':
                if not w: return h.send_json({'error':'sale_report_required'},409)
                amount,date,buyer,note=w['amount'],w['pickup_date'],w['buyer_name'],str(body.get('note',''))[:1000]
            else:
                if body.get('agreeFirstSaleTerms') is not True: return h.send_json({'error':'first_sale_terms_required','message':'初回無料特典は申請時に使用され、キャンセルしても戻らないことを確認してください。'},400)
                try:
                    amount=int(body.get('finalSaleAmount',0))
                    if amount<=0 or amount>100000000: raise ValueError()
                    date=str(body.get('pickupDate',''))
                    if date:
                        parsed=datetime.strptime(date,'%Y-%m-%d').date()
                        if kind=='pickup' and parsed>datetime.now(timezone(timedelta(hours=9))).date(): raise ValueError()
                    elif kind=='pickup': raise ValueError()
                except (TypeError,ValueError): return h.send_json({'error':'invalid_price_or_pickup_date'},400)
                buyer=str(body.get('buyerName',''))[:200]; note=str(body.get('note',''))[:1000]
            state={'sale':'sale_pending','pickup':'pickup_pending','cancellation':'cancellation_pending'}[kind]
            if w and w['state']==state and w['amount']==amount and w['pickup_date']==date and w['buyer_name']==buyer and w['note']==note:
                pending=c.execute("SELECT expires_at FROM sale_confirmations WHERE deal_id=? AND state='pending'",(d['id'],)).fetchone()
                if pending and pending['expires_at']>=now():
                    return h.send_json({'ok':True,'dealId':d['id'],'state':state,'alreadySubmitted':True})
            decision=fee_decision(c,d) if kind!='cancellation' else c.execute('SELECT * FROM sale_fee_decisions WHERE deal_id=?',(d['id'],)).fetchone()
            c.execute('INSERT INTO sale_report_consents VALUES(?,?,?,?,?,?,?)',(mid('consent_'),d['id'],u['id'],kind,TERMS,CONSENT_TEXT,now()))
            revision=(w['revision'] if w else 0)+1
            c.execute('INSERT INTO sale_workflow VALUES(?,?,?,?,?,?,?,?,?) ON CONFLICT(deal_id) DO UPDATE SET amount=excluded.amount,pickup_date=excluded.pickup_date,buyer_name=excluded.buyer_name,note=excluded.note,state=excluded.state,revision=excluded.revision,updated_at=excluded.updated_at',
                      (d['id'],d['breeder_id'],amount,date,buyer,note,state,revision,now()))
            if kind=='pickup':
                c.execute("INSERT INTO deal_completion_reports(id,deal_id,breeder_id,reported_by_user_id,final_sale_amount,pickup_date,buyer_name,note,status,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,'pending',?,?) ON CONFLICT(deal_id) DO UPDATE SET final_sale_amount=excluded.final_sale_amount,pickup_date=excluded.pickup_date,buyer_name=excluded.buyer_name,note=excluded.note,status='pending',updated_at=excluded.updated_at", (mid('cr_'),d['id'],d['breeder_id'],u['id'],amount,date,buyer,note,now(),now()))
            c.execute('UPDATE deals SET status=? WHERE id=?',(state,d['id']))
            c.execute("UPDATE puppies SET status='商談中' WHERE id=? AND status='募集中'",(d['puppy_id'],))
            fresh=c.execute('SELECT * FROM sale_workflow WHERE deal_id=?',(d['id'],)).fetchone()
            confirmation(c,d,kind,fresh)
            if kind=='pickup': finalize(c,d,fresh)
            if kind=='cancellation': monitor_cancel(c,d)
            audit(c,u['id'],'breeder_sale_report','deal',d['id'],kind)
            c.commit(); return h.send_json({'ok':True,'dealId':d['id'],'state':'completed' if kind=='pickup' else state,'waived':bool(decision['waived'])})
        finally:
            c.close()
            # Send outside DB write transaction; failed mail remains queued for retry.
            threading.Thread(target=flush_mail,daemon=True).start()

    def patch(h):
        path=urlparse(h.path).path
        am=re.fullmatch(r'/api/operator/cancellation-alerts/([^/]+)',path)
        if am:
            if not h.mutation_origin_allowed(): return h.send_json({'error':'invalid_origin'},403)
            u=h.require(['operator'])
            if not u: return
            body=h.json_body()
            if not isinstance(body,dict): return h.send_json({'error':'invalid_body'},400)
            action=body.get('action');note=str(body.get('note','')).strip()[:1000]
            if action not in ('warn','suspend','dismiss') or not note: return h.send_json({'error':'action_and_review_note_required'},400)
            c=db()
            try:
                c.execute('BEGIN IMMEDIATE')
                a=c.execute('SELECT * FROM cancellation_alerts WHERE id=?',(am.group(1),)).fetchone()
                if not a: return h.send_json({'error':'not_found'},404)
                if a['status']!='open': return h.send_json({'error':'already_reviewed'},409)
                if action=='warn':
                    text=str(body.get('message','')).strip()
                    if not text or len(text)>4000: return h.send_json({'error':'warning_message_required'},400)
                    b=c.execute('SELECT u.email,u.id FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?',(a['breeder_id'],)).fetchone()
                    if not b or not b['email']: return h.send_json({'error':'recipient_missing'},409)
                    wid=mid('cw_')
                    c.execute('INSERT INTO cancellation_warnings VALUES(?,?,?,?,?,?,?)',(wid,a['id'],a['breeder_id'],u['id'],note,text,now()))
                    enqueue(c,'warning:'+wid,b['email'],'BIG PAW キャンセル申告に関するご確認・警告',text+'\n\n'+g['PUBLIC_BASE_URL']+'/breeder-deal-report.html')
                    c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(mid('n_'),b['id'],'compliance','キャンセル申告に関するご確認・警告',text,0,now()))
                elif action=='suspend':
                    c.execute('UPDATE breeders SET compliance_suspended=1,compliance_note=? WHERE id=?',(note,a['breeder_id']))
                c.execute('UPDATE cancellation_alerts SET status=?,note=?,reviewed_at=? WHERE id=?',(action,note,now(),a['id']))
                audit(c,u['id'],'cancellation_alert_reviewed','breeder',a['breeder_id'],action+':'+note)
                c.commit();return h.send_json({'ok':True,'mailQueued':action=='warn'})
            finally:
                c.close();threading.Thread(target=flush_mail,daemon=True).start()
        m=re.fullmatch(r'/api/operator/sale-disputes/([^/]+)',path)
        resume=re.fullmatch(r'/api/operator/breeders/([^/]+)/compliance-resume',path)
        if m or resume:
            if not h.mutation_origin_allowed(): return h.send_json({'error':'invalid_origin'},403)
            u=h.require(['operator'])
            if not u: return
            body=h.json_body(); note=str(body.get('note','')).strip()[:1000]
            if not note: return h.send_json({'error':'review_note_required'},400)
            c=db()
            try:
                c.execute('BEGIN IMMEDIATE')
                if resume:
                    b=c.execute('SELECT id FROM breeders WHERE id=?',(resume.group(1),)).fetchone()
                    if not b: return h.send_json({'error':'not_found'},404)
                    c.execute("UPDATE breeders SET compliance_suspended=0,compliance_note=? WHERE id=?",(note,b['id']))
                    audit(c,u['id'],'breeder_compliance_resumed','breeder',b['id'],note)
                else:
                    action=body.get('action')
                    if action not in ('confirmed_false','dismiss','confirmed_cancelled','confirmed_pickup'): return h.send_json({'error':'invalid_action'},400)
                    dispute=c.execute('SELECT * FROM sale_disputes WHERE id=?',(m.group(1),)).fetchone()
                    if not dispute: return h.send_json({'error':'not_found'},404)
                    if dispute['status']!='open' and not ((dispute['status']=='confirmed_false' and action in ('confirmed_cancelled','confirmed_pickup')) or (dispute['status'] in ('confirmed_cancelled','confirmed_pickup') and action=='confirmed_false')): return h.send_json({'error':'already_reviewed'},409)
                    if action=='confirmed_pickup':
                        sc=c.execute('SELECT kind FROM sale_confirmations WHERE id=?',(dispute['confirmation_id'],)).fetchone()
                        if sc['kind']!='pickup' or c.execute("SELECT 1 FROM sale_workflow WHERE deal_id=? AND state='cancelled'",(dispute['deal_id'],)).fetchone(): return h.send_json({'error':'pickup_report_required'},409)
                    c.execute('UPDATE sale_disputes SET status=?,note=?,reviewed_by=?,reviewed_at=? WHERE id=?',(action,note,u['id'],now(),dispute['id']))
                    if action in ('confirmed_cancelled','confirmed_pickup'):
                        if action=='confirmed_cancelled':
                            paid=c.execute("SELECT 1 FROM commission_invoices WHERE deal_id=? AND status='paid'",(dispute['deal_id'],)).fetchone()
                            if paid: return h.send_json({'error':'paid_invoice_requires_refund_review'},409)
                            c.execute("UPDATE commission_invoices SET status='void',note=? WHERE deal_id=? AND status IN ('issued','review_hold')",(note,dispute['deal_id']))
                            c.execute("UPDATE deals SET status='cancelled' WHERE id=?",(dispute['deal_id'],))
                            c.execute("UPDATE sale_workflow SET state='cancelled',updated_at=? WHERE deal_id=?",(now(),dispute['deal_id']))
                            c.execute("UPDATE puppies SET status='募集中' WHERE id=(SELECT puppy_id FROM deals WHERE id=?)",(dispute['deal_id'],))
                            c.execute("UPDATE inquiries SET status='キャンセル' WHERE id=(SELECT inquiry_id FROM deals WHERE id=?)",(dispute['deal_id'],))
                        else:
                            c.execute("UPDATE commission_invoices SET status='issued',due_at=? WHERE deal_id=? AND status='review_hold'",(now()+g['COMMISSION_DUE_DAYS']*86400,dispute['deal_id']))
                            c.execute("UPDATE sale_workflow SET state='completed',updated_at=? WHERE deal_id=?",(now(),dispute['deal_id']))
                        g['sync_breeder_billing_suspension'](c,dispute['breeder_id'])
                    elif action=='confirmed_false':
                        c.execute('UPDATE breeders SET compliance_suspended=1,compliance_note=? WHERE id=?',(note,dispute['breeder_id']))
                        b=c.execute('SELECT user_id FROM breeders WHERE id=?',(dispute['breeder_id'],)).fetchone()
                        c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(mid('n_'),b['user_id'],'compliance','掲載を停止しました',note,0,now()))
                    else:
                        if c.execute("SELECT 1 FROM commission_invoices WHERE deal_id=? AND status IN ('review_hold','paid')",(dispute['deal_id'],)).fetchone():
                            return h.send_json({'error':'choose_pickup_or_cancellation_resolution'},409)
                        # Operator resolves the mismatch; breeder may correct and reapply. No automatic charge.
                        c.execute("UPDATE sale_workflow SET state='needs_correction',updated_at=? WHERE deal_id=?",(now(),dispute['deal_id']))
                        c.execute("UPDATE sale_confirmations SET state='superseded' WHERE deal_id=? AND state='pending'",(dispute['deal_id'],))
                    audit(c,u['id'],'sale_dispute_reviewed','deal',dispute['deal_id'],str(action)+':'+note)
                c.commit(); return h.send_json({'ok':True})
            finally: c.close()
        im=re.fullmatch(r'/api/operator/invoices/([^/]+)',path)
        if im:
            u=h.require(['operator'])
            if not u: return
            c=db(); inv=c.execute('SELECT status FROM commission_invoices WHERE id=?',(im.group(1),)).fetchone(); c.close()
            if inv and inv['status']=='review_hold':
                return h.send_json({'error':'invoice_review_hold','message':'食い違いの確認画面で事実を確認してください。保留中は督促できません。'},409)
        if re.fullmatch(r'/api/operator/deal-reports/[^/]+',path):
            # New workflow must not bypass unanswered or disputed buyer confirmation.
            c=db(); r=c.execute('SELECT w.state FROM sale_workflow w JOIN deal_completion_reports r ON r.deal_id=w.deal_id WHERE r.id=?',(path.rsplit('/',1)[-1],)).fetchone(); c.close()
            if r:
                u=h.require(['operator'])
                if not u: return
                return h.send_json({'error':'buyer_confirmation_required','message':'購入者の確認待ちです。食い違いは成約確認画面で対応してください。'},409)
        pm=re.fullmatch(r'/api/puppies/([^/]+)',path)
        if pm:
            if blocked(h): return
            c=db();before=c.execute('SELECT * FROM puppies WHERE id=?',(pm.group(1),)).fetchone();c.close()
            send=h.send_json;responses=[]
            h.send_json=lambda *args,**kwargs: responses.append((args,kwargs))
            try: result=old_patch(h)
            finally: h.send_json=send
            if before:
                c=db()
                try:
                    after=c.execute('SELECT * FROM puppies WHERE id=?',(pm.group(1),)).fetchone()
                    if after and before['status']!=after['status'] and after['status']=='非公開':
                        listing_history(c,before,'非公開化');c.commit()
                finally: c.close()
                threading.Thread(target=flush_mail,daemon=True).start()
            for args,kwargs in responses: send(*args,**kwargs)
            return result
        return old_patch(h)

    def delete(h):
        path=urlparse(h.path).path
        if re.fullmatch(r'/api/puppies/[^/]+',path):
            # Retain deal, fee and confirmation history. A listing with a deal is archived instead.
            u=h.require(['breeder','operator'])
            if not u: return
            c=db()
            try:
                p=c.execute('SELECT * FROM puppies WHERE id=?',(path.rsplit('/',1)[-1],)).fetchone()
                if p and c.execute('SELECT 1 FROM deals WHERE puppy_id=?',(p['id'],)).fetchone():
                    if not h.mutation_origin_allowed(): return h.send_json({'error':'invalid_origin'},403)
                    b=c.execute('SELECT id FROM breeders WHERE user_id=?',(u['id'],)).fetchone()
                    if u['role']!='operator' and (not b or b['id']!=p['breeder_id']): return h.send_json({'error':'forbidden'},403)
                    if p['review_status']!='archived': listing_history(c,p,'削除（履歴保存）')
                    c.execute("UPDATE puppies SET review_status='archived' WHERE id=?",(p['id'],)); audit(c,u['id'],'puppy_archived_with_deal','puppy',p['id']); c.commit()
                    return h.send_json({'ok':True,'archived':True})
            finally:
                c.close();threading.Thread(target=flush_mail,daemon=True).start()
        return old_delete(h)

    def auto():
        result=original_auto(); flush_mail(); return result

    g['init_db']=migrate
    g['ensure_commission_invoice']=invoice
    g['run_automations_once']=auto
    H.do_GET, H.do_POST, H.do_PATCH, H.do_DELETE = get, post, patch, delete
