from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

# Operator-only registered-user list and detail APIs. Password hashes/salts are never selected or returned.
get_marker="        if path=='/api/operator/stats':\n"
get_routes="""        if path=='/api/operator/users':
            u=self.require(['operator'])
            if not u:return
            con=db()
            rows=con.execute('''SELECT u.id,u.role,u.email,u.last,u.first,u.display_name,u.created_at,u.updated_at,u.email_verified,
                COALESCE(b.id,'') breeder_id,COALESCE(b.kennel_name,a.kennel_name,'') kennel_name,
                COALESCE(b.prefecture,a.prefecture,'') prefecture,COALESCE(a.status,'') breeder_application_status
                FROM users u
                LEFT JOIN breeders b ON b.user_id=u.id
                LEFT JOIN breeder_applications a ON a.user_id=u.id
                ORDER BY u.created_at DESC,u.id''').fetchall()
            con.close(); return self.send_json([dict(r) for r in rows])
        mu=re.fullmatch(r'/api/operator/users/([^/]+)',path)
        if mu:
            u=self.require(['operator'])
            if not u:return
            con=db(); uid=mu.group(1)
            r=con.execute('''SELECT u.id,u.role,u.email,u.last,u.first,u.display_name,u.created_at,u.updated_at,u.email_verified,
                b.id breeder_id,b.kennel_name,b.prefecture,b.registration_no,b.review_status breeder_review_status,
                b.billing_suspended,b.visit_address,b.visit_phone,b.visit_access,
                a.id breeder_application_id,a.representative,a.primary_breed,a.registration_no application_registration_no,
                a.expires_on,a.status breeder_application_status,a.review_note,a.created_at application_created_at,a.updated_at application_updated_at
                FROM users u
                LEFT JOIN breeders b ON b.user_id=u.id
                LEFT JOIN breeder_applications a ON a.user_id=u.id
                WHERE u.id=?''',(uid,)).fetchone()
            if not r: con.close(); return self.send_json({'error':'not_found'},404)
            out=dict(r)
            latest_phone=con.execute("SELECT phone FROM inquiries WHERE buyer_id=? AND COALESCE(phone,'')<>'' ORDER BY created_at DESC LIMIT 1",(uid,)).fetchone()
            out['buyer_phone']=(latest_phone['phone'] if latest_phone else '')
            out['favorite_count']=con.execute('SELECT COUNT(*) c FROM favorites WHERE user_id=?',(uid,)).fetchone()['c']
            out['inquiry_count']=con.execute('SELECT COUNT(*) c FROM inquiries WHERE buyer_id=?',(uid,)).fetchone()['c']
            out['deal_count']=con.execute('SELECT COUNT(*) c FROM deals WHERE buyer_id=?',(uid,)).fetchone()['c']
            if out.get('breeder_id'):
                out['breeder_puppy_count']=con.execute('SELECT COUNT(*) c FROM puppies WHERE breeder_id=?',(out['breeder_id'],)).fetchone()['c']
                out['breeder_inquiry_count']=con.execute('SELECT COUNT(*) c FROM inquiries WHERE breeder_id=?',(out['breeder_id'],)).fetchone()['c']
                out['breeder_deal_count']=con.execute('SELECT COUNT(*) c FROM deals WHERE breeder_id=?',(out['breeder_id'],)).fetchone()['c']
            else:
                out['breeder_puppy_count']=0; out['breeder_inquiry_count']=0; out['breeder_deal_count']=0
            out['mail_allowed']=bool(out.get('email')) and not str(out.get('email','')).endswith('@invalid.local')
            con.close(); return self.send_json(out)
"""
assert s.count(get_marker)==1,('operator_users_get_marker',s.count(get_marker))
s=s.replace(get_marker,get_routes+get_marker,1)

post_marker="""    def do_POST(self):
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        path=urlparse(self.path).path
        m=re.fullmatch(r'/api/inquiries/([^/]+)/messages',path)
"""
post_new="""    def do_POST(self):
        if not self.mutation_origin_allowed(): return self.send_json({'error':'invalid_origin'},403)
        path=urlparse(self.path).path
        mu=re.fullmatch(r'/api/operator/users/([^/]+)/email',path)
        if mu:
            u=self.require(['operator'])
            if not u:return
            body=self.json_body(); subject=str(body.get('subject','')).strip(); message=str(body.get('message','')).strip()
            if not subject or not message: return self.send_json({'error':'required_fields','message':'件名と本文を入力してください。'},400)
            if len(subject)>200 or len(message)>5000: return self.send_json({'error':'too_long','message':'メールの件名または本文が長すぎます。'},400)
            con=db(); target=con.execute('SELECT id,email,display_name,last,first FROM users WHERE id=?',(mu.group(1),)).fetchone()
            if not target: con.close(); return self.send_json({'error':'not_found'},404)
            email=str(target['email'] or '').strip()
            if not email or email.endswith('@invalid.local'): con.close(); return self.send_json({'error':'email_unavailable','message':'このユーザーには送信可能なメールアドレスがありません。'},409)
            audit(con,u['id'],'operator_user_email','user',target['id'],subject[:120]); con.commit(); con.close()
            sent=send_mail(email,subject,message)
            if not sent: return self.send_json({'error':'email_send_failed','message':'メール送信に失敗しました。メール設定を確認してください。'},502)
            return self.send_json({'ok':True})
        m=re.fullmatch(r'/api/inquiries/([^/]+)/messages',path)
"""
assert s.count(post_marker)==1,('operator_users_post_marker',s.count(post_marker))
s=s.replace(post_marker,post_new,1)
p.write_text(s,encoding='utf-8')

# Make the dashboard user count a real navigation entry.
admin=Path('/app/operator-admin.html')
html=admin.read_text(encoding='utf-8')
old='<div class="card statbox"><span class="muted">登録ユーザー</span><b id="opUsers">-</b></div>'
new='<a class="statlink" href="operator-users.html" aria-label="登録ユーザー一覧を確認"><div class="card statbox"><span class="muted">登録ユーザー</span><b id="opUsers">-</b></div></a>'
assert html.count(old)==1,('operator_users_dashboard_card',html.count(old))
html=html.replace(old,new,1)
side='<a href="operator-admin.html">ダッシュボード</a>'
if side in html and 'operator-users.html">登録ユーザー' not in html:
    html=html.replace(side,side+'<a href="operator-users.html">登録ユーザー</a>',1)
admin.write_text(html,encoding='utf-8')

print('OPERATOR_USERS_OK|dashboard=linked|list=enabled|detail=enabled|password=never_returned|private_contact=detail_only|operator_email=enabled',flush=True)
