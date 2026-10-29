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
