#!/usr/bin/env python3
"""Test a real inquiry HTTP flow with a disposable SQLite DB and intercepted mail.

No live inquiries, real customers, production database or external mail transport.
"""
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
from urllib.error import HTTPError
from urllib.request import Request, urlopen

APP = Path(__file__).resolve().parents[1]
SERVER = APP / "backend" / "server.py"
ORIGINAL = SERVER.read_text(encoding="utf-8")
MARKER = "from first_sale_workflow import install as _install_first_sale_workflow"
assert ORIGINAL.count(MARKER) == 1, "mail-capture injection marker changed"

def check(condition, name):
    if not condition:
        raise AssertionError(name)
    print("PASS", name, flush=True)

with tempfile.TemporaryDirectory(prefix="bigpaw-operator-inquiry-") as temp:
    work = Path(temp)
    data = work / "data"
    data.mkdir()
    mail_capture = work / "mails.jsonl"
    reject_operator = work / "reject-operator"
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    hook = """
def _capture_operator_mail(to_email, subject, body):
    import json as _json, os as _os
    with open(_os.environ["BIGPAW_TEST_MAIL_CAPTURE"], "a", encoding="utf-8") as f:
        f.write(_json.dumps({"to": to_email, "subject": subject, "body": body}, ensure_ascii=False) + "\\n")
    if to_email == "info@bigpaw.site" and _os.path.exists(_os.environ["BIGPAW_TEST_REJECT_OPERATOR"]):
        return False
    return True
send_mail = _capture_operator_mail
"""
    env = {key: val for key, val in os.environ.items()
           if not key.startswith(("BIGPAW_", "SMTP_", "RESEND_"))}
    env.update(
        PORT=str(port),
        BIGPAW_DATA_DIR=str(data),
        BIGPAW_ENV="development",
        BIGPAW_PUBLIC_BASE_URL=base,
        BIGPAW_AUTOMATION_INTERVAL_SECONDS="3600",
        BIGPAW_TEST_MAIL_CAPTURE=str(mail_capture),
        BIGPAW_TEST_REJECT_OPERATOR=str(reject_operator),
    )
    process = None
    log = (work / "server.log").open("w", encoding="utf-8")

    def sql(query, args=(), read=False):
        with sqlite3.connect(data / "bigpaw.sqlite3", timeout=20) as conn:
            conn.row_factory = sqlite3.Row
            cur = conn.execute(query, args)
            return [dict(row) for row in cur.fetchall()] if read else None

    def request(method, path, payload=None, user=None):
        headers = {"Content-Type": "application/json", "Origin": "https://bigpaw.site"}
        if user:
            headers["Cookie"] = "bigpaw_session=test-" + user
        req = Request(
            base + path, method=method, headers=headers,
            data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        )
        try:
            with urlopen(req, timeout=10) as response:
                return response.status, json.loads(response.read() or b"{}")
        except HTTPError as exc:
            return exc.code, json.loads(exc.read() or b"{}")

    def mails():
        if not mail_capture.exists():
            return []
        return [json.loads(line) for line in mail_capture.read_text(encoding="utf-8").splitlines()]

    def puppy(puppy_id, breeder_id, name, breeder_name):
        sql(
            """INSERT INTO puppies(
                id,breeder_id,name,breed,breed_key,gender,gender_key,color,
                price,status,area,area_key,breeder_name,created_at,review_status
            ) VALUES(?,?,?,'スタンダードプードル','standard','男の子',
                     'male','ブラック',300000,'募集中','埼玉県','saitama',?,?,'approved')""",
            (puppy_id, breeder_id, name, breeder_name, int(time.time())),
        )

    try:
        SERVER.write_text(ORIGINAL.replace(MARKER, hook + "\n" + MARKER, 1), encoding="utf-8")
        process = subprocess.Popen(
            [sys.executable, str(SERVER)], cwd=APP, env=env,
            stdout=log, stderr=log,
        )
        for _ in range(100):
            if process.poll() is not None:
                raise RuntimeError("server stopped during startup: " +
                                   (work / "server.log").read_text(encoding="utf-8")[-2500:])
            try:
                if request("GET", "/api/health")[0] == 200:
                    break
            except Exception:
                time.sleep(.1)
        else:
            raise RuntimeError("server did not become healthy: " +
                               (work / "server.log").read_text(encoding="utf-8")[-2500:])

        t = int(time.time())
        for uid in ("u_demo", "u_dog44", "u_admin"):
            sql("INSERT INTO sessions VALUES(?,?,?,?)",
                ("test-" + uid, uid, t, t + 3600))
        sql(
            """INSERT INTO users(id,role,email,salt,password_hash,created_at)
               VALUES('u_second_operator','operator','second@example.invalid','s','h',?)""",
            (t,),
        )
        puppy("p_ops_alert", "b_dog44", "通知テストの子犬", "古い登録名")
        buyer = {
            "puppyId": "p_ops_alert", "name": "非公開 テスト購入者",
            "email": "private.buyer@example.invalid", "phone": "090-1111-2222",
            "message": "購入者だけの秘密の問い合わせ",
        }

        check(request("POST", "/api/inquiries", buyer)[0] == 401,
              "anonymous buyer cannot create inquiry")
        check(request("POST", "/api/inquiries", buyer, "u_dog44")[0] == 403,
              "breeder cannot submit a buyer inquiry")
        check(request("POST", "/api/inquiries", {**buyer, "puppyId": "not-found"}, "u_demo")[0] == 404,
              "unknown puppy cannot create an inquiry")
        check(len(mails()) == 0, "rejected inquiries produce no mail")

        status, result = request("POST", "/api/inquiries", buyer, "u_demo")
        check(status == 201 and result.get("status") == "未返信",
              "valid buyer inquiry returns HTTP 201")
        qid = result["id"]
        check(len(sql("SELECT id FROM inquiries WHERE id=?", (qid,), True)) == 1,
              "inquiry saved once")
        check(len(sql("SELECT id FROM notifications WHERE user_id='u_dog44' AND type='inquiry'", read=True)) == 1,
              "existing breeder in-app alert preserved")
        check(len(sql("SELECT id FROM notifications WHERE user_id='u_admin' AND type='inquiry'", read=True)) == 1
              and len(sql("SELECT id FROM notifications WHERE user_id='u_second_operator' AND type='inquiry'", read=True)) == 1,
              "both operator accounts get in-app notifications")

        email_list = mails()
        check(len(email_list) == 2, "one breeder email and exactly one operator email")
        check(len([m for m in email_list if m["to"] == "dog44@bigpaw.jp"]) == 1,
              "breeder still receives email")
        op_email = [m for m in email_list if m["to"] == "info@bigpaw.site"]
        check(len(op_email) == 1, "operations mail goes to the correct address once")
        body = op_email[0]["body"]
        check("DOG44" in body and "通知テストの子犬" in body and qid in body
              and f"/messages.html?mode=operator&inquiry={qid}" in body,
              "operations mail identifies kennel, puppy, inquiry and protected link")
        check(not any(value in body for value in
                      (buyer["name"], buyer["email"], buyer["phone"], buyer["message"])),
              "private buyer contact details and inquiry text are omitted from operations email")

        op_status, op_rows = request("GET", "/api/inquiries", user="u_admin")
        check(op_status == 200 and any(row["id"] == qid for row in op_rows),
              "operator can see the inquiry in management")
        breeder_status, breeder_rows = request("GET", "/api/inquiries", user="u_dog44")
        check(breeder_status == 200 and any(row["id"] == qid for row in breeder_rows),
              "breeder can still see the inquiry")

        reject_operator.touch()
        status2, result2 = request("POST", "/api/inquiries", buyer, "u_demo")
        check(status2 == 201 and result2["id"] != qid,
              "operator mail provider rejection must not lose the saved inquiry")
        check(len(sql("SELECT id FROM inquiries WHERE id=?", (result2["id"],), True)) == 1,
              "inquiry persists even if operator mail fails")
        check(len([m for m in mails() if m["to"] == "info@bigpaw.site"]) == 2,
              "one operator mail attempt per accepted inquiry including rejected transport")
        check(len(sql("SELECT id FROM notifications WHERE user_id='u_admin' AND type='inquiry'", read=True)) == 2,
              "in-app operator notification remains on mail failure")

        reject_operator.unlink()
        puppy("p_ops_no_breeder", None, "犬舎未設定の子犬", "確認待ち")
        status3, result3 = request("POST", "/api/inquiries",
                                   {"puppyId": "p_ops_no_breeder"}, "u_demo")
        check(status3 == 201 and result3.get("id"),
              "valid inquiry without attached breeder is handled")
        third = [m for m in mails() if m["to"] == "info@bigpaw.site"][-1]
        check("確認待ち" in third["body"] and "犬舎未設定の子犬" in third["body"],
              "operator email still identifies puppy with no breeder assigned")
        print("OPERATOR_INQUIRY_NOTIFICATION_REGRESSION_OK", flush=True)
    finally:
        if process:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
        log.close()
        SERVER.write_text(ORIGINAL, encoding="utf-8")
