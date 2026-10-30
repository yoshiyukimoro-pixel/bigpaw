"""READ-ONLY audit of uncertain 2026-10-30 Square Sandbox fake refund.

One-shot GET /v2/refunds; never POST or retry a refund. Prints only a
non-identifying count and status; no Square IDs, names, addresses or tokens.
"""
from __future__ import annotations
from datetime import datetime, timezone
import json
import os
import sys
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError

BASE = "https://connect.squareupsandbox.com/v2/refunds"
START = "2026-10-30T21:24:00Z"
END = "2026-10-30T21:27:00Z"
REASON = "BIGPAW SANDBOX TEST ONLY"
REF = "refs/heads/feature/dogfood-shop-staging-20261028"


def audit(*, env=None, opener=urlopen):
    env = os.environ if env is None else env
    if env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REF") != REF:
        return "blocked_not_isolated_runner", 3
    token = env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", "")
    location = env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID", "")
    if not token or not location:
        return "sandbox_read_credentials_missing", 2

    cursor = None
    matches = []
    for _ in range(5):
        query = {"begin_time":START,"end_time":END,
                 "location_id":location,"limit":100}
        if cursor:
            query["cursor"] = cursor
        req = Request(BASE + "?" + urlencode(query), method="GET",
                      headers={"Authorization":"Bearer " + token,
                               "Square-Version":"2026-09-16",
                               "Accept":"application/json",
                               "User-Agent":"BIGPAW-Refund-Audit-GET-only/1.0"})
        try:
            with opener(req, timeout=12) as resp:
                if resp.status != 200:
                    return "sandbox_refund_listing_unavailable", 2
                raw=resp.read(262145)
                if len(raw) > 262144:
                    return "sandbox_refund_response_too_large", 2
                data=json.loads(raw)
        except HTTPError as e:
            if e.code in (401,403):
                return "sandbox_refund_read_permission_unavailable", 2
            return "sandbox_refund_provider_unavailable", 2
        except (URLError, OSError, TimeoutError, ValueError, TypeError):
            return "sandbox_refund_audit_network_unverified", 2
        if not isinstance(data,dict):
            return "sandbox_refund_response_invalid", 2
        for item in data.get("refunds") or []:
            if (isinstance(item,dict)
                    and item.get("reason")==REASON
                    and item.get("location_id")==location
                    and item.get("amount_money")=={"amount":21450,"currency":"JPY"}):
                matches.append(item.get("status"))
        cursor=data.get("cursor")
        if not cursor:
            break
    else:
        return "sandbox_refund_pagination_incomplete", 2
    if len(matches)==0:
        return "no_matching_refund_observed_eventual_consistency_possible", 1
    if len(matches)>1:
        return "multiple_matching_refunds_operator_review", 2
    state=matches[0]
    if state in ("PENDING","COMPLETED"):
        return "one_matching_refund_"+state.lower(), 0
    if state in ("FAILED","REJECTED"):
        return "one_matching_refund_"+state.lower(), 2
    return "one_matching_refund_unknown_state", 2


if __name__=="__main__":
    result,code=audit()
    print("SHOP_SANDBOX_REFUND_READONLY_AUDIT="+result)
    print("SHOP_SANDBOX_REFUND_POSTS_PERFORMED=0")
    sys.exit(code)
