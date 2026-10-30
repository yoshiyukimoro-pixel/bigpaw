"""Offline-only checkout intent and synthetic Square GET binding tests.

No actual Square POST or external network. The production checkout and
payment-link issuance routes remain absent and must not be enabled.
"""
import json
from pathlib import Path
import sqlite3
from tempfile import TemporaryDirectory
import unittest

from shop_payments.live_checkout_intent import LiveCheckoutIntent
from shop_payments.live_order_ledger import LiveOrderBlocked, LiveOrderLedger
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.square_live_readonly import ENDPOINT, LiveSquareNotVerified

ORDER = "FOOD" + "e" * 32
OTHER = "FOOD" + "f" * 32
SQUARE_ORDER = "OFFLINEFAKESQUAREORDER12345"
LOCATION = "OFFLINEFAKELOCATION12345"
LINK = {
    "order_id": SQUARE_ORDER,
    "id": "OFFLINEFAKELINK12345678",
    "url": "https://square.link/u/FAKE_ONLY",
}
API_KEY = "NOT_A_REAL_SQUARE_PRODUCTION_CREDENTIAL"


class FakeResponse:
    status = 200
    def __init__(self, result):
        self.body = json.dumps(result).encode()
    def __enter__(self):
        return self
    def __exit__(self, *_):
        return False
    def read(self, count):
        return self.body[:count]


class CheckoutIntentTests(unittest.TestCase):
    def setUp(self):
        tmp = TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "private-fake.sqlite3"
        self.ledger = LiveOrderLedger(self.path)
        self.intent = LiveCheckoutIntent(self.ledger)
        self.sku, item = next(iter(load_sale_catalog().items()))
        self.price = item.sale_price_yen
        self.cart = {self.sku: 1}
        self.calls = []
        self.square_total = self.price
        self.square_location = LOCATION
        self.square_state = "OPEN"
        self.square_lines = None

    def square_get(self, req, timeout):
        self.calls.append((req.get_method(), req.full_url))
        self.assertEqual(req.get_method(), "GET")
        self.assertEqual(req.full_url, ENDPOINT + "/orders/" + SQUARE_ORDER)
        self.assertEqual(req.headers["Authorization"], "Bearer " + API_KEY)
        self.assertEqual(timeout, 10)
        order = {"id": SQUARE_ORDER, "location_id": self.square_location,
                 "state": self.square_state,
                 "total_money": {"amount": self.square_total, "currency": "JPY"}}
        if self.square_lines is not None:
            order["line_items"] = self.square_lines
        return FakeResponse({"order": order})

    def prepare(self, **kwargs):
        args = {"order_id": ORDER, "location_id": LOCATION, "cart": self.cart}
        return self.intent.prepare(**{**args, **kwargs})

    def bind(self, **kwargs):
        args = {"order_id": ORDER, "link": LINK, "api_key": API_KEY,
                "opener": self.square_get}
        return self.intent.bind_square_result(**{**args, **kwargs})

    def test_prepare_is_immutable_and_reuses_same_amount(self):
        self.assertEqual(self.intent.status(ORDER), {"state": "not_found"})
        p = self.prepare()
        self.assertTrue(p["new_plan"])
        self.assertEqual(p["amount_yen"], self.price)
        self.assertEqual(self.ledger.status(ORDER), {"state": "not_found"})
        self.assertFalse(self.prepare()["new_plan"])
        for changed in ({"cart": {self.sku: 2}},
                        {"location_id": "ANOTHERFAKELOCATION1234"}):
            with self.assertRaises(LiveOrderBlocked):
                self.prepare(**changed)
        with sqlite3.connect(self.path) as db:
            row = db.execute(
                "SELECT state,request_json FROM food_live_checkout_intent"
            ).fetchone()
        payload = json.loads(row[1])
        self.assertEqual(row[0], "planned")
        self.assertEqual(payload["order"]["line_items"][0]
                         ["base_price_money"]["amount"], self.price)
        self.assertEqual(payload["order"]["location_id"], LOCATION)
        self.assertEqual(payload["checkout_options"]["ask_for_shipping_address"], True)
        self.assertEqual(payload["checkout_options"]["allow_tipping"], False)

    def test_one_claim_before_external_post_then_no_auto_retry(self):
        self.prepare()
        claim = self.intent.begin_attempt(order_id=ORDER)
        self.assertEqual(claim["state"], "attempt_unknown")
        self.assertEqual(claim["server_only_payload"]["payment_note"],
                         "BIG PAW food order " + ORDER)
        self.assertEqual(self.intent.status(ORDER),
                         {"state": "attempt_unknown", "amount_yen": self.price})
        self.assertEqual(self.ledger.status(ORDER), {"state": "not_found"})
        with self.assertRaises(LiveOrderBlocked):
            self.intent.begin_attempt(order_id=ORDER)
        self.assertEqual(self.prepare()["state"], "attempt_unknown")
        with self.assertRaises(LiveOrderBlocked):
            self.prepare(cart={self.sku: 2})
        self.assertEqual(self.calls, [])

    def test_independent_square_get_and_bind_to_live_ledger(self):
        self.prepare()
        self.intent.begin_attempt(order_id=ORDER)
        result = self.bind()
        self.assertEqual(result, {"state": "link_bound", "new_binding": True})
        self.assertEqual(self.calls, [("GET", ENDPOINT + "/orders/" + SQUARE_ORDER)])
        self.assertEqual(self.ledger.status(ORDER)["state"], "checkout_recorded")
        self.assertEqual(self.ledger.checkout_payment_match(ORDER)["amount_yen"],
                         self.price)
        self.assertEqual(self.ledger.order_id_for_square_order(SQUARE_ORDER, LOCATION),
                         ORDER)
        self.calls.clear()
        self.assertEqual(self.bind(),
                         {"state": "link_bound", "new_binding": False})
        self.assertEqual(self.calls, [])
        with self.assertRaises(LiveOrderBlocked):
            self.intent.begin_attempt(order_id=ORDER)
        # The journal must have no buyer data or Square bearer token.
        data = self.path.read_bytes()
        for forbidden in ("fake-buyer@example.invalid", "Buyer name",
                          API_KEY, "card_nonce"):
            self.assertNotIn(forbidden.encode(), data)

    def test_never_bind_before_attempt(self):
        self.prepare()
        with self.assertRaises(LiveOrderBlocked):
            self.bind()
        self.assertEqual(self.calls, [])

    def test_bad_url_link_ids_and_square_order_mismatch_fail_closed(self):
        self.prepare()
        self.intent.begin_attempt(order_id=ORDER)
        bad_links = [
            {**LINK, "url": "http://square.link/u/FAKE_ONLY"},
            {**LINK, "url": "https://evil.invalid/u/FAKE_ONLY"},
            {**LINK, "url": "https://square.link.evil.invalid/u/FAKE_ONLY"},
            {**LINK, "url": "https://square.link/u/X?redirect=evil"},
            {**LINK, "url": "https://user:pass@square.link/u/X"},
            {**LINK, "id": "bad"},
            {**LINK, "order_id": "bad"},
        ]
        for result in bad_links:
            with self.subTest(result=result), self.assertRaises(LiveOrderBlocked):
                self.bind(link=result)
            self.assertEqual(self.intent.status(ORDER)["state"], "attempt_unknown")
            self.assertEqual(self.ledger.status(ORDER)["state"], "not_found")
        self.assertEqual(self.calls, [])
        for bad_location, bad_total, bad_state in (
            ("WRONGLOCATION1234", self.price, "OPEN"),
            (LOCATION, self.price + 1, "OPEN"),
            (LOCATION, self.price, "CANCELED"),
        ):
            self.square_location, self.square_total, self.square_state = (
                bad_location, bad_total, bad_state
            )
            with self.assertRaises(LiveOrderBlocked):
                self.bind()
            self.assertEqual(self.ledger.status(ORDER)["state"], "not_found")

    def test_square_hosted_draft_link_records_checkout_not_payment(self):
        self.prepare()
        saved = self.intent.begin_attempt(order_id=ORDER)
        self.square_state = "DRAFT"
        self.square_lines = saved["server_only_payload"]["order"]["line_items"]
        self.assertEqual(self.bind(), {"state": "link_bound", "new_binding": True})
        self.assertEqual(self.ledger.status(ORDER)["state"], "checkout_recorded")
        self.assertFalse(self.bind()["new_binding"])

    def test_draft_requires_same_server_saved_items_even_if_total_matches(self):
        self.prepare()
        saved = self.intent.begin_attempt(order_id=ORDER)
        original = saved["server_only_payload"]["order"]["line_items"][0]
        self.square_state = "DRAFT"
        for lines in (
            None, [],
            [{**original, "name": "OTHER PRODUCT"}],
            [{**original, "quantity": "2"}],
            [{**original, "base_price_money": {"amount": self.price + 1,
                                              "currency": "JPY"}}],
            [{**original, "base_price_money": {"amount": True, "currency": "JPY"}}],
        ):
            with self.subTest(lines=lines):
                self.square_lines = lines
                with self.assertRaises(LiveOrderBlocked):
                    self.bind()
                self.assertEqual(self.intent.status(ORDER)["state"], "attempt_unknown")
                self.assertEqual(self.ledger.status(ORDER)["state"], "not_found")
        self.square_lines = [original]
        self.assertTrue(self.bind()["new_binding"])

    def test_recovery_after_crash_between_ledger_and_intent_commit(self):
        self.prepare()
        self.intent.begin_attempt(order_id=ORDER)
        # Simulates response + first DB commit, before second DB commit.
        self.ledger.register_checkout(
            order_id=ORDER, square_order_id=SQUARE_ORDER,
            location_id=LOCATION, cart=self.cart,
        )
        result = self.bind()
        self.assertTrue(result["new_binding"])
        self.assertEqual(self.intent.status(ORDER)["state"], "link_bound")
        self.assertFalse(self.bind()["new_binding"])
        self.assertEqual(self.ledger.status(ORDER)["state"], "checkout_recorded")

    def test_past_plan_cannot_issue_and_no_api_attempt_is_created(self):
        self.prepare()
        import time
        with sqlite3.connect(self.path) as db:
            db.execute(
                "UPDATE food_live_checkout_intent SET created_at=? WHERE order_id=?",
                (int(time.time()) - 16 * 60, ORDER),
            )
        with self.assertRaises(LiveOrderBlocked):
            self.intent.begin_attempt(order_id=ORDER)
        self.assertEqual(self.intent.status(ORDER)["state"], "planned")
        self.assertEqual(self.calls, [])

    def test_duplicate_square_link_id_cannot_leave_partial_order(self):
        self.prepare()
        self.intent.begin_attempt(order_id=ORDER)
        self.bind()
        self.intent.prepare(order_id=OTHER, location_id=LOCATION, cart=self.cart)
        self.intent.begin_attempt(order_id=OTHER)
        other_square_order = "SECONDSYNTHETICORDER12345"
        other_link = {**LINK, "order_id": other_square_order}
        def other_get(req, timeout):
            self.assertEqual(req.get_method(), "GET")
            self.assertEqual(req.full_url,
                             ENDPOINT + "/orders/" + other_square_order)
            return FakeResponse({"order": {
                "id": other_square_order, "location_id": LOCATION, "state": "OPEN",
                "total_money": {"amount": self.price, "currency": "JPY"},
            }})
        with self.assertRaises(LiveOrderBlocked):
            self.intent.bind_square_result(
                order_id=OTHER, link=other_link, api_key=API_KEY,
                opener=other_get,
            )
        self.assertEqual(self.intent.status(OTHER)["state"], "attempt_unknown")
        self.assertEqual(self.ledger.status(OTHER), {"state": "not_found"})

    def test_no_unknown_order_or_unsaved_cart_creates_payment(self):
        with self.assertRaises(LiveOrderBlocked):
            self.intent.begin_attempt(order_id=ORDER)
        with self.assertRaises(LiveOrderBlocked):
            self.bind()
        self.assertFalse(self.path.exists() and
            self.ledger.status(ORDER)["state"] != "not_found")
        for invalid in ({}, {"NOTSKU": 1}, {self.sku: True},
                        {self.sku: 11}, {self.sku: 0}):
            with self.assertRaises(LiveOrderBlocked):
                self.prepare(cart=invalid)
        self.assertEqual(self.calls, [])


if __name__ == "__main__":
    unittest.main()
