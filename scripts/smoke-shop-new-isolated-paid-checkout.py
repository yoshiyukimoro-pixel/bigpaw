"""One approved Square Sandbox Hosted Test Payment against NEW isolated DB.

Authorized only on staged feature branch, with exact scoped Railway project
token, NEW Sandbox webhook service, and real Square Sandbox secrets.
Uses one ephemeral unique order; no production payment, user card, mail,
supplier message, shipping, or public site mutation.

Square's hosted Sandbox Testing Panel runs separately between 'prepare' and
'verify'. The event posted here is synthetic but HMAC-signed using the actual
NEW Square subscriber key. It is NOT a Square-originated delivery.
No retry of payment-link POST or signed webhook POST after uncertainty.
No PII, URLs, tokens, IDs, or payment details printed.
"""
from __future__ import annotations
import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import re
import sys
import uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

PROJECT="91215e46-028b-4280-90f4-8d192c687164"
ENV="d0dacfcc-781b-4360-b539-461783ad47e2"
SERVICE="ca40ca3c-d65a-4f51-99f3-b85ebfca164d"
REF="refs/heads/feature/dogfood-shop-staging-20261028"
BASE="https://bigpaw-square-sandbox-staging-staging.up.railway.app"
WEBHOOK=BASE+"/api/shop/sandbox/webhook"
RAILWAY="https://backboard.railway.com/graphql/v2"
SQUARE="https://connect.squareupsandbox.com/v2"
PRICE=21450
TEST_PRODUCT="A02"

def _safe_error(error):
    # Never print provider errors, which may contain order URLs/PII.
    if isinstance(error,HTTPError):
        return "HTTP_ERROR_"+str(error.code)
    return "NETWORK_OR_PROVIDER_UNVERIFIED"

def _scope(secrets_map):
    if os.environ.get("GITHUB_ACTIONS")!="true" or os.environ.get("GITHUB_REF")!=REF:
        raise ValueError("Wrong environment")
    if os.environ.get("BIGPAW_ISOLATED_REAL_SANDBOX_PAYMENT_OPT_IN")!="1":
        raise ValueError("No explicit single test opt-in")
    token=os.environ.get("BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN","")
    if len(token)<16:raise ValueError("Scoped Railway token missing")
    query={"query":"query{projectToken{projectId environmentId}}"}
    response=_railway_request(query,token)
    if response.get("projectToken")!={"projectId":PROJECT,"environmentId":ENV}:
        raise ValueError("Wrong Railway project")
    data=_railway_request({
        "query":"query variables($projectId:String!,$environmentId:String!,$serviceId:String){variables(projectId:$projectId,environmentId:$environmentId,serviceId:$serviceId)}",
        "variables":{"projectId":PROJECT,"environmentId":ENV,"serviceId":SERVICE},
    },token)
    d=data.get("variables")
    if not isinstance(d,dict):
        raise ValueError("New Railway secret collection unavailable")
    required={
        "BIGPAW_ENV":"sandbox",
        "BIGPAW_SHOP_STAGING_ISOLATED":"1",
        "BIGPAW_SHOP_STAGE_PREVIEW_ENABLED":"1",
        "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID":PROJECT,
        "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL":WEBHOOK,
    }
    if any(d.get(k)!=v for k,v in required.items()):
        raise ValueError("New test-only service not correctly isolated/enabled")
    for key in (
        "BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED",
        "BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED",
        "BIGPAW_SHOP_SANDBOX_PAID_MAIL_ONCE_ENABLED",
    ):
        if d.get(key)=="1":
            raise ValueError("Real mail not permitted on isolated test")
    if d.get("BIGPAW_SHOP_STAGE_PREVIEW_USER") is None:
        raise ValueError("Private preview credentials missing")
    user=d.get("BIGPAW_SHOP_STAGE_PREVIEW_USER")
    password=d.get("BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD")
    sigkey=d.get("BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY")
    if not (isinstance(user,str) and re.fullmatch(r"[A-Za-z0-9_-]{4,32}",user)
            and isinstance(password,str) and len(password)>=32
            and isinstance(sigkey,str) and len(sigkey)>=16):
        raise ValueError("Sandbox staging credentials not valid")
    square_token=os.environ.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","")
    location=os.environ.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID","")
    if len(square_token)<16 or not re.fullmatch(r"[A-Za-z0-9_-]{8,80}",location):
        raise ValueError("Square Sandbox-only credentials required")
    if square_token!=d.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"):
        raise ValueError("Railway checkout token differs from Square job token")
    if location!=d.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID"):
        raise ValueError("Railway Square location differs from job location")
    return {"user":user,"password":password,"sigkey":sigkey,
            "square_token":square_token,"location":location}

def _railway_request(body,token):
    req=Request(RAILWAY,data=json.dumps(body,separators=(",",":")).encode(),
                method="POST",headers={
                   "Project-Access-Token":token,
                   "Content-Type":"application/json",
                   "User-Agent":"BIGPAW-StagingRealSandboxPayment/1.0",
                })
    with urlopen(req,timeout=18) as r:
        if r.status!=200:raise ValueError("Railway API error")
        raw=r.read(262145)
        if len(raw)>262144:raise ValueError("Railway response oversized")
        payload=json.loads(raw)
    if not isinstance(payload,dict) or payload.get("errors"):
        raise ValueError("Railway query not fulfilled")
    return payload.get("data",{})

def _http(path,auth=None,*,method="GET",body=None,extra=None,accept_status=None):
    if not path.startswith("/") or "?" in path or "#" in path:
        raise ValueError("Noncanonical staging path")
    headers={"User-Agent":"BIGPAW-StagingRealSandboxPayment/1.0",
             **(extra or {})}
    if auth is not None:
        headers["Authorization"]="Basic "+base64.b64encode(
            (auth["user"]+":"+auth["password"]).encode()).decode()
    if body is not None: headers["Content-Type"]="application/json"
    req=Request(BASE+path,method=method,headers=headers,data=body)
    try:
        with urlopen(req,timeout=28) as resp:
            code=resp.status
            head=dict(resp.getheaders())
            raw=resp.read(262145)
    except HTTPError as exc:
        code=exc.code
        head={}
        raw=exc.read(262145)
    if len(raw)>262144:raise ValueError("Staging HTTP response oversized")
    if accept_status is not None and code!=accept_status:
        raise ValueError("Wrong staging response status")
    return code,head,raw

def _square_get(url,token):
    if not url.startswith(SQUARE+"/"):raise ValueError("Non Sandbox Square URL")
    req=Request(url,headers={
        "Authorization":"Bearer "+token,
        "Square-Version":"2026-09-16",
        "Accept":"application/json",
        "User-Agent":"BIGPAW-StagingRealSandboxPayment/1.0",
    },method="GET")
    with urlopen(req,timeout=18) as response:
        if response.status!=200:raise ValueError("Sandbox GET failed")
        raw=response.read(262145)
        if len(raw)>262144:raise ValueError("Square response oversized")
        data=json.loads(raw)
    if not isinstance(data,dict):raise ValueError("Bad Square JSON")
    return data

def _file():
    tmp=os.environ.get("RUNNER_TEMP","")
    if not tmp or not Path(tmp).is_dir():
        raise ValueError("Must use ephemeral GitHub runner")
    return Path(tmp)/"bigpaw-new-stage-checkout.json"

def prepare():
    conf=_scope(None)
    # Existing Square Sandbox subscription is not mutated. It is active;
    # Square may send the synthetic payment notice there as normal.
    _,_,_= _http("/shop.html",auth=conf,accept_status=200)
    _,h,b=_http("/api/shop/sandbox/config",auth=conf,accept_status=200)
    config=json.loads(b)
    if config.get("ready") is not True or config.get("sandbox") is not True:
        raise ValueError("Sandbox checkout disabled")
    token=config.get("csrf_token")
    cookie=h.get("Set-Cookie","").split(";",1)[0]
    if not isinstance(token,str) or len(token)<32 or not cookie.startswith("bigpaw_shop_sandbox_csrf="):
        raise ValueError("CSRF cookie not issued")
    order=uuid.uuid4()
    attempt=str(order)
    local="FOOD"+attempt.replace("-","")
    body=json.dumps({"attempt_id":attempt,"cart":{TEST_PRODUCT:1}}).encode()
    _,_,raw=_http("/api/shop/sandbox/checkout",auth=conf,
        method="POST",body=body,accept_status=200,extra={
            "Origin":BASE,
            "X-Shop-CSRF":token,
            "Cookie":cookie,
        })
    obj=json.loads(raw)
    url=obj.get("checkout_url","")
    if (obj.get("order_id")!=local or obj.get("amount_yen")!=PRICE
            or obj.get("shipping_yen")!=0 or not isinstance(url,str)
            or not url.startswith("https://sandbox.square.link/u/")
            or "/" in url[len("https://sandbox.square.link/u/"):]):
        raise ValueError("Real Sandbox payment link invalid; DO NOT RETRY")
    status,_,value=_http("/api/shop/sandbox/order/"+local,
        auth=conf,accept_status=200)
    if json.loads(value).get("order_status")!="payment_pending":
        raise ValueError("NEW staging ledger not payment_pending")
    state={"link_url":url,"shop_order_id":local,
           "amount_yen":PRICE,"shipping_yen":0,
           "created_in":"new_isolated_railway_staging"}
    target=_file()
    if target.exists():raise ValueError("Never overwrite test state")
    with target.open("x",encoding="utf-8") as f:
        json.dump(state,f,separators=(",",":"))
    target.chmod(0o600)
    print("SHOP_ISOLATED_REAL_SANDBOX_CHECKOUT=ONE_LINK_CREATED_NEW_DURABLE_DB")
    print("SHOP_ISOLATED_REAL_SANDBOX_PAID=NOT_YET")
    print("SHOP_ISOLATED_REAL_SANDBOX_PRODUCTION_CHARGE=NO")

def verify():
    conf=_scope(None)
    state=json.loads(_file().read_text())
    url=state.get("link_url")
    local=state.get("shop_order_id")
    if (not isinstance(url,str) or not url.startswith("https://sandbox.square.link/u/")
            or not isinstance(local,str) or not re.fullmatch(r"FOOD[0-9a-f]{32}",local)
            or state.get("amount_yen")!=PRICE):
        raise ValueError("Test order state changed")
    # The authenticated preview's pending ledger is checked BEFORE we hint
    # any payment. No Square payment can be accepted on event text alone.
    _,_,raw=_http("/api/shop/sandbox/order/"+local,auth=conf,accept_status=200)
    if json.loads(raw).get("order_status")!="payment_pending":
        raise ValueError("Remote durable order not pending")
    # Caller is permitted to read only the unique sandbox checkout created in
    # this job. Fetch the correct order ID through the bound CheckoutLink API.
    # Read-only paginated lookup: old test runs may have produced >100 links.
    # Refuse partial listing or missing/ambiguous matches; never POST another.
    cursor=None
    matches=[]
    seen=set()
    for _ in range(20):
        from urllib.parse import urlencode
        query={"limit":100}
        if cursor:
            query["cursor"]=cursor
        links=_square_get(SQUARE+"/online-checkout/payment-links?"+urlencode(query),
                          conf["square_token"])
        items=links.get("payment_links",[])
        if not isinstance(items,list):
            raise ValueError("Square link listing invalid")
        matches.extend(item for item in items
                       if isinstance(item,dict) and item.get("url")==url)
        cursor=links.get("cursor")
        if not cursor:
            break
        if not isinstance(cursor,str) or cursor in seen:
            raise ValueError("Square link pagination invalid")
        seen.add(cursor)
    else:
        raise ValueError("Square link pagination incomplete")
    if len(matches)!=1:
        raise ValueError("Exactly one Square link not found; safe stop")
    link=matches[0]
    square_order=link.get("order_id")
    if not isinstance(square_order,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,192}",square_order):
        raise ValueError("Bound Square order missing")
    od=_square_get(SQUARE+"/orders/"+square_order,conf["square_token"]).get("order")
    if not isinstance(od,dict) or od.get("id")!=square_order:
        raise ValueError("Square order not verified")
    tenders=od.get("tenders")
    if not isinstance(tenders,list) or len(tenders)!=1:
        raise ValueError("One paid tender not found in Square order")
    pid=tenders[0].get("id")
    if not isinstance(pid,str) or not re.fullmatch(r"[A-Za-z0-9_-]{8,192}",pid):
        raise ValueError("Square tender missing payment reference")
    payment=_square_get(SQUARE+"/payments/"+pid,conf["square_token"]).get("payment")
    if not isinstance(payment,dict):
        raise ValueError("Square Payment missing")
    m=payment.get("amount_money")
    refund=payment.get("refunded_money")
    if (payment.get("id")!=pid or payment.get("order_id")!=square_order
            or payment.get("status")!="COMPLETED"
            or payment.get("location_id")!=conf["location"]
            or not isinstance(m,dict) or type(m.get("amount")) is not int
            or m.get("amount")!=PRICE or m.get("currency")!="JPY"
            or (refund is not None and
                (not isinstance(refund,dict) or refund.get("amount")!=0
                 or refund.get("currency")!="JPY"))):
        raise ValueError("Square paid money/order/location mismatch")
    print("SHOP_ISOLATED_REAL_SANDBOX_PROVIDER_PAID=VERIFIED_JPY_21450")
    event={"event_id":"isostage-"+uuid.uuid4().hex,
           "type":"payment.updated","data":{"object":{"payment":payment}}}
    body=json.dumps(event,separators=(",",":")).encode()
    digest=base64.b64encode(hmac.new(conf["sigkey"].encode(),
        WEBHOOK.encode()+body,hashlib.sha256).digest()).decode()
    status,_,raw=_http("/api/shop/sandbox/webhook",method="POST",
        body=body,accept_status=200,extra={
           "Square-Environment":"Sandbox",
           "X-Square-Hmacsha256-Signature":digest,
        })
    if json.loads(raw).get("status")!="received":
        raise ValueError("Webhook did not acknowledge")
    _,_,s=_http("/api/shop/sandbox/order/"+local,auth=conf,accept_status=200)
    if json.loads(s).get("order_status")!="paid":
        raise ValueError("Fresh Square payment not reflected in durable new DB")
    print("SHOP_ISOLATED_REAL_SANDBOX_DURABLE_PAID=VERIFIED")
    # Repeat exact same validated event once to establish idempotency, never
    # repeat the Square payment or link creation.
    status,_,raw=_http("/api/shop/sandbox/webhook",method="POST",
        body=body,accept_status=200,extra={
           "Square-Environment":"Sandbox",
           "X-Square-Hmacsha256-Signature":digest,
        })
    if json.loads(raw).get("status")!="received":
        raise ValueError("Duplicate webhook not idempotent")
    print("SHOP_ISOLATED_REAL_SANDBOX_DUPLICATE_EVENT=IDEMPOTENT")
    print("SHOP_ISOLATED_REAL_SANDBOX_SQUARE_DELIVERED_WEBHOOK=NO_SYNTHETIC_HMAC_INJECTION")
    print("SHOP_ISOLATED_REAL_SANDBOX_SHIPPING=NOT_VERIFIED")
    print("SHOP_ISOLATED_REAL_SANDBOX_PRODUCTION_CHARGE=NO")

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["prepare","verify"])
    args=parser.parse_args()
    try:
        if args.phase=="prepare":prepare()
        else:verify()
        return 0
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,
            TypeError,KeyError,IndexError,json.JSONDecodeError) as exc:
        print("SHOP_ISOLATED_REAL_SANDBOX_"+args.phase.upper()+"=BLOCKED_"+_safe_error(exc))
        print("SHOP_ISOLATED_REAL_SANDBOX_RETRY=NOT_ATTEMPTED")
        return 2

if __name__=="__main__":sys.exit(main())
