"""Opt-in actual Square Checkout Sandbox Testing Panel session.

setup: Create 1x A02 checkout link in Square Sandbox and save an ephemeral
session in RUNNER_TEMP (no link, token or identifiers printed).
verify: Re-read Square order/tender/payment from Sandbox API, verify exact
snapshot, and reconcile order journal using a *synthetic* signed event.
External Square-to-HTTPS webhook delivery remains untested.

Never uses production endpoint or real payment methods.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import secrets
import sys

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import (
    SandboxOrderStore, SquareSandboxError, create_square_sandbox_payment_link,
    completed_payment_matches,
)
from shop_payments.sandbox_reconcile import (
    retrieve_verified_sandbox_payment, retrieve_sandbox_shipment_status,
    _fetch_square_sandbox_resource,
)

BASE = "https://connect.squareupsandbox.com"
PRICE = 21450


def _home() -> Path:
    temp = os.environ.get("RUNNER_TEMP", "")
    if not temp:
        raise ValueError("Run only inside an isolated Actions runner")
    return Path(temp)


def _config() -> tuple[str,str]:
    token = os.environ.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", "").strip()
    location = os.environ.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID", "").strip()
    if not token or not location:
        raise ValueError("Sandbox credentials missing")
    return token,location


def setup() -> None:
    token,location=_config()
    home=_home()
    home.mkdir(parents=True,exist_ok=True)
    store=SandboxOrderStore(home/"bigpaw-panel.sqlite3")
    order_id="FOOD"+secrets.token_hex(16)
    payload,amount=store.add_pending_order(
        order_id=order_id,cart={"A02":1},verified_prices=load_sale_catalog(),
        shipping_yen=0,location_id=location)
    if amount!=PRICE:
        raise ValueError("Pricebook mismatch")
    # Reserve this attempt durably before contacting Square. Unknown
    # transport outcomes must never trigger an implicit second link.
    store.claim_checkout_link_attempt(order_id)
    link=create_square_sandbox_payment_link(payload,token=token)
    if not link["url"].startswith("https://sandbox.square.link/"):
        raise ValueError("Unsafe Square link")
    store.save_link(order_id,link)
    state={
        "shop_order_id":order_id,"square_order_id":link["square_order_id"],
        "link_url":link["url"],"location_id":location,
        "amount_yen":amount,"shipping_yen":0,
    }
    location_file=home/"bigpaw-panel.json"
    location_file.write_text(json.dumps(state),encoding="utf-8")
    location_file.chmod(0o600)
    print("SQUARE_CHECKOUT_PANEL_CREATED: authentic sandbox link, immutable "
          "1x A02 order, JPY 21,450 including tax and shipping. No URL exposed.")


def verify() -> None:
    token,location=_config()
    home=_home()
    state=json.loads((home/"bigpaw-panel.json").read_text(encoding="utf-8"))
    if (state.get("location_id")!=location or state.get("amount_yen")!=PRICE
            or state.get("shipping_yen")!=0):
        raise ValueError("Local checkout snapshot changed")
    shop_order_id=state["shop_order_id"]
    sq_order=state["square_order_id"]
    store=SandboxOrderStore(home/"bigpaw-panel.sqlite3")
    if store.status(shop_order_id)!="payment_pending":
        raise ValueError("Local order is not payment_pending")
    order_data=_fetch_square_sandbox_resource("/orders/"+sq_order,token=token)
    order=order_data.get("order")
    if not isinstance(order,dict) or order.get("id")!=sq_order:
        raise ValueError("Square order mismatch")
    status = order.get("state")
    safe_status = status if status in ("DRAFT","OPEN","COMPLETED","CANCELED") else "UNKNOWN"
    print("SQUARE_CHECKOUT_PANEL_ORDER_STATE="+safe_status)
    if order.get("state")!="OPEN":
        raise ValueError("Square checkout order not OPEN")
    tenders=order.get("tenders")
    print("SQUARE_CHECKOUT_PANEL_TENDERS="+str(len(tenders) if isinstance(tenders,list) else 0))
    if not isinstance(tenders,list) or len(tenders)!=1:
        raise ValueError("No unique payment tender recorded by Square")
    payment_id=tenders[0].get("id")
    if not isinstance(payment_id,str):
        raise ValueError("Tender does not reference a Square payment")
    payment=retrieve_verified_sandbox_payment(payment_id,token=token)
    if payment.get("id")!=payment_id or not completed_payment_matches(
        {"type":"payment.updated","data":{"object":{"payment":payment}}},
        square_order_id=sq_order,amount_yen=PRICE,location_id=location,
    ):
        raise ValueError("Square Payments API does not confirm this checkout")
    refunded=payment.get("refunded_money",{})
    if isinstance(refunded,dict) and refunded.get("amount",0)>0:
        raise ValueError("Square payment refunded")

    # The real hosted Sandbox panel can finish a fake payment without the
    # shipping form. Verify a FRESH Square Orders GET, and reveal only one
    # boolean; never print or persist the recipient, postal code or address.
    # Missing shipping is a separate blocker, not a failed charge. Do not
    # treat payment acceptance as permission to dispatch goods.
    shipping = retrieve_sandbox_shipment_status(sq_order, token=token)
    shipping_complete = shipping.get("shipment_details_complete") is True
    print("SQUARE_CHECKOUT_PANEL_SHIPPING="
          + ("COMPLETE" if shipping_complete else "INCOMPLETE"))
    if not shipping_complete:
        print("SQUARE_CHECKOUT_PANEL_SHIPPING_BLOCKED: "
              "manual shipping evidence needed before fulfillment; no PII")

    # This is an artificial event to test the local ledger. It is NOT an
    # externally delivered Square webhook.
    event={"event_id":"panel-check-"+secrets.token_hex(10),
           "type":"payment.updated","data":{"object":{"payment":payment}}}
    body=json.dumps(event,separators=(",",":")).encode("utf-8")
    signature_key=secrets.token_urlsafe(32)
    notification_url="https://sandbox-webhook.invalid/bigpaw"
    signature=base64.b64encode(hmac.new(
        signature_key.encode(),notification_url.encode()+body,hashlib.sha256
    ).digest()).decode()
    result=store.accept_webhook(
        raw_body=body,signature_header=signature,
        signature_key=signature_key,notification_url=notification_url,
        payment_lookup=lambda pid: retrieve_verified_sandbox_payment(pid,token=token),
    )
    snapshot=store.paid_order_snapshot(shop_order_id)
    if (result!="paid" or store.status(shop_order_id)!="paid"
            or not snapshot or snapshot.get("square_payment_id")!=payment_id
            or snapshot.get("cart")!={"A02":1} or snapshot.get("amount_yen")!=PRICE):
        raise ValueError("Failed to update verified checkout order journal")
    print("SQUARE_HOSTED_CHECKOUT_VERIFIED: Square Sandbox panel payment "
          "completed; Square Orders and Payments APIs confirm the SAME order, "
          "location, JPY 21,450, zero shipping. Local order journal updated "
          "from pending to paid using an artificial signed event. "
          "NO real funds and NO public webhook delivery test.")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("phase",choices=["setup","verify"])
    opt=parser.parse_args()
    try:
        if opt.phase=="setup":setup()
        else:verify()
    except (SquareSandboxError,ValueError,KeyError,TypeError,OSError,
            json.JSONDecodeError) as exc:
        # Deliberately NEVER print exception details, which can expose IDs/PII.
        print("SQUARE_CHECKOUT_PANEL_FAILED stage="+opt.phase)
        return 1
    return 0

if __name__=="__main__":
    sys.exit(main())
