# BIG PAW フード販売：Square連携方針（開発用・本番未公開）

利用者がdog fortyforで契約済みのSquareに「リンク決済」機能があり、BIG PAWで利用できると確認済み。

## 買い物の流れ（今後の実装）
1. お客さんがBIG PAWのカートで複数商品を選択する。
2. BIG PAWのサーバーが販売単価（税込）・数量・送料を再検証して、注文を「支払い待ち」として保存する。
3. Square Checkout APIのCreatePaymentLinkで、その注文の合計金額のSquareホスト決済リンクを自動生成する。35商品それぞれに手動リンクを用意する必要はない。
4. 購入者がSquare画面でカード決済する。BIG PAWサーバーはカード番号を扱わない。
5. Squareの署名付きWebhookを検証し、既存注文ID・Square注文ID・金額・JPY通貨・店舗IDが一致したときのみ「入金済み」にする。重複イベントは排除する。
6. 発送待ち→発送完了などの注文管理へつなぐ。

## 重要な制約
- メーカー希望小売価格は**参考表示**。実際のBIG PAW販売価格が確定するまで決済APIを呼び出さない。
- 仕入れ価格は**絶対にサイトやブラウザ向けコードに置かない**。
- 商品・送料の金額はサーバー内で確定。ブラウザの値段は信用しない。
- Squareアクセストークン、Webhook署名鍵はシークレットとしてRailwayに保管する。チャット・GitHub・HTMLに貼らない。
- Sandboxでテストし、決済の二重請求・返金・キャンセル・配送先・送料・税表示・未入金時の扱いを確認する。
- 本番Squareキー・実際の請求・Webhook登録・本番デプロイは別途明示承認まで行わない。
- 既存の子犬予約金・ブリーダー請求・認証・DBに変更を入れない。
- 2026-10-28のコードは単独の「決済リンク作成リクエスト整形・Webhook署名検証」ヘルパーと無通信のテスト**だけ**。注文DB保存、Web API公開、本番Square API接続はまだない。

## 関連
- shop_payments/square_checkout.py
- scripts/test-shop-square.py
- https://developer.squareup.com/reference/square/checkout/create-payment-link
- https://developer.squareup.com/docs/webhooks/step3validate


## 2026-10-29: Square Sandbox test app created by seller

The seller has created "BIG PAW Shop" in Square Developer Console, with Sandbox
selected and a default test Location visible. No real secrets were collected.

### Staging connector progress (this branch only)
- \`shop_payments/sandbox_connector.py\`: isolated, server-side Square
  Sandbox CreatePaymentLink API transport, hard-coded to the **sandbox API
  hostname only**. No production URL override.
- Durable **separate SQLite journal** for pending orders, saved Square links,
  signature-verified completion events and replay deduplication. No name,
  address, card number, or token persisted in its order table.
- \`scripts/test-shop-square-sandbox.py\`: offline tests with fake API responses;
  verifies sandbox hostname, JPY amount and shipping, tampered URLs and
  signatures, duplicate events, wrong order/amount/currency/location, retry
  behavior, and duplicate order protection.
- GitHub Actions runs these tests plus Chromium/Safari checks.
- This code is **not imported by app/backend/server.py**, not included by the
  production Dockerfile, and **not connected to the cart**. The production
  site and existing payment workflows remain untouched.

### Remaining dependencies before anyone can use a Square sandbox checkout
1. Approve final **BIG PAW tax-inclusive selling price** for each of the 35
   products. Current prices in public catalog are only reference MSRP, never
   to be used for charging. Keep all procurement costs private.
2. Approve shipping fee rules, dispatch locations, refund and return rules.
   A stable known shipping charge must be computed server-side before creating
   a checkout link. Asking for a shipping address *after* calculating shipping
   does not determine a correct region-based rate.
3. Configure Sandbox-only credential/Location ID in secret storage on a
   **separate, nonproduction** deployment (not in chat or GitHub).
4. Expose a staging-only checkout API with CSRF/rate limiting, approved price
   book and fixed shipping calculation, auth for order status, and webhook
   handler with a stable HTTPS URL and signature key. Build integration tests.
5. Reconcile against Square API on uncertain or out-of-order webhooks; verify
   order/payment existence, refund/cancel/idempotent state transitions.
6. Enable storefront checkout only after all of the above pass acceptance
   tests, then separately review production activation.

Official documentation:
https://developer.squareup.com/reference/square/checkout/create-payment-link
https://developer.squareup.com/docs/webhooks/step3validate

## 2026-10-29 送料込み・希望小売価格で販売する方針をユーザーが承認

- 35商品の**メーカー希望小売価格**を、そのままBIG PAWの**税込・送料込み販売価格**として採用する。画面の一覧・商品詳細・カートも同じ税込価格で表示する。
- お客様に追加で請求する送料は**0円**。サーバーで計算するSquare注文には送料行を追加しない。
- 仕入れ価格は公開画面・API・JavaScript・決済リンクのいずれにも出さない。
- 静的販売価格一覧 `shop_payments/retail_pricebook.json` は35商品をサーバー側の価格原本として扱う。`shop_payments/retail_catalog.py` は閲覧者が送った金額を一切受け付けずに、この価格原本からSquareの注文金額を計算する。
- **本番サイトへの公開、Square本番決済、決済用エンドポイントはまだ有効化していない。** 在庫・返品方針とSandbox接続テスト、運営承認が終わるまで本番反映しない。


## 2026-10-29: 独立テスト用カートからSquare Sandboxへ

- shop_payments/local_preview.py: 127.0.0.1 にのみバインドする独立HTTPテストサーバー。既存のapp/shop.htmlにテスト専用スクリプトを配信時のみ挿入し、本番HTMLは変更しない。
- shop_payments/preview_checkout.js: カートのID・数量のみ送信。希望小売価格（税込・送料込み）はサーバー側で再計算し、Square Sandbox専用決済URLへ遷移。
- GET /api/shop/sandbox/config: Sandboxの準備状況・CSRFトークンのみ返す（秘密鍵は返さない）。
- POST /api/shop/sandbox/checkout: 独立SQLite注文記録の保存、Square Sandbox専用CreatePaymentLink呼び出し。未設定では拒否。
- POST /api/shop/sandbox/webhook: Square署名と注文番号・金額・通貨JPY・店舗IDを照合してから入金済みにする。重複イベントを排除する。
- scripts/test-shop-local-preview.py: テスト用Square応答を使ったHTTP全体テスト。注文→決済リンク→署名付き入金通知→入金済みまで確認し、不正Origin・商品金額書き換え・偽署名の拒否を検証。
- 既存BIG PAWのサーバー、Dockerfile、本番決済、子犬販売用DBは**一切変更していない**。

ローカル起動: PYTHONPATH=. python3 -m shop_payments.local_preview --port 8765
閲覧: http://127.0.0.1:8765/shop.html
Sandboxの秘密鍵がなければ決済ボタンは無効。iPhoneからこのURLは直接開けない。

秘密のテスト環境変数（非本番シークレット管理に設定、GitHubやチャットに送信禁止）:
- BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN
- BIGPAW_SQUARE_SANDBOX_LOCATION_ID
- BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY
- BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL（Squareが到達可能なHTTPS URL）

### 未完了の作業
- 実際のSquare Sandbox API通信と実カードSandbox決済。秘密鍵はまだ接続していない。
- 公開HTTPSの非本番Webhook受信環境、SquareへのWebhook URL登録と実通知テスト。
- 返金・注文復旧、配送先取得・発送処理、注文通知メール・在庫管理の実装。
- 最終回帰試験を完了し、利用者の明示的な許可を得るまで本番公開・マージ・本番課金は禁止。


## 2026-10-29: 入金の二重検証・再試行の安全策

- Squareが送ったWebhook通知は、署名だけでは注文を入金済みにしない。サーバーがSquare **Sandbox Payments APIを読み直し**、Payment ID、Square注文番号、店舗ID、JPY金額、COMPLETED状態をすべて一致確認してから入金済みへ変更する。
- SquareのPayments APIの読取失敗、未完了、返金済み、金額不一致の場合は入金済みに変更せず、Squareに通知を再送してもらう。イベントIDによる重複処理防止も維持。
- shop_payments/sandbox_reconcile.py はSandbox専用の読取処理。発送先に必要な情報があるかをSquareの注文APIで確認するが、氏名や住所をテストログへ出したり、公開APIへ返さない。
- テスト画面のカートからは推測困難なUUIDv4の決済試行IDを生成して保持する。同じ内容で再試行した場合は前の注文IDとSquare決済URLを再利用し、通信失敗のたびに別注文を作成しない。商品・数量・価格が変わった状態での同じ試行ID利用は拒否。
- scripts/test-shop-square-reconcile.py, scripts/test-shop-square-sandbox.py, scripts/test-shop-local-preview.py で偽のAPI応答と署名付きイベントを組み合わせ、未決済/二重送信/同じ注文の再試行を検証。
- scripts/test-shop-square-browser.cjs はChromeとiPhone Safari相当のWebKitで、Sandboxボタンの無効・有効状態からSandboxドメインへの遷移までを**モック環境のみ**でテスト。外部決済や本番サイトへの通信なし。
- Railwayを調査したところ既存BIG PAWプロジェクトの環境はproductionのみ。**別のstaging環境の作成・課金・デプロイは行っていない**。本物のSquare Sandboxへの接続には隔離されたHTTPSテスト環境が先に必要。
- 開発用の仕様・テストは実装済みだが、Squareの実通信、実Webhook、配送先の発送画面、注文メール、運用上の返金フローは未完成。テスト通過と利用者の公開承認まではPRをDraftに保持する。

## 2026-10-29: 日本の消費税と購入者向け状態表示

- Square CreatePaymentLinkの注文情報に**10%の内税（INCLUSIVE）、ORDERスコープ**の税ルールを追加。税込の販売単価から消費税分を計上する方法で、税込・送料込みの合計金額を増やさない。Squareの日本向け計算規則に従う。
- Squareのチップ（追加請求）はfalseに明示設定。
- shop_payments/preview_checkout.js（localhostテスト専用）に、直近のテスト注文の入金状態を再確認するボタンを追加。Square決済ページから戻っただけでは「入金済み」と表示しない。
- Sandboxからの署名付きWebhookとSquare Payments APIの再照会が完了した場合のみ、テスト注文を「決済確認済み」と表示。未決済は「確認待ち」。いずれも現金は動かないテスト環境であることを明示。
- scripts/test-shop-square-browser.cjs: ChromeとiPhone WebKitでSandboxサイトへの遷移、戻り後の確認待ち・決済確認済み表示をモックサーバーで検証。
- 実Square Sandbox接続、公開HTTPS環境、Webhook登録、送料込みの発送条件および返金・特商法表示の最終確認は未完。本番環境にはデプロイしていない。

Square公式資料:
- https://developer.squareup.com/docs/international-development/japan-order-calculation
- https://developer.squareup.com/docs/checkout-api/optional-checkout-configurations

## GitHub ActionsでSquare Sandboxの実API接続を確認する準備

Railwayの新規staging環境を作る前に、GitHub ActionsからSquare **Sandbox API**に接続し、テスト注文の**決済リンクの生成だけ**を確認できる。カード決済や実際の請求は一切しない。

1. Square Developer Consoleで「BIG PAW Shop」→ **Sandbox** を選択し、Sandbox Access TokenとSandbox Location IDを表示・確認する。
2. GitHubの bigpaw リポジトリ → Settings → Secrets and variables → Actions → New repository secret で下記を**各々1個ずつ**安全に登録する。秘密鍵の本文をチャット・メール・スクリーンショット・GitHubコードに貼らない。
   - `BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN`
   - `BIGPAW_SQUARE_SANDBOX_LOCATION_ID`
3. 開発用featureブランチで、**明示的に `[square-smoke]` を含むコミット**を作った場合にのみ `.github/workflows/square-sandbox-smoke.yml` がSquare Sandbox APIへアクセスする。通常のpushではスキップされる。
4. 内部的にテスト用の商品A02（アカナ パピーラージ、税込送料込み21,450円）1点のSquare **Sandbox決済リンク**を発行し、Sandbox専用URLとSquare注文IDを検証する。
5. 成功ログに表示するのは成功・テスト商品の金額のみ。SandboxのAccess Tokenも、決済URLも、注文IDも出力しない。実カード払い、注文発送、顧客メール、本番Square APIには触れない。

上記手順でSquareの接続だけ確認しても、BIG PAWに決済機能が一般公開されたことにはならない。実際の購入・配送・Webhookを含むEnd-to-Endテストには別のHTTPS staging環境と、本番公開前の確認が必要。

Square sandbox checkout: https://developer.squareup.com/reference/square/checkout/create-payment-link


## 2026-10-29: Sandbox接続成功後の注文・在庫・返金の下地（PR #175のみ）

- Square Sandboxへの実通信はGitHub Actions run #40821207327で、決済リンクの作成成功まで確認。Square本番通信・本番デプロイは一切行っていない。
- \`shop_payments/sandbox_connector.py\` の隔離SQLite注文帳簿に、商品ID/数量の不変スナップショットと、Square Payments APIで検証したpayment IDを記録。過去帳簿には個人情報を追加せず、欠落した古い注文は手動確認とする。
- \`shop_payments/sandbox_fulfillment.py\` に運営専用の非公開在庫台帳・発送準備・キャンセル/返金確認待ち・非個人情報の通知キューを追加。**既存公開サイト/APIには接続しない**。
- 配送先はSquare Checkoutの\`ask_for_shipping_address: true\`で取得させる。Paid確認後、Square Sandbox Orders APIのSHIPMENT配送先情報を読み直し、国内住所・宛名・郵便番号等の有無を検査。住所・名前・電話番号は独立SQLiteにもGitHubログにも保存しない。運営への実際の住所表示は**将来の認証済み管理画面がSquareから読み出す必要があり未実装**。
- 商品在庫は35SKUを個別管理でき、**決済検証・発送先確認が済んだ注文に対してのみ**トランザクション内で引き当てる。欠品なら発送準備に進めない。多重引き当てを防止し、発送済み注文への返金確認待ち操作を拒否。
- キャンセル申請は\`refund_review\`として発送を凍結。**これは返金を実行・確約する操作ではない**。Square Sandbox Payments APIで金額・JPY・店舗・注文・payment ID・全額返金を再確認した場合だけ\`refunded\`にして未発送の在庫を一度だけ戻す。部分返金は要個別確認。
- 通知は\`food_operator_outbox\`に非PIIイベントを一度だけ積む段階。**メール送信・管理画面への通知配信は未実装**。
- \`scripts/test-shop-sandbox-fulfillment.py\` で35全SKUの入金済み注文・配送先確認・在庫引当、欠品/住所不足、二重処理、発送・返金確認の無通信テストを追加。
- 旧BIG PAWサイトの子犬データベース・認証・デプロイ・本番Squareの取引とは完全に分離。
- **重要：公開販売に必要な「決済リンク発行時点での在庫確保」はまだ未実装。** 現在のSandboxテストでは決済後に在庫が足りない注文が発生し得るため、一般公開してはいけない。
- 商品画像：旧会話の \`bigpaw_dogfood_staging_assets_updated.zip\` を確認。35 WebPの存在とファイルシグネチャを検査したが、GitHub上の実ファイル登録は未完。画像読み込みの実機確認は登録後に行う。
- 独立した公開HTTPS staging/Webhookの本物の受信・Sandboxカード決済、受注管理UI、通知送信、返品規約と特商法表示、在庫確保、発送完了連携、実機iPhone確認は未完了。CIのWebKitテストは自動エミュレーションであり実機ではない。

**必須ルール：PR #175はDraft維持。mainへのマージ、Railway本番デプロイ、Square本番決済開始は利用者の明示承認まで禁止。**


## 2026-10-30: Sandbox入金済み注文→運営宛通知の自動連携（本番無効）

- 受信できた `info@bigpaw.site` 宛Resend単発メールの成功を前提に、**開発ブランチのlocalhost専用** `shop_payments/local_preview.py` に、署名とSquare Sandbox Payments APIの両方で検証され、SQLiteで `paid` がコミットされた直後だけ運営宛のテスト通知を試みるフックを追加。
- `shop_payments/sandbox_auto_notify.py` は送信を初期状態で禁止。**3条件すべて** `BIGPAW_ENV=sandbox`, `BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED=1`, `BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED=1` が成立し、さらにローカル実行環境に有効な送信専用 `RESEND_API_KEY` が設定されている場合にのみ処理する。Railway環境変数が存在する場合は強制無効。
- メール宛先 `info@bigpaw.site` は固定。件名・本文に「Square Sandboxテスト・実注文ではない」「トランペッツへ発注しない」と明記。仕入先・お客様・LINEへは送信しない。注文内容（商品SKU・数量・税込金額・送料0円）以外の個人情報は含めない。
- `accept_webhook` が新規 `paid` を返す場合に限定。未決済・検証失敗・偽署名・二重Webhookは送信しない。メール送信前にSQLiteへ永続的な予約を残し、Resend `Idempotency-Key` を併用。通信結果が不明な場合も自動再送せず運営の照会が必要。
- `scripts/test-shop-sandbox-auto-notify.py` で未決済拒否、署名と支払い再検証後のみ、二重送信防止、Railway/本番環境の拒否、キー未設定、通信断、送信先固定を**全て模擬データ**で検査。実際のメールの再送信や決済は行わない。
- 今回の実装は**自動通知のソースとモック試験**。公開HTTPS Sandbox Webhook接続、実Sandboxカード決済→通知のEnd-to-End試験、認証済み運営画面、本番通知は未完成。GitHubの送信専用キーをRailway本番にコピーしない。
- PR #175はDraftのまま、mainマージ・Railway本番デプロイ・Square本番決済を禁止。公開前の明示承認、特商法・返品・配送手順確認が必要。


## 2026-10-30: 独立HTTPS Sandbox Webhook受信サービスの開発（非デプロイ）

- `shop_payments/staging_https_webhook.py` を追加。Squareの**Sandbox専用**イベントを受信するサーバーを、既存BIG PAW本番Webサーバーから完全に分離。通常の注文画面/管理画面/カート/商品情報を公開せず、公開経路は `GET /healthz` と `POST /api/shop/sandbox/webhook` のみ。
- TLSは**専用ホスティング側のHTTPS終端**を利用する前提で、アプリ内部はHTTP。Square Developer Consoleに登録するHTTPS通知URLと署名検証に用いるURLを**完全一致**させる。実URLやWebhook署名鍵は**まだ登録していない**。
- `Square-Environment: Sandbox` を要求し、本文サイズ/JSON形式を制限。Square署名のHMAC-SHA256を生バイトに対して照合し、さらにSquare Sandbox Payments APIで注文番号・金額・通貨・店舗・決済完了を再照会する。署名不正は403、検証保留は503、受理済みイベントは200。イベント重複防止はSQLiteで永続化。
- 確認済み決済に対する運営メールはレスポンスと分離したスレッドに送る。通知はさらに `BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED=1` / `BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED=1` / `BIGPAW_SHOP_STAGING_ISOLATED=1` の明示設定がなければ送信しない。予約/重複防止と不明結果の自動再送禁止を保持。
- **既存の2つのBIG PAW Railway本番プロジェクトIDを実行時に拒否**。別Railwayプロジェクトで動かす場合も `RAILWAY_PROJECT_ID` と `BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID` の完全一致が必要。SQLiteは別ボリュームの `BIGPAW_SHOP_SANDBOX_DB` だけを使う。
- `Dockerfile.shop-staging` はショップの検証に必要な `shop_payments/` のみコピーする隔離コンテナ。既存本番の `Dockerfile` や `app/backend/server.py` は変更しない。
- `scripts/test-shop-https-webhook.py` は偽署名、productionヘッダー、未入金、Square再照会不一致、重複、注文ダイアリーへの `paid` コミット後の通知、公開ルート制限、誤設定の起動拒否を**外部通信なし**で検査。ショップCIで実行し、隔離Dockerfileもビルドする。
- **未完了**：独立ホスティングの確保・有償課金/ボリュームの承認、Sandbox秘密情報と正確なHTTPS通知URLの安全な設定、Square Developer Consoleのテスト購読登録、実Sandbox決済→実Webhook→メールの通し試験、障害復旧時の未送信下書き再処理、実機確認。これら完了前に本番公開しない。
- 署名検証・再送仕様の公式参照： https://developer.squareup.com/docs/webhooks/step3validate 、 https://developer.squareup.com/docs/webhooks/overview

### 起動の前提（専用隔離環境のみ）

テスト専用ボリュームを添付し、`BIGPAW_SHOP_SANDBOX_DB` でそのDBパスを指定する。
必要な設定名は `BIGPAW_ENV=sandbox`, `BIGPAW_SHOP_STAGING_ISOLATED=1`,
`BIGPAW_SHOP_STAGING_HTTPS_ENABLED=1`,
`BIGPAW_SQUARE_SANDBOX_ACCESS_TOKEN`, `BIGPAW_SQUARE_SANDBOX_LOCATION_ID`,
`BIGPAW_SQUARE_SANDBOX_WEBHOOK_SIGNATURE_KEY`,
`BIGPAW_SQUARE_SANDBOX_WEBHOOK_URL=https://<staging-host>/api/shop/sandbox/webhook`。
実際の試験で運営メールを有効にする場合のみ
`BIGPAW_SHOP_SANDBOX_AUTO_NOTIFY_ENABLED=1` と
`BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED=1`, `RESEND_API_KEY` が必要。
Railwayの場合は追加で `BIGPAW_SHOP_STAGE_ALLOWED_PROJECT_ID` を別のstagingプロジェクトIDへ設定。
**秘密鍵はGitHubコード、チャット、公開ログ、スクリーンショットへ貼らない。**

