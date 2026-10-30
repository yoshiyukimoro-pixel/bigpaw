"""Zero-network Square PRODUCTION readiness diagnostics (synthetic data only)."""
import json
import unittest
from urllib.error import URLError

from shop_payments.square_live_preflight import (
    BASE, REQUIRED_VARIABLES, SQUARE_OAUTH_PERMISSIONS_REQUIRED,
    SquareLivePreflightBlocked, audit_variable_names,
    verify_live_location_readonly,
)

TOKEN = "NONREAL_SYNTHETIC_CREDENTIAL_123456789"
LOCATION = "FAKEJPLOCATION123456"


class FakeResponse:
    status = 200
    def __init__(self, obj, *, status=200):
        self.body = json.dumps(obj).encode()
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, size):
        return self.body[:size]


class LivePreflightTests(unittest.TestCase):
    def test_real_world_like_railway_name_inventory_is_missing_live_square(self):
        # Redacted variable NAMES only, not passwords or actual values.
        inventory = audit_variable_names({
            "BIGPAW_ENV", "BIGPAW_DATA_DIR", "BIGPAW_PUBLIC_BASE_URL",
        })
        self.assertFalse(inventory["production_variables_present"])
        self.assertIn("BIGPAW_SQUARE_LIVE_ACCESS_TOKEN",
                      inventory["missing_variable_names"])
        self.assertIn("BIGPAW_SQUARE_LIVE_LOCATION_ID",
                      inventory["missing_variable_names"])
        self.assertFalse(inventory["safe_to_enable_sales"])
        self.assertFalse(inventory["production_write_permissions_checked"])
        self.assertFalse(inventory["has_sandbox_credentials_on_live_service"])
        self.assertTrue(audit_variable_names(REQUIRED_VARIABLES)[
            "production_variables_present"])
        self.assertFalse(audit_variable_names(REQUIRED_VARIABLES)[
            "safe_to_enable_sales"], "presence alone is never authorization")
        suspicious = audit_variable_names(
            list(REQUIRED_VARIABLES) + ["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]
        )
        self.assertTrue(suspicious["has_sandbox_credentials_on_live_service"])
        for name in SQUARE_OAUTH_PERMISSIONS_REQUIRED:
            self.assertIn(name, {
                "MERCHANT_PROFILE_READ", "ORDERS_READ", "ORDERS_WRITE",
                "PAYMENTS_READ", "PAYMENTS_WRITE",
            })

    def test_single_read_only_square_production_japan_location(self):
        calls = []
        def opener(req, timeout):
            calls.append((req.get_method(), req.full_url))
            self.assertEqual(timeout, 10)
            self.assertEqual(req.headers["Authorization"], "Bearer " + TOKEN)
            self.assertEqual(req.headers["Square-version"], "2026-09-16")
            return FakeResponse({"location": {
                "id": LOCATION, "country": "JP", "currency": "JPY",
                "status": "ACTIVE", "capabilities": ["CREDIT_CARD_PROCESSING"],
                "name": "REDACTED", "address": {"address_line_1": "NOT FOR LOG"},
            }})
        result = verify_live_location_readonly(
            access_token=TOKEN, location_id=LOCATION, opener=opener)
        self.assertEqual(calls, [
            ("GET", BASE + "/locations/" + LOCATION),
        ])
        self.assertTrue(result["production_location_checked"])
        self.assertFalse(result["production_write_permissions_checked"])
        self.assertFalse(result["safe_to_enable_sales"])
        self.assertNotIn("REDACTED", str(result))
        self.assertNotIn("NOT FOR LOG", str(result))
        self.assertNotIn(TOKEN, str(result))

    def test_wrong_country_currency_status_or_id_fails_without_leak(self):
        normal = {
            "id": LOCATION, "country": "JP", "currency": "JPY",
            "status": "ACTIVE", "capabilities": ["CREDIT_CARD_PROCESSING"],
        }
        for changed in (
            {"id": "WRONGLOCATION123"},
            {"country": "US"},
            {"currency": "USD"},
            {"status": "INACTIVE"},
            {"capabilities": []},
        ):
            with self.subTest(changed=changed):
                def opener(req, timeout):
                    return FakeResponse({"location": {**normal, **changed}})
                with self.assertRaises(SquareLivePreflightBlocked):
                    verify_live_location_readonly(
                        access_token=TOKEN, location_id=LOCATION,
                        opener=opener)
        for bad in ({}, [], {"location": []}, {"errors": [{"code": "UNAUTHORIZED"}]}):
            with self.assertRaises(SquareLivePreflightBlocked):
                verify_live_location_readonly(
                    access_token=TOKEN, location_id=LOCATION,
                    opener=lambda req, timeout:FakeResponse(bad))

    def test_no_bad_location_id_or_secret_can_make_network_call(self):
        calls = []
        def opener(*args, **kwargs):
            calls.append(True)
            raise AssertionError("must not reach network")
        for token, location in (
            ("short", LOCATION), (TOKEN, "https://connect.squareupsandbox.com"),
            (TOKEN, "../orders"), (TOKEN, "bad/path"), (TOKEN, "x"),
            (TOKEN + "\n", LOCATION),
        ):
            with self.subTest(location=location), self.assertRaises(
                    SquareLivePreflightBlocked):
                verify_live_location_readonly(access_token=token,
                    location_id=location, opener=opener)
        self.assertEqual(calls, [])

    def test_timeout_fails_closed_without_a_write_or_secrets(self):
        calls=[]
        def opener(req, timeout):
            calls.append((req.get_method(), req.full_url))
            raise URLError("fake Square API access error")
        with self.assertRaisesRegex(
                SquareLivePreflightBlocked, "could not be verified"):
            verify_live_location_readonly(
                access_token=TOKEN, location_id=LOCATION, opener=opener)
        self.assertEqual(calls, [("GET", BASE + "/locations/" + LOCATION)])


if __name__ == "__main__":
    unittest.main()
