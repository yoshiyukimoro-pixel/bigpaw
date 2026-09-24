#!/usr/bin/env python3
from pathlib import Path
import os, sqlite3, sys

DATA_DIR = Path(os.environ.get('BIGPAW_DATA_DIR','/data')).resolve()
DB = DATA_DIR / 'bigpaw.sqlite3'
UPLOADS = DATA_DIR / 'uploads'

if not DB.exists():
    print('ORPHAN_TEST_CLEANUP_ABORT|database_missing', flush=True)
    sys.exit(2)

con = sqlite3.connect(DB)
con.row_factory = sqlite3.Row
con.execute('PRAGMA foreign_keys=ON')
rows = con.execute("SELECT id,name FROM puppies WHERE breeder_id IS NULL AND review_status='pending' ORDER BY created_at").fetchall()
ids = [r['id'] for r in rows]
print('ORPHAN_TEST_CLEANUP_FOUND|' + str(len(ids)), flush=True)

if not ids:
    real = con.execute("SELECT COUNT(*) AS n FROM puppies WHERE breeder_id IS NOT NULL AND review_status='approved'").fetchone()['n']
    print('ORPHAN_TEST_CLEANUP_DONE|deleted=0|remaining=0|approved_breeder_puppies=' + str(real), flush=True)
    con.close()
    sys.exit(0)

marks = ','.join('?' for _ in ids)
blockers = {}
for table in ('inquiries','deals','reports'):
    blockers[table] = con.execute(f"SELECT COUNT(*) AS n FROM {table} WHERE puppy_id IN ({marks})", ids).fetchone()['n']
if any(blockers.values()):
    print('ORPHAN_TEST_CLEANUP_ABORT|transaction_refs|' + '|'.join(f'{k}={v}' for k,v in blockers.items()), flush=True)
    con.close()
    sys.exit(3)

upload_rows = con.execute(f"SELECT stored_name FROM uploads WHERE puppy_id IN ({marks})", ids).fetchall()
health_n = con.execute(f"SELECT COUNT(*) AS n FROM health_records WHERE puppy_id IN ({marks})", ids).fetchone()['n']
fav_n = con.execute(f"SELECT COUNT(*) AS n FROM favorites WHERE puppy_id IN ({marks})", ids).fetchone()['n']
upload_n = len(upload_rows)

con.execute('BEGIN')
con.execute(f"DELETE FROM health_records WHERE puppy_id IN ({marks})", ids)
con.execute(f"DELETE FROM favorites WHERE puppy_id IN ({marks})", ids)
con.execute(f"DELETE FROM uploads WHERE puppy_id IN ({marks})", ids)
cur = con.execute(f"DELETE FROM puppies WHERE id IN ({marks}) AND breeder_id IS NULL AND review_status='pending'", ids)
deleted = cur.rowcount
con.commit()

for r in upload_rows:
    try:
        (UPLOADS / r['stored_name']).unlink(missing_ok=True)
    except Exception as exc:
        print('ORPHAN_TEST_CLEANUP_UPLOAD_WARN|' + type(exc).__name__, flush=True)

remaining = con.execute("SELECT COUNT(*) AS n FROM puppies WHERE breeder_id IS NULL AND review_status='pending'").fetchone()['n']
real = con.execute("SELECT COUNT(*) AS n FROM puppies WHERE breeder_id IS NOT NULL AND review_status='approved'").fetchone()['n']
print(f'ORPHAN_TEST_CLEANUP_DONE|deleted={deleted}|remaining={remaining}|health={health_n}|favorites={fav_n}|uploads={upload_n}|approved_breeder_puppies={real}', flush=True)
con.close()
if remaining != 0 or deleted != len(ids):
    sys.exit(4)
