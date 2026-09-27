#!/usr/bin/env bash
set -euo pipefail

BASE=http://127.0.0.1:18080
COOKIE='bigpaw_session=smoke-support-session'
ORIGIN='https://bigpaw.site'

# Create one operator session and tickets covering active, recent-completed,
# expired-completed, and manual-delete cases.
docker exec bigpaw-smoke python3 -c "import sqlite3,time; db='/tmp/bigpaw-data/bigpaw.sqlite3'; con=sqlite3.connect(db); t=int(time.time()); old=t-(181*86400); con.execute(\"INSERT OR REPLACE INTO users(id,role,email,last,first,display_name,salt,password_hash,created_at,email_verified,terms_accepted_at,privacy_accepted_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)\",('u_smoke_operator','operator','operator-smoke@example.invalid','試験','運営','試験 運営','x','x',t,1,t,t,t)); con.execute(\"INSERT OR REPLACE INTO sessions(token,user_id,created_at,expires_at) VALUES(?,?,?,?)\",('smoke-support-session','u_smoke_operator',t,t+3600)); tickets=[('sup_active',None,'利用者A','a@example.invalid','サイト利用について','未対応','本文A','open','',t,t),('sup_recent',None,'利用者B','b@example.invalid','サイト利用について','完了済み','本文B','resolved','',t,t),('sup_expired',None,'利用者C','c@example.invalid','サイト利用について','期限切れ','本文C','closed','',old,old),('sup_manual',None,'利用者D','d@example.invalid','サイト利用について','手動削除','本文D','closed','',t,t)]; con.executemany(\"INSERT OR REPLACE INTO support_tickets(id,user_id,name,email,category,subject,message,status,operator_note,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)\",tickets); con.execute(\"INSERT OR REPLACE INTO support_replies(id,ticket_id,operator_user_id,body,email_sent,created_at) VALUES(?,?,?,?,?,?)\",('sr_expired','sup_expired','u_smoke_operator','古い返信',1,old)); con.execute(\"INSERT OR REPLACE INTO support_replies(id,ticket_id,operator_user_id,body,email_sent,created_at) VALUES(?,?,?,?,?,?)\",('sr_manual','sup_manual','u_smoke_operator','削除対象の返信',1,t)); con.commit(); con.close()"

# Listing triggers the same retention purge used by the automation loop.
GET_CODE=$(curl -sS -o /tmp/support-list.json -w '%{http_code}' \
  -H 'Host: bigpaw.site' -H "Cookie: $COOKIE" \
  "$BASE/api/operator/support")
test "$GET_CODE" = "200"
python3 -c "import json; a=json.load(open('/tmp/support-list.json')); ids={x['id'] for x in a}; assert 'sup_active' in ids; assert 'sup_recent' in ids; assert 'sup_manual' in ids; assert 'sup_expired' not in ids; print('SUPPORT_RETENTION_LIST_OK|expired_removed=1|recent_completed_preserved=1|active_preserved=1')"

docker exec bigpaw-smoke python3 -c "import sqlite3; con=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); assert con.execute(\"SELECT COUNT(*) FROM support_tickets WHERE id='sup_expired'\").fetchone()[0]==0; assert con.execute(\"SELECT COUNT(*) FROM support_replies WHERE ticket_id='sup_expired'\").fetchone()[0]==0; con.close(); print('SUPPORT_RETENTION_DB_OK|expired_ticket_and_replies_deleted=1')"

# Active tickets cannot be manually deleted.
ACTIVE_DELETE_CODE=$(curl -sS -o /tmp/active-delete.json -w '%{http_code}' \
  -X DELETE -H 'Host: bigpaw.site' -H "Origin: $ORIGIN" -H 'Referer: https://bigpaw.site/operator-support.html' -H "Cookie: $COOKIE" \
  "$BASE/api/operator/support/sup_active")
test "$ACTIVE_DELETE_CODE" = "409"

# Completed tickets can be manually deleted, including their reply history.
MANUAL_DELETE_CODE=$(curl -sS -o /tmp/manual-delete.json -w '%{http_code}' \
  -X DELETE -H 'Host: bigpaw.site' -H "Origin: $ORIGIN" -H 'Referer: https://bigpaw.site/operator-support.html' -H "Cookie: $COOKIE" \
  "$BASE/api/operator/support/sup_manual")
test "$MANUAL_DELETE_CODE" = "200"
docker exec bigpaw-smoke python3 -c "import sqlite3; con=sqlite3.connect('/tmp/bigpaw-data/bigpaw.sqlite3'); assert con.execute(\"SELECT COUNT(*) FROM support_tickets WHERE id='sup_manual'\").fetchone()[0]==0; assert con.execute(\"SELECT COUNT(*) FROM support_replies WHERE ticket_id='sup_manual'\").fetchone()[0]==0; con.close(); print('SUPPORT_MANUAL_DELETE_OK|completed_only=1|reply_history_deleted=1')"

echo 'OPERATOR_SUPPORT_RETENTION_SMOKE_OK|retention_days=180|active_delete=blocked|completed_delete=allowed'
