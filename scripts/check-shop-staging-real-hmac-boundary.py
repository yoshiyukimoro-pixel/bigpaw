"""One controlled, real HTTPS HMAC boundary probe against isolated Square Sandbox webhook.

The private signing key is fetched from the *disabled* target subscription in
GitHub Actions process memory. Do NOT log Square responses, credentials, signed
payloads, subscription IDs, or any customer data.

This does NOT create payments, links, orders, or send real Square webhook events.
It only sends fabricated, unmatchable events to the new Railway test endpoint.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://connect.squareupsandbox.com/v2/webhooks/subscriptions"
TARGET = ("https://bigpaw-square-sandbox-staging-staging.up.railway.app"
          "/api/shop/sandbox/webhook")
OLD = "https://bigpaw-test-production.up.railway.app/api/shop/sandbox/webhook"
BRANCH = "refs/heads/feature/dogfood-shop-staging-20261028"
IDENTIFIER = re.compile(r"[A-Za-z0-9_-]{8,96}")
HEADERS = {"Square-Version": "2026-09-16",
           "User-Agent": "BIGPAW-Webhook-BoundaryCheck/1.0",
           "Accept": "application/json"}

def _get(url, token, opener):
    req = Request(url, headers={**HEADERS, "Authorization": "Bearer " + token},
                  method="GET")
    with opener(req, timeout=16) as response:
        if response.status != 200:
            raise ValueError("Unexpected provider GET status")
        raw = response.read(131073)
        if len(raw) > 131072:
            raise ValueError("Oversize provider response")
        obj = json.loads(raw)
    if not isinstance(obj, dict):
        raise ValueError("Invalid provider JSON")
    return obj

def _post(payload, signature, *, environment, opener):
    req = Request(TARGET, data=payload, method="POST", headers={
        "Content-Type": "application/json",
        "Square-Environment": environment,
        "X-Square-Hmacsha256-Signature": signature,
        "User-Agent": "BIGPAW-Webhook-BoundaryCheck/1.0",
    })
    # Read only a small, non-sensitive error code; never print the response.
    try:
        with opener(req, timeout=18) as response:
            raw = response.read(1025)
            if len(raw) > 1024:
                raise ValueError("Oversize receiver response")
            return response.status, json.loads(raw).get("status")
    except HTTPError as error:
        raw = error.read(1025)
        if len(raw) > 1024:
            raise ValueError("Oversize receiver error")
        return error.code, json.loads(raw).get("status")

def verify(env=None, *, opener=urlopen, nonce=None):
    env = os.environ if env is None else env
    if (env.get("GITHUB_ACTIONS") != "true"
            or env.get("GITHUB_REF") != BRANCH
            or env.get("BIGPAW_SANDBOX_HMAC_BOUNDARY_OPT_IN") != "1"):
        return "scope_or_opt_in_missing", 3
    token = env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", "")
    if not isinstance(token, str) or len(token.strip()) < 12:
        return "sandbox_token_unavailable", 2
    try:
        listing = _get(API + "?include_disabled=true&limit=100", token.strip(), opener)
        if listing.get("cursor"):
            return "subscription_list_not_exhaustive_no_post", 2
        rows = listing.get("subscriptions")
        if not isinstance(rows, list):
            return "subscription_list_invalid_no_post", 2
        current = [s for s in rows if isinstance(s, dict) and s.get("notification_url") == TARGET]
        old = [s for s in rows if isinstance(s, dict) and s.get("notification_url") == OLD]
        if (len(current) != 1 or current[0].get("enabled") is not False
                or "payment.updated" not in current[0].get("event_types", [])):
            return "target_subscription_unexpected_no_post", 2
        if (len(old) != 1 or old[0].get("enabled") is not True
                or "payment.updated" not in old[0].get("event_types", [])):
            return "original_subscription_unexpected_no_post", 2
        identifier = current[0].get("id")
        if not isinstance(identifier, str) or not IDENTIFIER.fullmatch(identifier):
            return "target_identifier_invalid_no_post", 2
        sub = _get(API + "/" + identifier, token.strip(), opener).get("subscription")
        if (not isinstance(sub, dict) or sub.get("id") != identifier
                or sub.get("notification_url") != TARGET or sub.get("enabled") is not False
                or "payment.updated" not in sub.get("event_types", [])):
            return "subscription_detail_changed_no_post", 2
        key = sub.get("signature_key")
        if not isinstance(key, str) or not 16 <= len(key) <= 1024:
            return "private_signature_key_missing_no_post", 2
    except HTTPError as exc:
        return "sandbox_subscription_read_http_" + str(exc.code), 2
    except (URLError, ValueError, OSError, TimeoutError, TypeError):
        return "sandbox_subscription_read_unavailable", 2

    marker = nonce if nonce is not None else secrets.token_hex(16)
    if not isinstance(marker, str) or not re.fullmatch(r"[0-9a-f]{32}", marker):
        return "nonce_invalid_no_post", 2

    # Not a real Square-created event. The impossible random Square order ID
    # must never match an entry in this isolated private database.
    event = {
        "event_id": "BIGPAW_SYNTHETIC_HMAC_" + marker,
        "type": "payment.updated",
        "data": {"object": {"payment": {
            "id": "SYNTHETIC_PAYMENT_" + marker,
            "order_id": "SYNTHETIC_ORDER_" + marker,
            "location_id": "SYNTHETIC_LOCATION",
            "status": "COMPLETED",
            "amount_money": {"amount": 1, "currency": "JPY"},
        }}},
    }
    raw = json.dumps(event, separators=(",", ":")).encode("utf-8")
    signed = base64.b64encode(hmac.new(
        key.encode("utf-8"), TARGET.encode("utf-8") + raw, hashlib.sha256
    ).digest()).decode("ascii")
    wrong_url = base64.b64encode(hmac.new(
        key.encode("utf-8"), (TARGET + "/").encode("utf-8") + raw, hashlib.sha256
    ).digest()).decode("ascii")

    # Exactly three controlled, non-retried posts. The positive HMAC must
    # reach the private journal and safely reject an unknown order, not mark
    # a completed payment. Invalid URL and environment must both return 403.
    checks = (
        ("correct_hmac_unknown_order", signed, "Sandbox", 503, "awaiting_square_confirmation"),
        ("wrong_url_signature", wrong_url, "Sandbox", 403, "invalid_signature_or_event"),
        ("wrong_environment", signed, "Production", 403, "invalid_environment"),
    )
    try:
        for name, signature, environment, expected_http, expected_code in checks:
            status, code = _post(raw, signature, environment=environment, opener=opener)
            if (status, code) != (expected_http, expected_code):
                return "rejected_boundary_" + name + "_no_retry", 2
    except (URLError, OSError, TimeoutError, ValueError, TypeError, UnicodeError):
        return "http_boundary_outcome_uncertain_no_retry", 2
    return "correct_signature_safe_rejection_and_invalid_signatures_blocked", 0

if __name__ == "__main__":
    result, exitcode = verify()
    print("SHOP_NEW_SANDBOX_HMAC_BOUNDARY=" + result)
    print("SHOP_SQUARE_PAYMENT_CREATED=NO")
    print("SHOP_SQUARE_SUBSCRIPTION_MUTATION=NO")
    print("SHOP_WEBHOOK_REAL_PAID_ORDER_VERIFIED=NO")
    sys.exit(exitcode)
