"""Offline-only signed PRODUCTION-event-to-paid-journal integration tests.

Synthetic raw HMAC signatures and in-memory fake Square GET responses ONLY.
Never calls actual Square, Resend, Railway, buyers, or suppliers.
"""
import base64
from copy import deepcopy
import hashlib
import hmac
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from shop_payments.live_payment_intake import record_verified_live_payment_event
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.square_live_readonly import ENDPOINT, LiveSquareNotVerified

ORDER_ID = "FOOD" + "d" * 32
SQUARE_ORDER = "SIGNEDFAKESQUAREORDER1234"
LOCATION = "SIGNEDFAKELOCATION1234"
PAYMENT_ID = "SIGNEDFAKEPAYMENT12345"
URL = "https://example.invalid/api/shop/live/webhook"
SIGN_KEY = "synthetic-square-webhook-signing-key-NOT-VALID"
API_KEY = "synthetic-square-production-token-NOT-VALID"


class Response:
    status = 200

    def __init__(self, content):
        self.raw = json.dumps(content).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, n):
        return self.raw[:n]


class SignedSquarePaymentIntakeTests(unittest.TestCase):
    def setUp(self):
        temp = TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.database = Path(temp.name) / "private-never-live.sqlite3"
        self.ledger = LiveOrderLedger(self.database)
        self.sku, item = next(iter(load_sale_catalog().items()))
        self.total = item.sale_price_yen
        self.ledger.register_checkout(
            order_id=ORDER_ID, square_order_id=SQUARE_ORDER,
            location_id=LOCATION, cart={self.sku: 1},
        )
        self.calls = []
        self.event = {
            "event_id": "example-event-123456789",
            "type": "payment.updated",
            "data": {
                "type": "payment",
                "object": {"payment": {
                    "id": PAYMENT_ID, "order_id": SQUARE_ORDER,
                    "location_id": LOCATION, "status": "COMPLETED",
                    "amount_money": {"amount": self.total, "currency": "JPY"},
                }},
            },
        }
        self.payment = {
            "id": PAYMENT_ID, "order_id": SQUARE_ORDER,
            "location_id": LOCATION, "status": "COMPLETED",
            "amount_money": {"amount": self.total, "currency": "JPY"},
            "refunded_money": {"amount": 0, "currency": "JPY"},
        }
        self.square_order = {
            "id": SQUARE_ORDER, "location_id": LOCATION, "state": "OPEN",
            "total_money": {"amount": self.total, "currency": "JPY"},
            "fulfillments": [{"type": "SHIPMENT",
                "shipment_details": {"recipient": {
                    "display_name": "SYNTHETIC BUYER",
                    "email_address": "fake-buyer@example.invalid",
                    "address": {"country": "JP", "address_line_1": "FAKE ADDRESS",
                                "postal_code": "000-0000"},
                }}}],
        }

    def fake_square(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url))
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 10)
        self.assertEqual(request.headers["Authorization"], "Bearer " + API_KEY)
        if request.full_url == ENDPOINT + "/payments/" + PAYMENT_ID:
            return Response({"payment": self.payment})
        if request.full_url == ENDPOINT + "/orders/" + SQUARE_ORDER:
            return Response({"order": self.square_order})
        self.fail("Unexpected Square endpoint")

    @staticmethod
    def signed(event, *, url=URL, secret=SIGN_KEY):
        raw = json.dumps(event, separators=(",", ":"), ensure_ascii=False).encode()
        signature = base64.b64encode(
            hmac.new(secret.encode(), url.encode() + raw, hashlib.sha256).digest()
        ).decode()
        return raw, signature

    def receive(self, *, event=None, signature=None, raw=None, url=URL, **changes):
        generated, correct_signature = self.signed(
            self.event if event is None else event
        )
        return record_verified_live_payment_event(
            ledger=self.ledger, raw_body=generated if raw is None else raw,
            signature_header=correct_signature if signature is None else signature,
            signature_key=SIGN_KEY, notification_url=url, api_key=API_KEY,
            opener=self.fake_square, **changes,
        )

    def test_signed_verified_paid_transition_and_duplicate_delivery(self):
        result = self.receive()
        self.assertEqual(result, {"state": "paid_verified", "new_transition": True})
        self.assertEqual(self.calls, [
            ("GET", ENDPOINT + "/payments/" + PAYMENT_ID),
            ("GET", ENDPOINT + "/orders/" + SQUARE_ORDER),
        ])
        self.assertEqual(self.ledger.status(ORDER_ID)["state"], "paid_verified")
        before = len(self.calls)
        self.assertEqual(
            self.receive(),
            {"state": "already_recorded", "new_transition": False},
        )
        self.assertEqual(len(self.calls), before + 2,
                         "replayed webhook must re-check current Square payment/order")
        self.payment["refunded_money"] = {"amount": 1, "currency": "JPY"}
        with self.assertRaises(LiveSquareNotVerified):
            self.receive()
        self.assertEqual(self.ledger.status(ORDER_ID)["state"], "paid_verified")
        self.payment["refunded_money"] = {"amount": 0, "currency": "JPY"}
        stored = self.database.read_bytes()
        for value in ("SYNTHETIC BUYER", "FAKE ADDRESS",
                      "fake-buyer@example.invalid", API_KEY, SIGN_KEY):
            self.assertNotIn(value.encode(), stored)
        self.assertNotIn("customer", str(result).lower())

    def test_invalid_signature_or_url_fails_before_read_or_state_change(self):
        for inputs in (
            {"signature": "untrusted"},
            {"url": "https://changed.example.invalid/api/shop/live/webhook"},
            {"raw": self.signed(self.event)[0] + b" "},
        ):
            with self.subTest(inputs=inputs):
                with self.assertRaises(ValueError):
                    self.receive(**inputs)
                self.assertEqual(self.calls, [])
                self.assertEqual(self.ledger.status(ORDER_ID)["state"],
                                 "checkout_recorded")

    def test_unrelated_and_pending_signed_events_do_not_charge_or_mark_paid(self):
        unrelated = deepcopy(self.event)
        unrelated["type"] = "refund.updated"
        self.assertEqual(self.receive(event=unrelated),
                         {"state": "ignored", "new_transition": False})
        pending = deepcopy(self.event)
        pending["data"]["object"]["payment"]["status"] = "PENDING"
        self.assertEqual(self.receive(event=pending),
                         {"state": "awaiting_square", "new_transition": False})
        self.assertEqual(self.calls, [])
        self.assertEqual(self.ledger.status(ORDER_ID)["state"],
                         "checkout_recorded")

    def test_unknown_square_order_location_or_amount_never_pays(self):
        for field, value in (
            ("order_id", "UNREGISTEREDSQUAREORDER1234"),
            ("location_id", "WRONGLOCATION1234"),
            ("amount_money", {"amount": self.total + 1, "currency": "JPY"}),
        ):
            event = deepcopy(self.event)
            event["data"]["object"]["payment"][field] = value
            with self.subTest(field=field), self.assertRaises(LiveOrderBlocked):
                self.receive(event=event)
            self.assertEqual(self.calls, [])
            self.assertEqual(self.ledger.status(ORDER_ID)["state"],
                             "checkout_recorded")

    def test_trusted_square_reverification_fails_on_refund_or_mismatch(self):
        original_payment, original_order = deepcopy(self.payment), deepcopy(self.square_order)
        cases = (
            ({"refunded_money": {"amount": 1, "currency": "JPY"}}, {}),
            ({"status": "PENDING"}, {}),
            ({"location_id": "WRONGLOCATION1234"}, {}),
            ({}, {"fulfillments": []}),
            ({}, {"total_money": {"amount": self.total + 1, "currency": "JPY"}}),
        )
        for payment_changes, order_changes in cases:
            with self.subTest(changes=(payment_changes, order_changes)):
                self.payment = {**original_payment, **payment_changes}
                self.square_order = {**original_order, **order_changes}
                with self.assertRaises(LiveSquareNotVerified):
                    self.receive()
                self.assertEqual(self.ledger.status(ORDER_ID)["state"],
                                 "checkout_recorded")
        self.payment, self.square_order = original_payment, original_order
        self.assertTrue(self.receive()["new_transition"])

    def test_missing_or_malformed_signed_payment_fields_are_rejected(self):
        for key, value in (
            ("id", ""), ("order_id", None),
            ("amount_money", {"amount": True, "currency": "JPY"}),
            ("amount_money", {"amount": self.total, "currency": "USD"}),
        ):
            event = deepcopy(self.event)
            event["data"]["object"]["payment"][key] = value
            with self.subTest(field=key), self.assertRaises(LiveOrderBlocked):
                self.receive(event=event)
        event = deepcopy(self.event)
        event["event_id"] = "bad"
        with self.assertRaises(LiveOrderBlocked):
            self.receive(event=event)
        self.assertEqual(self.calls, [])

    def test_no_existing_private_checkout_must_not_create_any(self):
        fake = deepcopy(self.event)
        fake["data"]["object"]["payment"]["order_id"] = "UNKNOWNFAKESQUAREORDER1234"
        with self.assertRaises(LiveOrderBlocked):
            self.receive(event=fake)
        self.assertEqual(self.ledger.status(ORDER_ID)["state"], "checkout_recorded")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
