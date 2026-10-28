#!/usr/bin/env python3
"""Ensure online-visit confirmation mail never directs people to BIG PAW video rooms.

Run after video_provider_patch.py and visit_contact_patch.py, before release tests.
No production DB changes, credentials, or outbound calls.
"""
from pathlib import Path
import os

server_path = Path(os.environ.get("BIGPAW_SERVER_PATH", "/app/backend/server.py"))
source = server_path.read_text(encoding="utf-8")
begin = "    def online_visit_email(self, inquiry_id, status, visit_date, visit_time):\n"
end = "    def do_POST(self):\n"
assert source.count(begin) == 1, ("online_visit_email_start", source.count(begin))
assert source.count(end) == 1, ("online_visit_email_end", source.count(end))
start = source.index(begin)
stop = source.index(end, start)
old = source[start:stop]
assert "Jitsi Meet" in old or "ONLINE_VISIT_EXTERNAL_EMAIL_V1" in old, "Unexpected online mail implementation"
replacement = '''    def online_visit_email(self, inquiry_id, status, visit_date, visit_time):
        # ONLINE_VISIT_EXTERNAL_EMAIL_V1: BIG PAW manages dates, not calls.
        try:
            con=db()
            row=con.execute("SELECT i.buyer_id,p.breeder_id FROM inquiries i JOIN puppies p ON p.id=i.puppy_id WHERE i.id=?",(inquiry_id,)).fetchone()
            if not row: con.close(); return False
            if status=='proposed':
                user=con.execute("SELECT u.email FROM breeders b JOIN users u ON u.id=b.user_id WHERE b.id=?",(row['breeder_id'],)).fetchone()
            else:
                user=con.execute("SELECT email FROM users WHERE id=?",(row['buyer_id'],)).fetchone()
            con.close()
            if not user or not user['email']: return False
            when=f"{visit_date} {visit_time}".strip()
            if status=='proposed':
                subject="【BIG PAW】オンライン見学の希望日時が届きました"
                intro="オンライン見学の希望日時が届きました。"
            else:
                subject="【BIG PAW】オンライン見学の日時が確定しました"
                intro="オンライン見学の日時が確定しました。"
            body=f""" {intro}

【見学日時】
{when}

【通話方法について】
BIG PAWでは日時の確認・確定までを行います。
実際のビデオ通話はLINE・FaceTimeなどを、購入希望者とブリーダーが直接利用してください。
BIG PAWのメッセージで、使うアプリや必要な連絡方法を相談してください。
個人情報・連絡先は同意した相手にだけ共有してください。
FaceTimeでは通話の参加リンクを使う方法もあります。

【BIG PAW メッセージ】
{PUBLIC_BASE_URL}/messages.html?inquiry={inquiry_id}

【確定日時の確認】
{PUBLIC_BASE_URL}/visit-confirm.html?inquiry={inquiry_id}

※オンライン見学は契約に必要な現物確認・対面説明の代わりにはなりません。
"""
            return send_mail(user['email'],subject,body.lstrip())
        except Exception as e:
            print('[BIG PAW] external online visit email failed:',e,flush=True)
            return False

'''
source = source[:start] + replacement + source[stop:]
assert "Jitsi" not in source[source.index(begin):source.index(end, source.index(begin))]
assert "LINE・FaceTime" in source[source.index(begin):source.index(end, source.index(begin))]
server_path.write_text(source, encoding="utf-8")
print("ONLINE_VISIT_EXTERNAL_MAIL_OK|date_confirmed=BIGPAW|call=LINE_FACETIME|no_jitsi_steps", flush=True)
