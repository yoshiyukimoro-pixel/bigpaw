"""Fail-closed Railway service identity guard for the BIG PAW food shop Sandbox.

The original BIG PAW production services must never run a Square Sandbox webhook.
The pre-existing Railway 'bigpaw-test' service can be reused ONLY if its exact
project + environment + service IDs match. Project name alone is NOT sufficient.
This module never configures Railway or reads secret values.
"""
from __future__ import annotations

PRIMARY_PRODUCTION_PROJECT = "afb79723-1a2d-4c43-b498-f166e501760c"
LEGACY_BIGPAW_PROJECT = "d70f7165-f5eb-41e8-95a0-62f85ff90478"
EXISTING_TEST_ENVIRONMENT = "ecc9fcbf-496f-4b51-a651-65a46a971588"
EXISTING_TEST_SERVICE = "1a1a32bd-e885-4848-a6b5-fde5ef9ac902"
NEW_STAGING_PROJECT = "91215e46-028b-4280-90f4-8d192c687164"
NEW_STAGING_ENVIRONMENT = "d0dacfcc-781b-4360-b539-461783ad47e2"
NEW_SANDBOX_WEBHOOK_SERVICE = "ca40ca3c-d65a-4f51-99f3-b85ebfca164d"


def is_allowed_sandbox_runtime(env: dict) -> bool:
    """Local tests or exactly one isolated non-production service are allowed.

    Railway's auto-generated service/environment/project IDs are authoritative.
    Explicit staging flags alone never make a production service eligible.
    """
    if env.get("BIGPAW_SHOP_STAGING_ISOLATED") != "1":
        return False
    project = env.get("RAILWAY_PROJECT_ID") or ""
    environment = env.get("RAILWAY_ENVIRONMENT_ID") or ""
    service = env.get("RAILWAY_SERVICE_ID") or ""
    allowed_project = env.get("BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID") or ""
    if project == PRIMARY_PRODUCTION_PROJECT:
        return False
    if not (project or environment or service):
        return True  # localhost-only test, no Railway identifiers
    if not all((project, environment, service, allowed_project)):
        return False
    if project != allowed_project:
        return False
    if project == LEGACY_BIGPAW_PROJECT:
        # Only the pre-existing test service, not bigpaw-site / bigpaw-web.
        return (environment == EXISTING_TEST_ENVIRONMENT
                and service == EXISTING_TEST_SERVICE)
    if project == NEW_STAGING_PROJECT:
        # The protected full-app service in this SAME project must not
        # accidentally accept or serve Square Sandbox events.
        return (environment == NEW_STAGING_ENVIRONMENT
                and service == NEW_SANDBOX_WEBHOOK_SERVICE)
    return False  # Unknown Railway projects must be explicitly added and reviewed
