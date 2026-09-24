# BIG PAW backend v0.15

Python標準ライブラリ + SQLiteで動くBIG PAW v1.0 system build backend。

## Start
```bash
cd puppy_link_site
python3 backend/server.py
```

## Smoke test
サーバー起動後:
```bash
python3 backend/smoke_test.py http://127.0.0.1:8080
```

## Implemented
- Authentication / roles / sessions
- Email-verification and password-reset token flows (development delivery)
- Breeder application and approval
- Puppy listing moderation
- Buyer favorites/inquiries/messages/visits
- Deal/payment-record/contract-sign-record/pickup/review workflow
- Parent dogs and health records with ownership checks
- Image upload restrictions
- Reports / operator moderation
- Audit logs / SQLite backups
- Security headers and basic rate limits
