"""Fail-closed food-shop public launch gate (offline, no secrets, no writes).

A checklist/CI preflight, not a production payment switch. Current storefront
remains disabled independently. All required merchant information, policy and
operating procedures must be verified by the proprietor before a future live
deployment can be considered. No personal details are committed to the repo.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
MANIFEST = ROOT / "retail_launch_status.json"
REQUIRED = (
    "seller_identity", "statutory_contact", "return_policy",
    "checkout_disclosure", "fulfillment_sla", "customer_email_delivery",
    "square_live_readiness", "environment_separation",
    "production_e2e_tests", "proprietor_approval",
)

def check(status: dict) -> tuple[bool, list[str]]:
    if not isinstance(status, dict):
        return False, ["invalid_manifest"]
    missing = []
    if status.get("business_structure") != "individual_proprietor":
        missing.append("business_structure")
    if status.get("sandbox_only") is not True:
        # This manifest may never declare the Sandbox switch itself to be off.
        missing.append("sandbox_only")
    checks = status.get("launch_checks")
    if not isinstance(checks, dict):
        return False, missing + ["missing_launch_checks"]
    for key in REQUIRED:
        if checks.get(key) is not True:
            missing.append(key)
    if status.get("public_live_checkout_enabled") is not False:
        missing.append("live_checkout_not_guarded")
    return not missing, missing


def load_and_check(path: Path = MANIFEST) -> tuple[bool, list[str]]:
    return check(json.loads(path.read_text(encoding="utf-8")))


if __name__ == "__main__":
    ready, pending = load_and_check()
    print("BIG PAW food-shop launch ready:", "YES" if ready else "NO")
    if pending:
        print("Pending:", ", ".join(pending))
    raise SystemExit(0 if not ready else 1)
    # CLI intentionally returns failure if someone attempts to treat a
    # completed-looking manifest as authorization to go live. Explicit human
    # production approval and a separate deployment gate are still required.
