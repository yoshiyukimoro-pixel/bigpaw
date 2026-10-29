"""Unit tests for opt-in Square Sandbox connection smoke, without HTTP or tokens."""
import importlib.util
import io
from pathlib import Path
from contextlib import redirect_stdout
import unittest

spec = importlib.util.spec_from_file_location(
    "square_smoke", Path("scripts/smoke-shop-square-sandbox.py")
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)


class SmokeCommandTest(unittest.TestCase):
    def test_missing_credentials_does_not_call_square(self):
        def must_not_call(*args, **kwargs):
            self.fail("Square should not be contacted")
        out = io.StringIO()
        with redirect_stdout(out):
            status = smoke.main(env={}, link_creator=must_not_call)
        self.assertEqual(status, 2)
        self.assertIn("NOT_CONFIGURED", out.getvalue())

    def test_valid_sandbox_link_and_no_secret_in_log(self):
        calls = []
        def fake_creator(payload, *, token):
            calls.append((payload, token))
            return {
                "url": "https://sandbox.square.link/u/offline-test",
                "square_order_id": "SQUAREORDERTEST001",
                "square_link_id": "SQUARELINKTEST001",
            }
        out = io.StringIO()
        with redirect_stdout(out):
            status = smoke.main(env={
                "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "FAKE_SANDBOX_SECRET",
                "BIGPAW_SQUARE_SANDBOX_LOCATION_ID": "SANDBOXLOCATION1234",
            }, link_creator=fake_creator)
        self.assertEqual(status, 0)
        self.assertEqual(len(calls), 1)
        self.assertEqual(calls[0][0]["order"]["line_items"][0]["base_price_money"]["amount"], 21450)
        self.assertEqual(calls[0][0]["order"]["taxes"][0]["type"], "INCLUSIVE")
        self.assertNotIn("FAKE_SANDBOX_SECRET", out.getvalue())
        self.assertNotIn("https://sandbox.square.link/u/", out.getvalue())

    def test_bad_square_response_fails_without_url_leak(self):
        def wrong_creator(*args, **kwargs):
            return {
                "url": "https://square.link/u/production-not-allowed",
                "square_order_id": "LIVEORDERTEST001",
                "square_link_id": "LIVELINKTEST001",
            }
        out = io.StringIO()
        with redirect_stdout(out):
            status = smoke.main(env={
                "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN": "DONT_LOG_THIS",
                "BIGPAW_SQUARE_SANDBOX_LOCATION_ID": "SANDBOXLOCATION1234",
            }, link_creator=wrong_creator)
        self.assertEqual(status, 1)
        self.assertNotIn("DONT_LOG_THIS", out.getvalue())
        self.assertNotIn("https://square.link/", out.getvalue())


if __name__ == "__main__":
    unittest.main()
