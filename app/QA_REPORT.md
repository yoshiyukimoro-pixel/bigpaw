# BIG PAW v1.0 Final QA

Build date: 2026-09-16

## Passed
- Python backend syntax compile
- External JavaScript syntax check
- 51 inline JavaScript blocks syntax check
- 60 HTML pages served successfully (HTTP 200)
- Internal static links: 0 missing
- Full smoke test: registration/login/email verification/password reset
- Breeder commission-terms consent required and recorded
- Breeder application / operator approval
- Puppy listing moderation: pending -> operator approval -> public
- Breeder cannot directly mark a puppy sold
- Deal completion report: breeder report -> operator approval -> completed deal
- 5% commission invoice created after operator approval
- Commission calculation uses integer yen; fractions below ¥1 are truncated
- Payment due 7 days from invoice issue
- Overdue invoice -> breeder and puppy public visibility suspended
- Suspended breeder can still log in and access billing
- Payment confirmation -> public visibility restored
- Public support ticket -> operator support queue -> resolution
- Automatic processing monitor available
- Manual backup created successfully
- robots.txt and dynamic sitemap.xml
- Protected backend/config/database paths return 404
- Production mode: demo credentials are not seeded
- Production login: HttpOnly / SameSite=Lax / Secure cookie; session token not returned in JSON
- Production cross-origin state-changing request rejected

## Release status
Application feature-complete for BIG PAW v1.0 scope.

## External go-live configuration still required
- Actual domain + TLS/HTTPS
- Actual SMTP provider and sender
- Actual operator / billing issuer information
- Actual bank-transfer destination
- Strong production operator credentials
- Production hosting + persistent storage + off-site backups
- Final review of terms/privacy/legal disclosures for actual operating entity and workflow
- Formal trademark/name clearance and domain availability check
- Optional: external reservation-payment provider, e-signature provider, object storage/CDN
