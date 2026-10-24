"""BIG PAW site-wide 100-report launch campaign.

Exactly one claim per valid breeder sale report. Claims are never deleted on
cancellation. Transaction locking is provided by the caller's BEGIN IMMEDIATE.
Campaign clock starts once on first enabled production DB initialization;
redeployments must never reset the six-calendar-month window.
"""
import calendar
import os
from datetime import datetime, timedelta, timezone

JST = timezone(timedelta(hours=9))
LIMIT = 100
HIDE_THRESHOLD = 20

SCHEMA = """
CREATE TABLE IF NOT EXISTS first100_campaign_meta(
  id INTEGER PRIMARY KEY CHECK(id=1),
  starts_at INTEGER NOT NULL,
  ends_at INTEGER NOT NULL
);
CREATE TABLE IF NOT EXISTS first100_campaign_claims(
  deal_id TEXT PRIMARY KEY,
  breeder_id TEXT NOT NULL,
  claimed_at INTEGER NOT NULL
);
CREATE INDEX IF NOT EXISTS first100_campaign_claims_at
  ON first100_campaign_claims(claimed_at);
"""

def enabled(is_production):
    # Opt out explicitly if emergency rollback is needed; dev tests keep old pricing.
    raw = os.environ.get('BIGPAW_CAMPAIGN_100_ENABLED')
    return raw == '1' if raw is not None else bool(is_production)

def six_months_later(start):
    d = datetime.fromtimestamp(start, JST)
    month_index = (d.year * 12 + d.month - 1) + 6
    y, m = divmod(month_index, 12)
    m += 1
    day = min(d.day, calendar.monthrange(y, m)[1])
    return int(d.replace(year=y, month=m, day=day).timestamp())

def initialize(c, timestamp, active):
    c.executescript(SCHEMA)
    if active:
        c.execute('INSERT OR IGNORE INTO first100_campaign_meta(id,starts_at,ends_at) VALUES(1,?,?)',
                  (timestamp, six_months_later(timestamp)))

def claim(c, deal_id, breeder_id, timestamp, active):
    if not active:
        return False
    prior = c.execute('SELECT 1 FROM first100_campaign_claims WHERE deal_id=?', (deal_id,)).fetchone()
    if prior:
        return True
    meta = c.execute('SELECT starts_at,ends_at FROM first100_campaign_meta WHERE id=1').fetchone()
    if not meta or not (meta['starts_at'] <= timestamp < meta['ends_at']):
        return False
    used = c.execute('SELECT COUNT(*) AS n FROM first100_campaign_claims').fetchone()['n']
    if used >= LIMIT:
        return False
    c.execute('INSERT INTO first100_campaign_claims(deal_id,breeder_id,claimed_at) VALUES(?,?,?)',
              (deal_id, breeder_id, timestamp))
    return True

def claimed(c, deal_id):
    return bool(c.execute('SELECT 1 FROM first100_campaign_claims WHERE deal_id=?',
                          (deal_id,)).fetchone())

def public_state(c, timestamp, active):
    meta = c.execute('SELECT starts_at,ends_at FROM first100_campaign_meta WHERE id=1').fetchone()
    if not active or not meta:
        return {'status':'inactive','limit':LIMIT,'eligible':False}
    used = c.execute('SELECT COUNT(*) AS n FROM first100_campaign_claims').fetchone()['n']
    remaining = max(0,LIMIT-used)
    if used >= LIMIT:
        status = 'sold_out'
    elif timestamp < meta['starts_at']:
        status = 'upcoming'
    elif timestamp >= meta['ends_at']:
        status = 'ended'
    else:
        status = 'active'
    return {
        'status':status,
        'limit':LIMIT,
        'eligible':status=='active',
        'startsAt':meta['starts_at'],
        'endsAt':meta['ends_at'],
        'remaining':remaining if status=='active' and remaining>HIDE_THRESHOLD else None,
        'remainingLabel':(
            str(remaining)+'頭' if status=='active' and remaining>HIDE_THRESHOLD
            else '残りわずか・受付中' if status=='active' and remaining>0
            else '終了'
        ),
        'standardRateWaived':500,
        'oshiwanExtraRateBps':300,
        'cancelledClaimsReopen':False
    }
