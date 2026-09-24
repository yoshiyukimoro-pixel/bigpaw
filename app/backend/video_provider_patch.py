from pathlib import Path

p=Path('/app/backend/server.py')
s=p.read_text(encoding='utf-8')

config_marker="PUBLIC_BASE_URL = os.environ.get('BIGPAW_PUBLIC_BASE_URL','https://bigpaw.site').rstrip('/')\n"
config_replacement=config_marker+"VIDEO_PROVIDER = os.environ.get('BIGPAW_VIDEO_PROVIDER','external').strip().lower()\nVIDEO_BASE_URL = os.environ.get('BIGPAW_VIDEO_BASE_URL','').strip().rstrip('/')\n"
assert s.count(config_marker)==1, ('video_config_marker_count',s.count(config_marker))
s=s.replace(config_marker,config_replacement,1)

old_room="""        m=re.fullmatch(r'/api/inquiries/([^/]+)/video-room',path)
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
            if not VIDEO_BASE_URL:
                con.close(); return self.send_json({'error':'video_service_not_configured','message':'オンライン見学システムは現在準備中です。運営へお問い合わせください。'},503)
            import hashlib
            room='BIGPAW-'+hashlib.sha256((m.group(1)+'|online-visit').encode()).hexdigest()[:32]
            encoded_room=quote(room,safe='')
            join_url=VIDEO_BASE_URL.replace('{room}',encoded_room) if '{room}' in VIDEO_BASE_URL else VIDEO_BASE_URL+'/'+encoded_room
            con.close(); return self.send_json({'room':room,'joinUrl':join_url,'provider':VIDEO_PROVIDER,'inquiryId':m.group(1),'role':u['role']})
"""
assert s.count(old_room)==1, ('video_room_post_final_count',s.count(old_room))
s=s.replace(old_room,new_room,1)

old_health="if path=='/api/health': return self.send_json({'ok':True,'service':'BIG PAW API','version':'1.0','environment':APP_ENV,'database':'sqlite','mailConfigured':bool(os.environ.get('RESEND_API_KEY') or SMTP_HOST),'paymentMode':PAYMENT_MODE})"
new_health="if path=='/api/health': return self.send_json({'ok':True,'service':'BIG PAW API','version':'1.0','environment':APP_ENV,'database':'sqlite','mailConfigured':bool(os.environ.get('RESEND_API_KEY') or SMTP_HOST),'videoConfigured':bool(VIDEO_BASE_URL),'paymentMode':PAYMENT_MODE})"
assert s.count(old_health)==1, ('video_health_count',s.count(old_health))
s=s.replace(old_health,new_health,1)

old_ready="'smtpConfigured':bool(os.environ.get('RESEND_API_KEY') or (SMTP_HOST and SMTP_FROM)),"
new_ready="'smtpConfigured':bool(os.environ.get('RESEND_API_KEY') or (SMTP_HOST and SMTP_FROM)),\n              'videoConfigured':bool(VIDEO_BASE_URL),"
assert s.count(old_ready)==1, ('video_readiness_count',s.count(old_ready))
s=s.replace(old_ready,new_ready,1)

p.write_text(s,encoding='utf-8')
print('VIDEO_PROVIDER_OK|join_url=server_controlled|hardcoded_public_jitsi=removed|readiness=tracked',flush=True)
