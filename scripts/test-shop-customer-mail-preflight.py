"""Offline tests for ephemeral customer email delivery preparation.

No Square production calls, no Resend calls, no actual buyer addresses.
Run on GitHub Actions with deterministic fake Square Sandbox responses.
"""
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from shop_payments.customer_mail_preflight import prepare_customer_email
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore, SquareSandboxError
from shop_payments.sandbox_customer_dispatch import SandboxDryRunOutbox
from shop_payments.sandbox_customer_review import SandboxCustomerReview
from shop_payments.sandbox_notifications import SandboxNotificationDrafts

ORDER = "FOOD" + "b" * 32
SQUARE_ORDER = "SQUAREORDERTEST12345"
LOC = "SQUARELOCATIONTEST12345"
TOKEN = "THIS_IS_A_FAKE_SANDBOX_TOKEN_FOR_TESTS"
SAFE_EMAIL = "test-buyer@example.invalid"


class Response:
    status = 200

    def __init__(self, value):
        self.raw = json.dumps({"order": value}).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.raw[:size]


class CustomerMailPreflightTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.file = Path(tmp.name) / "sandbox.sqlite3"
        self.store = SandboxOrderStore(self.file)
        self.store.add_pending_order(
            order_id=ORDER, cart={"A02": 1},
            verified_prices=load_sale_catalog(),
            shipping_yen=0, location_id=LOC,
        )
        with sqlite3.connect(self.file) as db:
            db.execute(
                "UPDATE orders SET state='paid',paid_at=1761780000,"
                "square_payment_id='SQUAREPAYMENTTEST12345',square_order_id=? "
                "WHERE order_id=?", (SQUARE_ORDER, ORDER)
            )
        self.assertEqual(SandboxNotificationDrafts(self.store).sync_paid(ORDER), 3)
        self.email = SAFE_EMAIL
        self.outbound = []
        self.square_reads = 0
        self.override_order = None

    def square_get(self, request, timeout):
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(
            request.full_url,
            "https://connect.squareupsandbox.com/v2/orders/" + SQUARE_ORDER
        )
        self.assertEqual(timeout, 10)
        self.square_reads += 1
        return Response(self.override_order or {
            "id": SQUARE_ORDER,
            "fulfillments": [{
                "type": "SHIPMENT",
                "shipment_details": {
                    "recipient": {"email_address": self.email}
                }
            }]
        })

    def prep(self):
        return prepare_customer_email(
            self.store, ORDER, "customer_order_confirmed",
            sandbox_token=TOKEN, opener=self.square_get,
        )

    def approve(self):
        return SandboxCustomerReview(self.store).mark_reviewed(
            ORDER, "customer_order_confirmed",
            token=TOKEN, opener=self.square_get,
        )

    def simulate(self):
        return SandboxDryRunOutbox(self.store).simulate_once(
            ORDER, "customer_order_confirmed",
            token=TOKEN, opener=self.square_get,
        )

    def test_requires_order_review_and_no_send_simulation(self):
        with self.assertRaisesRegex(ValueError, "Fresh operator approval"):
            self.prep()
        self.assertTrue(self.approve())
        with self.assertRaisesRegex(ValueError, "No no-send simulation"):
            self.prep()
        self.assertTrue(self.simulate())
        msg = self.prep()
        self.assertEqual(msg["to"], SAFE_EMAIL)
        self.assertIn("ドッグフードご注文", msg["subject"])
        self.assertIn("21,450円", msg["body"])
        self.assertEqual(
            msg["idempotency_key"],
            "bigpaw-shop-customer/v1/" + ORDER + "/customer_order_confirmed",
        )
        self.assertEqual(len(msg["snapshot_digest"]), 64)
        self.assertTrue(msg["prepared_only"])
        self.assertEqual(self.outbound, [], "No email provider was invoked")
        self.assertFalse(self.simulate(), "Retry cannot create another dryrun")
        msg2 = self.prep()
        self.assertEqual(msg2, msg, "Stable, deterministic approved snapshot")
        self.assertNotIn(SAFE_EMAIL.encode(), self.file.read_bytes(),
                         "Recipient address must NEVER persist in SQLite")

    def test_contact_changed_after_simulation_must_block(self):
        self.approve()
        self.simulate()
        self.email = "other-buyer@example.invalid"
        with self.assertRaisesRegex(ValueError, "Fresh operator approval"):
            self.prep()
        self.approve()
        with self.assertRaisesRegex(ValueError, "No matching no-send simulation"):
            self.prep()
        self.assertNotIn(self.email.encode(), self.file.read_bytes())

    def test_square_order_mismatch_and_ambiguous_contact_block(self):
        self.approve()
        self.simulate()
        self.override_order = {"id": "OTHER_ORDER", "fulfillments": []}
        with self.assertRaises(SquareSandboxError):
            self.prep()
        self.override_order = {
            "id": SQUARE_ORDER, "fulfillments": [
                {"type":"SHIPMENT","shipment_details":{"recipient":{
                    "email_address":SAFE_EMAIL}}},
                {"type":"SHIPMENT","shipment_details":{"recipient":{
                    "email_address":"another@example.invalid"}}}
            ]
        }
        with self.assertRaises(ValueError):
            self.prep()

    def test_never_accept_unapproved_kind_or_order(self):
        self.approve()
        self.simulate()
        for order, kind in (
            ("notanorder", "customer_order_confirmed"),
            (ORDER, "supplier_purchase_request"),
            (ORDER, "customer_refund_completed"),
        ):
            with self.subTest(order=order, kind=kind):
                with self.assertRaises(ValueError):
                    prepare_customer_email(
                        self.store, order, kind,
                        sandbox_token=TOKEN, opener=self.square_get,
                    )

if __name__ == "__main__":
    unittest.main()
