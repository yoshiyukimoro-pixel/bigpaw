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

# Direct breeder signup: the breeder page itself creates the login account,
# verifies email, submits the breeder application, and approval promotes the same account.
docker exec bigpaw-smoke grep -Fq 'DIRECT_BREEDER_SIGNUP_FLOW_V1' /app/backend/server.py
docker exec bigpaw-smoke grep -Fq "verify_flow='&flow=breeder' if account_type=='breeder' else ''" /app/backend/server.py
docker exec bigpaw-smoke grep -Fq "accountType:'breeder'" /app/breeder-register.html
docker exec bigpaw-smoke grep -Fq '一般会員登録を先に行う必要はありません' /app/breeder-register.html
docker exec bigpaw-smoke grep -Fq 'breeder-register.html?continue=1' /app/verify-email.html
if docker exec bigpaw-smoke grep -Fq '申請には購入希望者アカウントでのログインが必要です' /app/breeder-register.html; then
  echo 'DIRECT_BREEDER_SIGNUP_UI_FAIL|legacy_general_signup_instruction_present'
  exit 1
fi

DIRECT_EMAIL='direct-breeder-smoke@example.invalid'
DIRECT_PASSWORD='DirectBreeder123!'
REGISTER_CODE=$(curl -sS -o /tmp/direct-register.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' -H 'Origin: https://bigpaw.site' -H 'Content-Type: application/json' \
  --data "{\"last\":\"直登録\",\"first\":\"試験\",\"email\":\"$DIRECT_EMAIL\",\"password\":\"$DIRECT_PASSWORD\",\"agreeTerms\":true,\"agreePrivacy\":true,\"accountType\":\"breeder\"}" \
  http://127.0.0.1:18080/api/register)
test "$REGISTER_CODE" = "201"

LOGIN_CODE=$(curl -sS -o /tmp/direct-login.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' -H 'Origin: https://bigpaw.site' -H 'Content-Type: application/json' \
  --data "{\"email\":\"$DIRECT_EMAIL\",\"password\":\"$DIRECT_PASSWORD\"}" \
  http://127.0.0.1:18080/api/login)
test "$LOGIN_CODE" = "200"

DIRECT_UID=$(docker exec bigpaw-smoke python3 -c "import sqlite3; c=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); print(c.execute('SELECT id FROM users WHERE email=?',('$DIRECT_EMAIL',)).fetchone()[0])")
DIRECT_SESSION=$(docker exec bigpaw-smoke python3 -c "import sqlite3; c=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); print(c.execute('SELECT token FROM sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 1',('$DIRECT_UID',)).fetchone()[0])")
VERIFY_TOKEN=$(docker exec bigpaw-smoke python3 -c "import sqlite3; c=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); print(c.execute('SELECT token FROM email_verification_tokens WHERE user_id=? AND used_at IS NULL ORDER BY created_at DESC LIMIT 1',('$DIRECT_UID',)).fetchone()[0])")
DIRECT_COOKIE="bigpaw_session=$DIRECT_SESSION"

VERIFY_CODE=$(curl -sS -o /tmp/direct-verify.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' -H 'Origin: https://bigpaw.site' -H 'Cookie: '"$DIRECT_COOKIE" -H 'Content-Type: application/json' \
  --data "{\"token\":\"$VERIFY_TOKEN\"}" \
  http://127.0.0.1:18080/api/email-verification/confirm)
test "$VERIFY_CODE" = "200"

ME_CODE=$(curl -sS -o /tmp/direct-me.json -w '%{http_code}' -H 'Host: bigpaw.site' -H 'Cookie: '"$DIRECT_COOKIE" http://127.0.0.1:18080/api/me)
test "$ME_CODE" = "200"
python3 -c "import json; x=json.load(open('/tmp/direct-me.json')); assert x['role']=='buyer'; assert x.get('emailVerified') is True; print('DIRECT_BREEDER_ACCOUNT_OK|created_without_general_ui=1|preapproval_role=buyer|email_verified=1')"

python3 - <<'PY'
import struct,zlib,binascii

def chunk(kind,data):
    return struct.pack('>I',len(data))+kind+data+struct.pack('>I',binascii.crc32(kind+data)&0xffffffff)
png=b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',1,1,8,2,0,0,0))+chunk(b'IDAT',zlib.compress(b'\x00\xff\xff\xff'))+chunk(b'IEND',b'')
open('/tmp/direct-proof.png','wb').write(png)
PY

UPLOAD_CODE=$(curl -sS -o /tmp/direct-upload.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' -H 'Origin: https://bigpaw.site' -H 'Cookie: '"$DIRECT_COOKIE" \
  -F 'file=@/tmp/direct-proof.png;type=image/png' -F 'puppyId=breeder-proof' \
  http://127.0.0.1:18080/api/uploads)
test "$UPLOAD_CODE" = "201"
PROOF_URL=$(python3 -c "import json; print(json.load(open('/tmp/direct-upload.json'))['url'])")

APPLY_CODE=$(curl -sS -o /tmp/direct-apply.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' -H 'Origin: https://bigpaw.site' -H 'Cookie: '"$DIRECT_COOKIE" -H 'Content-Type: application/json' \
  --data "{\"kennelName\":\"Direct Smoke Kennel\",\"representative\":\"直登録 試験\",\"prefecture\":\"埼玉県\",\"primaryBreed\":\"スタンダードプードル\",\"registrationNo\":\"SMOKE-12345\",\"expiresOn\":\"2030-12-31\",\"profile\":\"大型犬を家庭内で育てています。\",\"registrationProofUrl\":\"$PROOF_URL\",\"visitAddress\":\"埼玉県テスト市1-2-3\",\"visitPhone\":\"09000000000\",\"visitAccess\":\"駐車場あり\",\"agreeCommissionTerms\":true}" \
  http://127.0.0.1:18080/api/breeder-applications)
test "$APPLY_CODE" = "201"
APP_ID=$(python3 -c "import json; print(json.load(open('/tmp/direct-apply.json'))['id'])")

APP_GET_CODE=$(curl -sS -o /tmp/direct-apps.json -w '%{http_code}' -H 'Host: bigpaw.site' -H 'Cookie: '"$DIRECT_COOKIE" http://127.0.0.1:18080/api/breeder-applications)
test "$APP_GET_CODE" = "200"
python3 -c "import json; x=json.load(open('/tmp/direct-apps.json')); assert x and x[0]['status']=='pending'; assert x[0]['kennel_name']=='Direct Smoke Kennel'; print('DIRECT_BREEDER_APPLICATION_OK|proof_uploaded=1|application=pending|operator_review_required=1')"

OP_LOGIN_CODE=$(curl -sS -o /tmp/direct-op-login.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' -H 'Origin: https://bigpaw.site' -H 'Content-Type: application/json' \
  --data '{"email":"smoke@example.com","password":"SmokeTestPassword123!"}' \
  http://127.0.0.1:18080/api/login)
test "$OP_LOGIN_CODE" = "200"
OP_UID=$(docker exec bigpaw-smoke python3 -c "import sqlite3; c=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); print(c.execute(\"SELECT id FROM users WHERE email='smoke@example.com'\").fetchone()[0])")
OP_SESSION=$(docker exec bigpaw-smoke python3 -c "import sqlite3; c=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); print(c.execute('SELECT token FROM sessions WHERE user_id=? ORDER BY created_at DESC LIMIT 1',('$OP_UID',)).fetchone()[0])")
OP_COOKIE="bigpaw_session=$OP_SESSION"

APPROVE_CODE=$(curl -sS -o /tmp/direct-approve.json -w '%{http_code}' -X PATCH \
  -H 'Host: bigpaw.site' -H 'Origin: https://bigpaw.site' -H 'Cookie: '"$OP_COOKIE" -H 'Content-Type: application/json' \
  --data '{"status":"approved","reviewNote":"smoke approved"}' \
  http://127.0.0.1:18080/api/breeder-applications/$APP_ID)
test "$APPROVE_CODE" = "200"

curl -sS -o /tmp/direct-me-approved.json -H 'Host: bigpaw.site' -H 'Cookie: '"$DIRECT_COOKIE" http://127.0.0.1:18080/api/me
python3 -c "import json; x=json.load(open('/tmp/direct-me-approved.json')); assert x['role']=='breeder'; print('DIRECT_BREEDER_APPROVAL_OK|same_account_promoted=1|role=breeder')"
docker exec bigpaw-smoke python3 -c "import sqlite3; c=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); n=c.execute('SELECT COUNT(*) FROM breeders WHERE user_id=?',('$DIRECT_UID',)).fetchone()[0]; assert n==1; print('DIRECT_BREEDER_PROFILE_OK|created_on_approval=1')"

GENERAL_EMAIL='general-register-smoke@example.invalid'
GENERAL_CODE=$(curl -sS -o /tmp/general-register.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' -H 'Origin: https://bigpaw.site' -H 'Content-Type: application/json' \
  --data "{\"last\":\"一般\",\"first\":\"試験\",\"email\":\"$GENERAL_EMAIL\",\"password\":\"GeneralBuyer123!\",\"agreeTerms\":true,\"agreePrivacy\":true}" \
  http://127.0.0.1:18080/api/register)
test "$GENERAL_CODE" = "201"
docker exec bigpaw-smoke python3 -c "import sqlite3; c=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); r=c.execute('SELECT role FROM users WHERE email=?',('$GENERAL_EMAIL',)).fetchone(); assert r and r[0]=='buyer'; print('GENERAL_REGISTRATION_REGRESSION_OK|role=buyer|flow_unchanged=1')"

echo 'DIRECT_BREEDER_SIGNUP_SMOKE_OK|direct_account=1|email_verify=1|proof=1|application=1|operator_approval=1|general_signup_preserved=1'
