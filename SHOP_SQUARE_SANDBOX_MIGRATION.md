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

## 新Webhook接続先制限の実デプロイ検証

- `shop_payments/sandbox_runtime_guard.py` と `staging_https_webhook.py` で新しいRailway Project/Environment/Service IDと通知URLの完全一致を必須化。新フルアプリと旧サービスの取り違え、誤URLは拒否。
- GitHub Actions `41129531895`（ショップ総合CI）、`41129531984`（非破壊両環境CI）はSUCCESS。Squareテストカード実決済・本番アクセスなし。
- 新Webhook専用サービスだけに `d653d7244ecd5a929db68c67cbd6ffede70cb77e` をデプロイ。`958fa8f1-71e0-4cba-badb-3bd1a722890b` SUCCESS／Online、警告0。
- 外部GitHub Actions `41130100145` がSUCCESS：旧Sandbox `/healthz=200`、新フルアプリ `/healthz=200` /匿名`401`、新Webhook `/healthz=200`・署名無しPOST`503`。JSONの`status=sandbox_webhook_standby`を検証し、**Square Sandbox鍵未設定で必ず停止中**であることを確認。
- T03の本当の完了にはSquare Developer ConsoleでSandbox専用サブスクリプションを登録し、Square署名鍵・Sandboxトークン・Location IDを新Railwayサービスへ秘密値として直接登録し、実際のSquare送信/署名/Payment照合に成功する必要がある。**残り46ポイント維持。**

## 2026-10-31：Square新Webhookの無効サブスクリプション事前登録

- Square公式 `GET /v2/webhooks/subscriptions` をGitHub Actions `41133493643` で検証。結果：**古いBIG PAW Sandbox URLは有効（payment.updated購読済み）、新URLは未登録**。秘密鍵、通知先ID、他事業者のURLはログに出していない。
- 新しい開発用 `https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook` だけを、Square **Sandbox** の `enabled=false` サブスクリプションとして1件登録する。既存のURL・イベント購読設定には一切触れない。
- GitHub Actionsの既存Sandboxトークンのみ利用。先にGETで重複防止、1件だけPOST（再試行なし）、固定冪等キー、POST失敗・タイムアウト時は再送禁止。作成応答に含まれるSquare `signature_key` はログやリポジトリに保存しない。
- 作成できても**通知は無効状態**であり、Square鍵を新Railway受信サービスに安全登録し、実署名Webhookのエンドツーエンド確認が済むまでは有効にしない。T03は未達で残り46ポイントのまま。

### 無効通知先の登録処理・安全性再試験

- 初回Actions `41133725838` はテストコードの引数指定により、Sandbox APIアクセス前に失敗。Squareへの追加/変更は0件。
- テストコードを修正し、ショップ総合CIへ合成テストを常設。**新通知先が未登録なら無効状態で1件だけ登録**し、有効な既存Webhookは絶対に変更しない。登録リクエストのタイムアウトや結果不明時は自動再送しない。
- Squareから返る署名鍵とサブスクリプションIDはCI出力・GitHub保存・チャットへ出さない。Square本番APIには接続しない。
- 今回は別の明示的なSandboxテスト開始であり、**T03やP04の完了宣言にはしない**。

## 2026-10-31：新Square Sandbox通知先を無効で登録・独立照合

- GitHub Actions `41133493643`（Sandbox Webhook Subscriptions APIへの**GETのみ**）で、既存 `bigpaw-test-production.up.railway.app` は有効かつ `payment.updated` 登録済み、新 `bigpaw-square-sandbox-staging-staging.up.railway.app` は未登録と判明。
- Square公式のWebhook Subscriptions APIで新しい受信URLだけを `enabled=false` として事前登録。登録ワークフロー `41133935500` **SUCCESS**、結果 `new_target_created_disabled_no_delivery`。Square本番APIは一切使用せず、旧Webhookの設定変更なし。
- 作成前の安全テストは一度 `41133725838` で引数指定の不具合により失敗したが、API書込前に止まった。テスト修正後に登録実施。既存通知先に副作用なし。
- 登録後の独立した読み取り専用チェック `41134021794` **SUCCESS**：`old_enabled_payment_updated__new_disabled_payment_updated__read_only`、外部API書込0回。
- 新WebhookサービスはSquare認証情報・**新通知先専用署名鍵が未設定**であり、HTTP 503 `sandbox_webhook_standby` を維持。未登録注文のWebhook受信や本番販売を有効化していない。
- 次に必要：Square Developer Console等から新サブスクリプションの`signature_key`を確認し、新Railwayサービスの`BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY`、`BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN`、`BIGPAW_SQUARE_SANDBOX_LOCATION_ID`を**安全な秘密変数**として設定する。秘密値をGitHub・チャット・CIログに貼らない。実署名通知と最新Square Payment照合に成功した後だけT03達成とする。
- 本作業でT03/P04/R02はまだ完了していないため、**残り46ポイント・完了54%維持**。

## 2026-10-31：Square新通知先の署名鍵GET検証と安全な秘密値移送

- Square無効Webhookの登録はGitHub Actions `41133935500` で **SUCCESS**。新URL `https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook` だけを `enabled=false` で登録、旧URLは未変更。
- GitHub Actions `41134370968` でSquare Sandboxの**GET**リクエストから新通知先の署名鍵を安全に取得できると確認。ローカルHMACの正しいURL/誤URL比較は成功。鍵そのもの・SquareサブスクリプションIDはGitHub・チャット・Railwayログへ出していない。
- `scripts/sync-shop-staging-sandbox-secrets.py` と `.github/workflows/shop-staging-sandbox-secret-sync.yml` を作成。元Square Sandboxの専用テストトークン・店舗ID、対象Webhookの署名鍵を、GitHub Actionsプロセス内だけで取得し、Railwayの新stagingサービス`ca40ca3c-d65a-4f51-99f3-b85ebfca164d`へのみ `variableCollectionUpsert` を行う。既存のBigPaw環境と本番サービスには一切触れない。対象Square通知先が`enabled=false`かつ、Railwayプロジェクト・環境トークンの参照先が完全一致する場合のみ1回実行し、`skipDeploys=true`。未知の返答では自動再試行しない。**通常Pushでは実行されない。**
- この自動化を使う場合は、**Railway新プロジェクト`BIG PAW App Staging`の`staging`環境だけ**を対象とするProject Tokenを生成し、**GitHubリポジトリのActions secret `BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN`** へ登録する。トークンをチャットに貼り付けない。Railway Project TokenでAPIの変数更新が拒否される場合は、広いAccount Tokenへ無条件に変更せず、Railway新サービス内にSquare署名鍵・Sandboxアクセストークン・Location IDを運営者が直接保存する経路を使う。
- GitHubのテスト用Sandbox認証情報は既存の`BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN`と`BIGPAW_SQUARE_SANDBOX_LOCATION_ID`（いずれもActions Secrets）を使用する。
- 機密値が設定されても、**新Webhookはまだ無効**。別途確認してデプロイし、Square側の試験配信時だけ制御付きで有効にする必要がある。T03やP04は現時点では未完了、**残り46ポイント**。
- Square公式資料： https://developer.squareup.com/reference/square/webhook-subscriptions-api/retrieve-webhook-subscription / https://docs.railway.com/integrations/api/manage-variables / https://docs.railway.com/integrations/api


## 2026-10-31：新Railway認証情報の安全な移送・外部受信準備確認

- 運営者が新 `BIG PAW App Staging` / `staging` の Project Token をGitHub Actions Secret `BIGPAW_SHOP_STAGING_RAILWAY_PROJECT_TOKEN` に登録。トークン値はGitHubコード・チャット・ログに記録しない。
- 初回の自動移送はRailway GraphQLでHTTP 403。Ray IDや機密情報をログに出さず、原因区分の診断を追加。GitHub ActionsのPython urllibデフォルトUser-AgentによるCloudflare拒否の可能性を踏まえ、明示的な `BIGPAW-Shop-StagingSync/1.0` ヘッダーを採用。修正後の一回限りの自動同期が [Actions 41147733135](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41147733135) で**SUCCESS**。
- 新WebhookサービスにだけSquare Sandbox Access Token・Location ID・当該無効サブスクリプション専用署名鍵の**変数名3点**が存在することをRailwayの値非表示一覧で確認。同期時は `skipDeploys=true`、Square通知先は引き続き `enabled=false`、旧Sandbox・本番・メールは無変更。
- 新Webhookサービスのみ既知のデプロイ成果物を再利用して再起動：`2cfec67f-c594-46c5-92a7-45f53bd0b8a7` が**SUCCESS / Online**。新アプリ側サービスへの変更なし。
- 外部HTTPS読み取りだけの [Actions 41148046554](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41148046554) が **SUCCESS**。`/healthz` が `sandbox_webhook_ready`、注文/運営などの非公開画面が404であることを確認。
- 旧Sandbox・新アプリ・新Webhookの非破壊総回帰 [Actions 41148074669](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41148074669) も **SUCCESS**。署名なしWebhook要求が受理されないことを確認。
- **T03未完**：Square Sandbox側の新通知先購読は無効のまま。実Square署名付き `payment.updated` の配送、Webhook Logs、Square Payments/Ordersの最新再取得、店舗・JPY・注文ID・金額一致はまだ確認できていない。既存の有効なSandbox通知先を巻き込まない実イベント範囲と試験順序を確定してから実施。**残り46ポイント（完了54/100）を維持。**
