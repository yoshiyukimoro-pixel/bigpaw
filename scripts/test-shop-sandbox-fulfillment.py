"""Offline regression of Sandbox-only fulfillment, refunds and all 35 SKUs."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import unittest

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.sandbox_fulfillment import SandboxFulfillmentOps

LOCATION = "SQUARE_SANDBOX_TEST01"
KEY = "fake_signature_not_a_secret"
URL = "https://sandbox.invalid/webhook"


class FakeResponse:
    status = 200
    def __init__(self, payload):
        self.data = json.dumps(payload).encode()
    def __enter__(self):
        return self
    def __exit__(self, *args):
        return None
    def read(self, size):
        return self.data


class TestFulfillment(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.store = SandboxOrderStore(Path(self.temp.name) / "sandbox.sqlite")
        self.ops = SandboxFulfillmentOps(self.store)
        self.catalog = load_sale_catalog()
        self.order_n = 0

    def make_paid_order(self, cart):
        self.order_n += 1
        order_id = "FOOD" + str(self.order_n).zfill(32)
        payment_id = "PAYMENTTEST" + str(self.order_n).zfill(10)
        square_id = "SQUAREORDERTEST" + str(self.order_n).zfill(10)
        _, amount = self.store.add_pending_order(
            order_id=order_id, cart=cart, verified_prices=self.catalog,
            shipping_yen=0, location_id=LOCATION,
        )
        self.store.save_link(order_id, {
            "url": "https://sandbox.square.link/u/mock",
            "square_order_id": square_id, "square_link_id": "LINKTEST" + str(self.order_n).zfill(10),
        })
        payment = {
            "id": payment_id, "status": "COMPLETED", "order_id": square_id,
            "location_id": LOCATION,
            "amount_money": {"amount": amount, "currency": "JPY"},
        }
        event = {
            "event_id": "event" + str(self.order_n), "type": "payment.updated",
            "data": {"object": {"payment": payment}},
        }
        raw = json.dumps(event).encode()
        sig = base64.b64encode(hmac.new(
            KEY.encode(), URL.encode() + raw, hashlib.sha256,
        ).digest()).decode()
        self.assertEqual(self.store.accept_webhook(
            raw_body=raw, signature_header=sig, signature_key=KEY,
            notification_url=URL, payment_lookup=lambda pid: payment,
        ), "paid")
        self.assertEqual(self.store.paid_order_snapshot(order_id)["square_payment_id"], payment_id)
        self.assertEqual(self.store.paid_order_snapshot(order_id)["cart"], cart)
        return order_id, payment, amount

    @staticmethod
    def square_order_opener(square_id, *, complete=True):
        def fake(req, timeout):
            assert req.get_method() == "GET"
            assert req.full_url == (
                "https://connect.squareupsandbox.com/v2/orders/" + square_id
            )
            recipient = {
                "display_name": "PRIVATE RECIPIENT",
                "address": {
                    "country": "JP" if complete else "US",
                    "postal_code": "100-0001",
                    "address_line_1": "PRIVATE ADDRESS",
                },
            }
            return FakeResponse({
                "order": {
                    "id": square_id,
                    "fulfillments": [{
                        "type": "SHIPMENT",
                        "shipment_details": {"recipient": recipient},
                    }],
                },
            })
        return fake

    @staticmethod
    def payment_opener(payment):
        def fake(req, timeout):
            assert req.full_url == (
                "https://connect.squareupsandbox.com/v2/payments/" + payment["id"]
            )
            return FakeResponse({"payment": payment})
        return fake

    def assess(self, order_id, payment, *, complete=True):
        return self.ops.assess_paid_order(
            order_id, token="FAKE_TEST_TOKEN",
            opener=self.square_order_opener(payment["order_id"], complete=complete),
        )

    def test_paid_shipping_and_stock_gate_with_idempotency(self):
        order_id, payment, _ = self.make_paid_order({"A02": 2})
        self.assertEqual(self.ops.state(order_id), "not_assessed")
        self.assertEqual(self.assess(order_id, payment, complete=False), "address_review")
        self.assertEqual(self.assess(order_id, payment), "stock_review")
        self.assertEqual(self.ops.stock("A02"), 0)
        with self.assertRaises(ValueError):
            self.ops.mark_shipped(order_id)
        self.ops.set_stock("A02", 2)
        self.assertEqual(self.assess(order_id, payment), "ready_to_pack")
        self.assertEqual(self.ops.stock("A02"), 0)
        self.assertEqual(self.assess(order_id, payment), "ready_to_pack")
        self.assertEqual(self.ops.stock("A02"), 0)
        self.assertEqual(self.ops.mark_shipped(order_id), "shipped")
        self.assertEqual(self.ops.mark_shipped(order_id), "shipped")
        with self.assertRaises(ValueError):
            self.ops.request_refund_review(order_id)
        events = self.ops.operator_queue()
        self.assertEqual(
            {e["event_type"] for e in events},
            {"address_review", "stock_review", "ready_to_pack", "shipped"},
        )
        self.assertNotIn("PRIVATE", json.dumps(events))

    def test_full_refund_only_after_square_confirmation(self):
        order_id, payment, total = self.make_paid_order({"Z01": 1, "A02": 2})
        self.ops.set_stock("Z01", 3)
        self.ops.set_stock("A02", 4)
        self.assertEqual(self.assess(order_id, payment), "ready_to_pack")
        self.assertEqual(self.ops.stock("Z01"), 2)
        self.assertEqual(self.ops.stock("A02"), 2)
        self.assertEqual(self.ops.request_refund_review(order_id), "refund_review")
        self.assertEqual(self.ops.request_refund_review(order_id), "refund_review")
        with self.assertRaises(ValueError):
            self.ops.mark_shipped(order_id)
        for refund in (
            {},
            {"amount": total - 1, "currency": "JPY"},
            {"amount": total, "currency": "USD"},
            {"amount": total, "currency": "JPY"},
        ):
            candidate = {**payment, "refunded_money": refund}
            if refund == {"amount": total, "currency": "JPY"}:
                candidate["location_id"] = "SPOOFED_LOCATION"
            with self.subTest(refund=refund), self.assertRaises(ValueError):
                self.ops.reconcile_full_refund(
                    order_id, token="TEST", opener=self.payment_opener(candidate),
                )
        self.assertEqual(self.ops.stock("Z01"), 2)
        complete = {**payment, "refunded_money": {
            "amount": total, "currency": "JPY",
        }}
        self.assertEqual(
            self.ops.reconcile_full_refund(
                order_id, token="TEST", opener=self.payment_opener(complete),
            ),
            "refunded",
        )
        self.assertEqual(self.ops.stock("Z01"), 3)
        self.assertEqual(self.ops.stock("A02"), 4)
        self.assertEqual(
            self.ops.reconcile_full_refund(
                order_id, token="TEST", opener=self.payment_opener(complete),
            ),
            "refunded",
        )
        self.assertEqual(self.ops.stock("Z01"), 3)
        self.assertEqual(
            [e["event_type"] for e in self.ops.operator_queue()].count("refunded"), 1,
        )

    def test_cannot_reserve_unpaid_or_invalid_stock(self):
        order_id = "FOOD" + "9" * 32
        self.store.add_pending_order(
            order_id=order_id, cart={"A02": 1}, verified_prices=self.catalog,
            shipping_yen=0, location_id=LOCATION,
        )
        self.assertIsNone(self.store.paid_order_snapshot(order_id))
        with self.assertRaises(ValueError):
            self.ops.assess_paid_order(order_id, token="FAKE", opener=lambda *_a, **_k: None)
        with self.assertRaises(ValueError):
            self.ops.set_stock("INVALID", 1)
        for qty in (-1, True, 1.2, 100001):
            with self.subTest(qty=qty), self.assertRaises(ValueError):
                self.ops.set_stock("A02", qty)

    def test_entire_35_product_pricebook_in_inventory(self):
        self.assertEqual(len(self.catalog), 35)
        # Exercise a valid paid order and domestic shipping check for every
        # SKU, not just a sample, with no real API network calls.
        for sku in sorted(self.catalog):
            self.ops.set_stock(sku, 2)
            order_id, payment, _ = self.make_paid_order({sku: 1})
            self.assertEqual(self.assess(order_id, payment), "ready_to_pack")
            self.assertEqual(self.ops.stock(sku), 1)
        self.assertEqual(
            len([e for e in self.ops.operator_queue()
                 if e["event_type"] == "ready_to_pack"]), 35,
        )


if __name__ == "__main__":
    unittest.main()
