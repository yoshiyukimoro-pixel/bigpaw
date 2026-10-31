"""Offline proof: future real-operator dispatch address never bypasses payment checks."""
from copy import deepcopy
import json
import unittest

from shop_payments.live_shipping_address_view import read_live_recipient_for_dispatch
from shop_payments.square_live_readonly import (
    ENDPOINT, LiveSquareNotVerified,
)
P="LIVEFAKEPAYMENT1234"
O="LIVEFAKEORDER1234"
L="LIVEFAKELOCATION1234"
PRICE=21450
T="FAKE_LIVE_TEST_TOKEN_NEVER_VALID"
SNAP={"order_id":"FOOD"+"a"*32,"payment_id":P,
      "square_order_id":O,"location_id":L,"amount_yen":PRICE,
      "lines":[{"sku":"A02","qty":1,"unit_yen":PRICE,
                "name":"Synthetic Test Food","size":"11.4kg"}]}
PAY={"id":P,"order_id":O,"location_id":L,"status":"COMPLETED",
     "amount_money":{"amount":PRICE,"currency":"JPY"},
     "refunded_money":{"amount":0,"currency":"JPY"}}
RECIPIENT={"display_name":"FAKE <Customer>","phone_number":"09012345678",
           "email_address":"example@example.invalid",
           "address":{"country":"JP","postal_code":"100-0001",
             "administrative_district_level_1":"東京都",
             "locality":"千代田区",
             "address_line_1":"丸の内1-1-1",
             "address_line_2":"テスト室"}}
ORDER={"id":O,"location_id":L,"state":"OPEN",
       "total_money":{"amount":PRICE,"currency":"JPY"},
       "fulfillments":[{"type":"SHIPMENT",
           "shipment_details":{"recipient":RECIPIENT}}]}
class Reply:
    status=200
    def __init__(self,v):self.raw=json.dumps(v).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,size):return self.raw[:size]

class Cases(unittest.TestCase):
    def setUp(self):
        self.pay=deepcopy(PAY)
        self.order=deepcopy(ORDER)
        self.calls=[]
    def opener(self,request,timeout):
        self.assertEqual(request.get_method(),"GET")
        self.assertTrue(request.full_url.startswith(ENDPOINT+"/"))
        self.assertEqual(timeout,10)
        self.calls.append(request.full_url)
        if request.full_url==ENDPOINT+"/payments/"+P:
            return Reply({"payment":self.pay})
        if request.full_url==ENDPOINT+"/orders/"+O:
            return Reply({"order":self.order})
        self.fail("Unexpected network request")
    def check(self,**overrides):
        return read_live_recipient_for_dispatch(
            snapshot=overrides.get("snapshot",SNAP),
            api_key=T,opener=self.opener)
    def test_returns_only_necessary_private_shipping_fields(self):
        label=self.check()
        self.assertEqual(label["name"],"FAKE <Customer>")
        self.assertEqual(label["postal"],"100-0001")
        self.assertEqual(label["city"],"千代田区")
        self.assertEqual(label["line2"],"テスト室")
        self.assertNotIn("email",str(label))
        self.assertNotIn("payment",str(label))
        self.assertEqual(self.calls,[
            ENDPOINT+"/payments/"+P,
            ENDPOINT+"/orders/"+O,
            ENDPOINT+"/orders/"+O,
        ])
    def test_refund_or_payment_mismatch_blocks_before_returning_recipient(self):
        for value in (1,PRICE):
            self.pay=deepcopy(PAY)
            self.pay["refunded_money"]={"amount":value,"currency":"JPY"}
            self.calls=[]
            with self.assertRaises(LiveSquareNotVerified):
                self.check()
            self.assertEqual(self.calls,[ENDPOINT+"/payments/"+P])
        self.pay=deepcopy(PAY)
        self.pay["status"]="PENDING"
        with self.assertRaises(LiveSquareNotVerified):self.check()
    def test_missing_prefecture_city_or_ambiguous_fulfillment_blocks(self):
        for field in ("administrative_district_level_1","locality","address_line_1"):
            self.order=deepcopy(ORDER)
            self.order["fulfillments"][0]["shipment_details"]["recipient"]["address"][field]=""
            with self.subTest(field=field),self.assertRaises(LiveSquareNotVerified):
                self.check()
        self.order=deepcopy(ORDER)
        self.order["fulfillments"].append(deepcopy(ORDER["fulfillments"][0]))
        with self.assertRaises(LiveSquareNotVerified):self.check()
    def test_malformed_optional_line_blocks(self):
        self.order=deepcopy(ORDER)
        self.order["fulfillments"][0]["shipment_details"]["recipient"]["address"]["address_line_3"]="x"+chr(10)+"Bcc:"
        with self.assertRaises(LiveSquareNotVerified):self.check()
    def test_wrong_or_untrusted_snapshot_never_calls_square(self):
        for invalid in ({}, {**SNAP,"amount_yen":0},
                        {**SNAP,"square_order_id":"bad"}):
            self.calls=[]
            with self.assertRaises((LiveSquareNotVerified,ValueError)):
                self.check(snapshot=invalid)
            self.assertEqual(self.calls,[])

if __name__=="__main__":unittest.main()
