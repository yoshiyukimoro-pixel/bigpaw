# BIG PAW Full-App Staging — Railway isolated test environment

Created on 2026-10-31 after the owner authorized additional Railway service charges.

- Project: `BIG PAW App Staging` (`91215e46-028b-4280-90f4-8d192c687164`)
- Environment: `staging` (`d0dacfcc-781b-4360-b539-461783ad47e2`)
- Service: `bigpaw-app-staging` (`26c225af-d7d3-41b3-86e3-347d22146312`)
- Persistent volume: `bigpaw-app-staging-data` (`929f1017-f474-45af-9fe1-c40e11d72801`), 500 MB, `/data`
- Source: `yoshiyukimoro-pixel/bigpaw`, Draft PR #175 branch, pinned to reviewed commit. `Dockerfile` full app rather than `Dockerfile.shop-staging` webhook-only.
- Separate project and SQLite volume; does not copy production data, customers, Square tokens, SMTP/Resend credentials or old Sandbox DB.
- `BIGPAW_ENV=staging`, `BIGPAW_PAYMENT_MODE=manual`; all food live checkout, live webhooks, real notification and Sandbox auto-notification switches off.
- Source-controlled `app/backend/staging_auth_gateway.py` provides an opt-in staging-only HTTP Basic Auth reverse proxy; the Railway start command must explicitly use `python3 backend/staging_auth_gateway.py` and `/healthz` for health check. Credentials must be privately provisioned in Railway `BIGPAW_STAGING_BASIC_USER`, `BIGPAW_STAGING_BASIC_PASSWORD` before exposing a staging domain.
- NEVER generate/attach public domain until a deployment with the authentication gateway is SUCCESS. Use a unique Railway-generated domain, never `bigpaw.site`.
- Costs use metered CPU/RAM, egress and volume. Initially cap one replica, 1 vCPU, 1 GB RAM and 500 MB volume. This is a resource ceiling, not a guaranteed monthly price.
- No shop production launch, PR merge, Square live payment, customer mail or shipment is authorized by this setup.
- Original `BigPaw/bigpaw-test` remains a separate existing Square Sandbox **webhook-only** service with its original 500 MB volume and secrets, not modified or migrated. It is not a full-app browser target.
- Work remaining: protected URL health and browser tests, safe Square Sandbox webhook/Checkout integration under a dedicated service, real HTTPS callback, separate data preservation tests. Do not count T02/T03/T04 as done just because the service exists.
