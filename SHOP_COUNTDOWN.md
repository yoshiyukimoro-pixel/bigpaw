# BIG PAW フードショップ：完成までの残りポイント

**現在：残り56ポイント（基準100／完了44ポイント）** — 2026-10-31（日本時間）

これは「2026-10-30時点で残っている仕事」を100ポイントに正規化した**これからの減算カウント**です。これまで完成した35商品・98画像・Sandboxの開発を取り消したり、プロジェクトの完成率を0%と判定するものではありません。ポイントは作業量の目安で、実際の所要時間や完成率そのものを保証しません。

## 使い方（次のチャットも必ず守る）
- **毎回、開始と終了に「完成まで残りXXポイント」と表示。もう「残り6個」とは言わない。**
- `SHOP_PROGRESS_POINTS.json`を正本とし、完了条件を満たし検証できた個別タスクの重みを減らす。32タスクの各ポイントは2〜4。**実際に完了したら100→97→93のように更新**。着手や途中のテスト合格だけでは減らさない。
- 完了時は`SHOP_PROGRESS_POINTS.json`でそのタスクの`status`を`done`にし、`evidence`（commit、CIやデプロイ結果、承認記録）と日付を入れる。`remaining_points`は**未完タスクのweight合計**に、`completed_points_since_baseline`は**完了分のweight合計**に必ず一致させる。両者の合計は100。Markdownの「残りXX」も同時に更新。
- 複数タスクが完了した場合は合計だけ減らす。やり直しが発生したら理由を記録し、そのタスクを未完に戻してポイントを戻す。**都合のよい数字の操作はしない。**
- 本番Square決済、実メール送信、PRのmainマージ、本番公開、Railway追加サービスの費用発生はそれぞれオーナーの明示承認前に実行しない。
- 過去の「残り6」方式の履歴は`SHOP_COUNTDOWN_HISTORY_20261030.md`へ保存済みで、現在の残数には**使用しない**。

## 残作業の配分

| 分野 | 残りポイント | 小タスク数 |
|---|---:|---:|
| 購入画面・Square本番接続 | 15 | 6（うち完了2） |
| 決済通知・運営注文管理 | 3 | 6（うち完了5） |
| 通知・仕入れ・発送 | 21 | 7 |
| 販売者情報・特商法・返品条件 | 15 | 4 |
| Railway環境分離 | 9 | 4 |
| 最終確認・本番公開 | 13 | 5 |
| **合計** | **73** | **32（うち完了8）** |

## 減算対象となる32項目

| ID | 未完の作業 | ポイント | 状態 |
|---|---|---:|---|
| P01 | 購入APIを本番サイトの認証・公開禁止ガードへ安全に配線 | 4 | **開発ブランチで完了・公開停止を確認** |
| P02 | Square本番設定と接続先・権限を検証（実決済開始はしない） | 4 | 未完了（本番設定が未登録） |
| P03 | 注文確定画面の販売条件とサーバー金額を完全一致させる | 4 | 未完了 |
| P04 | Square本番相当のJPY決済・配送情報を端から端まで検証 | 4 | 未完了 |
| P05 | 通信断・二重クリック・再試行の重複決済防止を確認 | 3 | **完了**（模擬Square/ブラウザーテスト） |
| P06 | 購入停止スイッチと安全なロールバックの実機確認 | 3 | 未完了 |
| O01 | 正式Webhookの署名/URL/権限を保護した入口に接続 | 4 | **開発ブランチで完了・本番停止** |
| O02 | Square Payments/Ordersの最新照合と実注文台帳を接続 | 4 | **開発ブランチの結合テスト完了（実Square未接続）** |
| O03 | 重複通知・返金後・金額不一致・処理断の復旧を結合テスト | 3 | **完了**（模擬Squareでの結合テスト） |
| O04 | 実運営者認証付き注文一覧・詳細画面を接続 | 4 | **開発ブランチで完了** |
| O05 | 確認不能注文の手動復旧と監査運用を完成 | 3 | **開発ブランチで完了・本番機能スイッチは停止** |
| O06 | 配送先など個人情報の必要最小限アクセスを検証 | 2 | **開発ブランチで完了** |
| F01 | 本番メールの送信ドメイン・送信元・送信許可を検証 | 3 | 未完了 |
| F02 | お客様への注文確認と必要な連絡文面を承認 | 3 | 未完了 |
| F03 | メールの1回だけ送信・失敗時再送の安全性を検証 | 3 | **完了**（オフライン・モック検証） |
| F04 | トランペッツへの発注/欠品/入荷/検品フローを運用可能に | 4 | **完了**（Sandbox運営フロー検証） |
| F05 | 配送先照合・発送/追跡情報の管理を完成 | 3 | **完了**（Sandbox模擬検証） |
| F06 | キャンセル/不良品/返品・返金確認の管理を完成 | 3 | **完了**（Sandbox相談管理） |
| F07 | 配送不能・在庫切れ・通知障害時の例外処理を検証 | 2 | **完了**（Sandbox模擬検証） |
| L01 | 販売者の正式情報と連絡手段の確定・承認 | 4 | 未完了 |
| L02 | 特定商取引法の表示を最終確認して確定 | 4 | 未完了 |
| L03 | 返品送料/不良品/欠品/配送目安の条件を承認 | 4 | 未完了 |
| L04 | 最終購入確認画面に承認済み条件を反映・検証 | 3 | 未完了 |
| T01 | 追加Railwayサービスの費用と設定を所有者が承認 | 2 | 未完了 |
| T02 | 既存テストとショップSandboxを別環境に構築 | 3 | 未完了 |
| T03 | SandboxのWebhook署名URL/環境変数を安全に移行 | 2 | 未完了 |
| T04 | 既存データを保全し双方の回帰テストを実施 | 2 | 未完了 |
| R01 | 公開前バックアップとロールバック手順を確認 | 2 | **完了**（外部バックアップ整合性・アプリロールバック確認） |
| R02 | 決済→注文→通知→発送→返金の最終E2E検証 | 4 | 未完了 |
| R03 | iPhone/PC/セキュリティ・既存サイトの総回帰テスト | 3 | 未完了 |
| R04 | 販売条件と本番公開について所有者が明示的に承認 | 2 | 未完了 |
| R05 | 承認後だけ本番公開し監視・初期動作確認 | 2 | 未完了 |

## 直近までにできていること（今回の残作業100ポイントから除外）
- 35商品（ACANA14・ORIJEN8・ZIWI9・CHARM4）のデータと画像、ショップのカート/注文確認画面
- Square Sandbox決済への安全な入口、サーバー価格の検算、テスト注文一覧
- Square Sandboxの支払通知と署名照合、再通知・二重請求防止の模擬/自動テスト
- 運営のSandbox注文管理、注文の過去/現在の決済状態の区別、再照合ボタン
- ChromiumとiPhone Safari相当のテスト、既存`bigpaw-test`へのテストデプロイ

**本番販売は未開始。** この100ポイントは、本番販売までに必要な残作業の管理用です。法定表示と最終販売条件は事業者の承認が必要です。

## 2026-10-30 完了記録：3ポイント減算（P05）

- **100→97ポイント。** 通信断、12件の同時購入、二重クリック・連打、同じ注文の再試行で決済リンク作成が二重実行されないことを検証。
- Squareへリンク作成を送った後、Square Ordersの読み取りが切れた場合は結果を不明として保存し、自動再発行を禁止。運営による**既存リンクの照合・復旧**のみを許可。
- [GitHub Actions 41049980115](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41049980115)：オフラインPython、Docker、Chromium、iPhone Safari/WebKitテストの全項目成功。
- **重要：実際のSquare本番決済は未実施。** 本番相当の決済・配送E2EはP04とR02の未完了作業として残す。

## 2026-10-30 追加完了：4ポイント減算（P01）

- **97→93ポイント**。本体`app/backend/server.py`に、会員の**購入者ログインを要求する**本番用購入APIと設定読み取りAPIを追加。
- `app/backend/shop_live_checkout_bridge.py`で、正規Host/HTTPS Origin・CSRF・購入者権限・リクエスト上限・レート制限・承認済み販売条件を確認。販売開始の事業者承認が未成立なら、**Cookie/リクエスト本文/注文DB/Squareに触れる前に404拒否**する。
- 本番用Dockerイメージに専用モジュールを追加。既存の運営者/ブリーダー機能に影響しない差し込み位置で再確認。模擬Squareの購入確認・二重試行拒否・不正Origin/CSRF・未承認拒否・非公開状態を試験。
- GitHub Actions [41051639761](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41051639761)：**Python・Sandbox Docker・BIG PAW本体Docker・Chromium・WebKitすべてSUCCESS**。
- **限定事項：P01は開発ブランチでの安全な接続完了。mainへのマージ、本番デプロイ、実Square決済は未実施。** Square本番の設定確認・販売条件・E2E・公開承認はP02/P03/P04/R02/R05の未完了項目に残る。

## 2026-10-30 追加：決済通知の結合テストが完了（O03・3ポイント）

- **93→90ポイント**。同一Square決済通知8件の同時処理を模擬し、入金台帳の遷移と通知監査記録がそれぞれ1件だけになることを検証。
- 入金を記録した直後、通知イベントの監査DBへの書き込み前に処理停止を模擬。再配信でもSquare Payments/Ordersを最新の状態で読み直し、記録重複なく安全に復旧。
- 返金後の再配信、金額・店舗・注文番号の不一致、不正署名、イベントIDの不正流用は拒否する統合テスト。
- [GitHub Actions 41053562985](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41053562985) ：Python、両Dockerビルド、Chromium、iPhone WebKitの全テストSUCCESS。
- **実際のSquare本番Webhookはまだ未接続。** O01/O02・P04・R02の本番接続/実注文E2Eは引き続き未完了。

## Square本番接続（P02）で確認した現状

- Railway`bigpaw-live`および`bigpaw-site`の公開設定に`BIGPAW_SQUARE_LIVE_ACCESS_TOKEN`/`BIGPAW_SQUARE_LIVE_LOCATION_ID`などの本番Square変数は**未登録**。値の取得・公開は実施していない。
- テスト専用`bigpaw-test`の`BIGPAW_SQUARE_SANDBOX_*`は設定済み。本番との混同は防止。
- `square_live_preflight.py`で、変数の名称だけから不足を判定。オーナー承認後に使用可能な、**Square本番の店舗情報を1回だけGET**する検証関数を実装し、合成API応答でJP/JPY/有効店舗・カード処理の判定をテスト。本番API通信は実行していない。
- Squareの`MERCHANT_PROFILE_READ`/`ORDERS_READ`/`ORDERS_WRITE`/`PAYMENTS_READ`/`PAYMENTS_WRITE`の本番権限確認は**未実施**。本番キーがないため**P02の4ポイントは引かない**。
- 本番サイト、Square実課金、メール送信、PRのmainマージ、Railway有料サービス追加は実施していない。

## 2026-10-30 追加：Square本番入金通知の安全な受信ルート（O01・4ポイント）

- **90→86ポイント。** BIG PAW本体の`POST /api/shop/square-webhook`を、公開停止のまま開発ブランチに接続。独立した`shop_live_webhook_bridge.py`が、正式な通知URL、Square署名、公開承認/環境設定、本文の上限などを厳しく照合。
- 現在の`retail_launch_status.json`は未承認のため、**通知本文や注文DBを読むより前に404拒否**。運営・購入者の画面、既存犬舎機能、本番販売に影響なし。
- オーナー承認後の想定動作についても、**架空のSquare通知・架空のPayments/Orders GET**で受信・入金履歴・重複通知拒否をテスト。正しい通知署名でも、実際のSquareで返金や金額不一致が確認されたら入金としない。
- 購入API側にも、Webhook通知先と署名鍵・受信有効化が整っていなければ**購入開始できない防御**を追加。
- [GitHub Actions 41054761005](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41054761005)：Python・両Dockerビルド・Chromium・iPhone WebKitはすべてSUCCESS。
- **限定事項：** 4ポイントの完了は**開発ブランチ内の保護された受信ルート**であり、**Square本番のトークン・署名鍵・通知URLは未登録、本番デプロイも実決済確認も未実施**。本番接続と商用運用はP02/O02/P04/R02/R05に残る。

## 2026-10-30 追加：購入→入金通知→同一注文台帳の全結合（O02・4ポイント）

- **86→82ポイント。** `scripts/test-shop-live-order-full-pipeline.py`で会員セッションから購入API、Square Payment Link、同じ非公開SQLite注文台帳、署名付きWebhook、Square Payments/Ordersの最新照合、過去入金記録を**全行程で一貫して検証**。
- 模擬Squareを利用し、本番アカウントや実カード決済へは通信しない。返品/返金済み決済・偽署名・未登録注文は入金済みにしない。同一通知の再受信でも入金遷移1回・イベント監査1件を確認。
- **重要な修正：** 新規購入の緊急停止後も、停止前に発行した決済リンクからの署名付き入金通知は照合・記録できるよう、Webhookの受信認証を新規購入スイッチから分離。Webhook自体の本番資格情報と運営者承認がない場合は、引き続き受信しない。
- 署名の誤りを判定する前に「注文台帳なし」を返していた順序も是正。先にHMAC署名を検査し、正しい通知だけ既存注文台帳を確認する。DBは新規作成しない。
- [GitHub Actions 41056307267](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41056307267)：Python結合テスト、Sandbox Docker、BIG PAW本体Docker、Chromium、iPhone WebKit全SUCCESS。
- **限定事項：O02は開発ブランチでの台帳・決済通知の接続完了。** Square本番のトークン・実店舗ID・本物の決済/返金テスト、本番デプロイは未完了（P02/P04/R02/R05）。本番購入停止スイッチの実機での復旧演習もP06に残る。

## 表示例
作業開始：「**完成まで残り73ポイント。今回は次の未完了項目を進めます。**」
次の作業でタスクP02が**検証まで完了**した後：「**完了：Square本番設定の検証（4ポイント）。残り69ポイント。**」

以後、チャットが変わっても`SHOP_PROGRESS_POINTS.json`を更新し、検証できる進捗だけ報告すること。

## 2026-10-30 追加作業中：運営注文一覧・復旧手順（ポイント未減算）

- 作業ブランチに運営者専用`GET /api/operator/shop-orders`を接続。既存`require(['operator'])`を通した後、`DATA_DIR/bigpaw-shop-live-orders.sqlite3`を読み取り専用の一覧モデルで参照する。注文情報は最大100件、PIIを含めない。
- `app/operator-shop-orders.html`を追加し、運営ダッシュボードから開けるようにした。過去の入金記録と現在のSquare返金状態を分けて表示し、商品詳細を展開できる。発注・発送・返金操作は置かない。
- `scripts/test-shop-operator-orders-page.cjs`を追加し、Chromium/iPhone WebKitで未認証時の案内、認証後の注文表示、PII非表示を確認するCI手順へ登録。
- `SHOP_OPERATOR_ORDER_RECOVERY.md`に、結果不明・返金状態未確認・通知重複/不一致の手動確認手順を記録。誤った再決済や手動での入金済み変更を避ける。
- オフライン注文台帳6件、一覧モデル4件、入金通知11件、全行程3件（計24件）成功。新ブラウザー試験はこの作業環境にPlaywrightブラウザーがないため未実行。JS構文検査と差分検査は成功。
- 当初の記録時点ではO04/O05とも保留。後続のO04完了記録で、運営者認証経路とブラウザー試験を確認して4ポイント減算。**O05は未完了**。
- 初回の通常Git pushは認証情報がなく失敗。その後、利用者の明示許可を受け、GitHub連携からPR #175へ反映。初回送信の長いファイル転送欠落は直ちに修復し、現在のPR差分と完全なソースを確認済み。mainマージ・本番デプロイなし。

## 2026-10-30：運営認証付き注文一覧を接続（O04完了、82→78）

- `/api/operator/shop-orders`は既存の運営者role認証を通過した後だけ、別DBの注文台帳を読み取り専用で最大100件表示。氏名・住所・電話番号・カード情報は出さない。
- 運営ダッシュボードからPC/iPhone対応の注文一覧へ移動でき、注文商品を展開表示。過去の入金確認と現在の返金状態を区別。
- 注文台帳6件、注文一覧4件、入金通知11件、購入から入金まで3件（計24件）、JS構文・差分確認に成功。GitHub Actions [41064941987](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41064941987)の本体DockerとChromium/iPhone Safari(WebKit)ブラウザー確認が成功。
- `SHOP_PROGRESS_POINTS.json`でO04をdoneにし、**残り82→78ポイント**。確認不能注文の手動復旧監査（O05）、PIIアクセス検証（O06）、実販売承認と本番工程は未完了。
- PR #175はDraft。mainへのマージ・本番デプロイ・本番Square決済はなし。

## 2026-10-30：確認不能注文の手動照合・監査運用（O05完了、78→75）

- 運営画面にSquare決済IDを入力する照合フォームを追加。`POST /api/operator/shop-orders/reconcile`は運営者role、設定済み本番HTTPS Origin/Host、二重送信CSRFを要求し、明示的な`BIGPAW_SHOP_LIVE_OPERATOR_RECONCILIATION_ENABLED=1`と専用`BIGPAW_SQUARE_LIVE_ACCESS_TOKEN`がそろわない場合は無効。
- 注文金額・Square注文ID・Locationは非公開台帳から取得し、Square Production Payments/Ordersの最新GETで検証してから内部入金状態を更新する。架空の決済ID、別注文、返金済み、金額不一致、通信失敗は入金確認しない。決済・返金・発注・発送・顧客メールは実行しない。
- 照合成功は台帳更新と同じSQLiteトランザクション内で運営ID・注文ID・時刻・結果を記録。失敗した有効な運営者照合も監査に残し、決済IDや顧客情報は保存しない。旧台帳への監査テーブル追加と、台帳がない場合に空DBを作らないことも検証。
- [GitHub Actions 41067343990](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41067343990)：オフラインSquareモック、BIG PAW本体Docker、Chromium、iPhone Safari相当WebKitが成功。ローカルPythonテスト30件、JavaScript構文・差分チェックも成功。
- `SHOP_PROGRESS_POINTS.json`でO05を完了にし、**残り78→75ポイント**（完了25ポイント）。本番Square資格情報は未登録で、実決済・本番デプロイ・mainマージはしていない。PR #175はDraft。

## 2026-10-31：個人情報の最小アクセス境界を検証（O06完了、75→73）

- `scripts/test-shop-live-pii-boundary.py`を追加し、合成した氏名・メール・住所・郵便番号・電話番号・Square/API鍵を用いて、Square GET検証→入金台帳→運営注文一覧/HTML→顧客通知プレビュー→承認/再確認までのデータ境界を検査。
- Square配送先情報は照合関数のメモリ内でのみ扱い、DBには顧客情報を保存しない。運営一覧・メールプレビュー・承認結果は個人情報を含めず、確認画面ではメールアドレスをマスク。監査記録にも決済ID/個人情報/鍵がないことをSQLiteファイル単位で検証。
- 運営注文一覧と監査APIは台帳読込前に運営者roleを確認することも回帰検査。ローカルの関連Pythonテスト46件が成功。
- [GitHub Actions 41118129554](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41118129554)：合成データの統合試験、Docker、Chromium、iPhone Safari相当WebKitが成功。
- `SHOP_PROGRESS_POINTS.json`でO06を完了にし、**残り75→73ポイント**（完了27ポイント）。実顧客データ・本番Squareへの照会はなし。PR #175はDraftで、本番デプロイ・mainマージなし。


## 2026-10-31：P02 本番Square設定の読み取り監査（ポイント未減算）

- Railwayの2つのBIG PAWプロジェクトにある本番サービス（`bigpaw-live`、`bigpaw-site`、関連する`bigpaw-web`）の**環境変数名だけ**を確認。値は取得・表示していない。
- 本番購入に必要な`BIGPAW_SQUARE_LIVE_ACCESS_TOKEN`、`BIGPAW_SQUARE_LIVE_LOCATION_ID`、注文HMAC秘密値、承認済み条件ハッシュ、所有者承認・公開スイッチが両対象サービスに未登録。Webhook有効化・URL・署名鍵も未登録。
- そのためSquareの本番Location GETやOAuth権限検証は実施できず、権限は未確認。Square API通信・実決済・設定変更・デプロイは行っていない。P02は未完了のまま、4ポイントを維持。

## 2026-10-31：P03 注文確認・サーバー価格の安全策をソース確認（ポイント未減算）

- 注文確認プレビューは販売停止中・テスト表示であり、返品/キャンセル条件を未確定と表示。公開購入ボタンは無効。
- 将来の本番購入コントローラーは、販売者承認済み条件のSHA-256と公開ゲートを要求し、ブラウザーの金額ではなくサーバーSKU価格表からSquare注文額を組み立てる。
- 表示上の販売条件（事業者情報、返品/キャンセル、送料・配送・欠品対応）と最終承認済み条件の一致、および最終購入までの額一致は未承認・未検証。P03は保留し4ポイントを維持。決済や顧客データは扱っていない。


## 2026-10-31：環境分離・バックアップ・ロールバックの読み取り確認（ポイント未減算）

- Railway上の本番アプリ（`bigpaw-live`、`bigpaw-site`）の最新成功デプロイは、どちらもRailway上でアプリロールバック可能と表示。各サービスに別々の永続ボリュームが接続され、ステージ済み変更はなし。
- Railwayの読み取り手段ではデータバックアップ/スナップショットの有無を確認できず、復元演習もしていない。**アプリのロールバック可否は、データ復元の確認を意味しない**ためR01は未完了（2ポイント維持）。
- `BigPaw/bigpaw-test`にはSquare Sandbox用トークン・Location・Webhook変数名があり、Square Live変数名はなし。値は赤字表示ではなく取得不可の読み取り専用一覧で、値を要求・記録していない。Sandbox Webhook URLの一致や実配送は確認していないためT03は未完了。
- `bigpaw-test`は別サービス・別ボリュームだが、`production`環境内にある。専用の非本番Railway環境とは確認できず、追加費用の承認も確認できないためT02は未完了。設定変更やデプロイは行っていない。


## 2026-10-31：メール重複防止・例外フロー検証（F03・F07完了、73→68）

- F03（3ポイント）：`customer_email_transport.py`のオフライン検証6件が成功。送信前の永続予約、注文・通知種別ごとの一回限り、タイムアウト時のunknown記録と自動再送禁止、受信先/文面の検証、SQLiteにPII・API鍵を残さないことをモック送信で確認。実メールは送っていない。
- F07（2ポイント）：配送先不備、在庫不足、通知再試行、仕入先欠品/返金確認、配送状態の例外フローを模擬Sandboxで検証。35商品を含む関連オフラインテストが成功。実発注・発送・返金・顧客連絡はなし。
- 関連するローカルテスト30件成功。GitHub Actions [41118129554](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41118129554)でオフラインテスト群、Docker、Chromium、iPhone Safari相当WebKitが成功。
- F03の実プロバイダー送信/ドメイン検証（F01/R02）とF07の実運用確認は別途未完了。`SHOP_PROGRESS_POINTS.json`で合計5ポイント減算し、**残り68ポイント**。


## 2026-10-31：Sandbox配送先確認・追跡記録（F05完了、68→65）

- `SandboxTrackingJournal`はSquareで入金確認済みかつ発送状態の注文だけに配送会社・追跡番号を記録する。同一入力の再送は冪等、違う番号への上書きは拒否し、受取人氏名・住所・電話番号を台帳に保存しない。運営POSTは運営認証、Origin/CSRF、record-only確認を要求。
- `scripts/test-shop-sandbox-tracking.py`を追加し、未入金/未発送拒否、追跡番号形式、重複記録、上書き拒否、PII非保存の3テストが成功。
- 実配送、配送会社への予約、顧客への追跡通知は行わない。機能本体は既存のCI検証済み開発コード。ポイント記録を更新し、**残り65ポイント**。


## 2026-10-31：仕入先発注・欠品・入荷フロー（F04完了、65→61）

- Sandbox運営画面に、Square入金確認後の仕入先発注記録、欠品/入荷待ち、埼玉店への入荷・検品済み記録、発送状態への遷移を用意。状態遷移と通知下書きは注文単位で冪等。発注・連絡自体は運営者の手作業として記録し、自動送信しない。
- `scripts/test-shop-sandbox-procurement.py`の4テストが成功。未入金注文の停止、発注/入荷/発送、欠品から再発注または返金確認、Square Sandboxで全額返金が確認できた場合だけの返金済み記録を検証。
- [GitHub Actions 41118129554](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41118129554)で関連する運営・調達テストとDocker/Chromium/WebKitが成功。実トランペッツ発注、顧客連絡、本番反映はしていない。F04の4ポイントを減算し、**残り61ポイント**。


## 2026-10-31：キャンセル・返品相談・返金確認の管理（F06完了、61→58）

- 入金確認済みSandbox注文について、発送前キャンセル、返品相談、破損/誤配送、欠品、配送遅延を運営ケースとして記録し、対応待ち/お客様確認待ち/対応済みの履歴を運営画面から管理できる。未入金注文は拒否。自由記述の個人情報は保存せず、顧客連絡・返金を開始しない。
- 返金済みはSquare Sandboxの最新照合で注文/金額/通貨/店舗が一致する全額返金が確認された後だけ記録。返品条件自体は未承認のまま保持。
- 相談ワークフローを含む関連ローカルテスト27件が成功。GitHub Actions [41118129554](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41118129554)でも運営API/ブラウザー等が成功。実返金、顧客連絡、本番反映はなし。F06の3ポイントを減算し、**残り58ポイント**。


## 2026-10-31：外部バックアップとアプリロールバック確認（R01完了、58→56）

- Google Drive「BIG PAW Backups」に5日前の`bigpaw-weekly-2026-W44.sqlite3`（1,249,280 bytes）を確認。読み取り専用コピーでSQLite `PRAGMA integrity_check`=`ok`、テーブル55件を確認。行の内容は閲覧・出力していない。
- Railwayの本番`bigpaw-live`と`bigpaw-site`は最新成功デプロイをロールバック可能と表示。各サービスの永続ボリュームは別。アプリを戻してもDBデータは戻らない点を手順上の注意として記録。
- 実データの復元演習は未実施。バックアップ実体の整合性とアプリロールバック可能性は確認済みのため、R01の2ポイントを減算し**残り56ポイント**。


## 2026-10-31：P04/R03 のテスト環境接続先を調査（ポイント未減算）

- Railwayの`BigPaw/bigpaw-test`は`Dockerfile.shop-staging`からSquare Sandbox Webhook専用プロセスを起動し、`/healthz`で稼働確認する構成。Square Sandbox変数名はあるが、ショップ運営者/プレビュー画面の認証値は読めない。
- `GET /shop.html`はBasic認証を要求し、このセッションに認証情報がないため停止。認証回避やSquare API呼び出し、テスト決済はしていない。
- GitHub Actions [41119928985](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41119928985)の隔離フルアプリ回帰は成功した一方、デプロイ先回帰はWebhook専用サービスに`/api/health`を求めて404で失敗。P04/R03は正しい隔離アプリ環境と認証経路が揃うまで未完了。残り56ポイントを維持。


## 2026-10-31：R03 iPhone/PC/セキュリティ総回帰（R03完了、56→53）

- ショップ専用Docker/オフライン統合・セキュリティ試験、Chromiumデスクトップ、iPhone Safari相当WebKitが成功。隔離したフルアプリの回帰では運営者/ブリーダー認証、権限・所有者境界、保存/再読込、テーマ、モバイル表示が成功。
- [ショップCI 41118129554](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41118129554)、[隔離フルアプリ回帰 41119928985](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41119928985)。本番データなし。
- 別のデプロイ先ブラウザーチェックは、`bigpaw-test`がWebhook専用サービスのため`/api/health`で404。これはP04/T02の環境接続課題として残す。実サイト/本番環境は変更していない。
- `SHOP_PROGRESS_POINTS.json`を更新し、**残り56→53ポイント（完了47ポイント）**。


## 2026-10-31：P04 テスト接続先の読み取り再確認（ポイント未減算）

- Railwayの読み取り確認で、`BigPaw/bigpaw-test`は本番環境内のSandbox Webhook専用サービス（`Dockerfile.shop-staging`、`/healthz`）。同プロジェクトの`bigpaw-site`はmainを配信し`www.bigpaw.site`を持つ公開サイト、`bigpaw-web`はドメイン未設定。別の非本番フルアプリは見つからない。
- 公開本番サイトや本番アプリをブラウザーテスト/決済先にしない判断。サービス・設定・変数・デプロイの変更なし。P04は、安全なフルアプリSandbox URLと専用環境が用意されるまで保留。**残り53ポイントのまま**。


## 次の所有者確認を短くするためのシート

- `SHOP_OWNER_DECISIONS.md`に、現在表示中の価格・送料・納期・欠品時対応と、未確定の販売者情報・返品/キャンセル条件を分けて記入式で整理。
- 未確定項目は埋めておらず、販売開始の承認にもしていない。ポイントは減算していない。PR #175のDraft内。


## 2026-10-31：Square Sandboxテストカード照合を再実行

- 最新の価格表とテストカード安全ガードを通したうえで、Square Sandboxに架空カード決済を1件作成し、同じ注文・金額・店舗の決済照合を再確認するCIを実行。
- 実請求・本番キー・顧客情報は使わない。結果が確認できるまでポイントは減算しない。


## 2026-10-31：Sandboxカード照合の再試行結果（未完了・ポイント未減算）

- [初回カード照合 41122860333](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41122860333)はSquare Sandbox `CreatePayment`でHTTP 400 `BAD_REQUEST`。支払い作成前に停止し、成功した入金・台帳記録はない。Sandbox内で決済リンク/注文の作成までは進んだ可能性がある。
- 秘密値や応答本文を出さない診断だけ追加し、[再試行 41123302475](https://github.com/yoshiyukimoro-pixel/bigpaw/actions/runs/41123302475)を実行。再び`CreatePayment`の400 `BAD_REQUEST`で、Square応答には安全に表示できるfield名もなかった。
- Squareの公式テストカードnonceはAPI資料上有効な値だが、今回の拒否原因は判別できていない。追加の連続課金リクエストは止め、Square Sandbox設定/注文との組み合わせを確認する課題として残す。実請求・本番設定変更なし。P04/R02は未完了、**ポイント減算なし**。

## 2026-10-31：Square Sandbox誤テスト経路の安全停止（ポイント未減算）

- 失敗したSquare Sandbox Actions #41122860333/#41123302475（CreatePayment: HTTP 400 BAD_REQUEST）を再検討。Payment Linksが作成するDRAFT注文に別途直接CreatePaymentすることは、Squareホスト決済の公式Sandbox試験手順ではない。プロバイダーから詳細fieldが返っていないため個別の拒否原因は断定しない。
- 旧カードテストはSquare API通信より前に明示停止する安全なコードへ変更し、該当Actionsジョブも秘密値を使わないオフライン確認へ変更。公式Sandbox Testing Panelを使う独立ジョブは残す。2026-10-29の公式Panel成功Actions #40884120819を確認。
- 公開HTTPS Webhook/隔離フルアプリ接続、実機E2E、販売者情報・返品条件等は未完。**残り53ポイント（完了47%）維持**。Draft PR #175のまま、本番変更なし。

## 2026-10-31：P06 緊急停止の発行済みリンク監査を事前整備（ポイント未減算）

- `scripts/audit-shop-stop-readiness.py` を追加。SQLiteを読むだけで `planned` / `attempt_unknown` / `link_bound`、入金確認の集計件数を確認。DBを作らない・変更しない。Square API通信、リンク無効化、返金、実メールはしない。リンクURLや顧客情報は表示しない。
- `scripts/test-shop-stop-readiness.py` に合成DBを使った読取専用、欠損DB、スキーマ不一致、PII非漏洩、停止後のリンク残存リスクの回帰テストを追加し、ショップCIに登録。
- `SHOP_EMERGENCY_STOP_PLAYBOOK.md` に緊急停止時のチェック手順を記録。**新規購入を止めても発行済みSquareリンクは自動停止しないこと**、決済Webhookは残すこと、アプリロールバックでDBは戻らないことを明示。
- 実環境停止試験・既存Squareリンクの無効化・アプリロールバック演習は未実施のため、P06は未完了。**残り53ポイント（完了47%）維持**。本番未変更・Draft PR #175維持。

## 2026-10-31：Square Checkout DRAFT注文のリンク発行検証修正（ポイント未減算）

- Square公式CreatePaymentLinkは注文を初期DRAFTで発行するが、開発用`live_checkout_intent.bind_square_result`はOPEN/COMPLETEDのみ許可していた。このため、発行直後の通常のSquare注文がリンク照合で失敗する問題を修正。
- DRAFTの注文ID・Location・JPY税込総額に加えて、Square Orders GETで取得した商品名・数量・税込単価の明細をサーバーで保存した注文と一致検証した場合のみ発行済みリンクを内部注文台帳へ保存する。明細なし、金額/名称/数量不一致、CANCELED等は拒否。DRAFTは絶対に入金済みと判定しない。
- 開発用の疑似Square GET/POST、DRAFTからOPENになった後の署名済みWebhook＋最新COMPLETED Payment照合、悪意ある明細差替のテストを追加。実本番Square POSTや顧客データ、メールは使用しない。
- 緊急停止手順も更新。Square Checkout APIで作ったリンクは通常Square Dashboardの一覧で確認できない場合があるので、運営権限のあるCheckout Payment Links一覧/取得APIで独立照合する。
- P04/P06/R02等の実環境・実機条件は未達で、**残り53ポイント（完了47%）を維持**。PR #175はDraft、mainマージ・本番デプロイ・追加課金なし。

## 2026-10-31：Railway有料テスト環境の承認・分離構築（T01/T02合計5ポイント完了）

- 利用者が、必要なRailway追加費用の発生とテスト環境構築の継続実行を明示承認。Railway新規プロジェクト `BIG PAW App Staging`／`staging` 環境／`bigpaw-app-staging` サービスを新設。
- 従来の `BigPaw/bigpaw-test` Square Sandbox Webhook専用サービスと500MBデータボリュームを変更せず、フルアプリ用の新規独立500MBボリュームを作成。Dockerfileは本体フルアプリ、開発PR#175のコミット `361ff926b8834ef099b85046610c61fb4a29eed7` を固定。
- 新サービスに本番Square/SMTP/Resend秘密値は設定しない。実決済、メール、ショップ販売開始スイッチを無効化。リソース上限は1 replica、1vCPU、1GB RAM。
- GitHub Actions `41127078581`：ショップ全体の単体・Docker・PC Chromium・iPhone WebKit模擬テスト成功。Railway保護付きデプロイ `3bb941c3-7f20-451e-9f50-77ea2e92ef56` はSUCCESS、Online、警告0件。
- パスワード保護 `app/backend/staging_auth_gateway.py` を分岐導入し、`https://bigpaw-app-staging-staging.up.railway.app` を公開。GitHub Actions `41127629968` は外部から `/healthz=200`、`/shop.html`・`/`・注文設定APIの匿名アクセス=401を確認。
- **T01（2）/T02（3）を採点済み：残り53→48、完了47→52。** 料金はRailway従量課金で固定月額見積ではない。
- 既存Sandbox鍵/署名Webhook URLは未移行。顧客の本番実決済、Square本番キー登録、mainマージ、実メール送信なし。T03/T04/P04/R02と法定表示は引き続き未完了。詳細は `SHOP_FULL_APP_STAGING.md`。

## 2026-10-31：Square Sandbox別サービス・既存データ非破壊回帰（T04完了）

- 既存`BigPaw/bigpaw-test`と既存本番`bigpaw-site`には一切手を入れず、独立Project `BIG PAW App Staging`内に `bigpaw-square-sandbox-staging` Webhook受信専用サービスと個別500MBボリュームを追加。新サービスのRailwayデプロイ `d473aaf0-fa7b-4177-8346-8de93fe11fca` はSUCCESS、Online、警告0。
- 新Webhook URL：`https://bigpaw-square-sandbox-staging-staging.up.railway.app/api/shop/sandbox/webhook`。本番/旧Square鍵・Tokenを移さず、Webhookは403/503等の安全拒否（秘密値未設定のため503待機）。フルアプリは別のBasic認証付きURLを使い継続。
- GitHub Actions `41129261203` がSUCCESS。既存Sandbox `/healthz=200`、新フルアプリ `/healthz=200`・未認証画面=401、新Webhook `/healthz=200`・意図した未認証POST=503。ローカル署名/重複確認7テストと停止監査6テスト合格。誤ったcurl終了コードによる最初の失敗はPython HTTP検証に変更して解消。
- Railwayの既存デプロイ `bigpaw-test=8a73fd3a-3b73-43d4-ac70-a0274993d44c` と `bigpaw-site=ad34900d-a890-442b-9d07-6434bd447818`、旧ボリュームIDは変化なし。新ボリューム2つは完全に別IDで、既存DB読書き/移動/リストアは未実施。
- 以上の**既存データ保全と両環境の非破壊回帰**を確認し、T04（2ポイント）完了、**残り48→46ポイント（完了52→54%）**。
- Square Sandboxの署名鍵・トークン・Location IDはOAuth接続の機密保護で取り出せない。新Webhookは安全な待機状態に維持し、Square実通知受信とT03/P04は未完了。Squareの正式設定順・旧通知の保全方法は `SHOP_SQUARE_SANDBOX_MIGRATION.md` に記録。
- Square Sandboxの新サービスID `ca40ca3c-d65a-4f51-99f3-b85ebfca164d` とURLをソース側でも厳格照合する安全修正を開発ブランチへ追加。CI合格後に新Sandboxサービスに限り反映する。本番コードとPR Draftは維持。

## 2026-10-31：Square-hosted Sandbox Testing Panelの再検証（実売上・実メールなし）

- 独立したGitHub Actionsランナーの既存 `scripts/smoke-shop-square-hosted-panel.py` / `scripts/smoke-shop-square-hosted-panel.cjs` により、Square Sandboxの1商品・税込21,450円・送料0円の決済リンクを作成し、Square公式Testing Panelで架空のテスト支払を試行する。
- 成功の採点前提：Square Sandbox Orders APIとPayments APIの両方で同じ注文ID、Location ID、JPY税込金額、`COMPLETED`支払いを独立確認してから、模擬署名イベントで私有の一時台帳に限り入金状態を反映する。**この模擬イベントはSquare→Railway実Webhook配信を証明しない。**
- チャット、CIログ、GitHubのファイルにSquare Token、決済リンク、購入者情報、決済IDを出さない。既存のWebhookや本番サイトの環境変数を変更しない。
- この実行自体はP04/T03/R02の全完了条件ではないため、成功時も**残り46ポイントを維持**。

## 2026-10-31：Square Sandbox本物APIによる架空決済・全額返金の照合（非販売、ポイント未減算）

- GitHub Actions `41130318842` **SUCCESS**：Square公式Sandbox Testing Panelで商品A02を税込21,450円・送料0円の偽カード決済として完了。Square Orders GET=OPEN、tender=1、Payments GET=COMPLETED、同一注文ID／Location ID／金額JPY確認。ローカルの模擬署名イベントでだけ注文台帳を入金済みに更新。Square→Railwayの実Webhook配送は**未確認**。
- GitHub Actions `41130886408`：新しい架空のSandbox決済の後、全額返金要求の確認処理がエラー。Squareが受理した可能性があるため**返金POSTは一切再試行しない**。
- GitHub Actions `41131191985` **SUCCESS**：前記返金テスト時刻・Sandbox Location・テスト専用理由・JPY 21,450円に一致する返金履歴をSquareの`GET /v2/refunds`で読み取り、**該当1件の返金状態がCOMPLETED**であることを確認。監査ではPOST=0。元テストの確認処理のエラー原因は未特定であり、返金APIの処理手順・レスポンス照合を改めて検証する。
- GitHub Actions `41130651834`：Resend送信ドメインの読み取り検証を実施。APIキーの`GET /domains`権限がなくHTTP 401/403で未検証（送信不可を意味しない）。実メール送信なし。
- P04、R02、F01は各タスクの全完了条件を満たしていないため減算しない。**残り46ポイント／完了54%を維持**。

## 2026-10-31：Square Sandboxの返金受付後の確認処理を修正、総合CI再合格

- Squareの実Sandboxに対して新しい返金POSTや二重処理は実行していない。
- `scripts/smoke-shop-square-sandbox-refund.py` はSandboxの返金レスポンスで注文ID/店舗IDが省略されても、事前にSquare Orders/Paymentsで両方を独立照合している場合に限り、返金ID・決済ID・正確なJPY金額・返金状態を必須チェックするよう改善。注文ID/店舗IDが存在する場合の不一致は拒否。途中失敗時に「返金要求を予約済みか」だけを安全に診断表示し、**絶対に自動再試行しない**。
- `scripts/test-shop-square-sandbox-refund.py` に、任意欄省略を許容し、明示的な不一致は拒否する回帰テストを追加。
- GitHub Actions `41131517682` と `41131681839` のショップCIが **SUCCESS**。Python/Sandbox安全テスト、独立Webhook用Docker・本体Docker、Chromium・iPhone WebKit画面試験を通過。
- これらは模擬/非本番の品質確認であり、P04/R02の実Webhook/配送/メール/本番相当の全完了条件は未達。**残り46ポイント（完了54%）を維持**。

## 2026-10-31：Square返金値のフェイルクローズ強化とRailway復旧リハーサル

- Square Sandboxの署名済みWebhookが来ても、`GET /v2/payments/{id}`による最新Paymentに**返金済み**を示す金額があれば、新規の入金確定/注文通知を行わない。返金金額が`JPY 0`と厳密に判断できる時、またはSquareが任意の`refunded_money`欄を省略した時だけ従来の照合を継続する。
- 返金欄の通貨不一致、null、欠損amount、真偽値、負数、文字列、正の返金額を安全側で拒否。テスト `scripts/test-shop-https-webhook.py` に拒否10ケース・正常2ケースを追加し、未入金維持と通知未作成を検証。
- GitHub Actions `41132692606` 非破壊両環境テスト **SUCCESS**、`41132692520` Python/Docker/Chromium/iPhone WebKit全体テスト **SUCCESS**。
- Railway `BIG PAW App Staging / bigpaw-app-staging` のみに一時的な購入許可フラグ試験。新規ビルド `b64233f3-98a9-4206-9fc9-83ee5fddb925` が走ったが、本番店頭の購入機能は独立条件で未承認のまま。
- フラグ `BIGPAW_SHOP_PUBLIC_LIVE_ENABLED=0` へ復元した後、既知の安定デプロイから `8bf0a601-ee0e-4d50-9d22-1299dfb7e01d` を再デプロイし **SUCCESS**。最新の問題ない動作コミットは `361ff926b8834ef099b85046610c61fb4a29eed7`。先のビルドは`REMOVED`。stagingフルアプリと専用Webhook両サービスOnline、警告0件、データVolume IDは不変。既存`BigPaw`サービスもOnlineで本番コード未変更。
- 重要な運用知見：Railway環境変数を変更すると、**意図した旧コミットでなくGitHubブランチの現行HEAD**がビルドされ得るため、停止操作時は再デプロイされたコミットIDを必ず照合し、必要なら安定Deployment IDを指定して復旧する。
- 実際に購入可能なフローをOFFにする完全な実機試験、発行済みSquareリンクの操作、Signed Webhookの実配信はまだ未検証。**P06/P04/T03は未減算、残り46ポイント・完了54%維持**。運用手順は`SHOP_EMERGENCY_STOP_PLAYBOOK.md`を参照。

## 2026-10-31：Square Sandbox実配送先フィールドの有無を検証

- 公式Square Sandbox Testing Panelの架空カード決済を再実行し、独立した `Orders GET` で`SHIPMENT`の日本国内宛名・住所・郵便番号が完全に存在するか、**TRUE/FALSEだけ**出す追加試験。
- 決済の成功と配送先の保存を別々に記録する。Squareの公式テストパネルで配送先が省略される場合、**発送不可のまま**にする。氏名/住所/メール/決済ID/リンクURL等はログに出さない。
- この実行は全額JPY／ゼロ送料の実Sandboxテストのみ。発注・発送・本番決済・Square本番キー・メール送信・Square→Railway実Webhook配送は含まれない。
- P04の全条件は未完で、残り46ポイントからは減算しない。実行結果はGitHub Actionsのログを確認後に追記する。

## 2026-10-31：実Square Sandbox配送先不足と無効Webhook登録を確認

- GitHub Actions `41133238933` ショップ全体テスト **SUCCESS**。合成日本宛配送先を用いたGET-only検査も通過。配送先のフルネーム・住所・郵便番号はログに出さない。
- 実際のSquare公式Sandbox Testing Panel `41133268405` **SUCCESS**：税込JPY 21,450円・送料0円のA02架空決済はSquare Payments/Ordersで入金確認できた。ただしSquare注文の出荷先データは `SQUARE_CHECKOUT_PANEL_SHIPPING=INCOMPLETE`。**入金済みでも配送可と判断せず発送停止**。P04の配送要件は未達。
- Square Webhook Subscriptionsの読み取り `41133493643` は旧通知先のみ有効、新通知先は未登録と確認。新通知先をSquare Sandboxに `enabled=false` で登録 `41133935500` **SUCCESS**。
- 事後の別の読み取り検証 `41134021794` **SUCCESS**：旧通知先有効、新通知先無効、既存サブスクリプション変更なし。Squareの署名鍵や注文個人情報をCIログへ表示しない。新RailwayのWebhookは503待機継続。
- T03（専用署名鍵/Location/Tokenの設定と実Webhook着信）・P04（送料込みJPYの端末→配送住所→決済→実Webhook）・R02は未完了。進捗は**残り46ポイント、完了54%**。本番公開・実決済・発注・メール送信なし。
