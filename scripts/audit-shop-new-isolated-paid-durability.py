"""Recover one NEW staging Square Sandbox paid order read-only, without IDs in logs.

No payment, webhook POST, refund, email, or Square subscription mutation.
A second, explicitly opted-in phase can read the isolated staging order
status via Basic Auth; only while preview is temporarily ON.
"""
import argparse
import base64
import json
import os
import re
import sys
from urllib.error import HTTPError,URLError
from urllib.parse import urlencode
from urllib.request import Request,urlopen

SQUARE="https://connect.squareupsandbox.com/v2"
RAILWAY="https://backboard.railway.com/graphql/v2"
HOST="https://bigpaw-square-sandbox-staging-staging.up.railway.app"
PROJECT="91215e46-028b-4280-90f4-8d192c687164"
ENV="d0dacfcc-781b-4360-b539-461783ad47e2"
SERVICE="ca40ca3c-d65a-4f51-99f3-b85ebfca164d"
REF="refs/heads/feature/dogfood-shop-staging-20261028"
START="2026-10-31T01:02:00Z"
END="2026-10-31T01:08:30Z"
ORDER_NOTE=re.compile(r"BIG PAW food order (FOOD[0-9a-f]{32})\Z")
IDENT=re.compile(r"[A-Za-z0-9_-]{8,192}\Z")
VERSION="2026-09-16"

def _read(req):
    with urlopen(req,timeout=18) as r:
        if r.status!=200:raise ValueError("Non-success read")
        blob=r.read(262145)
        if len(blob)>262144:raise ValueError("Provider response too big")
        out=json.loads(blob)
        if not isinstance(out,dict):raise ValueError("Unexpected JSON")
        return out

def sq(path,token,params=None):
    assert path.startswith("/") and not path.startswith("//")
    url=SQUARE+path+("?"+urlencode(params) if params else "")
    req=Request(url,headers={"Authorization":"Bearer "+token,
             "Square-Version":VERSION,"Accept":"application/json",
             "User-Agent":"BIGPAW-StagingPaidRecovery/1.0"},method="GET")
    return _read(req)

def recover_payment(token,location):
    cursor=None
    seen=set()
    hits=[]
    for _ in range(10):
        params={"begin_time":START,"end_time":END,"location_id":location,"limit":100}
        if cursor:params["cursor"]=cursor
        obj=sq("/payments",token,params)
        items=obj.get("payments",[])
        if not isinstance(items,list):raise ValueError("Unexpected payment list")
        for p in items:
            if not isinstance(p,dict):continue
            note=p.get("note")
            if not isinstance(note,str):continue
            m=ORDER_NOTE.fullmatch(note)
            if not m:continue
            if (p.get("status")!="COMPLETED" or
                p.get("location_id")!=location or
                not isinstance(p.get("amount_money"),dict) or
                p["amount_money"].get("amount")!=21450 or
                p["amount_money"].get("currency")!="JPY"):
                continue
            if not isinstance(p.get("id"),str) or not IDENT.fullmatch(p["id"]):
                raise ValueError("Unexpected Square payment identity")
            if not isinstance(p.get("order_id"),str) or not IDENT.fullmatch(p["order_id"]):
                raise ValueError("Unexpected Square order identity")
            hits.append((p["id"],p["order_id"],m.group(1)))
        cursor=obj.get("cursor")
        if not cursor:break
        if not isinstance(cursor,str) or cursor in seen:raise ValueError("Invalid pagination cursor")
        seen.add(cursor)
    else:raise ValueError("Payment listing incomplete")
    if len(hits)!=1:raise ValueError("Cannot uniquely identify one staged payment")
    pay_id,sq_order,local=hits[0]
    payment=sq("/payments/"+pay_id,token).get("payment")
    order=sq("/orders/"+sq_order,token).get("order")
    if not isinstance(payment,dict) or not isinstance(order,dict):
        raise ValueError("Fresh Square data unavailable")
    amount=payment.get("amount_money")
    if (payment.get("id")!=pay_id or payment.get("order_id")!=sq_order
            or payment.get("status")!="COMPLETED" or payment.get("location_id")!=location
            or not isinstance(amount,dict) or amount.get("amount")!=21450
            or amount.get("currency")!="JPY" or payment.get("note")!="BIG PAW food order "+local
            or order.get("id")!=sq_order):
        raise ValueError("Square payment or order mismatch")
    return local

def railway(token):
    def gql(query,variables=None):
        req=Request(RAILWAY,method="POST",data=json.dumps({"query":query,"variables":variables or {}}).encode(),
            headers={"Project-Access-Token":token,"Content-Type":"application/json",
                     "User-Agent":"BIGPAW-StagingPaidRecovery/1.0"})
        obj=_read(req)
        if obj.get("errors"):raise ValueError("Railway read denied")
        return obj.get("data")
    sc=gql("query{projectToken{projectId environmentId}}")
    ident=sc.get("projectToken") if isinstance(sc,dict) else None
    if ident!={"projectId":PROJECT,"environmentId":ENV}:raise ValueError("Wrong Railway scope")
    obj=gql("query vars($projectId:String!,$environmentId:String!,$serviceId:String){variables(projectId:$projectId,environmentId:$environmentId,serviceId:$serviceId)}",
            {"projectId":PROJECT,"environmentId":ENV,"serviceId":SERVICE})
    v=obj.get("variables") if isinstance(obj,dict) else None
    if not isinstance(v,dict):raise ValueError("No restricted staging variables")
    return v

def paid_read(local,v):
    if v.get("BIGPAW_ENV")!="sandbox" or v.get("BIGPAW_SHOP_STAGE_PREVIEW_ENABLED")!="1":
        raise ValueError("Private test preview must be temporarily enabled for status read")
    user=v.get("BIGPAW_SHOP_STAGE_PREVIEW_USER")
    password=v.get("BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD")
    if not isinstance(user,str) or not user or not isinstance(password,str) or len(password)<32:
        raise ValueError("Private staging authentication unavailable")
    auth=base64.b64encode((user+":"+password).encode()).decode()
    req=Request(HOST+"/api/shop/sandbox/order/"+local,
        headers={"Authorization":"Basic "+auth,"User-Agent":"BIGPAW-StagingPaidRecovery/1.0"},
        method="GET")
    info=_read(req)
    if info.get("order_status")!="paid":raise ValueError("Staging database not paid after rollback")
    return True

def run(phase):
    if (os.getenv("GITHUB_ACTIONS")!="true" or os.getenv("GITHUB_REF")!=REF
            or os.getenv("BIGPAW_STAGING_PAID_RECOVERY_READONLY_OPT_IN")!="1"):
        print("SHOP_STAGING_PAID_RECOVERY=OUT_OF_SCOPE")
        return 3
    if os.getenv("GITHUB_RUN_ATTEMPT")!="1":
        print("SHOP_STAGING_PAID_RECOVERY=RERUN_BLOCKED")
        return 3
    token=os.getenv("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","").strip()
    location=os.getenv("BIGPAW_SQUARE_SANDBOX_LOCATION_ID","").strip()
    railwaytoken=os.getenv("BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN","").strip()
    if min(len(token),len(location),len(railwaytoken))<8:
        print("SHOP_STAGING_PAID_RECOVERY=AUTH_UNAVAILABLE")
        return 2
    try:
        var=railway(railwaytoken)
        if var.get("BIGPAW_ENV")!="sandbox" or var.get("BIGPAW_SHOP_STAGING_ISOLATED")!="1":
            raise ValueError("Staging scope incorrect")
        if var.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID")!=location:
            raise ValueError("Square location mismatch")
        local=recover_payment(token,location)
        print("SHOP_STAGING_SQUARE_PAYMENT=UNIQUE_FRESH_VERIFIED_JPY_21450")
        if phase=="paid":
            paid_read(local,var)
            print("SHOP_STAGING_ISOLATED_DURABLE_ORDER_AFTER_REDEPLOY=PAID")
        else:
            print("SHOP_STAGING_ISOLATED_DURABLE_ORDER_AFTER_REDEPLOY=NOT_CHECKED")
        print("SHOP_STAGING_PAYMENT_CREATED=NO")
        print("SHOP_STAGING_CUSTOMER_DATA_LOGGED=NO")
        return 0
    except HTTPError as exc:
        # Never expose any response headers or body, URI or secrets.
        print("SHOP_STAGING_PAID_RECOVERY=PROTECTED_HTTP_" + str(exc.code))
        return 2
    except ValueError as exc:
        # Strict whitelist, all other provider/credential details remain hidden.
        diagnostic = {
            "Private test preview must be temporarily enabled for status read": "STAGING_FLAG_NOT_ENABLED",
            "Private staging authentication unavailable": "STAGING_AUTH_NOT_READY",
            "Staging database not paid after rollback": "DURABLE_STATE_NOT_PAID",
            "Wrong Railway scope": "WRONG_RAILWAY_SCOPE",
        }.get(str(exc), "UNVERIFIED_VALUE_ERROR")
        print("SHOP_STAGING_PAID_RECOVERY=" + diagnostic)
        return 2
    except (URLError,TimeoutError,OSError,TypeError,KeyError):
        print("SHOP_STAGING_PAID_RECOVERY=INCONCLUSIVE_FAIL_CLOSED")
        return 2

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=("square","paid"))
    args=parser.parse_args()
    sys.exit(run(args.phase))
