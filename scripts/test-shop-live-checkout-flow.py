"""Offline-only checkout assembly test; exactly one fake POST and one fake GET."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shop_payments.live_checkout_flow import exercise_checkout_components
from shop_payments.live_checkout_intent import LiveCheckoutIntent
from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.square_live_checkout_adapter import (
    create_live_square_link, ENDPOINT as POST_ENDPOINT,
)
from shop_payments.square_live_readonly import ENDPOINT as GET_ENDPOINT

ORDER = "FOOD" + "3" * 32
LOCATION = "FAKELOCATION12345678"
SQUARE_ORDER = "FAKESQUAREORDER12345678"
LINK_ID = "FAKESQUARELINK12345678"
LINK_URL = "https://square.link/u/FAKE-LINK-NOT-REAL"
TOKEN = "FAKE-LIVE-SQUARE-ACCESS-ONLY-NOT-REAL"
GET_TOKEN = "FAKE-KEY-SQUARE-GET-ONLY-NOT-REAL-123456"


class Response:
    def __init__(self, body, status):
        self.data = json.dumps(body).encode()
        self.status = status
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, size):
        return self.data[:size]


class OfflineCheckoutFlowTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.db_path = Path(tmp.name) / "offline-private.sqlite"
        self.ledger = LiveOrderLedger(self.db_path)
        self.intent = LiveCheckoutIntent(self.ledger)
        self.sku, self.item = next(iter(load_sale_catalog().items()))
        self.cart = {self.sku: 1}
        self.calls = []

    def fake_post(self, req, timeout):
        self.calls.append((req.get_method(), req.full_url))
        self.assertEqual((req.get_method(), req.full_url),
                         ("POST", POST_ENDPOINT))
        self.assertEqual(req.headers["Authorization"], "Bearer " + TOKEN)
        self.assertEqual(timeout, 12)
        payload = json.loads(req.data)
        self.assertEqual(
            payload["order"]["line_items"][0]["base_price_money"]["amount"],
            self.item.sale_price_yen,
        )
        self.assertEqual(payload["order"]["location_id"], LOCATION)
        return Response({"payment_link": {
            "id": LINK_ID, "order_id": SQUARE_ORDER, "url": LINK_URL,
        }}, 201)

    def create(self, payload):
        return create_live_square_link(
            server_payload=payload, access_token=TOKEN,
            opener=self.fake_post,
        )

    def fake_get(self, req, timeout):
        self.calls.append((req.get_method(), req.full_url))
        self.assertEqual((req.get_method(), req.full_url),
                         ("GET", GET_ENDPOINT + "/orders/" + SQUARE_ORDER))
        self.assertEqual(req.headers["Authorization"], "Bearer " + GET_TOKEN)
        self.assertEqual(timeout, 10)
        return Response({"order": {
            "id": SQUARE_ORDER,
            "state": "OPEN",
            "location_id": LOCATION,
            "total_money": {"amount": self.item.sale_price_yen,
                            "currency": "JPY"},
        }}, 200)

    def flow(self, **kwargs):
        args = dict(
            intent=self.intent, trusted_order_id=ORDER,
            trusted_location_id=LOCATION, trusted_cart=self.cart,
            fake_creator=self.create, fake_square_order_get=self.fake_get,
            test_mode=True,
        )
        return exercise_checkout_components(**{**args, **kwargs})

    def test_end_to_end_injected_post_get_and_atomic_ledger(self):
        result = self.flow()
        self.assertEqual(result, {
            "checkout_url": LINK_URL, "order_id": ORDER,
            "amount_yen": self.item.sale_price_yen,
            "shipping_yen": 0,
            "test_only": True, "real_payments": False,
        })
        self.assertEqual(self.calls, [
            ("POST", POST_ENDPOINT),
            ("GET", GET_ENDPOINT + "/orders/" + SQUARE_ORDER),
        ])
        self.assertEqual(self.ledger.status(ORDER)["state"],
                         "checkout_recorded")
        self.assertEqual(self.intent.status(ORDER)["state"], "link_bound")
        db = self.db_path.read_bytes()
        for forbidden in (TOKEN, GET_TOKEN, "card_number",
                          "synthetic-customer@example.invalid"):
            self.assertNotIn(forbidden.encode(), db)

    def test_disabled_by_default_and_not_publicly_callable(self):
        with self.assertRaises(LiveOrderBlocked):
            self.flow(test_mode=False)
        with self.assertRaises(LiveOrderBlocked):
            self.flow(fake_creator=None)
        with self.assertRaises(LiveOrderBlocked):
            self.flow(fake_square_order_get=None)
        self.assertEqual(self.calls, [])
        self.assertFalse(self.db_path.exists())

    def test_duplicate_attempt_never_posts_twice(self):
        self.flow()
        self.calls.clear()
        with self.assertRaises(LiveOrderBlocked):
            self.flow()
        self.assertEqual(self.calls, [])
        self.assertEqual(self.intent.status(ORDER)["state"], "link_bound")

    def test_lost_post_response_remains_unknown_for_manual_audit(self):
        attempted = []
        def disconnect(payload):
            attempted.append(payload["idempotency_key"])
            raise TimeoutError("fake connection dropped")
        with self.assertRaises(TimeoutError):
            self.flow(fake_creator=disconnect)
        self.assertEqual(len(attempted), 1)
        self.assertEqual(self.intent.status(ORDER)["state"], "attempt_unknown")
        self.assertEqual(self.ledger.status(ORDER), {"state": "not_found"})
        with self.assertRaises(LiveOrderBlocked):
            self.flow()
        self.assertEqual(len(attempted), 1)
        self.assertEqual(self.calls, [])

    def test_bad_square_response_does_not_bind_a_checkout(self):
        def wrong_link(payload):
            return {"id": LINK_ID, "order_id": SQUARE_ORDER,
                    "url": "https://not-square.invalid/checkout"}
        with self.assertRaises(LiveOrderBlocked):
            self.flow(fake_creator=wrong_link)
        self.assertEqual(self.ledger.status(ORDER), {"state": "not_found"})
        self.assertEqual(self.intent.status(ORDER)["state"], "attempt_unknown")
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
