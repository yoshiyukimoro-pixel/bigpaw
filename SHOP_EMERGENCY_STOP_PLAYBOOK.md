# BIG PAW フードショップ：緊急購入停止・既存決済リンクの安全確認（未公開・Draft）

この手順は将来の本番公開前の**訓練・設計資料**であり、現時点のSquare本番設定変更やRailway操作を許可しません。2026-10-31時点で正式な法定情報・返品規約・公開承認が未完了、販売停止中です。

## 停止操作の意味を混同しない

- 新規受付停止：将来、本番で開通した場合はサービス側の `BIGPAW_SHOP_PUBLIC_LIVE_ENABLED=0` が購入APIと購入設定取得を拒否する。追加で `BIGPAW_SHOP_OWNER_LAUNCH_APPROVED=0` を維持する。変更は環境変数の反映・再起動状況も実際の非本番/本番で確認する必要がある。**今は実環境を変更しない。**
- 発行済みのSquare決済リンク：購入APIを止めても、すでにSquareにあるリンクは**自動では無効にならない**。Square Checkout APIのRetrievePaymentLinkやListPaymentLinks等、権限を持つ運営者の読み取り照会で実際の状態を別途確認する。Checkout API発行のリンクはSquare Dashboardの通常の決済リンク一覧に現れない場合がある。無効化は運営者の明示判断に基づく別操作とし、この監査は実行しない。無効化の実行には運営者の明示判断が必要。
- 決済通知：既発行リンクの支払いを見落とさないよう、署名付きWebhookとPayments/Ordersの独立照合は**購入受付停止と独立して稼働を維持**。Webhookの鍵・URL・受信可否を安易に停止しない。
- 事故時の返金：お客様の決済と払い戻しは別処理。購入ボタン停止だけで入金や返金が取り消されることはない。

## 安全な確認順序（実公開後の運用案）

1. 新規注文の停止を優先。注文開始画面・APIが拒否し、外部Square POSTが増えないことを確認。
2. 既存の注文台帳を読むだけで確認。私有SQLiteの**コピー**を利用し、以下のカウント監査を行う。原本への書込、公開パスへの転送は禁止。
3. `attempt_unknown` はPOSTの成否が分からないためSquare側で照合。再試行で別リンクを作らない。
4. `link_bound` は入金確認済みのものも含め、Square側にリンクが存在する可能性がある。未入金と入金済みを区別し、Square側で各リンクの利用状況・失効/無効化状況を検証する。台帳の件数が0でもSquare側に孤立リンクがない保証にはならない。
5. 署名済み既存Webhook、再取得による入金照合、キャンセル・返金確認を継続。注文・支払の紐づけが不明な場合は運営者の手動照合へ。
6. アプリ版をロールバックしてもSQLiteの永続ボリュームは巻き戻らない。Webhook受信経路を消す旧版へのロールバックは避け、バックアップ整合性・復元方針を別途確認する。
7. 復旧は所有者承認、法定表示、Square設定、非本番E2Eを改めて確認した後に行う。安全スイッチを勝手に「1」へ戻さない。

## 完全オフラインの件数監査

```bash
PYTHONPATH=. python3 scripts/test-shop-stop-readiness.py
PYTHONPATH=. python3 scripts/audit-shop-stop-readiness.py --db /path/to/explicit-private-copy.sqlite3
```

- 実行には存在する私有DBファイルを明示指定。読取専用 `mode=ro` と `PRAGMA query_only` を使用。存在しないDBやスキーマ不一致は中止。
- 出力は `planned` / `attempt_unknown` / `link_bound` と入金確認の**集計件数だけ**。リンクURL・Square ID・購入者氏名・住所・電話・メール・鍵は表示しない。
- Squareとのネットワーク通信・無効化・返金・メール・DB更新は**一切行わない**。実際のリンク状態はSquare CheckoutのPayment Links取得・一覧APIとSquare Orders/Paymentsの独立した読み取り照合で確認する。Dashboardの通常一覧に見当たらなくてもリンクなしと判断しない。

## ポイント上の扱い

この監査とCIはP06の事前安全対策だが、P06の完了条件「購入停止スイッチと安全なロールバックの実機確認」のうち、実環境における停止復帰・発行済みリンク確認・ロールバック演習は未実施。**P06の3ポイントは減算しない**。P04/T02/R02も引き続き保留。

## Square Checkout APIの注文状態について（2026-10-31確認）

- CreatePaymentLink直後のSquare注文は原則`DRAFT`。これは支払済みを意味せず、Square Payments APIに直接`CreatePayment`を発行しても通常のHosted Checkout決済にはならない。
- 決済画面を開いた時点で`OPEN`へ変化する場合があり、**OPENも入金の証拠ではない**。正確なSquare Payments APIの`COMPLETED`、注文ID・店舗・金額・通貨と返金状態の再取得を必須とする。
- 開発ブランチは発行直後の`DRAFT`注文を、サーバー側の固定済み商品・数量・税込単価と照合し、一致した場合のみ「リンク発行済み」として保持する。`DRAFT`で受注入金確定にしてはならない。
- Square公式資料：https://developer.squareup.com/reference/square/checkout/create-payment-link ・ https://developer.squareup.com/docs/checkout-api/common-pitfalls ・ https://developer.squareup.com/docs/checkout-api/quick-pay-checkout

## 2026-10-31：実Railway staging停止・旧版復旧訓練（本番は変更しない）

- 隔離済み `BIG PAW App Staging / bigpaw-app-staging` のみで、購入受付フラグ `BIGPAW_SHOP_PUBLIC_LIVE_ENABLED` を一時的に `1` へ変更。起動時の別ガード `BIGPAW_ENV=staging` と、コード内の未承認チェック `retail_launch_status.json` は販売開始を許さない。**実購入は一件も作らない**。
- Railwayは変数変更により、元々固定していた古いコミットでなく開発ブランチ最新版 `4efd67db9d6c15541ef85869b166fdcb7be035f9` の新規ビルド `b64233f3-98a9-4206-9fc9-83ee5fddb925` を作成した。このため**環境変数変更は単なるフラグ操作ではなく新コードを自動ビルドし得る**という運用リスクが実際に判明。
- 検証中にフラグを `0` へ復元（`skipDeploys=true`）、先の安定版 `3bb941c3-7f20-451e-9f50-77ea2e92ef56` を指定して `redeploy`。復旧デプロイ `8bf0a601-ee0e-4d50-9d22-1299dfb7e01d` はRailway **SUCCESS**。先行ビルドは `REMOVED`、復旧後の動作コミットは `361ff926b8834ef099b85046610c61fb4a29eed7`。新アプリ・新Sandbox受信機ともOnline、警告0件。
- 元のフルアプリ保存ボリュームID `929f1017-f474-45af-9fe1-c40e11d72801` は変わらない。旧 `BigPaw/bigpaw-site`、`bigpaw-test`、`bigpaw-web` のサービスは引き続きOnline。mainのコード変更、Square Production API、実メール送信、顧客への請求なし。
- **確認できたこと**：Railwayサービスを再デプロイし、既知の安定版へ復旧して安全フラグをOFFに戻す運用。
- **未確認**：実際に購入可能な状態からの停止応答、発行済みSquareリンクの個別無効化、以前の支払いイベントを処理するWebhookとの協調、保管した実注文の復旧可否。したがってP06（3）は完了扱いにせず、引き続き残り46ポイントを維持。
- 本番緊急停止時は、`BIGPAW_SHOP_PUBLIC_LIVE_ENABLED=0` のみで安心せず、**デプロイ済みコミットID・保護されたサイト・注文台帳・既発行Squareリンク・Webhook経路**をそれぞれ点検。新コードで再デプロイされ得るため、正常ビルドIDを固定してロールバックする。本番運用の前に別途購入有効状態の隔離E2Eが必要。


## 2026-10-31：実Square Sandbox入金と購入停止後の保全を確認（P06完了）

この節は上の **P06未完了** と記された古い訓練記録より新しい正式な判定である。**本番公開やSquare Productionの許可ではない。**

- 隔離済み`BIG PAW App Staging` のフルアプリ：購入停止フラグ `BIGPAW_SHOP_PUBLIC_LIVE_ENABLED=0` のもとで別コード版へデプロイしてHTTPアクセス制御を確認し、既知安定版コミット`361ff926...`に戻してRailway `acba6bd1-ad8c-432c-8f04-eaa5c5bf41c7` がSUCCESS。Private Volume維持。
- 隔離済み`bigpaw-square-sandbox-staging`：パスワード保護されたSandbox購入画面をONにして、Square公式Testing Panelで **税込21,450円・送料0円のテスト決済** を確認。Square自身から届く `payment.updated` により隔離SQLiteの同一注文が `payment_pending→paid`。Square Payments/Ordersの最新再取得、店舗・注文・通貨JPY・金額が一致。GitHub [41154207823](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41154207823) SUCCESS。
- 独立したRailway HTTPログ：`2026-10-31T01:13:51Z`および`01:13:54Z`に、送信者`Square Connect v2`、新Webhookパス、HTTP200の2件。
- Square新テスト購読だけを一時ONにして上の本物のSquare通知を確認した後、常にOFFへ戻す処理が成功。追加のSquare読み取り監査 [41154464365](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41154464365) は旧購読`enabled=true`・新購読`enabled=false`を確認。旧購読設定には変更なし。
- テスト購入画面も`BIGPAW_SHOP_STAGE_PREVIEW_ENABLED=0`へ復元。Railway新Webhookサービス再デプロイ`5afc9929-645b-475d-a005-dcbd6f749e09` SUCCESS。
- 既発行の実Sandboxテストリンクを**決済の再試行なし**で読み取り、Square元のCOMPLETED支払いと21,450円を確認。停止・再デプロイ後にも既存の有効な署名鍵で同じ支払いの人工的な再照合を新Webhookへ送り、HTTP200で既存の入金済み台帳を正常に認識できることを確認。[41154781086](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41154781086) SUCCESS。
- 今回の **P06（3ポイント）は隔離stagingでの実機停止、戻し、既発行リンクの読み取り、既存入金確認と台帳保全の範囲として完了**。ただし実Shop本番の購入可能状態からの事故対応、発行済リンクの個別取消、返金、出荷済み注文対応まで行ったという意味ではない。後続P04/R02/R04/R05の承認と運用リハーサルは引き続き必要。
- **厳守**：購入停止は新規Checkout API受付を拒否するだけで、既発行のSquare Checkoutリンク自体は取り消さない。購入者がその既存リンクで入金する可能性があるため、Webhookは維持し、Square側の決済状態と残件を独立して確認する。顧客への実メール、仕入先への発注、Square Production決済は引き続き禁止。

2026-10-31時点の正本：`SHOP_PROGRESS_POINTS.json` は **59ポイント完了／残り41ポイント**。
