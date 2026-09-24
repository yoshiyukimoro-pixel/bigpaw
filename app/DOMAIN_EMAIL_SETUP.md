# BIG PAW — ドメイン・メール設定手順

更新日: 2026-09-16

## 決定済み
- 公開ドメイン候補: `bigpaw.jp`
- 公開URL: `https://bigpaw.jp`
- 問い合わせ/運営ログイン: `info@bigpaw.jp`
- 自動送信: `noreply@bigpaw.jp`
- ドメイン取得までの暫定連絡先: 現在使用中のGmail

## 1. bigpaw.jp を登録
JPドメインはJPRSへ直接申し込むのではなく、JPRS指定事業者を通して登録します。
候補としてXServerドメインを利用すると、日本語画面で `.jp` の登録ができます。

登録画面で `bigpaw.jp` を検索し、「取得可能」と表示された場合のみそのまま登録してください。
すでに登録済みの場合は購入せず、別候補を決めます。

※検索エンジン上で使用例が見つからないことと、ドメインが登録可能であることは同じではありません。必ず登録事業者のリアルタイム検索で確認します。

## 2. メールはGoogle Workspaceを第一候補にする
既存のGmail操作に近く、独自ドメインのメールを扱いやすいため、最初はGoogle Workspace Starterを想定します。

作るもの:
- メインユーザー: `info@bigpaw.jp`
- 送信用エイリアス/アドレス: `noreply@bigpaw.jp`

`info@bigpaw.jp` は問い合わせ受信と運営ログインに使用します。
`noreply@bigpaw.jp` は会員登録確認、パスワード再設定、成約、請求通知などの自動送信専用です。

## 3. DNS設定
メール提供元の案内どおり、ドメインDNSへMX、SPF、DKIM、DMARCを設定します。
サイト公開時には `bigpaw.jp` / `www.bigpaw.jp` をアプリのホスティング先へ向けます。

## 4. BIG PAWへ接続
本番環境変数にSMTP情報を設定します。

```text
BIGPAW_SMTP_HOST=<メール提供元のSMTPホスト>
BIGPAW_SMTP_PORT=587
BIGPAW_SMTP_USER=noreply@bigpaw.jp
BIGPAW_SMTP_PASSWORD=<非公開>
BIGPAW_SMTP_FROM=noreply@bigpaw.jp
BIGPAW_SMTP_TLS=1
```

## セキュリティ
- ドメイン管理アカウントは2段階認証を有効化する。
- 本番パスワードはチャットや公開ファイルへ書かない。
- 非公開設定ファイルをWeb公開フォルダへ置かない。
