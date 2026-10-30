"""Offline regression for private Sandbox order CLI; no real delivery or refund."""
import base64
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.sandbox_fulfillment import SandboxFulfillmentOps

spec=importlib.util.spec_from_file_location(
    "operator",Path("scripts/shop-sandbox-operator.py"))
console=importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)
LOCATION="SANDBOXLOCATION1234"


class FakeResponse:
    status=200
    def __init__(self,obj):
        self.content=json.dumps(obj).encode()
    def __enter__(self):return self
    def __exit__(self,*a):return None
    def read(self,n):return self.content


def shipment_opener(order_id):
    def opener(req,timeout):
        assert req.get_method()=="GET"
        assert req.full_url=="https://connect.squareupsandbox.com/v2/orders/"+order_id
        return FakeResponse({"order":{
            "id":order_id,"fulfillments":[{"type":"SHIPMENT","shipment_details":{
                "recipient":{"display_name":"PRIVATE NAME",
                    "phone_number":"09012345678",
                    "address":{"country":"JP","postal_code":"100-0001",
                               "address_line_1":"PRIVATE ADDRESS"}}
            }}]}})
    return opener


class OperatorConsoleTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"sandbox.sqlite3"
        self.store=SandboxOrderStore(self.db)
        self.ops=SandboxFulfillmentOps(self.store)
        self.parser=console.parser()
        self.order="FOOD"+"a"*32
        self.square="SQUAREORDERTEST1234"
        self.payment="SQUAREPAYMENTTEST1234"
        self.fake_payment={"id":self.payment,"order_id":self.square,
             "location_id":LOCATION,"status":"COMPLETED",
             "amount_money":{"amount":21450,"currency":"JPY"}}

    def run_console(self,command,*,write=False,opener=None):
        prefix=["--db",str(self.db)]
        if write:prefix.append("--confirm-sandbox")
        args=self.parser.parse_args(prefix+command)
        env={"BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE_TEST_TOKEN"}
        return console.execute(args,env=env,opener=opener)

    def paid_order(self):
        payload,amount=self.store.add_pending_order(
            order_id=self.order,cart={"A02":1},
            verified_prices=load_sale_catalog(),
            shipping_yen=0,location_id=LOCATION)
        self.assertEqual(amount,21450)
        self.store.save_link(self.order,{"url":"https://sandbox.square.link/u/mock",
            "square_order_id":self.square,"square_link_id":"TESTLINK001"})
        event={"event_id":"testevent12345","type":"payment.updated",
               "data":{"object":{"payment":self.fake_payment}}}
        raw=json.dumps(event).encode()
        key="FAKE_HMAC_KEY";url="https://sandbox.invalid/webhook"
        sig=base64.b64encode(hmac.new(
            key.encode(),url.encode()+raw,hashlib.sha256).digest()).decode()
        self.assertEqual(self.store.accept_webhook(
            raw_body=raw,signature_header=sig,
            signature_key=key,notification_url=url,
            payment_lookup=lambda x:self.fake_payment),"paid")

    def test_list_and_payment_status_no_pii(self):
        self.assertEqual(self.run_console(["list"])["orders"],[])
        self.paid_order()
        rows=self.run_console(["list"])["orders"]
        self.assertEqual(len(rows),1)
        self.assertEqual(rows[0]["payment_state"],"paid")
        self.assertEqual(rows[0]["amount_yen"],21450)
        self.assertEqual(rows[0]["shipping_yen"],0)
        self.assertEqual(rows[0]["items"][0]["sku"],"A02")
        self.assertEqual(rows[0]["fulfillment_state"],"not_assessed")
        self.assertNotIn("PRIVATE",json.dumps(rows))
        self.assertNotIn(self.payment,json.dumps(rows))
        self.assertEqual(self.run_console(["check-paid",self.order])["state"],
                         "not_assessed")

    def test_assess_stock_then_log_shipped_without_real_fulfillment(self):
        self.paid_order()
        self.assertEqual(self.run_console(["stock","A02"])["available"],0)
        with self.assertRaises(ValueError):
            self.run_console(["stock-set","A02","2"])
        self.run_console(["stock-set","A02","2"],write=True)
        self.assertEqual(self.run_console(["stock","A02"])["available"],2)
        with self.assertRaises(ValueError):
            self.run_console(["assess",self.order])
        with self.assertRaises(ValueError):
            self.run_console(["record-shipped",self.order],write=True)
        result=self.run_console(["assess",self.order],write=True,
            opener=shipment_opener(self.square))
        self.assertEqual(result["fulfillment_state"],"ready_to_pack")
        self.assertFalse(result["shipping_executed"])
        self.assertEqual(self.run_console(["stock","A02"])["available"],1)
        again=self.run_console(["assess",self.order],write=True,
            opener=shipment_opener(self.square))
        self.assertEqual(again["fulfillment_state"],"ready_to_pack")
        self.assertEqual(self.run_console(["stock","A02"])["available"],1)
        sent=self.run_console(["record-shipped",self.order],write=True)
        self.assertEqual(sent["fulfillment_state"],"shipped")
        self.assertFalse(sent["shipping_executed"])
        with self.assertRaises(ValueError):
            self.run_console(["refund-review",self.order],write=True)
        kinds={e["event_type"] for e in self.run_console(["events"])["events"]}
        self.assertEqual(kinds,{"ready_to_pack","shipped"})

    def test_refund_requires_square_verified_complete_refund(self):
        self.paid_order()
        self.run_console(["stock-set","A02","3"],write=True)
        self.run_console(["assess",self.order],write=True,
            opener=shipment_opener(self.square))
        self.run_console(["refund-review",self.order],write=True)
        def payment_opener(value):
            def open_fake(req,timeout):
                self.assertEqual(req.full_url,
                    "https://connect.squareupsandbox.com/v2/payments/"+self.payment)
                return FakeResponse({"payment":{**self.fake_payment,
                    "refunded_money":{"amount":value,"currency":"JPY"}}})
            return open_fake
        with self.assertRaises(ValueError):
            self.run_console(["verify-refund",self.order],write=True,
                opener=payment_opener(1))
        self.assertEqual(self.run_console(["stock","A02"])["available"],2)
        status=self.run_console(["verify-refund",self.order],write=True,
            opener=payment_opener(21450))
        self.assertEqual(status["fulfillment_state"],"refunded")
        self.assertFalse(status["refund_initiated"])
        self.assertEqual(self.run_console(["stock","A02"])["available"],3)
        self.run_console(["verify-refund",self.order],write=True,
            opener=payment_opener(21450))
        self.assertEqual(self.run_console(["stock","A02"])["available"],3)

    def test_missing_db_or_symlink_rejected(self):
        with self.assertRaises((ValueError,FileNotFoundError)):
            console._validated_db(str(self.db.parent/"missing.sqlite3"))
        alias=self.db.parent/"alias.sqlite3"
        alias.symlink_to(self.db)
        with self.assertRaises(ValueError):
            console._validated_db(str(alias))

    def test_invalid_sku_and_order_id(self):
        with self.assertRaises(ValueError):
            self.run_console(["stock","A99"])
        with self.assertRaises(ValueError):
            self.run_console(["record-shipped","ORDER_GUESSED"],write=True)


if __name__=="__main__":
    unittest.main()
