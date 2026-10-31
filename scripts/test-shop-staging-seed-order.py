"""No-network tests for manual Square Sandbox test order preparation."""
from pathlib import Path
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor

from shop_payments.sandbox_connector import SandboxOrderStore, SquareSandboxError

from shop_payments.staging_seed_order import prepare_test_checkout, main
from shop_payments.staging_https_webhook import WEBHOOK_PATH

LOCATION="SANDBOX_LOCATION_12345"
ORDER="FOOD"+"c"*32
URL="https://shop-stage.example.invalid"+WEBHOOK_PATH


class SeedOrderTests(unittest.TestCase):
    def setUp(self):
        folder=tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        self.db=str(Path(folder.name)/"sandbox.sqlite3")
        self.env={
            "BIGPAW_ENV":"sandbox",
            "BIGPAW_SHOP_STAGING_ISOLATED":"1",
            "BIGPAW_SHOP_STAGING_HTTPS_ENABLED":"1",
            "BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN":"FAKE_SANDBOX_TOKEN",
            "BIGPAW_SQUARE_SANDBOX_LOCATION_ID":LOCATION,
            "BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY":"FAKE_SIGNATURE",
            "BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL":URL,
            "BIGPAW_SHOP_SANDBOX_DB":self.db,
        }
        self.calls=[]

    def fake_creator(self,payload,*,token):
        self.assertEqual(token,"FAKE_SANDBOX_TOKEN")
        self.assertEqual(payload["order"]["location_id"],LOCATION)
        self.assertEqual(payload["order"]["line_items"][0]["base_price_money"]["amount"],21450)
        self.assertEqual(payload["checkout_options"]["allow_tipping"],False)
        self.calls.append(payload["idempotency_key"])
        return {"url":"https://sandbox.square.link/u/only-test",
                "square_order_id":"SQUARE_ORDER_STAGE_TEST",
                "square_link_id":"SQUARE_LINK_STAGE_TEST"}

    def make(self,**kwargs):
        return prepare_test_checkout(
            env=self.env,db_path=self.db,order_id=ORDER,
            sku="A02",quantity=1,creator=self.fake_creator,**kwargs
        )

    def test_one_test_checkout_is_reused_without_duplicate_square_charge(self):
        result=self.make()
        self.assertEqual(result["amount_yen"],21450)
        self.assertFalse(result["reused"])
        self.assertEqual(result["url"],"https://sandbox.square.link/u/only-test")
        again=self.make()
        self.assertTrue(again["reused"])
        self.assertEqual(again["url"],result["url"])
        self.assertEqual(len(self.calls),1)

    def test_invalid_runtime_product_or_db_prevents_square_network(self):
        for env,db,sku,qty in [
            ({**self.env,"BIGPAW_ENV":"production"},self.db,"A02",1),
            ({**self.env,"BIGPAW_SHOP_STAGING_ISOLATED":"0"},self.db,"A02",1),
            ({**self.env,"RAILWAY_PROJECT_ID":"afb79723-1a2d-4c43-b498-f166e501760c"},self.db,"A02",1),
            (self.env,self.db+"-other","A02",1),
            (self.env,self.db,"INVALID",1),
            (self.env,self.db,"A02",3),
        ]:
            with self.assertRaises(ValueError):
                prepare_test_checkout(env=env,db_path=db,order_id=ORDER,
                                      sku=sku,quantity=qty,creator=self.fake_creator)
        self.assertEqual(self.calls,[])

    def test_uncertain_square_result_never_posts_second_link(self):
        calls = []
        def uncertain(payload, *, token):
            calls.append(payload["idempotency_key"])
            raise SquareSandboxError("Synthetic timeout after unknown Square request")
        with self.assertRaises(SquareSandboxError):
            prepare_test_checkout(
                env=self.env, db_path=self.db, order_id=ORDER,
                sku="A02", quantity=1, creator=uncertain)
        store=SandboxOrderStore(self.db)
        self.assertEqual(store.status(ORDER), "created")
        with self.assertRaises(SquareSandboxError):
            self.make()
        self.assertEqual(len(calls), 1)
        self.assertEqual(len(self.calls), 0)
        with store._open() as db:
            claim=db.execute(
                "SELECT state FROM checkout_link_claims WHERE order_id=?", (ORDER,)
            ).fetchone()
        self.assertEqual(claim["state"], "attempt_unknown")

    def test_concurrent_cli_calls_allow_only_one_square_post(self):
        import threading
        calls=[]
        entered=threading.Event()
        release=threading.Event()
        def blocking_creator(payload, *, token):
            calls.append(payload["idempotency_key"])
            entered.set()
            self.assertTrue(release.wait(timeout=5))
            return {"url":"https://sandbox.square.link/u/only-test",
                    "square_order_id":"SQUARE_ORDER_STAGE_TEST",
                    "square_link_id":"SQUARE_LINK_STAGE_TEST"}
        def try_create():
            try:
                return prepare_test_checkout(
                    env=self.env, db_path=self.db, order_id=ORDER,
                    sku="A02", quantity=1, creator=blocking_creator)
            except SquareSandboxError:
                return "blocked"
        with ThreadPoolExecutor(max_workers=2) as pool:
            first=pool.submit(try_create)
            self.assertTrue(entered.wait(timeout=5))
            second=pool.submit(try_create)
            try:
                self.assertEqual(second.result(timeout=5), "blocked")
            finally:
                release.set()
            self.assertFalse(first.result(timeout=5)["reused"])
        self.assertEqual(len(calls), 1)
        self.assertTrue(self.make()["reused"])
        self.assertEqual(self.calls, [])

    def test_explicit_confirmation_required_by_cli(self):
        self.assertEqual(main(["--sku","A02"],env=self.env),2)


if __name__=="__main__":
    unittest.main()
