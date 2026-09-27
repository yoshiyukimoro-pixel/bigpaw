#!/usr/bin/env bash
set -euo pipefail

docker exec bigpaw-smoke python3 -c "import sqlite3,time; db='/tmp/bigpaw-data/bigpaw.sqlite3'; con=sqlite3.connect(db); t=int(time.time()); con.execute(\"INSERT OR REPLACE INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at,email_verified,terms_accepted_at,privacy_accepted_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)\",('u_smoke_breeder','breeder','breeder-smoke@example.invalid','試験','ブリーダー','試験 ブリーダー','x','x',t,1,t,t,t)); con.execute(\"INSERT OR REPLACE INTO breeders(id,user_id,kennel_name,prefecture,review_status,billing_suspended) VALUES(?,?,?,?,?,?)\",('b_smoke','u_smoke_breeder','Smoke Kennel','埼玉県','approved',0)); con.execute(\"INSERT OR REPLACE INTO sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)\",('smoke-sales-session','u_smoke_breeder',t,t+3600)); con.commit(); con.close()"

SAVE_CODE=$(curl -sS -o /tmp/save.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' \
  -H 'Origin: https://bigpaw.site' \
  -H 'Referer: https://bigpaw.site/breeder-sales-handover.html' \
  -H 'Cookie: bigpaw_session=smoke-sales-session' \
  -H 'Content-Type: application/json' \
  --data '{"pedigreeOrganizations":["JKC"],"vaccineIncluded":false,"vaccineNote":"1回目6種混合ワクチン\n2回目7種混合ワクチン\nワクチン接種代として別途10,000円","reservationAmount":100000,"balanceTiming":"お引き渡し当日まで","reservationNote":"ご予約は100,000円を予約金としてお支払いいただきます。予約金のお支払い確認後、他のお客様からのお問い合わせ受付を停止し、商談中とさせていただきます。残金につきましては、お引き渡し当日までにお支払いください。お客様都合によるキャンセルの場合、予約金は返金いたしかねます。","sameDayVisit":false,"handoverText":"健康診断後にお引き渡し","minHandoverDays":57,"healthExamIncluded":true,"microchipIncluded":false,"cancellationPolicy":"お客様都合によるキャンセルの場合、予約金は返金いたしかねます。"}' \
  http://127.0.0.1:18080/api/breeder/sales-handover-settings)

test "$SAVE_CODE" = "200"

GET_CODE=$(curl -sS -o /tmp/saved.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' \
  -H 'Cookie: bigpaw_session=smoke-sales-session' \
  http://127.0.0.1:18080/api/breeder/sales-handover-settings)

test "$GET_CODE" = "200"
python3 -c "import json; x=json.load(open('/tmp/saved.json')); assert x['configured'] is True; assert x['reservationAmount']==100000; assert x['minHandoverDays']==57; assert x['balanceTiming']=='お引き渡し当日まで'; assert '残金につきましては' in x['reservationNote']; assert 'キャンセルの場合' in x['reservationNote']; assert x['vaccineIncluded'] is False; assert x['vaccineNote']=='1回目6種混合ワクチン\n2回目7種混合ワクチン\nワクチン接種代として別途10,000円'; assert x['healthExamIncluded'] is True; assert x['microchipIncluded'] is True; print('SALES_HANDOVER_SAVE_SMOKE_OK|post=200|get=200|persistence=verified|microchip_forced_included=1|reservation_source_preserved=1')"

docker exec bigpaw-smoke grep -Fq '生体価格には含まれません' /app/assets/puppy-sales-handover-public.js
docker exec bigpaw-smoke grep -Fq 'ワクチン代：別途 $1円' /app/assets/puppy-sales-handover-public.js
if docker exec bigpaw-smoke grep -Fq '生体価格とは別途必要です' /app/assets/puppy-sales-handover-public.js; then
  echo 'VACCINE_PUBLIC_COPY_FAIL|old_copy_still_present'
  exit 1
fi
echo 'VACCINE_PUBLIC_COPY_SMOKE_OK|not_included=clear|fee_line=normalized|saved_note=preserved'

docker exec bigpaw-smoke grep -Fq "row('残金のお支払い',balanceTiming,balanceDetail)" /app/assets/puppy-sales-handover-public.js
docker exec bigpaw-smoke grep -Fq '生体代金から予約金を差し引いた残金は、' /app/assets/puppy-sales-handover-public.js
docker exec bigpaw-smoke grep -Fq "!/(残金|キャンセル|返金)/.test(x)" /app/assets/puppy-sales-handover-public.js
docker exec bigpaw-smoke grep -Fq "row('残金のお支払い',balanceTiming,balanceDetail)" /app/assets/sales-handover-public.js
echo 'RESERVATION_BALANCE_PUBLIC_SMOKE_OK|reservation=reservation_only|balance=separate_row|cancel_duplicate_filtered|saved_source=preserved'

docker exec bigpaw-smoke grep -Fq 'id="bigpaw-breeder-handover-blue-theme"' /app/breeder-sales-handover.html
docker exec bigpaw-smoke grep -Fq 'background:#f3f8ff!important' /app/breeder-sales-handover.html
docker exec bigpaw-smoke grep -Fq "'/breeder-sales-handover.html'" /app/mobile-global-nav.js
docker exec bigpaw-smoke grep -Fq "fetch('/api/breeder/sales-handover-settings'" /app/breeder-sales-handover.html
echo 'BREEDER_HANDOVER_BLUE_THEME_SMOKE_OK|page=blue|mobile_menu=breeder_blue|save_logic=preserved'
