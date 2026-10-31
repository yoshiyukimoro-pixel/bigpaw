"""Read-only Resend verified sender domain preflight (NO email send).

Never prints account data, domain IDs, authentication, addresses or provider
error messages. A successful read-only check does not establish delivery.
"""
from __future__ import annotations

import json
import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ENDPOINT = "https://api.resend.com/domains?limit=100"
DOMAIN = "bigpaw.site"
REF = "refs/heads/feature/dogfood-shop-staging-20261028"


def audit(env=None, opener=urlopen):
    env = os.environ if env is None else env
    if env.get("GITHUB_ACTIONS") != "true" or env.get("GITHUB_REF") != REF:
        return "blocked_wrong_environment", 3
    key = env.get("RESEND_API_KEY", "").strip()
    if not key or not key.startswith("re_"):
        return "email_api_key_not_configured", 2
    req = Request(ENDPOINT, headers={
        "Authorization": "Bearer " + key,
        "Accept": "application/json",
        "User-Agent": "BIGPAW-Sender-Domain-ReadOnly/1.0",
    }, method="GET")
    try:
        with opener(req, timeout=12) as resp:
            if resp.status != 200:
                return "provider_response_unverified", 2
            raw = resp.read(262145)
            if len(raw) > 262144:
                return "provider_data_too_large", 2
            data = json.loads(raw)
    except HTTPError as exc:
        # Sending-access keys legitimately cannot GET domain metadata.
        if exc.code in (401, 403):
            return "read_permission_unavailable", 2
        return "provider_http_unavailable", 2
    except (URLError, TimeoutError, ValueError, OSError, TypeError):
        return "provider_network_or_format_unverified", 2
    if not isinstance(data, dict) or not isinstance(data.get("data"), list):
        return "invalid_domains_response", 2
    matches = [d for d in data["data"]
               if isinstance(d, dict) and d.get("name") == DOMAIN]
    if len(matches) != 1:
        return ("domain_missing_or_paginated" if not matches
                else "duplicate_domain_ambiguous"), 2
    domain = matches[0]
    if domain.get("status") != "verified":
        return "domain_not_verified", 2
    capabilities = domain.get("capabilities")
    if not isinstance(capabilities, dict):
        return "domain_verified_sending_capability_unverified", 2
    if capabilities.get("sending") != "enabled":
        return "domain_verified_sending_disabled", 2
    return "domain_verified_sending_enabled_read_only", 0


def main():
    result, code = audit()
    print("SHOP_RESEND_DOMAIN_AUDIT=" + result)
    print("SHOP_RESEND_FROM=noreply_at_bigpaw_site_configured_in_code")
    print("SHOP_RESEND_DELIVERY=NOT_TESTED")
    return code


if __name__ == "__main__":
    sys.exit(main())
