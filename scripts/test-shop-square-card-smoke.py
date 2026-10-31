"""Offline regression: unsupported direct linked-card path cannot call Square."""
import contextlib
import importlib.util
import io
from pathlib import Path
import unittest

spec = importlib.util.spec_from_file_location(
    "square_card_smoke", Path("scripts/smoke-shop-square-card-payment.py"))
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class TestDisabledLinkedCard(unittest.TestCase):
    @staticmethod
    def forbidden(*args, **kwargs):
        raise AssertionError("Unexpected Square network operation")

    def test_no_credentials_no_requests(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = smoke.main(env={}, link_creator=self.forbidden,
                                payment_creator=self.forbidden, payment_reader=self.forbidden)
        self.assertEqual(result, 2)
        self.assertIn("PROBE_DISABLED", output.getvalue())

    def test_credentials_do_not_enable_unsupported_payment(self):
        secret = "FAKE_SANDBOX_SECRET_DO_NOT_LOG"
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            result = smoke.main(
                env={"BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": secret,
                     "BIGPAW_SQUARE_SANDBOX_LOCATION_ID": "TEST_LOCATION"},
                link_creator=self.forbidden, payment_creator=self.forbidden,
                payment_reader=self.forbidden)
        self.assertEqual(result, 2)
        self.assertIn("No Square request", output.getvalue())
        self.assertNotIn(secret, output.getvalue())

    def test_no_implicit_fallback_or_false_success(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(smoke.main(), 2)
        self.assertIn("Sandbox Testing Panel", output.getvalue())
        self.assertNotIn("SQUARE_CARD_SANDBOX_OK", output.getvalue())

    def test_linked_order_id_rejected_before_http(self):
        from shop_payments.sandbox_connector import SquareSandboxError
        with self.assertRaises(SquareSandboxError):
            smoke.create_fake_card_payment(
                order_id="DRAFT_LINK_ORDER", location_id="TESTLOCATION",
                token="FAKE_SANDBOX_TOKEN", idempotency_key="bpapi-test-123",
                opener=self.forbidden)

    def test_standalone_api_request_contains_no_checkout_order(self):
        import json
        class Response:
            status = 200
            def __enter__(self):
                return self
            def __exit__(self, *args):
                return None
            def read(self, limit):
                return json.dumps({"payment": {"id": "TESTSANDBOXPAYMENT"}}).encode()
        def opener(request, timeout):
            self.assertEqual(request.full_url, "https://connect.squareupsandbox.com/v2/payments")
            body = json.loads(request.data)
            self.assertNotIn("order_id", body)
            self.assertEqual(body["source_id"], "cnon:card-nonce-ok")
            self.assertEqual(body["amount_money"], {"amount": 21450, "currency": "JPY"})
            return Response()
        result = smoke.create_fake_card_payment(
            order_id=None, location_id="TESTLOCATION",
            token="FAKE_SANDBOX_TOKEN", idempotency_key="bpapi-test-123",
            opener=opener)
        self.assertEqual(result["id"], "TESTSANDBOXPAYMENT")


if __name__ == "__main__":
    unittest.main()
