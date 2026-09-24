BIG PAW v1.0
大型犬専門の子犬マッチングサービス。

実装済み
- SQLite永続保存
- 購入者 / ブリーダー / 運営の3権限
- 会員登録 / ログイン / メール確認 / パスワード再設定
- ブリーダー掲載申請 → 運営審査 → 権限付与
- ブリーダー申請時の成約手数料5%・7日払い条件への明示同意記録
- 子犬登録 → 掲載審査 → 承認後に一般公開
- 画像アップロード / 親犬 / 健康情報
- 検索 / 比較 / お気に入り
- 問い合わせ / メッセージ / 見学 / 商談
- ブリーダー成約申請 → 運営確認 → 成約確定
- 成約確定時に最終販売価格の5%（税込）を自動請求
- 請求日から7日以内の支払い
- 期限3日前・期限当日・期限超過の自動通知
- 期限超過時の犬舎・子犬公開自動停止
- 入金確認後の自動掲載再開
- 成約申請忘れの自動リマインド
- 請求書表示 / 印刷・PDF保存 / 運営入金確認
- 通報 / 監査ログ
- 運営問い合わせ窓口 / 対応ステータス管理
- 手動バックアップ / 復元 / 24時間ごとの自動バックアップ
- 公開ページ用 robots.txt / sitemap.xml 自動生成
- 本番設定自動診断 / 自動処理モニター
- Docker起動 / smoke test

ローカル起動
1. `python3 backend/server.py`
2. http://127.0.0.1:8080/

開発モードのテスト用アカウント
購入希望者: demo@bigpaw.jp / demo1234
ブリーダー: dog44@bigpaw.jp / demo1234
運営: admin@bigpaw.jp / admin1234
※ production モードでは上記デモアカウントは作成されません。

Docker
`docker compose up --build`

料金設定
- BIGPAW_COMMISSION_RATE_BPS=500
- BIGPAW_COMMISSION_DUE_DAYS=7
- BIGPAW_COMMISSION_TERMS_VERSION=2026-09-16-v1

自動処理
- BIGPAW_AUTOMATION_INTERVAL_SECONDS=300
- BIGPAW_AUTO_BACKUP_HOURS=24
- BIGPAW_AUTO_BACKUP_KEEP=14

本番公開に必要な実情報
独自ドメイン/HTTPS、SMTP、運営者情報、振込口座、必要に応じた予約金決済・電子契約・外部画像保存を設定してください。
詳細は DEPLOYMENT.md / SECURITY.md / RELEASE_CHECKLIST.md を参照してください。

運用手順: OPERATIONS.md
最終QA: QA_REPORT.md

公開準備: DOMAIN_EMAIL_SETUP.md / RAILWAY_DEPLOYMENT.md
