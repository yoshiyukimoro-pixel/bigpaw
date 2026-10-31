"""Offline fake Square POST+GET tests; no real token, charge or email."""
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from shop_payments.live_checkout_intent import LiveCheckoutIntent
from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.square_live_checkout_adapter import (
    ENDPOINT, create_live_square_link,
)
from shop_payments.square_live_readonly import ENDPOINT as GET_ENDPOINT

ORDER = "FOOD" + "9" * 32
LOCATION = "OFFLINELOCATION123456"
SQUARE_ORDER = "OFFLINELIVEORDER123456"
LINK_ID = "OFFLINEPAYMENTLINK123456"
TOKEN = "NOT_REAL_PRODUCTION_SQUARE_TOKEN_FAKE"
PRICE_SKU, PRICE_ITEM = next(iter(load_sale_catalog().items()))


class Response:
    def __init__(self, data, status=201):
        self.status = status
        self.body = json.dumps(data).encode()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False

    def read(self, size):
        return self.body[:size]


class LiveCheckoutAdapterTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "offline-journal.sqlite"
        self.ledger = LiveOrderLedger(self.path)
        self.intent = LiveCheckoutIntent(self.ledger)
        self.calls = []
        self.intent.prepare(order_id=ORDER, location_id=LOCATION,
                            cart={PRICE_SKU: 1})
        self.payload = self.intent.begin_attempt(
            order_id=ORDER
        )["server_only_payload"]

    def fake_post(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url))
        self.assertEqual(request.full_url, ENDPOINT)
        self.assertEqual(request.get_method(), "POST")
        self.assertEqual(timeout, 12)
        self.assertEqual(request.headers["Authorization"], "Bearer " + TOKEN)
        data = json.loads(request.data)
        self.assertEqual(data, self.payload)
        return Response({"payment_link": {
            "id": LINK_ID,
            "order_id": SQUARE_ORDER,
            "url": "https://square.link/u/TEST_ONLY_LINK",
        }})

    def fake_get(self, request, timeout):
        self.calls.append((request.get_method(), request.full_url))
        self.assertEqual(request.full_url,
                         GET_ENDPOINT + "/orders/" + SQUARE_ORDER)
        self.assertEqual(request.get_method(), "GET")
        self.assertEqual(timeout, 10)
        return Response({"order": {
            "id": SQUARE_ORDER, "location_id": LOCATION,
            "state": "OPEN",
            "total_money": {
                "amount": PRICE_ITEM.sale_price_yen,
                "currency": "JPY",
            },
        }}, status=200)

    def test_end_to_end_prepared_request_fake_post_fake_get_atomic_bind(self):
        link = create_live_square_link(
            server_payload=self.payload, access_token=TOKEN,
            opener=self.fake_post,
        )
        self.assertEqual(link["id"], LINK_ID)
        result = self.intent.bind_square_result(
            order_id=ORDER, link=link, api_key=TOKEN,
            opener=self.fake_get,
        )
        self.assertTrue(result["new_binding"])
        self.assertEqual(self.calls, [
            ("POST", ENDPOINT),
            ("GET", GET_ENDPOINT + "/orders/" + SQUARE_ORDER),
        ])
        self.assertEqual(self.intent.status(ORDER)["state"], "link_bound")
        self.assertEqual(self.ledger.status(ORDER)["state"], "checkout_recorded")
        with self.assertRaises(LiveOrderBlocked):
            self.intent.begin_attempt(order_id=ORDER)
        self.assertNotIn(TOKEN.encode(), self.path.read_bytes())

    def test_mutated_external_payload_never_posts(self):
        candidates = [
            {**self.payload, "idempotency_key": "user_overridden"},
            {**self.payload, "redirect_url": "https://attacker.invalid"},
            {**self.payload, "checkout_options": {"allow_tipping": True}},
            {**self.payload, "payment_note": "wrong"},
            {**self.payload, "order": {**self.payload["order"],
               "line_items": [{"name": "INJECTED", "quantity": "0",
                              "base_price_money": {"amount": 1, "currency": "JPY"}}]}},
            {**self.payload, "order": {**self.payload["order"],
               "line_items": [{"name": "INJECTED", "quantity": "1",
                              "base_price_money": {"amount": True, "currency": "JPY"}}]}},
        ]
        for payload in candidates:
            with self.subTest(candidate=payload), self.assertRaises(LiveOrderBlocked):
                create_live_square_link(
                    server_payload=payload, access_token=TOKEN,
                    opener=self.fake_post,
                )
        self.assertEqual(self.calls, [])

    def test_timeout_never_automatically_retries(self):
        def timeout(request, timeout):
            self.calls.append("POST")
            raise TimeoutError("Synthetic lost connection")
        with self.assertRaises(LiveOrderBlocked):
            create_live_square_link(
                server_payload=self.payload, access_token=TOKEN,
                opener=timeout,
            )
        self.assertEqual(self.calls, ["POST"])
        self.assertEqual(self.intent.status(ORDER)["state"], "attempt_unknown")
        with self.assertRaises(LiveOrderBlocked):
            self.intent.begin_attempt(order_id=ORDER)

    def test_bad_square_response_rejected_before_binding(self):
        for response in (
            {},
            {"payment_link": {"id": LINK_ID, "order_id": SQUARE_ORDER,
                              "url": "http://square.link/u/BAD"}},
            {"payment_link": {"id": LINK_ID, "order_id": SQUARE_ORDER,
                              "url": "https://evil.invalid/pay"}},
            {"payment_link": {"id": "x", "order_id": SQUARE_ORDER,
                              "url": "https://square.link/u/BAD"}},
        ):
            with self.subTest(response=response):
                def fake(request, timeout):
                    return Response(response)
                with self.assertRaises(LiveOrderBlocked):
                    create_live_square_link(
                        server_payload=self.payload, access_token=TOKEN,
                        opener=fake,
                    )
        self.assertEqual(self.ledger.status(ORDER)["state"], "not_found")


if __name__ == "__main__":
    unittest.main()
