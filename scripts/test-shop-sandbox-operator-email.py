"""Safe, offline operator email tests: never send or look up real mail."""
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
from shop_payments.sandbox_notifications import SandboxNotificationDrafts
from shop_payments.sandbox_operator_email import (
    SandboxOperatorEmail,send_resend,SafeMailError,
)

spec=importlib.util.spec_from_file_location(
    "operator",Path("scripts/shop-sandbox-operator.py"))
console=importlib.util.module_from_spec(spec)
spec.loader.exec_module(console)

ORDER="FOOD"+"d"*32
SQ="SQUAREORDER12345"
LOC="SQUARELOCATION12345"
PAYMENT="SQUAREPAYMENT12345"


class MockResponse:
    status=200
    def __enter__(self):return self
    def __exit__(self,*args):return None
    def read(self,n):return json.dumps({"id":"mock-resend-mail-123456"}).encode()


class OperatorMailTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.db=Path(temporary.name)/"shop-sandbox.sqlite3"
        self.store=SandboxOrderStore(self.db)
        self.notifications=SandboxNotificationDrafts(self.store)
        self.mail=SandboxOperatorEmail(self.store)
        self.sent=[]

    def paid_order(self,paid):
        payload,total=self.store.add_pending_order(
            order_id=ORDER,cart={"A02":1},
            verified_prices=load_sale_catalog(),shipping_yen=0,location_id=LOC,
        )
        self.assertEqual(total,21450)
        self.store.save_link(ORDER,{
            "url":"https://sandbox.square.link/u/mock",
            "square_order_id":SQ,"square_link_id":"SQUARELINK12345",
        })
        if not paid:return
        payment={"id":PAYMENT,"status":"COMPLETED","order_id":SQ,
                 "location_id":LOC,"amount_money":{"amount":21450,"currency":"JPY"}}
        evt={"event_id":"mail-test-event-1234","type":"payment.updated",
             "data":{"object":{"payment":payment}}}
        body=json.dumps(evt).encode()
        signing_key="fake-test-webhook-key";notification_url="https://test.invalid/callback"
        signature=base64.b64encode(hmac.new(
            signing_key.encode(),notification_url.encode()+body,
            hashlib.sha256).digest()).decode()
        self.assertEqual(self.store.accept_webhook(
            raw_body=body,signature_header=signature,
            signature_key=signing_key,notification_url=notification_url,
            payment_lookup=lambda _pid:payment,
        ),"paid")
        # The verified payment automatically inserts exactly 3 drafts.
        self.assertEqual(len(self.notifications.pending()),3)

    def sender(self,*,api_key,to,subject,body,idempotency_key):
        self.sent.append({"api_key":api_key,"to":to,"subject":subject,
                          "body":body,"idempotency_key":idempotency_key})
        return "mock-resend-mail-123456"

    def operator(self,cmd,*,confirm=False,enabled=False,credentials=True,sender=None):
        args=["--db",str(self.db)]
        if confirm:args.append("--confirm-sandbox")
        args.extend(cmd)
        parsed=console.parser().parse_args(args)
        env={
            "BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED":"1" if enabled else "0",
            "RESEND_API_KEY":"fake-staging-key" if credentials else "",
        }
        return console.execute(parsed,env=env,mail_sender=sender or self.sender)

    def test_payment_required_prevents_emails_and_reservations(self):
        self.paid_order(paid=False)
        with self.assertRaises(ValueError):
            self.operator(["notification-send-operator",ORDER],confirm=True,enabled=True)
        self.assertEqual(self.sent,[])
        self.assertEqual(self.mail.history(),[])

    def test_requires_both_explicit_operator_opt_in_and_environment_gate(self):
        self.paid_order(paid=True)
        for confirm,enabled,credentials in [
            (False,True,True),(True,False,True),(True,True,False)]:
            with self.assertRaises((SafeMailError,ValueError)):
                self.operator(["notification-send-operator",ORDER],
                              confirm=confirm,enabled=enabled,credentials=credentials)
        self.assertEqual(self.sent,[])
        self.assertEqual(self.mail.history(),[])

    def test_send_once_to_fixed_bigpaw_address_and_never_duplicate(self):
        self.paid_order(paid=True)
        first=self.operator(["notification-send-operator",ORDER],
                            confirm=True,enabled=True)
        self.assertEqual(first["recipient"],"info@bigpaw.site")
        self.assertEqual(first["status"],"accepted")
        self.assertFalse(first["delivered_to_inbox"])
        self.assertFalse(first["delivery_status_verified"])
        self.assertTrue(first["new_send"])
        self.assertEqual(len(self.sent),1)
        self.assertEqual(self.sent[0]["to"],"info@bigpaw.site")
        self.assertIn("Sandbox",self.sent[0]["subject"])
        self.assertIn("実際のお客様からの注文・入金ではありません",self.sent[0]["body"])
        self.assertIn("トランペッツへ発注しないでください",self.sent[0]["body"])
        self.assertIn("21,450円",self.sent[0]["body"])
        self.assertIn(ORDER,self.sent[0]["idempotency_key"])
        self.assertNotIn("PRIVATE",json.dumps(self.sent))
        second=self.operator(["notification-send-operator",ORDER],
                             confirm=True,enabled=True)
        self.assertFalse(second["new_send"])
        self.assertEqual(len(self.sent),1)
        self.assertEqual(len(self.mail.history()),1)
        self.assertEqual(self.mail.history()[0]["status"],"accepted")

    def test_ambiguous_sender_failure_never_retries(self):
        self.paid_order(paid=True)
        attempts=[]
        def timeout_sender(**kwargs):
            attempts.append(kwargs)
            raise TimeoutError("simulated timeout")
        initial=self.operator(["notification-send-operator",ORDER],
                              confirm=True,enabled=True,sender=timeout_sender)
        self.assertEqual(initial["status"],"unknown")
        result=self.operator(["notification-send-operator",ORDER],
                             confirm=True,enabled=True)
        self.assertEqual(result["status"],"unknown")
        self.assertFalse(result["new_send"])
        self.assertEqual(len(attempts),1)
        self.assertEqual(self.sent,[])

    def test_resend_transport_sends_only_fixed_target_with_idempotency(self):
        requests=[]
        def fake_network(req,timeout):
            requests.append(req)
            self.assertEqual(req.full_url,"https://api.resend.com/emails")
            self.assertEqual(req.get_method(),"POST")
            payload=json.loads(req.data)
            self.assertEqual(payload["from"],"BIG PAW <noreply@bigpaw.site>")
            self.assertEqual(payload["to"],["info@bigpaw.site"])
            self.assertIn("Idempotency-key",dict(req.header_items()))
            self.assertEqual(timeout,10)
            return MockResponse()
        id_=send_resend(
            api_key="mock-key",to="info@bigpaw.site",
            subject="[Sandbox] new order",body="Sample only",
            idempotency_key="bigpaw-shop-sandbox-operator-new-order/"+ORDER,
            opener=fake_network,
        )
        self.assertEqual(id_,"mock-resend-mail-123456")
        self.assertEqual(len(requests),1)
        with self.assertRaises(SafeMailError):
            send_resend(
                api_key="mock-key",to="untrusted@example.com",
                subject="Not allowed",body="Not allowed",
                idempotency_key="bigpaw-shop-sandbox-operator-new-order/"+ORDER,
                opener=fake_network,
            )
        self.assertEqual(len(requests),1)


if __name__=="__main__":
    unittest.main()
