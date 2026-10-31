"""Square-originated payment.updated Webhook E2E, ONE FAKE Sandbox payment.

This program never calls Square Production, never sends email, never creates
a real charge, never prints IDs/URLs/credentials/customer data. It changes
ONLY the new Square Sandbox subscription enabled flag. Old subscriber is
read-only. The workflow MUST execute 'off' in an always() cleanup step.

Use only after explicit one-shot opt-in on the feature branch, with new
isolated preview credentials and a distinct Github job. Never automatically
retry a checkout or the Square Hosted Testing Panel.
"""
from __future__ import annotations
import argparse
import json
import os
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import importlib.util
base_path=Path(__file__).with_name("smoke-shop-new-isolated-paid-checkout.py")
spec=importlib.util.spec_from_file_location("sandbox_new_base",base_path)
base=importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)

API=base.SQUARE+"/webhooks/subscriptions"
NEW=base.WEBHOOK
OLD="https://bigpaw-test-production.up.railway.app/api/shop/sandbox/webhook"
REF=base.REF

def _allowed():
    if (os.environ.get("GITHUB_ACTIONS")!="true"
            or os.environ.get("GITHUB_REF")!=REF
            or os.environ.get("BIGPAW_SQUARE_ORIGIN_NEW_STAGING_ONESHOT_OPT_IN")!="1"):
        raise ValueError("scope_optin_denied")
    t=os.environ.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","")
    if len(t)<16:raise ValueError("missing_sandbox_only_access")
    return t

def _subs(token):
    cursor=None
    rows=[]
    seen=set()
    for _ in range(5):
        query={"include_disabled":"true","limit":100}
        if cursor:
            if cursor in seen:raise ValueError("Square subscription pagination loop")
            seen.add(cursor)
            query["cursor"]=cursor
        data=base._square_get(API+"?"+urlencode(query),token)
        values=data.get("subscriptions")
        if not isinstance(values,list):raise ValueError("Square subscriptions unavailable")
        rows.extend(values)
        cursor=data.get("cursor")
        if not cursor:break
        if not isinstance(cursor,str):raise ValueError("Bad cursor")
    else:raise ValueError("Incomplete subscription enumeration")
    previous=[s for s in rows if isinstance(s,dict) and s.get("notification_url")==OLD]
    current=[s for s in rows if isinstance(s,dict) and s.get("notification_url")==NEW]
    if (len(previous)!=1 or previous[0].get("enabled") is not True
            or "payment.updated" not in previous[0].get("event_types",[])
            or len(current)!=1 or "payment.updated" not in current[0].get("event_types",[])):
        raise ValueError("Old/new Sandbox subscriptions do not match approved isolated plan")
    sid=current[0].get("id")
    if not isinstance(sid,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,96}",sid):
        raise ValueError("Invalid isolated Sandbox subscription ID")
    return sid,current[0]

def _update(token,sid,enabled):
    # Exactly one private Square Sandbox PUT. Never touch a different URL,
    # rotate signature key, or modify original subscription.
    req=Request(API+"/"+sid,method="PUT",data=json.dumps(
        {"subscription":{"enabled":bool(enabled)}},separators=(",",":")
    ).encode(),headers={
        "Authorization":"Bearer "+token,
        "Square-Version":"2026-09-16",
        "Content-Type":"application/json",
        "Accept":"application/json",
        "User-Agent":"BIGPAW-IsolatedSquareOriginTest/1.0",
    })
    with urlopen(req,timeout=18) as response:
        if response.status!=200:raise ValueError("Square update not confirmed")
        raw=response.read(131073)
        if len(raw)>131072:raise ValueError("Oversize Square response")
        obj=json.loads(raw)
    item=obj.get("subscription") if isinstance(obj,dict) else None
    if (not isinstance(item,dict) or item.get("id")!=sid
            or item.get("notification_url")!=NEW
            or item.get("enabled") is not enabled):
        raise ValueError("Square subscription update response changed")

def _enabled(token,should_be):
    _,s=_subs(token)
    return s.get("enabled") is should_be

def turn_on():
    token=_allowed()
    # Confirm production isolated, preview private, and no real mail.
    base._scope(None)
    sid,current=_subs(token)
    if current.get("enabled") is not False:
        raise ValueError("New subscription not disabled before one-shot")
    _update(token,sid,True)
    if not _enabled(token,True):
        raise ValueError("New notification subscription not confirmed enabled")
    print("SHOP_SQUARE_NEW_SANDBOX_SUBSCRIPTION=TEMPORARY_ENABLED")
    print("SHOP_SQUARE_OLD_SUBSCRIPTION=READ_ONLY")

def turn_off():
    token=_allowed()
    # Safety cleanup must work even if preview got disabled externally.
    sid,current=_subs(token)
    if current.get("enabled") is not False:
        _update(token,sid,False)
    if not _enabled(token,False):
        raise ValueError("New notification subscription remains active")
    print("SHOP_SQUARE_NEW_SANDBOX_SUBSCRIPTION=DISABLED_CONFIRMED")
    print("SHOP_SQUARE_OLD_SUBSCRIPTION=UNCHANGED_ACTIVE")

def verify_origin():
    token=_allowed()
    conf=base._scope(None)
    if not _enabled(token,True):
        raise ValueError("Real Square webhook not enabled for this test")
    state=json.loads(base._file().read_text())
    order=state.get("shop_order_id")
    link=state.get("link_url")
    if (not isinstance(order,str) or not re.fullmatch(r"FOOD[0-9a-f]{32}",order)
            or not isinstance(link,str) or not link.startswith("https://sandbox.square.link/u/")
            or state.get("amount_yen")!=base.PRICE):
        raise ValueError("Wrong isolated test order state")
    # Authenticate and poll NEW persistent store. No synthetic signed event
    # is sent: only Square can transition pending -> paid during this step.
    ready=False
    for _ in range(30):
        code,_,raw=base._http("/api/shop/sandbox/order/"+order,
                              auth=conf,accept_status=200)
        item=json.loads(raw)
        if item.get("order_status")=="paid":
            ready=True
            break
        if item.get("order_status")!="payment_pending":
            raise ValueError("Unexpected local payment state")
        time.sleep(4)
    if not ready:
        raise ValueError("Square-originated webhook not marked paid within polling window")
    print("SHOP_SQUARE_ORIGIN_STAGING_LEDGER=PAID_BY_AUTOMATIC_WEBHOOK")
    # Independent Square read-only API confirmation, never trust notification
    # or local ledger in isolation.
    cursor=None
    matches=[]
    for _ in range(20):
        query={"limit":100}
        if cursor:query["cursor"]=cursor
        d=base._square_get(base.SQUARE+"/online-checkout/payment-links?"+urlencode(query),
                           conf["square_token"])
        arr=d.get("payment_links")
        if not isinstance(arr,list):raise ValueError("Square link pagination invalid")
        matches.extend(x for x in arr
                       if isinstance(x,dict) and x.get("url")==link)
        cursor=d.get("cursor")
        if not cursor:break
        if not isinstance(cursor,str):raise ValueError("Square cursor invalid")
    else:raise ValueError("Square payment link listing incomplete")
    if len(matches)!=1:raise ValueError("Bound Square link not unique")
    sq_order=matches[0].get("order_id")
    if not isinstance(sq_order,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,192}",sq_order):
        raise ValueError("Square order ID not valid")
    record=base._square_get(base.SQUARE+"/orders/"+sq_order,conf["square_token"]).get("order")
    if not isinstance(record,dict) or record.get("id")!=sq_order:
        raise ValueError("Square Order mismatch")
    tenders=record.get("tenders")
    if not isinstance(tenders,list) or len(tenders)!=1:
        raise ValueError("Square tender missing")
    pid=tenders[0].get("id")
    if not isinstance(pid,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,192}",pid):
        raise ValueError("Square Payment ID invalid")
    payment=base._square_get(base.SQUARE+"/payments/"+pid,conf["square_token"]).get("payment")
    if not isinstance(payment,dict):raise ValueError("Square payment missing")
    money=payment.get("amount_money")
    refund=payment.get("refunded_money")
    if (payment.get("id")!=pid or payment.get("order_id")!=sq_order
            or payment.get("status")!="COMPLETED"
            or payment.get("location_id")!=conf["location"]
            or not isinstance(money,dict)
            or type(money.get("amount")) is not int or money.get("amount")!=base.PRICE
            or money.get("currency")!="JPY"
            or (refund is not None and
                (not isinstance(refund,dict)
                 or type(refund.get("amount")) is not int
                 or refund.get("amount")!=0 or refund.get("currency")!="JPY"))):
        raise ValueError("Provider payment/order/location/currency mismatch")
    print("SHOP_SQUARE_ORIGIN_PROVIDER=COMPLETED_JPY_21450_VERIFIED")
    print("SHOP_SQUARE_ORIGIN_NOTIFICATION=REAL_SQUARE_DELIVERY_NOT_MANUAL_HMAC")
    print("SHOP_SQUARE_ORIGIN_SHIPPING=NOT_VERIFIED")
    print("SHOP_SQUARE_ORIGIN_NO_CUSTOMER_MAIL=YES")
    print("SHOP_SQUARE_ORIGIN_NO_REAL_FUNDS=YES")

def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("phase",choices=["on","verify","off"])
    phase=arg.parse_args().phase
    try:
        if phase=="on":turn_on()
        elif phase=="off":turn_off()
        else:verify_origin()
        return 0
    except (HTTPError,URLError,TimeoutError,OSError,TypeError,ValueError,KeyError,IndexError,
            json.JSONDecodeError):
        print("SHOP_SQUARE_ORIGIN_PHASE="+phase.upper()+"_UNVERIFIED_OR_BLOCKED")
        print("SHOP_SQUARE_ORIGIN_SECRETS_OR_IDS_PRINTED=NO")
        return 2

if __name__=="__main__":
    sys.exit(main())
