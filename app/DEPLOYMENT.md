# BIG PAW v1.0 - Deployment guide

## Local start
```bash
python3 backend/server.py
```
Open http://127.0.0.1:8080/

## Docker
```bash
docker compose up --build
```

## Environment
- `PORT`: listen port (default 8080)
- `BIGPAW_DATA_DIR`: cloud deployment durable storage root (recommended `/data` when a persistent volume is mounted)
- `BIGPAW_DEV_LINKS`: set to `0` in production. When `1`, password-reset/email-verification tokens are returned in API responses for local testing.

## Production connections still required
1. HTTPS + domain/reverse proxy
2. Transactional email provider for verification/reset links
3. Payment provider for real reservation payments/refunds
4. Production electronic-signature/contract approach
5. Object storage/CDN for uploaded images
6. Managed database or protected persistent volume + off-site backups
7. Monitoring/error reporting

Do not launch publicly with demo credentials or `BIGPAW_DEV_LINKS=1`.

## 成約手数料・請求設定

BIG PAWの初期料金モデルは、初期費用0円・月額0円・掲載料0円、成約時のみ最終生体販売価格の5%（税込）です。
ブリーダーがお迎え完了後に成約申請を行い、運営確認後に請求書を自動発行します。支払期限は請求日から7日以内です。

本番環境では次の環境変数を設定してください。

- `BIGPAW_COMMISSION_RATE_BPS=500`（5.00%）
- `BIGPAW_COMMISSION_DUE_DAYS=7`
- `BIGPAW_COMMISSION_TERMS_VERSION=2026-09-16-v1`
- `BIGPAW_BILLING_ISSUER_NAME`
- `BIGPAW_BILLING_POSTAL`
- `BIGPAW_BILLING_ADDRESS`
- `BIGPAW_BILLING_INVOICE_REG_NO`（適格請求書発行事業者の場合）
- `BIGPAW_BILLING_BANK_NAME`
- `BIGPAW_BILLING_BANK_BRANCH`
- `BIGPAW_BILLING_BANK_ACCOUNT_TYPE`
- `BIGPAW_BILLING_BANK_ACCOUNT_NO`
- `BIGPAW_BILLING_BANK_ACCOUNT_HOLDER`

ブリーダーは管理画面の「請求・お支払い」から請求書を開き、印刷またはPDF保存できます。

掲載申請時に、ブリーダーは成約手数料5%・支払期限7日以内の条件へ明示同意します。同意日時・適用料率・期限・規約バージョンはDBに保存されます。

## 自動運用
- `BIGPAW_AUTOMATION_INTERVAL_SECONDS=300`
- `BIGPAW_AUTO_BACKUP_HOURS=24`
- `BIGPAW_AUTO_BACKUP_KEEP=14`

自動処理は請求3日前/当日/期限超過通知、期限超過時の公開停止、入金後の再開、成約申請確認通知、自動バックアップを実行します。運営画面 `operator-automations.html` で状態確認と手動実行ができます。
