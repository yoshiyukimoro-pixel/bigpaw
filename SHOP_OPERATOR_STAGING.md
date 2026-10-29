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

1. **公開前の在庫予約**：現時点では決済後に在庫を引き当てるため、在庫切れで決済済みになる可能性がある。公開前の必須改善項目。
2. Squareからの実Webhook署名検証を独立したHTTPS StagingでE2E検査（Sandbox Developer ConsoleのWebhook設定が必要）。
3. 認証された運営画面と送り先住所・配達業者/追跡番号・通知・返品返金・キャンセル手順の整備。
4. メーカー在庫連携や実在庫数の入力方法、リードタイム、在庫切れ時の運用方針。
5. 特商法表示、プライバシー、返品・キャンセル等の文面、実機iPhoneチェック、本番Square接続の公開前レビュー。
6. ユーザーの明示承認を得て初めてmainへのマージ・Railway本番への反映・Square本番販売を行う。

**本番のBIG PAW、mainブランチ、既存契約/一般サイト、Square本番決済は変更しない。PR #175はDraft維持。**
