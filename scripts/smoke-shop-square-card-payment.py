"""Retired Square Sandbox Payment Links direct-card probe (no network).

A Square-hosted Payment Link starts with a DRAFT Order. The supported
simulation is the official Sandbox Testing Panel, not Payments.CreatePayment
directly against the linked Order. Two 2026-10-31 attempts failed with
HTTP 400 BAD_REQUEST; no Payment was created by either attempt.

Standalone fake-card Payments API and hosted-panel tests remain separate
explicitly opted-in workflow jobs. This deprecated entry point never
contacts Square, from its main entry point, regardless of environment or injected dependencies.\nThe callable helper is retained ONLY for the separate standalone Sandbox API job\nand rejects any non-None Order ID before network.
"""
from __future__ import annotations
import sys
import json
import re
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from shop_payments.sandbox_connector import SANDBOX_ENDPOINT, SQUARE_VERSION, SquareSandboxError

_PAYMENT_ENDPOINT = "https://connect.squareupsandbox.com/v2/payments"
_ALLOWED_SOURCE = "cnon:card-nonce-ok"
_EXPECTED_YEN = 21450



def create_fake_card_payment(
    *, order_id: str | None, location_id: str, token: str,
    idempotency_key: str, opener=urlopen
) -> dict:
    """Actual Square Sandbox API call; zero production operations."""
    # This helper exists only for the standalone opt-in API test.
    # Never pay a Payment Links-created DRAFT order directly.
    if order_id is not None:
        raise SquareSandboxError("Hosted Payment Links DRAFT orders must use the Sandbox Testing Panel")
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
            if isinstance(candidate, str) and re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", candidate):
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



def main(*, env=None, link_creator=None, payment_creator=None, payment_reader=None) -> int:
    """Always fail closed before generating a payment link or card charge."""
    print("SQUARE_LINKED_CARD_PROBE_DISABLED: Payment Links orders start as DRAFT; "
          "use the separately opted-in Square Sandbox Testing Panel. "
          "No Square request, charge, or customer-data operation was made.")
    return 2


if __name__ == "__main__":
    sys.exit(main())
