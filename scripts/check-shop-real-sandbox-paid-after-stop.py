"""Read-only Square Sandbox order recheck after isolated checkout preview OFF.

The ONLY POST to the NEW isolated HTTP webhook is a synthetic HMAC signed
recheck of an already independently VERIFIED fake Sandbox COMPLETED Payment.
No Checkout, no Square Payment POST, no customer mail, no activation, no
production domain, no URLs/IDs/PII in any log. This proves NEW persistent
SQLite order survived preview shutdown/redeployment and still acknowledges
its already-paid fake Sandbox order.
"""
from __future__ import annotations
import base64
from datetime import datetime, timezone
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
import re
import sys
import uuid
from urllib.parse import urlencode
from urllib.error import HTTPError,URLError

path=Path(__file__).with_name("smoke-shop-new-isolated-paid-checkout.py")
spec=importlib.util.spec_from_file_location("base_checkout",path)
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

SQUARE=base.SQUARE
TARGET=base.WEBHOOK
PROJECT=base.PROJECT
ENV=base.ENV
SERVICE=base.SERVICE
FIRST=datetime.fromisoformat("2026-10-31T01:13:00+00:00")
LAST=datetime.fromisoformat("2026-10-31T01:13:45+00:00")
REF=base.REF

def _scope():
    if (os.environ.get("GITHUB_ACTIONS")!="true"
            or os.environ.get("GITHUB_REF")!=REF
            or os.environ.get("BIGPAW_POST_STOP_DURABILITY_PROOF_OPT_IN")!="1"):
        raise ValueError("Explicit scope missing")
    token=os.environ.get("BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN","")
    sqtoken=os.environ.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","")
    location=os.environ.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID","")
    if len(token)<16 or len(sqtoken)<16 or not location:
        raise ValueError("Staging-only scoped credential missing")
    data=base._railway_request({"query":"query{projectToken{projectId environmentId}}"},token)
    if data.get("projectToken")!={"projectId":PROJECT,"environmentId":ENV}:
        raise ValueError("Non staging token")
    data=base._railway_request({
        "query":"query variables($projectId:String!,$environmentId:String!,$serviceId:String){variables(projectId:$projectId,environmentId:$environmentId,serviceId:$serviceId)}",
        "variables":{"projectId":PROJECT,"environmentId":ENV,"serviceId":SERVICE},
    },token)
    var=data.get("variables")
    if not isinstance(var,dict) or any(var.get(k)!=v for k,v in {
        "BIGPAW_ENV":"sandbox",
        "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID":PROJECT,
        "BIGPAW_SHOP_STAGE_PREVIEW_ENABLED":"0",
        "BIGPAW_SHOP_STAGING_ISOLATED":"1",
        "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL":TARGET,
        "BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED":"0",
        "BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED":"0",
        "BIGPAW_SHOP_SANDBOX_PAID_MAIL_ONCE_ENABLED":"0",
    }.items()):
        raise ValueError("Stop/secret/notification safety not proven")
    if var.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN")!=sqtoken or var.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID")!=location:
        raise ValueError("Square staging token/location differ")
    signature=var.get("BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY")
    if not isinstance(signature,str) or len(signature)<16:
        raise ValueError("Sandbox webhook signature key missing")
    return sqtoken,location,signature

def _test_link(token):
    found=[]
    cursor=None
    seen=set()
    for _ in range(20):
        query={"limit":100}
        if cursor:
            if cursor in seen:raise ValueError("Square cursor loop")
            seen.add(cursor);query["cursor"]=cursor
        data=base._square_get(SQUARE+"/online-checkout/payment-links?"+urlencode(query),token)
        rows=data.get("payment_links")
        if not isinstance(rows,list):
            raise ValueError("Square Sandbox link list invalid")
        for item in rows:
            if not isinstance(item,dict):
                continue
            when=item.get("created_at")
            note=item.get("payment_note")
            if not isinstance(when,str) or not isinstance(note,str):
                continue
            try:
                created=datetime.fromisoformat(when.replace("Z","+00:00"))
            except ValueError:
                continue
            if (created.tzinfo is not None and FIRST<=created<=LAST
                    and re.fullmatch(r"BIG PAW food order FOOD[0-9a-f]{32}",note)):
                found.append(item)
        cursor=data.get("cursor")
        if not cursor:break
        if not isinstance(cursor,str):raise ValueError("Square cursor invalid")
    else:raise ValueError("Partial Square payment link listing")
    if len(found)!=1:
        raise ValueError("Expected one isolated real Sandbox test link in exact window")
    result=found[0]
    sqid=result.get("order_id")
    if not isinstance(sqid,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,192}",sqid):
        raise ValueError("No valid Sandbox order")
    return sqid

def audit():
    token,location,key=_scope()
    base._assert_square_subscription_safety(token)  # old active, new disabled
    sqorder=_test_link(token)
    order=base._square_get(SQUARE+"/orders/"+sqorder,token).get("order")
    if not isinstance(order,dict) or order.get("id")!=sqorder:
        raise ValueError("Square order missing")
    tenders=order.get("tenders")
    if not isinstance(tenders,list) or len(tenders)!=1:
        raise ValueError("Square fake payment tender not unique")
    pid=tenders[0].get("id")
    if not isinstance(pid,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,192}",pid):
        raise ValueError("Invalid Square Payment ID")
    pay=base._square_get(SQUARE+"/payments/"+pid,token).get("payment")
    if not isinstance(pay,dict):raise ValueError("Square fake Payment missing")
    money=pay.get("amount_money")
    refunded=pay.get("refunded_money")
    if (pay.get("id")!=pid or pay.get("order_id")!=sqorder or
            pay.get("location_id")!=location or pay.get("status")!="COMPLETED"
            or not isinstance(money,dict)
            or money.get("currency")!="JPY"
            or type(money.get("amount")) is not int or money.get("amount")!=21450
            or (refunded is not None and
                 (not isinstance(refunded,dict) or refunded.get("amount")!=0
                  or refunded.get("currency")!="JPY"))):
        raise ValueError("Original Sandbox fake Payment changed")
    # One POST only, after Square verification, to new webhook. The NEW
    # subscriber is DISABLED on provider side throughout this separate check.
    event={"event_id":"bigpaw-recheck-"+uuid.uuid4().hex,
           "type":"payment.updated","data":{"object":{"payment":pay}}}
    raw=json.dumps(event,separators=(",",":")).encode()
    sig=base64.b64encode(hmac.new(key.encode(),TARGET.encode()+raw,hashlib.sha256).digest()).decode()
    status,_,body=base._http("/api/shop/sandbox/webhook",method="POST",body=raw,
        accept_status=200,extra={
            "Square-Environment":"Sandbox",
            "X-Square-Hmacsha256-Signature":sig,
        })
    if json.loads(body).get("status")!="received":
        raise ValueError("Previously verified order not durable after stop")
    print("SHOP_POST_STOP_REAL_PAYMENT_PROVIDER=COMPLETED_JPY_21450")
    print("SHOP_POST_STOP_PREVIEW_FLAG=OFF_AND_PRIVATE")
    print("SHOP_POST_STOP_PREVIOUSLY_PAID_ORDER=STILL_ACKNOWLEDGED_AFTER_REDEPLOY")
    print("SHOP_POST_STOP_SQUARE_SUBSCRIPTION=OLD_ACTIVE_NEW_DISABLED")
    print("SHOP_POST_STOP_PAYMENT_OR_LINK_CREATED=NO")
    print("SHOP_POST_STOP_SIGNED_EVENT=NEW_ARTIFICIAL_RECHECK_NOT_SQUARE_DELIVERY")
    print("SHOP_POST_STOP_REAL_CARD_CHARGE_OR_EMAIL=NO")

def main():
    try:
        audit()
        return 0
    except (HTTPError,URLError,TimeoutError,ValueError,TypeError,OSError,KeyError,IndexError,
            json.JSONDecodeError):
        print("SHOP_POST_STOP_DURABILITY=UNVERIFIED_NO_RETRY")
        return 2

if __name__=="__main__":sys.exit(main())
