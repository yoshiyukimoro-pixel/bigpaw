# BIG PAW データベース設計 v0.1

このフォルダは、HTMLだけの試作品を本番サービスへ移行するためのデータ構造案です。

中心となる流れは以下です。

users → breeders → dogs → inquiries → messages → visits → deals → payments / contracts → pickups → reviews

重要ポイント:
- 購入希望者・ブリーダー・運営者を role で分ける
- 見学（visits）と対面確認を成約フロー上で記録する
- 予約金・残金・返金を payments で分離して記録する
- 契約書は contracts に版番号と署名時刻を保存する
- お迎え完了後の成約済み取引だけ口コミ投稿できる仕様を想定する
- 犬の健康情報は犬種ごとに項目が違うため dog_health_records で柔軟に持つ

次段階では、認証、画像保存、決済API、メール/SMS通知、監査ログを追加します。
