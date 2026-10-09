#!/usr/bin/env python3
"""One-time, opt-in test mail to BIG PAW's own info address.

Uses exactly the live backend's send_mail implementation, extracted as a
single AST function without importing / starting the HTTP server. No test
application, user account, or production database row is created.
"""
from __future__ import annotations

import ast
import json
import os
from pathlib import Path
import re
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

TARGET = "info@bigpaw.site"
ENV_KEY = "BIGPAW_ONE_TIME_MAIL_PROBE_ID"
API_URL = "https://api.resend.com/emails?limit=100"
FINAL_EVENTS = {"delivered", "bounced", "complained", "failed", "canceled"}


def live_send_mail():
    """Load only the exact deployed send_mail function; never execute server startup."""
    source = Path(__file__).with_name("server.py")
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    fns = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name == "send_mail"]
    if len(fns) != 1:
        raise RuntimeError("cannot locate unique BIG PAW mailer")
    scope = {}
    exec(compile(ast.Module(body=[fns[0]], type_ignores=[]), str(source), "exec"), scope)
    return scope["send_mail"]


def subject_for(probe_id):
    return "【BIG PAW】ブリーダー申請通知メール配信テスト " + probe_id


def send_once(probe_id, data_dir, sender):
    """Return (result, mail_accepted) and never send twice per persistent marker."""
    if not isinstance(probe_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,64}", probe_id):
        return "invalid_probe_id", False
    folder = Path(data_dir)
    folder.mkdir(parents=True, exist_ok=True)
    marker = folder / (".bigpaw-mail-test-" + probe_id + ".once")
    try:
        fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return "already_attempted", False
    with os.fdopen(fd, "w", encoding="utf-8") as out:
        out.write("attempt_reserved\n")
    message = (
        "これはBIG PAW運営による自動通知メールの配信テストです。\n"
        "実際のブリーダー申請があったわけではありません。\n\n"
        "送信元: BIG PAW <noreply@bigpaw.site>\n"
        "宛先: info@bigpaw.site\n"
        "テスト識別番号: " + probe_id + "\n\n"
        "このメールが表示されれば、BIG PAWからの自動メールを受信できています。\n"
        "BIG PAW https://bigpaw.site/\n"
    )
    try:
        accepted = bool(sender(TARGET, subject_for(probe_id), message))
    except Exception as exc:
        print("BIGPAW_MAIL_TEST|result=mailer_exception|kind=" + type(exc).__name__, flush=True)
        return "mailer_exception", False
    return ("provider_accepted" if accepted else "provider_rejected"), accepted


def check_resend_status(probe_id, key, opener=urlopen, sleeper=time.sleep, attempts=7):
    """Inspect the provider event without reading inbox messages or personal mail."""
    wanted_subject = subject_for(probe_id)
    last_event = "not_found"
    last_id = ""
    for n in range(attempts):
        if n:
            sleeper(2)
        req = Request(API_URL, headers={
            "Authorization": "Bearer " + key,
            "User-Agent": "BIGPAW-One-Time-Mail-Test/1.0",
            "Accept": "application/json",
        })
        try:
            with opener(req, timeout=10) as resp:
                payload = json.load(resp)
        except HTTPError as exc:
            return "provider_http_" + str(exc.code), ""
        except (URLError, TimeoutError, ValueError, OSError, TypeError) as exc:
            return "provider_query_" + type(exc).__name__, ""
        rows = payload.get("data") if isinstance(payload, dict) else None
        if not isinstance(rows, list):
            return "invalid_provider_response", ""
        for item in rows:
            if not isinstance(item, dict) or str(item.get("subject") or "") != wanted_subject:
                continue
            recipients = item.get("to") or []
            if isinstance(recipients, str):
                recipients = [recipients]
            if TARGET not in {str(a).strip().lower() for a in recipients}:
                continue
            last_event = str(item.get("last_event") or "unknown")[:60].lower()
            last_id = str(item.get("id") or "")[:100]
            if last_event in FINAL_EVENTS:
                return last_event, last_id
            break
    return last_event, last_id


def main():
    probe_id = os.environ.get(ENV_KEY, "").strip()
    if not probe_id:
        return 0
    key = (os.environ.get("RESEND_API_KEY") or "").strip()
    if not key:
        print("BIGPAW_MAIL_TEST|result=unavailable|reason=no_resend_key", flush=True)
        return 0
    data = os.environ.get("BIGPAW_DATA_DIR", "/tmp").strip() or "/tmp"
    result, accepted = send_once(probe_id, data, live_send_mail())
    print("BIGPAW_MAIL_TEST|result=" + result + "|target=info@bigpaw.site", flush=True)
    if accepted:
        event, provider_id = check_resend_status(probe_id, key)
        print("BIGPAW_MAIL_TEST_DELIVERY|event=" + event + "|provider_id=" + provider_id, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
