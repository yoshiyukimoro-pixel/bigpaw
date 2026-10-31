# BIG PAWフードショップ｜Square配送先の最終確認（P04の未完了項目）

最終調査：2026-10-31、日本時間。**本番販売・発送・実メール送信は引き続き禁止。**

## 確認済みの事実

- 独立したRailway `BIG PAW App Staging / staging / bigpaw-square-sandbox-staging`で、A02 1点、税込21,450円・追加送料0円のSquare Sandbox公式テスト決済がCOMPLETED。
- Square Connect v2 が署名付き `payment.updated` を実際に配信。Railwayの2件のHTTP 200記録、新SQLite台帳の「入金済み」、Square Orders / Payments GET の一致を確認。新Webhook通知先はテスト終了後にOFF、旧通知先の設定は維持。
- 注文を新規作成しない別の読み取り専用試験 [41155860279](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41155860279) は **SUCCESS**。既存の注文をSquare Orders GETで検査すると、`SHOP_SANDBOX_SHIPPING_ADDRESS=INCOMPLETE_BLOCK_DISPATCH`。氏名・住所・電話番号などはログに記録せず、判定のみ取得。
- Squareの正式なCheckout APIでは `checkout_options.ask_for_shipping_address=true` を指定すると通常の購入画面に配送先入力が付く仕様。BIG PAWのSandbox決済リンクは既に `true` を指定している。公式参照：https://developer.squareup.com/docs/checkout-api/optional-checkout-configurations
- Square Sandbox Testing Panelの `Test Payment` はフォーム入力を模擬する操作であり、`Preview Link` はUIプレビューだけで決済完了には使えない。公式参照：https://connect.squareupsandbox.com/v2/online-checkout/sandbox-testing-panel/（個別テストURLは公開ドキュメントへコピーしない）
- 現時点で**Square Sandbox Testing Panelが配送先まで埋める保証はない**。本番と同等に配送先情報が取得できると断言しない。あくまで現在の実テスト注文では不完全だったという事実を採用する。

## 実装済みの発送禁止ゲート

- `shop_payments/sandbox_reconcile.py` はSquare Ordersで、配送タイプ `SHIPMENT` が正確に1件、国 `JP`、7桁郵便番号、氏名・電話番号・住所がある場合のみ `shipment_details_complete=true`。
- `shop_payments/sandbox_fulfillment.py` と `shop_payments/sandbox_procurement.py` の「発送済み（Sandboxテスト記録）」遷移では、**過去の入金済み履歴だけでなく**Square Payments/Ordersを最新GETし、未返金・配送先完備を再検証する。住所がないと拒否。
- `shop_payments/staging_orders_dashboard.py` に「入金済みと配送先確認済みは別です」の常時警告を追加。画面の警告は**配送情報を照合済みにする処理ではない**。画面そのものはSandbox管理者向けで、実際の商品発送は行わない。

## P04を完了にするまでの不足

1. 氏名・電話番号・日本住所・郵便番号を含む、個人情報を使わない**架空の住所データで**、Square Checkoutの実入力 → Square Ordersの `SHIPMENT` に反映される経路を確認する。通常のSandbox Testing Panelでは実入力ができない可能性があるため、代替手順の安全性を先に判断する。
2. 新SQLite台帳の支払確認・配送先確認・顧客連絡・欠品対応・発送停止・返金監査が同一注文の一連として確認できること。現行のSandbox fake-paid E2Eは決済・自動通知までは実証したが配送先は未完了。
3. 事業者の正式な返品/送料/配送時期が確定した後に、最終確認画面の表示と支払画面の内容を一致させる。本番Square・購入者への送信・実商品の出荷は別途正式承認が必要。

P04は**4ポイント未完了のまま**。今回の検査結果を根拠なく「発送可能」に変えない。

## 追加開発：運営者ごとの再確認ボタン（2026-10-31、未公開）

- 新しいURL `POST /api/shop/sandbox/operator/check-current-shipping` は既存の `bigpaw-test` 専用運営認証、HTTPS Origin・SameSite/HttpOnly CookieとCSRF、明示的な「読み取りだけ」確認チェックを要求。公開側や購入者の認証では実行不可。
- Square Sandboxの `Payments` と `Orders` を注文台帳にひも付けて**毎回再取得**し、現時点のCOMPLETED・JPY金額・店舗・未返金と、日本国内への `SHIPMENT` 配送先（氏名/電話番号/郵便番号/住所）の適合を区別する。
- 「配送先の必須項目を確認しました（Sandbox）」「配送先情報が不足しています・発送禁止」「Squareの最新情報を確認できません」の3種類のみ表示。宛名/電話/住所はレスポンス、ログ、SQLiteに保存・表示しない。確認不能時は発送禁止。
- 既存の `shop-test-orders.html` の入金済み注文ごとに「配送先が揃っているか確認する（Sandbox）」ボタンを用意。**ステージング管理画面の開発ブランチ上の実装で、まだユーザーに公開されていない**。実際の出荷登録では再度Square情報を確認するため、この画面の結果は発送の最終許可ではない。
- ローカルHTTPの結合テスト（全外部通信はモック）で、運営未認証、CSRF・Origin不一致、配送先不備、正しいJP配送先、返金済み状態、個人情報非表示、SQLite非更新を確認。GitHub総合CIがSUCCESS後に回帰保証となる。Square公式の `ask_for_shipping_address=true` は通常の決済画面で配送情報を取得できる設計（公式：https://developer.squareup.com/docs/checkout-api/optional-checkout-configurations）だが、Square Sandbox Testing Panelが実入力を再現するという意味ではない。
