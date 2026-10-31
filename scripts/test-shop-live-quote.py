"""Offline regression for dormant server-authoritative checkout quote endpoint."""
import hashlib
import hmac
import io
import json
import sys
from pathlib import Path
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "app" / "backend"))
import shop_live_checkout_bridge as bridge
from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.retail_launch_guard import REQUIRED

SECRET = "synthetic-checkout-quote-secret-123456789012345"
TOKEN = "synthetic-buyersession_1234567890_1234567890"
USER = "synthetic-buyer"
TERMS = hashlib.sha256(b"OFFLINE TEST SELLER TERMS").hexdigest()
SITE = "https://bigpaw.site"
CATALOG = load_sale_catalog()


class Handler:
    path = "/api/shop/checkout/quote"
    def __init__(self, payload, role="buyer"):
        raw = json.dumps(payload).encode()
        self.rfile = io.BytesIO(raw)
        self.headers = {
            "Host": "bigpaw.site", "Origin": SITE,
            "Sec-Fetch-Site": "same-origin",
            "Content-Type": "application/json",
            "Content-Length": str(len(raw)),
            "Cookie": "bigpaw_session=" + TOKEN,
            "X-Shop-CSRF": bridge._csrf(SECRET,TOKEN,USER),
        }
        self.role = role
        self.auth_reads = 0
        self.responses = []
    def current_user(self):
        self.auth_reads += 1
        return {"id":USER,"role":self.role}
    def send_json(self,payload,status=200):
        self.responses.append((status,payload))
    @property
    def code(self):
        return self.responses[-1][0]


class Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.env = {
            "BIGPAW_ENV":"production",
            "BIGPAW_SHOP_PUBLIC_LIVE_ENABLED":"1",
            "BIGPAW_SHOP_OWNER_LAUNCH_APPROVED":"1",
            "BIGPAW_SHOP_ORDER_HMAC_SECRET":SECRET,
            "BIGPAW_SHOP_APPROVED_TERMS_SHA256":TERMS,
            "BIGPAW_SQUARE_LIVE_ACCESS_TOKEN":"FAKE_SQUARE_TOKEN_NEVER_REAL_123456789",
            "BIGPAW_SQUARE_LIVE_LOCATION_ID":"SYNTHETIC_LOCATION_123",
            "BIGPAW_SHOP_SQUARE_LIVE_WEBHOOK_ENABLED":"1",
            "BIGPAW_SQUARE_LIVE_WEBHOOK_URL":SITE+"/api/shop/square-webhook",
            "BIGPAW_SQUARE_LIVE_WEBHOOK_SIGNATURE_KEY":"FAKE_SIGNING_KEY_NEVER_REAL_123456789012345",
        }
        self.status = {
            "business_structure":"individual_proprietor",
            "sandbox_only":True,
            "public_live_checkout_enabled":False,
            "launch_checks":{k:True for k in REQUIRED},
        }
    def quote(self,cart,*,env=None,status="synthetic",terms=TERMS,mutate=None):
        h=Handler({"cart":cart,"terms_sha256":terms})
        if mutate:
            mutate(h)
        bridge.handle_post(
            h,env=self.env if env is None else env,base_url=SITE,
            data_dir=Path(self.temp.name),rate_limited=lambda *a:False,
            launch_status=self.status if status=="synthetic" else status,
        )
        return h
    def assert_no_mutations(self):
        self.assertEqual(list(Path(self.temp.name).iterdir()),[])
    def test_current_manifest_always_disabled_before_read(self):
        h=self.quote({"A02":1},status=None)
        self.assertEqual(h.code,404)
        self.assertEqual(h.auth_reads,0)
        self.assertEqual(h.rfile.tell(),0)
        self.assert_no_mutations()
    def test_all_35_products_and_mixed_cart_price_match(self):
        h=self.quote({id:1 for id in CATALOG})
        self.assertEqual(h.code,200)
        result=h.responses[-1][1]
        total=sum(v.sale_price_yen for v in CATALOG.values())
        self.assertEqual((result["amount_yen"],result["shipping_yen"]),(total,0))
        self.assertEqual(result["terms_sha256"],TERMS)
        self.assertEqual(result["currency"],"JPY")
        self.assertTrue(result["server_verified"])
        self.assertFalse(result["payment_link_created"])
        self.assertEqual(len(result["line_items"]),35)
        for row in result["line_items"]:
            self.assertEqual(row["unit_yen"],CATALOG[row["sku"]].sale_price_yen)
            self.assertEqual(row["line_yen"],row["unit_yen"])
        mixed=self.quote({"A02":2,"Z01":1})
        self.assertEqual(mixed.code,200)
        self.assertEqual(mixed.responses[-1][1]["amount_yen"],85800)
        self.assert_no_mutations()
    def test_stale_terms_tampered_prices_invalid_buyer_blocked(self):
        self.assertEqual(self.quote({"A02":1},terms="0"*64).code,409)
        for cart in ({"A02":False},{"A02":1.2},{"X99":1},{}):
            self.assertEqual(self.quote(cart).code,400)
        h=self.quote({"A02":1},mutate=lambda h:h.headers.update(
            {"Origin":"https://evil.invalid"}))
        self.assertEqual(h.code,403)
        h=self.quote({"A02":1},mutate=lambda h:h.headers.update(
            {"X-Shop-CSRF":"bad"}))
        self.assertEqual(h.code,403)
        h=self.quote({"A02":1},mutate=lambda h:setattr(h,"role","breeder"))
        self.assertEqual(h.code,401)
        h=self.quote({"A02":1},mutate=lambda h:h.headers.update(
            {"Transfer-Encoding":"chunked"}))
        self.assertEqual(h.code,400)
        self.assert_no_mutations()
    def test_extra_browser_amount_rejected(self):
        def inject_client_total(h):
            raw=json.dumps({"cart":{"A02":1},
                            "terms_sha256":TERMS,"amount_yen":1}).encode()
            h.rfile=io.BytesIO(raw)
            h.headers["Content-Length"]=str(len(raw))
        h=self.quote({"A02":1},mutate=inject_client_total)
        self.assertEqual(h.code,400)
        self.assert_no_mutations()
    def test_live_route_is_present_but_unapproved(self):
        source=(Path(__file__).resolve().parents[1] /
                "app/backend/server.py").read_text(encoding="utf-8")
        self.assertIn("'/api/shop/checkout/quote'",source)
        self.assertIn("handle_quote_post(",(Path(__file__).resolve().parents[1] /
                "app/backend/shop_live_checkout_bridge.py").read_text(encoding="utf-8"))

if __name__=="__main__":
    unittest.main()
