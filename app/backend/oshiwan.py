"""BIG PAW 推しワン: breeder-owned promotion, breed grouping and fair rotation."""
from collections import defaultdict
from urllib.parse import urlparse
import sqlite3
import time

SCHEMA = """
CREATE TABLE IF NOT EXISTS oshiwan_entries(
 puppy_id TEXT PRIMARY KEY REFERENCES puppies(id) ON DELETE CASCADE,
 breeder_id TEXT NOT NULL REFERENCES breeders(id),
 enabled_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS oshiwan_periods(
 id INTEGER PRIMARY KEY AUTOINCREMENT,
 puppy_id TEXT NOT NULL,
 breeder_id TEXT NOT NULL,
 started_at INTEGER NOT NULL,
 ended_at INTEGER
);
CREATE INDEX IF NOT EXISTS idx_oshiwan_periods_puppy ON oshiwan_periods(puppy_id,started_at,ended_at);
CREATE TABLE IF NOT EXISTS oshiwan_rotation(
 breed TEXT PRIMARY KEY,
 turn INTEGER NOT NULL DEFAULT 0
);
CREATE TRIGGER IF NOT EXISTS oshiwan_auto_cleanup
AFTER UPDATE OF breed,breeder_id,status,review_status ON puppies
WHEN OLD.breed<>NEW.breed OR OLD.breeder_id IS NOT NEW.breeder_id
 OR NEW.status<>'募集中' OR NEW.review_status<>'approved'
BEGIN
 UPDATE oshiwan_periods SET ended_at=CAST(strftime('%s','now') AS INTEGER)
 WHERE puppy_id=NEW.id AND ended_at IS NULL;
 DELETE FROM oshiwan_entries WHERE puppy_id=NEW.id;
END;
"""

def rotate_breed(rows, turn):
    """Give each kennel its turn before repeating it, then rotate fairly by page view."""
    buckets = defaultdict(list)
    for r in rows:
        buckets[r['breeder_id']].append(r)
    ordered = []
    keys = sorted(buckets)
    while any(buckets.values()):
        for key in keys:
            if buckets[key]:
                ordered.append(buckets[key].pop(0))
    if len(ordered) <= 5:
        return ordered
    start = (turn * 5) % len(ordered)
    return [ordered[(start + n) % len(ordered)] for n in range(5)]

def install(g):
    original_init = g['init_db']
    old_get = g['Handler'].do_GET
    old_post = g['Handler'].do_POST
    now = g['now']
    db = g['db']
    audit = g['audit']
    def new_init():
        original_init()
        c = db()
        try:
            c.executescript(SCHEMA)
            c.commit()
        finally:
            c.close()
    g['init_db'] = new_init

    def new_get(self):
        path = urlparse(self.path).path
        if path == '/api/oshiwan':
            c = db()
            try:
                c.execute('BEGIN IMMEDIATE')
                rows = c.execute("""
                  SELECT p.* FROM oshiwan_entries e
                  JOIN puppies p ON p.id=e.puppy_id
                  JOIN breeders b ON b.id=p.breeder_id
                  WHERE p.status='募集中' AND p.review_status='approved'
                    AND b.review_status='approved'
                    AND COALESCE(b.billing_suspended,0)=0
                    AND COALESCE(b.compliance_suspended,0)=0
                  ORDER BY e.enabled_at, p.id
                """).fetchall()
                grouped = defaultdict(list)
                for row in rows:
                    grouped[row['breed']].append(row)
                out = []
                for breed in sorted(grouped):
                    current = c.execute('SELECT turn FROM oshiwan_rotation WHERE breed=?', (breed,)).fetchone()
                    turn = current['turn'] if current else 0
                    selected = rotate_breed(grouped[breed], turn)
                    c.execute("""INSERT INTO oshiwan_rotation(breed,turn) VALUES(?,1)
                                 ON CONFLICT(breed) DO UPDATE SET turn=turn+1""", (breed,))
                    out.append({
                        'breed': breed,
                        'puppies': [g['public_puppy_json'](row) for row in selected],
                        'totalEligible': len(grouped[breed])
                    })
                c.commit()
                return self.send_json({'groups': out, 'label': '推しワン', 'advertisement': True})
            except Exception:
                c.rollback()
                raise
            finally:
                c.close()
        prefix = '/api/oshiwan/'
        if path.startswith(prefix) and path.endswith('/state'):
            pid = path[len(prefix):-len('/state')].strip('/')
            u = self.require(['breeder', 'operator'])
            if not u: return
            c = db()
            try:
                p = c.execute('SELECT * FROM puppies WHERE id=?', (pid,)).fetchone()
                if not p: return self.send_json({'error': 'not_found'}, 404)
                if u['role'] == 'breeder':
                    b = c.execute('SELECT id FROM breeders WHERE user_id=?', (u['id'],)).fetchone()
                    if not b or b['id'] != p['breeder_id']:
                        return self.send_json({'error': 'forbidden'}, 403)
                selected = c.execute('SELECT 1 FROM oshiwan_entries WHERE puppy_id=?', (pid,)).fetchone()
                count = c.execute("""SELECT count(*) AS n FROM oshiwan_entries e
                    JOIN puppies p ON p.id=e.puppy_id
                    WHERE p.breeder_id=? AND p.breed=? AND p.status='募集中'""",
                    (p['breeder_id'], p['breed'])).fetchone()['n']
                return self.send_json({'enabled': bool(selected), 'breed': p['breed'],
                     'eligible': p['status']=='募集中' and p['review_status']=='approved',
                     'kennelBreedCount': count, 'kennelBreedLimit': 2,
                     'feeRateBps': 300, 'firstSaleFreeForStandardOnly': True})
            finally:
                c.close()
        return old_get(self)

    def new_post(self):
        path = urlparse(self.path).path
        prefix = '/api/oshiwan/'
        if not (path.startswith(prefix) and path.endswith('/selection')):
            return old_post(self)
        if not self.mutation_origin_allowed():
            return self.send_json({'error': 'invalid_origin'}, 403)
        pid = path[len(prefix):-len('/selection')].strip('/')
        u = self.require(['breeder', 'operator'])
        if not u: return
        body = self.json_body()
        if type(body.get('enabled')) is not bool:
            return self.send_json({'error': 'enabled_boolean_required'}, 400)
        enabled = body['enabled']
        if enabled and body.get('agreeOshiwanTerms') is not True:
            return self.send_json({'error': 'oshiwan_fee_consent_required',
              'message': '推しワン経由の成約は通常5％に推しワン利用料3％を加算して合計8％です。先着100頭キャンペーン対象の場合は通常の5％のみ免除され、推しワン利用料3％は必要です。キャンペーン対象外は初回でも合計8％です。'}, 400)
        c = db()
        try:
            c.execute('BEGIN IMMEDIATE')
            p = c.execute('SELECT * FROM puppies WHERE id=?', (pid,)).fetchone()
            if not p: return self.send_json({'error': 'not_found'}, 404)
            if u['role'] == 'breeder':
                b = c.execute('SELECT id FROM breeders WHERE user_id=?', (u['id'],)).fetchone()
                if not b or b['id'] != p['breeder_id']:
                    return self.send_json({'error': 'forbidden'}, 403)
            if not p['breeder_id']: return self.send_json({'error': 'breeder_required'}, 409)
            current = c.execute('SELECT 1 FROM oshiwan_entries WHERE puppy_id=?', (pid,)).fetchone()
            if enabled and not current:
                b = c.execute('SELECT review_status,billing_suspended,compliance_suspended FROM breeders WHERE id=?', (p['breeder_id'],)).fetchone()
                if p['status'] != '募集中' or p['review_status'] != 'approved' or not b or b['review_status'] != 'approved' or b['billing_suspended'] or b['compliance_suspended']:
                    return self.send_json({'error': 'listing_not_eligible'}, 409)
                active_count = c.execute("""SELECT COUNT(*) AS n FROM oshiwan_entries e
                    JOIN puppies pp ON pp.id=e.puppy_id
                    WHERE pp.breeder_id=? AND pp.breed=? AND pp.status='募集中'""",
                    (p['breeder_id'], p['breed'])).fetchone()['n']
                if active_count >= 2:
                    return self.send_json({'error': 'kennel_breed_limit',
                     'message': '同じ犬舎の同じ犬種は推しワン2頭までです。'}, 409)
                t = now()
                c.execute('INSERT INTO oshiwan_entries VALUES(?,?,?)', (pid, p['breeder_id'], t))
                c.execute('INSERT INTO oshiwan_periods(puppy_id,breeder_id,started_at) VALUES(?,?,?)',
                          (pid, p['breeder_id'], t))
                audit(c, u['id'], 'oshiwan_enabled', 'puppy', pid, p['breed'] + ':3percent')
            elif not enabled and current:
                t = now()
                c.execute('UPDATE oshiwan_periods SET ended_at=? WHERE puppy_id=? AND ended_at IS NULL', (t, pid))
                c.execute('DELETE FROM oshiwan_entries WHERE puppy_id=?', (pid,))
                audit(c, u['id'], 'oshiwan_disabled', 'puppy', pid)
            c.commit()
            return self.send_json({'ok': True, 'enabled': enabled, 'feeRateBps': 300})
        except sqlite3.IntegrityError:
            c.rollback()
            return self.send_json({'error':'selection_conflict'},409)
        finally:
            c.close()

    g['Handler'].do_GET = new_get
    g['Handler'].do_POST = new_post
    print('OSHIWAN_INSTALLED|breed_slots=5|kennel_breed_limit=2|rotating=enabled|fee_rate_bps=300', flush=True)
