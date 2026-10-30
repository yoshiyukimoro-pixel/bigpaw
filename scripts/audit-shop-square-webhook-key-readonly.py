"""READ ONLY: confirm isolated disabled Square Sandbox webhook has retrievable signing key.

The Square application token is supplied only by GitHub Actions secrets. All
provider JSON fields (including subscription ID, signature key, and other
developers' notification URLs) stay in process memory and are never logged.
No checkout, payment, email, Railway changes, or webhook deliveries occur.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shop_payments.square_checkout import verify_square_webhook

API = "https://connect.squareupsandbox.com/v2/webhooks/subscriptions"
TARGET = (
    "https://bigpaw-square-sandbox-staging-staging.up.railway.app"
    "/api/shop/sandbox/webhook"
)
REF = "refs/heads/feature/dogfood-shop-staging-20261028"
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{8,96}\Z")


def _get(url, token, *, opener):
    request = Request(url, headers={
        "Authorization": "Bearer " + token,
        "Square-Version": "2026-09-16",
        "Accept": "application/json",
    }, method="GET")
    with opener(request, timeout=12) as response:
        if response.status != 200:
            raise ValueError("Square GET status unavailable")
        raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError("Square GET response too large")
        obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("Invalid Square response")
    return obj


def audit(env=None, opener=urlopen):
    env = os.environ if env is None else env
    if env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REF") != REF:
        return "wrong_execution_scope", 3
    token = env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", "").strip()
    if len(token) < 12:
        return "sandbox_application_token_unavailable", 2
    try:
        listing = _get(API + "?include_disabled=true&limit=100",
                       token, opener=opener)
        if listing.get("cursor"):
            return "subscription_list_not_exhaustive", 2
        rows = listing.get("subscriptions", [])
        if not isinstance(rows, list):
            return "subscription_list_invalid", 2
        matches = [
            sub for sub in rows if isinstance(sub, dict)
            and sub.get("notification_url") == TARGET
        ]
        if len(matches) != 1:
            return "missing_or_duplicate_isolated_target", 2
        stub = matches[0]
        identifier = stub.get("id")
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            return "isolated_subscription_id_invalid", 2
        if stub.get("enabled") is not False:
            return "isolated_subscription_not_disabled", 2
        detail = _get(API + "/" + identifier, token, opener=opener)
        sub = detail.get("subscription")
        if (not isinstance(sub, dict) or sub.get("id") != identifier
                or sub.get("notification_url") != TARGET
                or sub.get("enabled") is not False
                or not isinstance(sub.get("event_types"), list)
                or "payment.updated" not in sub["event_types"]):
            return "isolated_subscription_details_unverified", 2
        key = sub.get("signature_key")
        if not isinstance(key, str) or len(key) < 16 or len(key) > 1024:
            return "isolated_subscription_signature_key_unavailable", 2
        # Local-only signing exercise: signed bytes are not sent anywhere.
        body = (b'{"event_id":"SYNTHETIC_ONLY_123456789",'
                b'"type":"payment.updated","data":{}}')
        sig = base64.b64encode(hmac.new(
            key.encode("utf-8"), TARGET.encode("utf-8") + body,
            hashlib.sha256,
        ).digest()).decode("ascii")
        signed = verify_square_webhook(
            raw_body=body, signature_header=sig,
            signature_key=key, notification_url=TARGET,
        )
        if signed.get("event_id") != "SYNTHETIC_ONLY_123456789":
            return "local_signature_roundtrip_invalid", 2
        try:
            verify_square_webhook(
                raw_body=body, signature_header=sig,
                signature_key=key, notification_url=TARGET + "/",
            )
        except ValueError:
            pass
        else:
            return "signature_not_bound_to_exact_url", 2
    except HTTPError as error:
        return ("sandbox_read_permission_unavailable" if error.code in (401, 403)
                else "sandbox_subscription_read_http_unavailable"), 2
    except (URLError, OSError, TimeoutError, ValueError, TypeError,
            UnicodeError):
        return "sandbox_subscription_signature_check_unverified", 2
    return "new_disabled_subscription_key_readable_local_hmac_ok", 0


if __name__ == "__main__":
    result, code = audit()
    print("SHOP_SQUARE_SANDBOX_WEBHOOK_KEY_AUDIT=" + result)
    print("SHOP_SQUARE_SANDBOX_KEY_LOGGED=NO")
    print("SHOP_SQUARE_WEBHOOK_DELIVERY=NOT_TESTED")
    sys.exit(code)
