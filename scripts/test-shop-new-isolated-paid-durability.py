"""Offline guard test: Square order recovery cannot disclose or misattribute."""
import importlib.util
from pathlib import Path
from unittest import TestCase,main
from unittest.mock import patch
spec=importlib.util.spec_from_file_location("recovery",Path("scripts/audit-shop-new-isolated-paid-durability.py"))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
LOCAL="FOOD"+"b"*32
SQID="SANDBOX_ORDER_MOCK"
PAY="SANDBOX_PAYMENT_MOCK"
LOCATION="SANDBOX_LOCATION_MOCK"
def payment(note=None):
    return {"id":PAY,"order_id":SQID,"status":"COMPLETED","location_id":LOCATION,
        "amount_money":{"amount":21450,"currency":"JPY"},
        "note":note if note is not None else "BIG PAW food order "+LOCAL}
def fake(path,token,params=None):
    if path=="/payments":return {"payments":[payment()]}
    if path=="/payments/"+PAY:return {"payment":payment()}
    if path=="/orders/"+SQID:return {"order":{"id":SQID}}
    raise AssertionError("Wrong request")
class RecoverySafety(TestCase):
    def test_one_fresh_square_payment(self):
        with patch.object(m,"sq",side_effect=fake) as request:
            self.assertEqual(m.recover_payment("NO_REAL_TOKEN",LOCATION),LOCAL)
            self.assertEqual(request.call_count,3)
            self.assertTrue(all(x.args[0].startswith(("/payments","/orders")) for x in request.call_args_list))
    def test_no_match_blocked(self):
        def nothing(path,token,params=None):
            return {"payments":[]} if path=="/payments" else fake(path,token,params)
        with patch.object(m,"sq",side_effect=nothing):
            with self.assertRaises(ValueError):m.recover_payment("FAKE",LOCATION)
    def test_two_matches_blocked(self):
        def duplicates(path,token,params=None):
            return {"payments":[payment(),payment()]} if path=="/payments" else fake(path,token,params)
        with patch.object(m,"sq",side_effect=duplicates):
            with self.assertRaises(ValueError):m.recover_payment("FAKE",LOCATION)
    def test_no_public_paid_read_when_disabled(self):
        with self.assertRaises(ValueError):m.paid_read(LOCAL,{"BIGPAW_ENV":"sandbox","BIGPAW_SHOP_STAGE_PREVIEW_ENABLED":"0"})
if __name__=="__main__":main()
