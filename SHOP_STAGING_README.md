# BIG PAW ドッグフードショップ（本番未公開・作業ブランチ）

2026-10-28 専用ブランチ feature/dogfood-shop-staging-20261028 で開発。
main へのマージも Railway へのデプロイも行わない。

## 実装済み
- app/shop.html：ACANA 14品、ORIJEN 8品、ZIWI 9品、CHARM 4品（合計35品）
- ブランド・年齢・用途・キーワードの検索、商品詳細
- 購入者向けに4ブランドの大きな選択カードを追加。初期表示もACANA→ORIJEN→ZIWI→CHARMのブランド別に区切る
- ACANAはアカナドッグ／ハイエストプロテイン／シングル、ORIJENは子犬／成犬／シニア、ZIWIはエアドライ／スチームドライで小分類。ブランド選択後は選んだ商品だけ表示
- ブランドの選択解除・商品名検索・用途／年齢絞り込みを維持。商品購入は引き続き不可
- スマートフォン対応のレイアウト、販売準備中の明確な表示
- メーカー価格表の希望小売価格（税抜）を35商品に照合し、**参考希望小売価格（税込）**を一覧・詳細に表示。現時点の実販売価格ではない
- **仕入価格は公開用サイト・GitHubに入れていない**。BIG PAWの販売価格・送料・在庫・注文・決済は未設定で購入ボタンは無効
- 既存の子犬関連画面、ホーム、API、DB、認証は編集していない
- ホームページからの導線も、正式公開までは追加しない
- 検索エンジン向け noindex,nofollow を付ける

## メーカーから提供された写真
利用者の添付4 ZIPを照合。33商品の正面写真あり。さらに2026-10-28に
ZIWI エアドライ ベニソン 2.5kg と エアドライ トライプ＆ラム 2.5kg の正面写真を受領。
メーカー確認により、この2商品は**4kgの取り扱いがまだなく**、販売対象は2.5kg。
写真の準備パックでは35商品すべての画像がそろった。
この作業ブランチの HTML は app/assets/shop-products/[slug].webp を参照する。
画像未配置時もブランドと商品名の代替画像を表示する。
**画像の実ファイルはまだ GitHub にアップロードしていない。**
添付ZIPと追加受領した写真から生成した軽量WebP 35ファイルは別途ダウンロード可能な準備パックに保管。

## 公開前に必要
1. 写真実体35枚を GitHub に追加
2. メーカーと全商品名・表示用途・成分・原材料・給与量・表現を最終照合
3. 仕入・販売税込価格・送料・出荷形態・納期・在庫方針を確定
4. 決済/注文/返品/特商法などを安全に実装
5. CI と PC・iPhone Safari 画面テスト、画像読込を合格
6. 子犬掲載・見学・動画・予約・運営/ブリーダー操作の回帰を合格
7. Railway の安定確認後に別途本番公開を判断

販売準備中のカタログであり、現時点では注文可能な EC サイトではない。

## 2026-10-28 お試しカート（非取引デモ）
- 商品詳細に「お試しカートに入れる」を追加。数量の加減・削除、参考希望小売価格の税込合計を確認できる
- カート内容はブラウザのタブ内のみ（sessionStorage）に保存。顧客名・住所・決済情報は入力・保存しない
- **注文手続きボタンは無効**。購入・決済・予約・在庫減算・通知・請求・サーバー通信は一切行わない
- 現段階の金額は「メーカー参考希望小売価格（税込）」であって、BIG PAWの販売価格ではない。送料・割引を含まない
- 一覧の空検索メッセージが常時出るHTML不具合を修正
- iPhone Safari/WebKit と Chromium でカート操作・金額・注文禁止・セッション保持を検証

## 2026-10-29 メーカー提供の詳細画像の取り込み（35商品／63画像）

- トランペッツ様の4ブランドのZIPを読み取り：ACANA 14商品/24画像、ORIJEN 8商品/12画像、ZIWI 9商品/18画像、CHARM 4商品/9画像。
- 63個の実ファイルを計163回、35商品ページに使う商品別の対応表を`app/shop-detail-images.js`へ実装。原資料`detail-images.json`の**並び順、キャプション、scope=specific/brand**を全35商品についてSHA-256短縮指紋で照合し、別のSKU・ブランドを誤って表示しないようにした。
- `app/shop-detail-gallery.js`：既存の商品詳細ページのパッケージ写真や商品名/容量/価格は保持し、その下に画像を順番に表示。iPhone向けに縦スクロール/タップ拡大/閉じる操作。画像は`loading=lazy`, `decoding=async`で遅延読み込み。
- ZIWIのエアドライ（Z01-Z06）とスチームドライ（Z07-Z09）を分離。チキンZ06用の画像は他のエアドライ商品に使わず、Z08/Z09の固有画像は提供されていないので創作せずブランド共通画像のみ表示。
- `scripts/import-shop-detail-assets.py`：受領した4 ZIP（または検証済みの統合ZIP）の35商品と63実ファイルをチェックして`--install`を指定したときに限り`app/assets/shop-details/`へ配置する。権限/価格/本番ファイルを変更しない。
- `scripts/test-shop-detail-images.cjs`、`scripts/test-shop-detail-importer.py`：35商品/63実ファイル/163参照、商品・ブランドの誤紐づけ、部分アップロード/不正ZIPを拒否。画像をGitHubに配置後はWebPファイル実体の形式をCIで確認。
- `scripts/test-shop-detail-gallery.cjs`：Chromium・iPhone Safari相当のWebKitで35商品ページの画像順序/表示と拡大・戻り操作を自動検証。**GitHubに画像がない間は無通信の代替画像でDOMを試験し、画像登録後は実WebPを読み込む**。
- 現状：ZIP内の本物の画像は63枚ともPillowで検査・デコードできた。以前から用意していた35パッケージ画像も含め、98枚を同梱した統合プレビューZIPを会話内で生成した。
- **画像バイナリ98枚のGitHub登録は未完了**。現在のGitHub接続はテキストコードの編集・テストができるが、ローカルZIPから画像を直接GitHubへ送る操作はできない。上記ZIPをファイル転送できる作業環境でブランチへ取り込んでから、実画像のHTTP/Safari最終確認が必要。
- 発売/決済が承認されたわけではない。**PR #175はDraft維持。mainマージ・Railway本番デプロイ・本番決済は禁止**。

## 2026-10-29 98画像統合ZIPの安全な取り込み

- 前回の35枚と新しい63枚をまとめた `bigpaw_shop_98_images_staging_ready_fixed.zip` を検証。全98 WebPのSHA-256チェックサム一致、画像デコード、35商品に対する詳細163参照を確認。
- 個別のWebPを手作業でひとつずつ対応させなくてもよいように、`scripts/install-shop-98-assets.py` を追加。
- 検証コマンド: `python3 scripts/install-shop-98-assets.py /path/to/bigpaw_shop_98_images_staging_ready_fixed.zip`
- 開発用作業コピーへの取り込み: 同じコマンドに `--install` を付加。実行前に35パッケージ/63詳細の一致を確認し、全ファイルを `app/assets/` 下の正しいフォルダへ配置するだけで、**勝手にpush・mainマージ・本番デプロイはしない**。
- CIで疑似98枚の正常取り込みと改ざん拒否を追加。実ファイルがブランチへ反映されれば、既存の35商品Chromium/WebKitテストは実際のWebPを読み込む。
- 画像確認プレビューの相対参照の誤りもローカルパック内で修正（`../app/assets/`）。
- **現時点のGitHubブランチには98枚のバイナリ本体は未登録。** GitHubコネクタはテキスト更新・バイナリBlob APIはできるが、今のコンテナ内ZIPのバイト列を直接渡す機能がなく、自動登録できない。正しい画像ZIP自体はチャットで引き渡し可能。
- **Draft PR #175を維持。本番mainとRailway、本番Square決済は変更しない。**

## 2026-10-29 画像98枚のGitHub登録完了（最新状態）

- **完了**：商品パッケージ画像35枚を `app/assets/shop-products/`、詳細画像63枚を `app/assets/shop-details/` に、ブランチ `feature/dogfood-shop-staging-20261028` で登録。
- イメージ登録コミット：`1d866c915ef534403b9c35ef23635ae0ee4d0be9`。
- GitHub git-tree APIで98ファイルの存在、35＋63分類、ZIPとのパス一致、余剰/欠落0を検証した。
- 転送は非公開の一時Google Driveフォルダを経由してGitHubのBlob APIへ行った。Square Secrets・価格表・本番環境の変更なし。
- 前節までにある「画像実体は未登録」という記録は作業当時の履歴であり、**この節の完了状況が最新**。
- 実画像を含むCI・Chromium/WebKitの結果はコミットのGitHub Actionsランを参照。iPhone物理端末での操作試験とは別。
- 本番公開禁止は継続（PR Draft・mainマージなし・Railway本番デプロイなし）。

## 2026-10-29 夜：注文確認画面の開発（実決済は未開始）

- `shop.html?order=review` を追加。既存のお試しカートの「注文内容を確認する（お試し）」から遷移する。
- `app/shop-order-review.js`, `app/shop-order-review.css` を追加。35商品からセッション内の購入商品を検証し、各商品の商品名・容量・点数・税込単価・小計・追加送料0円・合計額を表示。
- 商品金額は既存 `catalog` の `referenceMsrpExTax` を利用し、商品定義や価格表の改変/二重管理なし。最大10個/品、総額2,000,000円のSandbox上限を画面上でも確認。商品変更時は確認チェックを自動解除。
- 配送先氏名・住所・電話番号・クレジットカード番号はこの画面では**入力・保存・送信しない**。将来のSquare側の安全な決済画面で入力させる方針。画面の確認ボタンはUI試験用で、注文・課金は行わない。
- 静的公開ショップの既存購入ボタンは引き続きdisabled。注文確認で押せるボタンは「確認のみ」。本番注文API・本番Square Checkoutは未接続。
- `shop_payments/local_preview.py` の静的配信許可リストにレビュー用のJS/CSSと詳細WebPを追加し、隔離されたlocalhost Sandboxで表示可能にした。Checkout自体は従来の独立したSandboxプレビューに限定。
- `scripts/test-shop-order-review.cjs` でChromiumとWebKit（iPhone Safari相当）の画面遷移、カート更新、送料0円、2百万円超制限、空カート表示、無課金を検証。
- GitHub Actions Run `40873987120` 成功。既存35商品・98画像の表示・Square Sandbox mock checkout・回帰テストにも合格。物理iPhoneの実機チェックと実際のSandboxカード決済エンドツーエンド試験は別途必要。
- Draft PR #175を維持。mainマージ・Railway本番反映・Square本番決済開始は明示承認まで禁止。

## 2026-10-29 夜：注文確認→Square Sandbox決済の導線

- **実装済み（Sandboxのみ）**：既存 `shop.html?order=review` で商品・数量・送料0円・税込総額を確認し、確認チェック→「注文内容を確認する（テスト）」を押すと、隔離されたlocalhostプレビューでのみ `Squareのテスト決済へ進む` が有効になる。
- `shop_payments/review_sandbox_checkout.js` を新規追加し、`shop_payments/local_preview.py` が `?order=review` の時だけ `shop-sandbox-review.js` として注入。**公開用`app/shop.html`はSandboxスクリプトを一切読み込まない**。ユーザーの承認まで本番注文・本番Squareは使わない。
- Square SandboxへのPOSTは商品ID/数量/UUID試行IDだけ。顧客氏名・配送先・カード情報・ブラウザ側の金額は送らない。サーバーが税込価格と送料0円を再計算して金額を返し、確認画面の金額と一致しない限りSquareへのリダイレクトを禁止。
- テストリンクは `https://sandbox.square.link` のみ受け付け、注文ID・サーバー確認額・送料0円を照合。CSRF/Origin保護、同一試行IDのリトライは従来のSandbox注文DBの冪等性に依存。
- 数量変更・確認チェック解除・ページ遷移後は再確認が必要。復帰しただけで入金済み表示にせず、ステータス確認ボタンからサーバー照会を行い、Square Payments API検証済みの`paid`だけをテスト入金済みとして表示。
- `scripts/test-shop-review-square-browser.cjs` でChromium/WebKit両方の確認・Sandbox未設定・チェック無しで進めない・金額不一致の遮断・同一カートの再試行ID維持・ステータス待ち/完了をモックHTTPで検証。以前からあるカート/画像/35商品および既存Square Sandboxテストも回帰成功。
- **CI 成功**：GitHub Actions `40877380432`、テストは疑似Square応答。実際のSandboxカード決済、公開HTTPSホストでのWebhook受信、実機iPhone、事前在庫確保、認証された注文運営画面、通知、発送、返金、法定表示は別途未完成。
- Draft PR #175を保持。mainマージ・Railway本番デプロイ・Square本番決済は実施しない。
