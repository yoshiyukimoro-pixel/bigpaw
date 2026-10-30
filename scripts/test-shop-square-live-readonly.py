"""Offline-only future Square PRODUCTION verification test; NO API requests."""
from copy import deepcopy
import json
import unittest

from shop_payments.square_live_readonly import (
    ENDPOINT, LiveSquareNotVerified, verify_paid_live_shipment,
)

P = "LIVEFAKEPAYMENT1234"
O = "LIVEFAKEORDER1234"
L = "LIVEFAKELOCATION1234"
T = "synthetic-live-token-NOT-VALID"
PRICE = 21450

PAY = {
    "id": P,
    "order_id": O,
    "location_id": L,
    "status": "COMPLETED",
    "amount_money": {"amount": PRICE, "currency": "JPY"},
    "refunded_money": {"amount": 0, "currency": "JPY"},
}
ORDER = {
    "id": O, "location_id": L, "state": "OPEN",
    "total_money": {"amount": PRICE, "currency": "JPY"},
    "fulfillments": [{
        "type": "SHIPMENT",
        "shipment_details": {
            "recipient": {
                "display_name": "FAKE PERSON",
                "email_address": "synthetic@example.invalid",
                "address": {
                    "country": "JP", "address_line_1": "TEST ONLY",
                    "postal_code": "000-0000",
                }
            }
        }
    }]
}


class FakeResponse:
    status = 200
    def __init__(self,payload):
        self.body = json.dumps(payload).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,size):return self.body[:size]


class LiveReadOnlyTests(unittest.TestCase):
    def setUp(self):
        self.pay = deepcopy(PAY)
        self.order = deepcopy(ORDER)
        self.calls=[]

    def opener(self,req,timeout):
        self.calls.append((req.get_method(),req.full_url))
        self.assertEqual(req.get_method(),"GET")
        self.assertTrue(req.full_url.startswith(ENDPOINT+"/"))
        self.assertEqual(timeout,10)
        self.assertEqual(req.headers["Authorization"],"Bearer "+T)
        self.assertEqual(req.headers["Square-version"],"2026-09-16")
        if req.full_url == ENDPOINT+"/payments/"+P:
            return FakeResponse({"payment": self.pay})
        if req.full_url == ENDPOINT+"/orders/"+O:
            return FakeResponse({"order": self.order})
        self.fail("Unexpected external request")

    def verify(self, **overrides):
        values={
            "payment_id":P,"square_order_id":O,"location_id":L,
            "amount_yen":PRICE,"api_key":T,"opener":self.opener,
        }
        return verify_paid_live_shipment(**{**values,**overrides})

    def test_success_returns_transient_contact_not_address(self):
        result=self.verify()
        self.assertTrue(result["live_square_verified"])
        self.assertEqual(result["recipient_email"],"synthetic@example.invalid")
        self.assertEqual(result["amount_yen"],PRICE)
        self.assertEqual(self.calls,[
            ("GET",ENDPOINT+"/payments/"+P),
            ("GET",ENDPOINT+"/orders/"+O),
        ])
        self.assertNotIn("address",str(result))
        self.assertNotIn("FAKE PERSON",str(result))

    def test_payment_mismatches_are_blocked_before_order_lookup(self):
        mutations=[
            ("id","OTHER_PAYMENT"),
            ("order_id","OTHER_ORDER"),
            ("location_id","OTHER_LOCATION"),
            ("status","PENDING"),
        ]
        for field,value in mutations:
            with self.subTest(field=field):
                self.calls=[]
                self.pay=deepcopy(PAY)
                self.pay[field]=value
                with self.assertRaises(LiveSquareNotVerified):
                    self.verify()
                self.assertEqual(len(self.calls),1)
        for updates in (
            {"amount_money":{"amount":500,"currency":"JPY"}},
            {"amount_money":{"amount":PRICE,"currency":"USD"}},
            {"amount_money":{"amount":True,"currency":"JPY"}},
            {"refunded_money":{"amount":1,"currency":"JPY"}},
            {"refunded_money":{"amount":0,"currency":"USD"}},
        ):
            with self.subTest(updates=updates):
                self.pay=deepcopy(PAY)
                self.pay.update(updates)
                with self.assertRaises(LiveSquareNotVerified):
                    self.verify()

    def test_present_malformed_refund_field_is_never_unrefunded(self):
        # A completed payment with an explicit malformed refunded_money must
        # NOT be treated as though Square omitted the optional field.
        for value in (None, {}, False, [], "", "0",
                      {"currency": "JPY"},
                      {"amount": False, "currency": "JPY"},
                      {"amount": -1, "currency": "JPY"},
                      {"amount": 0, "currency": "USD"},
                      {"amount": 1, "currency": "JPY"}):
            with self.subTest(refund=value):
                self.pay=deepcopy(PAY)
                self.pay["refunded_money"]=value
                self.calls=[]
                with self.assertRaises(LiveSquareNotVerified):
                    self.verify()
                self.assertEqual(self.calls,[
                    ("GET", ENDPOINT+"/payments/"+P),
                ])
        # The field may genuinely be absent on an unrefunded payment.
        self.pay=deepcopy(PAY)
        del self.pay["refunded_money"]
        self.calls=[]
        self.assertTrue(self.verify()["live_square_verified"])
        self.assertEqual(len(self.calls),2)

    def test_order_or_recipient_mismatch_is_blocked(self):
        cases=[
            {"id":"OTHER"},
            {"state":"DRAFT"},
            {"location_id":"OTHER_LOCATION"},
            {"total_money":{"amount":PRICE-1,"currency":"JPY"}},
            {"fulfillments":[]},
            {"fulfillments":[{"type":"PICKUP"}]},
        ]
        for updates in cases:
            with self.subTest(updates=updates):
                self.pay=deepcopy(PAY)
                self.order=deepcopy(ORDER)
                self.order.update(updates)
                with self.assertRaises(LiveSquareNotVerified):
                    self.verify()
        for field,value in (
            ("email_address","bad_email"),
            ("email_address","evil@example.invalid\nBcc:bad@example.invalid"),
            ("display_name",""),
        ):
            with self.subTest(field=field):
                self.order=deepcopy(ORDER)
                self.order["fulfillments"][0]["shipment_details"]["recipient"][field]=value
                with self.assertRaises(LiveSquareNotVerified):
                    self.verify()
        self.order=deepcopy(ORDER)
        self.order["fulfillments"].append(deepcopy(self.order["fulfillments"][0]))
        self.order["fulfillments"][1]["shipment_details"]["recipient"]["email_address"]="other@example.invalid"
        with self.assertRaises(LiveSquareNotVerified):
            self.verify()

    def test_multiple_shipments_even_same_email_are_ambiguous(self):
        self.pay=deepcopy(PAY)
        for second in (
            deepcopy(ORDER["fulfillments"][0]),
            {"type":"PICKUP"},
        ):
            with self.subTest(extra=second.get("type")):
                self.order=deepcopy(ORDER)
                self.order["fulfillments"].append(deepcopy(second))
                self.calls=[]
                with self.assertRaises(LiveSquareNotVerified):
                    self.verify()
                self.assertEqual(len(self.calls),2)

    def test_input_validation_makes_no_api_request(self):
        for modified in ({"payment_id":"foo"},{"location_id":"bad"},
                         {"square_order_id":".."},{"amount_yen":False},
                         {"amount_yen":-1},{"api_key":""}):
            with self.subTest(modified=modified):
                self.calls=[]
                with self.assertRaises(LiveSquareNotVerified):
                    self.verify(**modified)
                self.assertEqual(len(self.calls),0)

if __name__=="__main__":
    unittest.main()
