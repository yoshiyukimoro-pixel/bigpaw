# BIG PAW Shop: operator order recovery

This runbook applies to the future production order journal. It is not a
permission to turn on checkout, contact a customer, place a supplier order,
ship goods, or issue a refund. Those actions remain disabled until their
separate launch and legal approvals are complete.

## Before handling an order

1. Sign in with an operator account and open **フードショップ注文管理**.
2. Treat the page as a historical journal. `paid_verified` means Square was
   verified at the time recorded; it does not establish the current refund,
   dispute, or chargeback state.
3. Never retry checkout or create a replacement link for an order whose
   Square request timed out or whose result is unknown. A link may already
   exist. First reconcile the existing Square order and payment.
4. Keep names, addresses, phone numbers, email addresses, access tokens, and
   card data out of notes, screenshots, logs, and support messages.

## Unknown checkout result

- Preserve the local order ID and stop further checkout attempts for that
  purchase.
- In the Square dashboard, locate the existing order using the Square order
  reference from the trusted server journal. Check its payment and refund
  history. Do not rely on a browser return page or a customer screenshot as
  proof of payment.
- If Square confirms a completed, unrefunded payment, keep the order pending
  operator reconciliation until the approved authenticated server-side
  verifier has checked the exact order, location, JPY amount, and shipment.
- If Square is unavailable, IDs disagree, or the payment cannot be found,
  leave the order unresolved. Do not create another payment link or mark it
  paid by hand. Record only the time, order ID, operator account, and a short
  non-personal reason in the approved audit channel.

## Previously verified payment

- A historical `paid_verified` label is not a current payment check.
- Before any future fulfillment action, re-query Square Payments and Orders
  through the approved server-side read-only verifier. Require an exact JPY
  amount, location, order identity, completed status, no refund, and the
  required shipment information.
- If the current state differs from the journal, stop fulfillment and route
  the case for operator review. Do not edit the SQLite journal manually.

## Duplicate or conflicting notifications

- The webhook handler verifies the signature and then independently fetches
  the current Square Payment and Order before changing the journal.
- Duplicate verified events are expected to be idempotent. A conflict,
  unknown order, refund, amount mismatch, or Square outage must remain an
  unresolved case; do not bypass the handler or replay a database update.
- Preserve the Square event identity and local order ID in restricted audit
  records only. Never store the raw webhook body or credentials in a ticket.

## Current implementation limits

- The operator page omits customer personal information. Manual reconciliation
  is a separate, operator-authenticated action that accepts only an existing
  local order ID and the Square payment ID copied from the official dashboard.
- Reconciliation is disabled unless production explicitly sets
  `BIGPAW_SHOP_LIVE_OPERATOR_RECONCILIATION_ENABLED=1` and configures the
  dedicated `BIGPAW_SQUARE_LIVE_ACCESS_TOKEN`. It uses exact configured HTTPS
  Origin/Host checks, an HttpOnly SameSite=Strict double-submit CSRF token, and
  the operator session. Sandbox credentials cannot enable this route.
- The server derives amount, Square order, and location only from the private
  saved checkout record, then performs fresh Production Payments and Orders
  GETs before changing local state. The actor, local order ID, outcome, and
  time are recorded atomically for successful checks; failed authorized
  attempts also receive a PII-free audit entry. No submitted payment ID,
  provider payload, recipient data, or token is persisted in the audit log.
- This action only reads Square and updates the private local payment ledger.
  It never charges, refunds, sends email, places supplier orders, or ships.
  The feature flag remains off unless a production operator deliberately
  enables it. Checkout and webhook launch gates remain separate.
- Offline tests use synthetic identifiers and fake Square GET responses.
  They do not verify live credentials, a production merchant, or an actual
  payment. When Square cannot confirm an exact completed, unrefunded payment,
  keep the order unresolved and do not issue another link.
