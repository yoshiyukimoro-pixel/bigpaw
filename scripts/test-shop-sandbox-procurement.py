"""Offline buy-to-order procurement and shortage tests. No supplier orders are sent."""
from __future__ import annotations
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
from shop_payments.sandbox_procurement import SandboxProcurementOps

spec=importlib.util.spec_from_file_location(
    "sandbox_operator",Path("scripts/shop-sandbox-operator.py"))
console=importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)
LOCATION="SANDBOXLOCATION12345"
ORDER="FOOD"+"a"*32
SQUARE="SQUAREORDER12345"
PAYMENT="SQUAREPAYMENT12345"


class Response:
    status=200
    def __init__(self,data):self.data=json.dumps(data).encode()
    def __enter__(self):return self
    def __exit__(self,*args):return False
    def read(self,n):return self.data


def shipping_opener(*,complete=True):
    def get(req,timeout):
        assert req.get_method()=="GET"
        assert req.full_url=="https://connect.squareupsandbox.com/v2/orders/"+SQUARE
        recipient={"display_name":"PRIVATE PERSON","address":{
            "country":"JP","address_line_1":"PRIVATE STREET" if complete else "",
            "postal_code":"100-0001"}}
        return Response({"order":{"id":SQUARE,"fulfillments":[{
            "type":"SHIPMENT","shipment_details":{"recipient":recipient}}]}})
    return get


def payment_opener(*,amount=21450):
    def get(req,timeout):
        assert req.get_method()=="GET"
        assert req.full_url=="https://connect.squareupsandbox.com/v2/payments/"+PAYMENT
        return Response({"payment":{
            "id":PAYMENT,"order_id":SQUARE,"location_id":LOCATION,
            "status":"COMPLETED","amount_money":{"amount":21450,"currency":"JPY"},
            "refunded_money":{"amount":amount,"currency":"JPY"},
        }})
    return get


class ProcurementTests(unittest.TestCase):
    def setUp(self):
        temp=tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.db=Path(temp.name)/"sandbox.sqlite3"
        self.store=SandboxOrderStore(self.db)
        self.proc=SandboxProcurementOps(self.store)

    def order(self,paid=True):
        payload,amount=self.store.add_pending_order(
            order_id=ORDER,cart={"A02":1},
            verified_prices=load_sale_catalog(),shipping_yen=0,location_id=LOCATION)
        self.assertEqual(amount,21450)
        self.store.save_link(ORDER,{
            "url":"https://sandbox.square.link/u/test",
            "square_order_id":SQUARE,"square_link_id":"LINKTEST12345"})
        if not paid:return
        payment={"id":PAYMENT,"status":"COMPLETED","order_id":SQUARE,
                 "location_id":LOCATION,"amount_money":{
                    "amount":amount,"currency":"JPY"}}
        event={"event_id":"test-event-1234","type":"payment.updated",
               "data":{"object":{"payment":payment}}}
        raw=json.dumps(event).encode()
        url="https://webhook.invalid/bigpaw"
        key="fake_test_sign_key"
        signature=base64.b64encode(hmac.new(
            key.encode(),url.encode()+raw,hashlib.sha256).digest()).decode()
        self.assertEqual(self.store.accept_webhook(
            raw_body=raw,signature_header=signature,signature_key=key,
            notification_url=url,payment_lookup=lambda pid:payment),"paid")

    def command(self,action,*,confirm=False,opener=None):
        prefix=["--db",str(self.db)]
        if confirm:prefix.append("--confirm-sandbox")
        args=console.parser().parse_args(prefix+[action,ORDER])
        return console.execute(args,env={
            "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"fake-token",
        },opener=opener)

    def test_payment_needed_before_any_supplier_order_and_shipment(self):
        self.order(paid=False)
        self.assertEqual(self.proc.state(ORDER),"payment_not_verified")
        with self.assertRaises(ValueError):
            self.proc.transition(ORDER,"supplier_ordered")
        with self.assertRaises(ValueError):
            self.command("supplier-ordered",confirm=True)
        self.assertEqual(self.proc.events(),[])
        self.assertEqual(self.command("supplier-status")["state"],"payment_not_verified")

    def test_supplier_order_receive_ship_without_preexisting_stock(self):
        self.order()
        self.assertEqual(self.proc.state(ORDER),"awaiting_supplier_order")
        self.assertEqual(self.command("supplier-status")["state"],"awaiting_supplier_order")
        with self.assertRaises(ValueError):
            self.command("supplier-ordered")
        result=self.command("supplier-ordered",confirm=True)
        self.assertEqual(result["procurement_state"],"supplier_ordered")
        self.assertFalse(result["supplier_order_executed"])  # internal record only
        self.assertEqual(self.command("supplier-ordered",confirm=True)["procurement_state"],"supplier_ordered")
        with self.assertRaises(ValueError):
            self.command("supplier-shipped",confirm=True,opener=shipping_opener())
        self.assertEqual(self.command("supplier-received",confirm=True)["procurement_state"],
                         "received_at_shop")
        with self.assertRaises(ValueError):
            self.command("supplier-shipped",confirm=True,opener=shipping_opener(complete=False))
        recorded=self.command("supplier-shipped",confirm=True,opener=shipping_opener())
        self.assertEqual(recorded["procurement_state"],"shipped")
        self.assertFalse(recorded["shipping_executed"])
        self.assertEqual(self.proc.state(ORDER),"shipped")
        self.assertEqual([x["stage"] for x in self.proc.events(ORDER)],
                         ["supplier_ordered","received_at_shop","shipped"])
        with self.assertRaises(ValueError):
            self.command("supplier-refund-review",confirm=True)
        # Staging stock wasn't set. No 0-stock restriction for paid buy-to-order.
        self.assertEqual(self.command("list")["orders"][0]["procurement_state"],"shipped")

    def test_shortage_then_supplier_available_or_full_refund(self):
        self.order()
        self.assertEqual(self.command("supplier-shortage",confirm=True)["procurement_state"],
                         "supplier_backorder")
        self.assertEqual(self.command("supplier-ordered",confirm=True)["procurement_state"],
                         "supplier_ordered")
        self.assertEqual(self.command("supplier-shortage",confirm=True)["procurement_state"],
                         "supplier_backorder")
        self.assertEqual(self.command("supplier-refund-review",confirm=True)["procurement_state"],
                         "refund_review")
        with self.assertRaises(ValueError):
            self.command("supplier-ordered",confirm=True)
        with self.assertRaises(ValueError):
            self.command("supplier-verify-refund",confirm=True,
                         opener=payment_opener(amount=10))
        self.assertEqual(self.proc.state(ORDER),"refund_review")
        reconciled=self.command("supplier-verify-refund",confirm=True,
                                opener=payment_opener())
        self.assertEqual(reconciled["procurement_state"],"refunded")
        self.assertFalse(reconciled["refund_initiated"])
        self.assertEqual(self.command("supplier-verify-refund",confirm=True,
                                opener=payment_opener())["procurement_state"],"refunded")
        self.assertEqual([r["stage"] for r in self.proc.events(ORDER)].count("refunded"),1)
        self.assertNotIn("PRIVATE",json.dumps(self.command("list")))
        self.assertNotIn("PRIVATE",json.dumps(self.command("events")))

    def test_no_transition_from_paid_to_refunded_without_review(self):
        self.order()
        with self.assertRaises(ValueError):
            self.proc.transition(ORDER,"refunded")
        with self.assertRaises(ValueError):
            self.proc.confirm_full_refund(ORDER,token="fake",opener=payment_opener())
        self.assertEqual(self.proc.events(),[])


if __name__=="__main__":
    unittest.main()
