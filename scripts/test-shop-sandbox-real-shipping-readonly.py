"""Offline-only no-PII shipping gate tests. No provider connection."""
import importlib.util
from pathlib import Path
from unittest.mock import patch
import unittest

spec=importlib.util.spec_from_file_location(
    "shipping",Path("scripts/check-shop-sandbox-real-shipping-readonly.py"))
m=importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)

class ShippingSafety(unittest.TestCase):
    def test_missing_optin_no_provider_access(self):
        with patch.dict(m.os.environ,{},clear=True),patch.object(m.post,"_scope") as scope:
            self.assertEqual(m.main(),2)
            scope.assert_not_called()
    def test_empty_shipping_blocks_dispatch_but_audit_succeeds(self):
        with patch.dict(m.os.environ,{"BIGPAW_SHOP_SHIPPING_STATUS_READONLY_OPT_IN":"1"}),\
            patch.object(m.post,"_scope",return_value=("fake-token","fake-location","fake-signature")),\
            patch.object(m.post.base,"_assert_square_subscription_safety",return_value=True),\
            patch.object(m.post,"_test_link",return_value="SQ_SANDBOX_ORDER"),\
            patch.object(m,"retrieve_sandbox_shipment_status",return_value={"square_order_id":"SQ_SANDBOX_ORDER","shipment_details_complete":False}):
            self.assertEqual(m.check(),0)
    def test_complete_requires_exact_order(self):
        with patch.dict(m.os.environ,{"BIGPAW_SHOP_SHIPPING_STATUS_READONLY_OPT_IN":"1"}),\
            patch.object(m.post,"_scope",return_value=("fake-token","fake-location","fake-signature")),\
            patch.object(m.post.base,"_assert_square_subscription_safety",return_value=True),\
            patch.object(m.post,"_test_link",return_value="SQ_SANDBOX_ORDER"),\
            patch.object(m,"retrieve_sandbox_shipment_status",return_value={"square_order_id":"WRONG","shipment_details_complete":True}):
            with self.assertRaises(ValueError):m.check()
    def test_no_shipping_write_or_provider_charge(self):
        with patch.dict(m.os.environ,{"BIGPAW_SHOP_SHIPPING_STATUS_READONLY_OPT_IN":"1"}),\
            patch.object(m.post,"_scope",return_value=("fake-token","fake-location","fake-signature")),\
            patch.object(m.post.base,"_assert_square_subscription_safety",return_value=True) as audit,\
            patch.object(m.post,"_test_link",return_value="SQ_SANDBOX_ORDER") as link,\
            patch.object(m,"retrieve_sandbox_shipment_status",return_value={"square_order_id":"SQ_SANDBOX_ORDER","shipment_details_complete":True}) as shipping:
            self.assertEqual(m.check(),0)
            audit.assert_called_once_with("fake-token")
            link.assert_called_once_with("fake-token")
            shipping.assert_called_once_with("SQ_SANDBOX_ORDER",token="fake-token")
if __name__=="__main__":
    unittest.main()
