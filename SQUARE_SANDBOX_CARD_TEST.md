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

## 2026-10-29 validation update: idempotency key length fixed

- Direct Sandbox Payments API diagnostic exposed HTTP 400, sanitized code `VALUE_TOO_LONG`. The payment `idempotency_key` exceeded the **45 character** limit in Square's CreatePayment reference. This explains the earlier linked and standalone API rejections; it was our test request, not confirmed card availability.
- Fixed both test-only payment paths to use random/hash-derived keys shorter than 45 characters and added regression assertions + fail-closed API validation.
- Re-run BOTH opt-in checks independently (standalone fake card and attempted linked checkout order) before claiming a successful API payment. Real Square-hosted checkout page entry and public webhook delivery remain separate tests regardless.

## 2026-10-29: hosted Checkout panel end-to-end validation

- `40880609514`: Standalone Square Sandbox CreatePayment with Square's test nonce returned `COMPLETED` for JPY 21,450 and a fresh independent Payments API GET matched the amount and location. **Fake money, genuine Sandbox API.**
- Linking the Payments API directly to a Payment Links-created `DRAFT` order returned `BAD_REQUEST`; this is **not** the supported hosted checkout simulation.
- Therefore use the official Square Checkout Sandbox Testing Panel: create a real Sandbox link, click Next → Test Payment, then fetch the original Square order and corresponding payment from the Square APIs, and verify the exact local order snapshot.
- A hosted panel success proves the simulated Square checkout path, not public HTTPS webhook delivery or iPhone physical-device checkout. The local order journal is exercised only using an *artificial signed event*, verified by a live fresh Square API lookup.
- Scripts `scripts/smoke-shop-square-hosted-panel.py`, `scripts/smoke-shop-square-hosted-panel.cjs`; opt-in feature-branch-only action `square-sandbox-hosted-panel`.

## 2026-10-31: Direct CreatePayment on a Payment Link DRAFT order is disabled

- [Run 41122860333](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41122860333) and [run 41123302475](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41123302475) both failed at CreatePayment: HTTP 400 BAD_REQUEST, no error field, no verified new payment.
- Square-hosted Checkout Payment Links start with a DRAFT Order. The supported payment simulation is the hosted Sandbox Testing Panel, not attempting to pay its DRAFT order with a separate direct Payments.CreatePayment request. See https://developer.squareup.com/docs/checkout-api/quick-pay-checkout
- The previously successful official hosted-panel [run 40884120819](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/40884120819) had an independently matched Square Order/Payment (Sandbox only). It is not evidence that a public HTTPS webhook or new full-app staging deployment works.
- The deprecated linked-card script now returns a documented non-success code **before any network or order creation**; its optional workflow job runs an offline safety check with no secrets. The separately opted-in hosted-panel and standalone Payments API workflows remain unchanged.
- This is a probable explanation for these particular 400 errors, not a provider-confirmed detailed error field. No repeat payment attempt, production API call or release. No progress task completed by this investigation. **Remaining 53 points; 47 completed.**
