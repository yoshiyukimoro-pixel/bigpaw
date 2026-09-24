from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

old_room="""        m=re.fullmatch(r'/api/inquiries/([^/]+)/video-room',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            import hashlib
            room='BIGPAW-'+hashlib.sha256((m.group(1)+'|online-visit').encode()).hexdigest()[:32]
            con.close(); return self.send_json({'room':room,'inquiryId':m.group(1),'role':u['role']})
"""
new_room="""        m=re.fullmatch(r'/api/inquiries/([^/]+)/video-room',path)
        if m:
            u=self.require();
            if not u:return
            con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            visit=con.execute('SELECT * FROM visits WHERE inquiry_id=?',(m.group(1),)).fetchone()
            if not visit or visit['transport']!='オンライン見学' or visit['status']!='confirmed':
                con.close(); return self.send_json({'error':'online_visit_not_confirmed','message':'オンライン見学の日時確定後に入室できます。'},409)
            try:
                from datetime import datetime,timedelta,timezone
                jst=timezone(timedelta(hours=9))
                start=datetime.strptime(str(visit['visit_date'])+' '+str(visit['visit_time']),'%Y-%m-%d %H:%M').replace(tzinfo=jst)
                current=datetime.now(jst)
            except Exception:
                con.close(); return self.send_json({'error':'invalid_visit_time'},409)
            if current < start-timedelta(minutes=30):
                con.close(); return self.send_json({'error':'room_not_open','message':'オンライン見学は開始30分前から入室できます。'},409)
            import hashlib
            room='BIGPAW-'+hashlib.sha256((m.group(1)+'|online-visit').encode()).hexdigest()[:32]
            con.close(); return self.send_json({'room':room,'inquiryId':m.group(1),'role':u['role']})
"""
assert s.count(old_room)==1, ('video_room_block_count',s.count(old_room))
s=s.replace(old_room,new_room,1)

old_visit_start="""            body=self.json_body(); con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if body.get('status') == 'confirmed' and u.get('role') not in ('breeder','operator'):
                con.close(); return self.send_json({'error':'breeder_only_confirmation'},403)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
"""
new_visit_start="""            body=self.json_body(); con=db(); qrow=self.inquiry_for_user(con,m.group(1),u)
            if not qrow: con.close(); return self.send_json({'error':'forbidden_or_not_found'},404)
            visit_status=str(body.get('status','proposed'))
            if visit_status not in ('proposed','confirmed'):
                con.close(); return self.send_json({'error':'invalid_visit_status'},400)
            if not str(body.get('date','')).strip() or not str(body.get('time','')).strip():
                con.close(); return self.send_json({'error':'visit_date_time_required'},400)
            if visit_status == 'confirmed' and u.get('role') not in ('breeder','operator'):
                con.close(); return self.send_json({'error':'breeder_only_confirmation'},403)
"""
assert s.count(old_visit_start)==1, ('visit_start_block_count',s.count(old_visit_start))
s=s.replace(old_visit_start,new_visit_start,1)

old_visit_finish="""            con.execute(\"UPDATE inquiries SET status='見学確定' WHERE id=?\",(m.group(1),))
            con.commit(); r=con.execute('SELECT * FROM visits WHERE id=?',(vid,)).fetchone(); con.close(); self.online_visit_email(m.group(1), body.get('status','proposed'), body.get('date',''), body.get('time','')); return self.send_json(dict(r),201)
"""
new_visit_finish="""            inquiry_status='見学確定' if visit_status=='confirmed' else '見学調整中'
            con.execute('UPDATE inquiries SET status=? WHERE id=?',(inquiry_status,m.group(1)))
            con.commit(); r=con.execute('SELECT * FROM visits WHERE id=?',(vid,)).fetchone(); con.close()
            if body.get('transport')=='オンライン見学': self.online_visit_email(m.group(1), visit_status, body.get('date',''), body.get('time',''))
            return self.send_json(dict(r),201)
"""
assert s.count(old_visit_finish)==1, ('visit_finish_block_count',s.count(old_visit_finish))
s=s.replace(old_visit_finish,new_visit_finish,1)

old_email="""            subject=\"【BIG PAW】オンライン見学のお申し込みが入りました\" if status=='proposed' else \"【BIG PAW】オンライン見学の日時が確定しました\"
            lead=\"オンライン見学のお申し込みが入りました。\\n希望日時：\" if status=='proposed' else \"オンライン見学の日時が確定しました。\\n日時：\"
            body=f'''オンライン見学の日時が確定しました。

【確定日時】
{visit_date} {visit_time}

【当日の参加方法】
1. 開始時刻になりましたらBIG PAWへログインしてください。
2. 確定したオンライン見学画面を開き、「カメラを準備して入室」を押してください。
3. Jitsi Meetの画面が表示されたら、青い「Join in browser」を押してください。
4. カメラとマイクの使用を許可すると入室できます。
5. 相手がまだ入室していない場合は、そのままお待ちください。相手が同じルームへ入室すると映像と音声がつながります。

※購入希望者様・ブリーダー双方が同じ手順で入室します。
※同時に入室する必要はありません。先に入った方はそのままお待ちください。
※海外の電話番号へ電話をかける必要はありません。
※PINコードの入力は必要ありません。
※Jitsi Meetアプリのインストールは不要です。「Join in browser」からブラウザで参加できます。

BIG PAW
https://www.bigpaw.site/'''
"""
new_email="""            subject=\"【BIG PAW】オンライン見学のお申し込みが入りました\" if status=='proposed' else \"【BIG PAW】オンライン見学の日時が確定しました\"
            if status=='proposed':
                body=f'''オンライン見学のお申し込みが入りました。

【希望日時】
{visit_date} {visit_time}

BIG PAWの問い合わせ管理画面から希望日時を確認し、見学日時を確定してください。

{PUBLIC_BASE_URL}/breeder-inquiries.html'''
            else:
                body=f'''オンライン見学の日時が確定しました。

【確定日時】
{visit_date} {visit_time}

【当日の参加方法】
1. 開始30分前以降にBIG PAWへログインしてください。
2. 確定したオンライン見学画面を開き、「オンライン見学に参加」を押してください。
3. Jitsi Meetへ移動したら、ブラウザで参加してください。
4. カメラとマイクの使用を許可すると入室できます。
5. 相手がまだ入室していない場合は、そのままお待ちください。

※購入希望者様・ブリーダー双方が同じ専用ルームへ入室します。
※PINコードの入力は必要ありません。

BIG PAW
{PUBLIC_BASE_URL}/'''
"""
assert s.count(old_email)==1, ('online_visit_email_block_count',s.count(old_email))
s=s.replace(old_email,new_email,1)

old_health="if path=='/api/health': return self.send_json({'ok':True,'service':'BIG PAW API','version':'1.0','environment':APP_ENV,'database':'sqlite','mailConfigured':bool(SMTP_HOST),'paymentMode':PAYMENT_MODE})"
new_health="if path=='/api/health': return self.send_json({'ok':True,'service':'BIG PAW API','version':'1.0','environment':APP_ENV,'database':'sqlite','mailConfigured':bool(os.environ.get('RESEND_API_KEY') or SMTP_HOST),'paymentMode':PAYMENT_MODE})"
assert s.count(old_health)==1, ('health_mail_check_count',s.count(old_health))
s=s.replace(old_health,new_health,1)

old_ready="'smtpConfigured':bool(SMTP_HOST and SMTP_FROM),"
new_ready="'smtpConfigured':bool(os.environ.get('RESEND_API_KEY') or (SMTP_HOST and SMTP_FROM)),"
assert s.count(old_ready)==1, ('readiness_mail_check_count',s.count(old_ready))
s=s.replace(old_ready,new_ready,1)

old_public_list="SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.review_status='approved' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
new_public_list="SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.review_status='approved' AND p.status!='非公開' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
assert s.count(old_public_list)==1, ('public_list_visibility_count',s.count(old_public_list))
s=s.replace(old_public_list,new_public_list,1)

old_public_detail="SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=? AND p.review_status='approved' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
new_public_detail="SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=? AND p.review_status='approved' AND p.status!='非公開' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
assert s.count(old_public_detail)==1, ('public_detail_visibility_count',s.count(old_public_detail))
s=s.replace(old_public_detail,new_public_detail,1)

old_breeder_puppies="SELECT * FROM puppies WHERE breeder_id=? AND review_status='approved' ORDER BY created_at DESC"
new_breeder_puppies="SELECT * FROM puppies WHERE breeder_id=? AND review_status='approved' AND status!='非公開' ORDER BY created_at DESC"
assert s.count(old_breeder_puppies)==1, ('public_breeder_puppies_visibility_count',s.count(old_breeder_puppies))
s=s.replace(old_breeder_puppies,new_breeder_puppies,1)

old_sitemap="SELECT p.id FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.review_status='approved' AND p.status!='成約済み' AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
new_sitemap="SELECT p.id FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.review_status='approved' AND p.status NOT IN ('成約済み','非公開') AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)"
assert s.count(old_sitemap)==1, ('sitemap_visibility_count',s.count(old_sitemap))
s=s.replace(old_sitemap,new_sitemap,1)

old_favorites_get="""con=db(); sync_breeder_billing_suspension(con); con.commit(); rows=con.execute('''SELECT p.* FROM favorites f JOIN puppies p ON p.id=f.puppy_id LEFT JOIN breeders b ON b.id=p.breeder_id WHERE f.user_id=? AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0) ORDER BY f.created_at DESC''',(u['id'],)).fetchall(); con.close()"""
new_favorites_get="""con=db(); sync_breeder_billing_suspension(con); con.commit(); rows=con.execute('''SELECT p.* FROM favorites f JOIN puppies p ON p.id=f.puppy_id LEFT JOIN breeders b ON b.id=p.breeder_id WHERE f.user_id=? AND p.review_status='approved' AND p.status!='非公開' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0) ORDER BY f.created_at DESC''',(u['id'],)).fetchall(); con.close()"""
assert s.count(old_favorites_get)==1, ('favorites_get_visibility_count',s.count(old_favorites_get))
s=s.replace(old_favorites_get,new_favorites_get,1)

old_inquiry_lookup="con=db(); p=con.execute(\"SELECT * FROM puppies WHERE id=? AND review_status='approved' AND status!='成約済み'\",(puppy_id,)).fetchone()"
new_inquiry_lookup="con=db(); p=con.execute(\"SELECT p.* FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=? AND p.review_status='approved' AND p.status NOT IN ('成約済み','非公開') AND (p.breeder_id IS NULL OR b.review_status='approved')\",(puppy_id,)).fetchone()"
assert s.count(old_inquiry_lookup)==1, ('inquiry_visibility_count',s.count(old_inquiry_lookup))
s=s.replace(old_inquiry_lookup,new_inquiry_lookup,1)

old_favorite_add="""            else:
                if not con.execute(\"SELECT 1 FROM puppies WHERE id=? AND review_status='approved'\",(pid,)).fetchone(): con.close(); return self.send_json({'error':'not_found'},404)
                con.execute('INSERT INTO favorites VALUES(?,?,?)',(u['id'],pid,now())); value=True
"""
new_favorite_add="""            else:
                sync_breeder_billing_suspension(con); con.commit()
                visible=con.execute(\"SELECT 1 FROM puppies p LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=? AND p.review_status='approved' AND p.status!='非公開' AND (p.breeder_id IS NULL OR b.review_status='approved') AND (p.breeder_id IS NULL OR COALESCE(b.billing_suspended,0)=0)\",(pid,)).fetchone()
                if not visible: con.close(); return self.send_json({'error':'not_found'},404)
                con.execute('INSERT INTO favorites VALUES(?,?,?)',(u['id'],pid,now())); value=True
"""
assert s.count(old_favorite_add)==1, ('favorite_add_visibility_count',s.count(old_favorite_add))
s=s.replace(old_favorite_add,new_favorite_add,1)

old_legacy_reapprove="""    # legacy approved breeder puppies: approved breeders publish directly
    con.execute(\"UPDATE puppies SET review_status='approved' WHERE review_status!='approved' AND breeder_id IN (SELECT id FROM breeders WHERE review_status='approved')\")
"""
new_legacy_reapprove="""    # Direct publishing is handled when an approved breeder creates a listing.
    # Preserve later operator moderation decisions across application restarts.
"""
assert s.count(old_legacy_reapprove)==1, ('legacy_reapprove_count',s.count(old_legacy_reapprove))
s=s.replace(old_legacy_reapprove,new_legacy_reapprove,1)

p.write_text(s,encoding='utf-8')
print('FINAL_VISIT_PATCH_OK|buyer=proposed|breeder=confirmed|room=confirmed_plus_30min|mail=online_only|resend=readiness|public_visibility=guarded|moderation=persistent',flush=True)
