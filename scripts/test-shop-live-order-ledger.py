"""Offline integration tests: future live ledger + FAKE Square GET responses.

No real production credentials, real Square network, customer data, emails,
refunds, or live checkout. The production application does not import ledger.
"""
from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.square_live_readonly import (
    ENDPOINT, LiveSquareNotVerified,
)

ORDER_ID = "FOOD" + "a" * 32
SECOND_ID = "FOOD" + "b" * 32
SQUARE_ORDER = "SYNTHETICORDER123456"
LOCATION = "SYNTHETICLOCATION123456"
PAYMENT = "SYNTHETICPAYMENT123456"
FAKE_KEY = "test-synthetic-production-key-NOT-VALID"


class FakeResponse:
    status = 200
    def __init__(self, value):
        self.data = json.dumps(value).encode("utf-8")
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, n):
        return self.data[:n]


class LiveLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = Path(self.tmp.name) / "never-public.sqlite3"
        self.ledger = LiveOrderLedger(self.path)
        catalog = load_sale_catalog()
        self.sku, self.product = next(iter(catalog.items()))
        self.cart = {self.sku: 1}
        self.price = self.product.sale_price_yen
        self.calls = []
        self.payment = {
            "id": PAYMENT,
            "order_id": SQUARE_ORDER,
            "location_id": LOCATION,
            "status": "COMPLETED",
            "amount_money": {"amount": self.price, "currency": "JPY"},
            "refunded_money": {"amount": 0, "currency": "JPY"},
        }
        self.square_order = {
            "id": SQUARE_ORDER, "location_id": LOCATION, "state": "OPEN",
            "total_money": {"amount": self.price, "currency": "JPY"},
            "fulfillments": [{
                "type": "SHIPMENT",
                "shipment_details": {"recipient": {
                    "display_name": "FAKE BUYER",
                    "email_address": "synthetic-buyer@example.invalid",
                    "address": {"country": "JP", "address_line_1": "FAKE ONLY",
                                "postal_code": "000-0000"},
                }}
            }],
        }

    def register(self, **overrides):
        arguments = dict(order_id=ORDER_ID, square_order_id=SQUARE_ORDER,
                         location_id=LOCATION, cart=self.cart)
        return self.ledger.register_checkout(**{**arguments, **overrides})

    def fake_square(self, req, timeout):
        self.calls.append((req.get_method(), req.full_url))
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(timeout, 10)
        self.assertEqual(req.headers["Authorization"], "Bearer " + FAKE_KEY)
        if req.full_url == ENDPOINT + "/payments/" + PAYMENT:
            return FakeResponse({"payment": self.payment})
        if req.full_url == ENDPOINT + "/orders/" + SQUARE_ORDER:
            return FakeResponse({"order": self.square_order})
        self.fail("Unexpected external request")

    def pay(self, **overrides):
        args = dict(order_id=ORDER_ID, payment_id=PAYMENT, api_key=FAKE_KEY,
                    opener=self.fake_square)
        return self.ledger.reconcile_payment(**{**args, **overrides})

    def test_immutable_checkout_and_duplicate_are_safe(self):
        self.assertEqual(self.ledger.status(ORDER_ID), {"state": "not_found"})
        created = self.register()
        self.assertEqual(created["amount_yen"], self.price)
        self.assertTrue(created["new_record"])
        self.assertFalse(self.register()["new_record"])
        self.assertEqual(self.ledger.status(ORDER_ID),
                         {"state": "checkout_recorded", "amount_yen": self.price})
        for changed in (
            {"square_order_id": "SYNTHETICORDERDIFFERENT"},
            {"location_id": "SYNTHETICLOCATIONDIFFERENT"},
            {"cart": {self.sku: 2}},
        ):
            with self.subTest(changed=changed):
                with self.assertRaises(LiveOrderBlocked):
                    self.register(**changed)
        # One Square order cannot be attached to a second order.
        with self.assertRaises(LiveOrderBlocked):
            self.register(order_id=SECOND_ID)
        self.assertEqual(self.ledger.status(SECOND_ID), {"state": "not_found"})

    def test_invalid_inputs_cannot_create_record_or_network(self):
        for bad in (
            {"order_id": "external"},
            {"square_order_id": ""},
            {"location_id": "INVALID!"},
            {"cart": {}},
            {"cart": {"UNKNOWN": 1}},
            {"cart": {self.sku: True}},
            {"cart": {self.sku: 11}},
            {"cart": {self.sku: -1}},
        ):
            with self.subTest(bad=bad):
                with self.assertRaises(LiveOrderBlocked):
                    self.register(**bad)
        self.assertFalse(self.path.exists())
        with self.assertRaises(LiveOrderBlocked):
            self.pay()
        self.assertEqual(self.calls, [])

    def test_real_verifier_with_fake_square_payment_and_idempotency(self):
        self.register()
        result = self.pay()
        self.assertEqual(result, {"state": "paid_verified", "new_transition": True})
        self.assertEqual(self.calls, [
            ("GET", ENDPOINT + "/payments/" + PAYMENT),
            ("GET", ENDPOINT + "/orders/" + SQUARE_ORDER),
        ])
        self.assertEqual(self.ledger.status(ORDER_ID),
                         {"state": "paid_verified", "amount_yen": self.price})
        with self.assertRaises(LiveOrderBlocked):
            self.register()  # Never restart a completed checkout.
        self.calls.clear()
        self.assertEqual(self.pay(),
                         {"state": "paid_verified", "new_transition": False})
        self.assertEqual(self.calls, [
            ("GET", ENDPOINT + "/payments/" + PAYMENT),
            ("GET", ENDPOINT + "/orders/" + SQUARE_ORDER),
        ], "replayed paid event requires fresh independent Square GET")
        self.payment["refunded_money"] = {"amount": 1, "currency": "JPY"}
        with self.assertRaises(LiveSquareNotVerified):
            self.pay()
        self.assertEqual(self.ledger.status(ORDER_ID)["state"], "paid_verified")
        self.payment["refunded_money"] = {"amount": 0, "currency": "JPY"}
        with self.assertRaises(LiveOrderBlocked):
            self.pay(payment_id="ANOTHERFAKEPAYMENT12")
        raw = self.path.read_bytes()
        for forbidden in ("FAKE BUYER", "FAKE ONLY", "synthetic-buyer@example.invalid",
                          FAKE_KEY, "Authorization", "card_details"):
            self.assertNotIn(forbidden.encode("utf-8"), raw)
        self.assertNotIn("recipient_email", str(result))

    def test_operator_reconciliation_audits_atomically_without_payment_reference(self):
        self.register()
        result = self.pay(audit_actor_id="operator_123")
        self.assertTrue(result["new_transition"])
        events = self.ledger.operator_audit_events()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["order_id"], ORDER_ID)
        self.assertEqual(events[0]["actor_id"], "operator_123")
        self.assertEqual(events[0]["action"], "payment_reconciled")
        self.assertEqual(events[0]["outcome"], "newly_paid")
        self.assertNotIn("payment_id", events[0])
        self.calls.clear()
        self.pay(audit_actor_id="operator_123")
        events = self.ledger.operator_audit_events()
        self.assertEqual(len(events), 2)
        self.assertEqual(events[0]["outcome"], "already_paid")
        self.assertEqual(len(self.calls), 2)
        self.ledger.record_operator_reconciliation_failure(
            order_id=ORDER_ID, actor_id="operator_123")
        events = self.ledger.operator_audit_events()
        self.assertEqual(events[0]["outcome"], "verification_failed")
        self.assertNotIn("payment_id", events[0])

    def test_payment_mismatch_refund_or_bad_shipping_never_marks_paid(self):
        self.register()
        original_payment = deepcopy(self.payment)
        original_order = deepcopy(self.square_order)
        cases = [
            ("wrong amount", {"amount_money": {"amount": self.price + 1,
                                               "currency": "JPY"}}, {}),
            ("wrong location", {"location_id": "WRONGLOCATION123456"}, {}),
            ("pending", {"status": "PENDING"}, {}),
            ("partial refund", {"refunded_money": {"amount": 1,
                                                   "currency": "JPY"}}, {}),
            ("missing shipment", {}, {"fulfillments": []}),
            ("wrong currency", {}, {"total_money": {"amount": self.price,
                                                    "currency": "USD"}}),
        ]
        for name, pay_change, order_change in cases:
            with self.subTest(name=name):
                self.payment = {**original_payment, **pay_change}
                self.square_order = {**original_order, **order_change}
                with self.assertRaises(LiveSquareNotVerified):
                    self.pay()
                self.assertEqual(self.ledger.status(ORDER_ID)["state"],
                                 "checkout_recorded")
        self.payment = original_payment
        self.square_order = original_order
        self.assertTrue(self.pay()["new_transition"])

    def test_payment_evidence_must_match_private_journal(self):
        self.register()
        def forged(**kwargs):
            return {"live_square_verified": True,
                    "payment_id": PAYMENT,
                    "square_order_id": "OTHERFAKEORDER12345",
                    "location_id": LOCATION, "amount_yen": self.price}
        with self.assertRaises(LiveOrderBlocked):
            self.pay(verifier=forged)
        self.assertEqual(self.ledger.status(ORDER_ID)["state"],
                         "checkout_recorded")
        self.assertEqual(self.calls, [])

    def test_reused_payment_for_different_order_is_blocked(self):
        self.register()
        self.assertTrue(self.pay()["new_transition"])
        # A fresh distinct Square order with same payment ID is never accepted.
        second_square = "SECONDFAKEORDER12345"
        self.register(order_id=SECOND_ID, square_order_id=second_square)
        def forged_second(**kwargs):
            return {"live_square_verified": True, "payment_id": PAYMENT,
                    "square_order_id": second_square, "location_id": LOCATION,
                    "amount_yen": self.price}
        with self.assertRaises(LiveOrderBlocked):
            self.pay(order_id=SECOND_ID, verifier=forged_second)
        self.assertEqual(self.ledger.status(SECOND_ID)["state"],
                         "checkout_recorded")


if __name__ == "__main__":
    unittest.main()
