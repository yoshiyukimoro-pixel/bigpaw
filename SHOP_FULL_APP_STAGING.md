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

## 実行結果（2026-10-31）

- フルアプリRailwayデプロイ `3bb941c3-7f20-451e-9f50-77ea2e92ef56`：**SUCCESS/Online**、Railway警告0件。現行起動：`python3 backend/staging_auth_gateway.py`、ヘルスチェック `/healthz`。
- 保護付きテストURL：`https://bigpaw-app-staging-staging.up.railway.app/shop.html`。HTTP Basic認証はRailway内に保存した個別のユーザー名/32文字超パスワードで、GitHubへ秘密値を保存しない。
- GitHub Actions `41127078581`：ショップ単体・Docker・Chromium・WebKit総合テスト **SUCCESS**。
- GitHub Actions `41127629968`：外部HTTPS検査 **SUCCESS**。`/healthz=200`、`/shop.html=401`、`/=401`、`/api/shop/checkout/config=401`（すべて認証なし）。
- 既存`BigPaw/bigpaw-test`、本番`bigpaw-site`、`bigpaw-web`は引き続きOnline/警告0。元のSandboxボリューム・Webhook設定と本番データは未変更。
- T01（2ポイント）とT02（3ポイント）の条件を確認したため、**残り53→48ポイント、完了47→52ポイント**。なお、T02は新規フルアプリ環境を独立プロジェクトで追加する方法。元`bigpaw-test`はSandbox Webhook専用のまま。
- T03/T04/P04は未達。既存Sandbox Square SecretはOAuth経由で値が読めず、勝手に複製/移動しない。実カード・Webhook配信・配送情報・返金E2Eの成功扱いはしない。

## 追加のSquare Sandbox受信専用サービス（2026-10-31）

- 新規サービス：`bigpaw-square-sandbox-staging`（`ca40ca3c-d65a-4f51-99f3-b85ebfca164d`）。新独立Volume `75266e34-b0bf-4bb4-8e7c-2743fbbb3d78` は500MB。
- 完全別コンテナ、`Dockerfile.shop-staging`と`python3 -m shop_payments.staging_https_webhook`でデプロイ `d473aaf0-fa7b-4177-8346-8de93fe11fca` をSUCCESS確認。
- URL：`https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook`。Square署名鍵・APIトークン・Location IDの秘密値は存在しないため**503待機**。既存 `BigPaw/bigpaw-test` の署名鍵は持ち込まない。
- GitHub Actions `41129261203`：旧Sandbox・新アプリ・新Webhook全て非破壊外部回帰合格。旧Volume ID、旧デプロイID一致。**T04（2）完了、残り48→46（完了52→54%）。**
- 新Webhookを誤ったRailway IDや異なるHTTPS URLで起動させないソースガードと回帰テストを追加。Square Sandbox実イベントの移行・検証は未実施でT03保留。
- 安全な署名鍵/接続先の最終移行手順は `SHOP_SQUARE_SANDBOX_MIGRATION.md` を参照。
