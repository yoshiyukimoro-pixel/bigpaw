"""Read-only, opt-in preflight for Square PRODUCTION settings.

Never creates or updates a Square payment link, order, refund or location.
The normal, name-only audit has NO network and takes no token values.
A separate approved caller may inject a fake opener in tests, or explicitly
request a single GET to an exact production location once a credential exists.

Successful location GET confirms only merchant location access, NOT
ORDERS_WRITE/PAYMENTS_WRITE permissions required for CreatePaymentLink.
No token, location name, business name or address is printed or persisted.
"""
from __future__ import annotations

import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .sandbox_connector import SQUARE_VERSION

BASE = "https://connect.squareup.com/v2"
LOCATION_RE = re.compile(r"^[A-Za-z0-9_-]{8,80}$")
REQUIRED_VARIABLES = (
    "BIGPAW_SQUARE_LIVE_ACCESS_TOKEN",
    "BIGPAW_SQUARE_LIVE_LOCATION_ID",
    "BIGPAW_SHOP_ORDER_HMAC_SECRET",
    "BIGPAW_SHOP_APPROVED_TERMS_SHA256",
    "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED",
    "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED",
)
SQUARE_OAUTH_PERMISSIONS_REQUIRED = (
    "MERCHANT_PROFILE_READ", "ORDERS_READ", "ORDERS_WRITE",
    "PAYMENTS_READ", "PAYMENTS_WRITE",
)


def audit_variable_names(variable_names):
    """Use Railway redacted variable NAMES only, never request secret values.

    This is a READINESS inventory, not permission to turn checkout on.
    """
    if not isinstance(variable_names, (list, tuple, set, frozenset)):
        raise ValueError("Variable name inventory required")
    if any(not isinstance(name, str) for name in variable_names):
        raise ValueError("Variable name inventory invalid")
    names = set(variable_names)
    missing = sorted(set(REQUIRED_VARIABLES) - names)
    sandbox_names = sorted(
        key for key in names
        if key.startswith("BIGPAW_SQUARE_SANDBOX_")
    )
    return {
        "production_variables_present": not missing,
        "missing_variable_names": missing,
        "has_sandbox_credentials_on_live_service": bool(sandbox_names),
        "production_location_checked": False,
        "production_write_permissions_checked": False,
        "safe_to_enable_sales": False,
    }


class SquareLivePreflightBlocked(ValueError):
    """Insufficient proof for a production Square merchant location."""


def verify_live_location_readonly(*, access_token, location_id,
                                  opener=urlopen):
    """One optional, exact-path Square Production GET, NO payment writes.

    Call ONLY after explicit operator approval of a read-only production
    credential check. The caller holds the token privately; the returned
    dictionary never includes token, merchant, location or customer details.
    """
    if (not isinstance(access_token, str)
            or len(access_token.strip()) < 20
            or any(x in access_token for x in ("\n", "\r"))):
        raise SquareLivePreflightBlocked("Missing or invalid private credential")
    if (not isinstance(location_id, str)
            or not LOCATION_RE.fullmatch(location_id)):
        raise SquareLivePreflightBlocked("Unrecognized production location ID")
    req = Request(
        BASE + "/locations/" + location_id,
        headers={
            "Authorization": "Bearer " + access_token.strip(),
            "Square-Version": SQUARE_VERSION,
            "Accept": "application/json",
        }, method="GET",
    )
    try:
        with opener(req, timeout=10) as response:
            if getattr(response, "status", 200) != 200:
                raise SquareLivePreflightBlocked(
                    "Production location read unavailable")
            payload = response.read(65537)
            if len(payload) > 65536:
                raise SquareLivePreflightBlocked("Oversize Square response")
            data = json.loads(payload)
    except (HTTPError, URLError, TimeoutError, OSError, ValueError):
        raise SquareLivePreflightBlocked(
            "Production Square location could not be verified"
        ) from None
    loc = data.get("location") if isinstance(data, dict) else None
    if (not isinstance(loc, dict)
            or loc.get("id") != location_id
            or loc.get("country") != "JP"
            or loc.get("currency") != "JPY"
            or loc.get("status") != "ACTIVE"):
        raise SquareLivePreflightBlocked(
            "Merchant location inactive, mismatched, or not JPY/JP"
        )
    capabilities = loc.get("capabilities")
    if (not isinstance(capabilities, list)
            or "CREDIT_CARD_PROCESSING" not in capabilities):
        raise SquareLivePreflightBlocked(
            "Card processing capability not confirmed"
        )
    return {
        "production_location_checked": True,
        "country": "JP", "currency": "JPY", "active": True,
        "card_processing": True,
        "production_write_permissions_checked": False,
        "safe_to_enable_sales": False,
    }
