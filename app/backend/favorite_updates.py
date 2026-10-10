"""Optional, consent-based updates and aggregate puppy engagement for BIG PAW.

No buyer identity is exposed to breeders. Email sending is delayed and deduplicated
per puppy/update burst, and only delivered to verified opted-in buyers.
"""
from __future__ import annotations
import hashlib
import html
import json
import os
import re
import smtplib
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from email.message import EmailMessage

QUIET_SECONDS = 600
RETRY_SECONDS = 1800
MAX_ATTEMPTS = 3

def ensure_schema(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS favorite_change_batches (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      puppy_id TEXT NOT NULL,
      kinds TEXT NOT NULL DEFAULT '[]',
      first_price INTEGER,
      new_price INTEGER,
      photo_url TEXT NOT NULL DEFAULT '',
      status TEXT NOT NULL DEFAULT 'pending',
      created_at INTEGER NOT NULL,
      updated_at INTEGER NOT NULL,
      due_at INTEGER NOT NULL,
      FOREIGN KEY(puppy_id) REFERENCES puppies(id) ON DELETE CASCADE
    );
    CREATE UNIQUE INDEX IF NOT EXISTS favorite_one_pending_per_puppy
      ON favorite_change_batches(puppy_id) WHERE status='pending';
    CREATE TABLE IF NOT EXISTS favorite_update_deliveries (
      batch_id INTEGER NOT NULL REFERENCES favorite_change_batches(id) ON DELETE CASCADE,
      user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
      status TEXT NOT NULL DEFAULT 'retry',
      attempts INTEGER NOT NULL DEFAULT 0,
      updated_at INTEGER NOT NULL,
      PRIMARY KEY(batch_id,user_id)
    );
    CREATE TABLE IF NOT EXISTS puppy_page_views (
      puppy_id TEXT NOT NULL REFERENCES puppies(id) ON DELETE CASCADE,
      visitor_hash TEXT NOT NULL,
      viewed_day TEXT NOT NULL,
      page_loads INTEGER NOT NULL DEFAULT 0,
      PRIMARY KEY(puppy_id,visitor_hash,viewed_day)
    );
    CREATE INDEX IF NOT EXISTS puppy_view_by_puppy ON puppy_page_views(puppy_id);
    """)

def queue_change(con, puppy_id, kind, *, photo_url='', old_price=None, new_price=None, timestamp=None):
    """Coalesce multiple saved edits and photo uploads before mailing anyone."""
    when=int(time.time() if timestamp is None else timestamp)
    if kind not in ('price','photo','description','status'): return False
    puppy=con.execute("SELECT id FROM puppies WHERE id=? AND review_status='approved'",(puppy_id,)).fetchone()
    if not puppy: return False
    item=con.execute("SELECT * FROM favorite_change_batches WHERE puppy_id=? AND status='pending'",(puppy_id,)).fetchone()
    if item:
        kinds=list(dict.fromkeys(json.loads(item['kinds'])+[kind]))
        first=item['first_price'] if item['first_price'] is not None else old_price
        newer=new_price if new_price is not None else item['new_price']
        photo=photo_url or item['photo_url'] or ''
        con.execute("""UPDATE favorite_change_batches SET kinds=?, first_price=?,new_price=?,
            photo_url=?,updated_at=?,due_at=? WHERE id=?""",
            (json.dumps(kinds),first,newer,photo,when,when+QUIET_SECONDS,item['id']))
    else:
        con.execute("""INSERT INTO favorite_change_batches
            (puppy_id,kinds,first_price,new_price,photo_url,status,created_at,updated_at,due_at)
            VALUES(?,?,?,?,?,'pending',?,?,?)""",
            (puppy_id,json.dumps([kind]),old_price,new_price,photo_url or '',when,when,when+QUIET_SECONDS))
    return True

def record_view(con, puppy_id, visitor_id, ip='', user_agent='', timestamp=None):
    """Count page loads separately from estimated unique browsers."""
    if not re.fullmatch(r'[a-zA-Z0-9_-]{12,96}',str(visitor_id or '')):
        # Anonymous browsers without durable local storage get a privacy-safe
        # fallback key. This remains an estimate, not a verified person.
        visitor_id='anonymous:'+str(ip)[:64]+':'+str(user_agent)[:100]
    secret=os.environ.get('BIGPAW_VIEW_HASH_SECRET') or os.environ.get('BIGPAW_ADMIN_PASSWORD') or 'bigpaw-public-view-counter'
    fingerprint=hashlib.sha256((secret+'|'+visitor_id).encode('utf-8')).hexdigest()
    timestamp=int(time.time() if timestamp is None else timestamp)
    day=time.strftime('%Y-%m-%d',time.gmtime(timestamp+9*3600))
    found=con.execute("SELECT 1 FROM puppies WHERE id=? AND review_status='approved'",(puppy_id,)).fetchone()
    if not found: return False
    con.execute("""INSERT INTO puppy_page_views(puppy_id,visitor_hash,viewed_day,page_loads) VALUES(?,?,?,1)
        ON CONFLICT(puppy_id,visitor_hash,viewed_day)
        DO UPDATE SET page_loads=page_loads+1""",(puppy_id,fingerprint,day))
    return True

def engagement(con, breeder_id):
    """Private aggregated counts scoped to one breeder, never buyer emails/IDs."""
    rows=con.execute("SELECT id FROM puppies WHERE breeder_id=?",(breeder_id,)).fetchall()
    result={r['id']:{'favoriteCount':0,'viewCount':0,'viewerCount':0} for r in rows}
    for r in con.execute("""SELECT f.puppy_id,COUNT(*) AS n FROM favorites f
            JOIN puppies p ON p.id=f.puppy_id WHERE p.breeder_id=?
            GROUP BY f.puppy_id""",(breeder_id,)):
        result[r['puppy_id']]['favoriteCount']=r['n']
    for r in con.execute("""SELECT v.puppy_id,SUM(v.page_loads) AS n,
            COUNT(DISTINCT v.visitor_hash) AS people
            FROM puppy_page_views v JOIN puppies p ON p.id=v.puppy_id
            WHERE p.breeder_id=? GROUP BY v.puppy_id""",(breeder_id,)):
        result[r['puppy_id']]['viewCount']=r['n']
        result[r['puppy_id']]['viewerCount']=r['people']
    return result

def picture_url(raw, base):
    raw=str(raw or '').strip()
    if not raw: return ''
    if raw.startswith('/') and not raw.startswith('//'):
        if raw.startswith('/uploads/') and not re.search(r'[\x00-\x1f<>"\x27]',raw):
            return base.rstrip('/')+raw
        return ''
    url=urllib.parse.urlsplit(raw)
    if url.scheme=='https' and url.hostname and not url.username and not url.password:
        return raw
    return ''

def mail_content(puppy,batch,base):
    kinds=json.loads(batch['kinds'])
    # An interim price edit reverted before the email isn't a price change.
    if 'price' in kinds and batch['first_price'] is not None and int(puppy['price'])==int(batch['first_price']):
        kinds=[x for x in kinds if x!='price']
    if not kinds: return None
    labels={'price':'価格','photo':'写真','description':'紹介文','status':'募集状況'}
    changed='・'.join(labels[k] for k in kinds if k in labels)
    name=str(puppy['breed'] or '子犬')+'・'+str(puppy['name'] or '')
    status=str(puppy['status'] or '')
    price=str(int(puppy['price'])).replace(',','')
    new_price=f"{int(price):,}円"
    image=picture_url(batch['photo_url'] if 'photo' in kinds else '',base) or picture_url(puppy['image_url'],base)
    link=base.rstrip('/')+'/puppy-detail.html?id='+urllib.parse.quote(str(puppy['id']),safe='')
    settings=base.rstrip('/')+'/account.html'
    subject='【BIG PAW】お気に入りのワンちゃんの情報が更新されました'
    parts=[f"お気に入りに登録された {name} の情報が更新されました。",f"更新内容：{changed}"]
    if 'price' in kinds and batch['first_price'] is not None:
        parts.append(f"価格：{int(batch['first_price']):,}円 → {new_price}")
    else:
        parts.append(f"現在の価格：{new_price}")
    parts.extend([f"募集状況：{status}",f"詳しく見る：{link}",f"通知設定：{settings}"])
    plain='\n'.join(parts)
    safe=lambda x: html.escape(str(x),quote=True)
    details=(f'<p style="margin:8px 0"><strong>価格：{safe(f"{int(batch[\'first_price\']):,}円")} → {safe(new_price)}</strong></p>'
        if 'price' in kinds and batch['first_price'] is not None else
        f'<p style="margin:8px 0">現在の価格：<strong>{safe(new_price)}</strong></p>')
    photo_html=(f'<a href="{safe(link)}"><img src="{safe(image)}" alt="{safe(name)}" '
        'style="width:100%;max-width:440px;height:auto;border-radius:14px;display:block;border:0"></a>'
        if image else '')
    markup=('<!doctype html><html lang="ja"><body style="margin:0;background:#fff7fb;font-family:sans-serif;color:#4b4050">'
        '<div style="max-width:520px;margin:auto;padding:28px 20px;background:white">'
        '<h2 style="color:#c34d7e;margin-top:0">BIG PAW 🐾</h2>'
        '<p>お気に入りのワンちゃんの新しい情報が届きました！</p>'
        +photo_html+f'<h3>{safe(name)}</h3><p>更新内容：{safe(changed)}</p>'
        +details+f'<p>募集状況：{safe(status)}</p>'
        +f'<p><a href="{safe(link)}" style="display:inline-block;background:#c34d7e;color:white;padding:13px 20px;border-radius:9px;text-decoration:none">ワンちゃんの最新情報を見る</a></p>'
        +f'<p style="font-size:12px;color:#777">通知の停止・変更：<a href="{safe(settings)}">アカウント設定</a></p>'
        '</div></body></html>')
    return subject,plain,markup

def send_rich_mail(address, subject, plain, markup):
    """Transport matches the site's existing Resend-first/SMTP-fallback mail."""
    key=(os.environ.get('RESEND_API_KEY') or '').strip()
    if key:
        try:
            data=json.dumps({'from':'BIG PAW <noreply@bigpaw.site>','to':[address],
                'subject':subject,'text':plain,'html':markup},ensure_ascii=False).encode('utf-8')
            req=urllib.request.Request('https://api.resend.com/emails',data=data,method='POST',
                headers={'Authorization':'Bearer '+key,'Content-Type':'application/json'})
            with urllib.request.urlopen(req,timeout=12) as resp:
                if 200<=resp.status<300:return True
        except Exception as exc:
            print('[favorite-mail] Resend:',type(exc).__name__,flush=True)
    host=(os.environ.get('SMTP_HOST') or os.environ.get('BIGPAW_SMTP_HOST') or '').strip()
    port=int(os.environ.get('SMTP_PORT') or os.environ.get('BIGPAW_SMTP_PORT') or 587)
    username=(os.environ.get('SMTP_USER') or os.environ.get('BIGPAW_SMTP_USER') or '').strip()
    password=(os.environ.get('SMTP_PASSWORD') or os.environ.get('BIGPAW_SMTP_PASSWORD') or '').strip()
    sender=(os.environ.get('SMTP_FROM') or os.environ.get('BIGPAW_SMTP_FROM') or username).strip()
    if not(host and username and password and sender):return False
    try:
        msg=EmailMessage()
        msg['From']=sender;msg['To']=address;msg['Subject']=subject
        msg.set_content(plain);msg.add_alternative(markup,subtype='html')
        ctx=ssl.create_default_context()
        if port==465: client=smtplib.SMTP_SSL(host,port,timeout=20,context=ctx)
        else:
            client=smtplib.SMTP(host,port,timeout=20)
            client.ehlo();client.starttls(context=ctx);client.ehlo()
        with client:
            client.login(username,password);client.send_message(msg)
        return True
    except Exception as exc:
        print('[favorite-mail] SMTP:',type(exc).__name__,flush=True)
        return False

def deliver_due(db_connect, base_url, sender=None, timestamp=None, limit=12):
    """Send no more than one digest per buyer and batch; retry failed sends."""
    sender=sender or send_rich_mail
    when=int(time.time() if timestamp is None else timestamp)
    con=db_connect(); processed=0; sent=0; failed=0
    try:
        batches=con.execute("""SELECT * FROM favorite_change_batches
            WHERE status='pending' AND due_at<=? ORDER BY due_at LIMIT ?""",(when,limit)).fetchall()
        for batch in batches:
            claimed=con.execute("""UPDATE favorite_change_batches SET status='sending'
                WHERE id=? AND status='pending'""",(batch['id'],)).rowcount
            con.commit()
            if not claimed:continue
            puppy=con.execute("""SELECT p.* FROM puppies p
              LEFT JOIN breeders b ON b.id=p.breeder_id WHERE p.id=?
              AND p.review_status='approved'
              AND (p.breeder_id IS NULL OR (b.review_status='approved' AND COALESCE(b.billing_suspended,0)=0))""",
              (batch['puppy_id'],)).fetchone()
            content=mail_content(puppy,batch,base_url) if puppy else None
            if not content:
                con.execute("UPDATE favorite_change_batches SET status='done' WHERE id=?",(batch['id'],))
                con.commit();processed+=1;continue
            recipients=con.execute("""SELECT u.id,u.email FROM favorites f
              JOIN users u ON u.id=f.user_id WHERE f.puppy_id=?
              AND u.role='buyer' AND u.email_verified=1 AND u.favorite_email_enabled=1""",(batch['puppy_id'],)).fetchall()
            needs_retry=False
            for user in recipients:
                row=con.execute("SELECT status,attempts FROM favorite_update_deliveries WHERE batch_id=? AND user_id=?",
                    (batch['id'],user['id'])).fetchone()
                if row and (row['status']=='sent' or row['attempts']>=MAX_ATTEMPTS):continue
                attempts=(int(row['attempts']) if row else 0)+1
                # Record attempt before sending: protects against repeated mails if a worker dies.
                con.execute("""INSERT INTO favorite_update_deliveries(batch_id,user_id,status,attempts,updated_at)
                  VALUES(?,?,'sending',?,?)
                  ON CONFLICT(batch_id,user_id) DO UPDATE SET
                  status='sending',attempts=excluded.attempts,updated_at=excluded.updated_at""",
                  (batch['id'],user['id'],attempts,when))
                con.commit()
                ok=False
                try:ok=bool(sender(user['email'],*content))
                except Exception as exc:print('[favorite-mail] delivery:',type(exc).__name__,flush=True)
                if ok: sent+=1
                else:
                    failed+=1
                    if attempts<MAX_ATTEMPTS:needs_retry=True
                con.execute("UPDATE favorite_update_deliveries SET status=?,updated_at=? WHERE batch_id=? AND user_id=?",
                    ('sent' if ok else 'retry' if attempts<MAX_ATTEMPTS else 'failed',when,batch['id'],user['id']))
                con.commit()
            if needs_retry:
                # A new pending batch may have appeared while this was sending.
                # Keep the old batch in 'sending', retry it on the next pass below.
                con.execute("UPDATE favorite_change_batches SET status='retry_wait',due_at=? WHERE id=?",
                    (when+RETRY_SECONDS,batch['id']))
            else:
                con.execute("UPDATE favorite_change_batches SET status='done' WHERE id=?",(batch['id'],))
            con.commit();processed+=1
        retry=con.execute("SELECT id FROM favorite_change_batches WHERE status='retry_wait' AND due_at<=? LIMIT ?",(when,limit)).fetchall()
        for item in retry:
            # Retrying batches use unique row id, while pending can collect newer edits.
            con.execute("UPDATE favorite_change_batches SET status='pending' WHERE id=? AND NOT EXISTS (SELECT 1 FROM favorite_change_batches v WHERE v.puppy_id=(SELECT puppy_id FROM favorite_change_batches WHERE id=?) AND v.status='pending')",(item['id'],item['id']))
        con.commit()
        return {'batches':processed,'sent':sent,'failed':failed}
    finally: con.close()
