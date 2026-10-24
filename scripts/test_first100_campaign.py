#!/usr/bin/env python3
"""No production DB: deterministic tests of the 100-report ledger and display."""
import calendar
import os
import sqlite3
import sys
import tempfile
import threading
from datetime import datetime,timedelta,timezone
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app/backend'))
import first100_campaign as camp
JST=timezone(timedelta(hours=9))
now=int(datetime(2026,10,24,10,0,tzinfo=JST).timestamp())

def init(path):
    c=sqlite3.connect(str(path),timeout=20)
    c.row_factory=sqlite3.Row
    camp.initialize(c,now,True)
    c.commit()
    return c

with tempfile.TemporaryDirectory() as directory:
    path=Path(directory)/'isolated.sqlite3'
    c=init(path)
    assert camp.enabled(True)==True
    assert camp.enabled(False)==False
    meta=c.execute('SELECT * FROM first100_campaign_meta').fetchone()
    assert meta['starts_at']==now
    assert datetime.fromtimestamp(meta['ends_at'],JST)==datetime(2027,4,24,10,0,tzinfo=JST)
    c.close()
    # Reinitializing months later MUST not reset the campaign start and end dates.
    c=sqlite3.connect(path)
    c.row_factory=sqlite3.Row
    camp.initialize(c,now+60*86400,True)
    assert c.execute('SELECT ends_at FROM first100_campaign_meta').fetchone()['ends_at']==meta['ends_at']
    c.commit()
    assert camp.public_state(c,now,True)['remaining']==100
    assert camp.public_state(c,now,False)['status']=='inactive'
    assert not camp.claim(c,'before','b1',now-1,True)
    assert not camp.claim(c,'inactive','b1',now,False)
    for i in range(80):
        assert camp.claim(c,'deal'+str(i),'b'+str(i%7),now+i,True)
    c.commit()
    s=camp.public_state(c,now+81,True)
    assert s['remaining'] is None and s['remainingLabel']=='残りわずか・受付中',s
    assert camp.claim(c,'deal79','b2',now+81,True),'resubmission should not consume another free slot'
    assert c.execute('SELECT COUNT(*) FROM first100_campaign_claims').fetchone()[0]==80
    # Cancelled or rejected claim remains in the ledger; the quota never refills.
    for i in range(80,100):
        assert camp.claim(c,'deal'+str(i),'b1',now+i,True)
    c.commit()
    assert camp.public_state(c,now+101,True)['status']=='sold_out'
    assert camp.public_state(c,now+101,True)['remaining'] is None
    assert not camp.claim(c,'deal100','b1',now+102,True)
    assert camp.claim(c,'deal99','b1',now+102,True)
    assert c.execute('SELECT COUNT(*) FROM first100_campaign_claims').fetchone()[0]==100
    # Simulate cancellation by not deleting from claims: still 100 used.
    assert not camp.claim(c,'cancel_replacement','b1',now+103,True)
    assert camp.public_state(c,meta['ends_at']+1,True)['status']=='sold_out'
    c.close()

    # Simultaneous submissions from distinct breeders must never exceed 100.
    path2=Path(directory)/'concurrent.sqlite3'
    c=init(path2);c.close()
    successes=[]
    errors=[]
    def worker(i):
        try:
            conn=sqlite3.connect(path2,timeout=20)
            conn.row_factory=sqlite3.Row
            conn.execute('BEGIN IMMEDIATE')
            result=camp.claim(conn,'parallel'+str(i),'breeder'+str(i),now+i,True)
            conn.commit();conn.close()
            successes.append(result)
        except Exception as e: errors.append(e)
    threads=[threading.Thread(target=worker,args=(i,)) for i in range(108)]
    for t in threads:t.start()
    for t in threads:t.join()
    assert not errors,errors
    assert sum(successes)==100,('expected 100 accepted',sum(successes))
    c=sqlite3.connect(path2)
    assert c.execute('SELECT COUNT(*) FROM first100_campaign_claims').fetchone()[0]==100
    c.close()

    # No rounding/overflow on six calendar months, including leap years.
    feb29=int(datetime(2024,8,31,12,0,tzinfo=JST).timestamp())
    assert datetime.fromtimestamp(camp.six_months_later(feb29),JST)==datetime(2025,2,28,12,0,tzinfo=JST)
    print('FIRST100_CAMPAIGN_LEDGER_OK|100_max|20_hide|cancel_no_restore|idempotency|6_calendar_months|concurrency|no_production_data')
