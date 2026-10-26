"""Independent, non-binding planned-litter interest registrations.

No puppy sale, deposit, contract or handover is initiated by these routes.
"""
import re
from datetime import date

PHASES = ('交配予定', '妊娠中', '出産予定', '子犬誕生')
STATUSES = ('受付中', '非公開', '終了')
INQUIRY_STATUSES = ('新着', '相談中', '仮予約希望', '対応終了')
PUBLIC_WHERE = "p.status='受付中' AND b.review_status='approved' AND COALESCE(b.billing_suspended,0)=0"


def init_schema(con):
    con.executescript("""
    CREATE TABLE IF NOT EXISTS planned_litters(
        id TEXT PRIMARY KEY,
        breeder_id TEXT NOT NULL REFERENCES breeders(id),
        breed TEXT NOT NULL,
        breed_key TEXT NOT NULL,
        title TEXT NOT NULL,
        phase TEXT NOT NULL,
        planned_mating TEXT NOT NULL DEFAULT '',
        expected_birth TEXT NOT NULL DEFAULT '',
        description TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT '受付中',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_planned_litters_owner
        ON planned_litters(breeder_id, created_at);
    CREATE TABLE IF NOT EXISTS planned_litter_inquiries(
        id TEXT PRIMARY KEY,
        planned_litter_id TEXT NOT NULL REFERENCES planned_litters(id),
        buyer_id TEXT NOT NULL REFERENCES users(id),
        name TEXT NOT NULL,
        email TEXT NOT NULL,
        preferred_gender TEXT NOT NULL DEFAULT 'どちらでも',
        message TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT '新着',
        created_at INTEGER NOT NULL,
        updated_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_planned_litter_inquiries
        ON planned_litter_inquiries(planned_litter_id, created_at);
    """)


def list_rows(con, condition, args=()):
    return con.execute("""
        SELECT p.*, b.kennel_name, b.prefecture
        FROM planned_litters p
        JOIN breeders b ON b.id=p.breeder_id
        WHERE """ + condition + " ORDER BY p.created_at DESC", args).fetchall()


def public_row(row):
    d = dict(row)
    return {k: d[k] for k in (
        'id', 'breeder_id', 'kennel_name', 'prefecture', 'breed', 'breed_key',
        'title', 'phase', 'planned_mating', 'expected_birth',
        'description', 'status', 'created_at')}


def authorized_breeder(con, user, requested=''):
    if user['role'] == 'breeder':
        row = con.execute("SELECT id FROM breeders WHERE user_id=? AND review_status='approved'",
                          (user['id'],)).fetchone()
    elif user['role'] == 'operator' and requested:
        row = con.execute("SELECT id FROM breeders WHERE id=? AND review_status='approved'",
                          (requested,)).fetchone()
    else:
        row = None
    return row['id'] if row else None


def validate_listing(body, check_contacts):
    if not isinstance(body, dict):
        raise ValueError('invalid_body')
    breed = str(body.get('breed') or '').strip()
    breed_key = str(body.get('breedKey') or '').strip()
    title = str(body.get('title') or '').strip()
    phase = str(body.get('phase') or '')
    description = str(body.get('description') or '').strip()
    status = str(body.get('status') or '受付中')
    if not breed or len(breed) > 80 or not re.fullmatch(r'[a-z0-9-]{1,80}', breed_key):
        raise ValueError('breed_required')
    if not title or len(title) > 80:
        raise ValueError('title_required')
    if phase not in PHASES or status not in STATUSES:
        raise ValueError('invalid_phase_or_status')
    if not description or len(description) > 1500:
        raise ValueError('description_required')
    if check_contacts(title + '\n' + description):
        raise ValueError('direct_contact_not_allowed')
    values = []
    for k in ('plannedMating', 'expectedBirth'):
        raw = str(body.get(k) or '').strip()
        if raw:
            try:
                if date.fromisoformat(raw).isoformat() != raw:
                    raise ValueError()
            except ValueError:
                raise ValueError('invalid_date')
        values.append(raw)
    return (breed, breed_key, title, phase, values[0], values[1], description, status)


def handle(h, method, path, query, ctx):
    if not (path == '/api/planned-litters' or path.startswith('/api/planned-litters/')):
        return False
    db, now = ctx['db'], ctx['now']
    # Public requests use only approved, active, unsuspended kennels.
    if method == 'GET' and path == '/api/planned-litters':
        con = db()
        rows = list_rows(con, PUBLIC_WHERE)
        con.close()
        h.send_json([public_row(row) for row in rows])
        return True
    if method == 'GET' and path == '/api/planned-litters/mine':
        user = h.require(['breeder', 'operator'])
        if not user: return True
        con = db()
        bid = authorized_breeder(con, user, (query.get('breederId') or [''])[0])
        if not bid:
            con.close()
            h.send_json({'error':'approved_breeder_required'},403)
            return True
        rows = list_rows(con, 'p.breeder_id=?', (bid,))
        con.close()
        h.send_json([public_row(row) for row in rows])
        return True
    if method == 'GET' and path == '/api/planned-litters/inquiries':
        user = h.require(['breeder', 'operator'])
        if not user: return True
        con = db()
        bid = authorized_breeder(con, user, (query.get('breederId') or [''])[0])
        if not bid:
            con.close()
            h.send_json({'error':'approved_breeder_required'},403)
            return True
        rows = con.execute("""
            SELECT i.id, i.planned_litter_id, p.title, i.name, i.email,
                   i.preferred_gender, i.message, i.status, i.created_at
            FROM planned_litter_inquiries i JOIN planned_litters p
              ON i.planned_litter_id=p.id
            WHERE p.breeder_id=?
            ORDER BY i.created_at DESC""", (bid,)).fetchall()
        con.close()
        h.send_json([dict(x) for x in rows])
        return True
    if method == 'GET':
        match = re.fullmatch(r'/api/planned-litters/([^/]+)', path)
        if match:
            con = db()
            rows = list_rows(con, PUBLIC_WHERE + ' AND p.id=?', (match.group(1),))
            con.close()
            h.send_json(public_row(rows[0]) if rows else {'error':'not_found'}, 200 if rows else 404)
            return True
    if method == 'POST' and path == '/api/planned-litters':
        user = h.require(['breeder','operator'])
        if not user: return True
        body = h.json_body()
        con = db()
        requested = str(body.get('breederId') or '') if isinstance(body,dict) else ''
        bid = authorized_breeder(con,user,requested)
        if not bid:
            con.close()
            h.send_json({'error':'approved_breeder_required'},403)
            return True
        try:
            values = validate_listing(body,ctx['public_profile_has_direct_contact'])
        except ValueError as exc:
            con.close()
            h.send_json({'error':str(exc)},400)
            return True
        lid = ctx['make_id']('pl_')
        con.execute("""INSERT INTO planned_litters
          (id,breeder_id,breed,breed_key,title,phase,planned_mating,
           expected_birth,description,status,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",(lid,bid)+values+(now(),now()))
        ctx['audit'](con,user['id'],'planned_litter_created','planned_litter',lid)
        con.commit()
        result = public_row(list_rows(con,'p.id=?',(lid,))[0])
        con.close()
        h.send_json(result,201)
        return True
    match = re.fullmatch(r'/api/planned-litters/([^/]+)', path)
    if method == 'PATCH' and match:
        user = h.require(['breeder','operator'])
        if not user: return True
        body = h.json_body()
        con = db()
        old = con.execute("SELECT * FROM planned_litters WHERE id=?",(match.group(1),)).fetchone()
        if not old:
            con.close()
            h.send_json({'error':'not_found'},404)
            return True
        bid = authorized_breeder(con,user,str(old['breeder_id']) if user['role']=='operator' else '')
        if bid != old['breeder_id']:
            con.close()
            h.send_json({'error':'forbidden'},403)
            return True
        updated = {'breed':old['breed'],'breedKey':old['breed_key'],
                   'title':old['title'],'phase':old['phase'],
                   'plannedMating':old['planned_mating'],'expectedBirth':old['expected_birth'],
                   'description':old['description'],'status':old['status']}
        if isinstance(body,dict): updated.update(body)
        try:
            values = validate_listing(updated,ctx['public_profile_has_direct_contact'])
        except ValueError as exc:
            con.close()
            h.send_json({'error':str(exc)},400)
            return True
        con.execute("""UPDATE planned_litters SET breed=?,breed_key=?,title=?,phase=?,
            planned_mating=?,expected_birth=?,description=?,status=?,updated_at=?
            WHERE id=?""",values+(now(),match.group(1)))
        ctx['audit'](con,user['id'],'planned_litter_updated','planned_litter',match.group(1))
        con.commit()
        result=public_row(list_rows(con,'p.id=?',(match.group(1),))[0])
        con.close()
        h.send_json(result)
        return True
    match = re.fullmatch(r'/api/planned-litters/([^/]+)/inquiries',path)
    if method == 'POST' and match:
        user = h.require(['buyer'])
        if not user: return True
        body = h.json_body()
        message = str(body.get('message') or '').strip() if isinstance(body,dict) else ''
        gender = str(body.get('preferredGender') or 'どちらでも') if isinstance(body,dict) else ''
        if len(message) < 10 or len(message) > 1500 or gender not in ('男の子','女の子','どちらでも'):
            h.send_json({'error':'invalid_inquiry'},400)
            return True
        con = db()
        rows = list_rows(con,PUBLIC_WHERE+' AND p.id=?',(match.group(1),))
        if not rows:
            con.close()
            h.send_json({'error':'not_accepting_inquiries'},409)
            return True
        repeated = con.execute("""SELECT 1 FROM planned_litter_inquiries
             WHERE planned_litter_id=? AND buyer_id=? AND created_at>? LIMIT 1""",
             (match.group(1),user['id'],now()-3600)).fetchone()
        if repeated:
            con.close()
            h.send_json({'error':'recent_inquiry_exists'},429)
            return True
        lid = ctx['make_id']('pli_')
        name = (str(user['last'] or '')+' '+str(user['first'] or '')).strip()
        con.execute("""INSERT INTO planned_litter_inquiries
          (id,planned_litter_id,buyer_id,name,email,preferred_gender,message,status,created_at,updated_at)
          VALUES (?,?,?,?,?,?,?,?,?,?)""",
          (lid,match.group(1),user['id'],name,user['email'],gender,message,'新着',now(),now()))
        owner = con.execute("SELECT user_id FROM breeders WHERE id=?",(rows[0]['breeder_id'],)).fetchone()
        if owner:
            con.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?)",
                (ctx['make_id']('n_'),owner['user_id'],'inquiry','予約希望の問い合わせ',
                 rows[0]['title']+'に新しい予約希望が届きました',0,now()))
        con.commit()
        if owner:
            contact = con.execute('SELECT email FROM users WHERE id=?',(owner['user_id'],)).fetchone()
            recipient=contact['email'] if contact else None
        else:
            recipient=None
        con.close()
        if recipient:
            ctx['send_mail'](recipient,'BIG PAW 予約希望の問い合わせ',
                rows[0]['title']+'に事前相談が届きました。\n\n'+
                ctx['public_url']+'/planned-litter-manage.html')
        h.send_json({'id':lid,'status':'新着'},201)
        return True
    match = re.fullmatch(r'/api/planned-litters/inquiries/([^/]+)',path)
    if method == 'PATCH' and match:
        user = h.require(['breeder','operator'])
        if not user: return True
        body = h.json_body()
        status = str(body.get('status') or '') if isinstance(body,dict) else ''
        if status not in INQUIRY_STATUSES:
            h.send_json({'error':'invalid_status'},400)
            return True
        con = db()
        inquiry = con.execute("""SELECT i.id,p.breeder_id FROM planned_litter_inquiries i
          JOIN planned_litters p ON i.planned_litter_id=p.id WHERE i.id=?""",
          (match.group(1),)).fetchone()
        if not inquiry:
            con.close()
            h.send_json({'error':'not_found'},404)
            return True
        bid=authorized_breeder(con,user,inquiry['breeder_id'] if user['role']=='operator' else '')
        if bid != inquiry['breeder_id']:
            con.close()
            h.send_json({'error':'forbidden'},403)
            return True
        con.execute("UPDATE planned_litter_inquiries SET status=?,updated_at=? WHERE id=?",
                    (status,now(),match.group(1)))
        ctx['audit'](con,user['id'],'planned_inquiry_updated','planned_inquiry',match.group(1))
        con.commit()
        con.close()
        h.send_json({'id':match.group(1),'status':status})
        return True
    h.send_json({'error':'not_found'},404)
    return True
