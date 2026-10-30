"""ONE-TIME opt-in: register a DISABLED Square Sandbox webhook subscription.
No live Square API calls, email, charge, refund, existing subscription changes,
secret logs or automatic POST retries. Result key is NEVER printed/stored.
"""
import json, os, re, sys, uuid
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API="https://connect.squareupsandbox.com/v2/webhooks/subscriptions"
TARGET="https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook"
REF="refs/heads/feature/dogfood-shop-staging-20261028"
KEY=str(uuid.uuid5(uuid.NAMESPACE_URL,"bigpaw-shop-sandbox-disabled-subscription-20261031:"+TARGET))
HEADER_VERSION="2026-09-16"


def _call(url,token,*,payload=None,opener=urlopen):
    headers={"Authorization":"Bearer "+token,"Square-Version":HEADER_VERSION,
             "Accept":"application/json"}
    if payload is not None:headers["Content-Type"]="application/json"
    req=Request(url,headers=headers,
                data=(json.dumps(payload,separators=(",",":")).encode() if payload is not None else None),
                method=("POST" if payload is not None else "GET"))
    with opener(req,timeout=12) as res:
        if res.status not in ((200,201) if payload is not None else (200,)):
            raise ValueError("Unexpected Square status")
        raw=res.read(131073)
        if len(raw)>131072:raise ValueError("Oversized response")
        data=json.loads(raw)
        if not isinstance(data,dict):raise ValueError("Invalid response")
        return data


def register_disabled(*,env=None,opener=urlopen):
    env=os.environ if env is None else env
    if (env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_REF")!=REF
            or env.get("BIGPAW_SHOP_REGISTER_DISABLED_WEBHOOK")!="1"):
        return "blocked_scope_or_owner_opt_in_missing",3
    token=env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","")
    if not isinstance(token,str) or len(token.strip())<12:
        return "sandbox_token_unavailable",2
    try:
        before=_call(API+"?include_disabled=true&limit=100",token.strip(),opener=opener)
        rows=before.get("subscriptions",[])
        if not isinstance(rows,list):return "invalid_subscription_list",2
        if before.get("cursor"):
            # No creation when the list is not exhaustive.
            return "subscriptions_paginated_manual_review",2
        matches=[v for v in rows if isinstance(v,dict) and v.get("notification_url")==TARGET]
        if len(matches)>1:return "duplicate_new_target_manual_review",2
        if matches:
            if matches[0].get("enabled") is False:
                return "new_target_already_registered_disabled",0
            return "new_target_exists_enabled_manual_review",2
    except HTTPError as exc:
        return ("square_subscription_permission_unavailable" if exc.code in (401,403)
                else "sandbox_preflight_http_failed"),2
    except (URLError,OSError,TimeoutError,ValueError,TypeError):
        return "sandbox_subscription_preflight_unverified",2

    # Exactly one external mutation, allowed only when preflight saw no target.
    payload={
        "idempotency_key":KEY,
        "subscription":{
            "name":"BIG PAW Shop Isolated Staging (Disabled)",
            "enabled":False,
            "event_types":["payment.created","payment.updated"],
            "notification_url":TARGET,
            "api_version":HEADER_VERSION,
        }
    }
    try:
        created=_call(API,token.strip(),payload=payload,opener=opener)
    except (HTTPError,URLError,OSError,TimeoutError,ValueError,TypeError):
        # POST might have succeeded! Never retry. GET subscriptions to inspect.
        return "subscription_post_uncertain_no_retry_manual_get",2
    data=created.get("subscription",{})
    if (not isinstance(data,dict) or data.get("notification_url")!=TARGET
            or data.get("enabled") is not False
            or "payment.updated" not in data.get("event_types",[])):
        return "created_subscription_state_unverified_manual_review",2
    # Square's response may contain a signature_key; absolutely never print it.
    return "new_target_created_disabled_no_delivery",0


if __name__=="__main__":
    status,code=register_disabled()
    print("SHOP_SQUARE_DISABLED_SUBSCRIPTION="+status)
    print("SQUARE_PRODUCTION_MUTATIONS=ZERO")
    print("SQUARE_EXISTING_SUBSCRIPTION_CHANGES=ZERO")
    sys.exit(code)
