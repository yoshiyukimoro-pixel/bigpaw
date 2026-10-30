# BIG PAW Square Sandbox Webhook 移行・追加の安全手順（2026-10-31）

## すでに作成した独立したリソース

- 新アプリ側：Railway `BIG PAW App Staging`（Project `91215e46-028b-4280-90f4-8d192c687164`）、環境 `staging`。
- 新Square Sandbox受信専用：`bigpaw-square-sandbox-staging`（Service `ca40ca3c-d65a-4f51-99f3-b85ebfca164d`）。
- 独立データ領域：`bigpaw-square-sandbox-staging-data`（Volume `75266e34-b0bf-4bb4-8e7c-2743fbbb3d78`）、500 MB、マウント先 `/data`。
- 受信URL：`https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook`。
- 既存Sandbox `BigPaw/bigpaw-test` は別プロジェクトのサービスに残し、決済情報・署名鍵・DB・500MBボリュームを移動/停止していない。
- 新Webhook `/healthz` はHTTP 200、正常な検証可能署名が設定されない状態のWebhook POSTはHTTP 503（待機）。GitHub Actions 41129261203で外部HTTPS確認済み。
- 設定済み非秘密値：`BIGPAW_ENV=sandbox`、`BIGPAW_SHOP_STAGING_ISOLATED=1`、`BIGPAW_SHOP_STAGING_HTTPS_ENABLED=1`、`BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID=91215e46-028b-4280-90f4-8d192c687164`、`BIGPAW_SHOP_SANDBOX_DB=/data/bigpaw-shop-sandbox-staging.sqlite3`。メールとサンプル注文自動作成は全て無効。
- **現時点で未設定**：Square Sandboxアクセストークン、Location ID、通知先専用署名鍵。HTTPS通信が可能でも、Square実イベント受信は未検証。T03は未完了。

## 次に必要なSquare Sandbox側の安全設定

1. 原則としてこの新しいstaging環境用に**別のSquare Sandboxアプリケーション**または、他のテスト決済を巻き込まない隔離された実行方法を使用する。同じSquareアプリに追加の有効な`payment.updated`サブスクリプションを作ると、**無関係のSandboxテスト決済も届き、未登録注文は503で再試行されうる**。初期設定ではサブスクリプションを無効にし、配送対象の取引範囲と試験順序を先に確定。
2. Square Developer Consoleで対象アプリの**Sandbox環境**を選び、受信URLを完全一致で登録。`payment.created`、`payment.updated`等、実際に必要なイベントだけに限定。本番/Production側に登録しない。Square Webhook Subscriptions APIを使う場合、**OAuthトークンではなくアプリケーションのpersonal access token**が必要。
3. 受信URLごとのSquare署名鍵を取得し、Railwayの**新しいWebhookサービスだけ**に下記を直接登録する。秘密値をチャット、GitHub、CIログ、スクリーンショット、コードやドキュメントへ貼り付けない。
   - `BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN`（Sandbox用アプリのトークン）
   - `BIGPAW_SQUARE_SANDBOX_LOCATION_ID`（同Sandboxアプリ/店舗）
   - `BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY`（**この通知先専用**署名鍵）
   - `BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL`（上述HTTPS URL、パスを含む完全一致）
4. 新サービスのみデプロイして`/healthz`が`sandbox_webhook_ready`に変わることを確認。既存`bigpaw-test`は変更しない。
5. 偽注文を新サービス固有の新しいDBに先に作り、Square **Sandbox限定**の通知テストを行う。署名・URL・イベントID・金額・JPY・注文ID・店舗ID・決済COMPLETEDを外部Square GETで照合。署名不正・本番環境ヘッダ・重複は拒否。テストケースは本番メールや実発送を引き起こさない。
6. Square Developer ConsoleのWebhook Logsで、テストイベントの通知先・HTTP応答・リトライの有無を確認してからT03を採点する。未確認の状態でメールや本番販売を有効化しない。

## Square参照

- https://developer.squareup.com/docs/webhooks/step2subscribe
- https://developer.squareup.com/docs/webhooks/step3validate
- https://developer.squareup.com/reference/square/webhook-subscriptions-api
- https://developer.squareup.com/docs/webhooks/overview
- https://developer.squareup.com/docs/devtools/webhook-logs

## 現時点の採点と責任分界

T04（既存ボリューム保全とオフライン／HTTP両環境回帰）はGitHub Actions `41129261203` 成功により完了。**残り46ポイント（完了54%）**。

T03（Square実Webhook鍵とURL移行、受信検証）、P04（決済JPY・配送情報の実E2E）、R02は**未完了**。新サービスが稼働しただけでポイントを減算しない。PR #175はDraft維持、本番未変更。
