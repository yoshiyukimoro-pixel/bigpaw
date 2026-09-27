#!/usr/bin/env python3
from pathlib import Path
import runpy

p=Path(__file__).with_name('server.py')
s=p.read_text(encoding='utf-8')

schema_old="""CREATE TABLE IF NOT EXISTS support_tickets(
 id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), name TEXT NOT NULL, email TEXT NOT NULL,
 category TEXT NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
 operator_note TEXT DEFAULT '', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS backup_runs(
"""
schema_new="""CREATE TABLE IF NOT EXISTS support_tickets(
 id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), name TEXT NOT NULL, email TEXT NOT NULL,
 category TEXT NOT NULL, subject TEXT NOT NULL, message TEXT NOT NULL, status TEXT NOT NULL DEFAULT 'open',
 operator_note TEXT DEFAULT '', created_at INTEGER NOT NULL, updated_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS support_replies(
 id TEXT PRIMARY KEY, ticket_id TEXT NOT NULL REFERENCES support_tickets(id) ON DELETE CASCADE,
 operator_user_id TEXT REFERENCES users(id), body TEXT NOT NULL, email_sent INTEGER NOT NULL DEFAULT 1,
 created_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS backup_runs(
"""
assert s.count(schema_old)==1, ('support_schema_marker_count',s.count(schema_old))
s=s.replace(schema_old,schema_new,1)

get_old="""        if path=='/api/operator/support':
            u=self.require(['operator'])
            if not u:return
            con=db(); rows=con.execute(\"SELECT * FROM support_tickets ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END, created_at DESC\").fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        if path=='/api/operator/reports':
"""
get_new="""        if path=='/api/operator/support':
            u=self.require(['operator'])
            if not u:return
            con=db(); rows=con.execute(\"SELECT * FROM support_tickets ORDER BY CASE status WHEN 'open' THEN 0 WHEN 'reviewing' THEN 1 ELSE 2 END, created_at DESC\").fetchall(); con.close(); return self.send_json([dict(r) for r in rows])
        msupport_replies=re.fullmatch(r'/api/operator/support/([^/]+)/replies',path)
        if msupport_replies:
            u=self.require(['operator'])
            if not u:return
            con=db(); ticket=con.execute('SELECT id FROM support_tickets WHERE id=?',(msupport_replies.group(1),)).fetchone()
            if not ticket: con.close(); return self.send_json({'error':'not_found'},404)
            rows=con.execute('''SELECT r.*,COALESCE(NULLIF(u.display_name,''),u.email,'BIG PAW運営') operator_name
                                FROM support_replies r LEFT JOIN users u ON u.id=r.operator_user_id
                                WHERE r.ticket_id=? ORDER BY r.created_at ASC''',(ticket['id'],)).fetchall(); con.close()
            return self.send_json([dict(r) for r in rows])
        if path=='/api/operator/reports':
"""
assert s.count(get_old)==1, ('support_get_marker_count',s.count(get_old))
s=s.replace(get_old,get_new,1)

post_anchor="""    def do_POST(self):
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        path=urlparse(self.path).path
"""
post_route="""        msupport_reply=re.fullmatch(r'/api/operator/support/([^/]+)/reply',path)
        if msupport_reply:
            u=self.require(['operator'])
            if not u:return
            body=self.json_body(); text=str(body.get('body','')).strip()
            if not text: return self.send_json({'error':'reply_required','message':'返信内容を入力してください。'},400)
            if len(text)>5000: return self.send_json({'error':'too_long','message':'返信内容は5000文字以内で入力してください。'},400)
            con=db(); ticket=con.execute('SELECT * FROM support_tickets WHERE id=?',(msupport_reply.group(1),)).fetchone()
            if not ticket: con.close(); return self.send_json({'error':'not_found'},404)
            to_email=str(ticket['email'] or '').strip().lower()
            if not to_email or '@' not in to_email: con.close(); return self.send_json({'error':'invalid_recipient'},400)
            subject='【BIG PAW】Re: '+str(ticket['subject'] or 'お問い合わせ')
            mail_body=f\"{ticket['name']} 様\\n\\nBIG PAWへお問い合わせいただきありがとうございます。\\n\\n{text}\\n\\n――――――――――\\nBIG PAW運営\"
            sent=send_mail(to_email,subject,mail_body)
            if not sent: con.close(); return self.send_json({'error':'mail_send_failed','message':'メールを送信できませんでした。設定を確認して再度お試しください。'},502)
            rid=make_id('sr_'); t=now()
            con.execute('INSERT INTO support_replies(id,ticket_id,operator_user_id,body,email_sent,created_at) VALUES(?,?,?,?,?,?)',(rid,ticket['id'],u['id'],text,1,t))
            con.execute(\"UPDATE support_tickets SET status='reviewing',updated_at=? WHERE id=?\",(t,ticket['id']))
            audit(con,u['id'],'support_reply_sent','support_ticket',ticket['id'],rid); con.commit(); con.close()
            return self.send_json({'ok':True,'mailSent':True,'replyId':rid},201)
"""
assert s.count(post_anchor)==1, ('support_post_anchor_count',s.count(post_anchor))
s=s.replace(post_anchor,post_anchor+post_route,1)

p.write_text(s,encoding='utf-8')
print('OPERATOR_SUPPORT_REPLY_OK|history=enabled|email=enabled|status=reviewing',flush=True)
runpy.run_path(str(Path(__file__).with_name('operator_support_retention_patch.py')),run_name='__main__')
