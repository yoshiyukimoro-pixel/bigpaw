"""No-network tests: dormant live recipient HTTP never leaks without owner gate."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import unittest

from shop_payments import live_operator_reconciliation as route

ID="FOOD"+"a"*32
SNAP={"order_id":ID,"square_order_id":"LIVEFAKEORDER1234",
      "location_id":"LIVEFAKELOCATION1234","payment_id":"LIVEFAKEPAYMENT1234",
      "amount_yen":21450,"lines":[]}
DEST={"name":"PRIVATE <Buyer>","phone":"09012345678","postal":"100-0001",
      "prefecture":"東京都","city":"千代田区","line1":"丸の内1-1-1",
      "line2":"","line3":""}
class DummyHandler:
    def __init__(self,*,auth=True,host="bigpaw.site",origin="https://bigpaw.site",
                 csrf=True,confirmation="view_delivery_label_once"):
        self.path="/api/operator/shop-orders/shipping-address"
        self.headers={"Host":host,"Origin":origin,"Content-Type":"application/json",
                      "Content-Length":"128",
                      "Cookie":f"{route.COOKIE}="+("A"*43 if csrf else "bad")}
        self.body={"order_id":ID,"csrf_token":"A"*43,
                   "confirmation":confirmation}
        self.allowed=auth
        self.responses=[]
    def require(self,roles):
        assert roles==["operator"]
        return {"id":"test-operator"} if self.allowed else None
    def json_body(self):return self.body
    def send_json(self,payload,status=200,extra=None):
        self.responses.append((status,payload,extra))
class Tests(unittest.TestCase):
    def setUp(self):
        self.env={
            "BIGPAW_SHOP_LIVE_OPERATOR_RECONCILIATION_ENABLED":"1",
            "BIGPAW_SHOP_LIVE_ADDRESS_VIEW_ENABLED":"1",
            "BIGPAW_SQUARE_LIVE_ACCESS_TOKEN":"FAKE_LIVE_API_KEY_NOT_VALID_1234567890",
        }
    def handle(self,h,env=None,prod=True,path=None):
        with TemporaryDirectory() as tmp:
            if path:
                Path(tmp,"bigpaw-shop-live-orders.sqlite3").write_bytes(b"mock")
            return route.handle_post(h,env=self.env if env is None else env,
                is_production=prod,base_url="https://bigpaw.site",
                data_dir=Path(tmp))
    def test_disabled_by_default_even_with_operator_and_live_token(self):
        h=DummyHandler()
        self.assertTrue(self.handle(h,env={**self.env,"BIGPAW_SHOP_LIVE_ADDRESS_VIEW_ENABLED":"0"}))
        self.assertEqual(h.responses[0][0],404)
        h=DummyHandler()
        self.assertTrue(self.handle(h,prod=False))
        self.assertEqual(h.responses[0][0],404)
    def test_reject_wrong_origin_or_csrf_before_db_and_square(self):
        for kw in ({"origin":"https://evil.invalid"},{"host":"evil.invalid"},
                   {"csrf":False},{"confirmation":"ship_now"}):
            h=DummyHandler(**kw)
            self.assertTrue(self.handle(h))
            self.assertIn(h.responses[0][0],(400,403))
    def test_operator_authentication_required(self):
        h=DummyHandler(auth=False)
        self.assertTrue(self.handle(h))
        self.assertEqual(h.responses,[])
    def test_never_creates_missing_db(self):
        h=DummyHandler()
        self.assertTrue(self.handle(h))
        self.assertEqual(h.responses[0][0],409)
    def test_verified_snapshot_can_show_only_one_address_no_store(self):
        h=DummyHandler()
        with patch.object(route.LiveOrderLedger,"paid_notice_snapshot",
                          return_value=SNAP) as paid,patch(
                "shop_payments.live_shipping_address_view.read_live_recipient_for_dispatch",
                return_value=DEST) as provider:
            self.assertTrue(self.handle(h,path=True))
        self.assertEqual(h.responses[0][0],200)
        data=h.responses[0][1]
        self.assertEqual(data["recipient"]["name"],"PRIVATE <Buyer>")
        self.assertTrue(data["temporary_view_only"])
        headers=h.responses[0][2]
        self.assertIn("no-store",headers["Cache-Control"])
        self.assertEqual(headers["Referrer-Policy"],"no-referrer")
        paid.assert_called_once_with(ID)
        self.assertEqual(provider.call_args.kwargs["snapshot"],SNAP)
    def test_provider_reject_no_partial_personal_data(self):
        h=DummyHandler()
        with patch.object(route.LiveOrderLedger,"paid_notice_snapshot",
                          return_value=SNAP),patch(
                "shop_payments.live_shipping_address_view.read_live_recipient_for_dispatch",
                side_effect=ValueError("private provider detail")):
            self.assertTrue(self.handle(h,path=True))
        self.assertEqual(h.responses[0][0],409)
        self.assertNotIn("private provider detail",str(h.responses))

if __name__=="__main__":unittest.main()
