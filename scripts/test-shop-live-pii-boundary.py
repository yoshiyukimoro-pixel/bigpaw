"""End-to-end PII minimization checks with fully synthetic Square fixtures."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shop_payments.live_customer_notice_preview import preview_paid_order_confirmation
from shop_payments.live_notice_approval import LiveNoticeApproval
from shop_payments.live_order_ledger import LiveOrderLedger
from shop_payments.live_order_overview import read_order_management_snapshot
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.square_live_readonly import ENDPOINT, verify_paid_live_shipment
from shop_payments.staging_live_overview_page import render_order_overview_preview

ORDER = "FOOD" + "d" * 32
SQUARE_ORDER = "PIIBOUNDARYORDER12345"
LOCATION = "PIIBOUNDARYLOCATION12"
PAYMENT = "PIIBOUNDARYPAYMENT123"
API_KEY = "synthetic-live-square-key-not-real"
REVIEW_KEY = "synthetic-review-key-not-real-123456"
PII = (
    "FAKE RECIPIENT NAME",
    "synthetic-pii@example.invalid",
    "99 Synthetic Street",
    "999-9999",
    "090-9999-9999",
)


class FakeResponse:
    status = 200

    def __init__(self, value):
        self.raw = json.dumps(value).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.raw[:size]


class LivePiiBoundaryTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / "synthetic-private-orders.sqlite3"
        self.ledger = LiveOrderLedger(self.path)
        self.sku, self.product = next(iter(load_sale_catalog().items()))
        self.amount = self.product.sale_price_yen
        self.payment = {
            "id": PAYMENT, "order_id": SQUARE_ORDER,
            "location_id": LOCATION, "status": "COMPLETED",
            "amount_money": {"amount": self.amount, "currency": "JPY"},
            "refunded_money": {"amount": 0, "currency": "JPY"},
        }
        self.order = {
            "id": SQUARE_ORDER, "location_id": LOCATION, "state": "OPEN",
            "total_money": {"amount": self.amount, "currency": "JPY"},
            "fulfillments": [{"type": "SHIPMENT", "shipment_details": {
                "recipient": {
                    "display_name": PII[0], "email_address": PII[1],
                    "phone_number": PII[4],
                    "address": {"country": "JP", "address_line_1": PII[2],
                                "postal_code": PII[3]},
                },
            }}],
        }
        self.calls = []

    def square_get(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url))
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 10)
        self.assertEqual(request.headers["Authorization"], "Bearer " + API_KEY)
        if request.full_url == ENDPOINT + "/payments/" + PAYMENT:
            return FakeResponse({"payment": self.payment})
        if request.full_url == ENDPOINT + "/orders/" + SQUARE_ORDER:
            return FakeResponse({"order": self.order})
        self.fail("Unexpected Square read")

    def test_pii_is_ephemeral_and_never_in_operator_or_review_outputs(self):
        self.ledger.register_checkout(
            order_id=ORDER, square_order_id=SQUARE_ORDER,
            location_id=LOCATION, cart={self.sku: 1},
        )
        evidence = verify_paid_live_shipment(
            payment_id=PAYMENT, square_order_id=SQUARE_ORDER,
            location_id=LOCATION, amount_yen=self.amount,
            api_key=API_KEY, opener=self.square_get,
        )
        self.assertEqual(evidence["recipient_email"], PII[1])
        self.assertEqual(set(evidence), {
            "live_square_verified", "payment_id", "square_order_id",
            "location_id", "amount_yen", "recipient_email",
        })
        result = self.ledger.reconcile_payment(
            order_id=ORDER, payment_id=PAYMENT, api_key=API_KEY,
            opener=self.square_get, audit_actor_id="operator_synthetic",
        )
        self.assertEqual(result, {"state": "paid_verified", "new_transition": True})

        snapshot = read_order_management_snapshot(ledger=self.ledger)
        self.assertEqual(snapshot["count"], 1)
        html = render_order_overview_preview(self.ledger)
        draft = preview_paid_order_confirmation(
            ledger=self.ledger, order_id=ORDER, api_key=API_KEY,
            review_secret=REVIEW_KEY, opener=self.square_get,
        )
        self.assertEqual(draft["masked_recipient"], "s***@e***")
        approval = LiveNoticeApproval(self.ledger)
        approved = approval.approve(
            order_id=ORDER, reviewed_fingerprint=draft["review_fingerprint"],
            authorized=True, confirmed=True, api_key=API_KEY,
            review_secret=REVIEW_KEY, opener=self.square_get, now=1000,
        )
        checked = approval.check(
            order_id=ORDER, api_key=API_KEY, review_secret=REVIEW_KEY,
            opener=self.square_get, now=1001,
        )
        self.assertTrue(approved["approved"])
        self.assertEqual(checked["masked_recipient"], "s***@e***")

        outputs = json.dumps(
            {"result": result, "snapshot": snapshot,
             "html": html, "draft": draft, "approved": approved,
             "checked": checked}, ensure_ascii=False,
        )
        for private_value in PII + (API_KEY, REVIEW_KEY):
            self.assertNotIn(private_value, outputs)
        self.assertNotIn("recipient_email", str(snapshot))
        self.assertNotIn("recipient_email", html)
        self.assertNotIn("recipient_email", json.dumps(draft))
        self.assertNotIn("to", checked)
        self.assertNotIn("body", checked)

        database = self.path.read_bytes()
        for private_value in PII + (API_KEY, REVIEW_KEY):
            self.assertNotIn(private_value.encode("utf-8"), database)
        self.assertGreaterEqual(len(self.calls), 8)

    def test_server_order_routes_authenticate_before_reading_shop_data(self):
        source = (Path(__file__).resolve().parents[1] /
                  "app/backend/server.py").read_text(encoding="utf-8")
        list_route = source.split("if path=='/api/operator/shop-orders':", 1)[1]
        self.assertLess(list_route.index("self.require(['operator'])"),
                        list_route.index("LiveOrderLedger"))
        audit_route = source.split("if path=='/api/operator/shop-orders/audit':", 1)[1]
        self.assertLess(audit_route.index("self.require(['operator'])"),
                        audit_route.index("LiveOrderLedger"))


if __name__ == "__main__":
    unittest.main()
