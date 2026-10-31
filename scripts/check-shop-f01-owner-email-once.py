"""One and ONLY one Resend test to owner-controlled Gmail, not a customer.

Purpose: F01 sender/domain/permission check for BIG PAW food shop.
Runs only in GitHub Actions on the feature branch with explicit one-shot
opt-in; never re-run, retry, or send to customers/suppliers.
Never logs email IDs, authentication, full provider responses, or addresses.
A provider 'accepted' response is NOT proof of recipient delivery.
"""
from __future__ import annotations
import json
import os
import re
import sys
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

REF="refs/heads/feature/dogfood-shop-staging-20261028"
HOST="https://api.resend.com/emails"
FROM="BIG PAW <noreply@bigpaw.site>"
TO="yoshiyukimoro@gmail.com"
SUBJECT="【BIG PAW】フードショップ送信経路テスト（実注文ではありません・2026-10-31）"
BODY=(
    "BIG PAW ドッグフードショップのメール送信経路のテストです。\\n"
    "実際の注文、支払い、発送、仕入先への発注ではありません。\\n"
    "テスト用メールですのでご対応は不要です。\\n"
)
KEY="bigpaw-shop-f01-self-mail-proof-20261031-v1"

def once(env=None,opener=urlopen):
    env=os.environ if env is None else env
    if (env.get("GITHUB_ACTIONS")!="true"
            or env.get("GITHUB_REF")!=REF
            or env.get("GITHUB_RUN_ATTEMPT")!="1"
            or env.get("BIGPAW_ONE_SHOP_SENDER_TEST_OPT_IN")!="1"):
        return "REFUSE_SCOPE_OR_RERUN",3
    token=env.get("RESEND_API_KEY","")
    if not isinstance(token,str) or not re.fullmatch(r"re_[A-Za-z0-9_-]{8,256}",token):
        return "RESEND_SHOP_KEY_UNAVAILABLE",2
    body=json.dumps({
        "from":FROM,"to":[TO],"subject":SUBJECT,"text":BODY
    },ensure_ascii=False,separators=(",",":")).encode("utf-8")
    req=Request(HOST,data=body,method="POST",headers={
        "Authorization":"Bearer "+token,
        "Content-Type":"application/json",
        "Accept":"application/json",
        "Idempotency-Key":KEY,
        "User-Agent":"BIGPAW-Shop-Sender-F01-InternalTest/1.0",
    })
    # One POST only. Even after network timeout, do not retry unknown result.
    try:
        with opener(req,timeout=22) as response:
            if response.status not in (200,201):
                return "RESEND_HTTP_STATUS_NOT_ACCEPTED",2
            raw=response.read(8193)
            if len(raw)>8192:return "RESEND_RESPONSE_OVERSIZE",2
            obj=json.loads(raw)
        ident=obj.get("id") if isinstance(obj,dict) else None
        if not isinstance(ident,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,128}",ident):
            return "RESEND_ACCEPTANCE_UNCERTAIN",2
        return "RESEND_ACCEPTED_ONE_INTERNAL_TEST_DELIVERY_UNCONFIRMED",0
    except HTTPError as error:
        if error.code in (401,403):return "RESEND_SENDING_PERMISSION_DENIED",2
        if error.code==422:return "RESEND_REQUEST_VALIDATION_REJECTED",2
        return "RESEND_PROVIDER_HTTP_"+str(error.code),2
    except (URLError,TimeoutError,OSError,ValueError,TypeError,UnicodeError):
        return "RESEND_NETWORK_RESULT_UNKNOWN_DO_NOT_RETRY",2

def main():
    result,code=once()
    print("SHOP_F01_RESEND_INTERNAL_TEST="+result)
    print("SHOP_F01_MAILS_ATTEMPTED=AT_MOST_ONE")
    print("SHOP_F01_CUSTOMER_OR_SUPPLIER_MAIL=NO")
    print("SHOP_F01_PROVIDER_ACCEPTED_IS_NOT_DELIVERED=TRUE")
    return code

if __name__=="__main__":sys.exit(main())
