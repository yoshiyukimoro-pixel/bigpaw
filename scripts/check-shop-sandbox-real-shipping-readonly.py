"""Read-only shipping-status check for ONE already-paid Square Sandbox test order.

No new orders, payment, refunds, emails, sender or fulfillment updates.
Never log names, phone numbers, addresses, order IDs, tokens, or payment links.
A missing recipient must remain BLOCKED, never auto-create a placeholder.
"""
from __future__ import annotations
import importlib.util
import os
from pathlib import Path
import sys

path=Path(__file__).with_name("check-shop-real-sandbox-paid-after-stop.py")
spec=importlib.util.spec_from_file_location("paid_after_stop",path)
post=importlib.util.module_from_spec(spec)
spec.loader.exec_module(post)

from shop_payments.sandbox_reconcile import retrieve_sandbox_shipment_status

def check():
    if os.environ.get("BIGPAW_SHOP_SHIPPING_STATUS_READONLY_OPT_IN")!="1":
        raise ValueError("No explicit read-only scope")
    token,location,_=post._scope()
    post.base._assert_square_subscription_safety(token)
    order_id=post._test_link(token)
    result=retrieve_sandbox_shipment_status(order_id,token=token)
    if result.get("square_order_id")!=order_id or type(result.get("shipment_details_complete")) is not bool:
        raise ValueError("Invalid Square response")
    complete=result["shipment_details_complete"]
    print("SHOP_SANDBOX_SHIPPING_ADDRESS="+("COMPLETE" if complete else "INCOMPLETE_BLOCK_DISPATCH"))
    print("SHOP_SANDBOX_EXISTING_PAYMENT_REUSED=READ_ONLY")
    print("SHOP_SANDBOX_ORDER_OR_RECIPIENT_LOGGED=NO")
    print("SHOP_SANDBOX_CUSTOMER_EMAIL_OR_FULFILLMENT_WRITTEN=NO")
    # Missing shipping blocks P04 but does not fail a read-only audit.
    return 0

def main():
    try:
        return check()
    except (ValueError,TypeError,KeyError,OSError,TimeoutError):
        print("SHOP_SANDBOX_SHIPPING_ADDRESS=NOT_VERIFIED")
        return 2
    except Exception:
        print("SHOP_SANDBOX_SHIPPING_ADDRESS=UNAVAILABLE")
        return 2

if __name__=="__main__":
    sys.exit(main())
