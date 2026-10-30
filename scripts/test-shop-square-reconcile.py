"""Offline Square Sandbox read-back and shipment metadata tests."""
import json
import unittest

from shop_payments.sandbox_connector import SquareSandboxError
from shop_payments.sandbox_reconcile import (
    retrieve_verified_sandbox_payment,
    retrieve_sandbox_shipment_status,
    verify_current_sandbox_payment,
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

    def test_fresh_sandbox_refund_metadata_never_treats_present_null_as_zero(self):
        snapshot = {
            "order_id": "FOOD" + "a" * 32,
            "amount_yen": 21450,
            "square_order_id": ORDER_ID,
            "square_location_id": "SQUARELOCATIONTEST001",
            "square_payment_id": PAYMENT_ID,
            "cart": {"A02": 1},
        }
        original = {
            "id": PAYMENT_ID, "order_id": ORDER_ID,
            "location_id": snapshot["square_location_id"],
            "status": "COMPLETED",
            "amount_money": {"amount": 21450, "currency": "JPY"},
        }
        order = {"id": ORDER_ID,
                 "location_id": snapshot["square_location_id"],
                 "state": "OPEN",
                 "total_money": {"amount": 21450, "currency": "JPY"}}
        def opener(payment):
            def fake(request, timeout):
                self.assertEqual(request.get_method(), "GET")
                if request.full_url.endswith("/payments/"+PAYMENT_ID):
                    return FakeResponse({"payment": payment})
                if request.full_url.endswith("/orders/"+ORDER_ID):
                    return FakeResponse({"order": order})
                self.fail("Unknown Square endpoint")
            return fake
        good = verify_current_sandbox_payment(
            snapshot=snapshot, token="FAKE_SANDBOX_ONLY",
            opener=opener(original))
        self.assertTrue(good["unrefunded_verified"])
        for refund in (None, {}, [], False, "0",
                       {"amount": True, "currency": "JPY"},
                       {"amount": 0, "currency": "USD"},
                       {"amount": 1, "currency": "JPY"}):
            with self.subTest(refund=refund), self.assertRaises(SquareSandboxError):
                verify_current_sandbox_payment(
                    snapshot=snapshot, token="FAKE_SANDBOX_ONLY",
                    opener=opener({**original, "refunded_money": refund}))
        self.assertTrue(verify_current_sandbox_payment(
            snapshot=snapshot, token="FAKE_SANDBOX_ONLY",
            opener=opener({**original, "refunded_money": {
                "amount": 0, "currency": "JPY"}}))["unrefunded_verified"])

    def test_shipping_address_is_only_tested_not_returned(self):
        def mock_order(req, timeout):
            self.assertEqual(req.get_method(), "GET")
            self.assertEqual(req.full_url, "https://connect.squareupsandbox.com/v2/orders/" + ORDER_ID)
            return FakeResponse({"order": {
                "id": ORDER_ID, "fulfillments": [{
                    "type": "SHIPMENT",
                    "shipment_details": {"recipient": {
                        "display_name": "PRIVATE_TEST_CUSTOMER",
                        "phone_number": "09012345678",
                        "address": {"country": "JP", "postal_code": "111-2222",
                                    "address_line_1": "PRIVATE_TEST_ADDRESS"}
                    }}
                }]
            }})
        result = retrieve_sandbox_shipment_status(ORDER_ID, token="FAKE", opener=mock_order)
        self.assertTrue(result["shipment_details_complete"])
        self.assertNotIn("PRIVATE_TEST_CUSTOMER", json.dumps(result))
        self.assertNotIn("PRIVATE_TEST_ADDRESS", json.dumps(result))

    def test_multiple_square_shipments_require_manual_address_review(self):
        recipient = {
            "display_name": "SYNTHETIC",
            "address": {"country": "JP", "postal_code": "111-2222",
                        "address_line_1": "TEST ONLY"},
        }
        one = {"type": "SHIPMENT", "shipment_details": {
            "recipient": recipient}}
        for fulfillments in ([one, one], [one, {"type": "PICKUP"}],
                             [one, {"type": "SHIPMENT"}]):
            with self.subTest(count=len(fulfillments)):
                def fake(req,timeout):
                    self.assertEqual(req.get_method(),"GET")
                    return FakeResponse({"order": {
                        "id": ORDER_ID,"fulfillments": fulfillments}})
                outcome=retrieve_sandbox_shipment_status(
                    ORDER_ID,token="FAKE",opener=fake)
                self.assertEqual(outcome,{
                    "square_order_id": ORDER_ID,
                    "shipment_details_complete": False,
                })
                self.assertNotIn("SYNTHETIC", str(outcome))

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
                        "phone_number": "09012345678",
                        "address": {"country": "US", "postal_code": "99999",
                                    "address_line_1": "PRIVATE"}
                    }}
                }]
            }})
        self.assertFalse(retrieve_sandbox_shipment_status(ORDER_ID, token="FAKE", opener=foreign)["shipment_details_complete"])


if __name__ == "__main__":
    unittest.main()
