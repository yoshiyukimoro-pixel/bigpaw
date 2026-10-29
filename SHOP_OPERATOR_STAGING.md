# BIG PAW ドッグフードショップ 運営用 Sandbox 注文管理（2026-10-29）

## 検証済み

- Square Checkout公式Sandbox Testing PanelでA02 1点の注文・決済シミュレーションが成功。税込21,450円、追加送料0円、注文が`DRAFT → OPEN`、決済`COMPLETED`、Square注文と決済の一致を独立したAPIで照合。結果: [GitHub Actions 40884120819](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/40884120819)。
- ローカル注文記録は人工の署名済みWebhookを使って`payment_pending → paid`、重複イベント防止を確認。**Squareから実際に公開HTTPS宛へWebhookが届くかは未確認**。
- 35商品の在庫/注文/発送準備/発送済みの*内部記録*/返金レビューのロジックを追加。実際の配送、ラベル作成、返金実行、メール送信は行わない。
- `scripts/shop-sandbox-operator.py` は**ローカルDB限定**の運営用CLI。注文番号とSKU/数量/税込合計のみ扱い、住所/電話/カード情報は保存しない。
- `scripts/render-shop-sandbox-orders.py` は閲覧専用のローカルHTMLを生成。35商品在庫と注文明細を一覧表示。公開`app/`配下への書き込み・既存ファイル上書きは拒否。HTMLはchmod 0600、外部通信なし。

## Sandboxの操作例（開発環境の既存テストDBのみ）

```bash
# 既存の隔離テストDBを指定。DBはここでは自動で作らない。
PYTHONPATH=. python3 scripts/shop-sandbox-operator.py --db /tmp/bigpaw-sandbox.sqlite3 list

# 35 SKUの在庫量を確認
PYTHONPATH=. python3 scripts/shop-sandbox-operator.py --db /tmp/bigpaw-sandbox.sqlite3 stock A02

# テスト用DBの在庫数を2点に設定（明示確認必須）
PYTHONPATH=. python3 scripts/shop-sandbox-operator.py --db /tmp/bigpaw-sandbox.sqlite3 --confirm-sandbox stock-set A02 2

# サンドボックス決済により入金済みと照合された注文だけ、Squareの配送先情報を
# サーバー側で確認し、在庫引当・発送準備の内部状態へ進める（個人情報の保存なし）
PYTHONPATH=. python3 scripts/shop-sandbox-operator.py --db /tmp/bigpaw-sandbox.sqlite3 --confirm-sandbox assess FOOD<32桁の16進数>

# 閲覧専用HTML。アプリ公開ディレクトリではないローカル場所に作る
PYTHONPATH=. python3 scripts/render-shop-sandbox-orders.py --db /tmp/bigpaw-sandbox.sqlite3 --out /tmp/bigpaw-sandbox-report.html
```

※`record-shipped`はあくまで内部記録で配送手配ではない。`refund-review`は返金申請ではなく内部レビュー、`verify-refund`はSquare Sandbox APIからの完全返金の確認のみ。**本番用の運営画面ではない。**

## 販売開始までに必要

1. **受注発注に切替**：初期販売は在庫を持たず、注文時にSquareで決済 → 九州の仕入先（トランペッツ）に発注 → 埼玉の当店に入荷・検品 → 当店からお客様へ発送。仕入先在庫の欠品で決済済みとなる可能性があるため、欠品時の迅速な顧客連絡・入荷待ちの希望確認・全額返金の運用と通知機能を本番公開までに整備する。手元在庫0は受注不可を意味しない。
2. Squareからの実Webhook署名検証を独立したHTTPS StagingでE2E検査（Sandbox Developer ConsoleのWebhook設定が必要）。
3. 認証された運営画面と送り先住所・配達業者/追跡番号・通知・返品返金・キャンセル手順の整備。
4. メーカー在庫連携や実在庫数の入力方法、リードタイム、在庫切れ時の運用方針。
5. 特商法表示、プライバシー、返品・キャンセル等の文面、実機iPhoneチェック、本番Square接続の公開前レビュー。
6. ユーザーの明示承認を得て初めてmainへのマージ・Railway本番への反映・Square本番販売を行う。

**本番のBIG PAW、mainブランチ、既存契約/一般サイト、Square本番決済は変更しない。PR #175はDraft維持。**

## 2026-10-30 決定した受注発注方式（本番未反映）

- 販売開始時は35商品とも**受注発注（注文時にSquareで決済）**。仕入先のトランペッツからお客様への直送はできず、九州 → 埼玉の当店へ入荷（目安約2日） → 検品後に当店からお客様へ発送（地域によって約1〜2日）。
- お客様向けには**「ご注文・決済完了からお届けまで通常4〜7日程度」**を目安として記載。入荷・発送を保証する日付ではない。休日・仕入先の休業日・配送地域・交通事情・欠品で前後する場合がある。
- 全35商品の商品詳細テンプレート、一覧ページ、カート、注文確認画面へ受注発注の流れ、目安日数、**全国送料無料（追加送料0円）**、仕入先欠品時の連絡・入荷予定案内・全額返金方針を表示。注文確認チェックでも了承を求める。
- `shop_payments/sandbox_procurement.py` は別系統のSandbox限定受注発注ジャーナル。`awaiting_supplier_order → supplier_ordered → received_at_shop → shipped` の記録、欠品`supplier_backorder`、返金検証`refund_review → refunded`を安全に扱う。どの操作も仕入先への実発注・発送・返金を実行しない。
- `scripts/shop-sandbox-operator.py` に`supplier-status`、`supplier-ordered`、`supplier-shortage`、`supplier-received`、`supplier-shipped`、`supplier-refund-review`、`supplier-verify-refund`を追加。変更に`--confirm-sandbox`必須。支払いがSquareで検証されない注文では仕入・発送状態を進められず、発送記録にはSquare配送先情報のAPI確認が必要。返金済みの記録にもSquare APIによる全額返金確認が必要。
- 非公開のHTML管理画面にも仕入れ・入荷段階を表示。旧在庫表の0点表示は仕入先欠品と区別して説明する。
- *未実装*：仕入先への自動発注、仕入先の実在庫同期、顧客への欠品連絡や発送通知の自動送信、実際の返金申請、配送業者連携、公開可能な認証付き運営画面。Squareの本物のWebhook配送も未検証。
- GitHub Actionsによる静的テスト、受注発注管理の回帰テスト、PCおよびSafari相当のブラウザテストを行う。本番サイト、既存取引機能、Squareの本番決済は変更しない。PR #175はDraft維持。

## 2026-10-30: 注文・仕入・発送・返金に応じた**通知下書き**（Sandbox限定）

- `shop_payments/sandbox_notifications.py` にSQLiteを使った**未送信の下書きキュー**を追加。宛先アドレス、顧客氏名・住所・電話番号、Squareのカード情報や認証キーは記録しない。
- SquareのWebhookに相当する署名済みイベントを受け、**Square Payments APIからの独立した再確認後**、`payment_pending→paid`への変更と同じDBトランザクション内で、(1)運営への注文通知、(2)トランペッツ向け仕入れ依頼、(3)お客様への注文受付確認の3種類を自動で下書き登録。同一注文・同一種類の重複はSQLite主キーで防ぐ。Webhooksの本番受信は未完成。
- 手動記録した仕入先への発注済み・欠品・埼玉の当店への入荷・発送済み・返金レビュー・Squareによる全額返金確認についても、ステータス変更の**同一トランザクション**で適切な下書きを登録。
- 仕入先に送る依頼文にはSKU・商品名・内容量・数量を表示。**卸値・仕入価格・顧客個人情報を含まない**。仕入れの正式発注前に数量・入荷日・条件を運営が再確認する必要がある。
- お客様向け注文確認文には**九州の仕入先→埼玉の当店→検品してお客様へ発送、通常4〜7日程度、追加送料0円、欠品時の入荷予定案内または全額返金**を明示。発送通知には配送会社・追跡番号の未入力プレースホルダがあるため、人の確認なしに送信できない。
- **私有CLI操作**（既存の隔離Sandbox SQLiteファイルを`--db`に指定）：
  - `list`：注文・発注状態一覧
  - `notifications`：通知の未送信下書き一覧
  - `notification-preview FOOD<32桁の16進数> customer_order_confirmed`：本文表示
  - `--confirm-sandbox notification-sync FOOD<32桁の16進数>`：Square決済が検証済みの注文にだけ、未作成分を重複なく再登録（再実行は原則0件）
- 非公開のオフライン注文管理HTMLにも、**運営・仕入先・お客様ごとの未送信下書きの件数・件名・注文番号**を表示。メールやLINEへの接続はしていない。
- 自動テスト：`scripts/test-shop-sandbox-notifications.py`で未決済時に下書きが作られない、検証済み決済で3種類作られる、二重生成しない、欠品/発送/返金の段階と通知内容が一致、返金未確認の注文は完了通知が作られないことを確認。商品一覧・カート・Square Sandboxのモック接続・Chromium/WebKit回帰も成功。[GitHub Actions 40961186225](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/40961186225)
- **残作業**：認証付きで閲覧・送信承認する運営画面、送信サービス・宛先取得の連携、実際のSquare Webhook配送試験、発送会社/追跡番号の入力、欠品/返金の実運用、特商法・返品条件の最終化、実機iPhone確認。メールが「送信された」と記録する機能はまだない。
- 本番は変更していない。Square実課金なし、トランペッツへの実発注なし、注文者への実メール送信なし。PR #175はDraft維持。

## 2026-10-30：info@bigpaw.site 運営メールの準備（Sandbox限定）

- **送信先を固定**：`info@bigpaw.site`。送信者は既存BIG PAWのResend方式に合わせた `BIG PAW <noreply@bigpaw.site>`。過去のドキュメントに残る`bigpaw.jp`は今回使わない。
- `shop_payments/sandbox_operator_email.py`を追加。Square Sandboxの**検証済み入金**かつ`operator_new_order`下書きが存在し、`RESEND_API_KEY`、`BIGPAW_SHOP_SANDBOX_OPERATOR_EMAIL_ENABLED=1`、明示した`--confirm-sandbox`がすべて揃う場合だけ、Resendの`https://api.resend.com/emails`へ運営宛て**Sandboxのテスト通知1通**を送信できる。デフォルトは無効、テストCIでは実送信しない。
- メールの件名・本文に**「Square Sandboxテスト・実注文ではありません／トランペッツへ発注しないでください」**と明示。実際の発注指示・実顧客メールは送らない。既存の購入者・子犬掲載の通知機能にも触れない。
- `food_operator_email_dispatch`へ注文ID・通知種類・受付状態・ResendメールID・最終イベントを記録。**送信予約を先にDBへ確定**し、ネットワークのタイムアウトなど不確実な結果は`unknown`で固定して自動リトライしない。さらにResendの`Idempotency-Key`を使用。同一注文の二重送信リスクを軽減（プロバイダの冪等期限は24時間であり、ローカルの長期記録が必須）。
- `notification-email-check FOOD<32桁>`はResendの**読取専用**`GET /emails/:id`を使い、送信先が本当に`info@bigpaw.site`だったか、`last_event`が`delivered`（相手のメールサーバーが受信）か等を照合。`accepted`だけでは**受信完了と判定しない**。`delivered`でも受信トレイの表示・開封まで保証するものではない。
- `scripts/shop-sandbox-operator.py`に`notification-email-history`、`notification-send-operator`（環境・承認ゲート付き）、`notification-email-check`（読み取り）を追加。非公開のローカル運営HTMLにも送信受付・配達イベントを別欄に表示。
- `scripts/test-shop-sandbox-operator-email.py`で未入金禁止・環境変数/承認必須・宛先固定・Resend送信形式・同一注文の二重送信防止・ネットワーク障害の未知状態・相手サーバー配達ステータス照合・誤送信先排除をオフライン検証。他の35商品・画像98枚・Chrome/WebKit回帰も継続。
- **未実施**：実際のResend送信および`info@bigpaw.site`受信トレイへの到達検証、公開HTTPSでのSquare Webhook、認証付き本番運営画面、実注文通知の自動送信開始。実テストには独立したSandbox実行環境と適切なResendキーが必要。テスト済みと未確認を混同しない。
- mainマージ・Railway本番デプロイ・本番決済接続・実仕入発注なし。PR #175 Draft維持。

## 2026-10-30：メール到達の独立した一回限りのテスト

- 本番のRails/Railwayサービスから分離したGitHub Actions上で`info@bigpaw.site`へ、架空Sandbox注文のテストメール1通を送信する専用フローを追加。
- 通常のpushは送信されない。明示的なタグ付きコミットだけで一回起動する。送信キー`RESEND_API_KEY`がGitHubのSecretsに無ければ**送信せずに未設定と報告**。
- タイトル・本文は**実際の注文でないこと、トランペッツに発注しないこと**を明記。
- レスポンス`accepted`と配達イベント`delivered`を別に照合し、配達未確認を成功と扱わない。配信後は再送を行わない。実行後は自動トリガーを無効化予定。
- 事前安全性チェック/35商品の回帰は[Actions 40969719860](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/40969719860)で合格。次の専用ワークフロー結果で「実際の送信可否」を確認する。

## 2026-10-30：Resend 1回限りの試験結果と再送禁止

- 分離GitHub Actions Run `40969912963`でテスト通知の**送信を1回だけ試行**。`RESEND_API_KEY`はActionsに渡されたが、Resendの受付完了を確認できず`ACCEPTANCE_UNCONFIRMED`で終了。**実際に送信・配達されたとは断定できない**。本番の注文・決済・仕入れは一切発生していない。
- 不確実な試行を再送すると二重メールになる可能性があるため、元ワークフローから**メール送信ジョブを削除**して、読み取り専用Resend照合ジョブだけに更新済み。
- Resendの`GET /emails`と`GET /logs`から該当時間帯（2026-10-29 22:55–23:10 UTC）、送信先`info@bigpaw.site`、件名が正確に一致する送信記録・APIステータスだけを照合。受信の確認に失敗した場合は未検証と記録し、**自動再送しない**。
- メールの送信やプロダクションデプロイは行わず、診断結果をもとに本番公開前のメール設定調整を行う。
