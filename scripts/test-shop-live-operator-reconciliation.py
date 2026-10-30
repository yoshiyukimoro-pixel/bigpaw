"""Offline guard tests for the dormant operator live-Square reconciliation."""
import unittest

from shop_payments import live_operator_reconciliation as route


class DummyHandler:
    def __init__(self, *, origin="https://bigpaw.site", host="bigpaw.site",
                 cookie="", body=None):
        self.path = "/api/operator/shop-orders/reconcile"
        self.headers = {"Origin": origin, "Host": host, "Cookie": cookie,
                        "Content-Length": "128"}
        self.body = body or {"order_id": "FOOD" + "a" * 32,
                             "payment_id": "SYNTHETICPAYMENT123",
                             "csrf_token": "A" * 43}
        self.responses = []

    def require(self, roles):
        assert roles == ["operator"]
        return {"id": "operator_123", "role": "operator"}

    def json_body(self):
        return self.body

    def send_json(self, payload, status=200, extra=None):
        self.responses.append((status, payload, extra))


class OperatorReconciliationGuardTests(unittest.TestCase):
    def setUp(self):
        self.env = {
            "BIGPAW_SHOP_LIVE_OPERATOR_RECONCILIATION_ENABLED": "1",
            "BIGPAW_SQUARE_LIVE_ACCESS_TOKEN": "synthetic-live-key-not-valid-000000000000000",
        }

    def test_disabled_by_default_and_nonproduction(self):
        self.assertFalse(route.enabled({}, is_production=True))
        self.assertFalse(route.enabled(self.env, is_production=False))
        self.assertTrue(route.enabled(self.env, is_production=True))

    def test_strict_exact_origin_and_host(self):
        self.assertTrue(route._same_origin(
            DummyHandler(), "https://bigpaw.site"))
        self.assertFalse(route._same_origin(
            DummyHandler(origin="https://www.bigpaw.site"), "https://bigpaw.site"))
        self.assertFalse(route._same_origin(
            DummyHandler(host="evil.example"), "https://bigpaw.site"))

    def test_post_rejects_bad_origin_before_operator_or_square_action(self):
        handler = DummyHandler(origin="https://evil.example")
        handled = route.handle_post(
            handler, env=self.env, is_production=True,
            base_url="https://bigpaw.site", data_dir=None)
        self.assertTrue(handled)
        self.assertEqual(handler.responses[0][0], 403)
        self.assertEqual(handler.responses[0][1]["error"], "invalid_origin_or_csrf")

    def test_post_requires_double_submit_csrf(self):
        handler = DummyHandler()
        handled = route.handle_post(
            handler, env=self.env, is_production=True,
            base_url="https://bigpaw.site", data_dir=None)
        self.assertTrue(handled)
        self.assertEqual(handler.responses[0][0], 403)
        self.assertEqual(handler.responses[0][1]["error"], "invalid_origin_or_csrf")


if __name__ == "__main__":
    unittest.main()
