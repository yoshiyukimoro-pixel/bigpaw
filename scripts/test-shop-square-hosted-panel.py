"""Offline safety checks for opted-in hosted Checkout Sandbox panel probe."""
import ast
from pathlib import Path
import unittest

class PanelSmokeSafety(unittest.TestCase):
    def test_checkout_panel_scripts_do_not_target_production(self):
        py = Path("scripts/smoke-shop-square-hosted-panel.py").read_text()
        js = Path("scripts/smoke-shop-square-hosted-panel.cjs").read_text()
        ast.parse(py)
        self.assertIn("connect.squareupsandbox.com", js)
        self.assertNotIn("connect.squareup.com", py)
        self.assertNotIn("connect.squareup.com", js)
        self.assertIn("sandbox.square.link", js)
        self.assertIn("Square Sandbox", py)
        self.assertIn("order_id", py)
        self.assertIn("payment_lookup=lambda pid:", py)
        self.assertIn("checkout", js.lower())
        self.assertNotIn("console.log(link.href)", js)
        self.assertNotIn("console.log(page.url())", js)
    def test_actions_branch_opt_in(self):
        workflow=Path(".github/workflows/square-sandbox-smoke.yml").read_text()
        self.assertIn("feature/dogfood-shop-staging-20261028", workflow)
        self.assertIn("run_sandbox_panel_smoke", workflow)
        self.assertIn("[square-panel-smoke]", workflow)
        self.assertIn("scripts/smoke-shop-square-hosted-panel.py",workflow)
        self.assertIn("scripts/smoke-shop-square-hosted-panel.cjs",workflow)

if __name__=="__main__":
    unittest.main()
