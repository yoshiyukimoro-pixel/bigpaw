# BIG PAW メール設定状況

- 基本メールアドレス: `info@bigpaw.jp`
- 問い合わせ先: `info@bigpaw.jp`
- 自動送信元: `noreply@bigpaw.jp`
- 運営ログインID: `info@bigpaw.jp`
- 公開URL: `https://bigpaw.jp`

## 公開前に残っている作業

1. `bigpaw.jp` を実際に取得する。
2. ドメインのメール機能またはメール配信サービスで `info@bigpaw.jp` を作成し、`noreply@bigpaw.jp` は送信用エイリアス/アドレスとして用意する。
3. SMTPホスト、ポート、SMTPパスワードを非公開設定へ入力する。
4. SPF / DKIM / DMARC をメール提供元の案内に従ってDNSへ設定する。
5. 本番用の運営者パスワードは12文字以上の強い別パスワードを設定する。

※ `bigpaw0731` は12文字未満のため、本番設定では使用しない。
