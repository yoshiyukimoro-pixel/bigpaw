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
