"""Offline regression for verified Sandbox shipment and tracking records."""
import base64
import hashlib
import hmac
import json
from pathlib import Path
import tempfile
import unittest

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.sandbox_procurement import SandboxProcurementOps
from shop_payments.sandbox_tracking import SandboxTrackingJournal

ORDER = "FOOD" + "a" * 32
SQUARE_ORDER = "SQUAREORDERTEST1234"
PAYMENT = "SQUAREPAYMENTTEST1234"
LOCATION = "SANDBOXLOCATION1234"
PII = ("PRIVATE NAME", "PRIVATE STREET", "100-0001", "090-0000-0000")


class Response:
    status = 200

    def __init__(self, value):
        self.data = json.dumps(value).encode()

    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self, size): return self.data


def shipping_opener(req, timeout):
    assert req.get_method() == "GET"
    if req.full_url == "https://connect.squareupsandbox.com/v2/payments/" + PAYMENT:
        return Response({"payment": {
            "id": PAYMENT, "order_id": SQUARE_ORDER, "location_id": LOCATION,
            "status": "COMPLETED", "amount_money": {
                "amount": load_sale_catalog()["A02"].sale_price_yen, "currency": "JPY"},
        }})
    assert req.full_url == (
        "https://connect.squareupsandbox.com/v2/orders/" + SQUARE_ORDER
    )
    return Response({"order": {"id": SQUARE_ORDER,
        "location_id": LOCATION, "state": "OPEN",
        "total_money": {
            "amount": load_sale_catalog()["A02"].sale_price_yen, "currency": "JPY"},
        "fulfillments": [{
        "type": "SHIPMENT", "shipment_details": {"recipient": {
            "display_name": PII[0],
            "address": {"country": "JP", "address_line_1": PII[1],
                        "administrative_district_level_1": "東京都",
                        "locality": "千代田区",
                        "postal_code": PII[2]},
            "phone_number": PII[3],
        }},
    }]}})


class TrackingTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db = Path(tmp.name) / "sandbox.sqlite3"
        self.store = SandboxOrderStore(self.db)
        self.procurement = SandboxProcurementOps(self.store)
        self.tracking = SandboxTrackingJournal(self.store)

    def create_paid_order(self):
        _, amount = self.store.add_pending_order(
            order_id=ORDER, cart={"A02": 1},
            verified_prices=load_sale_catalog(), shipping_yen=0,
            location_id=LOCATION,
        )
        payment = {
            "id": PAYMENT, "status": "COMPLETED", "order_id": SQUARE_ORDER,
            "location_id": LOCATION,
            "amount_money": {"amount": amount, "currency": "JPY"},
        }
        self.store.save_link(ORDER, {
            "url": "https://sandbox.square.link/u/mock",
            "square_order_id": SQUARE_ORDER, "square_link_id": "LINKTEST12345",
        })
        event = {"event_id": "tracking-event-1", "type": "payment.updated",
                 "data": {"object": {"payment": payment}}}
        raw = json.dumps(event).encode()
        key, url = "fake-test-key", "https://sandbox.invalid/webhook"
        signature = base64.b64encode(hmac.new(
            key.encode(), url.encode() + raw, hashlib.sha256,
        ).digest()).decode()
        self.assertEqual(self.store.accept_webhook(
            raw_body=raw, signature_header=signature,
            signature_key=key, notification_url=url,
            payment_lookup=lambda _payment_id: payment,
        ), "paid")

    def mark_shipped(self):
        self.procurement.transition(ORDER, "supplier_ordered")
        self.procurement.transition(ORDER, "received_at_shop")
        self.procurement.transition(
            ORDER, "shipped", token="FAKE_SANDBOX_TOKEN",
            opener=shipping_opener,
        )

    def test_tracking_requires_paid_order_and_verified_shipped_stage(self):
        with self.assertRaises(ValueError):
            self.tracking.record_once(ORDER, "yamato", "123456789012")
        self.create_paid_order()
        with self.assertRaises(ValueError):
            self.tracking.record_once(ORDER, "yamato", "123456789012")
        self.mark_shipped()
        self.assertTrue(self.tracking.record_once(ORDER, "yamato", "123456789012"))

    def test_tracking_is_idempotent_and_cannot_be_silently_overwritten(self):
        self.create_paid_order()
        self.mark_shipped()
        self.assertTrue(self.tracking.record_once(ORDER, "sagawa", "AbC123456789"))
        self.assertFalse(self.tracking.record_once(ORDER, "sagawa", "AbC123456789"))
        with self.assertRaises(ValueError):
            self.tracking.record_once(ORDER, "yamato", "DIFFERENT1234")
        with self.assertRaises(ValueError):
            self.tracking.record_once(ORDER, "sagawa", "DIFFERENT1234")
        self.assertEqual(self.tracking.read(ORDER)["tracking_number"], "AbC123456789")

    def test_carrier_and_reference_are_validated_and_pii_is_not_saved(self):
        self.create_paid_order()
        self.mark_shipped()
        for carrier, reference in (("unknown", "123456789012"),
                                   ("yamato", "short"),
                                   ("yamato", "-123456789"),
                                   ("yamato", "123456789-"),
                                   ("yamato", "1234 56789012")):
            with self.subTest(carrier=carrier, reference=reference):
                with self.assertRaises(ValueError):
                    self.tracking.record_once(ORDER, carrier, reference)
        self.tracking.record_once(ORDER, "japan_post", "123456789012")
        raw = self.db.read_bytes()
        for value in PII:
            self.assertNotIn(value.encode(), raw)
        self.assertNotIn(b"FAKE_SANDBOX_TOKEN", raw)


if __name__ == "__main__":
    unittest.main()
