"""No external network tests for isolated, one-shot Square Sandbox checkout."""
from pathlib import Path
import tempfile
import unittest

from shop_payments.staging_seed_boot import create_enabled_test_link
from shop_payments.sandbox_runtime_guard import (
    EXISTING_TEST_ENVIRONMENT, EXISTING_TEST_SERVICE, LEGACY_BIGPAW_PROJECT,
)

ORDER = "FOOD" + "d" * 32
URL = "https://bigpaw-test-production.up.railway.app/api/shop/sandbox/webhook"
ENV = {
    "RAILWAY_PROJECT_ID": LEGACY_BIGPAW_PROJECT,
    "RAILWAY_ENVIRONMENT_ID": EXISTING_TEST_ENVIRONMENT,
    "RAILWAY_SERVICE_ID": EXISTING_TEST_SERVICE,
    "BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID": LEGACY_BIGPAW_PROJECT,
    "BIGPAW_ENV": "sandbox",
    "BIGPAW_SHOP_STAGING_ISOLATED": "1",
    "BIGPAW_SHOP_STAGING_HTTPS_ENABLED": "1",
    "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "FAKE_SANDBOX_TOKEN",
    "BIGPAW_SQUARE_SANDBOX_LOCATION_ID": "SANDBOX_LOCATION_12345",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY": "FAKE_SIGNATURE",
    "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL": URL,
    "BIGPAW_SHOP_SANDBOX_SEED_ENABLED": "1",
    "BIGPAW_SHOP_SANDBOX_SEED_ORDER_ID": ORDER,
}


class TestSeedBoot(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.env = {**ENV, "BIGPAW_SHOP_SANDBOX_DB": str(Path(tmp.name) / "test.sqlite3")}
        self.events = []
        self.orders = []

    def creator(self, payload, *, token):
        self.assertEqual(token, "FAKE_SANDBOX_TOKEN")
        self.assertEqual(payload["order"]["location_id"], "SANDBOX_LOCATION_12345")
        self.assertEqual(payload["order"]["line_items"][0]["base_price_money"]["amount"], 21450)
        self.orders.append(payload["idempotency_key"])
        return {
            "url": "https://sandbox.square.link/u/test-order-only",
            "square_order_id": "SANDBOX_ORDER_ONLY_12345",
            "square_link_id": "SANDBOX_LINK_ONLY_12345",
        }

    def invoke(self, env=None):
        return create_enabled_test_link(
            self.env if env is None else env,
            creator=self.creator,
            output=self.events.append,
        )

    def test_exactly_one_link_after_repeated_startups(self):
        self.assertEqual(self.invoke(), "created")
        self.assertEqual(len(self.orders), 1)
        self.assertIn("price_yen=21450", self.events[-1])
        self.assertIn("sandbox.square.link", self.events[-1])
        self.assertEqual(self.invoke(), "reused")
        self.assertEqual(len(self.orders), 1)
        self.assertIn("SHOP_SANDBOX_SEED=REUSED", self.events[-1])

    def test_fail_closed_for_wrong_service_or_missing_consent(self):
        altered = [
            {**self.env, "BIGPAW_SHOP_SANDBOX_SEED_ENABLED": "0"},
            {**self.env, "BIGPAW_SHOP_SANDBOX_SEED_ORDER_ID": ""},
            {**self.env, "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": ""},
            {**self.env, "RAILWAY_PROJECT_ID": "afb79723-1a2d-4c43-b498-f166e501760c"},
            {**self.env, "RAILWAY_SERVICE_ID": "32e31163-1049-41d3-84f8-dd61a0a7019e"},
            {**self.env, "RAILWAY_SERVICE_ID": "1ad6d952-c284-4886-9237-a30c364132fd"},
            {**self.env, "RAILWAY_ENVIRONMENT_ID": "another-environment"},
        ]
        for invalid in altered:
            self.assertNotIn(self.invoke(invalid), ("created", "reused"))
        self.assertEqual(self.orders, [])

    def test_sandbox_api_failure_does_not_kill_server_or_log_secrets(self):
        def unavailable(payload, *, token):
            from shop_payments.sandbox_connector import SquareSandboxError
            raise SquareSandboxError("test network failure: " + token)
        outcome = create_enabled_test_link(
            self.env, creator=unavailable, output=self.events.append,
        )
        self.assertEqual(outcome, "failed")
        self.assertEqual(self.events[-1], "SHOP_SANDBOX_SEED=FAILED_CHECK_SANDBOX_SETUP")
        self.assertNotIn("FAKE_SANDBOX_TOKEN", self.events[-1])


if __name__ == "__main__":
    unittest.main()
