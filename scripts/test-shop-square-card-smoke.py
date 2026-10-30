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


if __name__ == "__main__":
    unittest.main()
