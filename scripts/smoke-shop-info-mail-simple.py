"""BIG PAW one-shot simple real mail diagnostic. Authorized recipient: info@bigpaw.site.

No Square fixture or actual order. The single test is triggered ONLY by an
explicit tagged commit on the private staging branch; never in production.
The script POSTs once and never retries. A provider receipt ('accepted') is
not proof of delivered email. Never prints API key, email ID or payload.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

HOST = "https://api.resend.com"
TO = "info@bigpaw.site"
FROM = "BIG PAW <noreply@bigpaw.site>"
SUBJECT = "【BIG PAW】メール送信テスト（2026年10月30日・実注文ではありません）"
BODY = (
    "BIG PAW ドッグフードショップの通知メールが正しく届くかのテストです。\n"
    "これは実際の注文・決済・発送・仕入れ依頼ではありません。\n"
    "トランペッツへの発注は不要です。\n"
    "このメールが info@bigpaw.site で受信できればテスト受信の確認になります。\n"
)
KEY = "bigpaw-shop-owner-info-test-20261030-v2"
REF = "refs/heads/feature/dogfood-shop-staging-20261028"


def diagnostic(exc):
    """Only predefined error category; never expose provider free text."""
    symbol="unknown"
    category="unclassified"
    try:
        details=json.loads(exc.read(4096))
        name=details.get("name",details.get("code",""))
        if isinstance(name,str) and re.fullmatch(r"[a-zA-Z_]{3,50}",name):
            symbol=name
        message=str(details.get("message","")).lower()
        if any(p in message for p in ("domain", "verify", "verified")):
            category="sender_domain"
        elif any(p in message for p in ("idempot", "duplicate")):
            category="idempotency"
        elif any(p in message for p in ("from", "sender")):
            category="sender"
        elif any(p in message for p in ("to", "recipient", "email address")):
            category="recipient"
        elif any(p in message for p in ("api key", "authentication", "authorization")):
            category="api_key_or_scope"
        elif any(p in message for p in ("limit", "invalid", "validation", "required", "parameter")):
            category="parameter_validation"
    except (ValueError,TypeError,KeyError,AttributeError):
        pass
    return {"http":exc.code,"error":symbol,"category":category}


def once(*, env=None, opener=urlopen, delay=time.sleep):
    env = os.environ if env is None else env
    if not (
        env.get("GITHUB_ACTIONS")=="true"
        and env.get("GITHUB_REF")==REF
        and env.get("BIGPAW_SINGLE_INFO_EMAIL_TEST")=="1"
    ):
        print("BIGPAW_REAL_MAIL_TEST=BLOCKED")
        return 3
    key=(env.get("RESEND_API_KEY") or "").strip()
    if not key:
        print("BIGPAW_REAL_MAIL_TEST=NOT_CONFIGURED")
        return 2
    if not key.startswith("re_") or any(ch.isspace() for ch in key):
        print("BIGPAW_REAL_MAIL_TEST=INVALID_KEY_FORMAT")
        return 2
    body=json.dumps({"from":FROM,"to":[TO],"subject":SUBJECT,"text":BODY},
                    ensure_ascii=False).encode("utf-8")
    request=Request(HOST+"/emails",data=body,method="POST",headers={
        "Authorization":"Bearer "+key,
        "Content-Type":"application/json",
        "Accept":"application/json",
        "Idempotency-Key":KEY,
        "User-Agent":"BIGPAW-Shop-Single-Mail-Check/1.0",
    })
    try:
        with opener(request,timeout=15) as response:
            if response.status not in (200,201):
                print("BIGPAW_REAL_MAIL_TEST=API_RESPONSE_NOT_ACCEPTED")
                return 1
            payload=json.loads(response.read(4096))
        email_id=payload.get("id")
        if not isinstance(email_id,str) or not re.fullmatch(r"[a-zA-Z0-9_-]{8,100}",email_id):
            print("BIGPAW_REAL_MAIL_TEST=RECEIPT_UNVERIFIED")
            return 4
        print("BIGPAW_REAL_MAIL_TEST=ACCEPTED: Resend accepted one test email for info@bigpaw.site")
    except HTTPError as exc:
        details=diagnostic(exc)
        print("BIGPAW_REAL_MAIL_TEST=REJECTED "+json.dumps(details,separators=(",",":")))
        return 1
    except (URLError,TimeoutError,OSError,ValueError,TypeError):
        print("BIGPAW_REAL_MAIL_TEST=UNCERTAIN: do NOT retry, provider may have accepted")
        return 4

    # Pure read requests: no additional sending on failure or ambiguous state.
    for attempt in range(5):
        if attempt:delay(3)
        req=Request(HOST+"/emails/"+email_id,method="GET",headers={
            "Authorization":"Bearer "+key,
            "Accept":"application/json",
            "User-Agent":"BIGPAW-Shop-Single-Mail-Check/1.0",
        })
        try:
            with opener(req,timeout=12) as response:
                if response.status!=200:continue
                info=json.loads(response.read(8192))
            if info.get("id")!=email_id or info.get("to")!=[TO]:
                print("BIGPAW_REAL_MAIL_TEST=RECEIPT_MISMATCH")
                return 4
            event=str(info.get("last_event") or "unknown").lower()
            if event=="delivered":
                print("BIGPAW_REAL_MAIL_TEST=DELIVERED: recipient mail server accepted; inbox view not checked")
                return 0
            if event in ("bounced","complained","failed","canceled"):
                print("BIGPAW_REAL_MAIL_TEST=DELIVERY_FAILED event="+event)
                return 5
        except (HTTPError,URLError,OSError,TimeoutError,ValueError,TypeError):
            continue
    print("BIGPAW_REAL_MAIL_TEST=ACCEPTED_DELIVERY_UNVERIFIED: do NOT resend automatically")
    return 4


if __name__=="__main__":
    sys.exit(once())
