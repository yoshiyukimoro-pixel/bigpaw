"""Square Sandbox -> Railway staging ONLY: opt-in secret transfer, no logs, no deploy.

Uses a Railway project-scoped token in GitHub Actions Secrets. Validates exact
project/environment via projectToken GraphQL first. Reads the DISABLED Square
Sandbox subscription's signature key and upserts only three variables into
the isolated new webhook service; no Square mutation. Never prints secrets,
responses, subscription IDs, URLs other than fixed public API domains, or PII.
"""
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

PROJECT = "91215e46-028b-4280-90f4-8d192c687164"
ENVIRONMENT = "d0dacfcc-781b-4360-b539-461783ad47e2"
SERVICE = "ca40ca3c-d65a-4f51-99f3-b85ebfca164d"
WEBHOOK = "https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook"
SQUARE = "https://connect.squareupsandbox.com/v2/webhooks/subscriptions"
RAILWAY = "https://backboard.railway.com/graphql/v2"
REF = "refs/heads/feature/dogfood-shop-staging-20261028"
IDENTITY = re.compile(r"[A-Za-z0-9_-]{8,96}\Z")


def read_json(url, *, headers, body=None, opener=urlopen):
    req = Request(url, method="POST" if body is not None else "GET",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"User-Agent":"BIGPAW-Shop-StagingSync/1.0", "Accept":"application/json",
                 **headers, **({"Content-Type":"application/json"} if body is not None else {})})
    with opener(req, timeout=12) as response:
        if response.status not in ((200,201) if body is not None else (200,)):
            raise ValueError("Unexpected upstream status")
        raw=response.read(131073)
        if len(raw)>131072: raise ValueError("Response too large")
        obj=json.loads(raw)
        if not isinstance(obj,dict): raise ValueError("Invalid upstream payload")
        return obj


def sync(env=None, opener=urlopen):
    env=os.environ if env is None else env
    if (env.get("GITHUB_ACTIONS")!="true" or env.get("GITHUB_REF")!=REF
            or env.get("BIGPAW_SHOP_STAGING_SECRET_SYNC_OPT_IN")!="1"):
        return "scope_or_opt_in_blocked",3
    square=env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","").strip()
    location=env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID","").strip()
    railway=env.get("BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN","").strip()
    if (len(square)<12 or len(railway)<20 or not IDENTITY.fullmatch(location)):
        return "scoped_credentials_not_configured",2
    headers={"Project-Access-Token":railway}
    try:
        info=read_json(RAILWAY,headers=headers,
            body={"query":"query { projectToken { projectId environmentId } }"},
            opener=opener)
        t=(info.get("data") or {}).get("projectToken")
        if (not isinstance(t,dict) or t.get("projectId")!=PROJECT
                or t.get("environmentId")!=ENVIRONMENT):
            return "railway_project_token_wrong_scope",2
    except HTTPError as exc:
        # Report only the HTTP category. Never print the response, headers,
        # the supplied token, Railway account data, or secret material.
        if exc.code in (401, 403):
            return "railway_project_token_auth_rejected_http_" + str(exc.code),2
        if exc.code in (400, 422):
            return "railway_project_token_query_rejected_http_" + str(exc.code),2
        return "railway_project_token_http_failure",2
    except (URLError, OSError, TimeoutError):
        return "railway_project_token_network_failure",2
    except (TypeError, ValueError):
        return "railway_project_token_invalid_response",2
    sqheaders={"Authorization":"Bearer "+square,"Square-Version":"2026-09-16",
               "Accept":"application/json"}
    try:
        data=read_json(SQUARE+"?include_disabled=true&limit=100",
                       headers=sqheaders,opener=opener)
        if data.get("cursor"):return "square_subscription_list_incomplete",2
        subs=data.get("subscriptions")
        if not isinstance(subs,list):return "square_list_invalid",2
        matches=[x for x in subs if isinstance(x,dict)
                 and x.get("notification_url")==WEBHOOK]
        if len(matches)!=1:return "square_subscription_missing_or_duplicate",2
        sub=matches[0]
        sid=sub.get("id")
        if (not isinstance(sid,str) or not IDENTITY.fullmatch(sid)
                or sub.get("enabled") is not False):
            return "square_target_not_disabled",2
        fetched=read_json(SQUARE+"/"+sid,headers=sqheaders,opener=opener)
        detail=fetched.get("subscription")
        if (not isinstance(detail,dict) or detail.get("id")!=sid
                or detail.get("notification_url")!=WEBHOOK
                or detail.get("enabled") is not False
                or "payment.updated" not in detail.get("event_types",[])):
            return "square_subscription_details_invalid",2
        key=detail.get("signature_key")
        if not isinstance(key,str) or not 16<=len(key)<=1024:
            return "square_subscription_key_unavailable",2
    except (HTTPError,URLError,OSError,TimeoutError,TypeError,ValueError):
        return "square_subscription_read_failed",2
    # One mutation only; no automatic retry after a timeout. Never replace all
    # variables and NEVER deploy automatically (branch HEAD may have changed).
    values={"BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":square,
            "BIGPAW_SQUARE_SANDBOX_LOCATION_ID":location,
            "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY":key}
    try:
        upsert=read_json(RAILWAY,headers=headers,body={
            "query":"mutation($input:VariableCollectionUpsertInput!){variableCollectionUpsert(input:$input)}",
            "variables":{"input":{"projectId":PROJECT,"environmentId":ENVIRONMENT,
                       "serviceId":SERVICE,"variables":values,"skipDeploys":True}}},
            opener=opener)
        if upsert.get("errors") or (upsert.get("data") or {}).get("variableCollectionUpsert") is not True:
            return "staging_secret_write_uncertain_no_retry",2
    except (HTTPError,URLError,OSError,TimeoutError,TypeError,ValueError):
        return "staging_secret_write_uncertain_no_retry",2
    return "only_new_webhook_secrets_configured_no_deploy",0


if __name__=="__main__":
    result,exitcode=sync()
    print("SHOP_STAGING_SANDBOX_SECRET_SYNC="+result)
    print("SHOP_STAGING_SQUARE_SUBSCRIPTION_ENABLED=NO")
    print("SHOP_STAGING_RAILWAY_DEPLOY_TRIGGERED=NO")
    sys.exit(exitcode)
