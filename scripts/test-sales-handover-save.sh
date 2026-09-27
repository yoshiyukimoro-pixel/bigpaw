#!/usr/bin/env bash
set -euo pipefail

docker exec bigpaw-smoke python3 -c "import sqlite3,time; db='/tmp/bigpaw-data/bigpaw.sqlite3'; con=sqlite3.connect(db); t=int(time.time()); con.execute(\"INSERT OR REPLACE INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at,email_verified,terms_accepted_at,privacy_accepted_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)\",('u_smoke_breeder','breeder','breeder-smoke@example.invalid','試験','ブリーダー','試験 ブリーダー','x','x',t,1,t,t,t)); con.execute(\"INSERT OR REPLACE INTO breeders(id,user_id,kennel_name,prefecture,review_status,billing_suspended) VALUES(?,?,?,?,?,?)\",('b_smoke','u_smoke_breeder','Smoke Kennel','埼玉県','approved',0)); con.execute(\"INSERT OR REPLACE INTO sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)\",('smoke-sales-session','u_smoke_breeder',t,t+3600)); con.commit(); con.close()"

SAVE_CODE=$(curl -sS -o /tmp/save.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' \
  -H 'Origin: https://bigpaw.site' \
  -H 'Referer: https://bigpaw.site/breeder-sales-handover.html' \
  -H 'Cookie: bigpaw_session=smoke-sales-session' \
  -H 'Content-Type: application/json' \
  --data '{"pedigreeOrganizations":["JKC"],"vaccineIncluded":false,"reservationAmount":100000,"balanceTiming":"お引き渡し当日まで","sameDayVisit":false,"handoverText":"健康診断後にお引き渡し","minHandoverDays":57,"healthExamIncluded":true,"microchipIncluded":false,"cancellationPolicy":"予約条件に基づき対応"}' \
  http://127.0.0.1:18080/api/breeder/sales-handover-settings)

test "$SAVE_CODE" = "200"

GET_CODE=$(curl -sS -o /tmp/saved.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' \
  -H 'Cookie: bigpaw_session=smoke-sales-session' \
  http://127.0.0.1:18080/api/breeder/sales-handover-settings)

test "$GET_CODE" = "200"
python3 -c "import json; x=json.load(open('/tmp/saved.json')); assert x['configured'] is True; assert x['reservationAmount']==100000; assert x['minHandoverDays']==57; assert x['balanceTiming']=='お引き渡し当日まで'; assert x['vaccineIncluded'] is False; assert x['healthExamIncluded'] is True; assert x['microchipIncluded'] is True; print('SALES_HANDOVER_SAVE_SMOKE_OK|post=200|get=200|persistence=verified|microchip_forced_included=1')"
