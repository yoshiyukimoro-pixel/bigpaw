#!/usr/bin/env python3
"""Disposable real-HTTP regression for breeder inquiry reply attention."""
import json
import os
from pathlib import Path
import socket
import sqlite3
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request

ROOT = Path(__file__).resolve().parents[1]

def request(base, method, path, body=None, token=None):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    req = urllib.request.Request(
        base + path,
        data=None if body is None else json.dumps(body, ensure_ascii=False).encode(),
        headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=5) as res:
            return res.status, json.loads(res.read())
    except urllib.error.HTTPError as err:
        return err.code, json.loads(err.read())

def check(ok, name):
    assert ok, name
    print("PASS", name, flush=True)

with tempfile.TemporaryDirectory(prefix="bigpaw-reply-e2e-") as directory:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    dbfile = Path(directory) / "bigpaw.sqlite3"
    env = os.environ.copy()
    env.update({"BIGPAW_ENV": "development", "BIGPAW_DATA_DIR": directory,
                "PORT": str(port), "BIGPAW_AUTO_BACKUP_HOURS": "999999",
                "BIGPAW_DEV_LINKS": "1"})

    def start_server():
        proc = subprocess.Popen(
            [sys.executable, str(ROOT / "app/backend/server.py")],
            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
        for _ in range(90):
            if proc.poll() is not None:
                raise AssertionError("server crashed on startup")
            try:
                status, health = request(base, "GET", "/api/health")
                if status == 200:
                    return proc
            except (OSError, ValueError):
                pass
            time.sleep(.2)
        proc.terminate()
        raise AssertionError("server failed to become ready")

    def stop_server(proc):
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=10)

    def login(mail, password):
        code, result = request(base, "POST", "/api/login",
                               {"email": mail, "password": password})
        check(code == 200 and bool(result.get("token")), f"login {mail}")
        return result["token"]

    def query_inquiry(token, inquiry_id):
        code, rows = request(base, "GET", "/api/inquiries", token=token)
        check(code == 200, "retrieve breeder inquiries")
        return next(row for row in rows if row["id"] == inquiry_id)

    proc = start_server()
    try:
        buyer = login("demo@bigpaw.jp", "demo1234")
        breeder = login("dog44@bigpaw.jp", "demo1234")
        code, puppies = request(base, "GET", "/api/puppies")
        check(code == 200 and any(p["id"] == "p1" for p in puppies), "seed puppy is available")

        def new_inquiry():
            code, inquiry = request(base, "POST", "/api/inquiries",
                                    {"puppyId": "p1", "name": "返信検証", "message": "見学できますか"},
                                    buyer)
            check(code == 201, "create inquiry")
            return inquiry["id"]

        first_id = new_inquiry()
        check(query_inquiry(breeder, first_id)["needs_reply"] == 1, "new inquiry needs reply")

        def send(token, message):
            code, result = request(base, "POST",
                                   f"/api/inquiries/{first_id}/messages",
                                   {"body": message}, token)
            check(code == 201, f"send message: {message}")

        send(breeder, "見学できます")
        first = query_inquiry(breeder, first_id)
        check(first["needs_reply"] == 0 and first["status"] == "返信済み",
              "breeder reply clears badge automatically")

        send(buyer, "もう一度質問です")
        first = query_inquiry(breeder, first_id)
        check(first["needs_reply"] == 1 and first["status"] == "未返信",
              "buyer follow-up restores badge")

        send(breeder, "回答しました")
        check(query_inquiry(breeder, first_id)["needs_reply"] == 0,
              "second breeder response clears badge")

        code, visit = request(base, "POST", f"/api/inquiries/{first_id}/visit",
                              {"date": "2026-11-01", "time": "14:00",
                               "status": "confirmed", "faceToFaceConfirmed": True},
                              breeder)
        check(code == 201, "confirm visit")
        first = query_inquiry(breeder, first_id)
        check(first["status"] == "見学確定" and first["needs_reply"] == 0,
              "confirmed visit needs no response")

        send(buyer, "当日の駐車場を教えてください")
        first = query_inquiry(breeder, first_id)
        check(first["status"] == "見学確定" and first["needs_reply"] == 1,
              "buyer follow-up after visit confirmation needs reply without losing visit status")

        code, _ = request(base, "PATCH", f"/api/inquiries/{first_id}",
                          {"needsReply": False}, buyer)
        check(code == 403, "buyer cannot dismiss breeder attention")
        code, res = request(base, "PATCH", f"/api/inquiries/{first_id}",
                            {"needsReply": False}, breeder)
        check(code == 200 and res["needs_reply"] == 0 and res["status"] == "見学確定",
              "breeder can manually resolve without changing visit status")

        send(buyer, "新しい問い合わせです")
        check(query_inquiry(breeder, first_id)["needs_reply"] == 1,
              "new buyer reply reopens a manually resolved inquiry")
        send(breeder, "再度返信しました")
        check(query_inquiry(breeder, first_id)["needs_reply"] == 0,
              "breeder response resolves new follow-up")

        second_id = new_inquiry()
        check(query_inquiry(breeder, second_id)["needs_reply"] == 1,
              "different unanswered inquiry remains visible")
        code, msgs = request(base, "GET",
                             f"/api/inquiries/{first_id}/messages", token=breeder)
        check(code == 200 and len(msgs) == 6, "original message history is preserved")
    finally:
        stop_server(proc)

    # Emulate an older production SQLite file that did not yet have the column.
    con = sqlite3.connect(dbfile)
    con.execute("ALTER TABLE inquiries DROP COLUMN needs_reply")
    con.commit()
    con.close()
    proc = start_server()
    try:
        breeder = login("dog44@bigpaw.jp", "demo1234")
        first = query_inquiry(breeder, first_id)
        second = query_inquiry(breeder, second_id)
        check(first["needs_reply"] == 0 and second["needs_reply"] == 1,
              "first-start migration reconstructs replied/unanswered state")
        code, msgs = request(base, "GET",
                             f"/api/inquiries/{first_id}/messages", token=breeder)
        check(code == 200 and len(msgs) == 6, "migration preserves chat history")
    finally:
        stop_server(proc)

print("INQUIRY_REPLY_STATE_E2E_OK")
