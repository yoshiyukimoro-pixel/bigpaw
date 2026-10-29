import base64
import hashlib
import hmac
import json
import unittest

from shop_payments.square_checkout import SaleItem, build_square_link_payload, verify_square_webhook, completed_payment_matches


class SquareSafety(unittest.TestCase):
    def args(self, **changes):
        result = {
            "cart": {"A02": 2, "Z01": 1},
            "verified_prices": {
                "A02": SaleItem("A02", "アカナ パピーラージ", "11.4kg", 21450),
                "Z01": SaleItem("Z01", "ZIWI ベニソン", "2.5kg", 42900),
            },
            "shipping_yen": 1200,
            "square_location_id": "SQUARETEST1234",
            "local_order_id": "FOOD202610280001",
            "shipping_confirmed": True,
        }
        result.update(changes)
        return result

    def test_order_has_server_verified_prices_and_shipping(self):
        request, total = build_square_link_payload(**self.args())
        self.assertEqual(total, 87000)
        self.assertEqual(len(request["order"]["line_items"]), 3)
        self.assertEqual(request["order"]["line_items"][-1]["name"], "送料")
        self.assertTrue(request["checkout_options"]["ask_for_shipping_address"])
        self.assertFalse(request["checkout_options"]["allow_tipping"])
        self.assertEqual(request["order"]["taxes"][0]["type"], "INCLUSIVE")
        self.assertEqual(request["order"]["taxes"][0]["scope"], "ORDER")
        self.assertEqual(request["order"]["taxes"][0]["percentage"], "10")
        self.assertNotIn("quick_pay", request)

    def test_idempotent_per_persisted_order(self):
        first, _ = build_square_link_payload(**self.args())
        same, _ = build_square_link_payload(**self.args())
        different, _ = build_square_link_payload(**self.args(local_order_id="FOOD202610280002"))
        self.assertEqual(first["idempotency_key"], same["idempotency_key"])
        self.assertNotEqual(first["idempotency_key"], different["idempotency_key"])

    def test_rejects_bad_order_data(self):
        for item in ({"A99": 1}, {"A02": 0}, {"A02": -1}, {"A02": 11}, {"A02": "1"}, {"A02": True}):
            with self.subTest(cart=item), self.assertRaises(ValueError):
                build_square_link_payload(**self.args(cart=item))
        with self.assertRaises(ValueError):
            build_square_link_payload(**self.args(shipping_confirmed=False))
        with self.assertRaises(ValueError):
            build_square_link_payload(**self.args(shipping_yen=-100))
        with self.assertRaises(ValueError):
            build_square_link_payload(**self.args(verified_prices={"A02": SaleItem("A02", "a", "kg", 0)}, cart={"A02": 1}))

    def test_valid_signed_webhook_and_price_match(self):
        event = {
            "event_id": "event-123",
            "type": "payment.updated",
            "data": {"object": {"payment": {
                "status": "COMPLETED", "order_id": "order-456",
                "location_id": "SQUARETEST1234", "amount_money": {"amount": 87000, "currency": "JPY"}
            }}}
        }
        data = json.dumps(event).encode("utf-8")
        key = "not-a-real-signature-key"
        url = "https://example.com/api/shop/webhook"
        signature = base64.b64encode(hmac.new(key.encode(), url.encode()+data, hashlib.sha256).digest()).decode()
        validated = verify_square_webhook(raw_body=data, signature_header=signature, signature_key=key, notification_url=url)
        self.assertEqual(validated["event_id"], "event-123")
        self.assertTrue(completed_payment_matches(validated, square_order_id="order-456", amount_yen=87000, location_id="SQUARETEST1234"))
        self.assertFalse(completed_payment_matches(validated, square_order_id="other-order", amount_yen=87000, location_id="SQUARETEST1234"))
        self.assertFalse(completed_payment_matches(validated, square_order_id="order-456", amount_yen=87001, location_id="SQUARETEST1234"))
        for tamper in [dict(raw_body=data+b" "), dict(notification_url=url+"/"), dict(signature_key="wrong"), dict(signature_header="invalid")]:
            payload = dict(raw_body=data, signature_header=signature, signature_key=key, notification_url=url)
            payload.update(tamper)
            with self.assertRaises(ValueError):
                verify_square_webhook(**payload)
        validated["data"]["object"]["payment"]["status"] = "PENDING"
        self.assertFalse(completed_payment_matches(validated, square_order_id="order-456", amount_yen=87000, location_id="SQUARETEST1234"))


if __name__ == "__main__":
    unittest.main()
