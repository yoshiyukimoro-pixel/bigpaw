"""Safe authenticated, quote-only HTTPS verification of NEW Square Sandbox preview.
No Checkout POST, Square charges, emails, customer data, or subscription mutation.
Gets isolated Basic Auth from exact scoped Railway Project Token in Actions memory.
"""
from __future__ import annotations
import base64
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import HTTPRedirectHandler, Request, build_opener

PROJ="91215e46-028b-4280-90f4-8d192c687164"
ENV="d0dacfcc-781b-4360-b539-461783ad47e2"
SERVICE="ca40ca3c-d65a-4f51-99f3-b85ebfca164d"
BASE="https://bigpaw-square-sandbox-staging-staging.up.railway.app"
RAILWAY="https://backboard.railway.com/graphql/v2"
REF="refs/heads/feature/dogfood-shop-staging-20261028"

class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        return None
CLIENT=build_opener(NoRedirect())

def gql(token,query,variables):
    data=json.dumps({"query":query,"variables":variables},separators=(",",":")).encode()
    req=Request(RAILWAY,method="POST",data=data,headers={
        "Project-Access-Token":token,"Content-Type":"application/json",
        "User-Agent":"BIGPAW-IsolatedPreviewQuote/1.0"})
    with CLIENT.open(req,timeout=18) as response:
        if response.status!=200:raise ValueError("Railway GET query unavailable")
        raw=response.read(262145)
        if len(raw)>262144:raise ValueError("Railway response too large")
        result=json.loads(raw)
    if not isinstance(result,dict) or result.get("errors"):
        raise ValueError("Railway query failed")
    return result.get("data")

def http(path,*,username=None,password=None,method="GET",body=None,csrf=None,cookie=None,origin=None):
    assert path in ("/shop.html","/api/shop/sandbox/config",
                    "/api/shop/sandbox/quote","/api/shop/sandbox/checkout")
    h={"User-Agent":"BIGPAW-IsolatedPreviewQuote/1.0"}
    if username is not None:
        h["Authorization"]="Basic "+base64.b64encode(
            (username+":"+password).encode()).decode("ascii")
    if body is not None:h["Content-Type"]="application/json"
    if csrf is not None:h["X-Shop-CSRF"]=csrf
    if cookie is not None:h["Cookie"]=cookie
    if origin is not None:h["Origin"]=origin
    req=Request(BASE+path,method=method,headers=h,data=body)
    try:
        with CLIENT.open(req,timeout=20) as resp:
            return resp.status,dict(resp.getheaders()),resp.read(16385)
    except HTTPError as e:
        return e.code,{},b""

def main():
    if (os.environ.get("GITHUB_ACTIONS")!="true"
            or os.environ.get("GITHUB_REF")!=REF
            or os.environ.get("BIGPAW_SANDBOX_PREVIEW_QUOTE_OPT_IN")!="1"):
        print("SHOP_STAGING_PREVIEW_QUOTE=BLOCKED_SCOPE")
        return 3
    token=os.environ.get("BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN","")
    if len(token)<16:
        print("SHOP_STAGING_PREVIEW_QUOTE=MISSING_SCOPED_TOKEN")
        return 2
    try:
        scope=gql(token,"query{projectToken{projectId environmentId}}",{}).get("projectToken")
        if not isinstance(scope,dict) or scope.get("projectId")!=PROJ or scope.get("environmentId")!=ENV:
            return _fail("WRONG_PROJECT")
        data=gql(token,
            "query variables($projectId:String!,$environmentId:String!,$serviceId:String){"
            "variables(projectId:$projectId,environmentId:$environmentId,serviceId:$serviceId)}",
            {"projectId":PROJ,"environmentId":ENV,"serviceId":SERVICE})
        var=data.get("variables") if isinstance(data,dict) else None
        if not isinstance(var,dict) or any(var.get(k)!=v for k,v in {
                "BIGPAW_ENV":"sandbox","BIGPAW_SHOP_STAGE_PREVIEW_ENABLED":"1",
                "BIGPAW_SHOP_STAGING_ISOLATED":"1",
                "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED":"0",
            }.items()):
            return _fail("NOT_PRIVATE_ENABLED_SANDBOX")
        username=var.get("BIGPAW_SHOP_STAGE_PREVIEW_USER")
        password=var.get("BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD")
        if not isinstance(username,str) or not username or not isinstance(password,str) or len(password)<32:
            return _fail("CREDENTIALS_NOT_READY")
        unauth,_,_=http("/shop.html")
        if unauth!=401:return _fail("UNAUTHENTICATED_ACCESS_NOT_REJECTED")
        status,_,html=http("/shop.html",username=username,password=password)
        if status!=200 or not html:return _fail("AUTHENTICATED_PREVIEW_UNAVAILABLE")
        status,headers,raw=http("/api/shop/sandbox/config",username=username,password=password)
        if status!=200:return _fail("CONFIG_UNAVAILABLE")
        config=json.loads(raw)
        if config.get("ready") is not True or config.get("sandbox") is not True:
            return _fail("NOT_SANDBOX_CONFIG")
        csrf=config.get("csrf_token")
        cookies=headers.get("Set-Cookie","")
        if not isinstance(csrf,str) or len(csrf)<32 or not cookies.startswith("bigpaw_shop_sandbox_csrf="):
            return _fail("CSRF_NOT_ISSUED")
        cookie=cookies.split(";",1)[0]
        quote=b'{"cart":{"A02":1}}'
        status,_,raw=http("/api/shop/sandbox/quote",username=username,password=password,
            method="POST",body=quote,csrf=csrf,cookie=cookie,origin=BASE)
        if status!=200:return _fail("QUOTE_FAILED")
        obj=json.loads(raw)
        if (obj.get("amount_yen")!=21450 or obj.get("shipping_yen")!=0
                or obj.get("verified") is not True or obj.get("real_payments") is not False):
            return _fail("QUOTE_MISMATCH")
        # Tampered price or missing CSRF must be refused BEFORE Square request.
        status,_,_=http("/api/shop/sandbox/quote",username=username,password=password,
            method="POST",body=b'{"cart":{"A02":1},"amount_yen":1}',
            csrf=csrf,cookie=cookie,origin=BASE)
        if status!=400:return _fail("PRICE_TAMPER_ACCEPTED")
        status,_,_=http("/api/shop/sandbox/checkout",username=username,password=password,
            method="POST",body=b'{"cart":{"A02":1}}',origin=BASE)
        if status!=403:return _fail("CHECKOUT_CSRF_NOT_GUARDED")
        print("SHOP_STAGING_PREVIEW_QUOTE=PASS_PRIVATE_JPY_21450_NO_CHECKOUT")
        print("SHOP_STAGING_PREVIEW_PAYMENT_LINK_CREATED=NO")
        return 0
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,KeyError,UnicodeError,AssertionError):
        return _fail("EXTERNAL_VERIFICATION_UNAVAILABLE")

def _fail(code):
    print("SHOP_STAGING_PREVIEW_QUOTE="+code)
    return 2

if __name__=="__main__":
    sys.exit(main())
