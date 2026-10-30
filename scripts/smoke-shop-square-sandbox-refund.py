"""One-shot Square Sandbox ONLY refund of an independently verified fake checkout.

Run only in an explicit GitHub Actions opt-in job AFTER hosted Sandbox
Testing Panel checkout and independently verified Square payment. No real
funds, Square production, messages, customer details or retry on uncertainty.
"""
from __future__ import annotations
import hashlib
import json
import os
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from shop_payments.retail_catalog import load_sale_catalog
from shop_payments.sandbox_connector import SandboxOrderStore, SQUARE_VERSION
from shop_payments.sandbox_reconcile import (
    _fetch_square_sandbox_resource, retrieve_verified_sandbox_payment,
)
from shop_payments.sandbox_connector import completed_payment_matches

BASE = "https://connect.squareupsandbox.com/v2"
ORDER_PRICE = 21450
REF = "refs/heads/feature/dogfood-shop-staging-20261028"


def safe_env(env):
    return (env.get("GITHUB_ACTIONS") == "true"
            and env.get("GITHUB_REF") == REF
            and env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN", "").startswith("EAAA")
            and bool(env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID"))
            and bool(env.get("RUNNER_TEMP")))


def build_refund_request(payment_id, shop_order_id):
    if not isinstance(payment_id, str) or not 8 <= len(payment_id) <= 192:
        raise ValueError("No independently verified Square payment")
    if not isinstance(shop_order_id, str) or not shop_order_id.startswith("FOOD"):
        raise ValueError("No trusted order")
    key = "bigpaw-refund-" + hashlib.sha256(shop_order_id.encode()).hexdigest()[:29]
    assert len(key) <= 45
    return {"idempotency_key": key, "payment_id": payment_id,
            "amount_money": {"amount": ORDER_PRICE, "currency": "JPY"},
            "reason": "BIGPAW SANDBOX TEST ONLY"}


def _post_refund(payload, token, opener=urlopen):
    req = Request(BASE + "/refunds",
                  data=json.dumps(payload, separators=(",", ":")).encode(),
                  method="POST",
                  headers={"Authorization": "Bearer " + token,
                           "Square-Version": SQUARE_VERSION,
                           "Content-Type": "application/json",
                           "Accept": "application/json",
                           "User-Agent": "BIGPAW-Sandbox-Refund-OneShot/1.0"})
    with opener(req, timeout=12) as resp:
        if resp.status not in (200, 201):
            raise RuntimeError("Sandbox refund acceptance unconfirmed")
        data = resp.read(65537)
        if len(data) > 65536:
            raise RuntimeError("Sandbox refund response too large")
        return json.loads(data)


def verify_refund(record, payment_id, square_order_id, location_id):
    # Square may omit order_id/location_id from an initial refund response.
    # If supplied they must match. The independent fresh Square Order and
    # Payment API GET checks above already prove the payment's order/location.
    # Never weaken the required payment ID, JPY amount or refund status checks.
    if not isinstance(record, dict):
        raise ValueError("Refund response missing")
    ref = record.get("refund")
    if (not isinstance(ref, dict) or not isinstance(ref.get("id"), str)
            or not 8 <= len(ref["id"]) <= 192
            or ref.get("payment_id") != payment_id
            or ("order_id" in ref and ref["order_id"] != square_order_id)
            or ("location_id" in ref and ref["location_id"] != location_id)
            or ref.get("amount_money") != {"amount": ORDER_PRICE, "currency": "JPY"}
            or ref.get("status") not in ("PENDING", "COMPLETED")):
        raise ValueError("Refund must match exact independently checked payment")
    return ref["status"]


def run(*, env=None, get_resource=None, get_payment=None, opener=urlopen):
    env = dict(os.environ if env is None else env)
    if not safe_env(env):
        raise ValueError("Not a configured isolated Sandbox-only Actions runner")
    temp = Path(env["RUNNER_TEMP"])
    state = json.loads((temp / "bigpaw-panel.json").read_text())
    if state.get("amount_yen") != ORDER_PRICE or state.get("shipping_yen") != 0:
        raise ValueError("Checkout amount or shipping altered")
    if state.get("location_id") != env["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"]:
        raise ValueError("Sandbox location mismatch")
    shop_order = state["shop_order_id"]
    square_order = state["square_order_id"]
    store = SandboxOrderStore(temp / "bigpaw-panel.sqlite3")
    if store.status(shop_order) != "paid":
        raise ValueError("Trusted local payment verification not completed")

    get_resource = get_resource or (lambda path:
        _fetch_square_sandbox_resource(
            path, token=env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]))
    get_payment = get_payment or (lambda pid:
        retrieve_verified_sandbox_payment(
            pid, token=env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"]))
    remote = get_resource("/orders/" + square_order).get("order", {})
    tenders = remote.get("tenders") if isinstance(remote, dict) else None
    if not isinstance(tenders, list) or len(tenders) != 1:
        raise ValueError("Expected exactly one paid checkout tender")
    payment_id = tenders[0].get("id")
    if not isinstance(payment_id, str):
        raise ValueError("Square tender missing")
    payment = get_payment(payment_id)
    if not isinstance(payment, dict) or payment.get("id") != payment_id:
        raise ValueError("Payment mismatch")
    if not completed_payment_matches(
        {"type": "payment.updated", "data": {"object": {"payment": payment}}},
        square_order_id=square_order, amount_yen=ORDER_PRICE,
        location_id=env["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"],
    ):
        raise ValueError("Square payment is not independently COMPLETED")
    refunded = payment.get("refunded_money")
    if isinstance(refunded, dict) and refunded.get("amount", 0) != 0:
        raise ValueError("Payment already refunded, no second refund")

    # An uncertain POST may already have been accepted. Reserve BEFORE it and
    # NEVER retry automatically, even with an idempotency key.
    marker = temp / "bigpaw-refund-attempted"
    with marker.open("x") as f:
        f.write("one attempt only; outcome may be unknown")
    marker.chmod(0o600)

    request = build_refund_request(payment_id, shop_order)
    response = _post_refund(
        request, env["BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN"], opener=opener)
    accepted = verify_refund(
        response, payment_id, square_order,
        env["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"])
    refund_id = response["refund"]["id"]
    fetched = get_resource("/refunds/" + refund_id)
    state = verify_refund(fetched, payment_id, square_order,
                          env["BIGPAW_SQUARE_SANDBOX_LOCATION_ID"])
    print("SHOP_SANDBOX_REFUND_ACCEPTED=" + accepted)
    print("SHOP_SANDBOX_REFUND_LATEST=" + state)
    print("SHOP_SANDBOX_REFUND_NO_SECOND_POST=true")
    print("SHOP_SANDBOX_NO_REAL_FUNDS=true")
    return state


def main():
    try:
        run()
        return 0
    except Exception:
        # Never reveal payment URL, IDs, tokens or customer info.
        attempted = bool(os.environ.get("RUNNER_TEMP")) and (
            Path(os.environ["RUNNER_TEMP"]) / "bigpaw-refund-attempted").exists()
        print("SHOP_SANDBOX_REFUND_UNVERIFIED=YES; NEVER AUTOMATICALLY RETRY")
        print("SHOP_SANDBOX_REFUND_ATTEMPT_RESERVED=" + str(attempted).lower())
        return 2


if __name__ == "__main__":
    sys.exit(main())
