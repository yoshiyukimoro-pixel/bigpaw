"""One-time isolated Railway preview credentials, initially DISABLED.

No Square payment, webhook activation, secret logging, email, or service deploy.
Never run against production, original Sandbox, or existing full app.
Unknown API outcomes must NOT be retried automatically.
"""
import json
import os
import secrets
import sys
from urllib.error import HTTPError,URLError
from urllib.request import Request,urlopen

RAILWAY="https://backboard.railway.com/graphql/v2"
PROJECT="91215e46-028b-4280-90f4-8d192c687164"
ENV="d0dacfcc-781b-4360-b539-461783ad47e2"
TARGET="ca40ca3c-d65a-4f51-99f3-b85ebfca164d"
REF="refs/heads/feature/dogfood-shop-staging-20261028"

def gql(token,query,variables,opener):
    req=Request(RAILWAY,data=json.dumps(
        {"query":query,"variables":variables},separators=(",",":")
    ).encode(),headers={
        "Project-Access-Token":token,
        "Content-Type":"application/json",
        "User-Agent":"BIGPAW-SandboxPreviewSetup/1.0",
    },method="POST")
    with opener(req,timeout=20) as resp:
        if resp.status!=200:raise ValueError("Unexpected Railway response")
        raw=resp.read(262145)
        if len(raw)>262144:raise ValueError("Railway response too large")
        obj=json.loads(raw)
    if not isinstance(obj,dict) or obj.get("errors"):
        raise ValueError("Railway GraphQL did not confirm")
    return obj.get("data")

def run(env=None,opener=urlopen):
    env=os.environ if env is None else env
    if (env.get("GITHUB_ACTIONS")!="true"
            or env.get("GITHUB_REF")!=REF
            or env.get("BIGPAW_SHOP_PREVIEW_CREDENTIAL_SETUP_OPT_IN")!="1"):
        return "scope_or_opt_in_missing",3
    token=env.get("BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN","").strip()
    if len(token)<16:return "railway_token_unavailable",2
    try:
        data=gql(token,"query{projectToken{projectId environmentId}}",{},opener)
        scope=data.get("projectToken") if isinstance(data,dict) else None
        if (not isinstance(scope,dict) or scope.get("projectId")!=PROJECT
                or scope.get("environmentId")!=ENV):
            return "railway_token_scope_mismatch",2
        data=gql(token,
            "query variables($projectId:String!,$environmentId:String!,$serviceId:String){"
            "variables(projectId:$projectId,environmentId:$environmentId,serviceId:$serviceId)}",
            {"projectId":PROJECT,"environmentId":ENV,"serviceId":TARGET},opener)
        current=data.get("variables") if isinstance(data,dict) else None
        if not isinstance(current,dict):return "cannot_confirm_target_variables",2
        if current.get("BIGPAW_SHOP_STAGE_PREVIEW_ENABLED")=="1":
            return "preview_already_enabled_refuse_overwrite",2
        if any(current.get(key) for key in (
            "BIGPAW_SHOP_STAGE_PREVIEW_USER",
            "BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD",
        )):
            return "preview_credentials_already_exist_no_overwrite",2
        if current.get("BIGPAW_ENV")!="sandbox":
            return "target_not_sandbox",2
    except HTTPError as exc:
        return "railway_read_http_"+str(exc.code),2
    except (URLError,OSError,TimeoutError,ValueError,TypeError):
        return "railway_read_unavailable",2

    username="bpstage_"+secrets.token_hex(4)
    password=secrets.token_urlsafe(48)
    newvars={
        "BIGPAW_SHOP_STAGE_PREVIEW_USER":username,
        "BIGPAW_SHOP_STAGE_PREVIEW_PASSWORD":password,
        "BIGPAW_SHOP_STAGE_PREVIEW_ENABLED":"0",
    }
    # One irreversible POST attempt, skip deployment. Never print new values.
    try:
        data=gql(token,
            "mutation($input:VariableCollectionUpsertInput!){variableCollectionUpsert(input:$input)}",
            {"input":{"projectId":PROJECT,"environmentId":ENV,"serviceId":TARGET,
                      "variables":newvars,"skipDeploys":True}},opener)
        if not isinstance(data,dict) or data.get("variableCollectionUpsert") is not True:
            return "staging_private_credentials_write_uncertain_no_retry",2
    except (HTTPError,URLError,OSError,TimeoutError,ValueError,TypeError):
        return "staging_private_credentials_write_uncertain_no_retry",2
    return "credentials_configured_preview_disabled_no_deployment",0

if __name__=="__main__":
    result,code=run()
    print("SHOP_ISOLATED_PREVIEW_SETUP="+result)
    print("SHOP_ISOLATED_PREVIEW_ENABLED=NO")
    print("SHOP_SQUARE_PAYMENT_CREATED=NO")
    print("SHOP_RAILWAY_DEPLOY_TRIGGERED=NO")
    sys.exit(code)
