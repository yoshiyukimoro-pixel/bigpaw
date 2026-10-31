"""One-time real Resend delivery test to info@bigpaw.site, isolated GitHub runner.

This test creates NO customer, sale or real Square payment. A completely
synthetic signed Square Sandbox fixture produces exactly one locally 'paid'
test order, marked explicitly TEST-ONLY in email subject/body. Only one
owned operator address may receive it. Never sends to customers/suppliers,
never mutates the production backend, never prints secrets/mail IDs.

Only run once from feature branch GitHub Actions when the marker is set;
missing RESEND_API_KEY exits with status 2 (not a delivered success).
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import hmac
import json
import os
from pathlib import Path
import tempfile
import time

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore
from shop_payments.sandbox_operator_email import (
    SandboxOperatorEmail, SafeMailError, read_resend_delivery, send_resend,
)

BRANCH="refs/heads/feature/dogfood-shop-staging-20261028"
FIXED_ORDER="FOOD"+hashlib.sha256(
    b"bigpaw-shop-info-owner-one-time-notification-2026-10-30"
).hexdigest()[:32]
SQ_ORDER="SANDBOXONLYSHOPORDER123456"
SQ_PAYMENT="SANDBOXONLYPAYMENT123456"
SQ_LOCATION="SANDBOXONLYLOCATION123456"


def fake_verified_order(db: Path) -> SandboxOrderStore:
    """Simulate local verified payment logic; this is NOT a real Square payment."""
    store=SandboxOrderStore(db)
    pricebook=load_sale_catalog()
    _,amount=store.add_pending_order(
        order_id=FIXED_ORDER,cart={"A02":1},verified_prices=pricebook,
        shipping_yen=0,location_id=SQ_LOCATION)
    if amount!=21450:
        raise ValueError("Test-only expected retail amount changed")
    store.save_link(FIXED_ORDER,{
        "url":"https://sandbox.square.link/u/ONE_TIME_EMAIL_FAKE",
        "square_order_id":SQ_ORDER,"square_link_id":"SANDBOXONLYLINK123456",
    })
    fake_payment={
        "id":SQ_PAYMENT,"order_id":SQ_ORDER,
        "location_id":SQ_LOCATION,"status":"COMPLETED",
        "amount_money":{"amount":21450,"currency":"JPY"},
    }
    event={"event_id":"bigpaw-test-owner-mail-only-20261030",
           "type":"payment.updated",
           "data":{"object":{"payment":fake_payment}}}
    payload=json.dumps(event,separators=(",",":")).encode("utf-8")
    callback="https://sandbox-test.invalid/owner-email"
    key="synthetic-not-real-square"
    signature=base64.b64encode(hmac.new(
        key.encode(),callback.encode()+payload,hashlib.sha256,
    ).digest()).decode()
    status=store.accept_webhook(
        raw_body=payload,signature_header=signature,
        signature_key=key,notification_url=callback,
        payment_lookup=lambda _id: fake_payment,
    )
    if status!="paid":
        raise ValueError("Offline synthetic payment fixture failed")
    return store


def run(*, env=None, sender=send_resend, reader=read_resend_delivery,
        sleep=time.sleep, confirm=False) -> int:
    env=os.environ if env is None else env
    if not (
        confirm
        and env.get("GITHUB_ACTIONS")=="true"
        and env.get("GITHUB_REF")==BRANCH
        and env.get("BIGPAW_FOOD_MAIL_ONE_TIME")=="1"
    ):
        print("FOOD_OWNER_MAIL_SMOKE=BLOCKED: not authorized isolated GH feature runner")
        return 3
    api_key=str(env.get("RESEND_API_KEY") or "").strip()
    if not api_key:
        print("FOOD_OWNER_MAIL_SMOKE=NOT_CONFIGURED: isolated runner has no Resend key; no email sent")
        return 2
    try:
        with tempfile.TemporaryDirectory(prefix="bigpaw-food-test-mail-") as folder:
            mail=SandboxOperatorEmail(fake_verified_order(Path(folder)/"test.sqlite3"))
            record=mail.send_once(
                FIXED_ORDER,api_key=api_key,enabled=True,confirmed=True,sender=sender,
            )
            if record["recipient"]!="info@bigpaw.site":
                raise ValueError("Unexpected test destination")
            if not record["new_send"] or record["status"]!="accepted":
                print("FOOD_OWNER_MAIL_SMOKE=ACCEPTANCE_UNCONFIRMED: no second attempt")
                return 1
            print("FOOD_OWNER_MAIL_SMOKE=ACCEPTED: provider accepted 1 test email to info@bigpaw.site")
            result={"provider_event":"unknown"}
            for index in range(7):
                if index:sleep(2)
                try:
                    result=mail.refresh_delivery(
                        FIXED_ORDER,api_key=api_key,reader=reader,
                    )
                except SafeMailError:
                    continue
                if result["provider_event"] in (
                    "delivered","bounced","complained","failed","canceled",
                ):
                    break
            event=result["provider_event"]
            if event=="delivered":
                print("FOOD_OWNER_MAIL_SMOKE=DELIVERED: info@bigpaw.site mail server accepted test; inbox UI not checked")
                return 0
            print("FOOD_OWNER_MAIL_SMOKE=NOT_VERIFIED event="+event+
                  ": provider acceptance is not confirmed delivery")
            return 4
    except (ValueError,SafeMailError,TypeError,KeyError,OSError):
        # Do not print exception details: this test must never leak private IDs
        # or API errors. Importantly we also never retry an ambiguous send.
        print("FOOD_OWNER_MAIL_SMOKE=FAILED_SAFE: test email receipt unverified")
        return 1


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--confirm-once",action="store_true")
    options=parser.parse_args()
    raise SystemExit(run(confirm=options.confirm_once))
