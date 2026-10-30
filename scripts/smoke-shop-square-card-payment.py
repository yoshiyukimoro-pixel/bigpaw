"""Explicitly opted-in BIG PAW Square Sandbox *real API* card-payment check.

Never takes real payments: fixed Sandbox endpoint, fixed Square-provided
source_id cnon:card-nonce-ok, test-only location/access token from Actions.
Creates a 1x A02 / JPY 21,450 Sandbox checkout order and attempts an API
card payment against *that same* Square order; retrieves the actual payment
again, checks its amount/location/order and verifies local ledger updates
using a synthetic signed notification. The synthetic notification is NOT
proof that Square delivered a public HTTPS webhook.

No real customer/card/PII data. Never logs tokens, links, payment IDs.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
from pathlib import Path
import secrets
import sys
import tempfile
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import (
    SANDBOX_ENDPOINT, SQUARE_VERSION, SandboxOrderStore, SquareSandboxError,
    create_square_sandbox_payment_link,
)
from shop_payments.sandbox_reconcile import retrieve_verified_sandbox_payment

_PAYMENT_ENDPOINT = "https://connect.squareupsandbox.com/v2/payments"
_ALLOWED_SOURCE = "cnon:card-nonce-ok"
_EXPECTED_YEN = 21450


def create_fake_card_payment(
    *, order_id: str | None, location_id: str, token: str,
    idempotency_key: str, opener=urlopen
) -> dict:
    """Actual Square Sandbox API call; zero production operations."""
    if not SANDBOX_ENDPOINT.startswith("https://connect.squareupsandbox.com/"):
        raise SquareSandboxError("Sandbox link endpoint is not pinned")
    if not location_id or not token or not idempotency_key or (order_id is not None and not order_id):
        raise SquareSandboxError("Missing sandbox payment parameters")
    if not isinstance(idempotency_key,str) or len(idempotency_key) > 45:
        raise SquareSandboxError("Square Payments API idempotency key length invalid")
    body = {
        "idempotency_key": idempotency_key,
        "source_id": _ALLOWED_SOURCE,
        "amount_money": {"amount": _EXPECTED_YEN, "currency": "JPY"},
        "location_id": location_id,
        "autocomplete": True,
    }
    if order_id is not None:
        body["order_id"] = order_id
    request = Request(
        _PAYMENT_ENDPOINT,
        data=json.dumps(body, separators=(",", ":")).encode("utf-8"),
        headers={
            "Authorization": "Bearer " + token,
            "Square-Version": SQUARE_VERSION,
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=12) as response:
            if getattr(response, "status", 200) not in (200, 201):
                raise SquareSandboxError("Sandbox payment API status unexpected")
            data = json.loads(response.read(262144))
    except HTTPError as exc:
        # Only print sanitized provider error CODE and field name. Never print
        # response messages, tokens, order IDs, request headers or payloads.
        code = "UNKNOWN"
        field = "UNSPECIFIED"
        try:
            detail = json.loads(exc.read(4096))
            error = detail.get("errors", [{}])[0]
            candidate = error.get("code", "")
            if isinstance(candidate, str) and re.fullmatch(r"[A-Z_]{3,64}", candidate):
                code = candidate
            candidate = error.get("field", "")
            if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_.\\[\\]-]{1,80}", candidate):
                field = candidate
        except (ValueError, TypeError, KeyError, IndexError):
            pass
        print("SQUARE_SANDBOX_PAYMENTS_HTTP_STATUS=%d CODE=%s FIELD=%s" % (exc.code, code, field))
        raise SquareSandboxError("Square Sandbox CreatePayment HTTP error") from None
    except (URLError, OSError, ValueError, TimeoutError):
        raise SquareSandboxError("Square Sandbox CreatePayment connection unavailable") from None
    payment = data.get("payment") if isinstance(data, dict) else None
    if not isinstance(payment, dict) or not isinstance(payment.get("id"), str):
        raise SquareSandboxError("Square Sandbox did not return payment ID")
    return payment


def _match(payment: dict, *, square_order: str, location: str) -> bool:
    money = payment.get("amount_money", {})
    return bool(
        isinstance(payment, dict) and
        payment.get("status") == "COMPLETED" and
        payment.get("order_id") == square_order and
        payment.get("location_id") == location and
        isinstance(money, dict) and
        type(money.get("amount")) is int and
        money["amount"] == _EXPECTED_YEN and money.get("currency") == "JPY" and
        not (isinstance(payment.get("refunded_money"), dict) and
             payment["refunded_money"].get("amount", 0) > 0)
    )


def main(*, env=None, link_creator=create_square_sandbox_payment_link,
         payment_creator=create_fake_card_payment,
         payment_reader=retrieve_verified_sandbox_payment) -> int:
    env = os.environ if env is None else env
    token = str(env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", "")).strip()
    location = str(env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID", "")).strip()
    if not token or not location:
        print("SQUARE_CARD_SANDBOX_NOT_CONFIGURED: Missing test-only connection")
        return 2
    if ("connect.squareupsandbox.com" not in _PAYMENT_ENDPOINT or
            "connect.squareup.com" in _PAYMENT_ENDPOINT):
        print("SQUARE_CARD_SANDBOX_SAFETY_BLOCK")
        return 3
    stage = "prepare"
    try:
        order_id = "FOOD" + secrets.token_hex(16)
        with tempfile.TemporaryDirectory() as directory:
            store = SandboxOrderStore(Path(directory) / "smoke.sqlite3")
            payload, total = store.add_pending_order(
                order_id=order_id,
                cart={"A02": 1},
                verified_prices=load_sale_catalog(),
                shipping_yen=0,
                location_id=location,
            )
            if total != _EXPECTED_YEN:
                raise ValueError("Sale price changed")
            stage = "create_link"
            link = link_creator(payload, token=token)
            if not link["url"].startswith("https://sandbox.square.link/"):
                raise ValueError("Unsafe Square checkout link")
            store.save_link(order_id, link)
            if store.status(order_id) != "payment_pending":
                raise ValueError("Did not persist pending order")
            stage = "create_payment"
            payment = payment_creator(
                order_id=link["square_order_id"], location_id=location, token=token,
                idempotency_key="bp-link-" + hashlib.sha256(order_id.encode()).hexdigest()[:32],
            )
            if not isinstance(payment, dict) or not payment.get("id"):
                raise ValueError("Square card payment was not created")
            stage = "verify_payment"
            fresh = payment_reader(payment["id"], token=token)
            if (fresh.get("id") != payment["id"] or
                    not _match(fresh, square_order=link["square_order_id"], location=location)):
                raise ValueError("Live Sandbox payment did not match link and amount")

            # Synthetic signed event exercises our journal with a *fresh real*
            # Square Payments API response, but does not test remote delivery.
            simulated = {
                "event_id": "test-" + secrets.token_hex(12),
                "type": "payment.updated",
                "data": {"object": {"payment": fresh}},
            }
            raw = json.dumps(simulated, separators=(",", ":")).encode()
            notification_url = "https://sandbox-test.example.invalid/api/shop/sandbox/webhook"
            signature_key = secrets.token_urlsafe(32)
            signature = base64.b64encode(hmac.new(
                signature_key.encode(),
                notification_url.encode() + raw, hashlib.sha256
            ).digest()).decode()
            stage = "reconcile_local"
            result = store.accept_webhook(
                raw_body=raw, signature_header=signature,
                signature_key=signature_key, notification_url=notification_url,
                payment_lookup=lambda pid: payment_reader(pid, token=token),
            )
            snapshot = store.paid_order_snapshot(order_id)
            if (result != "paid" or store.status(order_id) != "paid" or not snapshot
                    or snapshot.get("square_payment_id") != payment["id"]
                    or snapshot.get("amount_yen") != _EXPECTED_YEN):
                raise ValueError("Verified Sandbox payment not recorded")
            if store.accept_webhook(
                raw_body=raw, signature_header=signature,
                signature_key=signature_key, notification_url=notification_url,
                payment_lookup=lambda pid: payment_reader(pid, token=token),
            ) != "duplicate":
                raise ValueError("Duplicate event was not rejected")
    except (SquareSandboxError, ValueError, KeyError, TypeError):
        # Only reveal the phase, never a token, response body, link or payment ID.
        print("SQUARE_CARD_SANDBOX_FAILED stage=" + stage)
        return 1

    print("SQUARE_CARD_SANDBOX_OK: Actual Square Sandbox fake-card payment verified via API; "
          "JPY 21,450, shipping 0, exact order/location matched, "
          "local signed-event reconciliation and duplicate protection passed. "
          "This was NOT a real charge, hosted checkout card entry, or public webhook delivery.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
