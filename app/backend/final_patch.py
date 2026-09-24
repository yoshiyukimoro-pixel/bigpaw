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
                from datetime import datetime,timedelta
                from zoneinfo import ZoneInfo
                start=datetime.strptime(str(visit['visit_date'])+' '+str(visit['visit_time']),'%Y-%m-%d %H:%M').replace(tzinfo=ZoneInfo('Asia/Tokyo'))
                current=datetime.now(ZoneInfo('Asia/Tokyo'))
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

p.write_text(s,encoding='utf-8')
print('FINAL_VISIT_PATCH_OK|buyer=proposed|breeder=confirmed|room=confirmed_plus_30min|mail=online_only',flush=True)
