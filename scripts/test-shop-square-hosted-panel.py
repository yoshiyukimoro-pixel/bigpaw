"""Offline safety checks for opted-in hosted Checkout Sandbox panel probe."""
import ast
from pathlib import Path
import unittest

class PanelSmokeSafety(unittest.TestCase):
    def test_checkout_panel_scripts_do_not_target_production(self):
        py = Path("scripts/smoke-shop-square-hosted-panel.py").read_text()
        js = Path("scripts/smoke-shop-square-hosted-panel.cjs").read_text()
        ast.parse(py)
        self.assertIn("connect.squareupsandbox.com", js)
        self.assertNotIn("connect.squareup.com", py)
        self.assertNotIn("connect.squareup.com", js)
        self.assertIn("sandbox.square.link", js)
        self.assertIn("Square Sandbox", py)
        self.assertIn("order_id", py)
        self.assertIn("payment_lookup=lambda pid:", py)
        self.assertIn("checkout", js.lower())
        self.assertNotIn("console.log(link.href)", js)
        self.assertNotIn("console.log(page.url())", js)
    def test_actions_branch_opt_in(self):
        workflow=Path(".github/workflows/square-sandbox-smoke.yml").read_text()
        self.assertIn("feature/dogfood-shop-staging-20261028", workflow)
        self.assertIn("run_sandbox_panel_smoke", workflow)
        self.assertIn("[square-panel-smoke]", workflow)
        self.assertIn("scripts/smoke-shop-square-hosted-panel.py",workflow)
        self.assertIn("scripts/smoke-shop-square-hosted-panel.cjs",workflow)


class FakeSquareResponse:
    status = 200
    def __init__(self, order):
        import json
        self.data = json.dumps({"order": order}).encode("utf-8")
    def __enter__(self): return self
    def __exit__(self, *_): return False
    def read(self, size): return self.data[:size]


class HostedShippingReadOnlyTests(unittest.TestCase):
    def test_complete_japanese_shipment_from_square_get(self):
        from shop_payments.sandbox_reconcile import retrieve_sandbox_shipment_status
        calls = []
        order = {
            "id": "FAKE_SQUARE_ORDER_1234",
            "fulfillments": [{
                "type": "SHIPMENT",
                "shipment_details": {
                    "recipient": {
                        "display_name": "Synthetic Sample",
                        "phone_number": "09012345678",
                        "address": {
                            "country": "JP",
                            "postal_code": "000-0000",
                            "address_line_1": "Sample-only address",
                        },
                    },
                },
            }],
        }
        def fake(req, timeout):
            calls.append((req.get_method(), req.full_url, timeout))
            return FakeSquareResponse(order)
        result = retrieve_sandbox_shipment_status(
            order["id"], token="FAKE_SANDBOX_TOKEN", opener=fake
        )
        self.assertEqual(result, {
            "square_order_id": "FAKE_SQUARE_ORDER_1234",
            "shipment_details_complete": True,
        })
        self.assertEqual(calls, [(
            "GET",
            "https://connect.squareupsandbox.com/v2/orders/FAKE_SQUARE_ORDER_1234",
            10,
        )])
        self.assertNotIn("Sample-only address", str(result))
        self.assertNotIn("Synthetic Sample", str(result))

    def test_payment_completed_does_not_imply_shipping_complete(self):
        from shop_payments.sandbox_reconcile import retrieve_sandbox_shipment_status
        for overrides in (
            {"fulfillments": []},
            {"fulfillments": [{"type": "PICKUP"}]},
            {"fulfillments": [{"type": "SHIPMENT", "shipment_details": {
                "recipient": {"display_name": "Synthetic Sample",
                        "phone_number": "09012345678",
                              "email_address": "sample@example.invalid"}}}]},
            {"fulfillments": [{"type": "SHIPMENT", "shipment_details": {
                "recipient": {"display_name": "Synthetic Sample",
                        "phone_number": "09012345678",
                              "address": {"country": "US", "postal_code": "00000",
                                          "address_line_1": "Fake"}}}}]},
        ):
            with self.subTest(overrides=overrides):
                obj = {"id": "FAKE_SQUARE_ORDER_1234", **overrides}
                result = retrieve_sandbox_shipment_status(
                    obj["id"], token="FAKE_SANDBOX_TOKEN",
                    opener=lambda req, timeout: FakeSquareResponse(obj)
                )
                self.assertFalse(result["shipment_details_complete"])

    def test_shipping_audit_never_prints_or_persists_customer_data(self):
        source=Path("scripts/smoke-shop-square-hosted-panel.py").read_text()
        self.assertIn("retrieve_sandbox_shipment_status", source)
        self.assertIn("SQUARE_CHECKOUT_PANEL_SHIPPING=", source)
        self.assertNotIn('print(shipping)',source)
        self.assertNotIn('print(order["fulfillments"])',source)
        self.assertNotIn("square_order_data.dump",source)


if __name__=="__main__":
    unittest.main()
