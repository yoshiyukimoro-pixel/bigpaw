"""Offline-only HTML operator dashboard regression; never serves on the web."""
import importlib.util
import io
import contextlib
import os
from pathlib import Path
import stat
import tempfile
import unittest

from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.sandbox_fulfillment import SandboxFulfillmentOps

spec=importlib.util.spec_from_file_location(
    "operator_dashboard",Path("scripts/render-shop-sandbox-orders.py"))
dashboard=importlib.util.module_from_spec(spec)
spec.loader.exec_module(dashboard)


class OperatorDashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.db=Path(self.temp.name)/"test-orders.sqlite3"
        self.orders=SandboxOrderStore(self.db)
        self.ops=SandboxFulfillmentOps(self.orders)

    def test_read_only_private_dashboard_and_35_skus(self):
        output=Path(self.temp.name)/"private-orders.html"
        with contextlib.redirect_stdout(io.StringIO()) as stream:
            result=dashboard.main(["--db",str(self.db),"--out",str(output)])
        self.assertEqual(result,0)
        self.assertIn("SANDBOX_REPORT_OK",stream.getvalue())
        self.assertEqual(stat.S_IMODE(output.stat().st_mode),0o600)
        html=output.read_text(encoding="utf-8")
        self.assertIn("BIG PAW",html)
        self.assertIn("Sandbox",html)
        self.assertIn("注文一覧",html)
        self.assertIn("追加送料",html)
        self.assertIn("35商品の手元在庫",html)
        self.assertIn("仕入・入荷状況",html)
        self.assertIn("通知の未送信下書き",html)
        self.assertIn("運営・仕入先・お客様向け通知下書き",html)
        self.assertIn("info@bigpaw.site 運営メール配信状況",html)
        self.assertIn("サービス受付状況",html)
        self.assertIn("配達未確認",Path("scripts/render-shop-sandbox-orders.py").read_text())
        self.assertIn("メール・LINEの自動送信や仕入先への発注は行いません",html)
        self.assertIn("仕入先への発注待ち",html)
        self.assertIn("通常4〜7日程度",html)
        self.assertIn("受注発注",html)
        self.assertIn("A02",html)
        self.assertIn("ZIWI",html.upper())
        self.assertNotIn("Square Access Token",html)
        self.assertNotIn("<script",html)
        self.assertNotIn("fetch(",html)
        self.assertNotIn("http://",html)
        self.assertNotIn("https://",html)
        self.assertNotIn("PRIVATE ADDRESS",html)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(
                dashboard.main(["--db",str(self.db),"--out",str(output)]),1,
                "must never silently overwrite private previous report",
            )

    def test_cannot_write_dashboard_into_public_shop(self):
        forbidden=Path(__file__).resolve().parents[1]/"app/shop-orders-live.html"
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(dashboard.main(
                ["--db",str(self.db),"--out",str(forbidden)]),1)
        self.assertFalse(forbidden.exists())


if __name__=="__main__":
    unittest.main()
