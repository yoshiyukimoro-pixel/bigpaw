"""Read-only authenticated stop-switch proof for the isolated staging app.

In-memory Basic Auth is obtained from the exact project-scoped Railway token,
never printed or persisted. No live Square, customer, email, checkout, or DB
mutation is performed. The requested checkout POST is rejected before its body.
"""
import base64
import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, build_opener, HTTPRedirectHandler

PROJECT="91215e46-028b-4280-90f4-8d192c687164"
ENV="d0dacfcc-781b-4360-b539-461783ad47e2"
APP="26c225af-d7d3-41b3-86e3-347d22146312"
HOST="https://bigpaw-app-staging-staging.up.railway.app"
API="https://backboard.railway.com/graphql/v2"
REF="refs/heads/feature/dogfood-shop-staging-20261028"

class BlockRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        return None

HTTP = build_opener(BlockRedirect())

def gql(query, variables, token):
    req=Request(API,method="POST",data=json.dumps({
        "query":query,"variables":variables,
    },separators=(",",":")).encode(),headers={
        "Project-Access-Token":token,
        "Content-Type":"application/json",
        "User-Agent":"BIGPAW-PrivateStopProbe/1.0",
    })
    with HTTP.open(req,timeout=20) as response:
        if response.status!=200:
            raise ValueError("Railway response not OK")
        raw=response.read(160000)
        if len(raw)>=160000:raise ValueError("Too large")
        obj=json.loads(raw)
    if not isinstance(obj,dict) or obj.get("errors"):
        raise ValueError("Railway query failed")
    return obj.get("data")

def request(path, credentials=None, method="GET"):
    assert path in ("/healthz","/shop.html","/api/shop/checkout/config","/api/shop/checkout")
    header={"User-Agent":"BIGPAW-PrivateStopProbe/1.0"}
    if credentials is not None:
        header["Authorization"]="Basic "+base64.b64encode(
            (credentials[0]+":"+credentials[1]).encode()).decode()
    body=b"{}" if method=="POST" else None
    if body is not None:header["Content-Type"]="application/json"
    req=Request(HOST+path,method=method,headers=header,data=body)
    try:
        with HTTP.open(req,timeout=18) as response:
            return response.status
    except HTTPError as error:
        return error.code

def run():
    if os.environ.get("GITHUB_REF")!=REF or os.environ.get("GITHUB_ACTIONS")!="true":
        print("SHOP_STAGING_STOP_PROOF=BLOCKED_SCOPE")
        return 3
    token=os.environ.get("BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN","")
    if len(token)<16:
        print("SHOP_STAGING_STOP_PROOF=MISSING_SCOPE_TOKEN")
        return 2
    try:
        data=gql("query{projectToken{projectId environmentId}}",{},token)
        scope=data.get("projectToken") if isinstance(data,dict) else None
        if (not isinstance(scope,dict) or scope.get("projectId")!=PROJECT
                or scope.get("environmentId")!=ENV):
            print("SHOP_STAGING_STOP_PROOF=WRONG_RAILWAY_PROJECT")
            return 2
        data=gql(
            "query variables($projectId:String!,$environmentId:String!,$serviceId:String){"
            "variables(projectId:$projectId,environmentId:$environmentId,serviceId:$serviceId)}",
            {"projectId":PROJECT,"environmentId":ENV,"serviceId":APP},token)
        variables=data.get("variables") if isinstance(data,dict) else None
        if not isinstance(variables,dict):
            print("SHOP_STAGING_STOP_PROOF=NO_STAGING_VARIABLE_VIEW")
            return 2
        if (variables.get("BIGPAW_SHOP_PUBLIC_LIVE_ENABLED")!="0"
                or variables.get("BIGPAW_ENV")!="staging"
                or variables.get("BIGPAW_SHOP_OWNER_LAUNCH_APPROVED")=="1"):
            print("SHOP_STAGING_STOP_PROOF=STOP_NOT_CONFIRMED")
            return 2
        user=variables.get("BIGPAW_STAGING_BASIC_USER")
        password=variables.get("BIGPAW_STAGING_BASIC_PASSWORD")
        if not isinstance(user,str) or not user or not isinstance(password,str) or len(password)<24:
            print("SHOP_STAGING_STOP_PROOF=STAGING_AUTH_UNAVAILABLE")
            return 2
        creds=(user,password)
        expected=[
            ("/healthz",None,"GET",200),
            ("/shop.html",None,"GET",401),
            ("/shop.html",creds,"GET",200),
            ("/api/shop/checkout/config",creds,"GET",404),
            ("/api/shop/checkout",creds,"POST",404),
        ]
        for path,auth,method,want in expected:
            status=request(path,auth,method)
            if status!=want:
                print("SHOP_STAGING_STOP_PROOF=HTTP_GATE_MISMATCH path="+path)
                return 2
        print("SHOP_STAGING_STOP_PROOF=PASS_PUBLIC_OFF_AUTHENTICATED_CHECKOUT_404")
        print("SHOP_STAGING_PAID_LINKS_CANCELLED=NO")
        print("SHOP_STAGING_SQUARE_PRODUCTION_TOUCHED=NO")
        return 0
    except (HTTPError,URLError,TimeoutError,OSError,ValueError,TypeError,KeyError,UnicodeError):
        print("SHOP_STAGING_STOP_PROOF=UNVERIFIED_NO_SECRET_OUTPUT")
        return 2

if __name__=="__main__":
    sys.exit(run())
