# BIG PAW — Railway公開手順

更新日: 2026-09-16

BIG PAW v1.0はDockerfileで起動できるため、初期公開先としてRailwayを使える構成にしてあります。
SQLite、アップロード画像、バックアップは永続ボリューム `/data` にまとめます。

## Railway側で行うこと
1. 新しいProject / Serviceを作成し、このBIG PAWコードをデプロイする。
2. ServiceにVolumeを追加して `/data` にマウントする。
3. Healthcheck Pathを `/api/health` にする。
4. `BIGPAW_DATA_DIR=/data` を設定する。
5. `BIGPAW_ENV=production` とその他の本番環境変数を設定する。
6. Railway上で仮URLが正常動作することを確認する。
7. Custom Domainに `bigpaw.jp` を追加し、表示されたDNSレコードをドメイン側へ設定する。
8. `www.bigpaw.jp` も必要なら追加し、正規URLへ転送する。

## 必須の主な環境変数
```text
BIGPAW_ENV=production
BIGPAW_PUBLIC_BASE_URL=https://bigpaw.jp
BIGPAW_DATA_DIR=/data
BIGPAW_DEV_LINKS=0
BIGPAW_ADMIN_EMAIL=info@bigpaw.jp
BIGPAW_ADMIN_PASSWORD=<12文字以上の強い非公開パスワード>
BIGPAW_PAYMENT_MODE=manual
BIGPAW_COMMISSION_RATE_BPS=500
BIGPAW_COMMISSION_DUE_DAYS=7
```

メール設定・請求口座などは公開コードではなくRailway Variablesへ登録してください。

## 注意
- `.env` や非公開設定ファイルはGitHub/公開ZIPへ含めない。
- VolumeなしでSQLiteを運用すると再デプロイ時にデータが消える可能性があるため、本番では必ず永続ボリュームを使う。
- 本番公開前に `backend-status.html` の公開準備診断を確認する。
