"""Offline notification outbox test: Square-verified buy-to-order only; sends nothing."""
import base64
import hashlib
import hmac
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore, SquareSandboxError
from shop_payments.sandbox_notifications import SandboxNotificationDrafts
from shop_payments.sandbox_procurement import SandboxProcurementOps

spec=importlib.util.spec_from_file_location(
    "operator",Path("scripts/shop-sandbox-operator.py"))
console=importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)

LOCATION="SANDBOXLOCATION12345"
ORDER="FOOD"+"e"*32
SQ_ORDER="SQUAREORDERTEST12345"
PAYMENT="SQUAREPAYMENTTEST12345"


class Response:
    status=200
    def __init__(self,payload):self.content=json.dumps(payload).encode()
    def read(self,n):return self.content
    def __enter__(self):return self
    def __exit__(self,*args):return False


def square_recipient(req,timeout):
    assert req.full_url=="https://connect.squareupsandbox.com/v2/orders/"+SQ_ORDER
    return Response({"order":{
        "id":SQ_ORDER,"fulfillments":[{"type":"SHIPMENT",
        "shipment_details":{"recipient":{"display_name":"PRIVATE CUSTOMER",
        "address":{"country":"JP","postal_code":"100-0001",
                   "address_line_1":"PRIVATE CUSTOMER ADDRESS"}}}}]}})


def refunded_payment(req,timeout):
    assert req.full_url=="https://connect.squareupsandbox.com/v2/payments/"+PAYMENT
    return Response({"payment":{
        "id":PAYMENT,"order_id":SQ_ORDER,"location_id":LOCATION,"status":"COMPLETED",
        "amount_money":{"amount":21450,"currency":"JPY"},
        "refunded_money":{"amount":21450,"currency":"JPY"}}})


class DraftTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.db=Path(self.tmp.name)/"order.sqlite3"
        self.store=SandboxOrderStore(self.db)
        self.proc=SandboxProcurementOps(self.store)
        self.drafts=SandboxNotificationDrafts(self.store)

    def order(self,*,paid=False):
        _,price=self.store.add_pending_order(
            order_id=ORDER,cart={"A02":1},verified_prices=load_sale_catalog(),
            shipping_yen=0,location_id=LOCATION)
        self.assertEqual(price,21450)
        self.store.save_link(ORDER,{
            "url":"https://sandbox.square.link/u/smoke",
            "square_order_id":SQ_ORDER,"square_link_id":"SQUARELINKTEST12345"})
        if not paid:return
        payment={"id":PAYMENT,"status":"COMPLETED","order_id":SQ_ORDER,
                 "location_id":LOCATION,"amount_money":{"amount":21450,"currency":"JPY"}}
        evt={"event_id":"sandbox-event-100","type":"payment.updated",
             "data":{"object":{"payment":payment}}}
        raw=json.dumps(evt).encode()
        sign_key="fake-key"
        url="https://sandbox.invalid/webhook"
        signature=base64.b64encode(hmac.new(
            sign_key.encode(),url.encode()+raw,hashlib.sha256).digest()).decode()
        self.assertEqual(self.store.accept_webhook(
            raw_body=raw,signature_header=signature,signature_key=sign_key,
            notification_url=url,payment_lookup=lambda payment_id:payment),"paid")

    def command(self,args,*,change=False,opener=None):
        base=["--db",str(self.db)]
        if change:base.append("--confirm-sandbox")
        arg=console.parser().parse_args(base+args)
        return console.execute(arg,env={
            "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE_SANDBOX_TOKEN",
        },opener=opener)

    def test_payment_is_gate_and_draft_generation_is_idempotent(self):
        self.order()
        with self.assertRaises(ValueError):
            self.command(["notification-sync",ORDER],change=True)
        self.assertEqual(self.drafts.pending(),[])
        with self.assertRaises(ValueError):
            self.command(["supplier-ordered",ORDER],change=True)
        self.order(paid=True)
        self.assertEqual(self.command(["notification-sync",ORDER],change=True)
                         ["drafts_created"],3)
        self.assertEqual(self.command(["notification-sync",ORDER],change=True)
                         ["drafts_created"],0)
        preview=self.command(["notifications"])["notifications"]
        self.assertEqual(len(preview),3)
        self.assertEqual({d["audience"] for d in preview},
                         {"operator","supplier","customer"})
        for notice in preview:
            self.assertEqual(notice["status"],"draft_not_sent")
            self.assertTrue(notice["requires_manual_approval"])
            self.assertIsNone(notice["recipient_address"])
            self.assertNotIn("PRIVATE CUSTOMER",json.dumps(notice))
            self.assertNotIn("FAKE_SANDBOX_TOKEN",json.dumps(notice))
        supplier=self.command(["notification-preview",ORDER,
                               "supplier_purchase_request"])["notification"]
        self.assertIn("トランペッツ",supplier["body"])
        self.assertIn("A02",supplier["body"])
        self.assertIn("11.4kg",supplier["body"])
        self.assertIn("まだ発注されていません",supplier["body"])
        self.assertNotIn("19,500",supplier["body"],"no internal ex-tax values")
        self.assertNotIn("21,450",supplier["body"],"no sale prices in supplier draft")
        customer=self.command(["notification-preview",ORDER,
                               "customer_order_confirmed"])["notification"]
        self.assertIn("通常、ご注文・決済完了から4〜7日",customer["body"])
        self.assertIn("全額返金",customer["body"])
        self.assertIn("追加送料：0円",customer["body"])
        with self.assertRaises(ValueError):
            self.command(["notification-preview",ORDER,"customer_refund_completed"])

    def test_supplier_steps_queue_drafts_once_but_never_send(self):
        self.order(paid=True)
        self.command(["notification-sync",ORDER],change=True)
        self.command(["supplier-ordered",ORDER],change=True)
        self.command(["supplier-ordered",ORDER],change=True)
        self.assertEqual(sum(x["kind"]=="operator_supplier_ordered"
                             for x in self.drafts.pending()),1)
        self.command(["supplier-shortage",ORDER],change=True)
        notices={n["kind"]:n for n in self.drafts.pending()}
        self.assertIn("operator_supplier_shortage",notices)
        self.assertIn("customer_supplier_shortage",notices)
        self.assertIn("入荷予定",notices["customer_supplier_shortage"]["body"])
        self.command(["supplier-ordered",ORDER],change=True)
        self.command(["supplier-received",ORDER],change=True)
        self.assertIn("operator_goods_received",{
            n["kind"] for n in self.drafts.pending()})
        with self.assertRaises(SquareSandboxError):
            self.command(["supplier-shipped",ORDER],change=True)
        self.command(["supplier-shipped",ORDER],change=True,opener=square_recipient)
        shipping=self.command(["notification-preview",ORDER,
                               "customer_shipment_notice"])["notification"]
        self.assertIn("配送会社：【運営が確認して入力】",shipping["body"])
        self.assertIn("追跡番号：【運営が確認して入力】",shipping["body"])
        self.assertEqual(len({(n["order_id"],n["kind"])
                             for n in self.drafts.pending()}),
                         len(self.drafts.pending()))
        self.assertNotIn("PRIVATE CUSTOMER",json.dumps(self.drafts.pending()))

    def test_refund_is_not_notified_complete_without_square_proof(self):
        self.order(paid=True)
        self.command(["supplier-shortage",ORDER],change=True)
        self.command(["supplier-refund-review",ORDER],change=True)
        kinds={n["kind"] for n in self.drafts.pending()}
        self.assertIn("operator_refund_action_needed",kinds)
        self.assertNotIn("customer_refund_completed",kinds)
        with self.assertRaises(SquareSandboxError):
            self.command(["supplier-verify-refund",ORDER],change=True)
        self.command(["supplier-verify-refund",ORDER],change=True,
                     opener=refunded_payment)
        completed=self.command(["notification-preview",ORDER,
                                "customer_refund_completed"])["notification"]
        self.assertIn("Squareにて21,450円の全額返金が確認",completed["body"])
        self.assertEqual(completed["status"],"draft_not_sent")


if __name__=="__main__":
    unittest.main()
