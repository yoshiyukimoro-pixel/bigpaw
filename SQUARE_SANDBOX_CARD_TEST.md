# BIG PAW Square Sandbox card test (staging only)

Date: 2026-10-29. Draft PR #175. This test never collects real funds.

## Purpose

Run a single explicit Square Sandbox fake-card transaction for **A02: 21,450 JPY including tax, shipping 0 JPY**. The script creates a Square Sandbox payment link, attempts a test card payment associated with the same Square order, calls the Sandbox Payments API to verify the current status, and uses an **artificial** signed event (with an ephemeral test key) to verify the local order journal and idempotent handling.

Run is limited to the branch `feature/dogfood-shop-staging-20261028` and to an explicit `[square-card-smoke]` commit marker or manual opt-in workflow input. It uses only GitHub Actions secrets `BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN` and `BIGPAW_SQUARE_SANDBOX_LOCATION_ID`. Token, checkout URL, payment ID, and any consumer data are never printed.

Square test source: `cnon:card-nonce-ok` is an official Sandbox test token. Endpoint is strictly `https://connect.squareupsandbox.com/v2/payments`.

## Scope and limitations

- Successful test proves a genuine **Square Sandbox API fake card** payment, exact Square order/location/amount match, and local journal transition `payment_pending -> paid` using a synthetic signed notification and fresh Square API confirmation.
- This does **not** prove that a buyer entered test card details through the Square-hosted checkout page or that Square delivered a webhook over public HTTPS. Those still require a separate isolated staging deployment / end-to-end test.
- This test does not use any production Square endpoint, customer address, actual charge, Railway production resource, `main` merge or live checkout.
- If Square declines to accept a Payments API charge against an order created by the Payment Links API, the test must fail safely with a generic diagnostic; do not silently fall back to testing a different order or claim the purchase path is verified.

Test source: `scripts/smoke-shop-square-card-payment.py`, offline unit tests: `scripts/test-shop-square-card-smoke.py`, workflow: `.github/workflows/square-sandbox-smoke.yml`.

## 2026-10-29 diagnostic update

- Genuine opt-in hosted-checkout-linked CreatePayment probe: Actions run `40878952556` and `40879107227` did **not** succeed. Square link creation passed, direct Payments API against its draft checkout order was rejected at `create_payment`. **Do not report any payment as verified**.
- Split out a **standalone Payments API** probe with the same fake-card token and JPY 21,450 but **no checkout order ID**. This separately tests the Square Sandbox token, permissions, supported currency and API endpoint. Even a success is not proof of the hosted checkout purchase journey or webhook delivery.
- Source `scripts/smoke-shop-square-standalone-payment.py`; offline safety tests `scripts/test-shop-square-standalone-smoke.py`; branch-only opt-in job `square-sandbox-standalone-card-api`.
