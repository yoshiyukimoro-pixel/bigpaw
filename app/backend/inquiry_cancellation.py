"""Inquiry-scoped cancellation with capability links and retained audit history."""
import hashlib
import json
import re
import secrets
import threading
from urllib.parse import urlparse, parse_qs

BREEDER_REASONS = {
    'buyer_withdrew': '見学前に購入希望者から辞退',
    'breeder_declined': '見学前にブリーダー側から中止',
    'visit_not_held': '見学予定だったが見学に至らなかった',
    'visited_no_contract': '見学したが契約には至らなかった',
    'another_puppy': '別の子犬を検討することになった',
    'unreachable': '連絡が取れなくなった',
    'other': 'その他',
}
BUYER_REASONS = {
    'before_visit': '見学前に取引を中止した',
    'visit_not_held': '見学予定だったが見学しなかった',
    'visited_no_contract': '見学したが契約には至らなかった',
    'another_puppy': '別の子犬を検討することになった',
    'negotiating': 'まだ検討・商談中',
    'purchased': 'すでに契約・購入した',
    'other': 'その他',
}
MATCH = {'buyer_withdrew':'before_visit', 'breeder_declined':'before_visit',
         'visit_not_held':'visit_not_held', 'visited_no_contract':'visited_no_contract',
         'another_puppy':'another_puppy'}
SCHEMA = '''
CREATE TABLE IF NOT EXISTS inquiry_cancellations(
 id TEXT PRIMARY KEY, inquiry_id TEXT NOT NULL REFERENCES inquiries(id),
 breeder_id TEXT NOT NULL, buyer_id TEXT NOT NULL,
 breeder_reason TEXT NOT NULL, breeder_note TEXT NOT NULL DEFAULT '',
 buyer_reason TEXT, buyer_note TEXT NOT NULL DEFAULT '',
 state TEXT NOT NULL DEFAULT 'buyer_pending', previous_inquiry_status TEXT NOT NULL,
 previous_deal_status TEXT, previous_workflow_state TEXT,
 token_hash TEXT UNIQUE NOT NULL, expires_at INTEGER NOT NULL,
 created_at INTEGER NOT NULL, answered_at INTEGER, reviewed_at INTEGER,
 reviewed_by TEXT, review_action TEXT, review_note TEXT NOT NULL DEFAULT ''
);
CREATE UNIQUE INDEX IF NOT EXISTS inquiry_cancellation_active
 ON inquiry_cancellations(inquiry_id) WHERE state IN ('buyer_pending','operator_review','unanswered');
CREATE INDEX IF NOT EXISTS inquiry_cancellation_breeder ON inquiry_cancellations(breeder_id,created_at);
CREATE TABLE IF NOT EXISTS inquiry_cancellation_history(
 id TEXT PRIMARY KEY, request_id TEXT NOT NULL REFERENCES inquiry_cancellations(id),
 actor_id TEXT, action TEXT NOT NULL, detail TEXT NOT NULL, created_at INTEGER NOT NULL
);
'''


def install(g):
    H=g['Handler']; db,now,mid,audit=(g[k] for k in ('db','now','make_id','audit'))
    old_init,old_auto=g['init_db'],g['run_automations_once']
    old_get,old_post,old_patch=H.do_GET,H.do_POST,H.do_PATCH
    base=lambda:g['PUBLIC_BASE_URL']

    def migrate():
        old_init()
        c=db()
        try:
            # Snapshot existing data before the first additive schema migration.
            if not c.execute("SELECT 1 FROM sqlite_master WHERE name='inquiry_cancellations'").fetchone():
                import sqlite3
                target=g['BACKUPS']/('before-inquiry-cancellation-'+str(now())+'.sqlite3')
                backup=sqlite3.connect(target)
                try:c.backup(backup)
                finally:backup.close()
            c.executescript(SCHEMA); c.commit()
        finally:c.close()
        print('INQUIRY_CANCELLATION_READY|schema=additive|reasons=required|buyer_link=7days|unanswered=operator_review',flush=True)

    def queue(c,key,email,subject,body):
        if email:c.execute('INSERT OR IGNORE INTO sale_mail_outbox(id,event_key,recipient,subject,body,created_at) VALUES(?,?,?,?,?,?)',
                           (mid('so_'),key,email,'BIG PAW '+subject,body,now()))

    def history(c,r,actor,action,detail):
        c.execute('INSERT INTO inquiry_cancellation_history VALUES(?,?,?,?,?,?)',
                  (mid('ich_'),r['id'],actor,action,detail,now()))
        audit(c,actor,'inquiry_cancellation_'+action,'inquiry',r['inquiry_id'],detail)

    def notify(c,r,title,ops=False):
        url=base()+'/operator-cancellations.html' if ops else base()+'/breeder-cancellation.html?inquiry='+r['inquiry_id']
        users=c.execute("SELECT id,email FROM users WHERE role='operator'").fetchall() if ops else c.execute('SELECT u.id,u.email FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?',(r['breeder_id'],)).fetchall()
        for u in users:
            c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(mid('n_'),u['id'],'inquiry_cancellation',title,'問い合わせ '+r['inquiry_id']+' / '+url,0,now()))
            # Operator notifications go to the support mailbox configured for BIG PAW.
            email=g.get('BIGPAW_SUPPORT_EMAIL') or __import__('os').environ.get('BIGPAW_SUPPORT_EMAIL') or u['email']
            queue(c,'ic:'+r['id']+':'+title+':'+u['id'],email if ops else u['email'],title,'問い合わせ '+r['inquiry_id']+'\n'+url)

    def risky(c,q):
        d=c.execute('SELECT * FROM deals WHERE inquiry_id=?',(q['id'],)).fetchone()
        if not d:return False
        return bool(d['status']=='completed' or
            c.execute("SELECT 1 FROM payments WHERE deal_id=? AND status='paid'",(d['id'],)).fetchone() or
            c.execute('SELECT 1 FROM contracts WHERE deal_id=? AND (buyer_signed_at IS NOT NULL OR breeder_signed_at IS NOT NULL)',(d['id'],)).fetchone() or
            c.execute("SELECT 1 FROM commission_invoices WHERE deal_id=? AND status!='void'",(d['id'],)).fetchone())

    def finish(c,r,actor):
        d=c.execute('SELECT * FROM deals WHERE inquiry_id=?',(r['inquiry_id'],)).fetchone()
        if d:
            if c.execute("SELECT 1 FROM commission_invoices WHERE deal_id=? AND status='paid'",(d['id'],)).fetchone():
                return False
            c.execute("UPDATE deals SET status='cancelled' WHERE id=?",(d['id'],))
            c.execute("UPDATE sale_workflow SET state='cancelled',updated_at=? WHERE deal_id=?",(now(),d['id']))
            c.execute("UPDATE sale_confirmations SET state='superseded' WHERE deal_id=? AND state='pending'",(d['id'],))
            c.execute("UPDATE deal_completion_reports SET status='cancelled',updated_at=? WHERE deal_id=?",(now(),d['id']))
            c.execute("UPDATE commission_invoices SET status='void',note=? WHERE deal_id=? AND status IN ('issued','review_hold')",('取引中止を運営確認：'+r['review_note'],d['id']))
            g['sync_breeder_billing_suspension'](c,r['breeder_id'])
        c.execute("UPDATE visits SET status='cancelled',updated_at=? WHERE inquiry_id=?",(now(),r['inquiry_id']))
        c.execute("UPDATE inquiries SET status='取引終了' WHERE id=?",(r['inquiry_id'],))
        c.execute("UPDATE inquiry_cancellations SET state='closed' WHERE id=?",(r['id'],))
        # No automatic relisting: another customer's ongoing deal must not be changed.
        history(c,r,actor,'closed','双方確認または運営判断により取引終了')
        notify(c,r,'取引中止を確認しました')
        queue(c,'ic-closed:'+r['id'],c.execute('SELECT email FROM users WHERE id=?',(r['buyer_id'],)).fetchone()['email'],
              '取引中止を確認しました','取引中止の確認が完了しました。問い合わせ・回答履歴は保存されています。\n'+base()+'/messages.html?inquiry='+r['inquiry_id'])
        return True

    def view(c,r,public=False):
        out=dict(r)
        out.pop('token_hash',None)
        q=c.execute('SELECT i.*,p.name puppy_name,p.breed,b.kennel_name FROM inquiries i JOIN puppies p ON p.id=i.puppy_id LEFT JOIN breeders b ON b.id=i.breeder_id WHERE i.id=?',(r['inquiry_id'],)).fetchone()
        out.update(puppy_name=q['puppy_name'],breed=q['breed'],breeder_reason_label=BREEDER_REASONS.get(r['breeder_reason'],''),buyer_reason_label=BUYER_REASONS.get(r['buyer_reason'],''))
        if public:
            # A forwarded capability link never discloses contact info or internal comments.
            return {k:out[k] for k in ('id','puppy_name','breed','breeder_reason_label','buyer_reason_label','state','expires_at','answered_at')}
        out.update(buyer_name=q['name'],kennel_name=q['kennel_name'],financial_review=risky(c,q))
        out['history']=[dict(x) for x in c.execute('SELECT actor_id,action,detail,created_at FROM inquiry_cancellation_history WHERE request_id=? ORDER BY created_at,rowid',(r['id'],))]
        sent=c.execute("SELECT sent_at,attempts FROM sale_mail_outbox WHERE event_key=?",('ic-confirm:'+r['id'],)).fetchone()
        out['mail']=dict(sent) if sent else None
        return out

    def lookup(c,token):
        if not isinstance(token,str) or len(token)<40 or len(token)>100:return None
        return c.execute('SELECT * FROM inquiry_cancellations WHERE token_hash=?',(hashlib.sha256(token.encode()).hexdigest(),)).fetchone()

    def expire(c):
        rows=c.execute("SELECT * FROM inquiry_cancellations WHERE state='buyer_pending' AND expires_at<?",(now(),)).fetchall()
        for r in rows:
            c.execute("UPDATE inquiry_cancellations SET state='unanswered' WHERE id=?",(r['id'],))
            c.execute("UPDATE inquiries SET status='取引中止・運営確認中' WHERE id=?",(r['inquiry_id'],))
            history(c,r,None,'unanswered','7日間未回答。自動終了しません。')
            notify(c,r,'取引中止の確認が未回答です',True)
        return len(rows)

    def get(h):
        path=urlparse(h.path).path
        m=re.fullmatch(r'/api/inquiries/([^/]+)/cancellation',path)
        if path not in ('/api/operator/inquiry-cancellations','/api/buyer/inquiry-cancellations','/api/cancellation-confirmation') and not m:return old_get(h)
        c=db()
        try:
            if path=='/api/cancellation-confirmation':return h.send_json({'error':'use_post_view'},405)
            u=h.require(['operator'] if '/operator/' in path else ['buyer'] if '/buyer/' in path else ['breeder','buyer','operator'])
            if not u:return
            expire(c);c.commit()
            if m:
                q=h.inquiry_for_user(c,m.group(1),u)
                if not q:return h.send_json({'error':'not_found'},404)
                r=c.execute('SELECT * FROM inquiry_cancellations WHERE inquiry_id=? ORDER BY created_at DESC,rowid DESC LIMIT 1',(q['id'],)).fetchone()
                return h.send_json({'request':view(c,r,u['role']=='buyer') if r else None,'puppy_name':c.execute('SELECT name FROM puppies WHERE id=?',(q['puppy_id'],)).fetchone()['name'],'inquiry_status':q['status'],'breederReasons':BREEDER_REASONS,'buyerReasons':BUYER_REASONS})
            sql='SELECT * FROM inquiry_cancellations';args=()
            if u['role']=='buyer':sql+=' WHERE buyer_id=?';args=(u['id'],)
            rows=c.execute(sql+' ORDER BY created_at DESC,rowid DESC',args).fetchall()
            return h.send_json({'requests':[view(c,r,u['role']=='buyer') for r in rows],'buyerReasons':BUYER_REASONS})
        finally:c.close()

    def post(h):
        path=urlparse(h.path).path
        m=re.fullmatch(r'/api/inquiries/([^/]+)/cancellation',path)
        answer=path=='/api/cancellation-confirmation/answer'
        public_view=path=='/api/cancellation-confirmation/view'
        resend=re.fullmatch(r'/api/operator/inquiry-cancellations/([^/]+)/resend',path)
        if re.fullmatch(r'/api/deals/[^/]+/cancel-report',path):
            return h.send_json({'error':'use_inquiry_cancellation','message':'問い合わせの「取引中止を申請」から理由を選択してください。'},409)
        if not m and not answer and not public_view and not resend:
            if mutation_guard(h,path):return
            return old_post(h)
        if not h.mutation_origin_allowed():return h.send_json({'error':'invalid_origin'},403)
        u=None if (answer or public_view) else h.require(['operator'] if resend else ['breeder'])
        if not answer and not public_view and not u:return
        body=h.json_body()
        if not isinstance(body,dict):return h.send_json({'error':'invalid_body'},400)
        c=db()
        try:
            c.execute('BEGIN IMMEDIATE')
            if public_view:
                r=lookup(c,body.get('token'))
                if not r:return h.send_json({'message':'確認リンクが無効です。BIG PAW運営へお問い合わせください。'},404)
                return h.send_json(view(c,r,True))
            if answer:
                r=lookup(c,body.get('token'))
                if not r:
                    u=h.require(['buyer'])
                    if not u:return
                    r=c.execute('SELECT * FROM inquiry_cancellations WHERE id=? AND buyer_id=?',(str(body.get('id','')),u['id'])).fetchone()
                if not r:return h.send_json({'error':'not_found'},404)
                reason=body.get('reason');note=body.get('note','')
                if not isinstance(reason,str) or reason not in BUYER_REASONS or not isinstance(note,str) or len(note)>1000 or (reason=='other' and not note.strip()):return h.send_json({'message':'状況を選択してください。「その他」は補足を入力してください。'},400)
                if r['buyer_reason']:
                    if r['buyer_reason']==reason and r['buyer_note']==note.strip():return h.send_json({'ok':True,'state':r['state'],'alreadyAnswered':True})
                    return h.send_json({'message':'回答は保存済みです。変更が必要な場合は運営へお問い合わせください。'},409)
                if r['state']!='buyer_pending' or r['expires_at']<now():return h.send_json({'message':'回答期限が過ぎています。BIG PAW運営へお問い合わせください。'},409)
                c.execute('UPDATE inquiry_cancellations SET buyer_reason=?,buyer_note=?,answered_at=? WHERE id=?',(reason,note.strip(),now(),r['id']))
                history(c,r,u['id'] if u else r['buyer_id'],'buyer_answered',json.dumps({'reason':reason,'note':note.strip(),'via':'account' if u else 'email_link'},ensure_ascii=False))
                q=c.execute('SELECT * FROM inquiries WHERE id=?',(r['inquiry_id'],)).fetchone()
                if MATCH.get(r['breeder_reason'])==reason and not risky(c,q):finish(c,r,r['buyer_id'])
                else:
                    c.execute("UPDATE inquiry_cancellations SET state='operator_review' WHERE id=?",(r['id'],))
                    c.execute("UPDATE inquiries SET status='取引中止・運営確認中' WHERE id=?",(r['inquiry_id'],))
                    notify(c,r,'取引中止申請の確認が必要です',True)
                    notify(c,r,'取引中止申請は運営確認中です')
                c.commit();return h.send_json({'ok':True,'state':c.execute('SELECT state FROM inquiry_cancellations WHERE id=?',(r['id'],)).fetchone()['state']})
            if resend:
                r=c.execute('SELECT * FROM inquiry_cancellations WHERE id=?',(resend.group(1),)).fetchone()
                if not r:return h.send_json({'error':'not_found'},404)
                if r['state'] not in ('unanswered','buyer_pending'):return h.send_json({'message':'再送できるのは未回答の申請だけです。'},409)
                if r['state']=='buyer_pending' and now()-r['created_at']<60:return h.send_json({'message':'送信直後です。少し待ってから再送してください。'},429)
                token=secrets.token_urlsafe(32)
                c.execute("UPDATE inquiry_cancellations SET token_hash=?,expires_at=?,state='buyer_pending' WHERE id=?",(hashlib.sha256(token.encode()).hexdigest(),now()+7*86400,r['id']))
                c.execute("UPDATE inquiries SET status='取引中止・購入者確認待ち' WHERE id=?",(r['inquiry_id'],))
                history(c,r,u['id'],'resent','新しい7日間の確認リンクを発行。旧リンクは無効。')
                send_confirmation(c,r,token,'ic-resend:'+mid('e_'));c.commit();return h.send_json({'ok':True})
            q=h.inquiry_for_user(c,m.group(1),u)
            if not q:return h.send_json({'error':'not_found'},404)
            reason=body.get('reason');note=body.get('note','')
            if not isinstance(reason,str) or reason not in BREEDER_REASONS or not isinstance(note,str) or len(note)>1000 or (reason=='other' and not note.strip()):return h.send_json({'message':'中止理由を選択してください。「その他」は補足を入力してください。'},400)
            if body.get('agreeAccurateReporting') is not True:return h.send_json({'message':'正確な申告の確認にチェックしてください。'},400)
            existing=c.execute("SELECT * FROM inquiry_cancellations WHERE inquiry_id=? AND state IN ('buyer_pending','operator_review','unanswered','closed') ORDER BY created_at DESC,rowid DESC LIMIT 1",(q['id'],)).fetchone()
            if existing:
                if existing['state']=='buyer_pending' and existing['breeder_reason']==reason and existing['breeder_note']==note.strip():return h.send_json({'ok':True,'state':existing['state'],'alreadySubmitted':True})
                return h.send_json({'message':'この問い合わせは中止申請済みです。運営の確認をお待ちください。'},409)
            buyer=c.execute("SELECT id,email FROM users WHERE id=? AND role='buyer'",(q['buyer_id'],)).fetchone()
            if not buyer or not buyer['email']:return h.send_json({'message':'購入希望者の確認先がありません。運営へお問い合わせください。'},409)
            d=c.execute('SELECT * FROM deals WHERE inquiry_id=?',(q['id'],)).fetchone()
            if d and d['status'] in ('completed','cancelled'):return h.send_json({'message':'成約済み・終了済みの取引は運営へお問い合わせください。'},409)
            w=c.execute('SELECT * FROM sale_workflow WHERE deal_id=?',(d['id'],)).fetchone() if d else None
            if w and w['state']=='disputed':return h.send_json({'message':'この取引は運営確認中です。'},409)
            token=secrets.token_urlsafe(32);rid=mid('ic_')
            c.execute('INSERT INTO inquiry_cancellations(id,inquiry_id,breeder_id,buyer_id,breeder_reason,breeder_note,previous_inquiry_status,previous_deal_status,previous_workflow_state,token_hash,expires_at,created_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)',
                      (rid,q['id'],q['breeder_id'],q['buyer_id'],reason,note.strip(),q['status'],d['status'] if d else None,w['state'] if w else None,hashlib.sha256(token.encode()).hexdigest(),now()+7*86400,now()))
            r=c.execute('SELECT * FROM inquiry_cancellations WHERE id=?',(rid,)).fetchone()
            c.execute("UPDATE inquiries SET status='取引中止・購入者確認待ち' WHERE id=?",(q['id'],))
            if d:
                c.execute("UPDATE deals SET status='cancellation_pending' WHERE id=?",(d['id'],))
                c.execute("UPDATE sale_workflow SET state='cancellation_pending',updated_at=? WHERE deal_id=?",(now(),d['id']))
                c.execute("UPDATE sale_confirmations SET state='superseded' WHERE deal_id=? AND state='pending'",(d['id'],))
                if g.get('monitor_inquiry_cancellation'):g['monitor_inquiry_cancellation'](c,d)
            history(c,r,u['id'],'submitted',json.dumps({'reason':reason,'note':note.strip()},ensure_ascii=False))
            send_confirmation(c,r,token,'ic-confirm:'+rid)
            notify(c,r,'取引中止申請を受け付けました',True)
            c.commit();return h.send_json({'ok':True,'state':'buyer_pending','id':rid})
        finally:
            c.close()
            threading.Thread(target=g['flush_sale_workflow_mail'],daemon=True).start()

    def send_confirmation(c,r,token,key):
        email=c.execute('SELECT email FROM users WHERE id=?',(r['buyer_id'],)).fetchone()['email']
        puppy=c.execute('SELECT p.name FROM inquiries i JOIN puppies p ON p.id=i.puppy_id WHERE i.id=?',(r['inquiry_id'],)).fetchone()['name']
        link=base()+'/buyer-cancellation-confirmation.html#token='+token
        queue(c,key,email,'取引状況の確認をお願いします',puppy+'について、ブリーダーより取引中止の申請がありました。\n理由：'+BREEDER_REASONS[r['breeder_reason']]+'\n\n現在の状況を選び、送信してください。\n【取引状況を確認する】\n'+link+'\n\n回答期限は送信から7日間です。メールに返信する必要はありません。メールを開くだけでは回答されません。このリンクはご本人だけで使用してください。未回答の場合は運営が確認します。\nお問い合わせ：info@bigpaw.site')
        c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(mid('n_'),r['buyer_id'],'inquiry_cancellation','取引中止申請の確認をお願いします','マイページの取引中止確認から回答してください。',0,now()))

    def mutation_guard(h,path):
        # Preserve messaging and puppy editing; block transaction changes during review or after closure.
        m=re.fullmatch(r'/api/inquiries/([^/]+)(?:/(visit|deal|video-room))?',path)
        dm=re.fullmatch(r'/api/deals/([^/]+)/(sale-report|completion-report|reservation|contract-sign|pickup)',path)
        if not m and not dm:return False
        u=h.require()
        if not u:return True
        c=db()
        try:
            qid=m.group(1) if m else (c.execute('SELECT inquiry_id FROM deals WHERE id=?',(dm.group(1),)).fetchone() or {'inquiry_id':None})['inquiry_id']
            r=c.execute("SELECT 1 FROM inquiry_cancellations WHERE inquiry_id=? AND state IN ('buyer_pending','operator_review','unanswered','closed')",(qid,)).fetchone()
            if r:h.send_json({'error':'cancellation_locked','message':'取引中止の確認中、または終了済みです。継続する場合は運営へお問い合わせください。'},409);return True
            return False
        finally:c.close()

    def patch(h):
        path=urlparse(h.path).path
        m=re.fullmatch(r'/api/operator/inquiry-cancellations/([^/]+)',path)
        if not m:
            if mutation_guard(h,path):return
            return old_patch(h)
        if not h.mutation_origin_allowed():return h.send_json({'error':'invalid_origin'},403)
        u=h.require(['operator'])
        if not u:return
        body=h.json_body()
        if not isinstance(body,dict):return h.send_json({'error':'invalid_body'},400)
        action,note=body.get('action'),body.get('note','')
        if action not in ('approve','continue','request_details','confirm_sale') or not isinstance(note,str) or not note.strip() or len(note)>1000:return h.send_json({'message':'判断と確認した内容を入力してください。'},400)
        c=db()
        try:
            c.execute('BEGIN IMMEDIATE')
            r=c.execute('SELECT * FROM inquiry_cancellations WHERE id=?',(m.group(1),)).fetchone()
            if not r:return h.send_json({'error':'not_found'},404)
            if r['state'] not in ('operator_review','unanswered','buyer_pending'):return h.send_json({'message':'この申請は対応済みです。'},409)
            c.execute('UPDATE inquiry_cancellations SET reviewed_by=?,reviewed_at=?,review_action=?,review_note=? WHERE id=?',(u['id'],now(),action,note.strip(),r['id']))
            r=c.execute('SELECT * FROM inquiry_cancellations WHERE id=?',(r['id'],)).fetchone()
            if action=='approve':
                if not finish(c,r,u['id']):return h.send_json({'message':'支払済み請求書があります。返金確認を先に行ってください。'},409)
            elif action=='request_details':
                c.execute("UPDATE inquiry_cancellations SET state='operator_review' WHERE id=?",(r['id'],))
                notify(c,r,'取引中止申請について確認をお願いします')
                breeder=c.execute('SELECT user_id FROM breeders WHERE id=?',(r['breeder_id'],)).fetchone()
                for uid in (breeder['user_id'],r['buyer_id']):
                    c.execute('INSERT INTO notifications VALUES(?,?,?,?,?,?,?)',(mid('n_'),uid,'inquiry_cancellation','運営から取引状況の確認',note.strip(),0,now()))
                    email=c.execute('SELECT email FROM users WHERE id=?',(uid,)).fetchone()['email']
                    queue(c,'ic-details:'+mid('e_'),email,'取引状況について運営からの確認',note.strip()+'\n\n'+base()+'/messages.html?inquiry='+r['inquiry_id'])
            else:
                c.execute("UPDATE inquiry_cancellations SET state=? WHERE id=?",('sale_review' if action=='confirm_sale' else 'continued',r['id']))
                c.execute('UPDATE inquiries SET status=? WHERE id=?',(r['previous_inquiry_status'],r['inquiry_id']))
                d=c.execute('SELECT * FROM deals WHERE inquiry_id=?',(r['inquiry_id'],)).fetchone()
                if d:
                    c.execute('UPDATE deals SET status=? WHERE id=?',(r['previous_deal_status'] or 'negotiating',d['id']))
                    c.execute('UPDATE sale_workflow SET state=?,updated_at=? WHERE deal_id=?',(r['previous_workflow_state'] or 'needs_correction',now(),d['id']))
                notify(c,r,'取引中止申請を差し戻しました' if action=='continue' else '成約・お迎えの報告をお願いします')
                # Sale confirmation follows the existing amount, pickup and fee process, never a guessed charge.
            history(c,r,u['id'],'operator_'+action,note.strip());c.commit()
            return h.send_json({'ok':True,'state':c.execute('SELECT state FROM inquiry_cancellations WHERE id=?',(r['id'],)).fetchone()['state']})
        finally:c.close();threading.Thread(target=g['flush_sale_workflow_mail'],daemon=True).start()

    def auto():
        c=db()
        try:c.execute('BEGIN IMMEDIATE');n=expire(c);c.commit()
        finally:c.close()
        result=old_auto();result['unansweredCancellations']=n;return result

    g['init_db'],g['run_automations_once']=migrate,auto
    H.do_GET,H.do_POST,H.do_PATCH=get,post,patch
