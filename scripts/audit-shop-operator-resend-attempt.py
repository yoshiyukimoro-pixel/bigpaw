"""Read-only Resend provider audit after attempted one-time owner test email.

NEVER sends mail or retries a potentially accepted send. Query only recent
sent emails/logs via GET; print event/status codes, not messages, IDs or keys.
"""
from __future__ import annotations
from datetime import datetime,timezone
import json
import os
import re
import sys
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

START=datetime(2026,10,29,22,55,tzinfo=timezone.utc).timestamp()
END=datetime(2026,10,29,23,10,tzinfo=timezone.utc).timestamp()
SUBJECT="[Square Sandboxテスト・実注文ではありません] 【BIG PAW・要対応】フード注文の決済確認"
TARGET="info@bigpaw.site"
FROM="BIG PAW <noreply@bigpaw.site>"
BASE="https://api.resend.com"


def get_json(uri,key,opener=urlopen):
    req=Request(uri,headers={
        "Authorization":"Bearer "+key,
        "Accept":"application/json",
        "User-Agent":"BIGPAW-ReadOnly-Sandbox-Mail-Audit/1.0",
    },method="GET")
    try:
        with opener(req,timeout=10) as response:
            if response.status!=200: return {"_http":str(response.status)}
            return json.loads(response.read(262144))
    except HTTPError as exc:
        # Only print provider-defined symbolic error names, NEVER free-text
        # messages, API key, addresses, request content, or response headers.
        name="UNKNOWN"
        try:
            body=json.loads(exc.read(4096))
            raw=body.get("name",body.get("code",""))
            if isinstance(raw,str) and re.fullmatch(r"[A-Za-z_]{3,50}",raw):
                name=raw
        except (ValueError,TypeError,IndexError,KeyError):
            pass
        return {"_http":str(exc.code),"_error":name}
    except (URLError,TimeoutError,ValueError,TypeError,OSError):
        return {"_http":"network_or_format_error"}


def _ts(value):
    try:
        stamp=datetime.fromisoformat(str(value).replace("Z","+00:00"))
        if stamp.tzinfo is None:return 0.
        return stamp.timestamp()
    except (TypeError,ValueError,OverflowError):
        return 0.


def search_provider_records(key,opener=urlopen):
    response=get_json(BASE+"/emails?limit=100",key,opener=opener)
    if "_http" in response:
        return {"result":"unavailable","http":response["_http"],"error":response.get("_error","UNKNOWN")}
    rows=response.get("data",[])
    if not isinstance(rows,list):return {"result":"invalid_response"}
    matched=[]
    for entry in rows:
        if not isinstance(entry,dict):continue
        to=entry.get("to")
        if (entry.get("subject")!=SUBJECT
            or to!=[TARGET]
            or entry.get("from")!=FROM
            or not START<=_ts(entry.get("created_at"))<=END):
            continue
        matched.append(str(entry.get("last_event") or "unknown")[:40])
    if len(matched)>1:
        return {"result":"ambiguous_multiple_matches","count":len(matched)}
    if len(matched)==1:
        return {"result":"provider_message_found","event":matched[0]}
    return {"result":"not_found_in_first_100","has_more":bool(response.get("has_more"))}


def search_api_log_status(key,opener=urlopen):
    resp=get_json(BASE+"/logs?limit=100",key,opener=opener)
    if "_http" in resp:return {"result":"unavailable","http":resp["_http"],"error":resp.get("_error","UNKNOWN")}
    rows=resp.get("data",[])
    if not isinstance(rows,list):return {"result":"invalid_response"}
    safe=[]
    for entry in rows:
        if not isinstance(entry,dict):continue
        stamp=_ts(entry.get("created_at") or entry.get("timestamp"))
        if not START<=stamp<=END:continue
        method=str(entry.get("method") or entry.get("request_method") or "").upper()
        path=str(entry.get("path") or entry.get("endpoint") or "")
        if method=="POST" and path in ("/emails","https://api.resend.com/emails"):
            code=entry.get("status_code",entry.get("status",None))
            if type(code) is int and 100<=code<=599:
                safe.append(code)
    return {"result":"checked","status_codes":safe[:10],"num":len(safe)}


def main(env=None,opener=urlopen):
    env=os.environ if env is None else env
    if not (
        env.get("GITHUB_ACTIONS")=="true"
        and env.get("GITHUB_REF")=="refs/heads/feature/dogfood-shop-staging-20261028"
    ):
        print("FOOD_OWNER_MAIL_AUDIT=BLOCKED")
        return 3
    key=str(env.get("RESEND_API_KEY") or "").strip()
    if not key:
        print("FOOD_OWNER_MAIL_AUDIT=NO_READ_KEY")
        return 2
    mail=search_provider_records(key,opener=opener)
    logs=search_api_log_status(key,opener=opener)
    print("FOOD_OWNER_MAIL_AUDIT="+json.dumps(mail,sort_keys=True,separators=(",",":")))
    print("FOOD_OWNER_MAIL_API_LOG="+json.dumps(logs,sort_keys=True,separators=(",",":")))
    if mail.get("result")=="provider_message_found" and mail.get("event")=="delivered":
        print("FOOD_OWNER_MAIL_AUDIT=DELIVERED_TO_MAIL_SERVER")
        return 0
    print("FOOD_OWNER_MAIL_AUDIT=DELIVERY_UNVERIFIED")
    return 4


if __name__=="__main__":
    sys.exit(main())
