"""Read-only Square Sandbox webhook subscriptions audit. Never logs private URLs or IDs."""
import json, os, re, sys
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API="https://connect.squareupsandbox.com/v2/webhooks/subscriptions"
LEGACY="https://bigpaw-test-production.up.railway.app/api/shop/sandbox/webhook"
NEW="https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook"
REF="refs/heads/feature/dogfood-shop-staging-20261028"

def audit(env=None, opener=urlopen):
    env = os.environ if env is None else env
    if env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_REF")!=REF:
        return "wrong_execution_scope",3
    token=env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","")
    if not isinstance(token,str) or len(token.strip())<12:
        return "missing_sandbox_application_token",2
    rows=[]
    cursor=None
    seen=set()
    for index in range(5):
        query={"limit":100,"include_disabled":"true"}
        if cursor is not None:
            if (not isinstance(cursor,str)
                or not re.fullmatch(r"[A-Za-z0-9_-]{1,512}",cursor)
                or cursor in seen):
                return "invalid_pagination",2
            seen.add(cursor)
            query["cursor"]=cursor
        req=Request(API+"?"+urlencode(query),headers={
            "Authorization":"Bearer "+token.strip(),
            "Square-Version":"2026-09-16",
            "Accept":"application/json",
        },method="GET")
        try:
            with opener(req,timeout=12) as response:
                if response.status!=200:return "provider_status_not_verified",2
                data=json.loads(response.read(131073))
        except HTTPError as e:
            return ("provider_token_lacks_subscription_permission",2) if e.code in (401,403) else ("provider_http_unavailable",2)
        except (URLError,OSError,TimeoutError,ValueError,TypeError):
            return "provider_network_or_format_unavailable",2
        if not isinstance(data,dict) or not isinstance(data.get("subscriptions",[]),list):
            return "invalid_provider_response",2
        rows.extend(data.get("subscriptions",[]))
        cursor=data.get("cursor")
        if not cursor:break
    else:
        return "pagination_incomplete",2

    def state(url):
        matches=[x for x in rows if isinstance(x,dict) and x.get("notification_url")==url]
        if len(matches)>1:return "duplicate"
        if not matches:return "none"
        item=matches[0]
        return ("enabled" if item.get("enabled") is True else "disabled") + (
            "_payment_updated" if "payment.updated" in item.get("event_types",[]) else "_missing_event")
    return "old_"+state(LEGACY)+"__new_"+state(NEW)+"__read_only",0

if __name__=="__main__":
    result,status=audit()
    print("SHOP_SQUARE_SANDBOX_SUBSCRIPTIONS="+result)
    print("SHOP_SQUARE_WEBHOOK_MUTATIONS=ZERO")
    sys.exit(status)
