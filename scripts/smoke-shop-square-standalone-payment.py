"""Square Sandbox Payments API credential + fake-card verification, independent of Checkout.

Explicit opt-in; JPY 21,450 simulated test only; no Checkout order and no
customer data. This does NOT prove hosted checkout or webhook delivery.
Never prints the test payment ID, access token, or any card details.
"""
import importlib.util
import os
from pathlib import Path
import secrets
import sys

from shop_payments.sandbox_connector import SquareSandboxError
from shop_payments.sandbox_reconcile import retrieve_verified_sandbox_payment

spec=importlib.util.spec_from_file_location(
    "linked_smoke",Path(__file__).with_name("smoke-shop-square-card-payment.py"))
linked=importlib.util.module_from_spec(spec)
spec.loader.exec_module(linked)


def main(*, env=None, payment_creator=linked.create_fake_card_payment,
         payment_reader=retrieve_verified_sandbox_payment):
    env=os.environ if env is None else env
    token=str(env.get("BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN","")).strip()
    location=str(env.get("BIGPAW_SQUARE_SANDBOX_LOCATION_ID","")).strip()
    if not token or not location:
        print("SQUARE_STANDALONE_SANDBOX_NOT_CONFIGURED")
        return 2
    try:
        result=payment_creator(
            order_id=None,
            location_id=location,token=token,
            idempotency_key="bpapi-"+secrets.token_hex(16),
        )
        if not isinstance(result,dict) or not isinstance(result.get("id"),str):
            raise ValueError("No sandbox payment")
        confirmed=payment_reader(result["id"],token=token)
        amount=confirmed.get("amount_money",{})
        if not (
            confirmed.get("id")==result["id"]
            and confirmed.get("status")=="COMPLETED"
            and confirmed.get("location_id")==location
            and isinstance(amount,dict)
            and type(amount.get("amount")) is int
            and amount["amount"]==21450
            and amount.get("currency")=="JPY"
            and not (isinstance(confirmed.get("refunded_money"),dict) and
                     confirmed["refunded_money"].get("amount",0)>0)
        ):
            raise ValueError("Fresh Sandbox API result mismatched expected JPY payment")
    except (SquareSandboxError,ValueError,TypeError,KeyError):
        print("SQUARE_STANDALONE_SANDBOX_FAILED: no verified completed test payment")
        return 1
    print("SQUARE_STANDALONE_SANDBOX_OK: Square Sandbox API test-card payment "
          "confirmed by independent API GET; JPY 21,450. No real money. "
          "Not linked to the hosted Checkout API order or public webhook.")
    return 0


if __name__=="__main__":
    sys.exit(main())
