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
    CREATE TABLE IF NOT EXISTS planned_litter_links(
        planned_inquiry_id TEXT PRIMARY KEY REFERENCES planned_litter_inquiries(id),
        inquiry_id TEXT NOT NULL UNIQUE REFERENCES inquiries(id),
        puppy_id TEXT NOT NULL REFERENCES puppies(id),
        linked_by TEXT NOT NULL REFERENCES users(id),
        linked_at INTEGER NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_planned_litter_links_puppy
        ON planned_litter_links(puppy_id);
    """)


def list_rows(con, condition, args=()):
    return con.execute("""
        SELECT p.*, b.kennel_name, b.prefecture
        FROM planned_litters p
        JOIN breeders b ON b.id=p.breeder_id
        WHERE """ + condition + " ORDER BY p.created_at DESC", args).fetchall()


def public_row(row):
    d = dict(row)
    # Follow the existing BIG PAW policy: public pages do not reveal kennel identity.
    d['kennel_name'] = (d.get('prefecture') or '') + 'のBIGPAW認定ブリーダー'
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
    if re.search(r'(?:都|道|府|県).{0,24}(?:市|区|郡|町|村).{0,24}(?:[0-9０-９]|丁目|番地|番|号)', title+'\n'+description):
        raise ValueError('private_location_not_allowed')
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


def no_private_kennel_name(con, breeder_id, values):
    row=con.execute('SELECT kennel_name FROM breeders WHERE id=?',(breeder_id,)).fetchone()
    name=str(row['kennel_name'] or '').strip() if row else ''
    text=values[2]+'\n'+values[6]
    return not (len(name)>=2 and name.lower() in text.lower())


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
    if method == 'GET' and path == '/api/planned-litters/operator/overview':
        user = h.require(['operator'])
        if not user: return True
        con = db()
        rows = con.execute("""
            SELECT i.id, i.planned_litter_id, i.buyer_id, i.name, i.email,
                   i.preferred_gender, i.status, i.created_at,
                   p.breeder_id, p.title, p.expected_birth, p.phase,
                   p.status AS listing_status, b.kennel_name,
                   l.puppy_id AS linked_puppy_id, l.inquiry_id AS linked_inquiry_id,
                   pup.name AS linked_puppy_name, d.id AS linked_deal_id,
                   d.status AS linked_deal_status
            FROM planned_litter_inquiries i
            JOIN planned_litters p ON p.id=i.planned_litter_id
            JOIN breeders b ON b.id=p.breeder_id
            LEFT JOIN planned_litter_links l ON l.planned_inquiry_id=i.id
            LEFT JOIN puppies pup ON pup.id=l.puppy_id
            LEFT JOIN deals d ON d.inquiry_id=l.inquiry_id
            ORDER BY i.created_at DESC LIMIT 500""").fetchall()
        con.close()
        h.send_json([dict(r) for r in rows])
        return True
    # The original buyer and litter inquiry remain permanent audit context.
    # This conversion only creates a normal puppy inquiry, NOT a deal/payment/reservation.
    match_link = re.fullmatch(r'/api/planned-litters/inquiries/([^/]+)/link-puppy', path)
    if method == 'POST' and match_link:
        user = h.require(['breeder', 'operator'])
        if not user: return True
        body = h.json_body()
        puppy_id = str(body.get('puppyId') or '').strip() if isinstance(body, dict) else ''
        if not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}', puppy_id):
            h.send_json({'error':'puppy_required','message':'生まれた子犬を選択してください。'},400)
            return True
        con = db()
        try:
            con.execute('BEGIN IMMEDIATE')
            old = con.execute("""
                SELECT i.*, p.breeder_id, p.breed_key, p.title
                FROM planned_litter_inquiries i JOIN planned_litters p
                ON p.id=i.planned_litter_id WHERE i.id=?""",(match_link.group(1),)).fetchone()
            if not old:
                h.send_json({'error':'not_found'},404)
                return True
            bid = authorized_breeder(con,user,old['breeder_id'] if user['role']=='operator' else '')
            if bid != old['breeder_id']:
                h.send_json({'error':'forbidden'},403)
                return True
            existing = con.execute("SELECT * FROM planned_litter_links WHERE planned_inquiry_id=?",
                                   (old['id'],)).fetchone()
            if existing:
                if existing['puppy_id']!=puppy_id:
                    h.send_json({'error':'already_linked','message':'この予約希望は別の子犬に紐付け済みです。変更が必要な場合は運営にご相談ください。'},409)
                else:
                    h.send_json({'ok':True,'alreadyLinked':True,'inquiryId':existing['inquiry_id'],
                                 'puppyId':existing['puppy_id']})
                return True
            puppy = con.execute("SELECT id,breeder_id,name,breed_key,status FROM puppies WHERE id=?",
                                (puppy_id,)).fetchone()
            if not puppy or puppy['breeder_id']!=bid:
                h.send_json({'error':'puppy_not_in_kennel','message':'この犬舎に登録された子犬を選んでください。'},403)
                return True
            if puppy['status']=='成約済み':
                h.send_json({'error':'puppy_already_sold','message':'成約済みの子犬には紐付けられません。'},409)
                return True
            if old['breed_key'] and puppy['breed_key'] and old['breed_key']!=puppy['breed_key']:
                h.send_json({'error':'breed_mismatch','message':'出産予定と犬種が一致する子犬を選んでください。'},409)
                return True
            qid = ctx['make_id']('q_')
            message = '出産予定「'+old['title']+'」の予約希望から引き継ぎ：\n'+old['message']
            con.execute("""
                INSERT INTO inquiries
                  (id,puppy_id,buyer_id,breeder_id,name,email,phone,preferred_date,message,status,created_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (qid,puppy['id'],old['buyer_id'],bid,old['name'],old['email'],'','',
                 message,'未返信',now()))
            con.execute("""INSERT INTO planned_litter_links
                (planned_inquiry_id,inquiry_id,puppy_id,linked_by,linked_at)
                VALUES(?,?,?,?,?)""",(old['id'],qid,puppy['id'],user['id'],now()))
            if old['status']=='新着':
                con.execute("UPDATE planned_litter_inquiries SET status='相談中',updated_at=? WHERE id=?",
                            (now(),old['id']))
            con.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?)",
                        (ctx['make_id']('n_'),old['buyer_id'],'inquiry','出産予定から子犬のご案内',
                         '予約希望をいただいた出産予定から子犬「'+puppy['name']+'」のご案内に進みました。購入・予約の確約や決済は発生していません。',0,now()))
            ctx['audit'](con,user['id'],'planned_inquiry_linked_to_puppy','planned_inquiry',old['id'],qid)
            con.commit()
            h.send_json({'ok':True,'alreadyLinked':False,'inquiryId':qid,'puppyId':puppy['id']},201)
            return True
        finally:
            con.close()
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
            SELECT i.id, i.planned_litter_id, p.title, p.breed_key, i.name, i.email,
                   i.preferred_gender, i.message, i.status, i.created_at,
                   l.puppy_id AS linked_puppy_id, l.inquiry_id AS linked_inquiry_id,
                   pup.name AS linked_puppy_name, d.id AS linked_deal_id,
                   d.status AS linked_deal_status
            FROM planned_litter_inquiries i JOIN planned_litters p
              ON i.planned_litter_id=p.id
            LEFT JOIN planned_litter_links l ON l.planned_inquiry_id=i.id
            LEFT JOIN puppies pup ON pup.id=l.puppy_id
            LEFT JOIN deals d ON d.inquiry_id=l.inquiry_id
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
        if not no_private_kennel_name(con,bid,values):
            con.close()
            h.send_json({'error':'private_kennel_name_not_allowed'},400)
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
    if method == 'DELETE' and match:
        user = h.require(['breeder','operator'])
        if not user: return True
        con = db()
        old = con.execute("SELECT id,breeder_id FROM planned_litters WHERE id=?", (match.group(1),)).fetchone()
        if not old:
            con.close()
            h.send_json({'error':'not_found'},404)
            return True
        bid = authorized_breeder(con,user,str(old['breeder_id']) if user['role']=='operator' else '')
        if bid != old['breeder_id']:
            con.close()
            h.send_json({'error':'forbidden'},403)
            return True
        if con.execute("SELECT 1 FROM planned_litter_inquiries WHERE planned_litter_id=? LIMIT 1", (old['id'],)).fetchone():
            con.close()
            h.send_json({'error':'planned_litter_has_inquiries',
                         'message':'予約希望・事前相談の履歴があるため削除できません。「非公開」または「終了」に変更してください。'},409)
            return True
        con.execute("DELETE FROM planned_litters WHERE id=? AND breeder_id=?", (old['id'],bid))
        ctx['audit'](con,user['id'],'planned_litter_deleted','planned_litter',old['id'])
        con.commit()
        con.close()
        h.send_json({'ok':True,'id':old['id']})
        return True
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
        if not no_private_kennel_name(con,bid,values):
            con.close()
            h.send_json({'error':'private_kennel_name_not_allowed'},400)
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
        operators = con.execute("SELECT id,email FROM users WHERE role='operator'").fetchall()
        for op in operators:
            con.execute("INSERT INTO notifications VALUES(?,?,?,?,?,?,?)",
                        (ctx['make_id']('n_'),op['id'],'inquiry','新しい出産予定の予約希望',
                         rows[0]['title']+'に予約希望が届きました。運営の予約希望追跡から確認してください。',0,now()))
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
        for op in operators:
            if op['email'] and op['email']!=recipient:
                ctx['send_mail'](op['email'],'BIG PAW 出産予定への予約希望（運営確認）',
                    rows[0]['title']+'に予約希望が入りました。\n\n'+
                    ctx['public_url']+'/operator-planned-litter-inquiries.html')
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
