"""Send exactly one Square-generated Sandbox test event to the NEW disabled webhook.

No payment/checkout/refund creation, subscription update, production endpoint, or
user data. No automatic retry. Never print token, subscription IDs, event
payload, notification keys, private responses or untrusted notification URLs.
Only runs in the opt-in GitHub Actions job for the dedicated test branch.
"""
import json
import os
import re
import sys
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

API = "https://connect.squareupsandbox.com/v2/webhooks/subscriptions"
NEW = "https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook"
OLD = "https://bigpaw-test-production.up.railway.app/api/shop/sandbox/webhook"
REF = "refs/heads/feature/dogfood-shop-staging-20261028"
ID = re.compile("[A-Za-z0-9_-]{8,96}")
HEADER = {"Square-Version": "2026-09-16", "Accept": "application/json",
          "User-Agent": "BIGPAW-Isolated-Square-Test/1.0"}

def get_json(url, token, opener):
    req = Request(url, method="GET", headers={**HEADER, "Authorization": "Bearer " + token})
    with opener(req, timeout=15) as response:
        if response.status != 200:
            raise ValueError("Non-200 GET")
        raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError("Oversize provider response")
        result = json.loads(raw)
        if not isinstance(result, dict):
            raise ValueError("Invalid provider data")
        return result

def execute(env=None, opener=urlopen):
    env = os.environ if env is None else env
    if (env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REF") != REF
            or env.get("BIGPAW_SQUARE_ONE_SHOT_DISABLED_TEST_OPT_IN") != "1"):
        return "opt_in_or_scope_missing", 3
    token = env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", "").strip()
    if len(token) < 12:
        return "sandbox_token_unavailable", 2
    try:
        subs = get_json(API + "?include_disabled=true&limit=100", token, opener)
        if subs.get("cursor"):
            return "subscription_list_not_complete_no_post", 2
        items = subs.get("subscriptions")
        if not isinstance(items, list):
            return "subscription_list_invalid_no_post", 2
        old = [s for s in items if isinstance(s,dict) and s.get("notification_url")==OLD]
        new = [s for s in items if isinstance(s,dict) and s.get("notification_url")==NEW]
        if (len(old)!=1 or old[0].get("enabled") is not True
                or "payment.updated" not in old[0].get("event_types", [])):
            return "existing_sandbox_subscription_unexpected_no_post", 2
        if (len(new)!=1 or new[0].get("enabled") is not False
                or "payment.updated" not in new[0].get("event_types", [])):
            return "new_disabled_subscription_unexpected_no_post", 2
        sid = new[0].get("id")
        if not isinstance(sid,str) or not ID.fullmatch(sid):
            return "isolated_subscription_id_invalid_no_post", 2
        detailed = get_json(API + "/" + sid,token,opener).get("subscription")
        if (not isinstance(detailed,dict) or detailed.get("id")!=sid
                or detailed.get("notification_url")!=NEW
                or detailed.get("enabled") is not False
                or "payment.updated" not in detailed.get("event_types", [])):
            return "isolated_subscription_detail_changed_no_post", 2
    except HTTPError as error:
        return "sandbox_subscription_get_http_"+str(error.code), 2
    except (URLError, OSError, TimeoutError, TypeError, ValueError, UnicodeError):
        return "sandbox_subscription_preflight_unavailable", 2

    # ONE POST. No retries; unknown outcome is never automatically replayed.
    request = Request(API + "/" + sid + "/test", method="POST",
        headers={**HEADER, "Authorization": "Bearer " + token,
                 "Content-Type": "application/json"},
        data=b'{"event_type":"payment.updated"}')
    try:
        with opener(request, timeout=25) as response:
            if response.status != 200:
                return "square_test_api_unexpected_http_"+str(response.status), 2
            raw=response.read(131073)
            if len(raw)>131072:
                return "square_test_api_response_oversize", 2
            result=json.loads(raw)
        test=result.get("subscription_test_result") if isinstance(result,dict) else None
        if not isinstance(test,dict):
            return "square_test_api_response_unrecognized", 2
        status=test.get("status_code")
        if type(status) is not int or not 100<=status<=599:
            return "square_test_api_no_receiver_status", 2
        # Square test events are synthetic and MUST NOT be a paid order.
        # Endpoint can reject them: 403=signature/environment rejected,
        # 503=unknown/unverified order, 2xx=ignored/accepted test.
        return "square_generated_test_delivered_receiver_http_"+str(status), 0
    except HTTPError as error:
        # HTTP 4xx on disabled subscription means Square refused the test.
        return "square_test_api_rejected_http_"+str(error.code), 2
    except (URLError,OSError,TimeoutError,TypeError,ValueError,UnicodeError):
        return "square_test_api_outcome_uncertain_do_not_retry", 2

if __name__=="__main__":
    result,code=execute()
    print("SHOP_SQUARE_ISOLATED_ONE_SHOT="+result)
    print("SHOP_SQUARE_TEST_TRANSACTION_CREATED=NO")
    print("SHOP_SQUARE_SUBSCRIPTION_ENABLE_OR_UPDATE=NO")
    print("SHOP_SQUARE_REAL_PAYMENT_E2E=NOT_TESTED")
    sys.exit(code)
