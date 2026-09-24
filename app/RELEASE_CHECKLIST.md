# BIG PAW v1.0 launch checklist

## Application — implemented
- [x] Buyer registration/login/profile
- [x] Email verification / password reset
- [x] Breeder application/review and fee-term consent log
- [x] Breeder public directory/detail
- [x] Puppy create/edit/image upload and listing moderation
- [x] Public search/detail/favorites/compare
- [x] Inquiry/messages/visit/deal workflow
- [x] Breeder completion report -> operator approval -> completed deal
- [x] 5% commission invoice generated after completion approval
- [x] Payment due 7 days from invoice issue
- [x] Automatic reminder at <=3 days, <=1 day, and overdue
- [x] Automatic public listing suspension on overdue invoice
- [x] Automatic reactivation after all overdue invoices are paid
- [x] Completion-report nudge after scheduled pickup date
- [x] Invoice display/print, operator payment confirmation, manual reminder
- [x] Reports/moderation/audit logs
- [x] Public/operator support inbox
- [x] Manual backup/restore + automatic local backup retention
- [x] Production readiness diagnostics and automation monitor
- [x] robots.txt / sitemap.xml generation
- [x] Smoke test

## Required before public launch
- [ ] Final operator/service business information entered
- [ ] Domain + TLS/HTTPS configured
- [ ] Production SMTP provider configured and tested
- [ ] Billing bank account and issuer data configured
- [ ] Decide reservation-payment operation (manual or payment provider)
- [ ] Decide production electronic-contract/signature approach
- [ ] Decide production image storage (local persistent volume or object storage/CDN)
- [ ] Terms/privacy/legal disclosures reviewed for the actual operating entity and workflow
- [ ] Strong operator password configured; development links disabled
- [ ] Off-site backup plan configured and restore tested
- [ ] Final security review of deployed infrastructure

## Go-live checks
- [ ] `/api/operator/readiness` returns `ready: true`
- [ ] Test breeder application and listing review
- [ ] Test inquiry -> deal -> completion report -> operator approval
- [ ] Confirm 5% invoice and 7-day due date
- [ ] Confirm overdue suspension and payment reactivation
- [ ] Confirm verification/reset emails arrive
- [ ] Confirm automated backup exists
