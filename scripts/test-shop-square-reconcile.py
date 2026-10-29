"""Offline Square Sandbox read-back and shipment metadata tests."""
import json
import unittest

from shop_payments.sandbox_connector import SquareSandboxError
from shop_payments.sandbox_reconcile import (
    retrieve_verified_sandbox_payment,
    retrieve_sandbox_shipment_status,
)

PAYMENT_ID = "PAYMENTTEST001"
ORDER_ID = "SQUAREORDERTEST001"


class FakeResponse:
    status = 200

    def __init__(self, body):
        self.body = json.dumps(body).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None

    def read(self, maximum):
        return self.body


class TestSandboxVerification(unittest.TestCase):
    def test_fetch_sandbox_payment_uses_read_only_sandbox_hostname(self):
        seen = []
        def mock(req, timeout):
            seen.append((req.full_url, req.get_method(), req.get_header("Authorization")))
            return FakeResponse({"payment": {
                "id": PAYMENT_ID, "order_id": ORDER_ID, "status": "COMPLETED"
            }})
        payment = retrieve_verified_sandbox_payment(PAYMENT_ID, token="FAKE_SANDBOX_ONLY", opener=mock)
        self.assertEqual(payment["id"], PAYMENT_ID)
        self.assertEqual(seen[0][0], "https://connect.squareupsandbox.com/v2/payments/" + PAYMENT_ID)
        self.assertEqual(seen[0][1], "GET")
        self.assertEqual(seen[0][2], "Bearer FAKE_SANDBOX_ONLY")
        self.assertNotIn("connect.squareup.com", seen[0][0])

    def test_refuse_bad_id_token_and_mismatched_response(self):
        def never_call(*args, **kwargs):
            self.fail("Must not call network with untrusted identifier")
        for value in ("../../orders/123", "x", "http://malicious.test", "", "foo?bar=1"):
            with self.subTest(value=value), self.assertRaises(SquareSandboxError):
                retrieve_verified_sandbox_payment(value, token="FAKE", opener=never_call)
        with self.assertRaises(SquareSandboxError):
            retrieve_verified_sandbox_payment(PAYMENT_ID, token="", opener=never_call)
        def wrong_payment(req, timeout):
            return FakeResponse({"payment": {"id": "DIFFERENTPAYMENT"}})
        with self.assertRaises(SquareSandboxError):
            retrieve_verified_sandbox_payment(PAYMENT_ID, token="FAKE", opener=wrong_payment)

    def test_shipping_address_is_only_tested_not_returned(self):
        def mock_order(req, timeout):
            self.assertEqual(req.get_method(), "GET")
            self.assertEqual(req.full_url, "https://connect.squareupsandbox.com/v2/orders/" + ORDER_ID)
            return FakeResponse({"order": {
                "id": ORDER_ID, "fulfillments": [{
                    "type": "SHIPMENT",
                    "shipment_details": {"recipient": {
                        "display_name": "PRIVATE_TEST_CUSTOMER",
                        "address": {"country": "JP", "postal_code": "111-2222",
                                    "address_line_1": "PRIVATE_TEST_ADDRESS"}
                    }}
                }]
            }})
        result = retrieve_sandbox_shipment_status(ORDER_ID, token="FAKE", opener=mock_order)
        self.assertTrue(result["shipment_details_complete"])
        self.assertNotIn("PRIVATE_TEST_CUSTOMER", json.dumps(result))
        self.assertNotIn("PRIVATE_TEST_ADDRESS", json.dumps(result))

    def test_empty_or_overseas_shipment_is_not_complete(self):
        def missing(req, timeout):
            return FakeResponse({"order": {"id": ORDER_ID, "fulfillments": []}})
        result = retrieve_sandbox_shipment_status(ORDER_ID, token="FAKE", opener=missing)
        self.assertFalse(result["shipment_details_complete"])
        def foreign(req, timeout):
            return FakeResponse({"order": {
                "id": ORDER_ID, "fulfillments": [{
                    "type": "SHIPMENT", "shipment_details": {"recipient": {
                        "display_name": "PRIVATE",
                        "address": {"country": "US", "postal_code": "99999",
                                    "address_line_1": "PRIVATE"}
                    }}
                }]
            }})
        self.assertFalse(retrieve_sandbox_shipment_status(ORDER_ID, token="FAKE", opener=foreign)["shipment_details_complete"])


if __name__ == "__main__":
    unittest.main()
